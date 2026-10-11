// Audio plumbing for the Mira voice bridge.
//  • Mic capture (AudioWorklet) → downsample to 16kHz PCM16 → onChunk(bytes)
//  • Playback of incoming 24kHz PCM16 chunks, gaplessly scheduled.
//
// Playback must be unlocked during the click that starts voice. Creating the
// AudioContext later (websocket onmessage) leaves it suspended, so Mira's PCM
// arrives and nothing comes out of the speakers.

const MIC_RATE = 16000;
const OUT_RATE = 24000;
// Keep the mic closed briefly after the last scheduled sample so speaker
// tail doesn't trip Gemini's VAD and cut Mira off.
const OUTPUT_HANGOVER_SEC = 0.25;

function floatTo16BitPCM(float32) {
  const out = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

// Linear resample. Used both to downsample the mic to 16kHz and to play
// Gemini's 24kHz PCM on whatever rate the output device actually runs at.
export function resampleLinear(float32, inRate, outRate) {
  if (inRate === outRate || float32.length === 0) return float32;
  const ratio = inRate / outRate;
  const outLen = Math.floor(float32.length / ratio);
  if (outLen <= 0) return new Float32Array(0);
  const out = new Float32Array(outLen);
  const max = float32.length - 1;
  for (let i = 0; i < outLen; i++) {
    const x = i * ratio;
    const i0 = Math.floor(x);
    const i1 = Math.min(i0 + 1, max);
    const f = x - i0;
    out[i] = float32[i0] * (1 - f) + float32[i1] * f;
  }
  return out;
}

function pcm16ToFloat32(arrayBuffer) {
  const bytes = arrayBuffer.byteLength - (arrayBuffer.byteLength % 2);
  if (bytes < 2) return new Float32Array(0);
  const pcm = new Int16Array(arrayBuffer, 0, bytes / 2);
  const out = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) out[i] = pcm[i] / 0x8000;
  return out;
}

export class MicCapture {
  constructor(onChunk) {
    this.onChunk = onChunk;
    this.ctx = null;
    this.stream = null;
    this.node = null;
    this._resume = null;
  }

  // Call synchronously inside the click that turns voice on.
  unlock() {
    if (this.ctx) {
      this._resume = this.ctx.resume();
      return;
    }
    this.ctx = new AudioContext();
    this._resume = this.ctx.resume();
  }

  async start() {
    this.unlock();
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      this.stop();
      throw e;
    }
    if (!this.ctx) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    this.stream = stream;
    try {
      await this._resume;
      await this.ctx.resume();
      if (!this.ctx || !this.stream) return;
      await this.ctx.audioWorklet.addModule("/mic-processor.js");
      if (!this.ctx || !this.stream) return;
      const src = this.ctx.createMediaStreamSource(this.stream);
      this.node = new AudioWorkletNode(this.ctx, "mic-processor");
      this.node.port.onmessage = (e) => {
        if (!this.ctx) return;
        const ds = resampleLinear(e.data, this.ctx.sampleRate, MIC_RATE);
        if (!ds.length) return;
        this.onChunk(floatTo16BitPCM(ds).buffer);
      };
      src.connect(this.node);
      // Worklet needs a sink to keep pulling; route to a muted gain.
      const sink = this.ctx.createGain();
      sink.gain.value = 0;
      this.node.connect(sink).connect(this.ctx.destination);
    } catch (e) {
      this.stop();
      throw e;
    }
  }

  stop() {
    try { this.node?.port.close(); } catch { /* already closed */ }
    try { this.node?.disconnect(); } catch { /* already disconnected */ }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.ctx = this.stream = this.node = null;
  }
}

export class PcmPlayer {
  constructor() {
    this.ctx = null;
    this.nextTime = 0;
    this.analyser = null;
    this._buf = null;
    this._sources = new Set();
    this._resume = null;
    // Context time at which the last queued sample ends. Stays 0 until real
    // audio is scheduled so an unlocked-but-silent player doesn't mute the mic.
    this._quietAt = 0;
  }

  // Call synchronously inside the click that turns voice on.
  unlock() {
    this._ensure();
    this._resume = this.ctx.resume();
  }

  _ensure() {
    if (this.ctx) return;
    // Don't pin sampleRate to 24kHz — Safari and some Chromium builds reject
    // that and throw, which used to kill the socket handler. Resample instead.
    this.ctx = new AudioContext();
    this.nextTime = this.ctx.currentTime;
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.connect(this.ctx.destination);
    this._buf = new Float32Array(this.analyser.fftSize);
  }

  // Schedule a PCM16 @24kHz chunk right after whatever's already queued.
  push(arrayBuffer) {
    if (!arrayBuffer || arrayBuffer.byteLength < 2) return;
    this._ensure();
    if (this.ctx.state === "suspended") this.ctx.resume();
    const floats = pcm16ToFloat32(arrayBuffer);
    const samples = resampleLinear(floats, OUT_RATE, this.ctx.sampleRate);
    if (!samples.length) return;
    const buf = this.ctx.createBuffer(1, samples.length, this.ctx.sampleRate);
    buf.getChannelData(0).set(samples);
    const node = this.ctx.createBufferSource();
    node.buffer = buf;
    node.connect(this.analyser);
    const start = Math.max(this.nextTime, this.ctx.currentTime);
    node.onended = () => this._sources.delete(node);
    this._sources.add(node);
    node.start(start);
    this.nextTime = start + buf.duration;
    this._quietAt = this.nextTime;
  }

  // Seconds of Mira still waiting to play. ~1.0 after a 1s chunk means the
  // 24kHz PCM was scheduled at the right speed on this device.
  queuedSeconds() {
    if (!this.ctx) return 0;
    return Math.max(0, this.nextTime - this.ctx.currentTime);
  }

  // True while scheduled speech (plus a short tail) is still coming out.
  isOutputActive() {
    if (!this.ctx) return false;
    if (this.nextTime > this.ctx.currentTime + 0.02) return true;
    return this._quietAt > 0 && this.ctx.currentTime < this._quietAt + OUTPUT_HANGOVER_SEC;
  }

  // Current output loudness as RMS in ~0..1 — drives the avatar's mouth.
  getLevel() {
    if (!this.analyser || !this._buf) return 0;
    this.analyser.getFloatTimeDomainData(this._buf);
    let sum = 0;
    for (let i = 0; i < this._buf.length; i++) sum += this._buf[i] * this._buf[i];
    const rms = Math.sqrt(sum / this._buf.length);
    return Math.min(1, rms * 3.5); // gain so normal speech swings the mouth fully
  }

  // Barge-in: drop everything queued so Mira stops instantly.
  // Keeps the unlocked AudioContext — closing it here made the next
  // utterance silent, because the replacement context had no user gesture.
  flush() {
    for (const node of this._sources) {
      try { node.stop(); } catch { /* already stopped */ }
      try { node.disconnect(); } catch { /* already disconnected */ }
    }
    this._sources.clear();
    if (this.ctx) this.nextTime = this.ctx.currentTime;
    this._quietAt = 0;
  }

  close() {
    this.flush();
    if (this.ctx) {
      this.ctx.close();
      this.ctx = null;
      this.analyser = null;
      this._buf = null;
    }
  }
}
