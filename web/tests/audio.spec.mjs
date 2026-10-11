/**
 * Mira voice playback: 24kHz PCM must come out of the speakers, and barge-in
 * must clear the queue without killing the unlocked audio context.
 *
 *   npm run test:audio
 *   BASE=https://127.0.0.1:5173 npm run test:audio
 */
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { resampleLinear } from "../src/audio.js";

const BASE = process.env.BASE || "https://127.0.0.1:5173";

function tone(seconds) {
  const n = Math.floor(24000 * seconds);
  const pcm = new Float32Array(n);
  for (let i = 0; i < n; i++) pcm[i] = Math.sin((2 * Math.PI * 440 * i) / 24000);
  return pcm;
}

const up = resampleLinear(tone(1), 24000, 48000);
assert.equal(up.length, 48000, "24k → 48k should be one second at the device rate");
assert.ok(Math.abs(up[0]) < 1e-6);
const down = resampleLinear(up, 48000, 16000);
assert.equal(down.length, 16000, "mic downsample should land on 16kHz");
assert.equal(resampleLinear(tone(0.1), 24000, 24000).length, 2400);
console.log("resample: 24k→48k and 48k→16k lengths ok");

const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: [
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
  ],
});
const ctx = await browser.newContext({
  ignoreHTTPSErrors: true,
  permissions: ["microphone"],
});
const page = await ctx.newPage();
page.on("pageerror", (err) => console.log("pageerror:", err.message));
await page.goto(BASE, { waitUntil: "domcontentloaded" });
await page.evaluate(async () => {
  window.__audio = await import("/src/audio.js");
});

await page.evaluate(() => {
  const btn = document.createElement("button");
  btn.id = "audio-go";
  btn.textContent = "go";
  btn.onclick = () => {
    const player = new window.__audio.PcmPlayer();
    player.unlock();
    window.__player = player;
  };
  document.body.appendChild(btn);
});
await page.click("#audio-go");

const playback = await page.evaluate(async () => {
  const player = window.__player;
  const idle = {
    state: player.ctx?.state || "none",
    active: player.isOutputActive(),
    rate: player.ctx?.sampleRate || 0,
  };
  const n = 24000;
  const pcm = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    pcm[i] = Math.round(Math.sin((2 * Math.PI * 440 * i) / 24000) * 0x7fff);
  }
  player.push(pcm.buffer);
  const queued = player.queuedSeconds();
  const active = player.isOutputActive();
  await new Promise((r) => setTimeout(r, 250));
  const level = player.getLevel();
  let oddThrew = false;
  try { player.push(new Uint8Array([1, 2, 3]).buffer); }
  catch { oddThrew = true; }
  player.flush();
  const flushed = {
    active: player.isOutputActive(),
    state: player.ctx?.state || "closed",
    queued: player.queuedSeconds(),
  };
  player.push(pcm.buffer);
  const resumed = player.queuedSeconds();
  player.close();
  return { idle, queued, active, level, oddThrew, flushed, resumed };
});

console.log("playback:", JSON.stringify(playback));
assert.equal(playback.idle.state, "running", "click must unlock the audio context");
assert.equal(playback.idle.active, false, "silence must not mute the mic");
assert.ok(playback.queued > 0.85 && playback.queued < 1.2,
  `1s of 24kHz PCM queued ${playback.queued.toFixed(3)}s (device rate ${playback.idle.rate})`);
assert.equal(playback.active, true);
assert.ok(playback.level > 0.2, `analyser heard nothing (level ${playback.level})`);
assert.equal(playback.oddThrew, false, "odd-length PCM chunk must not throw");
assert.equal(playback.flushed.active, false, "barge-in flush must stop playback");
assert.equal(playback.flushed.state, "running", "flush must keep the unlocked context");
assert.ok(playback.resumed > 0.85, "next utterance must still schedule after a flush");

await page.evaluate(() => {
  const btn = document.createElement("button");
  btn.id = "mic-go";
  btn.textContent = "mic";
  btn.onclick = () => {
    const chunks = [];
    window.__chunks = chunks;
    window.__micError = null;
    const mic = new window.__audio.MicCapture((buf) => chunks.push(buf.byteLength));
    window.__mic = mic;
    mic.unlock();
    window.__micPromise = mic.start().catch((e) => { window.__micError = String(e); });
  };
  document.body.appendChild(btn);
});
await page.click("#mic-go");
await page.waitForTimeout(1200);
const mic = await page.evaluate(() => {
  window.__mic?.stop();
  const chunks = window.__chunks || [];
  const bytes = chunks.reduce((s, n) => s + n, 0);
  return {
    error: window.__micError,
    n: chunks.length,
    bytes,
    odd: chunks.filter((n) => n % 2).length,
  };
});
console.log("mic:", JSON.stringify(mic));
assert.equal(mic.error, null, mic.error || "mic error");
assert.ok(mic.n > 5, `expected mic frames, got ${mic.n}`);
assert.equal(mic.odd, 0, "PCM16 frames must be even lengths");
// ~32000 bytes/s at 16kHz. Allow startup delay inside the 1.2s window.
assert.ok(mic.bytes > 8000 && mic.bytes < 80000, `mic bytes ${mic.bytes} not near 16kHz PCM`);

await browser.close();
console.log("audio ok");
