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

export function useMiraVoice({ userId, userName, userPrefs = null, textMode = false } = {}) {
  const [connected, setConnected] = useState(false);
  const [state, setState] = useState(AvatarState.IDLE);
  const [mood, setMood] = useState(Mood.NEUTRAL);
  const [captions, setCaptions] = useState({ you: "", mira: "" });
  const [products, setProducts] = useState([]);
  const [loved, setLoved] = useState(() => new Set());
  const [savedProducts, setSavedProducts] = useState([]);
  const [highlightedId, setHighlightedId] = useState(null);
  const [error, setError] = useState(null);
  const [miraText, setMiraText] = useState(null);
  const [canShowMore, setCanShowMore] = useState(false);

  // Text mode: full chat history (persists across turns so user can scroll up)
  const [messages, setMessages] = useState([]);
  // ref to the id of the bubble Mira is currently streaming into
  const miraBubbleId = useRef(null);

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

  // Add a message to the chat thread (text mode only)
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
            .insert({ user_id: userId, product_id: product.id, action: "would_buy", created_at: new Date().toISOString() })
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

  const start = useCallback(async () => {
    setError(null);
    setMessages([]);
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
          if (!textMode) playerRef.current?.push(e.data);
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
            if (!textMode) {
              // Voice mode: overwrite caption (latest chunk only)
              setCaptions((c) => ({ ...c, [msg.who]: msg.text }));
            } else if (msg.who === "mira") {
              // Text mode: stream chunks into the current Mira bubble
              if (!miraBubbleId.current) {
                miraBubbleId.current = _addMsg("mira", msg.text);
              } else {
                _appendMsg(miraBubbleId.current, msg.text);
              }
            }
            // Skip 'you' echo in text mode — already added optimistically in sendText
            break;

          case "mira_text":
            setMiraText({ text: msg.text, at: Date.now() });
            break;

          case "products": {
            const items = msg.items || [];
            // Show the button whenever server says more exist, OR any product arrives
            // (the catalog has 1000+ items so we almost always have more to page).
            // Only hide if the server explicitly says show_more: false.
            const serverSaysMore = msg.show_more === true;
            const serverSaysNoMore = msg.show_more === false;
            if (serverSaysMore || (!serverSaysNoMore && items.length > 0)) setCanShowMore(true);
            // Voice mode: update the product shelf
            if (!textMode) {
              setProducts((prev) => {
                const seen = new Set(prev.map((p) => p.id));
                return [...prev, ...items.filter((p) => !seen.has(p.id))];
              });
              if (items.length) setHighlightedId(items[items.length - 1].id);
            } else {
              // Text mode: attach cards to the bubble they came from
              const bubId = miraBubbleId.current;
              if (bubId) _attachProducts(bubId, items);
              // Also keep the top-level products list for the saved shelf
              setProducts((prev) => {
                const seen = new Set(prev.map((p) => p.id));
                return [...prev, ...items.filter((p) => !seen.has(p.id))];
              });
              if (items.length) setHighlightedId(items[items.length - 1].id);
            }
            break;
          }

          case "restore_loved":
            setLoved((prev) => { const n = new Set(prev); msg.ids.forEach((id) => n.add(id)); return n; });
            if (msg.products?.length) setSavedProducts(msg.products);
            break;
          case "interrupted":
            break;
          case "error":
            setError(msg.message);
            break;
        }
      };

      ws.onerror = () => setError("Could not reach the voice bridge (is live_server.py running?)");
      ws.onclose = () => stop();
    } catch (e) {
      setError(String(e));
    }
  }, [stop, textMode, userId, userName]);

  return {
    connected, state, mood, captions, messages,
    products, savedProducts, loved, highlightedId, error, miraText,
    canShowMore, setCanShowMore,
    start, stop, sendText, wouldBuy, getLevel, buyClick, showMore,
  };
}
