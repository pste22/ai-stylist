import {
  dismissFinishNudgeForToday,
  emptySlotPrompt,
  hideStripThisSession,
  progressLabel,
  shouldShowFinishNudge,
  visibleSlots,
} from "./lookProgress.js";
import { hdProductImageUrl, isProductPhotoUrl } from "./imageUrl.js";

export function FinishLookNudge({ state, onFinish, onDismiss }) {
  if (!shouldShowFinishNudge(state)) return null;
  const slots = visibleSlots(state);
  const summary = slots
    .map((s) => `${s.label}${s.product ? " ✓" : ""}`)
    .join(" · ");

  return (
    <div className="finish-nudge" role="status">
      <div className="finish-nudge-copy">
        <p className="finish-nudge-title">Your look is almost there</p>
        <p className="finish-nudge-sub">{summary}</p>
      </div>
      <div className="finish-nudge-actions">
        <button
          type="button"
          className="finish-nudge-primary"
          onClick={() => {
            dismissFinishNudgeForToday();
            onFinish?.();
          }}
        >
          Finish this look
        </button>
        <button
          type="button"
          className="finish-nudge-secondary"
          onClick={() => {
            dismissFinishNudgeForToday();
            onDismiss?.();
          }}
        >
          Not now
        </button>
      </div>
    </div>
  );
}

export default function LookProgressStrip({
  state,
  onComplete,
  onEmptySlot,
  onSelectProduct,
  onHide,
}) {
  const slots = visibleSlots(state);
  const filled = slots.filter((s) => s.product).length;
  if (filled < 1) return null;

  return (
    <div className="look-progress-strip" role="region" aria-label="Look in progress">
      <div className="look-progress-head">
        <span className="look-progress-title">Your look</span>
        <span className="look-progress-meta">{progressLabel(state)}</span>
        <button
          type="button"
          className="look-progress-hide"
          title="Hide for now"
          onClick={() => { hideStripThisSession(); onHide?.(); }}
        >
          ✕
        </button>
      </div>
      <div className="look-progress-slots">
        {slots.map((s) => {
          const p = s.product;
          const img = p && isProductPhotoUrl(p.image_url)
            ? hdProductImageUrl(p.image_url, 200)
            : p?.image_url;
          return (
            <button
              key={s.key}
              type="button"
              className={`look-progress-slot${p ? " is-filled" : ""}`}
              onClick={() => {
                if (p) onSelectProduct?.(p);
                else onEmptySlot?.(emptySlotPrompt(s.key, state));
              }}
              title={p ? p.name : `Add ${s.label}`}
            >
              {p && img ? (
                <img className="look-progress-thumb" src={img} alt="" loading="lazy" />
              ) : (
                <span className="look-progress-empty" aria-hidden="true" />
              )}
              <span className="look-progress-label">
                {p ? "✓ " : ""}{s.label}
              </span>
            </button>
          );
        })}
      </div>
      <button type="button" className="look-progress-cta" onClick={onComplete}>
        Complete the look
      </button>
    </div>
  );
}
