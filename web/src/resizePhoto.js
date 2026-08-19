/** Downscale a try-on photo so Gemini's 7MB-per-image cap isn't blown by a phone camera. */

const MAX_SIDE = 1280;
const JPEG_QUALITY = 0.82;

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

/**
 * @param {File | Blob | string} source  File, data URL, or raw base64
 * @param {string} [mimeHint]
 * @returns {Promise<{ dataUrl: string, base64: string, mime: string }>}
 */
export async function resizePhotoForTryOn(source, mimeHint = "image/jpeg") {
  let objectUrl = null;
  try {
    let src;
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
    const img = await loadImage(src);
    return canvasJpeg(img);
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}
