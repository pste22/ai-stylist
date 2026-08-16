import { useEffect, useState } from "react";
import { supabase } from "./supabaseClient.js";

function describeAuthError(error, provider) {
  const name = provider.charAt(0).toUpperCase() + provider.slice(1);
  if (/provider is not enabled/i.test(error?.message || "")) {
    return `${name} sign-in isn't switched on yet. Try another option.`;
  }
  return error?.message || `Couldn't start ${name} sign-in. Please try again.`;
}

/** Errors come back from the provider in the URL fragment, e.g. #error=access_denied. */
function readRedirectError() {
  if (typeof window === "undefined") return null;
  const hash = window.location.hash;
  if (!hash.includes("error")) return null;
  const params = new URLSearchParams(hash.slice(1));
  const code = params.get("error");
  if (!code) return null;
  // Don't leave the error in the address bar — a refresh would resurface it.
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  if (code === "access_denied") return "Sign-in was cancelled.";
  return params.get("error_description")?.replace(/\+/g, " ") || "Sign-in failed. Please try again.";
}

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
 *   authError    — message to show when sign-in fails, null otherwise
 *   signInWithGoogle()
 *   signInWithFacebook()
 *   signOut()
 */
export function useAuth() {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

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

  useEffect(() => {
    const message = readRedirectError();
    if (message) setAuthError(message);
  }, []);

  // Must end in a path, not a bare origin: Supabase's "https://host/**" allowlist
  // entries don't match "https://host". A rejected redirect_to is not an error —
  // GoTrue silently sends the user to the project's Site URL instead, so sign-in
  // appears to do nothing on whatever host you're actually developing on.
  const redirectTo =
    typeof window !== "undefined"
      ? window.location.origin + (window.location.pathname || "/")
      : undefined;

  // signInWithOAuth reports failures in the returned value instead of throwing,
  // so an ignored promise turns a real error into a button that does nothing.
  const signInWith = async (provider) => {
    setAuthError(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo },
    });
    if (error) setAuthError(describeAuthError(error, provider));
  };

  const signInWithGoogle   = () => signInWith("google");
  const signInWithFacebook = () => signInWith("facebook");
  const signInWithGithub   = () => signInWith("github");

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
    authError,
    clearAuthError: () => setAuthError(null),
    signInWithGoogle,
    signInWithFacebook,
    signInWithGithub,
    signOut,
    deleteAccount,
  };
}
