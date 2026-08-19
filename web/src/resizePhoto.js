/** Downscale a try-on photo so Gemini's 7MB-per-image cap isn't blown by a phone camera. */

const MAX_SIDE = 1280;
const JPEG_QUALITY = 0.82;
const SKIP_UNDER_BYTES = 1_200_000; // already small enough for Gemini
const RESIZE_MS = 2500;

function withTimeout(promise, ms, label = "timed out") {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(label)), ms);
    promise.then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); reject(e); },
    );
  });
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Could not read photo"));
    img.src = src;
  });
}

function canvasJpeg(img) {
  let w = img.naturalWidth || img.width || 0;
  let h = img.naturalHeight || img.height || 0;
  if (!w || !h) throw new Error("Could not read photo");
  const scale = Math.min(1, MAX_SIDE / Math.max(w, h));
  w = Math.max(1, Math.round(w * scale));
  h = Math.max(1, Math.round(h * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, w, h);
  const dataUrl = canvas.toDataURL("image/jpeg", JPEG_QUALITY);
  const base64 = dataUrl.split(",")[1] || "";
  if (!base64) throw new Error("Could not read photo");
  return { dataUrl, base64, mime: "image/jpeg" };
}

function skipResize(source, mimeHint) {
  const mime = (mimeHint || "image/jpeg").split(";")[0].trim().toLowerCase();
  const jpeg = mime === "image/jpeg" || mime === "image/jpg";
  if (!jpeg) return null;
  if (typeof Blob !== "undefined" && source instanceof Blob) {
    if (source.size > 0 && source.size <= SKIP_UNDER_BYTES) return "blob-small";
  }
  if (typeof source === "string" && !source.startsWith("data:")) {
    // raw base64; 1.6M chars ≈ 1.2MB binary
    if (source.length > 0 && source.length <= 1_600_000) {
      return { dataUrl: `data:${mime};base64,${source}`, base64: source, mime: "image/jpeg" };
    }
  }
  return null;
}

/**
 * @param {File | Blob | string} source  File, data URL, or raw base64
 * @param {string} [mimeHint]
 * @returns {Promise<{ dataUrl: string, base64: string, mime: string }>}
 */
export async function resizePhotoForTryOn(source, mimeHint = "image/jpeg") {
  const skipped = skipResize(source, mimeHint);
  if (skipped && skipped !== "blob-small") return skipped;

  let objectUrl = null;
  try {
    let src;
    if (skipped === "blob-small" && typeof FileReader !== "undefined") {
      const dataUrl = await withTimeout(new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(new Error("Could not read photo"));
        reader.readAsDataURL(source);
      }), RESIZE_MS);
      const base64 = dataUrl.split(",")[1] || "";
      return { dataUrl, base64, mime: "image/jpeg" };
    }
    if (typeof Blob !== "undefined" && source instanceof Blob) {
      objectUrl = URL.createObjectURL(source);
      src = objectUrl;
    } else if (typeof source === "string" && source.startsWith("data:")) {
      src = source;
    } else if (typeof source === "string") {
      src = `data:${mimeHint || "image/jpeg"};base64,${source}`;
    } else {
      throw new Error("Could not read photo");
    }
    const img = await withTimeout(loadImage(src), RESIZE_MS);
    return canvasJpeg(img);
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}
