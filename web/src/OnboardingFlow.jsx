import { useState } from "react";

const STYLE_OPTIONS = [
  { value: "minimal",  label: "Minimal",  emoji: "🖤", desc: "Clean lines, quiet colours" },
  { value: "classic",  label: "Classic",  emoji: "👔", desc: "Timeless, always elegant" },
  { value: "trendy",   label: "Trendy",   emoji: "✨", desc: "Fresh drops, latest looks" },
  { value: "eclectic", label: "Eclectic", emoji: "🎨", desc: "Bold, expressive, unique" },
];

const FOCUS_OPTIONS = [
  { value: "everyday",   label: "Everyday",   emoji: "👟", desc: "Casual & comfortable" },
  { value: "work",       label: "Work",        emoji: "💼", desc: "Sharp & professional" },
  { value: "occasions",  label: "Occasions",   emoji: "🎉", desc: "Events & nights out" },
  { value: "everything", label: "Everything",  emoji: "🛍️", desc: "A bit of all of it" },
];

const BUDGET_OPTIONS = [
  { value: "budget",   label: "Value",      emoji: "💰", desc: "Under $50 per piece" },
  { value: "mid",      label: "Mid-range",  emoji: "🏷️", desc: "$50 – $150" },
  { value: "premium",  label: "Premium",    emoji: "✦",  desc: "$150 – $400" },
  { value: "luxury",   label: "Luxury",     emoji: "💎", desc: "No limit, best quality" },
];

const TOPS_SIZES    = ["XS","S","M","L","XL","XXL"];
const BOTTOMS_SIZES = ["XS / 24","S / 26","M / 28","L / 30","XL / 32","XXL / 34"];

function TileGrid({ options, selected, onSelect }) {
  return (
    <div className="ob-tiles">
      {options.map(o => (
        <button
          key={o.value}
          className={`ob-tile${selected === o.value ? " ob-tile--on" : ""}`}
          onClick={() => onSelect(o.value)}
        >
          {selected === o.value && <span className="ob-tile-check">✓</span>}
          <span className="ob-tile-emoji">{o.emoji}</span>
          <span className="ob-tile-label">{o.label}</span>
          <span className="ob-tile-desc">{o.desc}</span>
        </button>
      ))}
    </div>
  );
}

function SizeRow({ label, sizes, selected, onSelect }) {
  return (
    <div className="ob-size-row">
      <p className="ob-size-label">{label}</p>
      <div className="ob-size-chips">
        {sizes.map(s => (
          <button
            key={s}
            className={`ob-size-chip${selected === s ? " ob-size-chip--on" : ""}`}
            onClick={() => onSelect(s)}
          >{s}</button>
        ))}
      </div>
    </div>
  );
}

const TOTAL_STEPS = 5; // style, focus, size, budget, pin

