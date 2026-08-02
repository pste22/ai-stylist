import { useEffect, useState } from "react";
import { supabase } from "./supabaseClient.js";

const BUDGET_BANDS = {
  budget: { min: null, max: 50 },
  mid: { min: 50, max: 150 },
  premium: { min: 150, max: 400 },
  luxury: { min: 400, max: null },
};

export function useOnboarding(userId) {
  const [needsOnboarding, setNeedsOnboarding] = useState(null);
  const [prefs, setPrefs]                     = useState(null);

  useEffect(() => {
    if (!userId) return;
    supabase
      .from("user_preferences")
      .select("style_vibe, shopping_focus, top_size, bottom_size, budget, pin_code")
      .eq("user_id", userId)
      .maybeSingle()
      .then(({ data, error }) => {
        if (error) { console.error("prefs fetch:", error); setNeedsOnboarding(false); return; }
        if (data) { setPrefs(data); setNeedsOnboarding(false); }
        else      { setNeedsOnboarding(true); }
      });
  }, [userId]);

  const completeOnboarding = async ({ styleVibe, shoppingFocus, topSize, bottomSize, budget, pinCode } = {}) => {
    if (!userId) return;
    const band = BUDGET_BANDS[budget] || {};
    const updates = {
      style_vibe:     styleVibe     ?? null,
      shopping_focus: shoppingFocus ?? null,
      top_size:       topSize       ?? null,
      bottom_size:    bottomSize    ?? null,
      budget:         budget        ?? null,
      pin_code:       pinCode       ?? null,
      vibes:          styleVibe ? [styleVibe] : [],
      budget_min:     band.min ?? null,
      budget_max:     band.max ?? null,
    };

    // Check if row exists first, then insert or update
    const { data: existing } = await supabase
      .from("user_preferences")
      .select("user_id")
      .eq("user_id", userId)
      .maybeSingle();

    const { error } = existing
      ? await supabase.from("user_preferences").update(updates).eq("user_id", userId)
      : await supabase.from("user_preferences").insert({ user_id: userId, ...updates });

    if (!error) {
      setPrefs({ user_id: userId, ...updates });
      setNeedsOnboarding(false);
    } else {
      console.error("save prefs:", error);
    }
  };

  const updatePrefs = async (updates) => {
    const { error } = await supabase
      .from("user_preferences")
      .update(updates)
      .eq("user_id", userId);
    if (!error) setPrefs(p => ({ ...p, ...updates }));
  };

  return { needsOnboarding, prefs, completeOnboarding, updatePrefs };
}
