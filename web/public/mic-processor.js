// AudioWorklet: forwards raw mic frames (Float32 @ context sample rate) to the main
// thread, which downsamples to 16kHz PCM16 for Gemini Live. Kept dumb on purpose.
class MicProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0]) {
      // Copy — the underlying buffer is reused by the engine.
      this.port.postMessage(input[0].slice(0));
    }
    return true;
  }
}
registerProcessor("mic-processor", MicProcessor);
