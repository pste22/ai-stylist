import { useCallback, useRef, useState } from "react";
import { MicCapture, PcmPlayer } from "./audio.js";
import { AvatarState, Mood } from "./avatarState.js";

// Resolve the voice-bridge WebSocket URL.
//   1. Explicit override always wins:        VITE_MIRA_WS_URL
//   2. Otherwise connect SAME-ORIGIN at /mira-ws, which Vite proxies to the Python
//      bridge (see vite.config.js). This is the only reliable path in GitHub
//      Codespaces: a separate forwarded port lives on a different *.app.github.dev
//      subdomain whose tunnel relay rejects cross-origin WS upgrades (HTTP 426).
//      Same-origin avoids that and works identically in local dev.
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

// Connects the browser to the Mira voice bridge (prototype/live_server.py):
// streams mic up, plays Mira's audio down, and surfaces avatar state/mood + captions.
export function useMiraVoice() {
  const [connected, setConnected] = useState(false);
  const [state, setState] = useState(AvatarState.IDLE);
  const [mood, setMood] = useState(Mood.NEUTRAL);
  const [captions, setCaptions] = useState({ you: "", mira: "" });
  const [products, setProducts] = useState([]);
  const [loved, setLoved] = useState(() => new Set());
  const [error, setError] = useState(null);
  // HeyGen voices Mira: each finished turn's full text is pushed here so the avatar speaks it.
  const [miraText, setMiraText] = useState(null);

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
  }, []);

  const wouldBuy = useCallback((product) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "would_buy", product_id: product.id }));
    }
    setLoved((prev) => new Set(prev).add(product.id));
  }, []);

  const getLevel = useCallback(() => playerRef.current?.getLevel?.() ?? 0, []);

  const buyClick = useCallback((product) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "buy_click", product_id: product.id }));
    }
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      const player = new PcmPlayer();
      playerRef.current = player;

      ws.onopen = async () => {
        setConnected(true);
        const mic = new MicCapture((bytes) => {
          if (ws.readyState === WebSocket.OPEN) ws.send(bytes);
        });
        micRef.current = mic;
        try {
          await mic.start();
        } catch (e) {
          setError("Mic permission denied");
          stop();
        }
      };

      ws.onmessage = (e) => {
        if (e.data instanceof ArrayBuffer) {
          // Direct Gemini PCM audio — play it via PcmPlayer for lip-sync.
          playerRef.current?.push(e.data);
          return;
        }
        const msg = JSON.parse(e.data);
        switch (msg.type) {
          case "state":
            setState(msg.state);
            setMood(msg.mood || Mood.NEUTRAL);
            break;
          case "transcript":
            setCaptions((c) => ({ ...c, [msg.who]: msg.text }));
            break;
          case "mira_text":
            // Full turn text → HeyGen avatar speaks it.
            setMiraText({ text: msg.text, at: Date.now() });
            break;
          case "products":
            // Merge new recommendations, keeping any already on screen.
            setProducts((prev) => {
              const seen = new Set(prev.map((p) => p.id));
              return [...prev, ...msg.items.filter((p) => !seen.has(p.id))];
            });
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
  }, [stop]);

  return { connected, state, mood, captions, products, loved, error, miraText, start, stop, wouldBuy, getLevel, buyClick };
}
