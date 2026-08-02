import { useState, useRef } from "react";

const SWIPE_THRESHOLD = 80; // px drag to trigger

export default function SwipeStack({ products = [], onLove, onSkip, onDone }) {
  const [index, setIndex] = useState(0);
  const [saved, setSaved] = useState(0);
  const [drag, setDrag] = useState({ x: 0, dragging: false, startX: 0 });
  const cardRef = useRef(null);

  const current = products[index];

  const decide = (liked) => {
    if (!current) return;
    if (liked) {
      onLove?.(current);
      setSaved(s => s + 1);
    } else {
      onSkip?.(current);
    }
    setDrag({ x: 0, dragging: false, startX: 0 });
    setIndex(i => i + 1);
  };

  // Mouse/touch drag handlers
  const onPointerDown = (e) => {
    setDrag({ x: 0, dragging: true, startX: e.clientX ?? e.touches?.[0]?.clientX ?? 0 });
  };
  const onPointerMove = (e) => {
    if (!drag.dragging) return;
    const cx = e.clientX ?? e.touches?.[0]?.clientX ?? drag.startX;
    setDrag(d => ({ ...d, x: cx - d.startX }));
  };
  const onPointerUp = () => {
    if (!drag.dragging) return;
    if (drag.x > SWIPE_THRESHOLD) decide(true);
    else if (drag.x < -SWIPE_THRESHOLD) decide(false);
    else setDrag({ x: 0, dragging: false, startX: 0 });
  };

  const done = index >= products.length;

  if (done) {
    return (
      <div className="swipe-done">
        <div className="swipe-done-icon">✦</div>
        <p className="swipe-done-head">Mira knows your vibe now</p>
        <p className="swipe-done-sub">Saved {saved} of {products.length} — your recommendations just got personal.</p>
        <button className="swipe-done-btn" onClick={onDone}>See my picks →</button>
      </div>
    );
  }

  const rotation = (drag.x / 300) * 15;
  const liking = drag.x > 40;
  const skipping = drag.x < -40;

  return (
    <div className="swipe-stack">
      {/* Progress */}
      <div className="swipe-progress">
        <div className="swipe-progress-bar" style={{ width: `${(index / products.length) * 100}%` }} />
      </div>
      <p className="swipe-counter">{index + 1} / {products.length}</p>

      {/* Next card peek */}
      {products[index + 1] && (
        <div className="swipe-card swipe-card--behind">
          <img src={products[index + 1].image_url} alt="" className="swipe-card-img" />
        </div>
      )}

      {/* Active card */}
      <div
        ref={cardRef}
        className="swipe-card swipe-card--active"
        style={{
          transform: `translateX(${drag.x}px) rotate(${rotation}deg)`,
          transition: drag.dragging ? "none" : "transform .3s ease",
          cursor: drag.dragging ? "grabbing" : "grab",
        }}
        onMouseDown={onPointerDown}
        onMouseMove={onPointerMove}
        onMouseUp={onPointerUp}
        onMouseLeave={onPointerUp}
        onTouchStart={onPointerDown}
        onTouchMove={onPointerMove}
        onTouchEnd={onPointerUp}
      >
        {liking  && <div className="swipe-badge swipe-badge--yes">♥ Save</div>}
        {skipping && <div className="swipe-badge swipe-badge--no">✕ Skip</div>}

        <img src={current.image_url} alt={current.name} className="swipe-card-img" loading="lazy" />

        <div className="swipe-card-info">
          <p className="swipe-card-cat">{current.category}</p>
          <p className="swipe-card-name">{current.name}</p>
          <p className="swipe-card-price">₹{Number(current.price || 0).toLocaleString("en-IN")}</p>
        </div>
      </div>

      {/* Buttons */}
      <div className="swipe-btns">
        <button className="swipe-btn swipe-btn--skip" onClick={() => decide(false)} aria-label="Skip">✕</button>
        <p className="swipe-hint">drag or tap</p>
        <button className="swipe-btn swipe-btn--love" onClick={() => decide(true)} aria-label="Save">♥</button>
      </div>
    </div>
  );
}
