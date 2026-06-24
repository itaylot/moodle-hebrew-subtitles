"""test_client.py — לקוח בדיקה לשרת (mock או אמיתי), מאמת את חוזה B.

שולח הודעת config + ~3 שניות של frames PCM (כאן: שקט/רעש מזויף), ומדפיס
כל partial/final שמתקבל. שימושי גם לוודא שהשרת רץ ומדבר נכון.

הרצה (כשהשרת פעיל):  python test_client.py
"""

import asyncio
import json
import struct
import math
import sys

import websockets

# אפשר להעביר כתובת כפרמטר, למשל wss://xxx.trycloudflare.com
URI = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:9090"
FRAME_SAMPLES = 1600  # ~100ms ב-16kHz (כמו ה-AudioWorklet)
NUM_FRAMES = 30       # ~3 שניות


def make_frame(i: int) -> bytes:
    """frame של Int16 PCM — גל סינוס קליל כדי לא להיות שקט מוחלט."""
    out = bytearray()
    for n in range(FRAME_SAMPLES):
        val = int(3000 * math.sin(2 * math.pi * 220 * (i * FRAME_SAMPLES + n) / 16000))
        out += struct.pack("<h", val)
    return bytes(out)


async def main():
    async with websockets.connect(URI, max_size=None) as ws:
        await ws.send(json.dumps(
            {"language": "he", "sample_rate": 16000, "encoding": "pcm_s16le"}
        ))
        print("[client] sent config, streaming PCM...")

        async def sender():
            for i in range(NUM_FRAMES):
                await ws.send(make_frame(i))
                await asyncio.sleep(0.1)
            await asyncio.sleep(1.0)  # לתת לשרת לסיים final
            await ws.close()

        async def receiver():
            try:
                async for m in ws:
                    print("[client] recv:", m)
            except websockets.ConnectionClosed:
                pass

        await asyncio.gather(sender(), receiver())
    print("[client] done")


if __name__ == "__main__":
    asyncio.run(main())
