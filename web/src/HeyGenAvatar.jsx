import { useEffect, useRef, useState } from "react";
import StreamingAvatar, { AvatarQuality, StreamingEvents, TaskType } from "@heygen/streaming-avatar";
import RiveAvatar from "./RiveAvatar.jsx";

// Real Mira face via HeyGen Interactive Avatar (P2-3, video path).
// Pipeline: mic → Gemini Live (TEXT) → bridge emits {mira_text} → we tell HeyGen to
// SPEAK it. HeyGen renders a streaming, lip-synced video; the API key stays server-side
// (minted at /heygen-token). If anything fails (no key/plan/network) we fall back to the
// Rive/CSS placeholder so the demo never breaks.
const AVATAR_ID = import.meta.env.VITE_HEYGEN_AVATAR_ID || "default";

export default function HeyGenAvatar({ state, mood, getLevel, connected, miraText }) {
  const videoRef = useRef(null);
  const avatarRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  // Boot a HeyGen session once the user connects; tear it down on disconnect.
  useEffect(() => {
    if (!connected) return;
    let cancelled = false;
    (async () => {
      try {
        const token = await fetch("/heygen-token").then((r) => r.json()).then((d) => d.token);
        if (!token) throw new Error("no token");
        const avatar = new StreamingAvatar({ token });
        avatarRef.current = avatar;
        avatar.on(StreamingEvents.STREAM_READY, (e) => {
          if (videoRef.current && e.detail) {
            videoRef.current.srcObject = e.detail;
            videoRef.current.play().catch(() => {});
          }
          if (!cancelled) setReady(true);
        });
        avatar.on(StreamingEvents.STREAM_DISCONNECTED, () => setReady(false));
        await avatar.createStartAvatar({ quality: AvatarQuality.Medium, avatarName: AVATAR_ID });
      } catch (e) {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      avatarRef.current?.stopAvatar().catch(() => {});
      avatarRef.current = null;
    };
  }, [connected]);

  // Speak each finished turn's text.
  useEffect(() => {
    const a = avatarRef.current;
    if (a && ready && miraText?.text) {
      a.speak({ text: miraText.text, taskType: TaskType.REPEAT }).catch(() => {});
    }
  }, [miraText, ready]);

  if (failed) return <RiveAvatar state={state} mood={mood} getLevel={getLevel} />;

  return (
    <div className="mira-stage">
      <video ref={videoRef} className="mira-video" autoPlay playsInline muted={false} />
      {!ready && <RiveAvatar state={state} mood={mood} getLevel={getLevel} />}
    </div>
  );
}
