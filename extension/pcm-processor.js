// pcm-processor.js — AudioWorklet (חייב להיות קובץ נפרד! נטען דרך audioWorklet.addModule)
//
// ממיר Float32 (מה שהדפדפן נותן) ל-Int16 PCM little-endian — מה ש-Whisper דורש.
// צובר ~100ms (1600 דגימות ב-16kHz) לבלוק לפני שליחה, כדי לא להציף את ה-WebSocket.

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
    this.targetSamples = 1600; // ~100ms ב-16kHz
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const channel = input[0]; // mono — ערוץ ראשון מספיק לתמלול דיבור

    for (let i = 0; i < channel.length; i++) {
      this.buffer.push(channel[i]);
    }

    while (this.buffer.length >= this.targetSamples) {
      const chunk = this.buffer.splice(0, this.targetSamples);
      const pcm = new Int16Array(chunk.length);
      for (let i = 0; i < chunk.length; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i])); // clamp ל-[-1,1]
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff; // float → int16
      }
      // transferable — מעביר את ה-buffer בלי העתקה
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true; // השאר את ה-processor חי
  }
}

registerProcessor('pcm-processor', PCMProcessor);
