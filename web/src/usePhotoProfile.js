import { useCallback, useState } from "react";

// The user's try-on photo, kept CLIENT-SIDE only (localStorage) so it never
// touches our servers — "upload once, try on everything". { image: base64, mime }.
const KEY = "mira_tryon_photo";

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function usePhotoProfile() {
  const [photo, setPhoto] = useState(load);

  const savePhoto = useCallback((image, mime = "image/jpeg") => {
    if (!image) return;
    const next = { image, mime };
    setPhoto(next);
    try { localStorage.setItem(KEY, JSON.stringify(next)); }
    catch { /* quota exceeded — keep it in memory for this session only */ }
  }, []);

  const clearPhoto = useCallback(() => {
    setPhoto(null);
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
  }, []);

  return { photo, savePhoto, clearPhoto };
}
