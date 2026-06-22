"""
🤖 RASCO - AI Desktop Assistant
JARVIS-style UI | Black & Gold | Powered by AlirezaRg (Pro/Max subscription)
"""

import os, json, time, subprocess, webbrowser, threading, math, random, shutil, tempfile, wave
import tkinter as tk
from tkinter import scrolledtext, messagebox
import urllib.request, urllib.error
import pyttsx3, pyautogui, psutil
from datetime import datetime

# میکروفون اختیاریه - اگه sounddevice/numpy نصب نباشن یا میکروفونی وصل نباشه،
# برنامه بدون قابلیت صوتی کار می‌کنه و فقط دکمه 🎤 غیرفعال می‌مونه.
try:
    import sounddevice as sd
    import numpy as np
    MIC_LIBS_AVAILABLE = True
except ImportError:
    MIC_LIBS_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

# ============================================================
CLAUDE_MODEL = "sonnet"  # alias: 'sonnet', 'opus', or full model name
ASSISTANT_NAME = "RASCO"
CITY = "Tehran"
CITY_FA = "تهران"
# ============================================================

BG     = "#050505"
GOLD   = "#C9A84C"
GOLD_L = "#F0C040"
GOLD_D = "#5a4820"
CYAN   = "#C9A84C"   # kept as alias so existing code paths still render gold accents
CYAN_D = "#7a6020"
GREEN  = "#39ff88"
RED    = "#ff3860"
ORANGE = "#F0C040"
WHITE  = "#f0ece0"
GRAY   = "#3a3a3a"
PANEL  = "#0d0d0d"

# ============================================================
# TTS
# ============================================================
def speak(text):
    def _s():
        try:
            e = pyttsx3.init()
            e.setProperty('rate', 160)
            e.say(text)
            e.runAndWait()
            e.stop()
        except: pass
    threading.Thread(target=_s, daemon=True).start()

# ============================================================
# MICROPHONE (اختیاری - فقط اگه میکروفون وصل و کتابخونه‌ها نصب باشن)
# ============================================================
def find_input_device():
    """
    اول سعی می‌کنه میکروفون پیش‌فرض ویندوز رو پیدا کنه (همونی که توی
    Sound Settings ست شده) - چون وقتی هدفون جدید وصل می‌کنی، معمولاً
    ویندوز خودش پیش‌فرض رو عوض می‌کنه. اگه نشد، اولین میکروفون موجود رو برمی‌گردونه.
    """
    if not MIC_LIBS_AVAILABLE:
        return None
    try:
        default_idx = sd.default.device[0]  # (input, output)
        if default_idx is not None and default_idx >= 0:
            devices = sd.query_devices()
            if devices[default_idx].get("max_input_channels", 0) > 0:
                return default_idx
    except Exception:
        pass
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0:
                return i
    except Exception:
        return None
    return None

def list_input_devices():
    """برای دیباگ: لیست همه میکروفون‌های موجود رو برمی‌گردونه."""
    if not MIC_LIBS_AVAILABLE:
        return []
    try:
        devices = sd.query_devices()
        return [(i, d["name"]) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]
    except Exception:
        return []

def mic_is_available():
    return MIC_LIBS_AVAILABLE and SR_AVAILABLE and find_input_device() is not None

def record_and_transcribe(duration=6, sample_rate=16000):
    """duration ثانیه ضبط می‌کنه و متن فارسی/انگلیسی رو برمی‌گردونه، یا None اگه نشد."""
    if not mic_is_available():
        raise Exception("میکروفونی پیدا نشد یا کتابخونه‌های صوتی نصب نیستن.")

    device_idx = find_input_device()
    audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                         channels=1, dtype=np.int16, device=device_idx)
    sd.wait()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        with wave.open(tmp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())

        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)

        try:
            return recognizer.recognize_google(audio, language="fa-IR")
        except Exception:
            return recognizer.recognize_google(audio, language="en-US")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ============================================================
# WEATHER - بدون API Key (از wttr.in رایگانه)
# ============================================================
def get_weather():
    try:
        url = f"https://wttr.in/{CITY}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.loads(r.read().decode())
        cur = d["current_condition"][0]
        desc = cur["lang_fa"][0]["value"] if cur.get("lang_fa") else cur["weatherDesc"][0]["value"]
        return {
            "temp": cur["temp_C"],
            "feels": cur["FeelsLikeC"],
            "humidity": cur["humidity"],
            "desc": desc,
            "wind": cur["windspeedKmph"],
        }
    except Exception as e:
        return {"temp":"--","feels":"--","humidity":"--","desc":"نامشخص","wind":"--"}

# ============================================================
# CLAUDE CODE (uses your Pro/Max subscription via CLI)
# ============================================================
SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, an AI assistant controlling a Windows PC.
User speaks Persian or English. Respond ONLY with JSON:
{{"action":"ACTION","params":{{}},"response":"reply in user language"}}

