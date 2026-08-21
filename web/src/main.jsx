import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";
import { initAnalytics } from "./analytics.js";

initAnalytics();

// Keep the app inside the *visible* viewport (iOS Safari chrome + keyboard).
function syncAppHeight() {
  const h = window.visualViewport?.height || window.innerHeight;
  document.documentElement.style.setProperty("--app-height", `${Math.round(h)}px`);
}
syncAppHeight();
window.visualViewport?.addEventListener("resize", syncAppHeight);
window.visualViewport?.addEventListener("scroll", syncAppHeight);
window.addEventListener("orientationchange", () => {
  requestAnimationFrame(syncAppHeight);
});

// Premium Atelier preview — flip to classic via header toggle (localStorage).
// Revert entirely: localStorage.removeItem('mira.uiMode') + hard refresh, or git checkout.
try {
  const mode = localStorage.getItem("mira.uiMode") || "atelier";
  document.documentElement.dataset.mira = mode === "classic" ? "classic" : "atelier";
} catch {
  document.documentElement.dataset.mira = "atelier";
}

// NOTE: No React.StrictMode. In dev it double-invokes effects (mount/unmount/remount),
// which races two LiveAvatar WebRTC sessions and tears down the live signaling socket
// (the "WebSocket failed" symptom). Media/WebRTC SDKs can't tolerate that double-mount.
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
