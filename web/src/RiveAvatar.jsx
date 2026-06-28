import { useEffect, useRef, useState } from "react";
import { useRive, useStateMachineInput } from "@rive-app/react-canvas";
import Avatar from "./Avatar.jsx";
import { AvatarState, Mood } from "./avatarState.js";

// Real Mira (P2-3): a Rive state machine driven by the SAME brain states
// (idle/thinking/talking/reacting) the CSS placeholder used. Drop a `mira.riv` into
// web/public and it renders; until the art lands we fall back to the CSS Avatar so the
// demo never breaks. This is the seam from docs/14-ui-strategy.md.
//
// The .riv must expose a state machine "Mira" with these inputs:
//   • state : Number  (0 idle, 1 thinking, 2 talking, 3 reacting)
//   • mood  : Number  (0 neutral, 1 excited, 2 low)
//   • mouth : Number  (0..100) — live talking amplitude for lip-sync
const RIV_SRC = "/23213-43483-watch.riv";
const MACHINE = "State Machine 1";
const STATE_NUM = { [AvatarState.IDLE]: 0, [AvatarState.THINKING]: 1, [AvatarState.TALKING]: 2, [AvatarState.REACTING]: 3 };
const MOOD_NUM = { [Mood.NEUTRAL]: 0, [Mood.EXCITED]: 1, [Mood.LOW]: 2 };

export default function RiveAvatar({ state, mood, getLevel }) {
  const [failed, setFailed] = useState(false);

  const { rive, RiveComponent } = useRive(
    {
      src: RIV_SRC,
      stateMachines: MACHINE,
      autoplay: true,
      onLoadError: () => setFailed(true),
    },
    { shouldDisableRiveListeners: true }
  );

  const stateInput = useStateMachineInput(rive, MACHINE, "state");
  const moodInput = useStateMachineInput(rive, MACHINE, "mood");
  const mouthInput = useStateMachineInput(rive, MACHINE, "mouth");

  useEffect(() => {
    if (stateInput) stateInput.value = STATE_NUM[state] ?? 0;
  }, [stateInput, state]);
  useEffect(() => {
    if (moodInput) moodInput.value = MOOD_NUM[mood] ?? 0;
  }, [moodInput, mood]);

  // Drive lip-sync from live output loudness while talking (no React re-render/frame).
  const rafRef = useRef();
  useEffect(() => {
    if (state !== AvatarState.TALKING || !getLevel || !mouthInput) {
      if (mouthInput) mouthInput.value = 0;
      return;
    }
    const tick = () => {
      mouthInput.value = Math.max(0, Math.min(1, getLevel())) * 100;
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [state, getLevel, mouthInput]);

  // No art yet (or load error) → keep the lively CSS placeholder.
  if (failed) return <Avatar state={state} mood={mood} getLevel={getLevel} />;

  return (
    <div className="mira-stage">
      <RiveComponent className="mira-rive" />
    </div>
  );
}
