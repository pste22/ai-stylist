import { useEffect, useRef, useState } from "react";

const SLOW_TYPES = new Set(["slow-2g", "2g"]);

export function getQuality(conn) {
  if (!conn) return "unknown";
  if (conn.saveData)                     return "datasaver";
  if (SLOW_TYPES.has(conn.effectiveType)) return "slow";
  if (conn.effectiveType === "3g")        return "moderate";
  return "good";
}

export function checkNetworkNow() {
  const conn = typeof navigator !== "undefined" ? navigator.connection ?? null : null;
  return getQuality(conn);
}

/**
 * Tracks navigator.connection quality changes.
 *
 * Returns:
 *   quality       — "good" | "moderate" | "slow" | "datasaver" | "unknown"
 *   prevQuality   — previous value (detect transitions)
 *   supported     — whether the Network Information API is available
 */
export function useNetworkMode() {
  const conn = typeof navigator !== "undefined" ? navigator.connection ?? null : null;
  const supported = !!conn;

  const [quality, setQuality]         = useState(() => getQuality(conn));
  const prevQualityRef                = useRef(quality);
  const [prevQuality, setPrevQuality] = useState(quality);

  useEffect(() => {
    if (!conn) return;
    const update = () => {
      const next = getQuality(conn);
      setPrevQuality(prevQualityRef.current);
      prevQualityRef.current = next;
      setQuality(next);
    };
    conn.addEventListener("change", update);
    return () => conn.removeEventListener("change", update);
  }, [conn]);

  const isSlow     = quality === "slow" || quality === "datasaver";
  const isRecovered = (prevQuality === "slow" || prevQuality === "datasaver") && quality === "good";

  return { quality, prevQuality, isSlow, isRecovered, supported };
}
