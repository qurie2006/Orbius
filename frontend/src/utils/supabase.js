import { createClient } from "@supabase/supabase-js";

export const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || "";
export const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

export const isSupabaseConfigured = Boolean(
  supabaseUrl && 
  supabaseAnonKey && 
  supabaseUrl.startsWith("http") &&
  supabaseAnonKey.length > 10
);

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

export async function checkSupabaseGoogleEnabled() {
  if (!isSupabaseConfigured) return false;
  try {
    const res = await fetch(`${supabaseUrl}/auth/v1/authorize?provider=google`, {
      method: "GET",
      headers: { apikey: supabaseAnonKey },
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      if (data?.error_code === "validation_failed" || data?.msg?.includes("Unsupported provider") || data?.msg?.includes("not enabled")) {
        return false;
      }
    }
    return true;
  } catch {
    return false;
  }
}
