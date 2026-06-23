"""mock_server.py — שרת תמלול מדומה (ללא ML), מדבר בדיוק לפי חוזה B.

מטרה: לבדוק את כל פייפליין התוסף (capture → offscreen → UI) **בלי** Whisper.
מחזיר טקסט עברי מזויף בקצב סביר. כך מאמתים שהצינור עובד מקצה-לקצה לפני
שמתעסקים בהתקנת המודל האמיתי.

הרצה:  python mock_server.py     (מאזין על ws://localhost:9090)
"""

import asyncio
import json

import websockets

HOST = "localhost"
PORT = 9090

# שלבי "תמלול" מזויפים — מתארכים בהדרגה כמו partial אמיתי
PARTIALS = [
    "שלום",
    "שלום לכולם",
    "שלום לכולם וברוכים",
    "שלום לכולם וברוכים הבאים להרצאה",
]
FINAL = "שלום לכולם וברוכים הבאים להרצאה."


async def handle(ws, *_):
    # הודעה ראשונה לפי חוזה B: config JSON
    try:
        first = await ws.recv()
        print("[mock] config:", first)
    except Exception as e:  # noqa: BLE001
        print("[mock] no config message:", e)

    frames = 0  # כל frame ≈ 100ms אודיו
    idx = 0
    try:
        async for msg in ws:
            if not isinstance(msg, (bytes, bytearray)):
                continue  # מתעלמים מהודעות טקסט אחרי ה-config
            frames += 1

            # כל ~0.5s → partial (אפור, מתעדכן)
            if frames % 5 == 0:
                text = PARTIALS[min(idx, len(PARTIALS) - 1)]
                await ws.send(json.dumps(
                    {"type": "partial", "text": text, "is_final": False},
                    ensure_ascii=False,
                ))
                idx += 1

            # כל ~2.5s → final (לבן, יציב) ואיפוס
            if frames % 25 == 0:
                await ws.send(json.dumps(
                    {"type": "final", "text": FINAL, "is_final": True},
                    ensure_ascii=False,
                ))
                idx = 0
    except websockets.ConnectionClosed:
        pass
    print("[mock] client disconnected")


async def main():
    print(f"[mock] STT server on ws://{HOST}:{PORT} (contract B, no ML)")
    async with websockets.serve(handle, HOST, PORT, max_size=None):
        await asyncio.Future()  # רוץ לנצח


if __name__ == "__main__":
    asyncio.run(main())
