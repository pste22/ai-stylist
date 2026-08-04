import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "mira_platform_pulse_v1";
const COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
const MIN_ACTIONS = 3;
const SHOW_DELAY_MS = 4500; // let them finish the moment before asking

function load() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function save(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch { /* quota / private mode */ }
}

function forcePulse() {
  if (typeof location === "undefined") return false;
  return new URLSearchParams(location.search).has("pulse");
}

/**
 * Occasional "Was Mira helpful?" pulse.
 * - Counts meaningful actions in-session
 * - Shows at most once per 7 days (unless ?pulse=1)
 * - After a few "yes" answers, also asks the miss-her question
 */
export function usePlatformPulse({ enabled = true } = {}) {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState("helpful"); // helpful | why | miss | thanks
  const stateRef = useRef(load());
  const actionsRef = useRef(0);
  const scheduledRef = useRef(false);
  const timerRef = useRef(null);

  const canShow = useCallback(() => {
    if (forcePulse()) return true;
    const s = stateRef.current;
    if (s.snoozeUntil && Date.now() < s.snoozeUntil) return false;
    if (s.lastShownAt && Date.now() - s.lastShownAt < COOLDOWN_MS) return false;
    return true;
  }, []);

  const markShown = useCallback(() => {
    const s = { ...stateRef.current, lastShownAt: Date.now() };
    stateRef.current = s;
    save(s);
  }, []);

  const snooze = useCallback((ms = COOLDOWN_MS) => {
    const s = { ...stateRef.current, snoozeUntil: Date.now() + ms, lastShownAt: Date.now() };
    stateRef.current = s;
    save(s);
  }, []);

  const trySchedule = useCallback(() => {
    if (!enabled || scheduledRef.current || visible) return;
    if (actionsRef.current < MIN_ACTIONS) return;
    if (!canShow()) return;
    scheduledRef.current = true;
    timerRef.current = setTimeout(() => {
      markShown();
      setStep("helpful");
      setVisible(true);
    }, forcePulse() ? 600 : SHOW_DELAY_MS);
  }, [enabled, visible, canShow, markShown]);

  const recordAction = useCallback((kind = "generic") => {
    if (!enabled) return;
    actionsRef.current += 1;
    // Heavier moments count as two
    if (kind === "try_on" || kind === "ask_product" || kind === "buy") {
      actionsRef.current += 1;
    }
    trySchedule();
  }, [enabled, trySchedule]);

  useEffect(() => {
    if (forcePulse() && enabled && canShow()) {
      scheduledRef.current = true;
      timerRef.current = setTimeout(() => {
        markShown();
        setStep("helpful");
        setVisible(true);
      }, 800);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [enabled, canShow, markShown]);

  const dismiss = useCallback(() => {
    setVisible(false);
    snooze();
  }, [snooze]);

  const submitHelpful = useCallback((value) => {
    const s = {
      ...stateRef.current,
      lastHelpful: value,
      helpfulCount: (stateRef.current.helpfulCount || 0) + (value === "yes" ? 1 : 0),
      responses: [
        ...(stateRef.current.responses || []).slice(-19),
        { t: Date.now(), helpful: value },
      ],
    };
    stateRef.current = s;
    save(s);

    if (value === "yes") {
      // Every 3rd yes → miss-her question; else thanks
      if ((s.helpfulCount || 0) % 3 === 0) {
        setStep("miss");
      } else {
        setStep("thanks");
        setTimeout(() => { setVisible(false); snooze(); }, 1600);
      }
    } else {
      setStep("why");
    }
  }, [snooze]);

  const submitWhy = useCallback((reason, note = "") => {
    const s = {
      ...stateRef.current,
      responses: [
        ...(stateRef.current.responses || []).slice(-19),
        { t: Date.now(), helpful: stateRef.current.lastHelpful, reason, note },
      ],
    };
    stateRef.current = s;
    save(s);
    setStep("thanks");
    setTimeout(() => { setVisible(false); snooze(); }, 1600);
  }, [snooze]);

  const submitMiss = useCallback((value) => {
    const s = {
      ...stateRef.current,
      lastMiss: value,
      responses: [
        ...(stateRef.current.responses || []).slice(-19),
        { t: Date.now(), miss_her: value },
      ],
    };
    stateRef.current = s;
    save(s);
    setStep("thanks");
    setTimeout(() => { setVisible(false); snooze(); }, 1600);
  }, [snooze]);

  return {
    visible,
    step,
    recordAction,
    dismiss,
    submitHelpful,
    submitWhy,
    submitMiss,
  };
}