Actions:
- open_website: {{"url":"https://..."}}
- youtube_search: {{"query":"..."}}
- open_app: {{"app":"chrome/firefox/notepad/calc/explorer/cmd/vlc/spotify/vscode/word/excel"}}
- open_drive: {{"drive":"C"}} - opens a drive like C:\\ or D:\\ in File Explorer
- open_folder: {{"path":"C:/Users/..."}} - opens a specific folder
- copy_file: {{"source":"C:/path/file.txt","destination":"D:/path/"}}
- move_file: {{"source":"C:/path/file.txt","destination":"D:/path/"}}
- delete_file: {{"path":"C:/path/file.txt"}} - will ask user to confirm first
- open_gmail: {{}} - opens Gmail in Chrome
- type_text: {{"text":"..."}}
- press_key: {{"key":"enter/ctrl+c/alt+tab/win+d/etc"}}
- take_screenshot
- search_web: {{"query":"..."}}
- volume_up
- volume_down
- minimize_window
- close_window
- speak_only

You will also receive recent CONVERSATION HISTORY before each new command. Use it to understand
context, follow-up references ("آن یکی", "همون که گفتم", "it" / "that one"), and to keep a natural,
continuous conversation — not just isolated one-off commands.

Always respond in same language as user. Return ONLY valid JSON, nothing else."""

def find_claude_command():
    """
    سعی می‌کنه مسیر claude.cmd رو پیدا کنه، چون بستگی به اینکه برنامه چطور
    اجرا شده (CMD/VS Code Run/شورتکات)، PATH ممکنه شامل npm global نباشه.
    """
    candidates = [
        "claude",  # اگه توی PATH باشه (حالت ایده‌آل)
        os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
        os.path.expanduser(r"~\AppData\Roaming\npm\claude.cmd"),
    ]
    for candidate in candidates:
        if candidate == "claude":
            # چک کن آیا توی PATH واقعاً موجوده
            found = shutil.which("claude") or shutil.which("claude.cmd")
            if found:
                return found
        elif os.path.exists(candidate):
            return candidate
    # اگه هیچی پیدا نشد، همون "claude" رو برمی‌گردونیم تا پیام خطای روشن بدیم
    return "claude"

CLAUDE_CMD_PATH = find_claude_command()

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rasco_debug.log")

def log_debug(message):
    print(message)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
    except Exception:
        pass

def ask_claude_code(cmd, history=None):
    history_text = ""
    if history:
        for role, msg in history[-10:]:  # فقط ۱۰ پیام آخر برای جلوگیری از سنگین شدن
            history_text += f"\n{role}: {msg}\n"

    full_prompt = (
        SYSTEM_PROMPT
        + "\n\n=== CONVERSATION HISTORY (most recent first context) ===\n" + history_text
        + "\n\n=== NEW COMMAND ===\nUser command: " + cmd
        + "\n\nRespond with ONLY the JSON object, no markdown fences, no extra text."
    )
    log_debug(f"[DEBUG] Using claude command path: {CLAUDE_CMD_PATH!r}")
    log_debug(f"[DEBUG] Sending to claude: {cmd!r}")
    try:
        result = subprocess.run(
            f'"{CLAUDE_CMD_PATH}" -p --model {CLAUDE_MODEL}',
            input=full_prompt,
            capture_output=True, text=True, encoding="utf-8", timeout=90,
            shell=True  # 'claude' is a .ps1/.cmd shim on Windows
        )
    except subprocess.TimeoutExpired:
        log_debug("[DEBUG] TimeoutExpired")
        raise Exception("Claude Code خیلی طول کشید. دوباره امتحان کن.")
    except FileNotFoundError:
        log_debug("[DEBUG] FileNotFoundError")
        raise Exception("دستور 'claude' پیدا نشد. مطمئن شو Claude Code نصب و لاگین شده.")
    except Exception as e:
        log_debug(f"[DEBUG] Unexpected subprocess error: {type(e).__name__}: {e}")
        raise Exception(f"خطای ناشناخته در اجرای claude: {e}")

    log_debug(f"[DEBUG] returncode={result.returncode}")
    log_debug(f"[DEBUG] stdout={result.stdout!r}")
    log_debug(f"[DEBUG] stderr={result.stderr!r}")

    if result.returncode != 0:
        err = (result.stderr or "خطای نامشخص").strip()
        raise Exception(f"Claude Code خطا داد (کد {result.returncode}): {err[:200]}")

    text = (result.stdout or "").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # اگه مدل JSON کامل برنگردوند، یه speak_only میسازیم
        return {"action": "speak_only", "params": {}, "response": text[:300] if text else "متوجه نشدم (جواب خالی بود)."}

# ============================================================
# ACTIONS
# ============================================================
def execute_action(data, confirm_callback=None):
    """confirm_callback(message) -> bool, used to ask user before destructive actions (e.g. delete)."""
    action = data.get("action","")
    p = data.get("params",{})
    resp = data.get("response","انجام شد")
    try:
        if action == "open_website":
            u = p.get("url","https://google.com")
            webbrowser.open(u if u.startswith("http") else "https://"+u)
        elif action == "youtube_search":
            webbrowser.open("https://www.youtube.com/results?search_query="+p.get("query","").replace(" ","+"))
        elif action == "open_app":
            app = p.get("app","").lower()
            mp = {
                "chrome":"chrome","firefox":"firefox","notepad":"notepad",
                "calculator":"calc","calc":"calc","paint":"mspaint",
                "explorer":"explorer","my computer":"explorer","this pc":"explorer",
                "cmd":"cmd","vlc":"vlc","spotify":"spotify",
                "word":"winword","excel":"excel","vscode":"code","vs code":"code",
                "task manager":"taskmgr","taskmgr":"taskmgr",
            }
            subprocess.Popen(mp.get(app, app), shell=True)
        elif action == "open_drive":
            drive = p.get("drive") or p.get("letter") or p.get("path") or "C"
            drive = str(drive).strip().upper().rstrip(":\\/")
            os.startfile(f"{drive}:\\")
        elif action == "open_folder":
            path = p.get("path", os.path.expanduser("~"))
            os.startfile(path)
        elif action == "open_gmail":
            webbrowser.open("https://mail.google.com")
        elif action == "copy_file":
            src = p.get("source") or p.get("src") or p.get("path")
            dst = p.get("destination") or p.get("dest") or p.get("to")
            if not src or not dst:
                resp = "مسیر مبدا یا مقصد مشخص نیست."
            elif not os.path.exists(src):
                resp = f"فایل پیدا نشد: {src}"
            else:
                if os.path.isdir(dst):
                    shutil.copy2(src, dst)
                else:
                    shutil.copy2(src, dst)
                resp = resp or f"کپی شد به {dst}"
        elif action == "move_file":
            src = p.get("source") or p.get("src") or p.get("path")
            dst = p.get("destination") or p.get("dest") or p.get("to")
            if not src or not dst:
                resp = "مسیر مبدا یا مقصد مشخص نیست."
            elif not os.path.exists(src):
                resp = f"فایل پیدا نشد: {src}"
            else:
                shutil.move(src, dst)
                resp = resp or f"منتقل شد به {dst}"
        elif action == "delete_file":
            target = p.get("path") or p.get("source")
            if not target:
                resp = "مسیر فایل مشخص نیست."
            elif not os.path.exists(target):
                resp = f"فایل پیدا نشد: {target}"
            else:
                allowed = True
                if confirm_callback:
                    allowed = confirm_callback(f"مطمئنی می‌خوای حذف کنی؟\n{target}")
                if allowed:
                    if os.path.isdir(target):
                        shutil.rmtree(target)
                    else:
                        os.remove(target)
                    resp = resp or "حذف شد."
                else:
                    resp = "حذف لغو شد."
        elif action == "type_text":
            time.sleep(0.5)
            pyautogui.typewrite(p.get("text",""), interval=0.05)
        elif action == "press_key":
            k = p.get("key","").split("+")
            pyautogui.hotkey(*k) if len(k)>1 else pyautogui.press(k[0])
        elif action == "take_screenshot":
            s = pyautogui.screenshot()
            path = os.path.join(os.path.expanduser("~"),"Desktop",f"rasco_{int(time.time())}.png")
            s.save(path)
            resp += f" — ذخیره روی دسکتاپ"
        elif action == "search_web":
            webbrowser.open("https://www.google.com/search?q="+p.get("query","").replace(" ","+"))
        elif action == "volume_up":
            pyautogui.press('volumeup', presses=5)
        elif action == "volume_down":
            pyautogui.press('volumedown', presses=5)
        elif action == "minimize_window":
            pyautogui.hotkey('win','down')
        elif action == "close_window":
            pyautogui.hotkey('alt','f4')
        elif action == "speak_only":
            pass
        else:
            resp += f" (دستور '{action}' هنوز پشتیبانی نمیشه)"
    except Exception as e:
        resp = f"خطا: {e}"
    return resp

# ============================================================
# MAIN APP
# ============================================================
class RascoApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{ASSISTANT_NAME} — AI Desktop Assistant")
        self.root.geometry("1150x700")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self.angle = 0
        self.weather_data = {}
        self.processing = False

        # حالت چهره: idle / listening / thinking / talking / error
        self.face_state = "idle"
        self.blink_timer = 0
        self.talk_phase = 0

        # تاریخچه مکالمه برای یادسپاری گفتگوهای قبلی
        self.history = []  # list of (role, text) tuples

        self.build_ui()
        self.update_clock()
        self.animate_orb()
        self.update_stats()
        threading.Thread(target=self._load_weather, daemon=True).start()

        self.log("SYS", f"{ASSISTANT_NAME} آماده‌ست. دستورت رو بنویس.")
        if CLAUDE_CMD_PATH == "claude":
            self.log("SYS", "⚠️ مسیر claude پیدا نشد به‌صورت دقیق — اگه جواب نگرفتی، فایل rasco_debug.log رو کنار این برنامه چک کن.")
        else:
            self.log("SYS", f"موتور Claude Code پیدا شد: {CLAUDE_CMD_PATH}")
        if mic_is_available():
            idx = find_input_device()
            devices = list_input_devices()
            device_name = next((name for i, name in devices if i == idx), "نامشخص")
            self.log("SYS", f"میکروفون پیدا شد ({device_name}) — دکمه 🎤 فعاله.")
        else:
            self.log("SYS", "میکروفونی پیدا نشد — فقط با تایپ کار می‌کنه. بعد از وصل کردن میکروفون، برنامه رو دوباره باز کن.")
        self.root.after(500, lambda: self._speak_and_animate(f"سلام. من {ASSISTANT_NAME} هستم. آماده‌ام."))

    def _load_weather(self):
        self.weather_data = get_weather()
        self.root.after(0, self._refresh_weather)
        # هر ۱۵ دقیقه آپدیت
        self.root.after(900000, lambda: threading.Thread(target=self._load_weather, daemon=True).start())

    def _refresh_weather(self):
        w = self.weather_data
        self.temp_lbl.config(text=f"{w.get('temp','--')}°C")
        self.wdesc_lbl.config(text=str(w.get('desc','نامشخص')))
        self.humid_lbl.config(text=f"رطوبت: {w.get('humidity','--')}%  |  باد: {w.get('wind','--')} km/h")

    # ────────────────────────────────────────────────────────
    def build_ui(self):
        # TOP BAR
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x")
        tk.Frame(top, bg=GOLD, height=2).pack(fill="x")
        bar = tk.Frame(top, bg=BG, pady=5)
        bar.pack(fill="x", padx=16)
        tk.Label(bar, text="SYSTEM SETTINGS  |  VOICE CORE: Windows",
                 font=("Courier New",7), bg=BG, fg=GOLD_D).pack(side="left")
        tk.Label(bar, text=ASSISTANT_NAME,
                 font=("Courier New",30,"bold"), bg=BG, fg=GOLD_L).pack(side="left", expand=True)
        tk.Label(bar, text="Just A Rather Clever Operating System",
                 font=("Courier New",7), bg=BG, fg=GOLD_D).pack(side="left", expand=True)
        self.online_lbl = tk.Label(bar, text="◉ ONLINE",
                 font=("Courier New",8,"bold"), bg=BG, fg=GREEN)
        self.online_lbl.pack(side="right")
        tk.Frame(top, bg=CYAN_D, height=1).pack(fill="x")

        # MAIN 3-COLUMN
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=6, pady=4)

        left = tk.Frame(main, bg=BG, width=230)
        left.pack(side="left", fill="y", padx=(0,5))
        left.pack_propagate(False)

        center = tk.Frame(main, bg=BG)
        center.pack(side="left", fill="both", expand=True)

        right = tk.Frame(main, bg=BG, width=295)
        right.pack(side="left", fill="y", padx=(5,0))
        right.pack_propagate(False)

        self._build_left(left)
        self._build_center(center)
        self._build_right(right)

    # ── LEFT ────────────────────────────────────────────────
    def _panel(self, parent, title):
        f = tk.Frame(parent, bg=PANEL)
        f.pack(fill="x", pady=3, padx=2)
        tk.Frame(f, bg=CYAN_D, height=1).pack(fill="x")
        tk.Label(f, text=title, font=("Courier New",7,"bold"),
                 bg=PANEL, fg=CYAN, anchor="w", padx=8, pady=3).pack(fill="x")
        return f

    def _build_left(self, p):
        # TIME
        tf = self._panel(p, "TIME")
        self.clock_lbl = tk.Label(tf, text="00:00", font=("Courier New",30,"bold"),
                                   bg=PANEL, fg=WHITE, anchor="w", padx=10)
        self.clock_lbl.pack(fill="x")
        self.date_lbl = tk.Label(tf, text="", font=("Courier New",8),
                                  bg=PANEL, fg=GOLD, anchor="w", padx=10, pady=1)
        self.date_lbl.pack(fill="x")
        self.day_lbl = tk.Label(tf, text="", font=("Courier New",8),
                                 bg=PANEL, fg=GRAY, anchor="w", padx=10, pady=2)
        self.day_lbl.pack(fill="x")

        # WEATHER
        wf = self._panel(p, f"WEATHER · {CITY_FA}")
        self.temp_lbl = tk.Label(wf, text="--°C", font=("Courier New",24,"bold"),
                                  bg=PANEL, fg=CYAN, anchor="w", padx=10)
        self.temp_lbl.pack(fill="x")
        self.wdesc_lbl = tk.Label(wf, text="بارگذاری...", font=("Courier New",8),
                                   bg=PANEL, fg=WHITE, anchor="w", padx=10)
        self.wdesc_lbl.pack(fill="x")
        self.humid_lbl = tk.Label(wf, text="", font=("Courier New",7),
                                   bg=PANEL, fg=GRAY, anchor="w", padx=10, pady=3)
        self.humid_lbl.pack(fill="x")

        # SYSTEM STATUS
        sf = self._panel(p, "SYSTEM STATUS")
        self.stat_labels = {}
        for key in ["CPU","RAM","DISK"]:
            row = tk.Frame(sf, bg=PANEL)
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=key, font=("Courier New",7), bg=PANEL,
                     fg=GRAY, width=5, anchor="w").pack(side="left")
            bar_bg = tk.Canvas(row, bg="#0d1020", height=6, width=130,
                               highlightthickness=0)
            bar_bg.pack(side="left", padx=4)
            lbl = tk.Label(row, text="0%", font=("Courier New",7),
                           bg=PANEL, fg=GOLD, width=4)
            lbl.pack(side="left")
            self.stat_labels[key] = (bar_bg, lbl)

        # NETWORK
        nf = self._panel(p, "NETWORK")
        self.net_lbl = tk.Label(nf, text="▲ 0 KB/s  ▼ 0 KB/s",
                                 font=("Courier New",8), bg=PANEL, fg=GREEN,
                                 anchor="w", padx=10, pady=4)
        self.net_lbl.pack(fill="x")
        self._net_old = psutil.net_io_counters()
        self._update_net()

    def _update_net(self):
        try:
            new = psutil.net_io_counters()
            old = self._net_old
            up = (new.bytes_sent - old.bytes_sent) // 1024
            dn = (new.bytes_recv - old.bytes_recv) // 1024
            self._net_old = new
            self.net_lbl.config(text=f"▲ {up} KB/s   ▼ {dn} KB/s")
        except: pass
        self.root.after(2000, self._update_net)

    # ── CENTER ──────────────────────────────────────────────
    def _build_center(self, p):
        self.canvas = tk.Canvas(p, bg=BG, highlightthickness=0, width=420, height=460)
        self.canvas.pack(expand=True)

        tk.Label(p, text=ASSISTANT_NAME, font=("Courier New",14,"bold"),
                 bg=BG, fg=GOLD_L).pack()
        self.state_lbl = tk.Label(p, text="● Standby",
                 font=("Courier New",9), bg=BG, fg=GOLD_D)
        self.state_lbl.pack(pady=2)

        btn_row = tk.Frame(p, bg=BG)
        btn_row.pack(pady=8)
        def mkbtn(txt, col, cmd):
            tk.Button(btn_row, text=txt, font=("Courier New",8,"bold"),
                      bg=BG, fg=col, activebackground=BG, activeforeground=col,
                      relief="flat", bd=0, padx=14, pady=5, cursor="hand2",
                      highlightthickness=1, highlightbackground=col,
                      command=cmd).pack(side="left", padx=7)
        mkbtn("◉ LIVE",     GREEN,  self._set_live)
        mkbtn("⏸ PAUSE",   ORANGE, self._set_pause)
        mkbtn("⏻ SHUTDOWN", RED,   self._shutdown)

    # ── RIGHT ───────────────────────────────────────────────
    def _build_right(self, p):
        tk.Frame(p, bg=CYAN_D, height=1).pack(fill="x")
        hdr = tk.Frame(p, bg=PANEL, pady=5)
        hdr.pack(fill="x")
        tk.Label(hdr, text="CONVERSATION", font=("Courier New",8,"bold"),
                 bg=PANEL, fg=CYAN, padx=8).pack(side="left")
        self.listen_ind = tk.Label(hdr, text="STANDBY",
                 font=("Courier New",7,"bold"), bg=PANEL, fg=GOLD_D)
        self.listen_ind.pack(side="right", padx=8)
        tk.Frame(p, bg=CYAN_D, height=1).pack(fill="x")

        self.chat = scrolledtext.ScrolledText(
            p, bg=PANEL, fg=WHITE, font=("Courier New",9),
            bd=0, relief="flat", padx=8, pady=8,
            wrap=tk.WORD, state="disabled", cursor="arrow"
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("SYS", foreground=ORANGE)
        self.chat.tag_config("YOU", foreground=GOLD_L, font=("Courier New",9,"bold"))
        self.chat.tag_config("BOT", foreground=WHITE)
        self.chat.tag_config("ACT", foreground=GREEN, font=("Courier New",8))
        self.chat.tag_config("ERR", foreground=RED)

        tk.Frame(p, bg=GOLD_D, height=1).pack(fill="x", pady=(4,0))
        inp_row = tk.Frame(p, bg=PANEL, pady=6, padx=6)
        inp_row.pack(fill="x")
        self.input_var = tk.StringVar()
        inp = tk.Entry(inp_row, textvariable=self.input_var,
                       font=("Courier New",10), bg="#0d1020", fg=WHITE,
                       insertbackground=GOLD, relief="flat", bd=6)
        inp.pack(side="left", fill="x", expand=True, ipady=5)
        inp.bind("<Return>", self.send)
        inp.focus()

        self.mic_btn = tk.Button(inp_row, text="🎤",
                       font=("Courier New",10,"bold"), bg="#1e1e1e", fg=GRAY,
                       activebackground=GOLD_D, relief="flat", bd=0,
                       padx=8, pady=5, cursor="hand2", command=self.toggle_mic)
        self.mic_btn.pack(side="left", padx=(4,0))
        self._update_mic_button_state()

        self.send_btn = tk.Button(inp_row, text="SEND ►",
                       font=("Courier New",8,"bold"), bg=GOLD, fg=BG,
                       activebackground=GOLD_L, relief="flat", bd=0,
                       padx=10, pady=5, cursor="hand2", command=self.send)
        self.send_btn.pack(side="left", padx=(4,0))

    # ── CLOCK ───────────────────────────────────────────────
    def update_clock(self):
        now = datetime.now()
        self.clock_lbl.config(text=now.strftime("%H:%M"))
        self.date_lbl.config(text=now.strftime("%d %b %Y").upper())
        days_fa = ["دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه"]
        self.day_lbl.config(text=days_fa[now.weekday()])
        self.root.after(1000, self.update_clock)

    # ── STATS ───────────────────────────────────────────────
    def update_stats(self):
        vals = {
            "CPU":  psutil.cpu_percent(interval=None),
            "RAM":  psutil.virtual_memory().percent,
            "DISK": psutil.disk_usage('/').percent,
        }
        for key,(bar_bg, lbl) in self.stat_labels.items():
            v = vals[key]
            w = bar_bg.winfo_width()
            if w < 2: w = 130
            fill_w = max(2, int(w * v / 100))
            color = RED if v > 80 else (ORANGE if v > 50 else CYAN)
            bar_bg.delete("all")
            bar_bg.create_rectangle(0, 0, fill_w, 6, fill=color, outline="")
            lbl.config(text=f"{int(v)}%")
        self.root.after(2000, self.update_stats)

    # ── ORB ─────────────────────────────────────────────────
    def animate_orb(self):
        c = self.canvas
        c.delete("all")
        cx, cy = 210, 230

        bounce = math.sin(math.radians(self.angle*2)) * 2  # idle bob

        # ── COOL ROBOTIC DOBERMAN ─────────────────────────
        FUR       = "#1c1c1c"
        FUR_D     = "#000000"
        TAN       = "#7a4a22"
        METAL     = "#555555"
        SHADE_LENS= "#0c0c0c"
        SHADE_RIM = GOLD

        hx, hy = cx, cy + bounce

        if self.face_state == "listening":
            tilt = 8
        elif self.face_state == "thinking":
            tilt = -5
        elif self.face_state == "error":
            tilt = -10
        else:
            tilt = 0

        # ── HEAD (skull) — wide rounded oval ──
        head_w, head_h = 95, 80
        head_cy = hy - 20
        c.create_oval(hx-head_w, head_cy-head_h, hx+head_w, head_cy+head_h,
                      fill=FUR, outline=METAL, width=2)

        # ── EARS — solid wide triangles, clearly attached to top of skull ──
        for side in (-1, 1):
            base_x = hx + side*head_w*0.55
            base_y = head_cy - head_h*0.55
            tip_x  = hx + side*(head_w*0.85 + tilt*0.4)
            tip_y  = head_cy - head_h*1.55
            c.create_polygon(
                base_x, base_y - 15,
                base_x + side*36, base_y + 35,
                tip_x, tip_y,
                fill=FUR, outline=METAL, width=2
            )

        # tan eyebrow markings (doberman rust spots above the eyes)
        for side in (-1, 1):
            ex = hx + side*head_w*0.42
            c.create_oval(ex-8, head_cy-head_h*0.30-6, ex+8, head_cy-head_h*0.30+6,
                         fill=TAN, outline="")

        # ── MUZZLE — rectangle that clearly overlaps the lower head ──
        muz_w = head_w*0.72
        muz_top = head_cy + head_h*0.55
        muz_bottom = head_cy + head_h*1.85
        c.create_rectangle(hx-muz_w, muz_top, hx+muz_w, muz_bottom,
                           fill=FUR, outline=METAL, width=2)
        # round the bottom corners visually with small arcs
        c.create_oval(hx-muz_w, muz_bottom-30, hx-muz_w+30, muz_bottom+10, fill=FUR, outline="")
        c.create_oval(hx+muz_w-30, muz_bottom-30, hx+muz_w, muz_bottom+10, fill=FUR, outline="")
        c.create_oval(hx-muz_w, muz_bottom-30, hx-muz_w+30, muz_bottom+10, outline=METAL, width=2)
        c.create_oval(hx+muz_w-30, muz_bottom-30, hx+muz_w, muz_bottom+10, outline=METAL, width=2)
        c.create_line(hx-muz_w+2, muz_bottom, hx+muz_w-2, muz_bottom, fill=METAL, width=2)

        # tan markings on lower sides of the muzzle (classic doberman pattern)
        for side in (-1, 1):
            c.create_rectangle(
                hx+side*muz_w*0.55, muz_top+8,
                hx+side*muz_w*0.95, muz_bottom-4,
                fill=TAN, outline=""
            )

        # nose at the bottom of the muzzle
        nose_y = muz_bottom - 10
        c.create_oval(hx-13, nose_y-10, hx+13, nose_y+8, fill=FUR_D, outline=GOLD_D, width=1)
        c.create_oval(hx-4, nose_y-7, hx+2, nose_y-2, fill=GOLD_L, outline="")  # nose shine

        # ── SUNGLASSES — sit right at the head/muzzle junction ──
        lens_w, lens_h = 32, 18
        bridge_y = muz_top - 8
        eye_dx = head_w*0.40
        for side in (-1, 1):
            ex = hx + side*eye_dx
            c.create_oval(ex-lens_w/2, bridge_y-lens_h/2, ex+lens_w/2, bridge_y+lens_h/2,
                         fill=SHADE_LENS, outline=SHADE_RIM, width=3)
            c.create_line(ex-lens_w/2+6, bridge_y-lens_h/2+5, ex-2, bridge_y-2,
                         fill=GOLD_L, width=2)
        c.create_line(hx-eye_dx+lens_w/2-2, bridge_y, hx+eye_dx-lens_w/2+2, bridge_y,
                     fill=SHADE_RIM, width=3)
        for side in (-1, 1):
            ex = hx + side*eye_dx
            c.create_line(ex+side*lens_w/2, bridge_y, ex+side*(lens_w/2+16), bridge_y-2,
                         fill=SHADE_RIM, width=2)

        # eyebrow ridge glow above shades — shows mood since eyes are hidden
        self.blink_timer += 1
        brow_y = bridge_y - lens_h/2 - 10
        if self.face_state == "error":
            brow_tilt = 6
        elif self.face_state == "thinking":
            brow_tilt = 4
        else:
            brow_tilt = 0
        for side in (-1, 1):
            ex = hx + side*eye_dx
            glow = RED if self.face_state == "error" else GOLD
            c.create_line(ex-10, brow_y + brow_tilt*side, ex+10, brow_y - brow_tilt*side,
                         fill=glow, width=2, capstyle="round")

        # ── MOUTH — on the muzzle, below the nose level reference ──
        mouth_y = muz_top + muz_w*0.55
        mouth_w = 22
        if self.face_state == "talking":
            self.talk_phase += 1
            open_amt = 6 + 6 * abs(math.sin(self.talk_phase * 0.6))
            c.create_oval(hx-mouth_w/2.2, mouth_y-open_amt/2, hx+mouth_w/2.2, mouth_y+open_amt/2,
                         fill=FUR_D, outline=GOLD_D, width=2)
        elif self.face_state == "listening":
            c.create_oval(hx-mouth_w/3, mouth_y-5, hx+mouth_w/3, mouth_y+5,
                         fill=FUR_D, outline=GOLD_D, width=2)
        elif self.face_state == "thinking":
            c.create_line(hx-mouth_w/2.2, mouth_y, hx+mouth_w/2.2, mouth_y-3,
                         fill=GOLD_D, width=3, capstyle="round")
        elif self.face_state == "error":
            c.create_line(hx-mouth_w/2.2, mouth_y+5, hx+mouth_w/2.2, mouth_y-5,
                         fill=RED, width=3, capstyle="round")
        else:  # idle — cool one-sided smirk
            c.create_line(hx-mouth_w/2, mouth_y, hx, mouth_y+3, fill=GOLD_D, width=3, capstyle="round")
            c.create_line(hx, mouth_y+3, hx+mouth_w/2, mouth_y-6, fill=GOLD_D, width=3, capstyle="round")

        # whisker hints
        for side in (-1, 1):
            for i in range(2):
                wy = mouth_y - 10 + i*9
                c.create_line(hx+side*muz_w*0.7, wy, hx+side*(muz_w*0.7+16), wy-3,
                             fill=METAL, width=1)

        # ── GOLD COLLAR — below the chin ──
        collar_y = muz_bottom + 22
        c.create_arc(hx-head_w*1.2, collar_y-22, hx+head_w*1.2, collar_y+30,
                    start=200, extent=140, outline=GOLD, width=9, style="arc")
        c.create_oval(hx-10, collar_y+18, hx+10, collar_y+38, fill=GOLD_L, outline=GOLD_D, width=2)

        # state label badge below
        state_labels = {
            "idle": ("IDLE", GOLD_D), "listening": ("LISTENING", GREEN),
            "thinking": ("THINKING", GOLD), "talking": ("TALKING", CYAN),
            "error": ("ERROR", RED)
        }
        lbl, lbl_col = state_labels.get(self.face_state, ("IDLE", GOLD_D))
        c.create_text(cx, collar_y + 54, text=lbl, fill=lbl_col,
                      font=("Courier New", 9, "bold"))

        self.angle = (self.angle + 0.7) % 720
        self.root.after(40, self.animate_orb)

    def set_face_state(self, state):
        """state: idle / listening / thinking / talking / error"""
        self.face_state = state



    # ── CONTROLS ────────────────────────────────────────────
    def _set_live(self):
        self.state_lbl.config(text="● Listening", fg=GREEN)
        self.listen_ind.config(text="LISTENING", fg=GREEN)
        self.online_lbl.config(text="◉ LIVE", fg=GREEN)
        self.set_face_state("idle")

    def _set_pause(self):
        self.state_lbl.config(text="⏸ Paused", fg=ORANGE)
        self.listen_ind.config(text="PAUSED", fg=ORANGE)
        self.online_lbl.config(text="◉ PAUSED", fg=ORANGE)
        self.set_face_state("idle")

    def _shutdown(self):
        speak("در حال خاموش شدن.")
        self.root.after(1200, self.root.destroy)

    # ── LOG ─────────────────────────────────────────────────
    def log(self, role, text):
        self.chat.config(state="normal")
        prefix = {"SYS":"[SYS]","YOU":"[YOU]","BOT":f"[{ASSISTANT_NAME}]",
                  "ACT":"  ⚡","ERR":"  ✗"}.get(role, role)
        self.chat.insert("end", f"{prefix} {text}\n", role)
        self.chat.config(state="disabled")
        self.chat.see("end")

    # ── SEND ────────────────────────────────────────────────
    def _update_mic_button_state(self):
        if mic_is_available():
            self.mic_btn.config(state="normal", fg=GOLD, cursor="hand2")
        else:
            self.mic_btn.config(state="disabled", fg=GRAY, cursor="arrow")

    def toggle_mic(self):
        if not mic_is_available():
            self.log("SYS", "میکروفونی پیدا نشد. وقتی وصل کردی، دوباره برنامه رو باز کن.")
            return
        if self.processing:
            return
        self.mic_btn.config(state="disabled", text="●", fg=RED)
        self.set_face_state("listening")
        self.log("SYS", "در حال ضبط صدا... (۶ ثانیه)")
        threading.Thread(target=self._record_thread, daemon=True).start()

    def _record_thread(self):
        try:
            text = record_and_transcribe(duration=6)
            if text:
                self.root.after(0, lambda: self._on_transcribed(text))
            else:
                self.root.after(0, lambda: self.log("ERR", "چیزی شنیده نشد."))
                self.root.after(0, lambda: self.set_face_state("error"))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.log("ERR", f"خطای میکروفون: {err}"))
            self.root.after(0, lambda: self.set_face_state("error"))
        finally:
            self.root.after(0, lambda: self.mic_btn.config(state="normal", text="🎤", fg=GOLD))

    def _on_transcribed(self, text):
        self.input_var.set(text)
        self.send()

    def send(self, event=None):
        cmd = self.input_var.get().strip()
        if not cmd or self.processing: return
        self.input_var.set("")
        self.log("YOU", cmd)

        if any(w in cmd.lower() for w in ["exit","quit","خروج","خداحافظ"]):
            self.log("BOT", "خداحافظ! 👋")
            speak("خداحافظ!")
            self.root.after(1500, self.root.destroy)
            return

        if cmd.strip() in ["پاک کن حافظه", "حافظه رو پاک کن", "clear memory", "forget everything"]:
            self.history = []
            self.log("SYS", "حافظه گفتگو پاک شد. از اول شروع می‌کنیم.")
            return

        self.processing = True
        self.send_btn.config(state="disabled", text="...")
        self.state_lbl.config(text="◌ Processing...", fg=GOLD)
        self.online_lbl.config(text="◉ THINKING", fg=GOLD)
        self.set_face_state("thinking")
        threading.Thread(target=self._process, args=(cmd,), daemon=True).start()

    def _confirm_dialog(self, message):
        """Thread-safe yes/no confirmation, callable from background thread."""
        result = {"value": False}
        done = threading.Event()

        def ask():
            result["value"] = messagebox.askyesno("تأیید عملیات", message)
            done.set()

        self.root.after(0, ask)
        done.wait(timeout=30)
        return result["value"]

    def _speak_and_animate(self, text):
        """Speak while showing a talking face, then return to idle."""
        self.set_face_state("talking")
        speak(text)
        # تخمین تقریبی مدت گفتار بر اساس تعداد کاراکتر، برای برگشت به حالت idle
        approx_ms = min(8000, max(1200, len(text) * 70))
        self.root.after(approx_ms, lambda: self.set_face_state("idle"))

    def _process(self, cmd):
        try:
            self._process_inner(cmd)
        except Exception as e:
            # safety net: guarantee something always shows in the UI
            err = f"خطای داخلی: {e}"
            print(f"[DEBUG] _process top-level exception: {e}")
            self.root.after(0, lambda: self.log("ERR", err))
            self.root.after(0, lambda: self.online_lbl.config(text="◉ ERROR", fg=RED))
            self.root.after(0, lambda: self.set_face_state("error"))
        finally:
            self.processing = False
            self.root.after(0, lambda: self.send_btn.config(state="normal", text="SEND ►"))

    def _process_inner(self, cmd):
        try:
            data = ask_claude_code(cmd, history=self.history)
            action = data.get("action","")
            resp = execute_action(data, confirm_callback=self._confirm_dialog)
            self.history.append(("User", cmd))
            self.history.append(("Assistant", resp))
            self.root.after(0, lambda: self.log("ACT", f"Action: {action}"))
            self.root.after(0, lambda: self.log("BOT", resp))
            self.root.after(0, lambda: self._speak_and_animate(resp))
            self.root.after(0, lambda: self.online_lbl.config(text="◉ ONLINE", fg=GREEN))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.log("ERR", err))
            self.root.after(0, lambda: self.state_lbl.config(text="● Error", fg=RED))
            self.root.after(0, lambda: self.online_lbl.config(text="◉ ERROR", fg=RED))
            self.root.after(0, lambda: self.set_face_state("error"))

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = RascoApp()
    app.run()