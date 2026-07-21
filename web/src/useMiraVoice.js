import { useCallback, useRef, useState } from "react";
import { MicCapture, PcmPlayer } from "./audio.js";
import { AvatarState, Mood } from "./avatarState.js";
import { supabase } from "./supabaseClient.js";

function resolveWsUrl() {
  const override = import.meta.env.VITE_MIRA_WS_URL;
  if (override) return override;
  if (typeof window !== "undefined") {
    const { host, protocol } = window.location;
    const wsProto = protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${host}/mira-ws`;
  }
  return "ws://localhost:8765";
}

const WS_URL = resolveWsUrl();

// message shape: { id, role: 'you'|'mira', text, products?: [], ts }
let _msgId = 0;
const mkId = () => ++_msgId;

export function useMiraVoice({ userId, userName, userPrefs = null, eventBrief = null, textMode = false } = {}) {
  const [connected, setConnected] = useState(false);
  const [state, setState] = useState(AvatarState.IDLE);
  const [mood, setMood] = useState(Mood.NEUTRAL);
  const [captions, setCaptions] = useState({ you: "", mira: "" });
  const [products, setProducts] = useState([]);
  const [loved, setLoved] = useState(() => new Set());
  const [savedProducts, setSavedProducts] = useState([]);
  const [highlightedId, setHighlightedId] = useState(null);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [miraText, setMiraText] = useState(null);
  const [canShowMore, setCanShowMore] = useState(false);
  const [looks, setLooks] = useState([]);

  // Full chat history — always built regardless of voice/text mode
  const [messages, setMessages] = useState([]);
  // ref to the id of the bubble Mira is currently streaming into
  const miraBubbleId = useRef(null);

  // Product timeline — each item records which message bubble it came from
  const [productTimeline, setProductTimeline] = useState([]);

  // Keep a live ref to textMode so WS handlers see mid-session switches
  const textModeRef = useRef(textMode);
  textModeRef.current = textMode;

  const wsRef = useRef(null);
  const micRef = useRef(null);
  const playerRef = useRef(null);

  const stop = useCallback(() => {
    micRef.current?.stop();
    playerRef.current?.flush();
    wsRef.current?.close();
    micRef.current = playerRef.current = wsRef.current = null;
    setConnected(false);
    setState(AvatarState.IDLE);
    setMood(Mood.NEUTRAL);
    miraBubbleId.current = null;
  }, []);

  // Add a message to the chat thread
  const _addMsg = (role, text) => {
    const id = mkId();
    setMessages((prev) => [...prev, { id, role, text, products: [], ts: new Date() }]);
    return id;
  };

  // Append text to an existing bubble (streaming)
  const _appendMsg = (id, chunk) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, text: m.text + chunk } : m))
    );
  };

  // Attach product cards to the bubble they were mentioned in
  const _attachProducts = (id, items) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== id) return m;
        const seen = new Set(m.products.map((p) => p.id));
        const fresh = items.filter((p) => !seen.has(p.id));
        return fresh.length ? { ...m, products: [...m.products, ...fresh] } : m;
      })
    );
  };

  // Send a typed message
  const sendText = useCallback((text) => {
    const ws = wsRef.current;
    const trimmed = (text || "").trim();
    if (!ws || ws.readyState !== WebSocket.OPEN || !trimmed) return;
    // Optimistically add the user bubble immediately
    _addMsg("you", trimmed);
    ws.send(JSON.stringify({ type: "text_input", text: trimmed }));
    setState(AvatarState.THINKING);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const wouldBuy = useCallback((product) => {
    setLoved((prev) => {
      const isLoved = prev.has(product.id);
      const ws = wsRef.current;

      // Always persist directly to Supabase so unlike survives after session ends
      if (userId) {
        if (isLoved) {
          supabase.from("user_history")
            .delete()
            .eq("user_id", userId)
            .eq("product_id", product.id)
            .in("action", ["would_buy", "wishlist"])
            .then(({ error }) => { if (error) console.error("unlike:", error); });
        } else {
          supabase.from("user_history")
            .insert({ user_id: userId, product_id: product.id, action: "would_buy", ts: new Date().toISOString() })
            .then(({ error }) => { if (error) console.error("save:", error); });
        }
      }

      // Also notify server (for in-session context injection)
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: isLoved ? "unlike" : "would_buy", product_id: product.id }));
      }

      if (isLoved) {
        setSavedProducts((sp) => sp.filter((p) => p.id !== product.id));
        const next = new Set(prev); next.delete(product.id); return next;
      } else {
        setSavedProducts((sp) => sp.find((p) => p.id === product.id) ? sp : [...sp, product]);
        return new Set(prev).add(product.id);
      }
    });
  }, [userId]);

  const getLevel = useCallback(() => playerRef.current?.getLevel?.() ?? 0, []);

  const buyClick = useCallback((product) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN)
      ws.send(JSON.stringify({ type: "buy_click", product_id: product.id }));
  }, []);

  const showMore = useCallback(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      setCanShowMore(false);
      ws.send(JSON.stringify({ type: "show_more" }));
    }
  }, []);

  // Switch audio on/off mid-session without restarting the WebSocket
  const switchAudio = useCallback(async (enableAudio) => {
    if (enableAudio && !micRef.current) {
      const mic = new MicCapture((bytes) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(bytes);
      });
      micRef.current = mic;
      try { await mic.start(); } catch { setError("Mic permission denied"); }
      if (!playerRef.current) playerRef.current = new PcmPlayer();
    } else if (!enableAudio) {
      micRef.current?.stop();
      micRef.current = null;
      playerRef.current?.flush();
      playerRef.current = null; // null so binary frames are silently dropped
    }
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setMessages([]);
    setLooks([]);
    setProductTimeline([]);
    miraBubbleId.current = null;
    try {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      if (!textMode) playerRef.current = new PcmPlayer();

      ws.onopen = async () => {
        if (userId)
          ws.send(JSON.stringify({
            type:           "init",
            user_id:        userId,
            name:           userName || "there",
            style_vibe:     userPrefs?.style_vibe     ?? null,
            shopping_focus: userPrefs?.shopping_focus ?? null,
            top_size:       userPrefs?.top_size       ?? null,
            bottom_size:    userPrefs?.bottom_size    ?? null,
            budget:         userPrefs?.budget         ?? null,
            event_brief:    eventBrief,
          }));
        setConnected(true);
        setCanShowMore(true); // always show browse button once connected (1000+ products available)
        if (!textMode) {
          const mic = new MicCapture((bytes) => {
            if (ws.readyState === WebSocket.OPEN) ws.send(bytes);
          });
          micRef.current = mic;
          try { await mic.start(); }
          catch { setError("Mic permission denied"); stop(); }
        }
      };

      ws.onmessage = (e) => {
        if (e.data instanceof ArrayBuffer) {
          // Null-safe: playerRef is nulled by switchAudio when audio is off
          playerRef.current?.push(e.data);
          return;
        }
        const msg = JSON.parse(e.data);
        switch (msg.type) {
          case "state":
            setState(msg.state);
            setMood(msg.mood || Mood.NEUTRAL);
            if (msg.state === AvatarState.IDLE || msg.state === AvatarState.REACTING) {
              setHighlightedId(null);
              // Seal the current Mira bubble so the next turn starts fresh
              miraBubbleId.current = null;
            }
            break;

          case "transcript":
            if (!textModeRef.current) {
              // Voice mode: update captions (latest chunk overwrites)
              setCaptions((c) => ({ ...c, [msg.who]: msg.text }));
            }
            if (msg.who === "mira") {
              // Always stream into Mira bubble regardless of mode
              if (!miraBubbleId.current) {
                miraBubbleId.current = _addMsg("mira", msg.text);
              } else {
                _appendMsg(miraBubbleId.current, msg.text);
              }
            } else if (msg.who === "you" && !textModeRef.current) {
              // Voice mode: add your speech as a bubble (no optimistic add in voice)
              _addMsg("you", msg.text);
            }
            // Skip 'you' echo in text mode — already added optimistically in sendText
            break;

          case "mira_text":
            setMiraText({ text: msg.text, at: Date.now() });
            break;

          case "products": {
            const items = msg.items || [];
            const serverSaysMore = msg.show_more === true;
            const serverSaysNoMore = msg.show_more === false;
            if (serverSaysMore || (!serverSaysNoMore && items.length > 0)) setCanShowMore(true);
            if (serverSaysNoMore) setCanShowMore(false);

            // Ensure there's a bubble to attach products to.
            // If no active Mira bubble (e.g. show_more fired between turns),
            // create a lightweight synthetic message so cards appear in the thread.
            let bubId = miraBubbleId.current;
            if (!bubId && items.length) {
              bubId = _addMsg("mira", "Here are a few more picks for you ✦");
              miraBubbleId.current = bubId;
            }
            if (bubId) _attachProducts(bubId, items);

            // Update top-level products list and highlighted card
            setProducts((prev) => {
              const seen = new Set(prev.map((p) => p.id));
              return [...prev, ...items.filter((p) => !seen.has(p.id))];
            });
            if (items.length) setHighlightedId(items[items.length - 1].id);

            // Product timeline for context lookups ("that red dress from earlier")
            if (items.length) {
              setProductTimeline((prev) => [
                ...prev,
                ...items.map((p) => ({ ...p, messageId: bubId, ts: Date.now() })),
              ]);
            }
            break;
          }
          case "looks":
            setLooks(msg.items || []);
            break;

          case "restore_loved":
            setLoved((prev) => { const n = new Set(prev); msg.ids.forEach((id) => n.add(id)); return n; });
            if (msg.products?.length) setSavedProducts(msg.products);
            break;
          case "interrupted":
            break;
          case "error":
            setError(msg.message || "connection_failed");
            break;
        }
      };

      ws.onerror = () => {
        setRetryCount((c) => c + 1);
        setError("connection_failed");
      };
      ws.onclose = () => stop();
    } catch (e) {
      setError(String(e));
    }
  }, [stop, textMode, userId, userName, userPrefs, eventBrief]);

  const retry = useCallback(() => {
    setError(null);
    start();
  }, [start]);

  return {
    connected, state, mood, captions, messages,
    products, looks, savedProducts, loved, highlightedId, error, retryCount, miraText,
    canShowMore, setCanShowMore,
    productTimeline, switchAudio,
    start, stop, retry, sendText, wouldBuy, getLevel, buyClick, showMore,
  };
}
