import { useCallback, useEffect, useRef, useState } from "react";

const IDLE_MS    = 20 * 60 * 1000; // 20 min — show warning
const WARNING_MS = 60 * 1000;      // 60 sec — then auto sign-out

const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "click"];

export function useIdleTimeout({ onSignOut, enabled = true }) {
  const [showWarning, setShowWarning]   = useState(false);
  const [countdown, setCountdown]       = useState(60);
  const idleTimer    = useRef(null);
  const warnTimer    = useRef(null);
  const countdownRef = useRef(null);

  const clearAll = useCallback(() => {
    clearTimeout(idleTimer.current);
    clearTimeout(warnTimer.current);
    clearInterval(countdownRef.current);
  }, []);

  const resetIdle = useCallback(() => {
    if (!enabled) return;
    clearAll();
    setShowWarning(false);
    setCountdown(60);
    idleTimer.current = setTimeout(() => {
      setShowWarning(true);
      setCountdown(60);
      // Countdown tick
      countdownRef.current = setInterval(() => {
        setCountdown(c => {
          if (c <= 1) { clearInterval(countdownRef.current); return 0; }
          return c - 1;
        });
      }, 1000);
      // Auto sign-out after warning period
      warnTimer.current = setTimeout(() => {
        setShowWarning(false);
        onSignOut();
      }, WARNING_MS);
    }, IDLE_MS);
  }, [enabled, clearAll, onSignOut]);

  // Attach activity listeners
  useEffect(() => {
    if (!enabled) return;
    resetIdle();
    ACTIVITY_EVENTS.forEach(e => window.addEventListener(e, resetIdle, { passive: true }));
    return () => {
      clearAll();
      ACTIVITY_EVENTS.forEach(e => window.removeEventListener(e, resetIdle));
    };
  }, [enabled, resetIdle, clearAll]);

  const staySignedIn = useCallback(() => {
    resetIdle();
  }, [resetIdle]);

  return { showWarning, countdown, staySignedIn };
}
