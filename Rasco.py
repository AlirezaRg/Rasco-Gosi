"""
RASCO - AI Desktop Assistant
JARVIS-style UI | Black & Gold | Powered by Claude Code
"""

import os, json, time, subprocess, webbrowser, threading, math, random, shutil, tempfile, wave
import tkinter as tk
from tkinter import scrolledtext, messagebox
import urllib.request, urllib.error
import pyttsx3, pyautogui, psutil
from datetime import datetime

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

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# ============================================================
CLAUDE_MODEL   = "sonnet"
ASSISTANT_NAME = "RASCO"
CITY           = "Tehran"
CITY_FA        = "تهران"
# ============================================================

BG     = "#030303"
GOLD   = "#C9A84C"
GOLD_L = "#F0C040"
GOLD_D = "#5a4820"
GOLD_G = "#8a6e2a"
CYAN   = "#C9A84C"
CYAN_D = "#7a6020"
GREEN  = "#00ff88"
RED    = "#ff2255"
ORANGE = "#F0C040"
WHITE  = "#f0ece0"
GRAY   = "#3a3a3a"
PANEL  = "#080808"
DARK   = "#0a0a0a"

# ============================================================
# BROWSER ENGINE
# ============================================================
_browser = None
_browser_lock = threading.Lock()

def get_browser():
    global _browser
    with _browser_lock:
        if _browser is not None:
            try:
                _ = _browser.title
                return _browser
            except Exception:
                _browser = None
        if not SELENIUM_AVAILABLE:
            raise Exception("Selenium نصب نیست.")
        opts = Options()
        opts.add_argument("--start-maximized")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("--disable-blink-features=AutomationControlled")
        try:
            service = Service(ChromeDriverManager().install())
            _browser = webdriver.Chrome(service=service, options=opts)
        except Exception as e:
            raise Exception(f"Chrome باز نشد: {e}")
        return _browser

def browser_navigate(url):
    b = get_browser()
    b.get(url)
    return b

def browser_click_text(text, timeout=8):
    b = get_browser()
    try:
        el = WebDriverWait(b, timeout).until(
            EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(),'{text}')]"))
        )
        el.click()
        return True
    except Exception:
        return False

def browser_click_selector(selector, timeout=8):
    b = get_browser()
    try:
        el = WebDriverWait(b, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        el.click()
        return True
    except Exception:
        return False

def browser_type(selector, text, timeout=8):
    b = get_browser()
    try:
        el = WebDriverWait(b, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        el.clear()
        el.send_keys(text)
        return True
    except Exception:
        return False

def browser_js(script):
    b = get_browser()
    return b.execute_script(script)

def youtube_play(query):
    """یوتیوب رو باز می‌کنه، سرچ می‌کنه و اولین ویدیو رو پلی می‌کنه."""
    b = browser_navigate(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
    time.sleep(2)
    try:
        first = WebDriverWait(b, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "ytd-video-renderer a#video-title"))
        )
        first.click()
        return "پلی شد."
    except Exception:
        return "ویدیو پیدا نشد، ولی یوتیوب باز شد."

def spotify_play(query):
    b = browser_navigate("https://open.spotify.com")
    time.sleep(3)
    try:
        search_btn = WebDriverWait(b, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/search']"))
        )
        search_btn.click()
        time.sleep(1)
        inp = WebDriverWait(b, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='search-input']"))
        )
        inp.send_keys(query)
        time.sleep(2)
        first_song = WebDriverWait(b, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div[data-testid='tracklist-row']"))
        )
        play_btn = first_song.find_element(By.CSS_SELECTOR, "button[data-testid='play-button']")
        play_btn.click()
        return f"آهنگ {query} در Spotify پلی شد."
    except Exception:
        return f"Spotify باز شد، آهنگ رو خودت انتخاب کن."

# ============================================================
# TTS
# ============================================================
def speak(text):
    def _s():
        try:
            e = pyttsx3.init()
            e.setProperty('rate', 165)
            e.say(text)
            e.runAndWait()
            e.stop()
        except: pass
    threading.Thread(target=_s, daemon=True).start()

# ============================================================
# MICROPHONE
# ============================================================
def find_input_device():
    if not MIC_LIBS_AVAILABLE: return None
    try:
        default_idx = sd.default.device[0]
        if default_idx is not None and default_idx >= 0:
            devices = sd.query_devices()
            if devices[default_idx].get("max_input_channels", 0) > 0:
                return default_idx
    except Exception: pass
    try:
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                return i
    except Exception: pass
    return None

def mic_is_available():
    return MIC_LIBS_AVAILABLE and SR_AVAILABLE and find_input_device() is not None

def record_and_transcribe(duration=6, sample_rate=16000):
    if not mic_is_available():
        raise Exception("میکروفونی پیدا نشد.")
    device_idx = find_input_device()
    audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                        channels=1, dtype=np.int16, device=device_idx)
    sd.wait()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        with wave.open(tmp_path, 'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2)
            wf.setframerate(sample_rate); wf.writeframes(audio_data.tobytes())
        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio, language="fa-IR")
        except Exception:
            return recognizer.recognize_google(audio, language="en-US")
    finally:
        if tmp_path and os.path.exists(tmp_path): os.unlink(tmp_path)

# ============================================================
# WEATHER
# ============================================================
def get_weather():
    try:
        url = f"https://wttr.in/{CITY}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.loads(r.read().decode())
        cur = d["current_condition"][0]
        desc = cur["lang_fa"][0]["value"] if cur.get("lang_fa") else cur["weatherDesc"][0]["value"]
        return {"temp": cur["temp_C"], "feels": cur["FeelsLikeC"],
                "humidity": cur["humidity"], "desc": desc, "wind": cur["windspeedKmph"]}
    except Exception:
        return {"temp":"--","feels":"--","humidity":"--","desc":"نامشخص","wind":"--"}

# ============================================================
# CLAUDE
# ============================================================
SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, an AI desktop assistant controlling a Windows PC and Chrome browser.
User speaks Persian or English. Respond ONLY with JSON:
{{"action":"ACTION","params":{{}},"response":"reply in user language"}}

Actions:
- youtube_play: {{"query":"..."}} — opens YouTube and plays first result video
- youtube_search: {{"query":"..."}} — opens YouTube search results
- spotify_play: {{"query":"..."}} — opens Spotify and plays song
- browser_open: {{"url":"https://..."}} — opens any URL in Chrome
- browser_click: {{"selector":"css_selector OR text_to_click","type":"css|text"}}
- browser_type: {{"selector":"css_selector","text":"..."}}
- browser_scroll: {{"direction":"up|down","amount":3}}
- browser_js: {{"script":"javascript code"}}
- google_search: {{"query":"..."}} — Google search in browser
- open_app: {{"app":"chrome/notepad/calc/explorer/cmd/vlc/spotify/vscode/word/excel/taskmgr"}}
- open_drive: {{"drive":"C"}}
- open_folder: {{"path":"C:/Users/..."}}
- copy_file: {{"source":"...","destination":"..."}}
- move_file: {{"source":"...","destination":"..."}}
- delete_file: {{"path":"..."}}
- type_text: {{"text":"..."}} — types text at current cursor position
- press_key: {{"key":"enter/ctrl+c/alt+tab/win+d/etc"}}
- take_screenshot
- volume_up
- volume_down
- minimize_window
- close_window
- speak_only — just respond in conversation

