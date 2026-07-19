import { useState } from "react";

const OCCASIONS = ["Festival", "Wedding guest", "Concert", "First date", "Work event", "Trip", "Other"];
const VIBES = ["Relaxed", "Polished", "Playful", "Statement-making", "Minimal"];

export default function EventBriefFlow({ onStart, onCancel }) {
  const [brief, setBrief] = useState({
    occasion: "", date: "", location: "", dress_code: "",
    vibe: "", budget_max: "", constraints: "",
  });
  const update = (key, value) => setBrief((current) => ({ ...current, [key]: value }));
  const submit = (event) => {
    event.preventDefault();
    if (!brief.occasion) return;
    onStart({
      ...brief,
      budget_max: brief.budget_max ? Number(brief.budget_max) : null,
    });
  };

  return (
    <main className="event-brief-screen">
      <form className="event-brief-card" onSubmit={submit}>
        <button className="event-brief-close" type="button" onClick={onCancel}>← Back</button>
        <p className="event-brief-eyebrow">Mira Event Edit</p>
        <h1>Let’s get your look right.</h1>
        <p className="event-brief-intro">
          Tell Mira the moment you’re dressing for. She’ll build three grounded looks
          from products you can actually shop.
        </p>

        <fieldset>
          <legend>What are you dressing for?</legend>
          <div className="event-brief-chips">
            {OCCASIONS.map((occasion) => (
              <button key={occasion} type="button"
                className={brief.occasion === occasion ? "is-selected" : ""}
                onClick={() => update("occasion", occasion)}>
                {occasion}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="event-brief-grid">
          <label>Date<input type="date" value={brief.date} onChange={(e) => update("date", e.target.value)} /></label>
          <label>Location<input placeholder="e.g. Austin, TX" value={brief.location} onChange={(e) => update("location", e.target.value)} /></label>
          <label>Dress code<input placeholder="Optional" value={brief.dress_code} onChange={(e) => update("dress_code", e.target.value)} /></label>
          <label>Total outfit budget<input type="number" min="0" inputMode="decimal" placeholder="Optional" value={brief.budget_max} onChange={(e) => update("budget_max", e.target.value)} /></label>
        </div>

        <fieldset>
          <legend>How do you want to feel?</legend>
          <div className="event-brief-chips">
            {VIBES.map((vibe) => (
              <button key={vibe} type="button"
                className={brief.vibe === vibe ? "is-selected" : ""}
                onClick={() => update("vibe", vibe)}>
                {vibe}
              </button>
            ))}
          </div>
        </fieldset>

        <label className="event-brief-notes">
          Non-negotiables
          <textarea rows="3" placeholder="No heels, needs to arrive by Thursday, breathable fabrics…"
            value={brief.constraints} onChange={(e) => update("constraints", e.target.value)} />
        </label>
        <button className="event-brief-submit" type="submit" disabled={!brief.occasion}>
          Build my three looks →
        </button>
        <p className="event-brief-disclosure">Mira may earn a commission when you shop a recommendation. It never changes the recommendation or your price.</p>
      </form>
    </main>
  );
}
