import { useEffect, useRef, useState } from "react";
import SizeAdvice from "./SizeAdvice.jsx";
import { track } from "./analytics.js";
import { hdProductImageUrl, isProductPhotoUrl } from "./imageUrl.js";
import {
  matchesLookSlot,
  nextEmptySlot,
  slotProductIds,
  visibleSlots,
  VTO_SLOT_LABELS,
} from "./lookProgress.js";

const VIEW_ORDER = ["front", "look", "side", "back"];
const VIEW_LABEL = { front: "Front", look: "Full look", side: "Side", back: "Back" };

// On-demand videos: Instagram-style showcase + curated occasion reels.
const VIDEO_KINDS = [
  { key: "spin",      label: "Showcase",    emoji: "💃" },
  { key: "sangeet",   label: "Sangeet",     emoji: "🪩" },
  { key: "beach",     label: "Beach",       emoji: "🏖️" },
  { key: "date",      label: "Date night",  emoji: "🍷" },
  { key: "office",    label: "Party",       emoji: "🥂" },
  { key: "vacation",  label: "Vacation",    emoji: "✈️" },
  { key: "redcarpet", label: "Red carpet",  emoji: "✨" },
];
const VIDEO_KEYS = VIDEO_KINDS.map((k) => k.key);

const BUFFER_PHASES = [
  { after: 0,  text: "Setting the scene" },
  { after: 10, text: "Lighting the shot" },
  { after: 24, text: "Filming your look" },
  { after: 48, text: "Cutting the clip" },
  { after: 72, text: "Almost there" },
];

function bufferPhase(seconds) {
  let text = BUFFER_PHASES[0].text;
  for (const p of BUFFER_PHASES) {
    if (seconds >= p.after) text = p.text;
  }
  return text;
}

/** Crawl toward ~90% over ~80s, then hold — never complete until the clip arrives. */
function bufferPercent(ms) {
  const t = Math.max(0, ms) / 1000;
  const raw = 1 - Math.exp(-t / 28);
  return Math.min(92, 6 + raw * 86);
}

function isDailyCapMessage(msg) {
  if (!msg) return false;
  const text = String(msg).toLowerCase();
  return text.includes("try-on limit") || text.includes("today's limit") || text.includes("paused right now");
}

