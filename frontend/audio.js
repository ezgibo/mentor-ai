// Browser audio for the mock interview.
//   MicStream  — microphone → 16-bit PCM, mono, 16 kHz chunks (what the Live API expects)
//   PcmPlayer  — plays 16-bit PCM chunks (Live API / TTS voice is 24 kHz)
//   encodeWav  — wraps recorded PCM in a WAV file for the turn-by-turn fallback

const TARGET_RATE = 16000;

// Runs on the audio thread: downsample to 16 kHz and post ~100 ms Int16 chunks.
const CAPTURE_WORKLET = `
class Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / ${TARGET_RATE};
    this.pos = 0;
    this.buffer = [];
  }
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;
    for (let i = 0; i < channel.length; i++) {
      this.pos += 1;
      if (this.pos >= this.ratio) {
        this.pos -= this.ratio;
        this.buffer.push(channel[i]);
      }
    }
    if (this.buffer.length >= ${TARGET_RATE / 10}) {
      const out = new Int16Array(this.buffer.length);
      let peak = 0;
      for (let i = 0; i < this.buffer.length; i++) {
        const s = Math.max(-1, Math.min(1, this.buffer[i]));
        peak = Math.max(peak, Math.abs(s));
        out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage({ pcm: out.buffer, peak }, [out.buffer]);
      this.buffer = [];
    }
    return true;
  }
}
registerProcessor('capture', Capture);
`;

export class MicStream {
  constructor() {
    this.context = null;
    this.stream = null;
    this.node = null;
  }

  // onChunk(ArrayBuffer pcm16) is called ~10 times per second; onLevel(0..1) for a level meter.
  async start(onChunk, onLevel = () => {}) {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    this.context = new AudioContext();
    const url = URL.createObjectURL(new Blob([CAPTURE_WORKLET], { type: 'application/javascript' }));
    await this.context.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const source = this.context.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.context, 'capture');
    this.node.port.onmessage = (event) => {
      onChunk(event.data.pcm);
      onLevel(event.data.peak);
    };
    source.connect(this.node);
  }

  stop() {
    if (this.node) this.node.port.onmessage = null;
    if (this.stream) this.stream.getTracks().forEach((track) => track.stop());
    if (this.context) this.context.close();
    this.context = this.stream = this.node = null;
  }
}

export class PcmPlayer {
  constructor(sampleRate = 24000) {
    this.sampleRate = sampleRate;
    this.context = new AudioContext({ sampleRate });
    this.nextTime = 0;
    this.sources = new Set();
  }

  async resume() {
    if (this.context.state === 'suspended') await this.context.resume();
  }

  play(arrayBuffer) {
    const pcm = new Int16Array(arrayBuffer);
    if (!pcm.length) return;
    const buffer = this.context.createBuffer(1, pcm.length, this.sampleRate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 0x8000;
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    const startAt = Math.max(this.context.currentTime + 0.02, this.nextTime);
    source.start(startAt);
    this.nextTime = startAt + buffer.duration;
    this.sources.add(source);
    source.onended = () => this.sources.delete(source);
  }

  // Stop everything immediately (the candidate interrupted the interviewer).
  clear() {
    this.sources.forEach((source) => { try { source.stop(); } catch { /* already stopped */ } });
    this.sources.clear();
    this.nextTime = 0;
  }

  get speaking() {
    return this.nextTime > this.context.currentTime;
  }

  // Resolves when queued audio has finished playing.
  async idle() {
    while (this.speaking) await new Promise((resolve) => setTimeout(resolve, 150));
  }

  close() {
    this.clear();
    this.context.close();
  }
}

export function base64ToArrayBuffer(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

// chunks: ArrayBuffer[] of Int16 PCM at `rate` → a WAV Blob.
export function encodeWav(chunks, rate = TARGET_RATE) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
  const header = new DataView(new ArrayBuffer(44));
  const write = (offset, text) => [...text].forEach((c, i) => header.setUint8(offset + i, c.charCodeAt(0)));
  write(0, 'RIFF');
  header.setUint32(4, 36 + length, true);
  write(8, 'WAVE');
  write(12, 'fmt ');
  header.setUint32(16, 16, true);
  header.setUint16(20, 1, true);          // PCM
  header.setUint16(22, 1, true);          // mono
  header.setUint32(24, rate, true);
  header.setUint32(28, rate * 2, true);   // byte rate
  header.setUint16(32, 2, true);          // block align
  header.setUint16(34, 16, true);         // bits per sample
  write(36, 'data');
  header.setUint32(40, length, true);
  return new Blob([header.buffer, ...chunks], { type: 'audio/wav' });
}
