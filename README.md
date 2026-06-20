# Rasco & CodePilot

دو دستیار هوش مصنوعی دسکتاپ که با Python و Tkinter ساخته شدن، با رابط گرافیکی سایبرپانک/JARVIS-style.

## 🤖 Rasco

دستیار صوتی/متنی برای کنترل کامپیوتر ویندوز — باز کردن برنامه‌ها، مرورگر، یوتیوب، کپی/حذف فایل، اسکرین‌شات و غیره.
رابط گرافیکی مشکی-طلایی الهام‌گرفته از JARVIS، با ساعت، آب‌وهوا، و مانیتور سیستم زنده.

**اجرا:**
```bash
python rasco.py
```

## ⚡ CodePilot

دستیار AI برای دیباگ و تحلیل کدبیس‌های Flask/Python. یه پوشه پروژه یا یه فایل خاص رو انتخاب می‌کنی،
و از روی کد و لاگ‌ها جواب فنی می‌گیری.

**اجرا:**
```bash
python codepilot.py
```

دو نسخه موجوده:
- `codepilot.py` — با Claude Code (نیاز به اشتراک Pro/Max و نصب Claude Code CLI)
- `codepilot_ollama.py` — کاملاً محلی و آفلاین با Ollama (نیاز به نصب Ollama + مدل llama3.2)

## ⚙️ پیش‌نیازها

```bash
pip install pyttsx3 pyautogui psutil
```

برای Rasco و CodePilot (نسخه Claude Code)، نیاز به نصب و لاگین [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) داری:
```bash
npm install -g @anthropic-ai/claude-code
claude
```

برای نسخه Ollama، نیاز به نصب [Ollama](https://ollama.com) و دانلود مدل داری:
```bash
ollama pull llama3.2
ollama serve
```

## ⚠️ نکته امنیتی

این پروژه از Claude Code CLI به صورت subprocess استفاده می‌کنه و هیچ کلید API مستقیم
توی کد ذخیره نمی‌شه. اگه نسخه‌ای با کلید API (مثل Gemini) می‌سازی، **هرگز کلید واقعی رو
کامیت نکن** — از environment variable یا فایل `.env` (که توی `.gitignore` باشه) استفاده کن.