function VideoBuffer({ kindLabel, still, stillMime, elapsedMs }) {
  const seconds = Math.floor(elapsedMs / 1000);
  const pct = bufferPercent(elapsedMs);
  const phase = bufferPhase(seconds);
  return (
    <div className="vto-buffer" role="status" aria-live="polite" aria-busy="true">
      {still && (
        <img
          className="vto-buffer-still"
          src={`data:${stillMime || "image/png"};base64,${still}`}
          alt=""
        />
      )}
      <div className="vto-buffer-veil" aria-hidden="true" />
      <div className="vto-buffer-core">
        <div className="vto-buffer-ring" aria-hidden="true">
          <svg viewBox="0 0 72 72">
            <circle className="vto-buffer-track" cx="36" cy="36" r="30" />
            <circle className="vto-buffer-arc" cx="36" cy="36" r="30" />
          </svg>
          <span className="vto-buffer-spark">✦</span>
        </div>
        <p className="vto-buffer-phase">{phase}</p>
        <p className="vto-buffer-sub">
          {kindLabel} · about a minute
          {seconds > 4 ? ` · ${seconds}s` : ""}
        </p>
        <div className="vto-buffer-bar" aria-hidden="true">
          <i style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}

// base64 → Blob
function b64toBlob(b64, mime = "application/octet-stream") {
  const bytes = atob(b64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  return new Blob([arr], { type: mime });
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

// Compose a branded 9:16 share card (1080×1920) from a try-on image.
async function composeShareCard(imgBase64, imgMime, product) {
  const W = 1080, H = 1920;
  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d");

  // Soft brand gradient backdrop
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, "#fbeef0"); g.addColorStop(1, "#efe7f6");
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

  // Draw the try-on image "contain" into the top region, centered
  const img = new Image();
  img.src = `data:${imgMime};base64,${imgBase64}`;
  try { await img.decode(); } catch { /* fall through */ }
  const areaTop = 60, areaH = 1440, areaW = W - 120, areaX = 60;
  const scale = Math.min(areaW / img.width, areaH / img.height);
  const dw = img.width * scale, dh = img.height * scale;
  const dx = (W - dw) / 2, dy = areaTop + (areaH - dh) / 2;
  ctx.save();
  ctx.shadowColor = "rgba(60,30,40,.18)"; ctx.shadowBlur = 40; ctx.shadowOffsetY = 16;
  ctx.drawImage(img, dx, dy, dw, dh);
  ctx.restore();

  // Bottom text block
  ctx.textAlign = "center";
  ctx.fillStyle = "#1a1410";
  ctx.font = "700 46px Georgia, serif";
  const name = (product.name || "").slice(0, 60);
  // simple 1-2 line wrap
  const words = name.split(" "); let line = "", lines = [];
  for (const w of words) {
    if ((line + " " + w).trim().length > 26) { lines.push(line.trim()); line = w; }
    else line += " " + w;
    if (lines.length === 2) break;
  }
  if (line && lines.length < 2) lines.push(line.trim());
  lines.forEach((ln, i) => ctx.fillText(ln, W / 2, 1580 + i * 56));

  if (product.price != null) {
    const cur = product.currency === "USD" ? "$" : "₹";
    ctx.font = "700 44px Georgia, serif"; ctx.fillStyle = "#c0103a";
    ctx.fillText(`${cur}${Number(product.price).toLocaleString("en-IN")}`, W / 2, 1580 + lines.length * 56 + 20);
  }

  ctx.font = "800 34px Georgia, serif"; ctx.fillStyle = "#7c3aed";
  ctx.fillText("✦ Styled by Mira", W / 2, 1840);

  return await new Promise((res) => canvas.toBlob((b) => res(b), "image/png", 0.92));
}

/* ── Minimal body-outline SVG silhouette ── */
function SilhouetteSVG() {
  return (
    <svg
      className="tryon-silhouette"
      viewBox="0 0 120 280"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Head */}
      <ellipse cx="60" cy="28" rx="18" ry="22" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      {/* Neck */}
      <path d="M52 49 Q60 56 68 49" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      {/* Shoulders */}
      <path d="M52 49 C38 54 24 64 18 80 L22 82 C28 68 40 60 52 56 Z" fill="currentColor" opacity=".15" />
      <path d="M68 49 C82 54 96 64 102 80 L98 82 C92 68 80 60 68 56 Z" fill="currentColor" opacity=".15" />
      {/* Torso outline */}
      <path
        d="M52 56 C40 60 28 70 26 90 L28 130 C30 140 32 144 60 144 C88 144 90 140 92 130 L94 90 C92 70 80 60 68 56 Q60 60 52 56 Z"
        stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round"
        fill="currentColor" opacity=".06"
      />
      {/* Arms */}
      <path d="M28 80 C18 95 14 115 16 140 L24 138 C22 115 26 96 34 82 Z" fill="currentColor" opacity=".12" />
      <path d="M92 80 C102 95 106 115 104 140 L96 138 C98 115 94 96 86 82 Z" fill="currentColor" opacity=".12" />
      {/* Waist pinch */}
      <path d="M28 128 Q60 136 92 128" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".4" />
      {/* Hips */}
      <path
        d="M28 130 C22 148 20 162 26 178 L94 178 C100 162 98 148 92 130"
        stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round"
        fill="currentColor" opacity=".08"
      />
      {/* Legs */}
      <path d="M26 178 C22 210 24 240 28 268 L46 268 C44 240 42 210 46 178 Z" fill="currentColor" opacity=".1" />
      <path d="M74 178 C78 210 76 240 72 268 L90 268 C96 240 98 210 94 178 Z" fill="currentColor" opacity=".1" />
      {/* Dashed vertical centre line */}
      <line x1="60" y1="56" x2="60" y2="275" stroke="currentColor" strokeWidth="1" strokeDasharray="4 5" opacity=".2" />
      {/* Sparkle dots — hint of magic */}
      <circle cx="15" cy="55" r="2.5" fill="currentColor" opacity=".35" />
      <circle cx="105" cy="90" r="2" fill="currentColor" opacity=".28" />
      <circle cx="20" cy="170" r="1.8" fill="currentColor" opacity=".22" />
    </svg>
  );
}

function slotThumb(product) {
  if (!product) return null;
  return isProductPhotoUrl(product.image_url)
    ? hdProductImageUrl(product.image_url, { longest: 240 })
    : product.image_url;
}

function lookHint(slots, remaining) {
  const next = slots.find((s) => !s.product && remaining.some((item) => matchesLookSlot(item, s.key)))
    || slots.find((s) => !s.product);
  if (!next) return "Look’s set — tap a slot to open it.";
  const noun = next.label.toLowerCase();
  const article = /^[aeiou]/.test(noun) ? "an" : "a";
  return `♥ ${article} ${noun} to pin it on your look — then keep going.`;
}

function LookSlotRail({ lookProgress, focusSlot, onFocusSlot, onOpen, onUnpin }) {
  const slots = visibleSlots(lookProgress, VTO_SLOT_LABELS);
  if (!slots.length) return null;
  return (
    <div className="tryon-slots" role="list" aria-label="Your look">
      {slots.map((s) => {
        const p = s.product;
        const img = slotThumb(p);
        return (
          <div key={s.key} className="tryon-slot-wrap" role="listitem">
            <button
              type="button"
              className={`tryon-slot${p ? " is-filled" : ""}${focusSlot === s.key && !p ? " is-focus" : ""}`}
              onClick={() => {
                if (p) onOpen?.(p);
                else onFocusSlot?.(s.key);
              }}
              title={p ? p.name : `Add ${s.label}`}
              aria-label={p ? `${s.label}: ${p.name}` : `Empty ${s.label} slot`}
            >
              {p && img ? (
                <img className="tryon-slot-thumb" src={img} alt="" />
              ) : (
                <span className="tryon-slot-empty" aria-hidden="true" />
              )}
              <span className="tryon-slot-label">{p ? "✓ " : ""}{s.label}</span>
            </button>
            {p && onUnpin && (
              <button
                type="button"
                className="tryon-slot-clear"
                aria-label={`Remove ${s.label} from look`}
                title="Unpin"
                onClick={() => onUnpin(p)}
              >
                ×
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function TryOnModal({ product, onClose, onTryOn, result, loading, error,
                                     onVideo, video, videoLoadingKind, videoError,
                                     savedPhoto, onSavePhoto, onClearPhoto,
                                     savedTryOn, savedStale, userPrefs, onSetSize,
                                     onCompleteLook, lookItems, onShopLookItem, onTryLookItem, onOpenLookItem,
                                     lookProgress, loved, onLikeLookItem, onUnpinLookItem }) {
  const overlayRef = useRef(null);
  const fileRef = useRef(null);
  const [userPhoto, setUserPhoto] = useState(null); // data URL preview of uploaded photo
  const [selectedView, setSelectedView] = useState("front");
  const [zoom, setZoom] = useState(false); // fullscreen magnified result
  const [showAngles, setShowAngles] = useState(false);
  const [showVideos, setShowVideos] = useState(false);
  const [focusSlot, setFocusSlot] = useState(null);

  /* Close on Escape key */
  useEffect(() => {
    function onKey(e) {
      if (e.key !== "Escape") return;
      if (zoom) setZoom(false);   // close the enlarged view first
      else onClose();
    }
    document.addEventListener("keydown", onKey);
    /* Prevent body scroll while modal open */
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose, zoom]);

  /* Close on backdrop click */
  function handleOverlayClick(e) {
    if (e.target === overlayRef.current) onClose();
  }

  const emoji = {
    dresses: "👗", tops: "👚", bottoms: "👖", outerwear: "🧥",
    shoes: "👟", bags: "👜", accessories: "✨", activewear: "🏃",
  }[product.category] || "🛍️";

  const hasPhoto =
    product.image_url &&
    (product.image_url.includes("m.media-amazon.com") ||
      product.image_url.includes("images.pexels.com"));

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      setUserPhoto(dataUrl);
      const base64 = String(dataUrl).split(",")[1];
      const mime = file.type || "image/jpeg";
      track("try_on_photo_uploaded", { product_id: product.id, source: "upload" });
      onSavePhoto?.(base64, mime);   // remember for next time (client-side only)
      onTryOn?.(product.id, base64, mime);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  // One-tap "try it on me" using the previously saved photo — no re-upload.
  const tryWithSaved = () => {
    if (!savedPhoto?.image) return;
    track("try_on_photo_uploaded", { product_id: product.id, source: "saved" });
    setUserPhoto(`data:${savedPhoto.mime};base64,${savedPhoto.image}`);
    onTryOn?.(product.id, savedPhoto.image, savedPhoto.mime || "image/jpeg");
  };

  // Live result for THIS product, plus the saved (Fitting Room) fallback so a
  // previously-tried product shows instantly with no regeneration.
  const myResult = result && result.productId === product.id ? result : null;
  const saved = savedTryOn && savedTryOn.productId === product.id ? savedTryOn : null;
  const liveViews = myResult?.views || {};
  // Merge saved + live (live overlays saved) so a saved angle always shows, even
  // if a late in-flight message would otherwise leave it looking "pending".
  const views = { ...(saved?.views || {}), ...liveViews };
  const failed = myResult?.failed || {};
  const total = Math.max(myResult?.total || 0, Object.keys(views).length) || 0;
  // Which angle buttons to show: the expected set (front/side/back), capped to total.
  const angleKeys = VIEW_ORDER.filter((v) => views[v] || failed[v]);
  const selected = views[selectedView];
  const selectedPending = myResult && !selected && !failed[selectedView];
  const selectedFailed = myResult && !selected && failed[selectedView];
  const anyDone = Object.keys(views).length > 0;
  const lookSlots = visibleSlots(lookProgress, VTO_SLOT_LABELS);
  const pinnedLookIds = slotProductIds(lookProgress);
  const remainingLookItems = (lookItems || []).filter((item) => item?.id && !pinnedLookIds.has(item.id));
  const shownLookItems = focusSlot
    ? [...remainingLookItems].sort((a, b) => {
        const am = matchesLookSlot(a, focusSlot) ? 0 : 1;
        const bm = matchesLookSlot(b, focusSlot) ? 0 : 1;
        return am - bm;
      })
    : remainingLookItems;
  const nextLookSlot = nextEmptySlot(lookProgress, VTO_SLOT_LABELS);

  // ── Videos (Veo): fashion-reel showcase + occasion clips ──
  const myVideo = video && video.productId === product.id ? video : null;
  const clips = { ...(saved?.clips || {}), ...(myVideo?.clips || {}) };
  const stills = { ...(saved?.stills || {}), ...(myVideo?.stills || {}) };
  const isVideoView = VIDEO_KEYS.includes(selectedView);
  const front = views.front;
  const [hd, setHd] = useState(false);
  const [bufferMs, setBufferMs] = useState(0);

  /* Reset progressive UI whenever a new product's try-on begins */
  useEffect(() => {
    setSelectedView("front");
    setShowAngles(false);
    setShowVideos(false);
    setHd(false);
    setFocusSlot(null);
  }, [product.id]);

  /* Reveal angle tabs once the full-look still lands. */
  useEffect(() => {
    if (views.look) setShowAngles(true);
  }, [views.look]);

  /* Keep the buffer clock running until THIS clip arrives or errors out. */
  useEffect(() => {
    if (!videoLoadingKind) {
      setBufferMs(0);
      return;
    }
    const t0 = Date.now();
    setBufferMs(0);
    const id = setInterval(() => setBufferMs(Date.now() - t0), 250);
    return () => clearInterval(id);
  }, [videoLoadingKind]);

  const handleVideo = (kind) => {
    setSelectedView(kind);
    if (isDailyCapMessage(videoError)) return;
    // Generate the first time, or re-render when the requested quality (HD/Lite)
    // differs from what we already have cached for this scene.
    const existing = clips[kind];
    const needsRender = !existing || !!existing.hd !== hd;
    if (needsRender && videoLoadingKind !== kind && front && onVideo) {
      onVideo(product.id, front.image, front.mime || "image/png", kind, hd);
    }
  };

  const [sharing, setSharing] = useState(false);
  const handleShare = async () => {
    if (sharing) return;
    setSharing(true);
    track("try_on_shared", { product_id: product.id, kind: selectedView });
    const caption = `Styled by Mira ✦ — ${product.name || "my look"}`;
    try {
      // If a video clip is showing, share the clip itself.
      const clip = clips[selectedView];
      if (clip) {
        const blob = b64toBlob(clip.video, clip.mime || "video/mp4");
        const file = new File([blob], "mira-tryon.mp4", { type: blob.type });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], title: "My Mira try-on", text: caption });
        } else { triggerDownload(blob, "mira-tryon.mp4"); }
        return;
      }
      // Otherwise compose a branded card from the best available still image.
      const src = selected?.image || stills[selectedView]?.image || front?.image;
      const srcMime = selected?.mime || stills[selectedView]?.mime || front?.mime || "image/png";
      if (!src) return;
      const blob = await composeShareCard(src, srcMime, product);
      const file = new File([blob], "mira-look.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: "My Mira look", text: caption });
      } else { triggerDownload(blob, "mira-look.png"); }
    } catch { /* user cancelled share or unsupported — no-op */ }
    finally { setSharing(false); }
  };
  const canShare = anyDone; // share available once we have at least the front image

  return (
    <div
      className="tryon-overlay"
      ref={overlayRef}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Virtual try-on"
    >
      <div className={`tryon-modal${anyDone ? " has-result" : ""}`}>
        {/* Close */}
        <button className="tryon-close" onClick={onClose} aria-label="Close">
          ✕
        </button>

        {/* Header */}
        <div className="tryon-header">
          <span className="tryon-badge">✨ AI</span>
          <h2 className="tryon-title">Virtual Try-On</h2>
          <p className="tryon-subtitle">
            See how the {product.name?.split(" ").slice(0, 4).join(" ")} looks on you.
          </p>
          <p className="tryon-preview-note">✨ AI style preview — shows the look, not exact fit</p>
        </div>

        {anyDone && isVideoView ? (
          /* ── Video view (spin or scene) ── */
          <div className="tryon-result-stage">
            {clips[selectedView] ? (
              <video
                className="tryon-result-full"
                src={`data:${clips[selectedView].mime};base64,${clips[selectedView].video}`}
                autoPlay loop muted playsInline controls
              />
            ) : videoLoadingKind === selectedView ? (
              <VideoBuffer
                kindLabel={VIDEO_KINDS.find((k) => k.key === selectedView)?.label || "Video"}
                still={stills[selectedView]?.image}
                stillMime={stills[selectedView]?.mime}
                elapsedMs={bufferMs}
              />
            ) : stills[selectedView] ? (
              <div className="tryon-scene-still-wrap">
                <img
                  className="tryon-result-full"
                  src={`data:${stills[selectedView].mime};base64,${stills[selectedView].image}`}
                  alt="Scene preview"
                />
                {videoError ? (
                  <span className="tryon-zoom-hint tryon-zoom-hint--error">{videoError}</span>
                ) : null}
              </div>
            ) : videoError ? (
              <div className="tryon-result-placeholder">
                <span className="tryon-product-emoji">🎬</span>
                <p style={{ color: "#c0103a" }}>{videoError}</p>
              </div>
            ) : (
              <div className="tryon-result-placeholder">
                <span className="tryon-angle-dot big" aria-hidden="true" />
                <p>Tap a scene to film it.</p>
              </div>
            )}
          </div>
        ) : anyDone ? (
          /* ── Large result view — full magnified image of you in the item ── */
          <div className="tryon-result-stage">
            {selected ? (
              <button
                className="tryon-result-full-btn"
                onClick={() => setZoom(true)}
                title="Click to enlarge"
                aria-label="Enlarge try-on image"
              >
                <img
                  className="tryon-result-full"
                  src={`data:${selected.mime};base64,${selected.image}`}
                  alt={`Virtual try-on — ${VIEW_LABEL[selectedView] || selectedView}`}
                />
                <span className="tryon-zoom-hint">⤢ Tap to enlarge</span>
              </button>
            ) : selectedPending ? (
              <div className="tryon-result-placeholder">
                <span className="tryon-angle-dot big" aria-hidden="true" />
                <p>Generating the {(VIEW_LABEL[selectedView] || selectedView).toLowerCase()} view…</p>
              </div>
            ) : (
              <div className="tryon-result-placeholder">
                <span className="tryon-product-emoji">🙈</span>
                <p>Couldn't generate this angle — try another.</p>
              </div>
            )}
          </div>
        ) : (
          /* ── Pre-upload / loading — item + silhouette ── */
          <div className="tryon-stage">
            <div className="tryon-product-preview">
              {hasPhoto ? (
                <img className="tryon-product-img" src={product.image_url} alt={product.name} loading="lazy" />
              ) : (
                <div className="tryon-product-emoji-wrap">
                  <span className="tryon-product-emoji">{emoji}</span>
                </div>
              )}
              <span className="tryon-product-label">Item</span>
            </div>

            <div className="tryon-connector" aria-hidden="true">
              <svg viewBox="0 0 48 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M2 12 H44 M36 4 L44 12 L36 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>+</span>
              <svg viewBox="0 0 48 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M2 12 H44 M36 4 L44 12 L36 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>

            <div className="tryon-silhouette-wrap">
              {loading ? (
                <>
                  <SilhouetteSVG />
                  <div className="tryon-shimmer-bar" aria-hidden="true" />
                </>
              ) : userPhoto ? (
                <img className="tryon-product-img" src={userPhoto} alt="Your photo" />
              ) : (
                <SilhouetteSVG />
              )}
              <span className="tryon-product-label">You</span>
            </div>
          </div>
        )}

        {/* Angles — progressive disclosure after the first still is ready */}
        {anyDone && angleKeys.length > 1 && !showAngles && (
          <div className="tryon-scenes-wrap" style={{ paddingTop: ".25rem" }}>
            <button
              type="button"
              className="tryon-share-btn"
              style={{ width: "100%" }}
              onClick={() => setShowAngles(true)}
            >
              View angles ({angleKeys.length})
            </button>
          </div>
        )}
        {anyDone && showAngles && (
          <div className="tryon-angles" role="tablist" aria-label="View angles">
            {angleKeys.map((v) => {
              const ready = !!views[v];
              const isFailed = !!failed[v];
              return (
                <button
                  key={v}
                  role="tab"
                  aria-selected={selectedView === v}
                  className={`tryon-angle${selectedView === v ? " active" : ""}${ready ? "" : " pending"}${isFailed ? " failed" : ""}`}
                  disabled={!ready}
                  onClick={() => ready && setSelectedView(v)}
                  title={isFailed ? "Couldn't generate this angle" : VIEW_LABEL[v]}
                >
                  {VIEW_LABEL[v] || v}
                  {!ready && !isFailed && <span className="tryon-angle-dot" aria-hidden="true" />}
                  {isFailed && " ✕"}
                </button>
              );
            })}
          </div>
        )}

        {anyDone && (
          <div className="tryon-look-wrap">
            <p className="tryon-look-label">Your look</p>
            <LookSlotRail
              lookProgress={lookProgress}
              focusSlot={focusSlot}
              onFocusSlot={setFocusSlot}
              onOpen={onOpenLookItem}
              onUnpin={onUnpinLookItem}
            />
            {shownLookItems.length === 0 ? (
              nextLookSlot ? (
                <p className="tryon-look-sub">Mira’s still pulling pieces for the empty slots.</p>
              ) : null
            ) : (
              <>
                <p className="tryon-look-sub">{lookHint(lookSlots, shownLookItems)}</p>
                <div className="tryon-look-rail">
                  {shownLookItems.map((item) => {
                    const cur = item.currency === "USD" ? "$" : "₹";
                    const slot = String(item.category || "piece");
                    const isLoved = !!(loved && loved.has(item.id));
                    const isFocus = !!(focusSlot && matchesLookSlot(item, focusSlot));
                    return (
                      <article
                        key={item.id}
                        className={`tryon-look-card${isFocus ? " is-focus" : ""}`}
                      >
                        {onLikeLookItem && (
                          <button
                            type="button"
                            className={`tryon-look-love${isLoved ? " is-loved" : ""}`}
                            aria-label={isLoved ? `Pinned ${item.name}` : `Like and pin ${item.name}`}
                            title="Like — pin on your look"
                            onClick={() => {
                              onLikeLookItem(item);
                              setFocusSlot(null);
                            }}
                          >
                            {isLoved ? "♥" : "♡"}
                          </button>
                        )}
                        <button
                          type="button"
                          className="tryon-look-open"
                          onClick={() => onOpenLookItem?.(item)}
                          aria-label={`Open ${item.name} on Mira`}
                        >
                          {item.image_url
                            ? <img className="tryon-look-img" src={item.image_url} alt="" />
                            : <div className="tryon-look-img tryon-look-img--ph">🛍️</div>}
                          <span className="tryon-look-slot">{slot}</span>
                          <p className="tryon-look-name">{item.name}</p>
                          <p className="tryon-look-price">
                            {item.price != null ? `${cur}${Number(item.price).toLocaleString("en-IN")}` : ""}
                          </p>
                        </button>
                        <div className="tryon-look-actions">
                          {onTryLookItem && (
                            <button type="button" className="tryon-look-btn" onClick={() => onTryLookItem(item)}>
                              Try on
                            </button>
                          )}
                          {onShopLookItem && (
                            <button type="button" className="tryon-look-btn primary" onClick={() => onShopLookItem(item)}>
                              Add
                            </button>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}

        {/* Video — opt-in; Lite quality by default */}
        {anyDone && !showVideos && (
          <div className="tryon-scenes-wrap">
            <button
              type="button"
              className="tryon-notify-btn"
              style={{ width: "100%" }}
              disabled={!front}
              onClick={() => setShowVideos(true)}
            >
              Create a video (Lite · ~1 min)
            </button>
            <p className="tryon-preview-note" style={{ marginTop: ".4rem" }}>
              Optional · uses generation credits · HD available inside
            </p>
          </div>
        )}
        {anyDone && showVideos && (
          <div className="tryon-scenes-wrap">
            <div className="tryon-scenes-head">
              <p className="tryon-scenes-label">Create a video</p>
              <button
                type="button"
                className={`tryon-hd-toggle${hd ? " on" : ""}`}
                role="switch"
                aria-checked={hd}
                onClick={() => {
                  const next = !hd;
                  setHd(next);
                  const cur = clips[selectedView];
                  if (!isDailyCapMessage(videoError) &&
                      VIDEO_KEYS.includes(selectedView) && front && onVideo &&
                      videoLoadingKind !== selectedView && (!cur || !!cur.hd !== next)) {
                    onVideo(product.id, front.image, front.mime || "image/png", selectedView, next);
                  }
                }}
                title="HD is sharper but slower and costs more"
              >
                HD {hd ? "on" : "off"}
              </button>
            </div>
            <div className="tryon-scenes" role="tablist" aria-label="Videos and scenes">
              {VIDEO_KINDS.map(({ key, label, emoji }) => {
                const ready = !!clips[key];
                const busy = videoLoadingKind === key;
                return (
                  <button
                    key={key}
                    role="tab"
                    aria-selected={selectedView === key}
                    className={`tryon-angle tryon-scene${selectedView === key ? " active" : ""}${ready ? " ready" : ""}`}
                    disabled={!front}
                    onClick={() => handleVideo(key)}
                    title={`${label} fashion reel (~1 min)`}
                  >
                    <span aria-hidden="true">{emoji}</span> {label}
                    {busy && <span className="tryon-angle-dot" aria-hidden="true" />}
                    {ready && !busy && <span className="tryon-scene-check" aria-hidden="true">▸</span>}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* CTA copy + upload */}
        <div className="tryon-cta-area">
          {loading ? (
            <p className="tryon-magic-text">Styling it on you… this takes a few seconds 🪄</p>
          ) : anyDone ? (
            videoLoadingKind === selectedView && isVideoView ? (
              <p className="tryon-magic-text">Stay with Mira — this clip keeps filming until it’s ready</p>
            ) : videoError && isVideoView && videoLoadingKind !== selectedView ? (
              <p className="tryon-desc" style={{ color: "#c0103a" }}>
                {videoError}
                {isDailyCapMessage(videoError) ? null : (
                  <>
                    {" "}
                    <button type="button" className="tryon-stale-link" onClick={() => handleVideo(selectedView)}>
                      Try again
                    </button>
                  </>
                )}
              </p>
            ) : angleKeys.every((v) => views[v] || failed[v]) ? (
              <p className="tryon-magic-text">That's the upgrade — you look amazing in this ✨</p>
            ) : (
              <p className="tryon-magic-text">Front's ready — spinning up the other angles… ✨</p>
            )
          ) : error ? (
            <p className="tryon-desc" style={{ color: "#c0103a" }}>{error}</p>
          ) : savedPhoto?.image && !userPhoto ? (
            <p className="tryon-desc">
              See it on you in one tap — or upload a new photo. Your photo stays on your device.
            </p>
          ) : (
            <p className="tryon-desc">
              Upload a clear, front-facing full-body photo and Mira will show this
              piece styled on you. Your photo stays on your device — never uploaded to our servers.
            </p>
          )}

          {anyDone && savedStale && (
            <p className="tryon-stale-nudge">
              Made with your old photo — <button className="tryon-stale-link" onClick={() => fileRef.current?.click()}>refresh with your current one?</button>
            </p>
          )}

          <SizeAdvice product={product} prefs={userPrefs} onSetSize={onSetSize} />

          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={handleFile}
          />
          <div className="tryon-actions">
            {/* One-tap try-on with the saved photo (pre-upload only) */}
            {!loading && !anyDone && savedPhoto?.image && !userPhoto && (
              <button className="tryon-notify-btn" type="button" onClick={tryWithSaved}>
                ✨ Try it on me
              </button>
            )}
            {!loading && (
              <button
                className={(!anyDone && savedPhoto?.image && !userPhoto) ? "tryon-share-btn" : "tryon-notify-btn"}
                type="button"
                onClick={() => fileRef.current?.click()}
              >
                {anyDone || error || userPhoto
                  ? "Try another photo"
                  : (savedPhoto?.image ? "Upload a different photo" : "Upload your photo")} 📷
              </button>
            )}
            {canShare && (
              <button className="tryon-share-btn" type="button" onClick={handleShare} disabled={sharing}>
                {sharing ? "Preparing…" : "Share ✦"}
              </button>
            )}
            {anyDone && onCompleteLook && (
              <button
                className="tryon-share-btn"
                type="button"
                onClick={() => { onCompleteLook(product); onClose?.(); }}
              >
                Complete the look
              </button>
            )}
            {savedPhoto?.image && !anyDone && !loading && (
              <button className="tryon-skip-btn" type="button" onClick={onClearPhoto}>
                Forget my photo
              </button>
            )}
            <button className="tryon-skip-btn" type="button" onClick={onClose}>
              {anyDone ? "Done" : "Maybe later"}
            </button>
          </div>
        </div>
      </div>

      {/* Fullscreen magnified view */}
      {zoom && selected && (
        <div className="tryon-zoom" onClick={() => setZoom(false)} role="dialog" aria-label="Enlarged try-on">
          <img
            className="tryon-zoom-img"
            src={`data:${selected.mime};base64,${selected.image}`}
            alt={`Virtual try-on — ${VIEW_LABEL[selectedView] || selectedView}`}
          />
          <button className="tryon-zoom-close" onClick={() => setZoom(false)} aria-label="Close enlarged view">✕</button>
        </div>
      )}
    </div>
  );
}
