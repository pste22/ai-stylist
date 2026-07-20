import { useEffect, useState } from "react";
import { supabase } from "./supabaseClient.js";

/**
 * Replaces useUserIdentity with real OAuth-backed identity.
 *
 * Returns:
 *   user         — Supabase User object (null if not signed in)
 *   loading      — true during initial session check
 *   userId       — user.id (stable UUID, same across devices)
 *   userName     — first name from OAuth profile
 *   userEmail    — email from OAuth profile
 *   userAvatar   — profile picture URL
 *   signInWithGoogle()
 *   signInWithFacebook()
 *   signOut()
 */
export function useAuth() {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // onAuthStateChange fires with INITIAL_SESSION on mount (covers PKCE code exchange too)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null);
        setLoading(false);
      }
    );
    return () => subscription.unsubscribe();
  }, []);

  const redirectTo = typeof window !== "undefined" ? window.location.origin : undefined;

  const signInWithGoogle = () =>
    supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo },
    });

  const signInWithFacebook = () =>
    supabase.auth.signInWithOAuth({
      provider: "facebook",
      options: { redirectTo },
    });

  const signInWithGithub = () =>
    supabase.auth.signInWithOAuth({
      provider: "github",
      options: { redirectTo },
    });

  const signOut = () => supabase.auth.signOut();

  const deleteAccount = async () => {
    if (!user) return;
    const uid = user.id;
    // Delete all user data (FK cascades handle preferences + history)
    await supabase.from("user_preferences").delete().eq("user_id", uid);
    await supabase.from("user_history").delete().eq("user_id", uid);
    await supabase.from("users").delete().eq("user_id", uid);
    // Sign out — Supabase auth entry cleanup handled server-side by admin
    await supabase.auth.signOut();
  };

  // Extract first name from whichever field the provider populates
  const meta     = user?.user_metadata ?? {};
  const fullName = meta.full_name || meta.name || "";
  const firstName = fullName.split(" ")[0] || meta.email?.split("@")[0] || "there";

  return {
    user,
    loading,
    userId:     user?.id ?? null,
    userName:   firstName,
    userEmail:  user?.email ?? null,
    userAvatar: meta.avatar_url ?? meta.picture ?? null,
    signInWithGoogle,
    signInWithFacebook,
    signInWithGithub,
    signOut,
    deleteAccount,
  };
}
