import { useState } from "react";
import Avatar from "./Avatar.jsx";
import { AvatarState, Mood } from "./avatarState.js";

// Web shell (P2-3). For now this is a DEMO harness that lets us drive the avatar
// states by hand, proving the brain→avatar seam. Next step: replace the buttons with
// real Gemini Live voice events that set `state`/`mood` automatically.
export default function App() {
  const [state, setState] = useState(AvatarState.IDLE);
  const [mood, setMood] = useState(Mood.NEUTRAL);

  // Simulate a full turn: thinking → talking → reacting → idle.
  function simulateTurn(turnMood) {
    setMood(turnMood);
    setState(AvatarState.THINKING);
    setTimeout(() => setState(AvatarState.TALKING), 700);
    setTimeout(() => setState(AvatarState.REACTING), 2600);
    setTimeout(() => setState(AvatarState.IDLE), 4200);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Mira</h1>
        <p className="tagline">your AI stylist — voice-first, character-driven</p>
      </header>

      <Avatar state={state} mood={mood} />

      <div className="controls">
        <p className="controls-hint">
          Demo harness — drive the avatar states (real voice wiring is next):
        </p>
        <div className="btn-row">
          <button onClick={() => simulateTurn(Mood.NEUTRAL)}>Ask Mira</button>
          <button onClick={() => simulateTurn(Mood.EXCITED)}>Excited turn</button>
          <button onClick={() => simulateTurn(Mood.LOW)}>Tough-day turn</button>
        </div>
        <div className="btn-row subtle">
          <button onClick={() => setState(AvatarState.IDLE)}>idle</button>
          <button onClick={() => setState(AvatarState.THINKING)}>thinking</button>
          <button onClick={() => setState(AvatarState.TALKING)}>talking</button>
          <button onClick={() => setState(AvatarState.REACTING)}>reacting</button>
        </div>
      </div>

      <footer className="app-footer">
        state: <code>{state}</code> · mood: <code>{mood}</code>
      </footer>
    </div>
  );
}
