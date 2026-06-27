import { useEffect, useRef } from "react";
import { AvatarState, Mood } from "./avatarState.js";

// Placeholder Mira (P2-3 v1): a CSS-animated face whose expression reflects the brain
// state. This is the seam where a Rive state machine drops in later — same inputs,
// richer rendering. The job of v1 is simply to feel ALIVE, not photoreal.
//
// `getLevel` (optional) returns live output loudness 0..1; when talking we drive the
// mouth from it (real lip-sync) via a CSS var, avoiding a re-render every frame.
export default function Avatar({ state, mood, getLevel }) {
  const isTalking = state === AvatarState.TALKING;
  const isThinking = state === AvatarState.THINKING;
  const mouthRef = useRef(null);

  useEffect(() => {
    if (!isTalking || !getLevel) {
      if (mouthRef.current) mouthRef.current.style.setProperty("--mouth", "0");
      return;
    }
    let raf;
    const tick = () => {
      const lvl = getLevel();
      if (mouthRef.current) {
        mouthRef.current.style.setProperty("--mouth", lvl.toFixed(3));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [isTalking, getLevel]);

  // Eyes/brows/mouth shift subtly with state + mood.
  const faceClass = [
    "mira-face",
    `state-${state}`,
    `mood-${mood}`,
  ].join(" ");

  return (
    <div className="mira-stage">
      <div className={faceClass}>
        <div className="mira-eyes">
          <span className="eye left" />
          <span className="eye right" />
        </div>
        <div ref={mouthRef} className={`mira-mouth ${isTalking ? "talking" : ""}`} />
        {isThinking && <div className="mira-thought">…</div>}
      </div>
      <div className="mira-label">
        {labelFor(state, mood)}
      </div>
    </div>
  );
}

function labelFor(state, mood) {
  if (state === AvatarState.THINKING) return "thinking…";
  if (state === AvatarState.TALKING) return "Mira is speaking";
  if (state === AvatarState.REACTING)
    return mood === Mood.EXCITED ? "excited for you!" : "here for you";
  return "ready when you are";
}
