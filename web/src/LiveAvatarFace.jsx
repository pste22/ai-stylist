import { useEffect, useRef, useState } from "react";
import { LiveAvatarSession, SessionEvent, SessionState } from "@heygen/liveavatar-web-sdk";
import RiveAvatar from "./RiveAvatar.jsx";

// Real Mira face via LiveAvatar LITE mode (HeyGen's successor to the sunset Interactive
// Avatar API). Pipeline: mic → Gemini Live (TEXT) → bridge emits {mira_text} → we tell
// LiveAvatar to SPEAK it via session.repeat(); LiveAvatar renders the lip-synced video
// (its own TTS using the avatar's default voice). The API key stays server-side, minted
// at /avatar-token. If anything fails (no key/credits/network) we fall back to the
// Rive/CSS placeholder so the demo never breaks.

export default function LiveAvatarFace({ state, mood, getLevel, connected, miraText }) {
  const videoRef = useRef(null);
  const sessionRef = useRef(null);
  const canSpeakRef = useRef(false); // true only once session state === CONNECTED
  const pendingRef = useRef([]); // text that arrived before we could speak
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  // Speak now if the session is connected, otherwise queue until it is. repeat() throws
  // unless the session state is CONNECTED, so we must gate on that (not just stream-ready).
  const speak = (text) => {
    const s = sessionRef.current;
    if (!text) return;
    if (!s || !canSpeakRef.current) {
      pendingRef.current.push(text);
      return;
    }
    try {
      s.interrupt();
    } catch {
      /* nothing playing */
    }
    try {
      s.repeat(text);
    } catch (e) {
      console.warn("[LiveAvatar] repeat failed", e);
    }
  };

  // Boot a LiveAvatar session once the user connects; tear it down on disconnect.
  useEffect(() => {
    if (!connected) return;
    let cancelled = false;
    (async () => {
      try {
        const { token, error } = await fetch("/avatar-token").then((r) => r.json());
        if (!token) throw new Error(error || "no token");
        // LITE: we drive speech ourselves (no built-in voice chat / mic capture).
        const session = new LiveAvatarSession(token, { voiceChat: false });
        sessionRef.current = session;
        session.on(SessionEvent.SESSION_STREAM_READY, () => {
          console.log("[LiveAvatar] stream ready");
          if (cancelled) return;
          if (videoRef.current) {
            try {
              session.attach(videoRef.current);
              videoRef.current.play?.().catch(() => {});
            } catch (e) {
              console.warn("[LiveAvatar] attach failed", e);
            }
          }
          setReady(true);
        });
        session.on(SessionEvent.SESSION_STATE_CHANGED, (s) => {
          console.log("[LiveAvatar] state", s);
          if (s === SessionState.CONNECTED) {
            canSpeakRef.current = true;
            pendingRef.current.splice(0).forEach(speak); // flush queued turns
          } else if (s === SessionState.DISCONNECTED) {
            canSpeakRef.current = false;
            setReady(false);
          }
        });
        session.on(SessionEvent.SESSION_DISCONNECTED, (r) => {
          console.warn("[LiveAvatar] disconnected", r);
          canSpeakRef.current = false;
          setReady(false);
        });
        console.log("[LiveAvatar] starting session…");
        // SDK quirk: connectWebSocket() never rejects on socket failure, so start()
        // can hang forever (e.g. when the signaling socket 404s on an out-of-credits or
        // failed session). Watchdog: if we aren't speak-ready shortly, fall back.
        const watchdog = setTimeout(() => {
          if (!cancelled && !canSpeakRef.current) {
            console.error("[LiveAvatar] not CONNECTED in time — falling back (check credits/session).");
            setFailed(true);
          }
        }, 15000);
        await session.start();
        clearTimeout(watchdog);
        console.log("[LiveAvatar] start() resolved");
      } catch (e) {
        console.error("[LiveAvatar] failed to start:", e);
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      canSpeakRef.current = false;
      pendingRef.current = [];
      sessionRef.current?.stop().catch(() => {});
      sessionRef.current = null;
    };
  }, [connected]);

  // Speak each finished turn's text (queued if not yet connected).
  useEffect(() => {
    if (miraText?.text) speak(miraText.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [miraText]);

  // Only fall back to the placeholder if the session truly failed — never on plain load.
  if (failed) return <RiveAvatar state={state} mood={mood} getLevel={getLevel} />;

  return (
    <div className="mira-stage">
      <video ref={videoRef} className="mira-video" autoPlay playsInline />
    </div>
  );
}
