"""
⚡ CODEPILOT — AI Coding Assistant for Flask Projects
Cyberpunk UI | Scans your codebase + logs | Powered by Gemini
"""

import os, json, time, threading, fnmatch
import tkinter as tk
from tkinter import scrolledtext, filedialog
import urllib.request, urllib.error

# ============================================================
GEMINI_API_KEY = "your gemini key"
APP_NAME = "Gosi"

# Files/extensions to scan
CODE_EXTENSIONS = {".py", ".html", ".xml", ".js", ".css", ".cfg", ".conf", ".txt", ".log"}
IGNORE_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", "env",
               "migrations", ".idea", ".vscode", "static", "dist", "build"}
MAX_FILE_CHARS = 6000     # truncate huge files when sending to AI
MAX_TOTAL_CONTEXT = 45000 # cap total chars sent to Gemini per question
LOG_EXTENSIONS = {".log", ".txt"}

# ============================================================
# 🎨 COLORS — Cyberpunk theme
# ============================================================
BG       = "#0a0118"
BG2      = "#120726"
PANEL    = "#0d0420"
NEON_P   = "#b14aff"   # purple
NEON_P_D = "#5a2580"
NEON_C   = "#00f0ff"   # cyan
NEON_C_D = "#007a80"
NEON_PINK= "#ff2e88"
WHITE    = "#e8e0ff"
GRAY     = "#4a3a66"
GREEN    = "#39ff88"
RED      = "#ff3860"
YELLOW   = "#ffe14d"

