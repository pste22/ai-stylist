import { useCallback, useRef, useState } from "react";
import { MicCapture, PcmPlayer } from "./audio.js";
import { AvatarState, Mood } from "./avatarState.js";
import { supabase } from "./supabaseClient.js";
import { track } from "./analytics.js";
import { resizePhotoForTryOn } from "./resizePhoto.js";
import { fetchProductImageBytes } from "./imageUrl.js";

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

export function useMiraVoice({ userId, userName, userEmail = null, userPrefs = null, eventBrief = null, textMode = false, onAddToCart = null, onVisualSearchResults = null } = {}) {
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
  const [editorialLooks, setEditorialLooks] = useState([]);
  const [trendingProducts, setTrendingProducts] = useState([]);
  const [youMightLike, setYouMightLike] = useState(null); // {anchorId, items}
  const [fullLook, setFullLook] = useState(null); // {hero, items, all_items, total, currency, title}

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
  const askWatchdogRef = useRef(null);

  const stop = useCallback(() => {
    micRef.current?.stop();
    playerRef.current?.flush();
    wsRef.current?.close();
    micRef.current = playerRef.current = wsRef.current = null;
    if (askWatchdogRef.current) {
      clearTimeout(askWatchdogRef.current);
      askWatchdogRef.current = null;
    }
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

  // If sendText is called before the WS is open, queue it and flush on connect.
  const pendingTextRef = useRef(null);
  const pendingTryOnRef = useRef(null);

  // Send a typed message (silent / text chat). Always shows the bubble when possible.
  const sendText = useCallback((text) => {
    const trimmed = (text || "").trim();
    if (!trimmed) return;
    // New conversation input — clear filter-chip browse context so show_more
    // uses server's own session_last_categories from this voice/text turn.
    lastBrowseCatRef.current = null;
    // Clear quick-replies — user is typing a real answer
    setQuickReplies([]);
    if (quickReplyTimerRef.current) { clearTimeout(quickReplyTimerRef.current); quickReplyTimerRef.current = null; }

    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      // Not connected yet — show the bubble and queue; caller/App should start().
      _addMsg("you", trimmed);
      pendingTextRef.current = trimmed;
      setState(AvatarState.THINKING);
      return false;
    }
    // Optimistically add the user bubble immediately.
    // Seal any welcome/prior Mira bubble so the next catalog answer can't
    // append behind the first 3 welcome cards (silent-mode cap bug).
    miraBubbleId.current = null;
    _addMsg("you", trimmed);
    ws.send(JSON.stringify({ type: "text_input", text: trimmed }));
    setState(AvatarState.THINKING);
    return true;
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
    const source = product?.source || "";
    let retailer = "partner";
    try {
      const host = product?.affiliate_url ? new URL(product.affiliate_url).hostname : "";
      if (/myntra/i.test(host) || /myntra/i.test(source)) retailer = "myntra";
      else if (/ajio/i.test(host) || /ajio/i.test(source)) retailer = "ajio";
      else if (/snitch/i.test(host) || /snitch/i.test(source)) retailer = "snitch";
      else if (/amazon|amzn/i.test(host) || /amazon|curated/i.test(source)) retailer = "amazon";
      else if (/nykaa/i.test(host) || /nykaa/i.test(source)) retailer = "nykaa";
      else if (product?.brand) retailer = String(product.brand).toLowerCase().slice(0, 32);
    } catch { /* ignore */ }
    track("affiliate_click_out", {
      product_id: product?.id,
      name: product?.name,
      price: product?.price,
      retailer,
      source,
      brand: product?.brand || null,
    });
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN)
      ws.send(JSON.stringify({
        type: "buy_click",
        product_id: product.id,
        retailer,
        source,
      }));
  }, []);

  const showMoreTimeoutRef = useRef(null);
  // Tracks the last category browsed via filter chip so show_more can stay in context.
  // Cleared when the user sends a text/voice message (new conversation resets category).
  const lastBrowseCatRef = useRef(null);
  // Tracks IDs shown via REST browse so the exclude list is correct for REST show_more.
  const restShownIdsRef = useRef(new Set());

  const showMore = useCallback(async () => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      setCanShowMore(false);
      const payload = { type: "show_more" };
      if (lastBrowseCatRef.current) payload.category = lastBrowseCatRef.current;
      ws.send(JSON.stringify(payload));
      // Safety: re-enable after 5s ONLY if server never responds at all.
      showMoreTimeoutRef.current = setTimeout(() => {
        showMoreTimeoutRef.current = null;
        setCanShowMore(true);
      }, 5000);
    } else if (lastBrowseCatRef.current) {
      // Not connected but have a browse category — use REST so no session needed.
      const cat = lastBrowseCatRef.current;
      const catLabel = cat.charAt(0).toUpperCase() + cat.slice(1);
      const excludeStr = [...restShownIdsRef.current].join(",");
      const bubId = _addMsg("mira", `Browsing: ${catLabel}`);
      try {
        const resp = await fetch(`/api/browse?category=${encodeURIComponent(cat)}&limit=6&exclude=${encodeURIComponent(excludeStr)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const items = data.products || [];
        items.forEach((p) => restShownIdsRef.current.add(p.id));
        if (items.length) _attachProducts(bubId, items);
        setCanShowMore(!!data.show_more);
      } catch (e) { console.error("[showMore REST]", e); }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Send a mid-session location update without restarting the session
  const updateLocation = useCallback((pinCode) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "update_location", pin_code: pinCode }));
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

  const addSystemEvent = useCallback((text) => {
    _addMsg("event", text);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clearHistory = useCallback(() => {
    setMessages([]);
    setLooks([]);
    setProductTimeline([]);
    miraBubbleId.current = null;
  }, []);

  const start = useCallback(async (initialText = null) => {
    // Defensive: only accept a real string (guards against a click event being
    // passed when start is used directly as an onClick handler).
    if (typeof initialText !== "string") initialText = null;
    setError(null);
    setLooks([]);
    setProductTimeline([]);
    miraBubbleId.current = null;
    try {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      if (!textMode) playerRef.current = new PcmPlayer();

      ws.onopen = async () => {
        // Queued sendText (bubble already on screen) or start(initialText)
        const queued = pendingTextRef.current;
        pendingTextRef.current = null;
        const bootText = initialText || queued || null;

        ws.send(JSON.stringify({
          type:             "init",
          user_id:          userId,
          email:            userEmail || null,
          name:             userName || "there",
          style_vibe:       userPrefs?.style_vibe     ?? null,
          shopping_focus:   userPrefs?.shopping_focus ?? null,
          top_size:         userPrefs?.top_size       ?? null,
          bottom_size:      userPrefs?.bottom_size    ?? null,
          budget:           userPrefs?.budget         ?? null,
          pin_code:         userPrefs?.pin_code       ?? null,
          text_mode:        textMode,
          event_brief:      eventBrief,
          initial_request:  bootText,
        }));
        setConnected(true);
        setCanShowMore(true); // always show browse button once connected (1000+ products available)
        // start("…") path — show user bubble (sendText queue already added one)
        if (initialText && !queued) {
          _addMsg("you", initialText);
        }
        if (bootText) setState(AvatarState.THINKING);
        const queuedTryOn = pendingTryOnRef.current;
        pendingTryOnRef.current = null;
        if (queuedTryOn) ws.send(JSON.stringify(queuedTryOn));
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
              if (askWatchdogRef.current) {
                clearTimeout(askWatchdogRef.current);
                askWatchdogRef.current = null;
              }
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
            console.log("[products] received:", items.length, "items, show_more:", msg.show_more, "→ canShowMore will be:", serverSaysMore || (!serverSaysNoMore && items.length > 0));
            // Cancel the show_more safety timeout — server responded, so
            // whatever it says about show_more is authoritative.
            if (showMoreTimeoutRef.current) {
              clearTimeout(showMoreTimeoutRef.current);
              showMoreTimeoutRef.current = null;
            }
            if (serverSaysMore || (!serverSaysNoMore && items.length > 0)) setCanShowMore(true);
            if (serverSaysNoMore) setCanShowMore(false);

            // Ensure there's a bubble to attach products to.
            // Paged results (Show 3 more) and labeled catalog answers (shop_query)
            // ALWAYS get their own fresh bubble — otherwise they pile into the
            // welcome "few more picks" cards and the per-bubble 3-card cap hides
            // the real matches (Tommy ask → only welcome 72styles/Aldo visible).
            let attachedBubId = null;
            const ownBubble = msg.paged || !!msg.label;
            if (ownBubble) {
              if (items.length) {
                const label = String(msg.label || "").trim();
                const bubbleText = label
                  ? (label.includes("·")
                      ? label
                      : `Here are some ${label.toLowerCase()} I like on you ✦`)
                  : "Here are a few more picks for you ✦";
                attachedBubId = _addMsg("mira", bubbleText);
                _attachProducts(attachedBubId, items);
                // Stamp the label so ProductGrid shows all matched items
                if (msg.label) {
                  setMessages(prev => prev.map(m =>
                    m.id === attachedBubId ? { ...m, label: msg.label } : m
                  ));
                }
                // Deliberately NOT stored in miraBubbleId — next Show 3 more /
                // catalog answer must create another fresh bubble.
              }
            } else {
              // In-turn products attach to Mira's current speaking bubble.
              let bubId = miraBubbleId.current;
              if (!bubId && items.length) {
                bubId = _addMsg("mira", "Here are a few more picks for you ✦");
                miraBubbleId.current = bubId;
              }
              if (bubId) _attachProducts(bubId, items);
              attachedBubId = bubId;
            }

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
                ...items.map((p) => ({ ...p, messageId: attachedBubId, ts: Date.now() })),
              ]);
            }
            break;
          }
          case "looks":
            setLooks(msg.items || []);
            break;

          case "full_look":
            setFullLook({
              hero: msg.hero || null,
              items: msg.items || [],
              all_items: msg.all_items || (msg.hero ? [msg.hero, ...(msg.items || [])] : (msg.items || [])),
              total: msg.total ?? null,
              currency: msg.currency || "USD",
              title: msg.title || "Shop the full look",
            });
            if (msg.hero?.id) setHighlightedId(msg.hero.id);
            break;
          case "trending":
            setTrendingProducts(msg.items || []);
            break;

          case "editorial_looks":
            setEditorialLooks(msg.items || []);
            break;

          case "you_might_like":
            if (msg.items?.length) {
              setYouMightLike({ anchorId: msg.anchor_id, items: msg.items });
            }
            break;

          case "add_to_cart":
            if (onAddToCart && msg.items?.length) msg.items.forEach(onAddToCart);
            break;

          case "restore_loved":
            setLoved((prev) => { const n = new Set(prev); msg.ids.forEach((id) => n.add(id)); return n; });
            if (msg.products?.length) setSavedProducts(msg.products);
            break;
          case "visual_search_results":
            setVsLoading(false);
            if (onVisualSearchResults) onVisualSearchResults(msg.items || [], msg.query || "", msg.catalog_note || null);
            break;
          case "outfit_url_status":
            // "fetching" status — loading is already true, nothing extra needed
            break;
          case "outfit_url_error": {
            setOutfitLoading(false);
            const PRIVATE_MSG = "This post is private or unavailable. Screenshot the outfit and use the 👗 button to upload it directly.";
            const NOT_FOUND_MSG = "Post not found — check the URL or try uploading a screenshot instead.";
            const FAIL_MSG = "Couldn't fetch the image from that link. Try uploading a screenshot instead.";
            const reason = msg.reason || "fetch_failed";
            setOutfitError(reason === "private" ? PRIVATE_MSG : reason === "not_found" ? NOT_FOUND_MSG : FAIL_MSG);
            break;
          }
          case "outfit_anatomy":
            setOutfitLoading(false);
            if (msg.items?.length) {
              setOutfitAnatomy({
                items: msg.items,
                gender: msg.outfit_gender || "women",
                catalogNote: msg.catalog_note || null,
              });
            } else {
              setOutfitError(msg.error || "Could not detect outfit items — try a clearer photo.");
            }
            break;
          case "try_on_result": {
            if (tryOnTimeoutRef.current) { clearTimeout(tryOnTimeoutRef.current); tryOnTimeoutRef.current = null; }
            setTryOnLoading(false); // first angle arrived — show it immediately
            setTryOnLayering(false);
            setTryOnError(null);
            const view = msg.view || "front";
            if (view === "front") track("try_on_result_shown", { product_id: msg.product_id }); // activation
            setTryOnResult((prev) => {
              const base = prev && prev.productId === msg.product_id
                ? prev
                : { productId: msg.product_id, views: {}, failed: {}, total: msg.total || 1 };
              return {
                ...base,
                total: msg.total || base.total,
                views: { ...base.views, [view]: { image: msg.image, mime: msg.mime || "image/png" } },
              };
            });
            break;
          }
          case "try_on_look": {
            if (msg.product_id) {
              setTryOnLookItems(Array.isArray(msg.items) ? msg.items : []);
            }
            break;
          }
          case "try_on_view_error":
            // A single angle failed — keep the others; mark this one so the UI stops waiting.
            setTryOnResult((prev) =>
              prev && prev.productId === msg.product_id
                ? { ...prev, failed: { ...prev.failed, [msg.view]: true } }
                : prev
            );
            break;
          case "try_on_error":
            if (tryOnTimeoutRef.current) { clearTimeout(tryOnTimeoutRef.current); tryOnTimeoutRef.current = null; }
            setTryOnLoading(false);
            setTryOnLayering(false);
            setTryOnError(msg.message || "Try-on failed. Please try again.");
            break;
          case "try_on_video_still": {
            // Scene composite preview — shown while the clip renders.
            const k = msg.kind || "spin";
            setTryOnVideo((prev) => {
              const base = prev && prev.productId === msg.product_id
                ? prev : { productId: msg.product_id, clips: {}, stills: {} };
              return { ...base, stills: { ...base.stills, [k]: { image: msg.image, mime: msg.mime || "image/png" } } };
            });
            break;
          }
          case "try_on_video_result": {
            if (tryOnVideoTimeoutRef.current) { clearTimeout(tryOnVideoTimeoutRef.current); tryOnVideoTimeoutRef.current = null; }
            const k = msg.kind || "spin";
            track("try_on_video_generated", { product_id: msg.product_id, kind: k, hd: !!msg.hd });
            setTryOnVideoLoadingKind((cur) => (cur === k ? null : cur));
            setTryOnVideoError(null);
            setTryOnVideo((prev) => {
              const base = prev && prev.productId === msg.product_id
                ? prev : { productId: msg.product_id, clips: {}, stills: {} };
              return { ...base, clips: { ...base.clips, [k]: { video: msg.video, mime: msg.mime || "video/mp4", hd: !!msg.hd } } };
            });
            break;
          }
          case "try_on_video_error": {
            if (tryOnVideoTimeoutRef.current) { clearTimeout(tryOnVideoTimeoutRef.current); tryOnVideoTimeoutRef.current = null; }
            const k = msg.kind || "spin";
            setTryOnVideoLoadingKind((cur) => (cur === k ? null : cur));
            setTryOnVideoError(msg.message || "Video failed. Please try again.");
            break;
          }
          case "quick_replies":
            setQuickReplies(msg.options || []);
            break;
          case "interrupted":
            break;
          case "error":
            setError(msg.message || "connection_failed");
            break;
        }
      };

      ws.onerror = (e) => {
        console.error("[ws] onerror — connection failed", e);
        setRetryCount((c) => c + 1);
        setError("connection_failed");
      };
      ws.onclose = (e) => {
        console.warn("[ws] onclose — code:", e.code, "reason:", e.reason, "wasClean:", e.wasClean);
        stop();
      };
    } catch (e) {
      setError(String(e));
    }
  }, [stop, textMode, userId, userName, userEmail, userPrefs, eventBrief]);

  const retry = useCallback(() => {
    setError(null);
    start();
  }, [start]);

  const [vsLoading, setVsLoading] = useState(false);
  const [quickReplies, setQuickReplies] = useState([]);
  const [outfitAnatomy, setOutfitAnatomy] = useState(null);
  const [outfitLoading, setOutfitLoading] = useState(false);
  const [outfitError, setOutfitError] = useState(null);
  const [tryOnResult, setTryOnResult] = useState(null);   // { productId, views:{}, failed:{}, total }
  const [tryOnLookItems, setTryOnLookItems] = useState([]);
  const [tryOnLoading, setTryOnLoading] = useState(false);
  const [tryOnLayering, setTryOnLayering] = useState(false);
  const [tryOnError, setTryOnError] = useState(null);
  const tryOnTimeoutRef = useRef(null);
  // Videos keyed by kind ("spin" | scene keys). clips = finished mp4s; stills = scene
  // preview images shown while the clip renders.
  const [tryOnVideo, setTryOnVideo] = useState(null);     // { productId, clips:{}, stills:{} }
  const [tryOnVideoLoadingKind, setTryOnVideoLoadingKind] = useState(null);
  const [tryOnVideoError, setTryOnVideoError] = useState(null);
  const tryOnVideoTimeoutRef = useRef(null);

  const clearTryOn = useCallback(() => {
    setTryOnResult(null);
    setTryOnLookItems([]);
    setTryOnError(null);
    setTryOnLoading(false);
    setTryOnLayering(false);
    setTryOnVideo(null);
    setTryOnVideoError(null);
    setTryOnVideoLoadingKind(null);
    if (tryOnTimeoutRef.current) { clearTimeout(tryOnTimeoutRef.current); tryOnTimeoutRef.current = null; }
    if (tryOnVideoTimeoutRef.current) { clearTimeout(tryOnVideoTimeoutRef.current); tryOnVideoTimeoutRef.current = null; }
  }, []);

  const sendTryOnVideo = useCallback((productId, imageBase64, mime = "image/png", kind = "spin", hd = false) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || !productId || !imageBase64) return;
    setTryOnVideoError(null);
    setTryOnVideoLoadingKind(kind);
    ws.send(JSON.stringify({ type: "try_on_video", product_id: productId, image: imageBase64, mime, kind, hd }));
    if (tryOnVideoTimeoutRef.current) clearTimeout(tryOnVideoTimeoutRef.current);
    tryOnVideoTimeoutRef.current = setTimeout(() => {
      tryOnVideoTimeoutRef.current = null;
      setTryOnVideoLoadingKind(null);
      setTryOnVideoError((e) => e || "Video timed out. Please try again.");
    }, 240000);
  }, []);

  const sendTryOn = useCallback(async (productId, imageBase64, mime = "image/jpeg", garmentUrl = null) => {
    if (!productId || !imageBase64) return;
    setTryOnResult(null);
    setTryOnLookItems([]);
    setTryOnError(null);
    setTryOnLoading(true);
    setTryOnLayering(false);
    let payload = imageBase64;
    let outMime = mime || "image/jpeg";
    try {
      const resized = await resizePhotoForTryOn(imageBase64, outMime);
      payload = resized.base64;
      outMime = resized.mime;
    } catch (e) {
      console.warn("[try_on] photo resize skipped", e);
    }
    const packet = { type: "try_on", product_id: productId, image: payload, mime: outMime };
    if (garmentUrl) {
      try {
        const garment = await fetchProductImageBytes(garmentUrl);
        if (garment?.base64) {
          packet.garment = garment.base64;
          packet.garment_mime = garment.mime || "image/jpeg";
        }
      } catch (e) {
        console.warn("[try_on] garment fetch skipped", e);
      }
    }
    if (tryOnTimeoutRef.current) clearTimeout(tryOnTimeoutRef.current);
    tryOnTimeoutRef.current = setTimeout(() => {
      tryOnTimeoutRef.current = null;
      setTryOnLoading(false);
      setTryOnLayering(false);
      setTryOnError((err) => err || "Try-on timed out. Please try again.");
    }, 90000);
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      pendingTryOnRef.current = packet;
      return;
    }
    ws.send(JSON.stringify(packet));
  }, []);

  const sendTryOnLayer = useCallback(async (heroId, piece, imageBase64, mime = "image/png") => {
    if (!heroId || !piece?.id || !imageBase64) return;
    setTryOnError(null);
    setTryOnLayering(true);
    setTryOnLoading(true);
    const packet = {
      type: "try_on_layer",
      product_id: heroId,
      add_id: piece.id,
      image: imageBase64,
      mime: mime || "image/png",
    };
    if (piece.image_url) {
      try {
        const garment = await fetchProductImageBytes(piece.image_url);
        if (garment?.base64) {
          packet.garment = garment.base64;
          packet.garment_mime = garment.mime || "image/jpeg";
        }
      } catch (e) {
        console.warn("[try_on_layer] garment fetch skipped", e);
      }
    }
    if (tryOnTimeoutRef.current) clearTimeout(tryOnTimeoutRef.current);
    tryOnTimeoutRef.current = setTimeout(() => {
      tryOnTimeoutRef.current = null;
      setTryOnLoading(false);
      setTryOnLayering(false);
      setTryOnError((err) => err || "Try-on timed out. Please try again.");
    }, 90000);
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setTryOnLoading(false);
      setTryOnLayering(false);
      setTryOnError("Mira isn't connected — try again in a moment.");
      return;
    }
    ws.send(JSON.stringify(packet));
  }, []);

  const sendOutfitImage = useCallback((imageBase64, mime = "image/jpeg") => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    setOutfitAnatomy(null);
    setOutfitError(null);
    setOutfitLoading(true);
    ws.send(JSON.stringify({ type: "visual_outfit", image: imageBase64, mime }));
    setTimeout(() => setOutfitLoading(false), 45000);
  }, []);

  const sendOutfitUrl = useCallback((url) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    setOutfitAnatomy(null);
    setOutfitError(null);
    setOutfitLoading(true);
    ws.send(JSON.stringify({ type: "outfit_url", url }));
    setTimeout(() => setOutfitLoading(false), 60000);
  }, []);

  const styleFullLook = useCallback((heroId) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    miraBubbleId.current = null;
    _addMsg("you", "Style a full look around this");
    ws.send(JSON.stringify({ type: "complete_look", hero_id: heroId || null }));
    setState(AvatarState.THINKING);
    return true;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const browseCategory = useCallback(async (cat) => {
    if (!cat) return;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      // Connected: use WS so session tracks context for show_more
      lastBrowseCatRef.current = cat;
      restShownIdsRef.current = new Set(); // reset REST tracking for new category
      ws.send(JSON.stringify({ type: "category_browse", category: cat }));
      return;
    }
    // Not connected: REST fetch — no session, no mic permission, instant results
    lastBrowseCatRef.current = cat;
    restShownIdsRef.current = new Set(); // reset for new category
    const catLabel = cat.charAt(0).toUpperCase() + cat.slice(1);
    const bubId = _addMsg("mira", `Browsing: ${catLabel}`);
    try {
      const resp = await fetch(`/api/browse?category=${encodeURIComponent(cat)}&limit=6`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const items = data.products || [];
      items.forEach((p) => restShownIdsRef.current.add(p.id));
      if (items.length) _attachProducts(bubId, items);
      setCanShowMore(!!data.show_more);
    } catch (e) {
      console.error("[browseCategory]", e);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendOutfitAssembled = useCallback((productIds) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || !productIds?.length) return;
    ws.send(JSON.stringify({ type: "outfit_assembled", product_ids: productIds }));
  }, []);

  // Immediately inject assembled look products into chat (before Mira replies).
  // Single atomic setMessages so products are never missing due to batching.
  const addAssembledLookToChat = useCallback((products) => {
    if (!products?.length) return;
    const id = mkId();
    setMessages(prev => [...prev, {
      id,
      role: "mira",
      text: "Your assembled look",
      products,
      label: "Your assembled look",
      showAll: true,
      ts: new Date(),
    }]);
  }, []);

  const ASK_PROMPTS = {
    suit: "Does this suit me?",
    wear: "When would I wear this?",
    pair: "What goes with it?",
  };

  const askFallbackText = (product, promptKey) => {
    const cat = String(product?.category || "piece").replace(/s$/, "");
    const color = String(product?.color || "").trim();
    const colorBit = color && !["multi", "multicolor"].includes(color.toLowerCase()) ? ` ${color}` : "";
    if (promptKey === "wear") {
      return `I'd wear this${colorBit} ${cat} for easy days out, dinner, or anytime you want the outfit to do the talking. Want shoes and a bag to go with it?`;
    }
    if (promptKey === "pair") {
      return `Keep the rest simple — a clean bottom, neat shoes, and one accent so the ${cat} stays the hero. Want me to pull those from the catalog?`;
    }
    return `Yes — this${colorBit} ${cat} is an easy yes. Keep everything else quiet so it reads polished, not busy. Want similar pieces or something to pair with it?`;
  };

  const askAboutProduct = useCallback((product, promptKey = "suit", { inject = true } = {}) => {
    const ws = wsRef.current;
    if (!product?.id) return false;
    const key = ASK_PROMPTS[promptKey] ? promptKey : "suit";
    const question = ASK_PROMPTS[key];
    const fallback = askFallbackText(product, key);
    miraBubbleId.current = null;
    if (inject) {
      // Show product + user question immediately; server drives Mira's reply.
      setMessages((prev) => [
        ...prev,
        {
          id: mkId(),
          role: "mira",
          text: "Talking about this piece",
          products: [product],
          label: "Talking about this piece",
          showAll: true,
          ts: new Date(),
        },
        { id: mkId(), role: "you", text: question, ts: new Date() },
      ]);
      setQuickReplies([]);
      if (quickReplyTimerRef.current) {
        clearTimeout(quickReplyTimerRef.current);
        quickReplyTimerRef.current = null;
      }
    }
    const armWatchdog = () => {
      if (askWatchdogRef.current) clearTimeout(askWatchdogRef.current);
      askWatchdogRef.current = setTimeout(() => {
        askWatchdogRef.current = null;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "you" && last.text === question) {
            return [...prev, { id: mkId(), role: "mira", text: fallback, ts: new Date() }];
          }
          return prev;
        });
        setState((s) => (s === AvatarState.THINKING ? AvatarState.IDLE : s));
      }, 8000);
    };
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setMessages((prev) => [...prev, { id: mkId(), role: "mira", text: fallback, ts: new Date() }]);
      setState(AvatarState.IDLE);
      return false;
    }
    ws.send(JSON.stringify({
      type: "ask_about_product",
      product_id: product.id,
      prompt_key: key,
    }));
    setState(AvatarState.THINKING);
    armWatchdog();
    return true;
  }, []);
  const quickReplyTimerRef = useRef(null);

  const sendLikeReason = useCallback((product, reasons) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "like_reason", product_id: product.id, reasons }));
    // Auto-clear quick replies after 12s if user ignores them
    if (quickReplyTimerRef.current) clearTimeout(quickReplyTimerRef.current);
    quickReplyTimerRef.current = setTimeout(() => {
      setQuickReplies([]);
      quickReplyTimerRef.current = null;
    }, 12000);
  }, []);

  const dismissQuickReplies = useCallback(() => {
    if (quickReplyTimerRef.current) clearTimeout(quickReplyTimerRef.current);
    setQuickReplies([]);
  }, []);

  const sendVisualSearch = useCallback((imageBase64, mime = "image/jpeg") => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    setVsLoading(true);
    ws.send(JSON.stringify({ type: "visual_search", image: imageBase64, mime }));
    // Safety timeout — clear loading after 20s if no response
    setTimeout(() => setVsLoading(false), 20000);
  }, []);

  return {
    connected, state, mood, captions, messages,
    products, looks, editorialLooks, trendingProducts, youMightLike, setYouMightLike,
    savedProducts, loved, highlightedId, error, retryCount, miraText,
    canShowMore, setCanShowMore,
    productTimeline, switchAudio, updateLocation, addSystemEvent, clearHistory,
    start, stop, retry, sendText, wouldBuy, getLevel, buyClick, showMore, browseCategory,
    sendVisualSearch, vsLoading, setVsLoading,
    sendLikeReason, quickReplies, dismissQuickReplies, styleFullLook,
    fullLook, setFullLook,
    sendOutfitImage, sendOutfitUrl, sendOutfitAssembled, addAssembledLookToChat,
    askAboutProduct,
    outfitAnatomy, setOutfitAnatomy, outfitLoading, outfitError, setOutfitError,
    sendTryOn, sendTryOnLayer, tryOnResult, tryOnLoading, tryOnLayering, tryOnError, clearTryOn, tryOnLookItems,
    sendTryOnVideo, tryOnVideo, tryOnVideoLoadingKind, tryOnVideoError,
  };
}
