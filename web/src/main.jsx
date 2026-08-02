import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";
import { initAnalytics } from "./analytics.js";

initAnalytics();

// NOTE: No React.StrictMode. In dev it double-invokes effects (mount/unmount/remount),
// which races two LiveAvatar WebRTC sessions and tears down the live signaling socket
// (the "WebSocket failed" symptom). Media/WebRTC SDKs can't tolerate that double-mount.
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
