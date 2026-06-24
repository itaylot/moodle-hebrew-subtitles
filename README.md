# 🎬 כתוביות עברית בזמן אמת ל-Moodle

תוסף Chrome (Manifest V3) שלוכד את אודיו ההרצאה בדף, מתמלל אותו לעברית בזמן אמת, ומציג כתוביות overlay על הסרטון — כמו כתוביות Netflix, רק חיות.

> רץ **לגמרי על המחשב שלך**: תוסף סטטי (JS/HTML/CSS) + שרת תמלול קטן מקומי. אין תלות בענן, אין חשבונות, **אין עלות**.

---

## ✨ מה הוא עושה

- 🎧 **לוכד את אודיו הטאב** (`chrome.tabCapture`) — עובד גם כשהסרטון בתוך iframe (נפוץ ב-Moodle).
- 🔊 **לא קוטע את ההאזנה** — ממשיכים לשמוע את ההרצאה רגיל תוך כדי.
- 🇮🇱 **תמלול עברי** דרך Whisper, עם כתוביות זמניות (אפור) שמתייצבות לסופיות (לבן).
- 🛡️ **עמיד** — מתחבר מחדש לבד אם החיבור נופל, מודיע על שגיאות, ונעצר כשהסרטון נעצר.
- ⚙️ **ניתן להגדרה** — כתובת שרת, גודל ומיקום הכתוביות.

## 🧠 איך זה עובד

```
כפתור בדף  →  service-worker  →  offscreen document            →  שרת תמלול מקומי
(content.js)   (tabCapture)       (AudioWorklet: PCM 16kHz)        (faster-whisper)
     ▲                                   │  WebSocket (PCM)              │
     └──────────  כתובית עברית  ◄─────────┴──────  partial / final  ◄────┘
```

הארכיטקטורה המלאה והנימוקים: [BUILD_SPEC.md](BUILD_SPEC.md) · החוזים בין הרכיבים: [CONTRACTS.md](CONTRACTS.md).

---

## 📥 התקנה (כל אחד מריץ אצלו)

הפרויקט רץ מקומית. שני חלקים: **שרת התמלול** (חלון טרמינל) + **התוסף** (ב-Chrome).

### דרישות מקדימות
- **Google Chrome**.
- **Python** — מומלץ **3.11 או 3.12** (לתמלול אמיתי. לגרסה 3.14 אין עדיין תאימות מלאה).
- **Git** (או להוריד את הקוד כ-ZIP מ-GitHub).

### שלב 1 — הורדת הקוד
```bash
git clone https://github.com/itaylot/moodle-hebrew-subtitles.git
cd moodle-hebrew-subtitles
```
(או: בעמוד ה-GitHub → כפתור ירוק **Code** → **Download ZIP** → חלץ.)

### שלב 2 — הפעלת שרת התמלול
```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac / Linux:
source .venv/bin/activate
```

**א. בדיקה מהירה (עברית מזויפת, בלי הורדת מודל):**
```bash
pip install websockets
python mock_server.py
```

**ב. תמלול עברי אמיתי:**
```bash
pip install -r requirements.txt
python server.py        # בהרצה ראשונה יורד מודל (~כמה מאות MB)
```
השאר את החלון פתוח. אמור להופיע `ready` על `ws://localhost:9090`.
פרטים, GPU ושיפור איכות: [backend/README.md](backend/README.md).

### שלב 3 — טעינת התוסף ב-Chrome
1. פתח `chrome://extensions`
2. הפעל **Developer mode** (פינה ימנית-עליונה)
3. **Load unpacked** → בחר את תיקיית **`extension/`**

### שלב 4 — שימוש
1. פתח דף עם וידאו בעברית (Moodle, או YouTube לבדיקה).
2. לחץ על **אייקון התוסף** בסרגל הכלים → **"▶ הפעל כתוביות"**.
3. הכתוביות מופיעות בתחתית הסרטון. לחיצה שנייה עוצרת.

> ברירת המחדל מחוברת ל-`ws://localhost:9090` — אז אם השרת מהשלב הקודם רץ, הכל עובד מיד, בלי להגדיר כלום.

---

## 📁 מבנה

```
extension/     התוסף עצמו (זה מה שטוענים ב-Chrome)
backend/       שרת התמלול — mock_server.py (בדיקה) + server.py (אמיתי) + הוראות
tools/         ui-mock.html (בדיקת UI) + package-extension.ps1
CONTRACTS.md   פרוטוקול ההודעות הפנימי + פרוטוקול ה-WebSocket
BUILD_SPEC.md  אפיון טכני מלא ונימוקי הארכיטקטורה
```

## 🔒 פרטיות

אודיו ההרצאה נשלח לשרת התמלול בזמן לכידה בלבד. כשהשרת מקומי (`localhost`, ברירת המחדל) — **הכל נשאר על המחשב שלך** ולא נשמר. ראה [PRIVACY.md](PRIVACY.md).

## 🌐 שיתוף מתקדם (אופציונלי)

רוצים ששרת אחד ישרת כמה אנשים? אפשר להריץ שרת משותף עם TLS — ראה [backend/DEPLOY.md](backend/DEPLOY.md). לרוב המקרים, הרצה מקומית (לעיל) פשוטה יותר וחינמית.

---

<sub>נבנה כפרויקט סטודנטיאלי בסיוע <a href="https://claude.com/claude-code">Claude Code</a>. עברית קוראת מימין לשמאל, וגם הכתוביות 🙂</sub>
