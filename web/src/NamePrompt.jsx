import { useState } from "react";

// Full-screen overlay shown on first visit to collect the user's name.
// Mira uses it to greet them personally and persist memory across sessions.
export default function NamePrompt({ onSubmit }) {
  const [value, setValue] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    const name = value.trim();
    if (name) onSubmit(name);
  }

  return (
    <div className="name-prompt-overlay">
      <div className="name-prompt-card">
        <h2>Hi, I'm Mira 👋</h2>
        <p>Your personal AI stylist. What should I call you?</p>
        <form onSubmit={handleSubmit}>
          <input
            className="name-input"
            type="text"
            placeholder="Your first name"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
            maxLength={40}
          />
          <button
            className="primary"
            type="submit"
            disabled={!value.trim()}
          >
            Let's go →
          </button>
        </form>
      </div>
    </div>
  );
}