# ============================================================
# 📁 PROJECT SCANNER
# ============================================================
class ProjectIndex:
    def __init__(self):
        self.root = None
        self.files = []        # list of relative paths
        self.file_contents = {}  # path -> content (truncated)

    def scan(self, root_path):
        self.root = root_path
        self.files = []
        self.file_contents = {}
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext in CODE_EXTENSIONS:
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, root_path)
                    self.files.append(rel)
        return len(self.files)

    def read_file(self, rel_path):
        full = os.path.join(self.root, rel_path)
        try:
            with open(full, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + "\n...[truncated]..."
            return content
        except Exception as e:
            return f"[Error reading file: {e}]"

    def find_relevant_files(self, query, max_files=8):
        """Very simple relevance scoring: filename mention + keyword overlap."""
        query_lower = query.lower()
        words = [w for w in query_lower.replace("/", " ").replace(".", " ").split() if len(w) > 2]
        scored = []
        for rel in self.files:
            score = 0
            rel_lower = rel.lower()
            # direct filename mention
            base = os.path.basename(rel_lower)
            if base in query_lower or base.replace(".py","") in query_lower:
                score += 10
            for w in words:
                if w in rel_lower:
                    score += 3
            # prioritize logs if query mentions error/log/exception
            if any(k in query_lower for k in ["error", "خطا", "exception", "log", "لاگ", "crash"]):
                if rel_lower.endswith((".log", ".txt")):
                    score += 5
            if score > 0:
                scored.append((score, rel))
        scored.sort(key=lambda x: -x[0])
        top = [rel for _, rel in scored[:max_files]]
        # fallback: if nothing matched, grab a few main files
        if not top:
            py_files = [f for f in self.files if f.endswith(".py")]
            top = py_files[:max_files]
        return top

    def build_context(self, query):
        relevant = self.find_relevant_files(query)
        context_parts = []
        total = 0
        for rel in relevant:
            content = self.read_file(rel)
            piece = f"\n--- FILE: {rel} ---\n{content}\n"
            if total + len(piece) > MAX_TOTAL_CONTEXT:
                break
            context_parts.append(piece)
            total += len(piece)
        return "".join(context_parts), relevant


PROJECT = ProjectIndex()

# ============================================================
# 🧠 GEMINI
# ============================================================
SYSTEM_PROMPT = """You are CodePilot, an expert AI coding assistant specialized in Python, Flask,
and Odoo projects. The user speaks Persian or English — always reply in the same language they used.

You will be given relevant source files and/or log excerpts from the user's project as CONTEXT,
followed by their QUESTION. Use the context to:
- Explain bugs and their root cause
- Suggest concrete code fixes (show code snippets)
- Explain what a piece of code does
- Help debug errors from logs

Be concise but technical. If the context doesn't contain enough information, say so clearly
and ask what additional file you should look at, rather than guessing."""

def ask_gemini(context, question, history):
    history_text = ""
    for role, msg in history[-6:]:
        history_text += f"\n{role}: {msg}\n"

    full_prompt = f"{SYSTEM_PROMPT}\n\n=== PROJECT CONTEXT ===\n{context}\n\n=== CONVERSATION HISTORY ===\n{history_text}\n\n=== QUESTION ===\n{question}\n\nAnswer:"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": full_prompt}]}]
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep((attempt + 1) * 5)
                continue
            raise Exception(f"Gemini API error: {e.code}")
        except urllib.error.URLError:
            raise Exception("اتصال به اینترنت برقرار نیست.")
    raise Exception("سرویس Gemini شلوغه، چند لحظه صبر کن.")

# ============================================================
# 🎨 GUI
# ============================================================
class CodePilotApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} — AI Coding Assistant")
        self.root.geometry("1000x720")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self.history = []  # list of (role, text)
        self.processing = False

        self.build_ui()
        self.log_system(f"{APP_NAME} آماده‌ست. اول یه پوشه پروژه انتخاب کن (دکمه بالا سمت راست).")

    def build_ui(self):
        # HEADER
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x")
        tk.Frame(header, bg=NEON_P, height=2).pack(fill="x")
        bar = tk.Frame(header, bg=BG, pady=14, padx=22)
        bar.pack(fill="x")

        tk.Label(bar, text="⚡", font=("Consolas", 20, "bold"), bg=BG, fg=NEON_C).pack(side="left", padx=(0,10))
        title_frame = tk.Frame(bar, bg=BG)
        title_frame.pack(side="left")
        tk.Label(title_frame, text=APP_NAME, font=("Consolas", 18, "bold"),
                 bg=BG, fg=NEON_P).pack(anchor="w")
        tk.Label(title_frame, text="AI CODING ASSISTANT · FLASK / ODOO",
                 font=("Consolas", 8), bg=BG, fg=GRAY).pack(anchor="w")

        self.folder_btn = tk.Button(
            bar, text="📁 انتخاب پوشه پروژه", font=("Consolas", 9, "bold"),
            bg=PANEL, fg=NEON_C, activebackground=BG2, activeforeground=NEON_C,
            relief="flat", bd=0, padx=14, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=NEON_C_D,
            command=self.choose_folder
        )
        self.folder_btn.pack(side="right")

        self.project_lbl = tk.Label(bar, text="هیچ پروژه‌ای انتخاب نشده",
                                     font=("Consolas", 8), bg=BG, fg=GRAY)
        self.project_lbl.pack(side="right", padx=12)

        tk.Frame(header, bg=NEON_P_D, height=1).pack(fill="x")

        # MAIN: split chat (left, wide) and file list (right, narrow)
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        chat_col = tk.Frame(main, bg=BG)
        chat_col.pack(side="left", fill="both", expand=True)

        files_col = tk.Frame(main, bg=BG, width=240)
        files_col.pack(side="left", fill="y", padx=(10,0))
        files_col.pack_propagate(False)

        # CHAT
        self.chat = scrolledtext.ScrolledText(
            chat_col, bg=PANEL, fg=WHITE, font=("Consolas", 10),
            bd=0, relief="flat", padx=14, pady=14, wrap=tk.WORD,
            state="disabled", cursor="arrow", insertbackground=NEON_C
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("sys",  foreground=YELLOW, font=("Consolas", 9, "italic"))
        self.chat.tag_config("you",  foreground=NEON_C, font=("Consolas", 10, "bold"))
        self.chat.tag_config("bot",  foreground=WHITE, font=("Consolas", 10))
        self.chat.tag_config("err",  foreground=RED)
        self.chat.tag_config("meta", foreground=NEON_P, font=("Consolas", 8))

        # INPUT
        tk.Frame(chat_col, bg=NEON_P_D, height=1).pack(fill="x", pady=(8,8))
        input_row = tk.Frame(chat_col, bg=BG)
        input_row.pack(fill="x")

        self.input_var = tk.StringVar()
        self.input_field = tk.Entry(
            input_row, textvariable=self.input_var,
            font=("Consolas", 11), bg=PANEL, fg=WHITE,
            insertbackground=NEON_C, relief="flat", bd=10
        )
        self.input_field.pack(side="left", fill="x", expand=True, ipady=6)
        self.input_field.bind("<Return>", self.send)
        self.input_field.focus()

        self.send_btn = tk.Button(
            input_row, text="ASK ⚡", font=("Consolas", 10, "bold"),
            bg=NEON_P, fg=BG, activebackground=NEON_C, activeforeground=BG,
            relief="flat", bd=0, padx=18, pady=8, cursor="hand2",
            command=self.send
        )
        self.send_btn.pack(side="left", padx=(8,0))

        # FILE LIST PANEL
        tk.Frame(files_col, bg=NEON_C_D, height=1).pack(fill="x")
        fhdr = tk.Frame(files_col, bg=PANEL, pady=6)
        fhdr.pack(fill="x")
        tk.Label(fhdr, text="📂 PROJECT FILES", font=("Consolas", 8, "bold"),
                 bg=PANEL, fg=NEON_C).pack(padx=8, anchor="w")
        tk.Frame(files_col, bg=NEON_C_D, height=1).pack(fill="x")

        self.file_list = tk.Listbox(
            files_col, bg=PANEL, fg=GRAY, font=("Consolas", 8),
            bd=0, relief="flat", highlightthickness=0,
            selectbackground=NEON_P_D, selectforeground=WHITE
        )
        self.file_list.pack(fill="both", expand=True, padx=2, pady=2)

        # FOOTER
        footer = tk.Frame(self.root, bg=BG, pady=6)
        footer.pack(fill="x")
        tk.Label(footer, text=f"{APP_NAME} v1.0 · Powered by Gemini · Persian & English",
                 font=("Consolas", 7), bg=BG, fg=GRAY).pack()

    def log(self, role, text):
        self.chat.config(state="normal")
        if role == "sys":
            self.chat.insert("end", f"\n  ✦ {text}\n", "sys")
        elif role == "you":
            self.chat.insert("end", f"\n┌─ YOU\n", "meta")
            self.chat.insert("end", f"│  {text}\n", "you")
            self.chat.insert("end", f"└{'─'*40}\n", "meta")
        elif role == "bot":
            self.chat.insert("end", f"\n┌─ {APP_NAME}\n", "meta")
            self.chat.insert("end", f"│  {text}\n", "bot")
            self.chat.insert("end", f"└{'─'*40}\n", "meta")
        elif role == "err":
            self.chat.insert("end", f"  ✗ {text}\n", "err")
        self.chat.config(state="disabled")
        self.chat.see("end")

    def log_system(self, text):
        self.log("sys", text)

    def choose_folder(self):
        folder = filedialog.askdirectory(title="پوشه پروژه رو انتخاب کن")
        if not folder:
            return
        self.folder_btn.config(state="disabled", text="در حال اسکن...")
        threading.Thread(target=self._scan_folder, args=(folder,), daemon=True).start()

    def _scan_folder(self, folder):
        try:
            count = PROJECT.scan(folder)
            self.root.after(0, lambda: self._on_scan_done(folder, count))
        except Exception as e:
            self.root.after(0, lambda: self.log("err", f"خطا در اسکن: {e}"))
            self.root.after(0, lambda: self.folder_btn.config(state="normal", text="📁 انتخاب پوشه پروژه"))

    def _on_scan_done(self, folder, count):
        short_name = os.path.basename(folder.rstrip("/\\")) or folder
        self.project_lbl.config(text=f"📦 {short_name}  ({count} فایل)", fg=NEON_C)
        self.folder_btn.config(state="normal", text="📁 تغییر پوشه")
        self.file_list.delete(0, "end")
        for f in sorted(PROJECT.files)[:200]:
            self.file_list.insert("end", f)
        self.log_system(f"پروژه اسکن شد: {count} فایل کد/لاگ پیدا شد. حالا می‌تونی سوال بپرسی.")

    def send(self, event=None):
        q = self.input_var.get().strip()
        if not q or self.processing:
            return
        if PROJECT.root is None:
            self.log("err", "اول یه پوشه پروژه انتخاب کن.")
            return
        self.input_var.set("")
        self.log("you", q)
        self.history.append(("User", q))

        self.processing = True
        self.send_btn.config(state="disabled", text="...")
        threading.Thread(target=self._process, args=(q,), daemon=True).start()

    def _process(self, question):
        try:
            context, relevant = PROJECT.build_context(question)
            answer = ask_gemini(context, question, self.history)
            self.history.append(("Assistant", answer))

            files_note = "، ".join(relevant) if relevant else "هیچ فایلی"
            self.root.after(0, lambda: self.log("sys", f"فایل‌های بررسی‌شده: {files_note}"))
            self.root.after(0, lambda: self.log("bot", answer))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.log("err", err))
        finally:
            self.processing = False
            self.root.after(0, lambda: self.send_btn.config(state="normal", text="ASK ⚡"))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = CodePilotApp()
    app.run()