"""app.py — אפליקציית כתוביות עברית להרצאות (עיצוב דשבורד מודרני, גרירה, בלי שורת פקודה).

בוחרים או גוררים קובץ הרצאה → "צור כתוביות" → צופים עם כתוביות עברית מסונכרנות.
סרגל צד עם "הרצאות אחרונות", אזור ראשי בהיר עם כרטיסים, שלב + זמן משוער.
"""

import os
import json
import time
import queue
import pathlib
import threading
import webbrowser

import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES

MODEL_ACCURATE = "ivrit-ai/whisper-large-v3-turbo-ct2"
MODEL_FAST = "small"

# ── פלטת צבעים (בהשראת דשבורד סגול/ירוק) ──
SIDEBAR = "#2E2B4A"
SIDEBAR_HOVER = "#3b3760"
BG = "#F3F4FA"
CARD = "#FFFFFF"
CARD_BORDER = "#E6E7F0"
PURPLE = "#6C5CE7"
PURPLE_HOVER = "#5a4bd4"
GREEN = "#28D9A0"
GREEN_HOVER = "#1fbf8c"
TEXT = "#2D2D3A"
MUTED = "#9AA0AA"
SIDE_MUTED = "#b9b6d6"

STORE = pathlib.Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "heb-subs" / "recent.json"
VIDEO_EXT = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mp3", ".m4a", ".wav", ".flac", ".ogg")


def fmt_time(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def human(sec: float) -> str:
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d} שע׳"
    if m:
        return f"{m}:{s:02d} דק׳"
    return f"{s} שנ׳"


def load_recent():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_recent(items):
    try:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="he" dir="rtl"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
 body{margin:0;background:#15151a;font-family:system-ui,Arial,sans-serif}
 #stage{position:relative;max-width:1100px;margin:0 auto}
 video{width:100%;display:block}
 #subs{position:absolute;bottom:7%;left:50%;transform:translateX(-50%);max-width:90%;
  text-align:center;direction:rtl;background:rgba(0,0,0,.72);color:#fff;font-size:30px;
  font-weight:600;line-height:1.35;padding:4px 16px;border-radius:8px;
  text-shadow:0 1px 3px rgba(0,0,0,.9);pointer-events:none;white-space:pre-wrap}
 #subs:empty{display:none}
</style></head><body>
<div id="stage"><video id="v" src="__SRC__" controls autoplay></video><div id="subs"></div></div>
<script>
 const cues=__CUES__,v=document.getElementById('v'),s=document.getElementById('subs');
 v.addEventListener('timeupdate',()=>{const t=v.currentTime;
   const c=cues.find(c=>t>=c.start&&t<=c.end);s.textContent=c?c.text:'';});
