import { useEffect, useRef, useState } from "react";
import {
  assembleDraft,
  fetchReviewDraft,
  reviewChatOpen,
  reviewChatTurn,
  starLabel,
} from "./reviewAssist.js";

function Stars({ value, size = "sm" }) {
  const n = Math.max(0, Math.min(5, Number(value) || 0));
  return (
    <span className={`qv-stars qv-stars--${size}`} aria-label={`${n} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={`qv-star${i <= n ? " is-on" : ""}`}>★</span>
      ))}
    </span>
  );
}

let _mid = 0;
const mkId = () => `rc-${++_mid}`;

export default function ReviewComposer({ product, onSubmit, onCancel }) {
  const open = reviewChatOpen(product);
  const [phase, setPhase] = useState(open.phase);
  const [answers, setAnswers] = useState({ stars: 0, fit: "", notes: [] });
  const [messages, setMessages] = useState(() => [
    { id: mkId(), role: "mira", text: open.mira },
  ]);
  const [shortcuts, setShortcuts] = useState(open.shortcuts);
  const [draft, setDraft] = useState("");
  const [input, setInput] = useState("");
  const [photo, setPhoto] = useState(null);
  const [thinking, setThinking] = useState(false);
  const [busy, setBusy] = useState(false);
  const threadRef = useRef(null);
  const inputRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking, draft, phase]);

  useEffect(() => {
    // Focus the reply box so typing is the default path
    inputRef.current?.focus();
  }, [phase]);

  function pushMira(text) {
    setMessages((prev) => [...prev, { id: mkId(), role: "mira", text }]);
  }

  function pushYou(text) {
    setMessages((prev) => [...prev, { id: mkId(), role: "you", text }]);
  }

  async function handleReply(raw) {
    const text = (raw || "").trim();
    if (!text || busy) return;
    setInput("");
    pushYou(text);
    setBusy(true);
    setThinking(true);
    setShortcuts([]);

    // Tiny pause so it feels like a reply, not a form submit
    await new Promise((r) => setTimeout(r, 280));

    if (phase === "draft" && /^(post|submit|looks good)$/i.test(text)) {
      setThinking(false);
      setBusy(false);
      onSubmit({
        stars: answers.stars || 5,
        fit: answers.fit || "true",
        text: draft || assembleDraft({ product, answers }),
        photo,
      });
      return;
    }

    if (phase === "draft" && /shorter|punchier|tighten/i.test(text)) {
      const short = (draft || "")
        .split(/(?<=[.!?])\s+/)
        .slice(0, 2)
        .join(" ")
        .slice(0, 160);
      setDraft(short);
      setThinking(false);
      pushMira("Shortened. Edit below or say “post” when it feels right.");
      setShortcuts([{ label: "Post review", value: "post" }]);
      setBusy(false);
      return;
    }

    const turn = reviewChatTurn({ product, phase, answers, userText: text });
    setAnswers(turn.answers);
    setPhase(turn.phase);
    setThinking(false);
    pushMira(turn.mira);
    setShortcuts(turn.shortcuts || []);

    if (turn.phase === "draft" && turn.draft) {
      setDraft(turn.draft);
      // Polish with API in background — keep user's words if API fails
      setThinking(true);
      const polished = await fetchReviewDraft({
        product,
        answers: turn.answers,
        draft: turn.draft,
      });
      setThinking(false);
      if (polished.draft) setDraft(polished.draft);
      if (polished.coach) pushMira(polished.coach);
      setShortcuts([
        { label: "Post review", value: "post" },
        { label: "Make it shorter", value: "Make it shorter" },
      ]);
    }

    if (turn.submit) {
      onSubmit({
        stars: turn.answers.stars || 5,
        fit: turn.answers.fit || "true",
        text: turn.draft || draft,
        photo,
      });
    }

    setBusy(false);
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function onFile(e) {
    const file = e.target.files?.[0];
    if (!file || !file.type.startsWith("image/")) return;
    if (file.size > 900_000) {
      pushMira("That photo's a bit large — try one under ~900KB?");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setPhoto(String(reader.result || ""));
      pushMira("Photo added — looks good next to your words.");
    };
    reader.readAsDataURL(file);
  }

  const placeholder =
    phase === "stars" ? "e.g. 4, or “really liked it”"
      : phase === "fit" ? "e.g. a bit snug / true to size"
        : phase === "detail" ? "Tell me what stood out…"
          : phase === "more" ? "Anything else, or “that's all”"
            : phase === "draft" ? "Tweak the draft, or say “post”"
              : "Type your reply…";

  return (
    <div className="qv-review-chat">
      <div className="qv-review-chat-head">
        <div>
          <p className="qv-review-form-title">Review with Mira</p>
          <p className="qv-review-sub">Just chat — shortcuts are optional</p>
        </div>
        <button type="button" className="qv-review-cancel" onClick={onCancel}>Close</button>
      </div>

      <div className="qv-review-thread" ref={threadRef} role="log" aria-live="polite">
        {messages.map((m) => (
          <div key={m.id} className={`qv-rc-bubble qv-rc-bubble--${m.role}`}>
            {m.role === "mira" && <span className="qv-rc-avatar" aria-hidden="true">M</span>}
            <p>{m.text}</p>
          </div>
        ))}
        {thinking && (
          <div className="qv-rc-bubble qv-rc-bubble--mira qv-rc-bubble--thinking">
            <span className="qv-rc-avatar" aria-hidden="true">M</span>
            <p><span className="qv-rc-dots"><i /><i /><i /></span></p>
          </div>
        )}
      </div>

      {phase === "draft" && (
        <div className="qv-rc-draft">
          <div className="qv-rc-draft-meta">
            {!!answers.stars && <Stars value={answers.stars} />}
            {!!answers.stars && <span>{starLabel(answers.stars)}</span>}
            {answers.fit && (
              <span className="qv-review-fit">
                {answers.fit === "true" ? "True to size" : answers.fit === "tight" ? "Runs tight" : "Runs loose"}
              </span>
            )}
          </div>
          <textarea
            className="qv-review-text"
            value={draft}
            onChange={(e) => setDraft(e.target.value.slice(0, 280))}
            rows={3}
            aria-label="Review draft"
          />
          <div className="qv-review-char">
            <span>Edit freely — this is what others will read</span>
            <span>{draft.length}/280</span>
          </div>
          <div className="qv-review-photo-row">
            <button type="button" className="qv-review-photo-btn" onClick={() => fileRef.current?.click()}>
              {photo ? "Change photo" : "Add a real photo"}
            </button>
            <input ref={fileRef} type="file" accept="image/*" hidden onChange={onFile} />
            {photo && <img className="qv-review-photo-preview" src={photo} alt="" />}
          </div>
          <button
            type="button"
            className="qv-review-submit qv-rc-post"
            disabled={!answers.stars || !draft.trim()}
            onClick={() => onSubmit({
              stars: answers.stars || 5,
              fit: answers.fit || "true",
              text: draft.trim(),
              photo,
            })}
          >
            Post review
          </button>
        </div>
      )}

      {phase !== "draft" && shortcuts.length > 0 && (
        <div className="qv-rc-shortcuts" aria-label="Quick replies">
          {shortcuts.map((s) => (
            <button
              key={s.value}
              type="button"
              className="qv-rc-shortcut"
              disabled={busy}
              onClick={() => handleReply(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {phase === "draft" && shortcuts.length > 0 && (
        <div className="qv-rc-shortcuts" aria-label="Quick replies">
          {shortcuts.map((s) => (
            <button
              key={s.value}
              type="button"
              className="qv-rc-shortcut"
              disabled={busy}
              onClick={() => handleReply(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      <form
        className="qv-rc-input-bar"
        onSubmit={(e) => {
          e.preventDefault();
          handleReply(input);
        }}
      >
        <input
          ref={inputRef}
          className="qv-rc-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          disabled={busy}
          enterKeyHint="send"
        />
        <button type="submit" className="qv-rc-send" disabled={busy || !input.trim()} aria-label="Send">
          ↑
        </button>
      </form>
      <p className="qv-review-note">Saved on this device for now · syncing later</p>
    </div>
  );
}
