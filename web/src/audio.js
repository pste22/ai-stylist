// Audio plumbing for the Mira voice bridge.
//  • Mic capture (AudioWorklet) → downsample to 16kHz PCM16 → onChunk(bytes)
//  • Playback of incoming 24kHz PCM16 chunks, gaplessly scheduled.

const MIC_RATE = 16000;
const OUT_RATE = 24000;

function floatTo16BitPCM(float32) {
  const out = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

// Linear resample a Float32 frame from `inRate` down to MIC_RATE.
function downsample(float32, inRate) {
  if (inRate === MIC_RATE) return float32;
  const ratio = inRate / MIC_RATE;
  const outLen = Math.floor(float32.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    out[i] = float32[Math.floor(i * ratio)];
  }
  return out;
}

export class MicCapture {
  constructor(onChunk) {
    this.onChunk = onChunk;
    this.ctx = null;
    this.stream = null;
    this.node = null;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    this.ctx = new AudioContext();
    await this.ctx.audioWorklet.addModule("/mic-processor.js");
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "mic-processor");
    this.node.port.onmessage = (e) => {
      const ds = downsample(e.data, this.ctx.sampleRate);
      this.onChunk(floatTo16BitPCM(ds).buffer);
    };
    src.connect(this.node);
    // Worklet needs a sink to keep pulling; route to a muted gain.
    const sink = this.ctx.createGain();
    sink.gain.value = 0;
    this.node.connect(sink).connect(this.ctx.destination);
  }

  stop() {
    this.node?.port.close();
    this.node?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.ctx = this.stream = this.node = null;
  }
}

export class PcmPlayer {
  constructor() {
    this.ctx = null;
    this.nextTime = 0;
  }

  _ensure() {
    if (!this.ctx) {
      this.ctx = new AudioContext({ sampleRate: OUT_RATE });
      this.nextTime = this.ctx.currentTime;
    }
  }

  // Schedule a PCM16 @24kHz chunk right after whatever's already queued.
  push(arrayBuffer) {
    this._ensure();
    const pcm = new Int16Array(arrayBuffer);
    const buf = this.ctx.createBuffer(1, pcm.length, OUT_RATE);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000;
    const node = this.ctx.createBufferSource();
    node.buffer = buf;
    node.connect(this.ctx.destination);
    const start = Math.max(this.nextTime, this.ctx.currentTime);
    node.start(start);
    this.nextTime = start + buf.duration;
  }

  // Barge-in: drop everything queued so Mira stops instantly.
  flush() {
    if (this.ctx) {
      this.ctx.close();
      this.ctx = null;
    }
  }
}
