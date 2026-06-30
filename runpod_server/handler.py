"""handler.py — RunPod Serverless handler: transcribes audio with faster-whisper.

Input  (job["input"]):  {"audio_b64": "<base64 Opus/Ogg audio>", "language": "he", "beam_size": 5}
Output:                 {"ok": true, "segments": [{"start","end","text"}, ...]}
                      or {"ok": false, "error": "..."}
RunPod wraps this in {"id", "status", "output", "executionTime", ...} automatically.

Two models: a Hebrew-specialised one for language="he", and a general multilingual one for
English / auto-detect. Each loads lazily on first use and is then reused across jobs on the same
worker — only the first request that needs a given model pays its load cost. Both are baked into
the image (see Dockerfile) so that cost is just a local load, not a multi-GB download.
"""

import os
import base64
import tempfile

import runpod
from faster_whisper import WhisperModel

HEBREW_MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2"   # specialised — best for Hebrew
GENERAL_MODEL = "large-v3"                              # multilingual — for English / auto-detect

_models = {}


def get_model(name):
    if name not in _models:
        print("Loading model:", name, flush=True)
        _models[name] = WhisperModel(name, device="cuda", compute_type="float16")
        print("Model loaded:", name, flush=True)
    return _models[name]


get_model(HEBREW_MODEL)   # warm the most common model at startup


def handler(job):
    inp = job.get("input") or {}
    audio_b64 = inp.get("audio_b64")
    if not audio_b64:
        return {"ok": False, "error": "audio_b64 חסר בקלט."}

    language = inp.get("language") or None   # "" / missing → None → Whisper auto-detects the language
    beam_size = int(inp.get("beam_size", 5))
    # Hebrew → specialised model; English or auto-detect → general multilingual model
    model = get_model(HEBREW_MODEL if language == "he" else GENERAL_MODEL)

    fd, audio_path = tempfile.mkstemp(suffix=".ogg")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(base64.b64decode(audio_b64))

        segments, _info = model.transcribe(
            audio_path, language=language, vad_filter=True, beam_size=beam_size)

        out = [
            {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
            for s in segments if s.text.strip()
        ]
        return {"ok": True, "segments": out}
    except Exception as e:  # noqa: BLE001 — surfaced to the client as a readable error
        return {"ok": False, "error": str(e)}
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass


runpod.serverless.start({"handler": handler})
