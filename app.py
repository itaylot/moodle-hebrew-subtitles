"""app.py — אפליקציית כתוביות עברית להרצאות (ממשק מודרני, גרירה, בלי שורת פקודה).

בוחרים או **גוררים** קובץ הרצאה → "צור כתוביות" → צופים עם כתוביות עברית מסונכרנות.
"""

import os
import json
import queue
import threading
import webbrowser

import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES

MODEL_ACCURATE = "ivrit-ai/whisper-large-v3-turbo-ct2"
MODEL_FAST = "small"

ACCENT = "#6C5CE7"
ACCENT_HOVER = "#5a4bd4"
SUCCESS = "#22c55e"
CARD = "#26262e"
CARD_BORDER = "#3a3a44"
MUTED = "#9aa0aa"

VIDEO_EXT = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".mp3", ".m4a", ".wav")


def fmt_time(t: float) -> str:
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


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


# שילוב customtkinter עם tkinterdnd2 (גרירת קבצים)
class Tk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.video_path = None
        self.model = None
        self.model_name = None
        self.viewer_path = None
        self.q = queue.Queue()

        root.title("כתוביות עברית להרצאות")
        root.geometry("660x680")
        root.minsize(560, 600)
        ctk.set_appearance_mode("dark")

        wrap = ctk.CTkFrame(root, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=26, pady=22)

        # כותרת
        ctk.CTkLabel(wrap, text="🎬  כתוביות עברית להרצאות",
                     font=ctk.CTkFont("Segoe UI", 26, "bold")).pack(anchor="center", pady=(2, 2))
        ctk.CTkLabel(wrap, text="גוררים הרצאה, יוצרים כתוביות, וצופים — הכל כאן.",
                     font=ctk.CTkFont("Segoe UI", 14), text_color=MUTED).pack(anchor="center", pady=(0, 18))

        # אזור גרירה / בחירה
        self.drop = ctk.CTkFrame(wrap, fg_color=CARD, border_color=CARD_BORDER,
                                 border_width=2, corner_radius=18, height=170)
        self.drop.pack(fill="x", pady=(0, 16))
        self.drop.pack_propagate(False)
        self.drop_icon = ctk.CTkLabel(self.drop, text="⬇️", font=ctk.CTkFont(size=40))
        self.drop_icon.pack(pady=(28, 4))
        self.drop_title = ctk.CTkLabel(self.drop, text="גררו לכאן קובץ הרצאה",
                                       font=ctk.CTkFont("Segoe UI", 17, "bold"))
        self.drop_title.pack()
        self.drop_sub = ctk.CTkLabel(self.drop, text="או לחצו לבחירת קובץ מהמחשב",
                                     font=ctk.CTkFont("Segoe UI", 13), text_color=MUTED)
        self.drop_sub.pack(pady=(2, 0))

        for w in (self.drop, self.drop_icon, self.drop_title, self.drop_sub):
            w.bind("<Button-1>", lambda e: self.choose())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))
        # רישום יעד גרירה (על החלון כולו — גרירה לכל מקום עובדת)
        root.drop_target_register(DND_FILES)
        root.dnd_bind("<<Drop>>", self.on_drop)

        # מצב דיוק/מהירות + כפתור ראשי
        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))
        self.mode = ctk.CTkSegmentedButton(row, values=["מדויק", "מהיר"],
                                           selected_color=ACCENT, selected_hover_color=ACCENT_HOVER)
        self.mode.set("מדויק")
        self.mode.pack(side="right")
        ctk.CTkLabel(row, text="איכות התמלול:", font=ctk.CTkFont("Segoe UI", 13),
                     text_color=MUTED).pack(side="right", padx=10)

        self.go_btn = ctk.CTkButton(wrap, text="צור כתוביות  ▶", height=46,
                                    font=ctk.CTkFont("Segoe UI", 16, "bold"), corner_radius=12,
                                    fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                    command=self.start, state="disabled")
        self.go_btn.pack(fill="x", pady=(0, 12))

        self.prog = ctk.CTkProgressBar(wrap, height=12, corner_radius=6, progress_color=ACCENT)
        self.prog.set(0)
        self.prog.pack(fill="x", pady=(0, 12))

        self.log = ctk.CTkTextbox(wrap, font=ctk.CTkFont("Consolas", 12), corner_radius=12,
                                  fg_color=CARD, wrap="word")
        self.log.pack(fill="both", expand=True, pady=(0, 12))
        self.log.configure(state="disabled")

        self.watch_btn = ctk.CTkButton(wrap, text="▶  צפה עם כתוביות", height=46,
                                       font=ctk.CTkFont("Segoe UI", 16, "bold"), corner_radius=12,
                                       fg_color=SUCCESS, hover_color="#16a34a",
                                       command=self.watch, state="disabled")
        self.watch_btn.pack(fill="x")

    # ── עיצוב/אינטראקציה ───────────────────────────────────
    def _hover(self, on):
        self.drop.configure(border_color=ACCENT if on else CARD_BORDER)

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
        self.video_path = path
        self.drop_icon.configure(text="🎞️")
        self.drop_title.configure(text=os.path.basename(path), text_color="#ffffff")
        self.drop_sub.configure(text="מוכן! לחצו ״צור כתוביות״ (או גררו קובץ אחר)")
        self.drop.configure(border_color=ACCENT)
        self.go_btn.configure(state="normal")
        self.watch_btn.configure(state="disabled")

    def logmsg(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ── תמלול ──────────────────────────────────────────────
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
                self.q.put(("log", f"טוען מודל ({'מהיר' if fast else 'מדויק'})… בפעם הראשונה זו הורדה, סבלנות."))
                self.model = WhisperModel(name, device="cpu", compute_type="int8")
                self.model_name = name
            self.q.put(("log", "מתמלל… (על המעבד זה לוקח זמן — רץ פעם אחת)"))
            segments, info = self.model.transcribe(
                self.video_path, language="he", vad_filter=True, beam_size=5)
            dur = getattr(info, "duration", 0) or 0
            base = os.path.splitext(self.video_path)[0]
            srt = base + ".srt"
            cues = []
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
                        self.q.put(("prog", min(0.99, seg.end / dur)))
            self.viewer_path = self.make_viewer(self.video_path, cues)
            self.q.put(("prog", 1.0))
            self.q.put(("done", n))
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
                elif kind == "prog":
                    self.prog.set(val)
                elif kind == "done":
                    self.logmsg(f"\n✓ נוצרו {val} כתוביות. אפשר לצפות!")
                    self.watch_btn.configure(state="normal")
                    self.go_btn.configure(state="normal")
                    return
                elif kind == "error":
                    messagebox.showerror("שגיאה", val)
                    self.logmsg("שגיאה: " + val)
                    self.go_btn.configure(state="normal")
                    return
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def watch(self):
        if self.viewer_path and os.path.exists(self.viewer_path):
            webbrowser.open("file:///" + self.viewer_path.replace("\\", "/"))


def center(root, w, h):
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"{w}x{h}+{x}+{y}")


def main():
    root = Tk()
    App(root)
    center(root, 660, 680)
    root.mainloop()


if __name__ == "__main__":
    main()
