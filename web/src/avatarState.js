// Canonical avatar states. The brain (Python) drives ONE of these; the UI just renders.
// Mapping (see docs/14-ui-strategy.md):
//   idle      ← waiting for input
//   thinking  ← backchannel() emitted (P2-4)
//   talking   ← reply_stream() streaming
//   reacting  ← mood detected (P2-5); use moods below for flavor
export const AvatarState = {
  IDLE: "idle",
  THINKING: "thinking",
  TALKING: "talking",
  REACTING: "reacting",
};

export const Mood = {
  NEUTRAL: "neutral",
  EXCITED: "excited",
  LOW: "low",
};
