import { createClient } from "@supabase/supabase-js";

const supabaseUrl  = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnon = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnon) {
  console.error(
    "Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in web/.env — OAuth won't work."
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnon, {
  auth: { flowType: "implicit" },
});

/**
 * Which OAuth providers the project actually has switched on.
 *
 * Offering a provider that's disabled in Supabase is a dead end: authorize
 * returns 400 "provider is not enabled" and supabase-js reports it as a value
 * rather than throwing, so an unhandled click looks like the button is broken.
 *
 * Returns null if the lookup fails — callers should fall back to showing every
 * provider rather than hiding sign-in over a transient network error.
 */
export async function fetchEnabledProviders() {
  try {
    const res = await fetch(`${supabaseUrl}/auth/v1/settings`, {
      headers: { apikey: supabaseAnon },
    });
    if (!res.ok) return null;
    const settings = await res.json();
    return settings?.external ?? null;
  } catch {
    return null;
  }
}
