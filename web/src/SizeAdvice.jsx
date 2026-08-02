import { getSizeAdvice } from "./sizeAdvisor.js";

const TOP_SIZES = ["XS", "S", "M", "L", "XL", "XXL"];
const BOTTOM_SIZES = ["XS / 24", "S / 26", "M / 28", "L / 30", "XL / 32", "XXL / 34"];

// A data-driven size recommendation. If the user hasn't set a usual size, it
// offers an inline picker so they can get a tip on the spot.
export default function SizeAdvice({ product, prefs, onSetSize }) {
  const a = getSizeAdvice(product, prefs);
  if (!a || a.kind === "onesize") return null;

  if (a.kind === "shoes") {
    return (
      <div className="size-advice">
        <span className="size-advice-icon">📏</span>
        <p className="size-advice-text">{a.note}</p>
      </div>
    );
  }

  if (a.kind === "need_size") {
    const sizes = a.field === "bottom_size" ? BOTTOM_SIZES : TOP_SIZES;
    return (
      <div className="size-advice size-advice--pick">
        <p className="size-advice-text">📏 Pick your usual size for a fit tip</p>
        <div className="size-advice-chips">
          {sizes.map((s) => (
            <button key={s} className="size-advice-chip" onClick={() => onSetSize?.(a.field, s)}>
              {s}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`size-advice size-advice--${a.fit}`}>
      <span className="size-advice-icon">📏</span>
      <p className="size-advice-text"><strong>Fit tip:</strong> {a.note}</p>
    </div>
  );
}
