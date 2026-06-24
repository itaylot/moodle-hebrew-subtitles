# Moodle Hebrew Subtitles

תוסף Chrome (Manifest V3) שמתמלל את אודיו סרטוני Moodle לעברית בזמן אמת ומציג כתוביות overlay על הסרטון.

> התוסף הוא JS/HTML/CSS סטטי. הוא שולח את האודיו לשרת תמלול (Whisper) ומקבל טקסט. **אין שום קריאה ל-Claude API בזמן ריצה.**

## מבנה הריפו

```
SUB-PRO/
├── START_HERE.md           # סדר העבודה והצ'קפוינטים
├── BUILD_SPEC.md           # האפיון הטכני המלא (מקור אמת)
├── MULTI_AGENT_BUILD.md    # חלוקת הבנייה לסוכנים
├── GOAL.md                 # היעד הסופי + בדיקת הקבלה ("מתי סיימנו")
├── CONTRACTS.md            # החוזים הקפואים (A: הודעות פנימיות, B: WebSocket)
├── README.md
├── extension/              # ⬅️ זה מה שטוענים ב-Chrome (Load unpacked)
│   ├── manifest.json       # [Lead]
│   ├── service-worker.js   # [Capture]
│   ├── offscreen.html/js   # [Capture]
│   ├── pcm-processor.js    # [Capture] AudioWorklet — קובץ נפרד חובה
│   ├── content.js          # [UI] כפתור + overlay
│   ├── subtitles.css       # [UI]
│   ├── popup.html/js       # [UI]
│   ├── options.html/js     # [UI]
│   ├── lib/
│   └── icons/              # [Lead] placeholder
└── backend/                # [Backend] שרת תמלול (WhisperLive) — נוצר בשלב מאוחר
```

## איך מריצים (אחרי שהבנייה תושלם)

1. **שרת התמלול:** ראה `backend/README.md` (בדיקה מקומית: CPU + מודל קטן).
2. **התוסף:** `chrome://extensions` → הפעל Developer mode → **Load unpacked** → בחר את תיקיית `extension/`.
3. פתח דף Moodle עם וידאו → לחץ על כפתור "▶ כתוביות".

## סטטוס בנייה

- [x] שלב 1 — Lead: שלד, `manifest.json`, `CONTRACTS.md`, icons.
- [x] שלב 2 — Capture Agent (service-worker, offscreen, pcm-processor)
- [x] שלב 2 — UI Agent (content, css, popup, options)
- [x] שלב 2 — Backend Agent (mock + faster-whisper, חוזה B אומת)
- [x] שלב 3 — אינטגרציה E2E ✅ **רמה A הושגה** — בדיקת הקבלה 1-7 ([GOAL.md](GOAL.md)) עברה מול שרת mock על YouTube: כתוביות עברית חיות על הסרטון, האודיו נשמר, עצירה נקייה.

➡️ **להרצה ולבדיקת הקבלה (רמה A):** [RUN.md](RUN.md)
