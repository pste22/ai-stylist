/**
 * Soft hand-sketched fashion motifs behind Mira chat / voice console.
 * Decorative only — pointer-events none, reduced-motion aware.
 */
const ICONS = [
  {
    id: "hanger",
    paths: [
      "M32 10c-3 0-5 2.2-5 5.2 0 2.4 1.4 3.8 3.2 5.1L18 36.5c-1.2 1.3-.4 3.5 1.5 3.5h25c1.9 0 2.7-2.2 1.5-3.5L33.8 20.3c1.8-1.3 3.2-2.7 3.2-5.1 0-3-2-5.2-5-5.2z",
      "M29.5 14.5c.3-1.4 1.2-2.2 2.5-2.2",
    ],
  },
  {
    id: "dress",
    paths: [
      "M26 12h12l3 8 9 4-6 28H20l-6-28 9-4z",
      "M26 12c2 3 4 4 6 4s4-1 6-4",
    ],
  },
  {
    id: "heel",
    paths: [
      "M12 34c8-2 16-3 22 2 4 3 8 6 14 6v4c-8 1-13-1-18-5-5-4-11-4-18-3z",
      "M48 42v10M44 52h8",
    ],
  },
  {
    id: "tote",
    paths: [
      "M18 24h28l-3 28H21z",
      "M26 24c0-6 3-10 6-10s6 4 6 10",
      "M22 34h20",
    ],
  },
  {
    id: "scarf",
    paths: [
      "M20 18c10-8 28-6 30 8 1 10-8 14-14 12-4-1-6 2-5 8l2 10",
      "M24 22c6-2 14-2 20 2",
    ],
  },
  {
    id: "needle",
    paths: [
      "M18 46l28-28",
      "M42 14c3 0 5 2 5 5 0 4-5 7-5 7s-5-3-5-7c0-3 2-5 5-5z",
      "M20 48c4 2 8 2 12 0",
    ],
  },
  {
    id: "mirror",
    ellipses: [{ cx: 32, cy: 26, rx: 14, ry: 16 }],
    paths: ["M32 42v12M24 54h16", "M26 20c2-4 6-6 10-5"],
  },
  {
    id: "ring",
    circles: [{ cx: 32, cy: 36, r: 12 }],
    paths: ["M26 24l6-10 6 10", "M28 24h8"],
  },
];

const PLACEMENTS = [
  { icon: 0, cls: "csw-s1" },
  { icon: 1, cls: "csw-s2" },
  { icon: 2, cls: "csw-s3" },
  { icon: 3, cls: "csw-s4" },
  { icon: 4, cls: "csw-s5" },
  { icon: 5, cls: "csw-s6" },
  { icon: 6, cls: "csw-s7" },
  { icon: 7, cls: "csw-s8" },
  { icon: 1, cls: "csw-s9" },
  { icon: 0, cls: "csw-s10" },
  { icon: 3, cls: "csw-s11" },
  { icon: 2, cls: "csw-s12" },
  { icon: 7, cls: "csw-s13" },
  { icon: 4, cls: "csw-s14" },
];

function SketchIcon({ def }) {
  return (
    <>
      {(def.paths || []).map((d) => (
        <path key={`g-${d.slice(0, 18)}`} className="csw-ghost" d={d} />
      ))}
      {(def.ellipses || []).map((e) => (
        <ellipse key={`ge-${e.cx}`} className="csw-ghost" cx={e.cx} cy={e.cy} rx={e.rx} ry={e.ry} />
      ))}
      {(def.circles || []).map((c) => (
        <circle key={`gc-${c.cx}`} className="csw-ghost" cx={c.cx} cy={c.cy} r={c.r} />
      ))}
      {(def.paths || []).map((d) => (
        <path key={`i-${d.slice(0, 18)}`} className="csw-ink" d={d} />
      ))}
      {(def.ellipses || []).map((e) => (
        <ellipse key={`ie-${e.cx}`} className="csw-ink" cx={e.cx} cy={e.cy} rx={e.rx} ry={e.ry} />
      ))}
      {(def.circles || []).map((c) => (
        <circle key={`ic-${c.cx}`} className="csw-ink" cx={c.cx} cy={c.cy} r={c.r} />
      ))}
    </>
  );
}

export default function ChatSketchWallpaper() {
  return (
    <div className="chat-sketch-wallpaper" aria-hidden="true">
      <svg width="0" height="0" className="csw-defs">
        <defs>
          <filter id="csw-wobble" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" seed="3" result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.6" xChannelSelector="R" yChannelSelector="G" />
          </filter>
        </defs>
      </svg>
      {PLACEMENTS.map(({ icon, cls }, i) => (
        <svg key={cls} className={`csw-icon ${cls}`} viewBox="0 0 64 64" style={{ "--csw-i": i }}>
          <SketchIcon def={ICONS[icon]} />
        </svg>
      ))}
    </div>
  );
}
