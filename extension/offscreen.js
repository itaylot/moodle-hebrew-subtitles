// offscreen.js — לב מסלול האודיו.
//
// מקבל streamId → MediaStream → AudioContext + AudioWorklet → PCM → WebSocket → טקסט.
//
// ⚠️ ה-offscreen לא נוגע ב-DOM של הדף. טקסט הכתוביות חוזר דרך ה-service worker
//    (chrome.runtime messaging), ומשם ל-content script. ראה חוזה A.

let audioContext = null;
let workletNode = null;
let sourceNode = null;
let ws = null;
let mediaStream = null;
let currentTabId = null;
let endedReported = false;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.target !== 'offscreen') return;
  if (msg.type === 'START') {
    start(msg.streamId, msg.config).catch((e) => {
      console.error('[offscreen] start failed:', e);
      reportEnded('error: ' + e.message);
    });
  } else if (msg.type === 'STOP') {
    stop();
    reportEnded('stopped');
  }
});

async function start(streamId, config) {
  currentTabId = config.tabId;
  endedReported = false;

  // 1. MediaStream מתוך ה-streamId (tab capture)
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: 'tab',
        chromeMediaSourceId: streamId,
      },
    },
    video: false,
  });

  // 2. AudioContext ב-16kHz → הדפדפן נותן ישירות 16kHz, בלי resampling ידני
  audioContext = new AudioContext({ sampleRate: 16000 });
  sourceNode = audioContext.createMediaStreamSource(mediaStream);

  // 3. טען את ה-AudioWorklet (קובץ נפרד! נטען דרך getURL, חייב web_accessible_resources)
  await audioContext.audioWorklet.addModule(chrome.runtime.getURL('pcm-processor.js'));
  workletNode = new AudioWorkletNode(audioContext, 'pcm-processor');

  // 4. חיבורים:
  //    source → worklet       (להפקת PCM לשליחה ל-backend)
  //    source → destination   ← ⚠️ קריטי! בלי זה המשתמש מפסיק לשמוע את ההרצאה
  sourceNode.connect(workletNode);
  sourceNode.connect(audioContext.destination);

  console.log('[offscreen] capture started @', audioContext.sampleRate, 'Hz');

  // 5. WebSocket ל-backend
  ws = new WebSocket(config.endpoint);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    // הודעת config ראשונה (חוזה B)
    ws.send(
      JSON.stringify({
        language: config.language,
        sample_rate: config.sampleRate,
        encoding: config.encoding,
      })
    );
    console.log('[offscreen] ws open →', config.endpoint);
  };

  ws.onmessage = (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return; // התעלם מהודעות שאינן JSON תקין
    }
    if (typeof data.text !== 'string') return;
    // חוזה B: שדה type הוא הסמכותי; isFinal = (type === 'final')
    const isFinal = data.type === 'final' || data.is_final === true;
    chrome.runtime.sendMessage({
      type: 'TRANSCRIPT',
      from: 'offscreen',
      tabId: currentTabId,
      text: data.text,
      isFinal,
    });
  };

  ws.onerror = () => console.error('[offscreen] WebSocket error');
  ws.onclose = () => reportEnded('ws closed');

  // 6. PCM מה-worklet → WebSocket
  workletNode.port.onmessage = (e) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(e.data); // ArrayBuffer של Int16 PCM
    }
  };
}

function stop() {
  if (workletNode) {
    workletNode.port.onmessage = null;
    workletNode.disconnect();
  }
  if (sourceNode) sourceNode.disconnect();
  if (ws) {
    ws.onclose = null; // כדי לא לדווח פעמיים דרך onclose
    try {
      ws.close();
    } catch {}
  }
  if (audioContext) audioContext.close().catch(() => {});
  if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
  audioContext = workletNode = sourceNode = ws = mediaStream = null;
}

// מודיע ל-SW שהלכידה הסתיימה (לעדכון ה-UI). נשלח פעם אחת בלבד לכל הפעלה.
function reportEnded(reason) {
  if (endedReported) return;
  endedReported = true;
  chrome.runtime.sendMessage({
    type: 'CAPTURE_ENDED',
    from: 'offscreen',
    tabId: currentTabId,
    reason,
  });
}
