import { useState } from "react";
import { track } from "./analytics.js";

const WHY_CHIPS = [
  { id: "slow", label: "Too slow" },
  { id: "picks", label: "Wrong picks" },
  { id: "hard", label: "Hard to use" },
  { id: "other", label: "Something else" },
];

export default function PlatformPulse({
  step,
  onDismiss,
  onHelpful,
  onWhy,
  onMiss,
}) {
  const [note, setNote] = useState("");
  const [why, setWhy] = useState("");

  if (!step) return null;

  return (
    <div className="pp-root" role="dialog" aria-label="Quick feedback">
      <div className="pp-card">
        <button type="button" className="pp-close" onClick={onDismiss} aria-label="Dismiss">✕</button>

        {step === "helpful" && (
          <>
            <p className="pp-eyebrow">Quick one</p>
            <h3 className="pp-title">Was Mira helpful today?</h3>
            <p className="pp-sub">Takes two seconds — helps us make her better.</p>
            <div className="pp-actions">
              <button
                type="button"
                className="pp-btn pp-btn--yes"
                onClick={() => { track("platform_feedback", { helpful: "yes" }); onHelpful("yes"); }}
              >
                Yes
              </button>
              <button
                type="button"
                className="pp-btn"
                onClick={() => { track("platform_feedback", { helpful: "a_bit" }); onHelpful("a_bit"); }}
              >
                A bit
              </button>
              <button
                type="button"
                className="pp-btn"
                onClick={() => { track("platform_feedback", { helpful: "no" }); onHelpful("no"); }}
              >
                Not really
              </button>
            </div>
          </>
        )}

        {step === "why" && (
          <>
            <p className="pp-eyebrow">Thanks for honesty</p>
            <h3 className="pp-title">What felt off?</h3>
            <div className="pp-chips">
              {WHY_CHIPS.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={`pp-chip${why === c.id ? " is-on" : ""}`}
                  onClick={() => setWhy(c.id)}
                >
                  {c.label}
                </button>
              ))}
            </div>
            <input
              className="pp-note"
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, 160))}
              placeholder="Optional — one line is enough"
            />
            <div className="pp-actions">
              <button
                type="button"
                className="pp-btn pp-btn--yes"
                disabled={!why && !note.trim()}
                onClick={() => {
                  track("platform_feedback", { helpful: "followup", reason: why, note: note.trim() });
                  onWhy(why || "other", note.trim());
                }}
              >
                Send
              </button>
              <button type="button" className="pp-btn pp-btn--ghost" onClick={onDismiss}>Skip</button>
            </div>
          </>
        )}

        {step === "miss" && (
          <>
            <p className="pp-eyebrow">One more</p>
            <h3 className="pp-title">Would you miss Mira if she were gone?</h3>
            <p className="pp-sub">The honest answer matters more than a polite one.</p>
            <div className="pp-actions">
              <button
                type="button"
                className="pp-btn pp-btn--yes"
                onClick={() => { track("platform_feedback", { miss_her: "yes" }); onMiss("yes"); }}
              >
                Yes, I’d miss her
              </button>
              <button
                type="button"
                className="pp-btn"
                onClick={() => { track("platform_feedback", { miss_her: "maybe" }); onMiss("maybe"); }}
              >
                Maybe
              </button>
              <button
                type="button"
                className="pp-btn"
                onClick={() => { track("platform_feedback", { miss_her: "no" }); onMiss("no"); }}
              >
                Not really
              </button>
            </div>
          </>
        )}

        {step === "thanks" && (
          <>
            <p className="pp-eyebrow">Mira</p>
            <h3 className="pp-title">Thank you</h3>
            <p className="pp-sub">That helps more than you know. Back to styling.</p>
          </>
        )}
      </div>
    </div>
  );
}