IMPORTANT RULES:
- For YouTube video requests → always use youtube_play (NOT youtube_search)
- For Spotify song requests → use spotify_play
- For any website → use browser_open
- Always respond in same language as the user
- Return ONLY valid JSON, no markdown, no extra text
- Use CONVERSATION HISTORY for context and follow-up references
"""

def find_claude_command():
    candidates = [
        "claude",
        os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
        os.path.expanduser(r"~\AppData\Roaming\npm\claude.cmd"),
    ]
    for c in candidates:
        if c == "claude":
            found = shutil.which("claude") or shutil.which("claude.cmd")
            if found: return found
        elif os.path.exists(c):
            return c
    return "claude"

CLAUDE_CMD_PATH = find_claude_command()
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rasco_debug.log")

def log_debug(msg):
    print(msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception: pass

def ask_claude(cmd, history=None):
    history_text = ""
    if history:
        for role, msg in history[-10:]:
            history_text += f"\n{role}: {msg}\n"
    full_prompt = (
        SYSTEM_PROMPT
        + "\n\n=== CONVERSATION HISTORY ===\n" + history_text
        + "\n\n=== NEW COMMAND ===\nUser: " + cmd
        + "\n\nRespond with ONLY the JSON object."
    )
    log_debug(f"[DEBUG] cmd={cmd!r}")
    try:
        result = subprocess.run(
            f'"{CLAUDE_CMD_PATH}" -p --model {CLAUDE_MODEL}',
            input=full_prompt, capture_output=True, text=True,
            encoding="utf-8", timeout=90, shell=True
        )
    except subprocess.TimeoutExpired:
        raise Exception("Claude Code خیلی طول کشید.")
    except FileNotFoundError:
        raise Exception("دستور 'claude' پیدا نشد.")
    except Exception as e:
        raise Exception(f"خطا در اجرای claude: {e}")

    log_debug(f"[DEBUG] rc={result.returncode} out={result.stdout[:200]!r}")
    if result.returncode != 0:
        raise Exception(f"Claude خطا داد: {(result.stderr or '').strip()[:200]}")

    text = (result.stdout or "").strip()
    text = text.replace("```json","").replace("```","").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"action":"speak_only","params":{},"response": text[:300] or "متوجه نشدم."}

# ============================================================
# ACTIONS
# ============================================================
def execute_action(data, confirm_callback=None):
    action = data.get("action","")
    p      = data.get("params",{})
    resp   = data.get("response","انجام شد.")
    try:
        if action == "youtube_play":
            result = youtube_play(p.get("query",""))
            resp = resp + " " + result

        elif action == "youtube_search":
            q = p.get("query","")
            browser_navigate("https://www.youtube.com/results?search_query=" + q.replace(" ","+"))

        elif action == "spotify_play":
            result = spotify_play(p.get("query",""))
            resp = result

        elif action == "browser_open":
            url = p.get("url","https://google.com")
            if not url.startswith("http"): url = "https://" + url
            browser_navigate(url)

        elif action == "browser_click":
            t = p.get("type","css")
            if t == "text":
                browser_click_text(p.get("selector",""))
            else:
                browser_click_selector(p.get("selector",""))

        elif action == "browser_type":
            browser_type(p.get("selector","body"), p.get("text",""))

        elif action == "browser_scroll":
            direction = p.get("direction","down")
            amount    = int(p.get("amount", 3)) * 300
            if direction == "up": amount = -amount
            browser_js(f"window.scrollBy(0, {amount})")

        elif action == "browser_js":
            browser_js(p.get("script",""))

        elif action == "google_search":
            q = p.get("query","")
            browser_navigate("https://www.google.com/search?q=" + q.replace(" ","+"))

        elif action == "open_app":
            app = p.get("app","").lower()
            mp = {"chrome":"chrome","firefox":"firefox","notepad":"notepad",
                  "calculator":"calc","calc":"calc","paint":"mspaint",
                  "explorer":"explorer","cmd":"cmd","vlc":"vlc","spotify":"spotify",
                  "word":"winword","excel":"excel","vscode":"code","vs code":"code",
                  "task manager":"taskmgr","taskmgr":"taskmgr"}
            subprocess.Popen(mp.get(app,app), shell=True)

        elif action == "open_drive":
            drive = str(p.get("drive","C")).strip().upper().rstrip(":\\/")
            os.startfile(f"{drive}:\\")

        elif action == "open_folder":
            os.startfile(p.get("path", os.path.expanduser("~")))

        elif action == "copy_file":
            src = p.get("source") or p.get("src")
            dst = p.get("destination") or p.get("dest")
            if src and dst and os.path.exists(src):
                shutil.copy2(src, dst)

        elif action == "move_file":
            src = p.get("source") or p.get("src")
            dst = p.get("destination") or p.get("dest")
            if src and dst and os.path.exists(src):
                shutil.move(src, dst)

        elif action == "delete_file":
            target = p.get("path") or p.get("source")
            if target and os.path.exists(target):
                ok = confirm_callback(f"مطمئنی حذف کنم؟\n{target}") if confirm_callback else True
                if ok:
                    (shutil.rmtree if os.path.isdir(target) else os.remove)(target)
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
            resp += " — ذخیره روی دسکتاپ"

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
            resp += f" (اکشن '{action}' هنوز پشتیبانی نمیشه)"

    except Exception as e:
        resp = f"خطا: {e}"
    return resp

# ============================================================
# DIGITAL SKULL FACE — canvas drawing helpers
# ============================================================

def _a(color, alpha_hex):
    """Simulate color+alpha blended on black — returns valid tkinter color."""
    color = color.lstrip('#')
    r,g,b = int(color[0:2],16), int(color[2:4],16), int(color[4:6],16)
    a = int(alpha_hex, 16) / 255
    return f'#{int(r*a):02x}{int(g*a):02x}{int(b*a):02x}'

STATE_COLORS = {
    'idle':      {'main':'#00ffe0','dark':'#003330','mid':'#009980','dim':'#002220'},
    'listening': {'main':'#00ff88','dark':'#003320','mid':'#00bb55','dim':'#002215'},
    'thinking':  {'main':'#a855f7','dark':'#2a0050','mid':'#7722cc','dim':'#1a0035'},
    'talking':   {'main':'#f0c040','dark':'#3a2800','mid':'#b08020','dim':'#251a00'},
    'error':     {'main':'#ff2255','dark':'#3a0010','mid':'#cc1040','dim':'#250008'},
}

def _hex_pts(cx, cy, r, angle_deg=0):
    pts = []
    for i in range(6):
        a = math.radians(60*i + angle_deg)
        pts.append(cx + r*math.cos(a))
        pts.append(cy + r*math.sin(a))
    return pts

def _bezier(p0, p1, p2, p3, n=22):
    pts = []
    for i in range(n+1):
        tt = i/n
        x = (1-tt)**3*p0[0]+3*(1-tt)**2*tt*p1[0]+3*(1-tt)*tt**2*p2[0]+tt**3*p3[0]
        y = (1-tt)**3*p0[1]+3*(1-tt)**2*tt*p1[1]+3*(1-tt)*tt**2*p2[1]+tt**3*p3[1]
        pts += [x, y]
    return pts

def _multi_oval(c, x1,y1,x2,y2, color, steps=4):
    for i in range(steps, 0, -1):
        pad = i*4
        c.create_oval(x1-pad,y1-pad,x2+pad,y2+pad, fill='', outline=color, width=1)

def _draw_skull(c, cx, cy, angle, face_state, talk_phase):
    c.delete("all")
    col = STATE_COLORS.get(face_state, STATE_COLORS['idle'])
    M, D, MID, DIM = col['main'], col['dark'], col['mid'], col['dim']
    bounce = math.sin(math.radians(angle*2.5)) * 4

    # background — faint grid
    for gx in range(0, 440, 28):
        c.create_line(gx, 0, gx, 470, fill='#0a0a0a', width=1)
    for gy in range(0, 470, 28):
        c.create_line(0, gy, 440, gy, fill='#0a0a0a', width=1)

    hx, hy = cx, cy + bounce

    # ── ambient glow rings ──
    for r, col_a in [(160,DIM),(120,D),(80,'#050505')]:
        c.create_oval(hx-r, hy-r-30, hx+r, hy+r-30, fill=col_a, outline='')

    # ── SKULL cranium — bezier polygon ──
    skull_pts = (
        _bezier((hx-105,hy+10),(hx-115,hy-30),(hx-110,hy-110),(hx-70,hy-148)) +
        _bezier((hx-70,hy-148),(hx-35,hy-183),(hx+35,hy-183),(hx+70,hy-148)) +
        _bezier((hx+70,hy-148),(hx+110,hy-110),(hx+115,hy-30),(hx+105,hy+10)) +
        _bezier((hx+105,hy+10),(hx+88,hy+52),(hx+50,hy+66),(hx,hy+70)) +
        _bezier((hx,hy+70),(hx-50,hy+66),(hx-88,hy+52),(hx-105,hy+10))
    )
    # pre-compute alpha variants (blended on black)
    M44=_a(M,'44'); M18=_a(M,'18'); M30=_a(M,'30'); M66=_a(M,'66')
    M22=_a(M,'22'); M88=_a(M,'88'); M55=_a(M,'55'); M99=_a(M,'99')
    M33=_a(M,'33'); MID88=_a(MID,'88')

    c.create_polygon(*skull_pts, fill='#0c0c0c', outline=MID, width=1, smooth=False)
    c.create_polygon(*skull_pts, fill='', outline=M44, width=3, smooth=False)
    c.create_polygon(*skull_pts, fill='', outline=M18, width=7, smooth=False)

    # ── circuit lines ──
    circuits = [
        [(hx-20,hy-168),(hx-20,hy-138),(hx-52,hy-138),(hx-52,hy-118)],
        [(hx+20,hy-168),(hx+20,hy-138),(hx+52,hy-138),(hx+52,hy-118)],
        [(hx-82,hy-98),(hx-100,hy-98),(hx-100,hy-68)],
        [(hx+82,hy-98),(hx+100,hy-98),(hx+100,hy-68)],
        [(hx,hy-178),(hx,hy-152),(hx-26,hy-152)],
        [(hx,hy-178),(hx,hy-152),(hx+26,hy-152)],
        [(hx-62,hy-158),(hx-62,hy-128)],
        [(hx+62,hy-158),(hx+62,hy-128)],
    ]
    for path in circuits:
        flat = [v for pt in path for v in pt]
        c.create_line(*flat, fill=M30, width=1)
        for px, py in path:
            c.create_oval(px-2,py-2,px+2,py+2, fill=M66, outline='')

    # ── scanning line ──
    scan_y = (hy-180) + (angle * 1.1 % 260)
    c.create_line(hx-112, scan_y, hx+112, scan_y, fill=M22, width=1)

    # ── EYES ──
    eye_y = hy - 58
    for side in (-1, 1):
        ex = hx + side*52

        # rotating hex rings
        for ring_r, ring_a_mult, a_hex in [(30, 0.3, '30'), (24, 0.5, '28'), (18, 0.0, '20')]:
            pts = _hex_pts(ex, eye_y, ring_r, angle * ring_a_mult * side)
            c.create_polygon(*pts, fill='', outline=_a(M,a_hex), width=1)

        # socket darkness
        c.create_oval(ex-23,eye_y-17,ex+23,eye_y+17, fill='#000000', outline='')

        # eye glow layers
        for r, a_hex in [(20,'66'),(14,'99'),(8,'cc'),(4,'ff')]:
            c.create_oval(ex-r,eye_y-int(r*0.72),ex+r,eye_y+int(r*0.72), fill=D, outline=_a(M,a_hex), width=1)

        # iris spokes (rotate)
        for spoke in range(8):
            a = math.radians(45*spoke + angle*0.8*side)
            x1,y1 = ex+9*math.cos(a), eye_y+9*math.sin(a)*0.7
            x2,y2 = ex+15*math.cos(a), eye_y+15*math.sin(a)*0.7
            c.create_line(x1,y1,x2,y2, fill=M88, width=1)

        # pupil
        c.create_oval(ex-5,eye_y-4,ex+5,eye_y+4, fill='#000', outline=M, width=2)

        # scan line (thinking)
        if face_state == 'thinking':
            sy = eye_y - 15 + (angle*1.5 % 30)
            c.create_line(ex-20,sy,ex+20,sy, fill=M55, width=1)

        # bloom glow
        _multi_oval(c, ex-20,eye_y-14,ex+20,eye_y+14, M22, 5)

        # corner brackets on eye
        for bx2, by2, sx2, sy2 in [(-23,-17,1,1),(-23,17,1,-1),(23,-17,-1,1),(23,17,-1,-1)]:
            c.create_line(ex+bx2+sx2*9,eye_y+by2, ex+bx2,eye_y+by2, fill=M99, width=1)
            c.create_line(ex+bx2,eye_y+by2, ex+bx2,eye_y+by2+sy2*7, fill=M99, width=1)

    # ── nose cavity ──
    nose_pts = _bezier((hx,hy-8),(hx-14,hy+4),(hx-18,hy+22),(hx-8,hy+29)) + \
               [(hx,hy+26)] + \
               list(reversed(_bezier((hx+8,hy+29),(hx+18,hy+22),(hx+14,hy+4),(hx,hy-8))))
    c.create_polygon(*nose_pts, fill='#000000', outline=M33, width=1)
    for ns in (-1,1):
        c.create_oval(hx+ns*6-8,hy+24-7,hx+ns*6+8,hy+24+7, fill=D, outline=M66, width=1)

    # ── cheekbone plates ──
    for side in (-1,1):
        px, py = hx+side*79, hy-5
        pts2 = [px-side*5,py-14, px+side*22,py-10, px+side*24,py+10, px-side*5,py+14]
        c.create_polygon(*pts2, fill='#0e0e0e', outline=M55, width=1)
        c.create_oval(px+side*6-3,py-3,px+side*6+3,py+3, fill=MID88, outline='')

    # ── temporal hex implants ──
    for side in (-1,1):
        ix, iy = hx+side*103, hy-78
        pts3 = _hex_pts(ix, iy, 14, angle*0.9*side)
        c.create_polygon(*pts3, fill='#080808', outline=M, width=1)
        pulse = abs(math.sin(math.radians(angle*3.5 + side*90)))
        inner_col = M if pulse > 0.5 else D
        c.create_oval(ix-5,iy-5,ix+5,iy+5, fill=inner_col, outline='')

    # ── JAW & TEETH ──
    jaw_pts = (
        _bezier((hx-90,hy+55),(hx-90,hy+100),(hx-50,hy+128),(hx,hy+136)) +
        _bezier((hx,hy+136),(hx+50,hy+128),(hx+90,hy+100),(hx+90,hy+55))
    )
    c.create_polygon(*jaw_pts, fill='#070707', outline=M33, width=1, smooth=False)

    # teeth
    t_count, t_w, t_gap = 7, 13, 2
    total_tw = t_count*(t_w+t_gap)-t_gap
    t_y = hy + 58
    for i in range(t_count):
        tx = hx - total_tw//2 + i*(t_w+t_gap)
        th = 13 if (i==0 or i==t_count-1) else 17
        c.create_rectangle(tx, t_y, tx+t_w, t_y+th, fill='#c8c4b4', outline='#666655', width=1)
        c.create_rectangle(tx, t_y, tx+t_w, t_y+3, fill='#ffffff', outline='')

    m_open = 0
    if face_state == 'talking':
        m_open = int(5 + 12*abs(math.sin(math.radians(talk_phase*8))))
    elif face_state == 'error':
        m_open = 16

    if m_open > 0:
        c.create_rectangle(hx-total_tw//2, t_y+17, hx+total_tw//2+t_w, t_y+17+m_open, fill='#000', outline='')
        for i in range(t_count):
            tx = hx - total_tw//2 + i*(t_w+t_gap)
            c.create_rectangle(tx, t_y+18+m_open, tx+t_w, t_y+30+m_open, fill='#b4b0a0', outline='#555544', width=1)
        c.create_oval(hx-16,t_y+14+m_open//2, hx+16,t_y+22+m_open//2, fill=D, outline=M66, width=1)

    # ── forehead center diamond ──
    d_cx, d_cy = hx, hy-172
    sz = 9
    pts_diamond2 = []
    for i in range(4):
        a = math.radians(45+90*i)
        pts_diamond2 += [d_cx+sz*math.cos(a), d_cy+sz*math.sin(a)]
    c.create_polygon(*pts_diamond2, fill='#0a0a0a', outline=M, width=1)
    pulse_d = abs(math.sin(math.radians(angle*7)))
    inner_sz = 5*pulse_d
    c.create_oval(d_cx-inner_sz,d_cy-inner_sz,d_cx+inner_sz,d_cy+inner_sz, fill=M, outline='')

    # vertical center line
    c.create_line(hx, hy-172, hx, hy-115, fill=M22, width=1)

    # ── glitch (error) ──
    if face_state == 'error' and random.random() < 0.12:
        gy = random.randint(0, 470)
        c.create_rectangle(0, gy, 440, gy+random.randint(3,16), fill='#1a0008', outline='')

    # ── state HUD bar ──
    state_map = {
        'idle':      ('STANDBY', M),
        'listening': ('LISTENING', M),
        'thinking':  ('PROCESSING', M),
        'talking':   ('TALKING', M),
        'error':     ('ERROR', M),
    }
    lbl, lbl_col = state_map.get(face_state, ('STANDBY', M))
    bar_y = hy + 168
    c.create_rectangle(hx-82,bar_y-12,hx+82,bar_y+12, fill='#060606', outline=M55, width=1)
    pulse_dot = abs(math.sin(math.radians(angle*6)))
    dot_r = 4*pulse_dot + 2
    c.create_oval(hx-70-dot_r,bar_y-dot_r,hx-70+dot_r,bar_y+dot_r, fill=M, outline='')
    c.create_text(hx+6, bar_y, text=lbl, fill=lbl_col, font=('Courier New',9,'bold'))

    # ── corner HUD brackets ──
    c.create_line(18,18, 18,44, fill=M33, width=1)
    c.create_line(18,18, 44,18, fill=M33, width=1)
    c.create_line(422,18, 422,44, fill=M33, width=1)
    c.create_line(422,18, 396,18, fill=M33, width=1)
    c.create_line(18,452, 18,426, fill=M33, width=1)
    c.create_line(18,452, 44,452, fill=M33, width=1)
    c.create_line(422,452, 422,426, fill=M33, width=1)
    c.create_line(422,452, 396,452, fill=M33, width=1)

    # version text
    c.create_text(28, 12, text='RASCO v2.0', fill=M44, font=('Courier New',7), anchor='w')

def _draw_doberman(c, cx, cy, angle, face_state, talk_phase):
    """
    Draws a detailed, beautiful robotic Doberman face on canvas c.
    cx, cy = center point, angle = animation tick, face_state = mood string.
    """
    c.delete("all")

    # Color palette
    FUR      = "#1a1a1a"
    FUR_MID  = "#222222"
    FUR_D    = "#000000"
    TAN      = "#8B5E3C"
    TAN_L    = "#C47A3A"
    METAL    = "#444444"
    METAL_L  = "#666666"
    LENS     = "#050d0f"
    RIM      = GOLD
    GLOW_COL = GREEN if face_state == "listening" else (RED if face_state == "error" else GOLD_L)

    bounce = math.sin(math.radians(angle * 2.2)) * 3
    hy     = cy + bounce

    # ── subtle ambient glow ring ──────────────────────────────
    glow_r = 175
    glow_color = "#1a1200" if face_state == "idle" else (
        "#001a08" if face_state == "listening" else (
        "#1a0008" if face_state == "error" else "#1a1200"))
    c.create_oval(cx-glow_r, hy-glow_r, cx+glow_r, hy+glow_r,
                  outline=glow_color, width=40)

    # ── SKULL ─────────────────────────────────────────────────
    HW, HH = 88, 75
    skull_cy = hy - 18

    # shadow beneath head
    c.create_oval(cx-HW+8, skull_cy-HH+10, cx+HW-8, skull_cy+HH+30,
                  fill="#000000", outline="")

    # skull gradient layers (dark→lighter toward center)
    for r_off, shade in [(0,"#1a1a1a"),(-5,"#202020"),(-10,"#262626")]:
        c.create_oval(cx-HW+r_off, skull_cy-HH+r_off,
                      cx+HW-r_off, skull_cy+HH-r_off,
                      fill=shade, outline="")
    c.create_oval(cx-HW, skull_cy-HH, cx+HW, skull_cy+HH,
                  fill="", outline=METAL, width=2)

    # chrome bolts on sides of skull
    for side in (-1,1):
        bx = cx + side*(HW-10)
        by = skull_cy
        c.create_oval(bx-5,by-5,bx+5,by+5, fill=METAL_L, outline=GOLD_D, width=1)
        c.create_oval(bx-2,by-2,bx+2,by+2, fill=GOLD_D, outline="")

    # ── EARS ─────────────────────────────────────────────────
    for side in (-1,1):
        bx  = cx + side * HW*0.52
        by  = skull_cy - HH*0.5
        tip_x = cx + side * (HW*0.82)
        tip_y = skull_cy - HH*1.6
        # ear shadow
        c.create_polygon(
            bx+side*2, by-12, bx+side*38, by+32, tip_x+side*3, tip_y+4,
            fill=FUR_D, outline=""
        )
        # main ear
        c.create_polygon(
            bx, by-14, bx+side*36, by+32, tip_x, tip_y,
            fill=FUR, outline=METAL, width=2
        )
        # inner ear (tan)
        c.create_polygon(
            bx+side*4, by-4, bx+side*24, by+20, tip_x+side*(-4)*side, tip_y+20,
            fill=TAN, outline=""
        )
        # ear tip highlight
        c.create_oval(tip_x-3, tip_y-3, tip_x+3, tip_y+3,
                      fill=METAL_L, outline="")

    # ── FOREHEAD PLATES (cyberpunk detail) ────────────────────
    for i, (px_off, pw) in enumerate([(-20,40),(0,22)]):
        plate_y = skull_cy - HH*0.75 + i*14
        c.create_rectangle(cx+px_off-pw//2, plate_y-4, cx+px_off+pw//2, plate_y+4,
                           fill=METAL, outline=GOLD_D, width=1)
    # center diamond
    pts = [cx, skull_cy-HH*0.6-8, cx+6, skull_cy-HH*0.6,
           cx, skull_cy-HH*0.6+8, cx-6, skull_cy-HH*0.6]
    c.create_polygon(*pts, fill=GOLD_D, outline=GOLD_L, width=1)

    # ── EYEBROW RUST SPOTS ────────────────────────────────────
    for side in (-1,1):
        ex = cx + side*HW*0.42
        ey = skull_cy - HH*0.28
        c.create_oval(ex-12, ey-8, ex+12, ey+8, fill=TAN, outline="")
        c.create_oval(ex-6,  ey-3, ex+6,  ey+3, fill=TAN_L, outline="")

    # ── MUZZLE ────────────────────────────────────────────────
    muz_w   = HW * 0.70
    muz_top = skull_cy + HH * 0.52
    muz_bot = skull_cy + HH * 1.82

    # muzzle shadow
    c.create_rectangle(cx-muz_w+4, muz_top+4, cx+muz_w+4, muz_bot+8,
                       fill=FUR_D, outline="")
    # muzzle body
    c.create_rectangle(cx-muz_w, muz_top, cx+muz_w, muz_bot,
                       fill=FUR_MID, outline=METAL, width=2)
    # muzzle top edge highlight
    c.create_line(cx-muz_w+4, muz_top+2, cx+muz_w-4, muz_top+2,
                  fill=METAL_L, width=1)

    # corner rounds
    for sx, sy, start in [(-1,-1,90),(-1,1,180),(1,-1,0),(1,1,270)]:
        ox = cx + sx*muz_w
        oy = muz_top if sy==-1 else muz_bot
        c.create_arc(ox+sx*(-28), oy+sy*(-20), ox, oy+sy*20,
                     start=start, extent=90, outline=METAL, style="arc", width=2)

    # tan cheek patches
    for side in (-1,1):
        px = cx + side*muz_w*0.62
        c.create_rectangle(px-side*36, muz_top+6, px, muz_bot-4,
                           fill=TAN, outline="")
        c.create_rectangle(px-side*20, muz_top+14, px-side*6, muz_bot-12,
                           fill=TAN_L, outline="")

    # ── SUNGLASSES ────────────────────────────────────────────
    bridge_y = muz_top - 6
    eye_dx   = HW * 0.40
    LW, LH   = 34, 20

    for side in (-1,1):
        ex = cx + side*eye_dx
        # lens shadow
        c.create_oval(ex-LW//2+3, bridge_y-LH//2+3,
                      ex+LW//2+3, bridge_y+LH//2+3, fill=FUR_D, outline="")
        # lens body
        c.create_oval(ex-LW//2, bridge_y-LH//2, ex+LW//2, bridge_y+LH//2,
                      fill=LENS, outline=RIM, width=3)
        # lens shine
        c.create_oval(ex-LW//2+5, bridge_y-LH//2+4,
                      ex-LW//2+14, bridge_y-LH//2+10,
                      fill=GOLD_G, outline="")
        # glow ring around lens (mood indicator)
        if face_state != "idle":
            c.create_oval(ex-LW//2-3, bridge_y-LH//2-3,
                          ex+LW//2+3, bridge_y+LH//2+3,
                          outline=GLOW_COL, width=2)

    # bridge
    c.create_line(cx-eye_dx+LW//2-2, bridge_y,
                  cx+eye_dx-LW//2+2, bridge_y,
                  fill=RIM, width=3)
    # temples
    for side in (-1,1):
        ex = cx + side*eye_dx
        c.create_line(ex+side*LW//2, bridge_y,
                      ex+side*(LW//2+22), bridge_y-4,
                      fill=RIM, width=2)

    # ── EYEBROW GLOW (mood) ────────────────────────────────────
    brow_y = bridge_y - LH//2 - 9
    brow_tilt = 0
    if face_state == "error":    brow_tilt = 7
    elif face_state == "thinking": brow_tilt = 3
    for side in (-1,1):
        ex = cx + side*eye_dx
        y1 = brow_y + brow_tilt*side
        y2 = brow_y - brow_tilt*side
        glow_w = 3 if face_state != "idle" else 2
        c.create_line(ex-12, y1, ex+12, y2,
                      fill=GLOW_COL, width=glow_w, capstyle="round")

    # ── NOSE ──────────────────────────────────────────────────
    nose_y = muz_bot - 12
    c.create_oval(cx-14, nose_y-11, cx+14, nose_y+9,
                  fill=FUR_D, outline=GOLD_D, width=2)
    # nose bridge ridge
    c.create_line(cx-4, nose_y-8, cx+4, nose_y-8, fill=METAL_L, width=2)
    # nostril highlights
    for nside in (-1,1):
        c.create_oval(cx+nside*5-3, nose_y-3, cx+nside*5+3, nose_y+3,
                      fill="#111111", outline="")
    # nose shine
    c.create_oval(cx-5, nose_y-9, cx, nose_y-4, fill=GOLD_L, outline="")

    # ── MOUTH ─────────────────────────────────────────────────
    mouth_y = muz_top + (muz_bot-muz_top)*0.52
    mouth_w = 24

    if face_state == "talking":
        open_amt = 6 + 7*abs(math.sin(talk_phase * 0.55))
        # teeth
        c.create_oval(cx-mouth_w//2, mouth_y-open_amt//2,
                      cx+mouth_w//2, mouth_y+open_amt//2,
                      fill=FUR_D, outline=GOLD_D, width=2)
        # upper teeth line
        if open_amt > 5:
            c.create_rectangle(cx-10, mouth_y-open_amt//2+2,
                               cx+10, mouth_y-open_amt//2+6,
                               fill=WHITE, outline="")
    elif face_state == "listening":
        c.create_oval(cx-mouth_w//3, mouth_y-6,
                      cx+mouth_w//3, mouth_y+6,
                      fill=FUR_D, outline=GOLD_D, width=2)
    elif face_state == "thinking":
        c.create_line(cx-mouth_w//2, mouth_y+2, cx+mouth_w//2, mouth_y-4,
                      fill=GOLD_D, width=3, capstyle="round")
        c.create_oval(cx+mouth_w//2-4, mouth_y-8,
                      cx+mouth_w//2+4, mouth_y,
                      fill=GOLD_D, outline="")
    elif face_state == "error":
        c.create_line(cx-mouth_w//2, mouth_y+6, cx+mouth_w//2, mouth_y-6,
                      fill=RED, width=3, capstyle="round")
    else:  # idle smirk
        c.create_line(cx-mouth_w//2, mouth_y+1, cx, mouth_y+4,
                      fill=GOLD_D, width=3, capstyle="round")
        c.create_line(cx, mouth_y+4, cx+mouth_w//2, mouth_y-7,
                      fill=GOLD_D, width=3, capstyle="round")

    # ── WHISKER DOTS ──────────────────────────────────────────
    for side in (-1,1):
        for i, (wy_off, wx_off) in enumerate([(-6,-18),(-1,-22),(5,-16)]):
            wx = cx + side*(muz_w*0.55+wx_off)
            wy = mouth_y + wy_off
            c.create_oval(wx-2, wy-2, wx+2, wy+2, fill=METAL_L, outline="")

    # ── COLLAR ────────────────────────────────────────────────
    collar_y = muz_bot + 20
    # collar band
    c.create_arc(cx-HW*1.18, collar_y-24, cx+HW*1.18, collar_y+32,
                 start=198, extent=144, outline=GOLD_D, width=10, style="arc")
    c.create_arc(cx-HW*1.18, collar_y-24, cx+HW*1.18, collar_y+32,
                 start=198, extent=144, outline=GOLD, width=4, style="arc")
    # collar studs
    for angle_deg in [220, 250, 270, 290, 320]:
        rad   = math.radians(angle_deg)
        sx    = cx + int(HW*1.1 * math.cos(rad))
        sy    = (collar_y+4) + int(28 * math.sin(rad))
        c.create_oval(sx-4, sy-4, sx+4, sy+4, fill=GOLD_L, outline=GOLD_D, width=1)
    # dog tag
    tag_y = collar_y + 30
    c.create_oval(cx-13, tag_y-2, cx+13, tag_y+20,
                  fill=GOLD_D, outline=GOLD, width=2)
    c.create_text(cx, tag_y+9, text="R", fill=GOLD_L, font=("Courier New",8,"bold"))

    # ── STATE INDICATOR ───────────────────────────────────────
    state_map = {
        "idle":      ("STANDBY", GOLD_D),
        "listening": ("LISTENING", GREEN),
        "thinking":  ("PROCESSING", GOLD),
        "talking":   ("TALKING", GOLD_L),
        "error":     ("ERROR", RED),
    }
    lbl, col = state_map.get(face_state, ("STANDBY", GOLD_D))

    # pulsing dot before label
    pulse_r = 4 + 2*abs(math.sin(math.radians(angle*3)))
    c.create_oval(cx-55-pulse_r, tag_y+26-pulse_r,
                  cx-55+pulse_r, tag_y+26+pulse_r,
                  fill=col, outline="")
    c.create_text(cx+5, tag_y+26, text=lbl, fill=col,
                  font=("Courier New",9,"bold"))

# ============================================================
# MAIN APP
# ============================================================
class RascoApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{ASSISTANT_NAME} — AI Desktop Assistant")
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rasco.ico")
            self.root.iconbitmap(icon_path)
        except Exception:
            pass
        self.root.geometry("1200x720")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self.angle      = 0
        self.weather_data = {}
        self.processing = False
        self.face_state = "idle"
        self.talk_phase = 0
        self.history    = []

        self.build_ui()
        self.update_clock()
        self.animate_orb()
        self.update_stats()
        threading.Thread(target=self._load_weather, daemon=True).start()

        self.log("SYS", f"{ASSISTANT_NAME} آماده‌ست. دستورت رو بنویس.")
        if SELENIUM_AVAILABLE:
            self.log("SYS", "✓ Browser automation فعاله — می‌تونم یوتیوب، Spotify و هر سایتی رو کنترل کنم.")
        else:
            self.log("SYS", "⚠ Selenium نصب نیست — browser automation غیرفعاله.")
        if CLAUDE_CMD_PATH != "claude":
            self.log("SYS", f"✓ Claude پیدا شد: {CLAUDE_CMD_PATH}")

        self.root.after(500, lambda: self._speak_and_animate(f"سلام. من {ASSISTANT_NAME} هستم. آماده‌ام."))

    def _load_weather(self):
        self.weather_data = get_weather()
        self.root.after(0, self._refresh_weather)
        self.root.after(900000, lambda: threading.Thread(target=self._load_weather, daemon=True).start())

    def _refresh_weather(self):
        w = self.weather_data
        self.temp_lbl.config(text=f"{w.get('temp','--')}°C")
        self.wdesc_lbl.config(text=str(w.get('desc','نامشخص')))
        self.humid_lbl.config(text=f"رطوبت: {w.get('humidity','--')}%  |  باد: {w.get('wind','--')} km/h")

    # ─── UI BUILD ───────────────────────────────────────────────
    def build_ui(self):
        # TOP BAR
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x")
        tk.Frame(top, bg=GOLD, height=2).pack(fill="x")
        bar = tk.Frame(top, bg=BG, pady=6)
        bar.pack(fill="x", padx=18)

        tk.Label(bar, text="SYSTEM ONLINE  |  BROWSER ENGINE: SELENIUM",
                 font=("Courier New",7), bg=BG, fg=GOLD_D).pack(side="left")
        tk.Label(bar, text=ASSISTANT_NAME,
                 font=("Courier New",32,"bold"), bg=BG, fg=GOLD_L).pack(side="left", expand=True)
        tk.Label(bar, text="Responsive Autonomous System for Comprehensive Operations",
                 font=("Courier New",7), bg=BG, fg=GOLD_D).pack(side="left", expand=True)
        self.online_lbl = tk.Label(bar, text="◉ ONLINE",
                 font=("Courier New",8,"bold"), bg=BG, fg=GREEN)
        self.online_lbl.pack(side="right")
        tk.Frame(top, bg=CYAN_D, height=1).pack(fill="x")

        # MAIN 3-COLUMN
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=6, pady=4)

        left   = tk.Frame(main, bg=BG, width=235)
        left.pack(side="left", fill="y", padx=(0,5))
        left.pack_propagate(False)

        center = tk.Frame(main, bg=BG)
        center.pack(side="left", fill="both", expand=True)

        right  = tk.Frame(main, bg=BG, width=300)
        right.pack(side="left", fill="y", padx=(5,0))
        right.pack_propagate(False)

        self._build_left(left)
        self._build_center(center)
        self._build_right(right)

    def _panel(self, parent, title):
        f = tk.Frame(parent, bg=PANEL)
        f.pack(fill="x", pady=3, padx=2)
        tk.Frame(f, bg=CYAN_D, height=1).pack(fill="x")
        hdr = tk.Frame(f, bg=DARK)
        hdr.pack(fill="x")
        tk.Label(hdr, text="▸ " + title, font=("Courier New",7,"bold"),
                 bg=DARK, fg=GOLD_D, anchor="w", padx=8, pady=3).pack(fill="x")
        tk.Frame(f, bg=GOLD_D, height=1).pack(fill="x")
        return f

    def _build_left(self, p):
        tf = self._panel(p, "TIME")
        self.clock_lbl = tk.Label(tf, text="00:00", font=("Courier New",32,"bold"),
                                   bg=PANEL, fg=WHITE, anchor="w", padx=10)
        self.clock_lbl.pack(fill="x")
        self.date_lbl = tk.Label(tf, text="", font=("Courier New",8),
                                  bg=PANEL, fg=GOLD, anchor="w", padx=10, pady=1)
        self.date_lbl.pack(fill="x")
        self.day_lbl = tk.Label(tf, text="", font=("Courier New",8),
                                 bg=PANEL, fg=GRAY, anchor="w", padx=10, pady=2)
        self.day_lbl.pack(fill="x")

        wf = self._panel(p, f"WEATHER · {CITY_FA}")
        self.temp_lbl = tk.Label(wf, text="--°C", font=("Courier New",26,"bold"),
                                  bg=PANEL, fg=GOLD, anchor="w", padx=10)
        self.temp_lbl.pack(fill="x")
        self.wdesc_lbl = tk.Label(wf, text="بارگذاری...", font=("Courier New",8),
                                   bg=PANEL, fg=WHITE, anchor="w", padx=10)
        self.wdesc_lbl.pack(fill="x")
        self.humid_lbl = tk.Label(wf, text="", font=("Courier New",7),
                                   bg=PANEL, fg=GRAY, anchor="w", padx=10, pady=3)
        self.humid_lbl.pack(fill="x")

        sf = self._panel(p, "SYSTEM STATUS")
        self.stat_labels = {}
        for key in ["CPU","RAM","DISK"]:
            row = tk.Frame(sf, bg=PANEL)
            row.pack(fill="x", padx=8, pady=4)
            tk.Label(row, text=key, font=("Courier New",7), bg=PANEL,
                     fg=GRAY, width=5, anchor="w").pack(side="left")
            bar_bg = tk.Canvas(row, bg="#050505", height=7, width=130, highlightthickness=0)
            bar_bg.pack(side="left", padx=4)
            lbl2 = tk.Label(row, text="0%", font=("Courier New",7),
                           bg=PANEL, fg=GOLD, width=4)
            lbl2.pack(side="left")
            self.stat_labels[key] = (bar_bg, lbl2)

        nf = self._panel(p, "NETWORK")
        self.net_lbl = tk.Label(nf, text="▲ 0 KB/s  ▼ 0 KB/s",
                                 font=("Courier New",8), bg=PANEL, fg=GREEN,
                                 anchor="w", padx=10, pady=4)
        self.net_lbl.pack(fill="x")
        self._net_old = psutil.net_io_counters()
        self._update_net()

        # CAPABILITIES
        cf = self._panel(p, "CAPABILITIES")
        caps = [
            ("🌐", "Browser Control"),
            ("▶", "YouTube / Spotify"),
            ("💬", "Conversation AI"),
            ("🖥", "System Control"),
            ("📁", "File Manager"),
        ]
        for icon, text in caps:
            tk.Label(cf, text=f"  {icon}  {text}", font=("Courier New",7),
                     bg=PANEL, fg=GOLD_G, anchor="w", pady=1).pack(fill="x")
        tk.Frame(cf, bg=PANEL, height=4).pack()

    def _update_net(self):
        try:
            new = psutil.net_io_counters()
            old = self._net_old
            up  = (new.bytes_sent - old.bytes_sent) // 1024
            dn  = (new.bytes_recv - old.bytes_recv) // 1024
            self._net_old = new
            self.net_lbl.config(text=f"▲ {up} KB/s   ▼ {dn} KB/s")
        except: pass
        self.root.after(2000, self._update_net)

    def _build_center(self, p):
        self.canvas = tk.Canvas(p, bg="#000000", highlightthickness=0, width=440, height=470)
        self.canvas.pack(expand=True)

        name_row = tk.Frame(p, bg=BG)
        name_row.pack()
        tk.Label(name_row, text=ASSISTANT_NAME,
                 font=("Courier New",15,"bold"), bg=BG, fg=GOLD_L).pack(side="left", padx=4)

        self.state_lbl = tk.Label(p, text="● Standby",
                 font=("Courier New",9), bg=BG, fg=GOLD_D)
        self.state_lbl.pack(pady=2)

        btn_row = tk.Frame(p, bg=BG)
        btn_row.pack(pady=8)
        def mkbtn(txt, col, cmd):
            tk.Button(btn_row, text=txt, font=("Courier New",8,"bold"),
                      bg=DARK, fg=col, activebackground=DARK, activeforeground=col,
                      relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
                      highlightthickness=1, highlightbackground=col,
                      command=cmd).pack(side="left", padx=8)
        mkbtn("◉ LIVE",     GREEN,  self._set_live)
        mkbtn("⏸ PAUSE",   ORANGE, self._set_pause)
        mkbtn("⏻ SHUTDOWN", RED,   self._shutdown)

    def _build_right(self, p):
        tk.Frame(p, bg=CYAN_D, height=1).pack(fill="x")
        hdr = tk.Frame(p, bg=PANEL, pady=5)
        hdr.pack(fill="x")
        tk.Label(hdr, text="CONVERSATION LOG", font=("Courier New",8,"bold"),
                 bg=PANEL, fg=GOLD, padx=8).pack(side="left")
        self.listen_ind = tk.Label(hdr, text="STANDBY",
                 font=("Courier New",7,"bold"), bg=PANEL, fg=GOLD_D)
        self.listen_ind.pack(side="right", padx=8)
        tk.Frame(p, bg=CYAN_D, height=1).pack(fill="x")

        self.chat = scrolledtext.ScrolledText(
            p, bg=PANEL, fg=WHITE, font=("Courier New",9),
            bd=0, relief="flat", padx=10, pady=10,
            wrap=tk.WORD, state="disabled", cursor="arrow"
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_config("SYS", foreground=ORANGE)
        self.chat.tag_config("YOU", foreground=GOLD_L, font=("Courier New",9,"bold"))
        self.chat.tag_config("BOT", foreground=WHITE)
        self.chat.tag_config("ACT", foreground=GREEN, font=("Courier New",8))
        self.chat.tag_config("ERR", foreground=RED)

        tk.Frame(p, bg=GOLD_D, height=1).pack(fill="x", pady=(4,0))
        inp_row = tk.Frame(p, bg=PANEL, pady=7, padx=6)
        inp_row.pack(fill="x")

        self.input_var = tk.StringVar()
        inp = tk.Entry(inp_row, textvariable=self.input_var,
                       font=("Courier New",10), bg="#080818", fg=WHITE,
                       insertbackground=GOLD_L, relief="flat", bd=8)
        inp.pack(side="left", fill="x", expand=True, ipady=6)
        inp.bind("<Return>", self.send)
        inp.focus()

        self.mic_btn = tk.Button(inp_row, text="🎤",
                       font=("Courier New",10,"bold"), bg="#151515", fg=GRAY,
                       activebackground=GOLD_D, relief="flat", bd=0,
                       padx=8, pady=6, cursor="hand2", command=self.toggle_mic)
        self.mic_btn.pack(side="left", padx=(4,0))
        self._update_mic_button_state()

        self.send_btn = tk.Button(inp_row, text="SEND ▶",
                       font=("Courier New",8,"bold"), bg=GOLD, fg=BG,
                       activebackground=GOLD_L, relief="flat", bd=0,
                       padx=12, pady=6, cursor="hand2", command=self.send)
        self.send_btn.pack(side="left", padx=(4,0))

    # ─── CLOCK ──────────────────────────────────────────────────
    def update_clock(self):
        now = datetime.now()
        self.clock_lbl.config(text=now.strftime("%H:%M"))
        self.date_lbl.config(text=now.strftime("%d %b %Y").upper())
        days_fa = ["دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه"]
        self.day_lbl.config(text=days_fa[now.weekday()])
        self.root.after(1000, self.update_clock)

    # ─── STATS ──────────────────────────────────────────────────
    def update_stats(self):
        vals = {"CPU": psutil.cpu_percent(interval=None),
                "RAM": psutil.virtual_memory().percent,
                "DISK": psutil.disk_usage('/').percent}
        for key,(bar_bg,lbl2) in self.stat_labels.items():
            v = vals[key]; w = bar_bg.winfo_width() or 130
            fw = max(2, int(w * v / 100))
            col = RED if v>80 else (ORANGE if v>50 else GOLD)
            bar_bg.delete("all")
            bar_bg.create_rectangle(0,0,fw,7, fill=col, outline="")
            lbl2.config(text=f"{int(v)}%")
        self.root.after(2000, self.update_stats)

    # ─── SKULL ANIMATION ────────────────────────────────────────
    def animate_orb(self):
        _draw_skull(self.canvas, 220, 235, self.angle, self.face_state, self.talk_phase)
        if self.face_state == "talking":
            self.talk_phase += 1
        self.angle = (self.angle + 1.0) % 3600
        self.root.after(40, self.animate_orb)

    def set_face_state(self, state):
        self.face_state = state

    # ─── CONTROLS ───────────────────────────────────────────────
    def _set_live(self):
        self.state_lbl.config(text="● Live", fg=GREEN)
        self.listen_ind.config(text="LIVE", fg=GREEN)
        self.online_lbl.config(text="◉ LIVE", fg=GREEN)
        self.set_face_state("idle")

    def _set_pause(self):
        self.state_lbl.config(text="⏸ Paused", fg=ORANGE)
        self.listen_ind.config(text="PAUSED", fg=ORANGE)
        self.online_lbl.config(text="◉ PAUSED", fg=ORANGE)
        self.set_face_state("idle")

    def _shutdown(self):
        global _browser
        speak("در حال خاموش شدن.")
        try:
            if _browser: _browser.quit()
        except: pass
        self.root.after(1200, self.root.destroy)

    # ─── LOG ────────────────────────────────────────────────────
    def log(self, role, text):
        self.chat.config(state="normal")
        prefix = {"SYS":"[SYS]","YOU":"[YOU]","BOT":f"[{ASSISTANT_NAME}]",
                  "ACT":"  ⚡","ERR":"  ✗"}.get(role, role)
        self.chat.insert("end", f"{prefix} {text}\n", role)
        self.chat.config(state="disabled")
        self.chat.see("end")

    # ─── MIC ────────────────────────────────────────────────────
    def _update_mic_button_state(self):
        if mic_is_available():
            self.mic_btn.config(state="normal", fg=GOLD, cursor="hand2")
        else:
            self.mic_btn.config(state="disabled", fg=GRAY, cursor="arrow")

    def toggle_mic(self):
        if not mic_is_available():
            self.log("SYS", "میکروفونی پیدا نشد.")
            return
        if self.processing: return
        self.mic_btn.config(state="disabled", text="●", fg=RED)
        self.set_face_state("listening")
        self.log("SYS", "در حال ضبط... (۶ ثانیه)")
        threading.Thread(target=self._record_thread, daemon=True).start()

    def _record_thread(self):
        try:
            text = record_and_transcribe(duration=6)
            if text:
                self.root.after(0, lambda: self._on_transcribed(text))
            else:
                self.root.after(0, lambda: self.log("ERR","چیزی شنیده نشد."))
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

    # ─── SEND ───────────────────────────────────────────────────
    def send(self, event=None):
        cmd = self.input_var.get().strip()
        if not cmd or self.processing: return
        self.input_var.set("")
        self.log("YOU", cmd)

        if any(w in cmd.lower() for w in ["exit","quit","خروج","خداحافظ"]):
            self.log("BOT","خداحافظ!")
            speak("خداحافظ!")
            self.root.after(1500, self.root.destroy)
            return

        if cmd.strip() in ["پاک کن حافظه","حافظه رو پاک کن","clear memory","forget everything"]:
            self.history = []
            self.log("SYS","حافظه پاک شد.")
            return

        self.processing = True
        self.send_btn.config(state="disabled", text="...")
        self.state_lbl.config(text="◌ Processing...", fg=GOLD)
        self.online_lbl.config(text="◉ THINKING", fg=GOLD)
        self.listen_ind.config(text="PROCESSING", fg=GOLD)
        self.set_face_state("thinking")
        threading.Thread(target=self._process, args=(cmd,), daemon=True).start()

    def _confirm_dialog(self, message):
        result = {"value": False}
        done   = threading.Event()
        def ask():
            result["value"] = messagebox.askyesno("تأیید", message)
            done.set()
        self.root.after(0, ask)
        done.wait(timeout=30)
        return result["value"]

    def _speak_and_animate(self, text):
        self.set_face_state("talking")
        speak(text)
        approx_ms = min(9000, max(1200, len(text) * 70))
        self.root.after(approx_ms, lambda: self.set_face_state("idle"))

    def _process(self, cmd):
        try:
            self._process_inner(cmd)
        except Exception as e:
            err = f"خطای داخلی: {e}"
            self.root.after(0, lambda: self.log("ERR", err))
            self.root.after(0, lambda: self.set_face_state("error"))
        finally:
            self.processing = False
            self.root.after(0, lambda: self.send_btn.config(state="normal", text="SEND ▶"))
            self.root.after(0, lambda: self.listen_ind.config(text="STANDBY", fg=GOLD_D))
            self.root.after(0, lambda: self.online_lbl.config(text="◉ ONLINE", fg=GREEN))
            self.root.after(0, lambda: self.state_lbl.config(text="● Standby", fg=GOLD_D))

    def _process_inner(self, cmd):
        try:
            data   = ask_claude(cmd, history=self.history)
            action = data.get("action","")
            resp   = execute_action(data, confirm_callback=self._confirm_dialog)
            self.history.append(("User", cmd))
            self.history.append(("Assistant", resp))
            self.root.after(0, lambda: self.log("ACT", f"Action: {action}"))
            self.root.after(0, lambda: self.log("BOT", resp))
            self.root.after(0, lambda: self._speak_and_animate(resp))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.log("ERR", err))
            self.root.after(0, lambda: self.set_face_state("error"))

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = RascoApp()
    app.run()