export default function OnboardingFlow({ userName, onComplete }) {
  const [step, setStep]           = useState(0); // 0=welcome
  const [styleVibe, setStyle]     = useState(null);
  const [shoppingFocus, setFocus] = useState(null);
  const [topSize, setTopSize]     = useState(null);
  const [bottomSize, setBottom]   = useState(null);
  const [budget, setBudget]       = useState(null);
  const [pinCode, setPinCode]     = useState("");
  const [pinCity, setPinCity]     = useState(null);
  const [pinLoading, setPinLoading] = useState(false);
  const [saving, setSaving]       = useState(false);

  const resolvePin = async (pin) => {
    if (pin.length !== 6) { setPinCity(null); return; }
    setPinLoading(true);
    try {
      const r = await fetch(`https://api.postalpincode.in/pincode/${pin}`);
      const d = await r.json();
      if (d?.[0]?.Status === "Success") {
        const po = d[0].PostOffice?.[0];
        setPinCity(po ? `${po.District}, ${po.State}` : null);
      } else { setPinCity(null); }
    } catch { setPinCity(null); }
    setPinLoading(false);
  };

  const handlePinChange = (val) => {
    const clean = val.replace(/\D/g, "").slice(0, 6);
    setPinCode(clean);
    if (clean.length === 6) resolvePin(clean);
    else setPinCity(null);
  };

  const finish = async () => {
    setSaving(true);
    await onComplete({ styleVibe, shoppingFocus, topSize, bottomSize, budget, pinCode: pinCode || null });
  };

  const pip = (active) => (
    <span className={`ob-pip${active ? " ob-pip--on" : ""}`} />
  );

  return (
    <div className="ob-screen">

      {/* ── Step 0: Welcome ── */}
      {step === 0 && (
        <div className="ob-card ob-card--welcome">
          <div className="ob-avatar">
            <div className="ob-face">
              <div className="ob-eyes"><span /><span /></div>
              <div className="ob-mouth" />
            </div>
          </div>
          <h1 className="ob-welcome-title">Hi {userName} 👋</h1>
          <p className="ob-welcome-sub">
            I'm Mira, your personal AI stylist.<br />
            Four quick questions and I'll give you great picks from the very first message — no generic suggestions.
          </p>
          <button className="ob-btn" onClick={() => setStep(1)}>Let's go →</button>
          <p className="ob-skip" onClick={() => onComplete({})}>Skip, I'll tell Mira myself</p>
        </div>
      )}

      {/* ── Step 1: Style vibe ── */}
      {step === 1 && (
        <div className="ob-card">
          <div className="ob-progress">{pip(true)}{pip(false)}{pip(false)}{pip(false)}{pip(false)}</div>
          <p className="ob-step-label">1 of {TOTAL_STEPS}</p>
          <h2 className="ob-q">What's your style?</h2>
          <p className="ob-hint">Pick the one that feels most like you</p>
          <TileGrid options={STYLE_OPTIONS} selected={styleVibe} onSelect={setStyle} />
          <button className="ob-btn" disabled={!styleVibe} onClick={() => setStep(2)}>Next →</button>
        </div>
      )}

      {/* ── Step 2: Shopping focus ── */}
      {step === 2 && (
        <div className="ob-card">
          <div className="ob-progress">{pip(true)}{pip(true)}{pip(false)}{pip(false)}{pip(false)}</div>
          <p className="ob-step-label">2 of {TOTAL_STEPS}</p>
          <h2 className="ob-q">What do you shop for most?</h2>
          <p className="ob-hint">Mira focuses suggestions here first</p>
          <TileGrid options={FOCUS_OPTIONS} selected={shoppingFocus} onSelect={setFocus} />
          <button className="ob-btn" disabled={!shoppingFocus} onClick={() => setStep(3)}>Next →</button>
        </div>
      )}

      {/* ── Step 3: Sizes ── */}
      {step === 3 && (
        <div className="ob-card">
          <div className="ob-progress">{pip(true)}{pip(true)}{pip(true)}{pip(false)}{pip(false)}</div>
          <p className="ob-step-label">3 of {TOTAL_STEPS}</p>
          <h2 className="ob-q">What sizes do you wear?</h2>
          <p className="ob-hint">So Mira only shows things that fit</p>
          <SizeRow label="Tops / Dresses" sizes={TOPS_SIZES}    selected={topSize}    onSelect={setTopSize} />
          <SizeRow label="Bottoms / Jeans" sizes={BOTTOMS_SIZES} selected={bottomSize} onSelect={setBottom} />
          <button
            className="ob-btn"
            disabled={!topSize || !bottomSize}
            onClick={() => setStep(4)}
          >Next →</button>
          <p className="ob-skip" onClick={() => setStep(4)}>Skip sizes for now</p>
        </div>
      )}

      {/* ── Step 4: Budget ── */}
      {step === 4 && (
        <div className="ob-card">
          <div className="ob-progress">{pip(true)}{pip(true)}{pip(true)}{pip(true)}{pip(false)}</div>
          <p className="ob-step-label">4 of {TOTAL_STEPS}</p>
          <h2 className="ob-q">What's your budget per piece?</h2>
          <p className="ob-hint">Mira won't suggest things out of range</p>
          <TileGrid options={BUDGET_OPTIONS} selected={budget} onSelect={setBudget} />
          <button className="ob-btn" disabled={!budget} onClick={() => setStep(5)}>Next →</button>
        </div>
      )}

      {/* ── Step 5: Pin code ── */}
      {step === 5 && (
        <div className="ob-card">
          <div className="ob-progress">{pip(true)}{pip(true)}{pip(true)}{pip(true)}{pip(true)}</div>
          <p className="ob-step-label">5 of {TOTAL_STEPS}</p>
          <h2 className="ob-q">Where are you shopping from?</h2>
          <p className="ob-hint">Mira uses your PIN code to show products available near you</p>
          <div className="ob-pin-wrap">
            <input
              className="ob-pin-input"
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder="Enter 6-digit PIN code"
              value={pinCode}
              onChange={(e) => handlePinChange(e.target.value)}
            />
            <div className={`ob-city-box ${pinLoading ? "loading" : ""} ${pinCity ? "resolved" : ""} ${pinCode.length === 6 && !pinCity && !pinLoading ? "error" : ""}`}>
              {pinLoading
                ? <><span className="ob-city-spinner" />Looking up location…</>
                : pinCity
                  ? <><span className="ob-city-pin-icon">📍</span>{pinCity}</>
                  : pinCode.length === 6
                    ? <><span className="ob-city-pin-icon">❌</span>PIN not found — check and re-enter</>
                    : <span className="ob-city-placeholder">City / town will appear here</span>
              }
            </div>
          </div>
          <button className="ob-btn" disabled={saving} onClick={finish}>
            {saving ? "Setting up…" : "Meet Mira ✦"}
          </button>
          <p className="ob-skip" onClick={finish}>Skip for now</p>
        </div>
      )}

    </div>
  );
}