</script></body></html>"""


class Tk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


def cfont(size, weight="normal"):
    return ctk.CTkFont("Segoe UI", size, weight)


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.video_path = None
        self.model = None
        self.model_name = None
        self.viewer_path = None
        self.q = queue.Queue()
        self.recent = load_recent()

        root.title("כתוביות עברית להרצאות")
        ctk.set_appearance_mode("light")
        root.configure(fg_color=BG)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._refresh_recent()

    # ── סרגל צד ──
    def _build_sidebar(self):
        bar = ctk.CTkFrame(self.root, fg_color=SIDEBAR, width=230, corner_radius=0)
        bar.grid(row=0, column=0, sticky="nsew")
        bar.grid_propagate(False)

        # לוגו + שם
        top = ctk.CTkFrame(bar, fg_color="transparent")
        top.pack(fill="x", padx=22, pady=(26, 18))
        badge = ctk.CTkLabel(top, text="🎬", font=cfont(22), width=44, height=44,
                             fg_color=PURPLE, corner_radius=12)
        badge.pack(side="right")
        ctk.CTkLabel(top, text="כתוביות עברית", font=cfont(16, "bold"),
                     text_color="#ffffff").pack(side="right", padx=10)

        # כפתור "תמלול חדש"
        ctk.CTkButton(bar, text="＋  תמלול חדש", height=44, corner_radius=22,
                      font=cfont(14, "bold"), fg_color=GREEN, hover_color=GREEN_HOVER,
                      text_color="#0c2a22", command=self.new_session).pack(fill="x", padx=20, pady=(0, 22))

        ctk.CTkLabel(bar, text="הרצאות אחרונות", font=cfont(12, "bold"),
                     text_color=SIDE_MUTED).pack(anchor="e", padx=24, pady=(0, 6))
        self.recent_box = ctk.CTkScrollableFrame(bar, fg_color="transparent")
        self.recent_box.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        ctk.CTkLabel(bar, text="רץ מקומית · בלי עלות", font=cfont(11),
                     text_color=SIDE_MUTED).pack(side="bottom", pady=14)

    # ── אזור ראשי ──
    def _build_main(self):
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=30, pady=26)
        main.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(main, text="תמלול הרצאה", font=cfont(24, "bold"),
                     text_color=TEXT).pack(anchor="e")
        ctk.CTkLabel(main, text="גוררים קובץ הרצאה, יוצרים כתוביות עברית, וצופים — הכל כאן.",
                     font=cfont(13), text_color=MUTED).pack(anchor="e", pady=(0, 16))

        # כרטיס גרירה
        self.drop = ctk.CTkFrame(main, fg_color=CARD, border_color=CARD_BORDER,
                                 border_width=2, corner_radius=18, height=150)
        self.drop.pack(fill="x", pady=(0, 14))
        self.drop.pack_propagate(False)
        self.drop_icon = ctk.CTkLabel(self.drop, text="⬇️", font=cfont(34))
        self.drop_icon.pack(pady=(24, 2))
        self.drop_title = ctk.CTkLabel(self.drop, text="גררו לכאן קובץ הרצאה",
                                       font=cfont(16, "bold"), text_color=TEXT)
        self.drop_title.pack()
        self.drop_sub = ctk.CTkLabel(self.drop, text="או לחצו לבחירת קובץ מהמחשב",
                                     font=cfont(12), text_color=MUTED)
        self.drop_sub.pack(pady=(2, 0))
        for w in (self.drop, self.drop_icon, self.drop_title, self.drop_sub):
            w.bind("<Button-1>", lambda e: self.choose())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self.on_drop)

        # שורת מצב + כפתור ראשי
        row = ctk.CTkFrame(main, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        self.mode = ctk.CTkSegmentedButton(row, values=["מדויק", "מהיר"],
                                           selected_color=PURPLE, selected_hover_color=PURPLE_HOVER,
                                           font=cfont(13))
        self.mode.set("מדויק")
        self.mode.pack(side="right")
        ctk.CTkLabel(row, text="איכות:", font=cfont(13), text_color=MUTED).pack(side="right", padx=10)
        self.go_btn = ctk.CTkButton(row, text="צור כתוביות  ▶", height=40, width=170,
                                    font=cfont(15, "bold"), corner_radius=12,
                                    fg_color=PURPLE, hover_color=PURPLE_HOVER,
                                    command=self.start, state="disabled")
        self.go_btn.pack(side="left")

        # כרטיס סטטוס
        self.status_card = ctk.CTkFrame(main, fg_color=CARD, border_color=CARD_BORDER,
                                        border_width=1, corner_radius=16)
        self.status_card.pack(fill="x", pady=(0, 12))
        self.stage_lbl = ctk.CTkLabel(self.status_card, text="מוכן להתחיל",
                                      font=cfont(15, "bold"), text_color=TEXT)
        self.stage_lbl.pack(pady=(14, 6))
        self.prog = ctk.CTkProgressBar(self.status_card, height=12, corner_radius=6, progress_color=PURPLE)
        self.prog.set(0)
        self.prog.pack(fill="x", padx=20, pady=(0, 8))
        self.detail_lbl = ctk.CTkLabel(self.status_card, text="בחרו קובץ כדי להתחיל",
                                       font=cfont(12), text_color=MUTED)
        self.detail_lbl.pack(pady=(0, 14))

        # יומן
        self.log = ctk.CTkTextbox(main, font=ctk.CTkFont("Consolas", 12), corner_radius=14,
                                  fg_color=CARD, border_color=CARD_BORDER, border_width=1,
                                  text_color=TEXT, wrap="word", height=120)
        self.log.pack(fill="both", expand=True, pady=(0, 12))
        self.log.configure(state="disabled")

        self.watch_btn = ctk.CTkButton(main, text="▶  צפה עם כתוביות", height=46,
                                       font=cfont(16, "bold"), corner_radius=12,
                                       fg_color=GREEN, hover_color=GREEN_HOVER, text_color="#0c2a22",
                                       command=self.watch, state="disabled")
        self.watch_btn.pack(fill="x")

    # ── רשימת אחרונות ──
    def _refresh_recent(self):
        for w in self.recent_box.winfo_children():
            w.destroy()
        if not self.recent:
            ctk.CTkLabel(self.recent_box, text="עדיין אין", font=cfont(12),
                         text_color=SIDE_MUTED).pack(pady=8)
            return
        for it in self.recent[:10]:
            b = ctk.CTkButton(self.recent_box, text="🎞  " + it["name"][:24], anchor="e",
                              font=cfont(12), fg_color="transparent", hover_color=SIDEBAR_HOVER,
                              text_color="#e7e6f5", corner_radius=8, height=34,
                              command=lambda v=it.get("viewer"): self._open_viewer(v))
            b.pack(fill="x", pady=2)

    def _add_recent(self, name, viewer):
        self.recent = [r for r in self.recent if r.get("viewer") != viewer]
        self.recent.insert(0, {"name": name, "viewer": viewer, "date": time.strftime("%Y-%m-%d")})
        self.recent = self.recent[:20]
        save_recent(self.recent)
        self._refresh_recent()

    def _open_viewer(self, path):
        if path and os.path.exists(path):
            webbrowser.open("file:///" + path.replace("\\", "/"))
        else:
            messagebox.showinfo("לא נמצא", "קובץ הצפייה לא נמצא (אולי נמחק/הוזז).")

    # ── אינטראקציה ──
    def _hover(self, on):
        if not self.video_path:
            self.drop.configure(border_color=PURPLE if on else CARD_BORDER)

    def new_session(self):
        self.video_path = None
        self.viewer_path = None
        self.drop_icon.configure(text="⬇️")
        self.drop_title.configure(text="גררו לכאן קובץ הרצאה", text_color=TEXT)
        self.drop_sub.configure(text="או לחצו לבחירת קובץ מהמחשב")
        self.drop.configure(border_color=CARD_BORDER)
        self.go_btn.configure(state="disabled")
        self.watch_btn.configure(state="disabled")
        self.stage_lbl.configure(text="מוכן להתחיל", text_color=TEXT)
        self.detail_lbl.configure(text="בחרו קובץ כדי להתחיל")
        self.prog.configure(mode="determinate"); self.prog.set(0)
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.configure(state="disabled")

    def on_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            self.set_file(files[0])

    def choose(self):
        p = filedialog.askopenfilename(
            title="בחר קובץ הרצאה",
            filetypes=[("וידאו/אודיו", "*.mp4 *.mkv *.webm *.mov *.avi *.m4v *.mp3 *.m4a *.wav"),
                       ("כל הקבצים", "*.*")])
        if p:
            self.set_file(p)

    def set_file(self, path):
        if not os.path.isfile(path):
            return
        if os.path.splitext(path)[1].lower() not in VIDEO_EXT:
            messagebox.showwarning("קובץ לא נתמך", "זה לא נראה כמו קובץ וידאו/אודיו. נסו קובץ אחר.")
            return
        self.video_path = path
        self.drop_icon.configure(text="🎞️")
        self.drop_title.configure(text=os.path.basename(path), text_color=TEXT)
        self.drop_sub.configure(text="מוכן! לחצו ״צור כתוביות״ (או גררו קובץ אחר)")
        self.drop.configure(border_color=PURPLE)
        self.go_btn.configure(state="normal")
        self.watch_btn.configure(state="disabled")
        self.stage_lbl.configure(text="מוכן להתחיל", text_color=TEXT)
        self.detail_lbl.configure(text="לחצו ״צור כתוביות״")
        self.prog.configure(mode="determinate"); self.prog.set(0)

    def logmsg(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ── תמלול ──
    def start(self):
        self.go_btn.configure(state="disabled")
        self.watch_btn.configure(state="disabled")
        self.prog.set(0)
        threading.Thread(target=self.worker, daemon=True).start()
        self.root.after(120, self.poll)

    def worker(self):
        try:
            from faster_whisper import WhisperModel
            fast = self.mode.get() == "מהיר"
            name = MODEL_FAST if fast else MODEL_ACCURATE
            if self.model is None or self.model_name != name:
                self.q.put(("stage", ("load", "טוען מודל… (בפעם הראשונה מוריד, כמה דקות)")))
                self.model = WhisperModel(name, device="cpu", compute_type="int8")
                self.model_name = name
            self.q.put(("stage", ("trans", "מתמלל…")))
            segments, info = self.model.transcribe(
                self.video_path, language="he", vad_filter=True, beam_size=5)
            dur = getattr(info, "duration", 0) or 0
            base = os.path.splitext(self.video_path)[0]
            srt = base + ".srt"
            cues = []
            t0 = time.time()
            with open(srt, "w", encoding="utf-8") as fh:
                n = 0
                for seg in segments:
                    txt = seg.text.strip()
                    if not txt:
                        continue
                    n += 1
                    fh.write(f"{n}\n{fmt_time(seg.start)} --> {fmt_time(seg.end)}\n{txt}\n\n")
                    cues.append({"start": round(seg.start, 3), "end": round(seg.end, 3), "text": txt})
                    self.q.put(("log", f"[{fmt_time(seg.start)}] {txt}"))
                    if dur:
                        elapsed = time.time() - t0
                        rate = seg.end / elapsed if elapsed > 0 else 0
                        eta = (dur - seg.end) / rate if rate > 0 else 0
                        self.q.put(("progress", (min(0.99, seg.end / dur), elapsed, eta)))
            self.q.put(("stage", ("finalize", "מכין נגן…")))
            self.viewer_path = self.make_viewer(self.video_path, cues)
            self.q.put(("done", (n, os.path.basename(self.video_path), self.viewer_path)))
        except Exception as e:  # noqa: BLE001
            self.q.put(("error", str(e)))

    def make_viewer(self, video, cues):
        folder = os.path.dirname(video)
        base = os.path.splitext(os.path.basename(video))[0]
        html = (VIEWER_TEMPLATE
                .replace("__TITLE__", base)
                .replace("__SRC__", os.path.basename(video))
                .replace("__CUES__", json.dumps(cues, ensure_ascii=False)))
        out = os.path.join(folder, base + " — כתוביות.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        return out

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.logmsg(val)
                elif kind == "stage":
                    code, text = val
                    self.stage_lbl.configure(text=text, text_color=TEXT)
                    if code == "load":
                        self.prog.configure(mode="indeterminate"); self.prog.start()
                        self.detail_lbl.configure(text="מתכונן…")
                    elif code == "trans":
                        self.prog.stop(); self.prog.configure(mode="determinate"); self.prog.set(0)
                    elif code == "finalize":
                        self.prog.stop(); self.prog.configure(mode="determinate"); self.prog.set(0.99)
                        self.detail_lbl.configure(text="כמעט סיימנו…")
                elif kind == "progress":
                    frac, elapsed, eta = val
                    self.prog.set(frac)
                    self.detail_lbl.configure(
                        text=f"{int(frac * 100)}%      ·      נותרו בערך {human(eta)}      ·      עברו {human(elapsed)}")
                elif kind == "done":
                    n, name, viewer = val
                    self.prog.set(1.0)
                    self.stage_lbl.configure(text=f"✓ מוכן! נוצרו {n} כתוביות", text_color=GREEN_HOVER)
                    self.detail_lbl.configure(text="לחצו ״צפה עם כתוביות״")
                    self.watch_btn.configure(state="normal")
                    self.go_btn.configure(state="normal")
                    self._add_recent(name, viewer)
                    return
                elif kind == "error":
                    self.prog.stop()
                    self.stage_lbl.configure(text="אירעה שגיאה", text_color="#e0455e")
                    self.detail_lbl.configure(text=str(val)[:80])
                    messagebox.showerror("שגיאה", str(val))
                    self.go_btn.configure(state="normal")
                    return
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def watch(self):
        self._open_viewer(self.viewer_path)


def center(root, w, h):
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"{w}x{h}+{x}+{y}")


def main():
    root = Tk()
    App(root)
    center(root, 940, 700)
    root.minsize(820, 600)
    root.mainloop()


if __name__ == "__main__":
    main()
