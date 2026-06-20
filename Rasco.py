"""
🤖 RASCO - AI Desktop Assistant
JARVIS-style UI | Black & Gold | Powered by Gemini
"""

import os, json, time, subprocess, webbrowser, threading, math, random
import tkinter as tk
from tkinter import scrolledtext
import urllib.request, urllib.error
import pyttsx3, pyautogui, psutil
from datetime import datetime

# ============================================================
GEMINI_API_KEY = "your gemini key"
ASSISTANT_NAME = "RASCO"
CITY = "Tehran"
CITY_FA = "تهران"
# ============================================================

BG     = "#050810"
GOLD   = "#C9A84C"
GOLD_L = "#F0C040"
GOLD_D = "#5a4820"
CYAN   = "#00CFCF"
CYAN_D = "#007a7a"
GREEN  = "#00FF88"
RED    = "#FF4444"
ORANGE = "#FF8C00"
WHITE  = "#E8E8E8"
GRAY   = "#333344"
PANEL  = "#0a0d1a"

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
# GEMINI
# ============================================================
SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, an AI assistant controlling a Windows PC.
User speaks Persian or English. Respond ONLY with JSON:
{{"action":"ACTION","params":{{}},"response":"reply in user language"}}

Actions:
- open_website: {{"url":"https://..."}}
- youtube_search: {{"query":"..."}}
- open_app: {{"app":"chrome/firefox/notepad/calc/explorer/cmd/vlc/spotify/vscode/word/excel"}}
- type_text: {{"text":"..."}}
- press_key: {{"key":"enter/ctrl+c/alt+tab/win+d/etc"}}
- take_screenshot
- search_web: {{"query":"..."}}
- volume_up
- volume_down
- minimize_window
- close_window
- speak_only

Always respond in same language as user. Return ONLY valid JSON, nothing else."""

def ask_gemini(cmd):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = json.dumps({"contents":[{"parts":[{"text": SYSTEM_PROMPT+"\n\nCommand: "+cmd}]}]}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"}, method="POST")
    for i in range(3):
        try:
            with urllib.request.urlopen(req) as r:
                data = json.loads(r.read().decode())
            t = data["candidates"][0]["content"]["parts"][0]["text"]
            t = t.replace("```json","").replace("```","").strip()
            return json.loads(t)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep((i+1)*5)
            else:
                raise
    raise Exception("سرویس Gemini شلوغه. چند ثانیه صبر کن.")

# ============================================================
# ACTIONS
# ============================================================
def execute_action(data):
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
        self.particles = [
            {"a": random.uniform(0,360), "r": random.uniform(40,130),
             "speed": random.uniform(0.15,0.7), "size": random.randint(1,3)}
            for _ in range(70)
        ]
        self.weather_data = {}
        self.processing = False

        self.build_ui()
        self.update_clock()
        self.animate_orb()
        self.update_stats()
        threading.Thread(target=self._load_weather, daemon=True).start()

        self.log("SYS", f"{ASSISTANT_NAME} آماده‌ست. دستورت رو بنویس.")
        self.root.after(500, lambda: speak(f"سلام. من {ASSISTANT_NAME} هستم. آماده‌ام."))

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
                 font=("Courier New",13,"bold"), bg=BG, fg=GOLD_L).pack(side="left", expand=True)
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
        self.canvas = tk.Canvas(p, bg=BG, highlightthickness=0, width=400, height=420)
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
        cx, cy, r = 200, 205, 148

        # Outer glow rings
        for i, (rr, op) in enumerate([(r+24,"33"),(r+14,"55"),(r+6,"88")]):
            c.create_oval(cx-rr,cy-rr,cx+rr,cy+rr, outline=CYAN, width=1)

        # Main ring
        c.create_oval(cx-r,cy-r,cx+r,cy+r, outline=CYAN, width=2)

        # Spinning arcs
        a = self.angle
        c.create_arc(cx-r+10,cy-r+10,cx+r-10,cy+r-10,
                     start=a, extent=120, outline=GOLD_L, width=2, style="arc")
        c.create_arc(cx-r+10,cy-r+10,cx+r-10,cy+r-10,
                     start=a+180, extent=60, outline=GOLD, width=1, style="arc")
        c.create_arc(cx-r+22,cy-r+22,cx+r-22,cy+r-22,
                     start=-a*1.5, extent=80, outline=CYAN_D, width=1, style="arc")

        # Particles
        for pt in self.particles:
            pt["a"] = (pt["a"] + pt["speed"]) % 360
            rad = math.radians(pt["a"])
            px = cx + pt["r"] * math.cos(rad)
            py = cy + pt["r"] * math.sin(rad) * 0.5
            if ((px-cx)/r)**2 + ((py-cy)/r)**2 < 0.92:
                s = pt["size"]
                col = GOLD_L if random.random() < 0.04 else CYAN
                c.create_oval(px-s, py-s, px+s, py+s, fill=col, outline="")

        # Cross hairs
        for dx,dy in [(-r+15,-1),(-r+15+20,-1),(r-35,-1),(r-15,-1)]:
            c.create_line(cx+dx, cy+dy, cx+dx+15, cy+dy, fill=CYAN_D, width=1)
        for dy in [-r+15,-r+35,r-35,r-15]:
            c.create_line(cx, cy+dy, cx, cy+dy+15, fill=CYAN_D, width=1)

        # Center
        c.create_oval(cx-4,cy-4,cx+4,cy+4, fill=GOLD_L, outline=GOLD)

        # Pulse ring (breathing)
        pulse_r = r * (0.6 + 0.06 * math.sin(math.radians(a*2)))
        c.create_oval(cx-pulse_r, cy-pulse_r*0.5,
                      cx+pulse_r, cy+pulse_r*0.5,
                      outline=CYAN_D, width=1)

        self.angle = (self.angle + 0.7) % 720
        self.root.after(28, self.animate_orb)

    # ── CONTROLS ────────────────────────────────────────────
    def _set_live(self):
        self.state_lbl.config(text="● Listening", fg=GREEN)
        self.listen_ind.config(text="LISTENING", fg=GREEN)
        self.online_lbl.config(text="◉ LIVE", fg=GREEN)

    def _set_pause(self):
        self.state_lbl.config(text="⏸ Paused", fg=ORANGE)
        self.listen_ind.config(text="PAUSED", fg=ORANGE)
        self.online_lbl.config(text="◉ PAUSED", fg=ORANGE)

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

        self.processing = True
        self.send_btn.config(state="disabled", text="...")
        self.state_lbl.config(text="◌ Processing...", fg=GOLD)
        self.online_lbl.config(text="◉ THINKING", fg=GOLD)
        threading.Thread(target=self._process, args=(cmd,), daemon=True).start()

    def _process(self, cmd):
        try:
            data = ask_gemini(cmd)
            action = data.get("action","")
            resp = execute_action(data)
            self.root.after(0, lambda: self.log("ACT", f"Action: {action}"))
            self.root.after(0, lambda: self.log("BOT", resp))
            speak(resp)
            self.root.after(0, self._set_live)
            self.root.after(0, lambda: self.online_lbl.config(text="◉ ONLINE", fg=GREEN))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.log("ERR", err))
            self.root.after(0, lambda: self.state_lbl.config(text="● Error", fg=RED))
            self.root.after(0, lambda: self.online_lbl.config(text="◉ ERROR", fg=RED))
        finally:
            self.processing = False
            self.root.after(0, lambda: self.send_btn.config(state="normal", text="SEND ►"))

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = RascoApp()
    app.run()
