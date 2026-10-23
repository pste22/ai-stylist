/** Stroke icons that scale cleanly on phone browsers (Unicode glyphs do not). */
const PATHS = {
  bag: (
    <>
      <path d="M6 8h12l-1 13H7L6 8z" />
      <path d="M9 8V7a3 3 0 0 1 6 0v1" />
    </>
  ),
  cart: (
    <>
      <circle cx="9" cy="20" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="18" cy="20" r="1.4" fill="currentColor" stroke="none" />
      <path d="M3 4h2l2.2 11h11.3l2-8H7" />
    </>
  ),
  user: <circle cx="12" cy="8" r="3.2" />,
  userBody: <path d="M5 19c.8-3.4 3.4-5 7-5s6.2 1.6 7 5" />,
  heart: <path d="M12 19s-7-4.4-7-9a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 4.6-7 9-7 9z" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  back: <path d="M15 5l-7 7 7 7" />,
  chevronLeft: <path d="M14 5l-7 7 7 7" />,
  chevronRight: <path d="M10 5l7 7-7 7" />,
  send: <path d="M12 5v14M7 10l5-5 5 5" />,
  camera: (
    <>
      <path d="M4 8h3l2-2h6l2 2h3v11H4V8z" />
      <circle cx="12" cy="13.5" r="3.2" />
    </>
  ),
  hanger: <path d="M12 5a2 2 0 1 1 2 2c0 1-8 5-8 8h12c0-3-8-7-8-8" />,
  history: <path d="M12 7v5l3 2M5.2 9A8 8 0 1 0 7 6.2M5 5v4h4" />,
  stop: <rect x="7" y="7" width="10" height="10" rx="1.2" />,
  mic: (
    <>
      <rect x="9" y="3.5" width="6" height="10" rx="3" />
      <path d="M6.5 11.5a5.5 5.5 0 0 0 11 0M12 17v3" />
    </>
  ),
  keyboard: (
    <>
      <rect x="3" y="7" width="18" height="11" rx="1.5" />
      <path d="M7 11h.01M12 11h.01M17 11h.01M8 15h8" />
    </>
  ),
  fitting: (
    <>
      <rect x="5" y="4" width="14" height="16" rx="2" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </>
  ),
};

const COMBO = {
  user: ["user", "userBody"],
};

export default function Icon({ name, size = 22 }) {
  const keys = COMBO[name] || [name];
  return (
    <svg
      className="mira-icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {keys.map((key) => PATHS[key])}
    </svg>
  );
}
