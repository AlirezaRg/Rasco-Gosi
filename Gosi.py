"""
⚡ CODEPILOT — AI Coding Assistant for Flask Projects
Cyberpunk UI | Scans your codebase + logs | Powered by AlirezaRg (Pro/Max subscription)
"""

import os, json, time, threading, fnmatch, subprocess, math, shutil, tempfile
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import urllib.request, urllib.error

# ============================================================
CLAUDE_MODEL = "sonnet"  # alias: 'sonnet', 'opus', or full model name
APP_NAME = "CODEPILOT"

def find_claude_command():
    """
    سعی می‌کنه مسیر claude.cmd رو پیدا کنه، چون بستگی به اینکه برنامه چطور
    اجرا شده (CMD/VS Code Run/شورتکات)، PATH ممکنه شامل npm global نباشه.
    """
    found = shutil.which("claude") or shutil.which("claude.cmd")
    if found:
        return found
    candidates = [
        os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
        os.path.expanduser(r"~\AppData\Roaming\npm\claude.cmd"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return "claude"

CLAUDE_CMD_PATH = find_claude_command()

# Files/extensions to scan
CODE_EXTENSIONS = {".py", ".html", ".xml", ".js", ".css", ".cfg", ".conf", ".txt", ".log"}
IGNORE_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", "env",
               "migrations", ".idea", ".vscode", "static", "dist", "build"}
MAX_FILE_CHARS = 6000     # truncate huge files when sending to AI
MAX_TOTAL_CONTEXT = 45000 # cap total chars sent to Claude per question
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
# 🧠 CLAUDE CODE
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

EDIT_SYSTEM_PROMPT = """You are CodePilot, an expert AI coding assistant. The user wants you to
directly edit a file based on their instruction. The user speaks Persian or English.

You will be given the FULL CONTENT of one file, followed by an EDIT INSTRUCTION describing
what change they want.

Your job: produce the COMPLETE new version of the file with the requested change applied.

Rules:
- Output ONLY the full new file content — no explanations, no markdown code fences, no
  commentary before or after.
- Preserve everything in the file that the instruction didn't ask you to change.
- If the instruction is ambiguous or could be destructive in an unexpected way, still make
  your best reasonable interpretation (the user will review a diff before anything is saved)."""

def ask_claude_code(context, question, history):
    history_text = ""
    for role, msg in history[-6:]:
        history_text += f"\n{role}: {msg}\n"

    full_prompt = f"{SYSTEM_PROMPT}\n\n=== PROJECT CONTEXT ===\n{context}\n\n=== CONVERSATION HISTORY ===\n{history_text}\n\n=== QUESTION ===\n{question}\n\nAnswer:"
    return _run_claude(full_prompt, timeout=120)


def _run_claude(prompt, timeout=120):
    """
    اجرای claude با نوشتن prompt توی یه فایل موقت و پایپ کردنش با 'type' —
    این روش برای پرامپت‌های بزرگ روی ویندوز خیلی مطمئن‌تر از input= مستقیمه.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write(prompt)
            tmp_path = tmp.name

        cmd = f'type "{tmp_path}" | "{CLAUDE_CMD_PATH}" -p --model {CLAUDE_MODEL}'
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, encoding="utf-8", timeout=timeout,
            shell=True
        )
    except subprocess.TimeoutExpired:
        raise Exception("Claude Code خیلی طول کشید. دوباره امتحان کن.")
    except FileNotFoundError:
        raise Exception("دستور 'claude' پیدا نشد. مطمئن شو Claude Code نصب و لاگین شده.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    if result.returncode != 0:
        err = (result.stderr or "").strip() or (result.stdout or "").strip() or "خطای نامشخص"
        raise Exception(f"Claude Code خطا داد (کد {result.returncode}): {err[:300]}")

    answer = (result.stdout or "").strip()
    if not answer:
        raise Exception("Claude Code جواب خالی برگردوند.")
    return answer


def ask_claude_for_edit(file_content, instruction, filename):
    """از Claude می‌خواد نسخه کامل و ویرایش‌شده فایل رو برگردونه."""
    prompt = (
        f"{EDIT_SYSTEM_PROMPT}\n\n--- FILE: {filename} ---\n{file_content}\n"
        f"\n--- EDIT INSTRUCTION ---\n{instruction}\n"
        f"\nRespond with ONLY the full new file content, nothing else."
    )
    new_content = _run_claude(prompt, timeout=180)
    # پاکسازی fence های احتمالی که مدل گاهی اضافه می‌کنه
    if new_content.startswith("```"):
        lines = new_content.split("\n")
        new_content = "\n".join(lines[1:])
    if new_content.endswith("```"):
        lines = new_content.split("\n")
        new_content = "\n".join(lines[:-1])
    return new_content.strip("\n") + "\n"

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

        # حالت چهره گوسی: idle / thinking / talking / error
        self.face_state = "idle"
        self.angle = 0
        self.talk_phase = 0
        self.blink_timer = 0

        self.build_ui()
        self.animate_face()
        self.log_system(f"{APP_NAME} آماده‌ست. «🐞 دیباگ یه فایل» برای بررسی، «✏️ ویرایش مستقیم فایل» برای تغییر مستقیم (با تأیید و بکاپ خودکار)، یا «📁 انتخاب پوشه پروژه» برای سوال درباره کل پروژه.")

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
        tk.Label(title_frame, text=APP_NAME, font=("Consolas", 24, "bold"),
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

        self.debug_btn = tk.Button(
            bar, text="🐞 دیباگ یه فایل", font=("Consolas", 9, "bold"),
            bg=PANEL, fg=NEON_PINK, activebackground=BG2, activeforeground=NEON_PINK,
            relief="flat", bd=0, padx=14, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=NEON_PINK,
            command=self.choose_file_to_debug
        )
        self.debug_btn.pack(side="right", padx=(0,8))

        self.edit_btn = tk.Button(
            bar, text="✏️ ویرایش مستقیم فایل", font=("Consolas", 9, "bold"),
            bg=PANEL, fg=GREEN, activebackground=BG2, activeforeground=GREEN,
            relief="flat", bd=0, padx=14, pady=8, cursor="hand2",
            highlightthickness=1, highlightbackground=GREEN,
            command=self.choose_file_to_edit
        )
        self.edit_btn.pack(side="right", padx=(0,8))

        self.project_lbl = tk.Label(bar, text="هیچ پروژه‌ای انتخاب نشده",
                                     font=("Consolas", 8), bg=BG, fg=GRAY)
        self.project_lbl.pack(side="right", padx=12)

        tk.Frame(header, bg=NEON_P_D, height=1).pack(fill="x")

        # MAIN: avatar (left, narrow) + chat (center, wide) + file list (right, narrow)
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        avatar_col = tk.Frame(main, bg=BG, width=190)
        avatar_col.pack(side="left", fill="y", padx=(0,10))
        avatar_col.pack_propagate(False)

        chat_col = tk.Frame(main, bg=BG)
        chat_col.pack(side="left", fill="both", expand=True)

        files_col = tk.Frame(main, bg=BG, width=240)
        files_col.pack(side="left", fill="y", padx=(10,0))
        files_col.pack_propagate(False)

        # AVATAR PANEL
        tk.Frame(avatar_col, bg=NEON_C_D, height=1).pack(fill="x")
        ahdr = tk.Frame(avatar_col, bg=PANEL, pady=6)
        ahdr.pack(fill="x")
        tk.Label(ahdr, text="🐑 GOSI", font=("Consolas", 8, "bold"),
                 bg=PANEL, fg=NEON_C).pack(padx=8, anchor="w")
        tk.Frame(avatar_col, bg=NEON_C_D, height=1).pack(fill="x")

        self.avatar_canvas = tk.Canvas(avatar_col, bg=PANEL, highlightthickness=0,
                                       width=186, height=200)
        self.avatar_canvas.pack(fill="x", pady=(0,4))

        self.face_state_lbl = tk.Label(avatar_col, text="IDLE", font=("Consolas", 8, "bold"),
                                       bg=PANEL, fg=GRAY)
        self.face_state_lbl.pack(fill="x", pady=(0,6))

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
        tk.Label(footer, text=f"{APP_NAME} v1.0 · Powered by AlirezaRg· Persian & English",
                 font=("Consolas", 7), bg=BG, fg=GRAY).pack()

    def set_face_state(self, state):
        """state: idle / thinking / talking / error"""
        self.face_state = state

    def animate_face(self):
        c = self.avatar_canvas
        c.delete("all")
        cx, cy = 93, 95

        bounce = math.sin(math.radians(self.angle*2)) * 2

        WOOL      = "#f0eaff"   # cyberpunk-tinted wool (light lavender white)
        WOOL_SH   = "#d8cdf0"
        FACE_SKIN = "#2a2438"   # dark muzzle/face patch
        FACE_SKIN_L = "#3a3250"
        HORN      = "#6a5a80"
        HORN_D    = "#4a3d5e"
        LENS      = "#0c0c0c"
        LENS_RIM  = NEON_C

        hx, hy = cx, cy + bounce

        # ── WOOL (big poofy cloud-like head) ──
        wool_r = 58
        puff_positions = [
            (0, -10), (-32, -2), (32, -2), (-20, 18), (20, 18),
            (-38, 22), (38, 22), (0, 30)
        ]
        for dx, dy in puff_positions:
            pr = 26
            c.create_oval(hx+dx-pr, hy+dy-pr, hx+dx+pr, hy+dy+pr,
                         fill=WOOL, outline=WOOL_SH, width=1)
        c.create_oval(hx-wool_r, hy-wool_r, hx+wool_r, hy+wool_r,
                     fill=WOOL, outline=WOOL_SH, width=1)

        # ── HORNS — small curled cyberpunk horns ──
        for side in (-1, 1):
            hx0 = hx + side*40
            hy0 = hy - 38
            c.create_arc(hx0-12, hy0-14, hx0+12, hy0+14,
                        start=20 if side>0 else 150, extent=160,
                        outline=HORN, width=5, style="arc")
            c.create_oval(hx0+side*8-3, hy0-10-3, hx0+side*8+3, hy0-10+3, fill=HORN_D, outline="")

        # ── FACE PATCH (dark muzzle area, like real sheep face) ──
        face_w, face_h = 34, 30
        face_cy = hy + 14
        c.create_oval(hx-face_w, face_cy-face_h, hx+face_w, face_cy+face_h,
                     fill=FACE_SKIN, outline=FACE_SKIN_L, width=2)

        # ── GLASSES — small round tech glasses ──
        lens_r = 11
        bridge_y = face_cy - 4
        eye_dx = 16
        for side in (-1, 1):
            ex = hx + side*eye_dx
            c.create_oval(ex-lens_r, bridge_y-lens_r, ex+lens_r, bridge_y+lens_r,
                         fill=LENS, outline=LENS_RIM, width=2)
            c.create_line(ex-lens_r+4, bridge_y-lens_r+3, ex-2, bridge_y-2,
                         fill=NEON_C, width=1)
        c.create_line(hx-eye_dx+lens_r, bridge_y, hx+eye_dx-lens_r, bridge_y,
                     fill=LENS_RIM, width=2)

        # eyebrow glow — shows mood since eyes hidden behind lenses
        self.blink_timer += 1
        brow_y = bridge_y - lens_r - 7
        if self.face_state == "error":
            brow_tilt = 5
        elif self.face_state == "thinking":
            brow_tilt = 3
        else:
            brow_tilt = 0
        for side in (-1, 1):
            ex = hx + side*eye_dx
            glow = RED if self.face_state == "error" else NEON_C
            c.create_line(ex-7, brow_y + brow_tilt*side, ex+7, brow_y - brow_tilt*side,
                         fill=glow, width=2, capstyle="round")

        # nose/mouth area — small dark nose + mouth that changes with state
        nose_y = face_cy + 12
        c.create_oval(hx-6, nose_y-4, hx+6, nose_y+4, fill="#1a1626", outline="")

        mouth_y = nose_y + 9
        mouth_w = 14
        if self.face_state == "talking":
            self.talk_phase += 1
            open_amt = 4 + 4 * abs(math.sin(self.talk_phase * 0.6))
            c.create_oval(hx-mouth_w/2.4, mouth_y-open_amt/2, hx+mouth_w/2.4, mouth_y+open_amt/2,
                         fill="#1a1626", outline=NEON_C, width=1)
        elif self.face_state == "thinking":
            c.create_line(hx-mouth_w/2.5, mouth_y, hx+mouth_w/2.5, mouth_y-2,
                         fill=NEON_C, width=2, capstyle="round")
        elif self.face_state == "error":
            c.create_line(hx-mouth_w/2.5, mouth_y+4, hx+mouth_w/2.5, mouth_y-4,
                         fill=RED, width=2, capstyle="round")
        else:  # idle — small content smile
            c.create_arc(hx-mouth_w/1.6, mouth_y-10, hx+mouth_w/1.6, mouth_y+10,
                        start=200, extent=140, outline=NEON_C, width=2, style="arc")

        # ── EARS — small floppy sheep ears on the sides ──
        for side in (-1, 1):
            ex = hx + side*54
            ey = hy + 6
            c.create_oval(ex-side*8, ey-14, ex+side*8, ey+14,
                         fill=FACE_SKIN, outline=FACE_SKIN_L, width=2)

        # state label
        labels = {"idle": ("IDLE", GRAY), "thinking": ("THINKING", NEON_P),
                  "talking": ("TALKING", NEON_C), "error": ("ERROR", RED)}
        lbl, lbl_col = labels.get(self.face_state, ("IDLE", GRAY))
        self.face_state_lbl.config(text=lbl, fg=lbl_col)

        self.angle = (self.angle + 0.7) % 720
        self.root.after(45, self.animate_face)

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

    def choose_file_to_debug(self):
        filepath = filedialog.askopenfilename(
            title="فایلی که می‌خوای دیباگ شه رو انتخاب کن",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if not filepath:
            return
        self.debug_btn.config(state="disabled", text="در حال بررسی...")
        self.log("you", f"دیباگ فایل: {os.path.basename(filepath)}")
        threading.Thread(target=self._debug_file, args=(filepath,), daemon=True).start()

    def _debug_file(self, filepath):
        self.root.after(0, lambda: self.set_face_state("thinking"))
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if len(content) > MAX_FILE_CHARS * 2:
                content = content[:MAX_FILE_CHARS * 2] + "\n...[truncated]..."

            question = (
                f"این فایل پایتون رو بررسی کن و باگ‌ها، خطاهای احتمالی، یا مشکلات منطقی رو "
                f"پیدا کن. اگه خطایی پیدا کردی، دقیقاً بگو کجاست و چطور درستش کنم (با کد اصلاح‌شده). "
                f"اگه چیزی مشکل‌دار نبود هم بگو."
            )
            context = f"\n--- FILE: {os.path.basename(filepath)} ---\n{content}\n"

            answer = ask_claude_code(context, question, self.history)
            self.history.append(("User", f"[Debug request for {os.path.basename(filepath)}]"))
            self.history.append(("Assistant", answer))

            self.root.after(0, lambda: self.log("sys", f"فایل بررسی‌شده: {os.path.basename(filepath)}"))
            self.root.after(0, lambda: self.log("bot", answer))
            self.root.after(0, lambda: self.set_face_state("talking"))
            self.root.after(2500, lambda: self.set_face_state("idle"))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.log("err", err))
            self.root.after(0, lambda: self.set_face_state("error"))
            self.root.after(2500, lambda: self.set_face_state("idle"))
        finally:
            self.root.after(0, lambda: self.debug_btn.config(state="normal", text="🐞 دیباگ یه فایل"))

    # ── DIRECT FILE EDITING ──────────────────────────────────
    def choose_file_to_edit(self):
        filepath = filedialog.askopenfilename(
            title="فایلی که می‌خوای ویرایش شه رو انتخاب کن",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if not filepath:
            return

        from tkinter import simpledialog
        instruction = simpledialog.askstring(
            "دستور ویرایش",
            f"چه تغییری توی «{os.path.basename(filepath)}» می‌خوای انجام بدم؟\n"
            f"(مثلاً: «تابع X رو حذف کن» یا «این باگ رو درست کن: ...»)",
            parent=self.root
        )
        if not instruction or not instruction.strip():
            return

        self.edit_btn.config(state="disabled", text="در حال ویرایش...")
        self.log("you", f"ویرایش «{os.path.basename(filepath)}»: {instruction}")
        threading.Thread(target=self._edit_file_thread,
                         args=(filepath, instruction), daemon=True).start()

    def _edit_file_thread(self, filepath, instruction):
        self.root.after(0, lambda: self.set_face_state("thinking"))
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                original_content = f.read()

            if len(original_content) > MAX_FILE_CHARS * 3:
                raise Exception("این فایل برای ویرایش مستقیم خیلی بزرگه. یه فایل کوچیک‌تر امتحان کن.")

            new_content = ask_claude_for_edit(original_content, instruction, os.path.basename(filepath))

            if new_content.strip() == original_content.strip():
                self.root.after(0, lambda: self.log("sys", "Claude هیچ تغییری لازم ندید یا فایل از قبل همینطوریه."))
                self.root.after(0, lambda: self.set_face_state("idle"))
                return

            # نشون دادن خلاصه تغییر و گرفتن تأیید کاربر، قبل از هر کاری روی فایل واقعی
            self.root.after(0, lambda: self._confirm_and_apply_edit(filepath, original_content, new_content))

        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.log("err", err))
            self.root.after(0, lambda: self.set_face_state("error"))
            self.root.after(2500, lambda: self.set_face_state("idle"))
        finally:
            self.root.after(0, lambda: self.edit_btn.config(state="normal", text="✏️ ویرایش مستقیم فایل"))

    def _confirm_and_apply_edit(self, filepath, original_content, new_content):
        self.set_face_state("talking")
        self.log("bot", f"یه نسخه ویرایش‌شده آماده‌ست. {len(new_content.splitlines())} خط در نسخه جدید "
                         f"(در مقابل {len(original_content.splitlines())} خط قبلی).")

        preview = new_content[:1500] + ("\n...[ادامه دارد]..." if len(new_content) > 1500 else "")
        confirmed = messagebox.askyesno(
            "تأیید ویرایش فایل",
            f"می‌خوام «{os.path.basename(filepath)}» رو با نسخه جدید جایگزین کنم.\n"
            f"قبلش یه نسخه پشتیبان (.bak) از فایل اصلی ساخته می‌شه.\n\n"
            f"پیش‌نمایش نسخه جدید:\n{'-'*40}\n{preview}\n{'-'*40}\n\n"
            f"مطمئنی می‌خوای اعمال کنم؟",
            parent=self.root
        )

        if not confirmed:
            self.log("sys", "ویرایش لغو شد. هیچ تغییری روی فایل اعمال نشد.")
            self.set_face_state("idle")
            return

        try:
            backup_path = self._backup_file(filepath)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            self.log("sys", f"✅ ویرایش اعمال شد. نسخه پشتیبان: {os.path.basename(backup_path)}")
            self.set_face_state("idle")
        except Exception as e:
            self.log("err", f"نتونستم فایل رو بنویسم: {e}")
            self.set_face_state("error")
            self.root.after(2500, lambda: self.set_face_state("idle"))

    def _backup_file(self, filepath):
        """یه نسخه پشتیبان با timestamp از فایل اصلی می‌سازه، قبل از هر ویرایش."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(filepath)
        backup_path = f"{base}.{timestamp}.bak{ext}"
        shutil.copy2(filepath, backup_path)
        return backup_path

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
        self.set_face_state("thinking")
        threading.Thread(target=self._process, args=(q,), daemon=True).start()

    def _process(self, question):
        try:
            context, relevant = PROJECT.build_context(question)
            answer = ask_claude_code(context, question, self.history)
            self.history.append(("Assistant", answer))

            files_note = "، ".join(relevant) if relevant else "هیچ فایلی"
            self.root.after(0, lambda: self.log("sys", f"فایل‌های بررسی‌شده: {files_note}"))
            self.root.after(0, lambda: self.log("bot", answer))
            self.root.after(0, lambda: self.set_face_state("talking"))
            self.root.after(2500, lambda: self.set_face_state("idle"))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.log("err", err))
            self.root.after(0, lambda: self.set_face_state("error"))
            self.root.after(2500, lambda: self.set_face_state("idle"))
        finally:
            self.processing = False
            self.root.after(0, lambda: self.send_btn.config(state="normal", text="ASK ⚡"))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = CodePilotApp()
    app.run()