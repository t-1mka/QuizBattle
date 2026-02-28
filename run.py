#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BrainStorm — локальный запуск: python run.py"""
import os, sys, subprocess, logging, socket as _socket

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ.setdefault("LANG", "C.UTF-8")
os.environ.setdefault("LC_ALL", "C.UTF-8")
for s in (sys.stdout, sys.stderr):
    if hasattr(s, "reconfigure"):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except: pass

if sys.version_info < (3, 10):
    print("Нужен Python 3.10+"); sys.exit(1)

req = os.path.join(os.path.dirname(__file__), "requirements.txt")
print("Проверяю зависимости...")
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-r", req, "-q"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
print("Зависимости OK")

env_f = os.path.join(os.path.dirname(__file__), ".env")
ex_f  = os.path.join(os.path.dirname(__file__), ".env.example")
if not os.path.exists(env_f) and os.path.exists(ex_f):
    import shutil; shutil.copy(ex_f, env_f)
    print("Создан .env — добавь GIGACHAT_CREDENTIALS!")

from dotenv import load_dotenv
load_dotenv(override=False)

# ── Логирование ──────────────────────────────────────────────
log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("engineio").setLevel(logging.WARNING)
logging.getLogger("socketio").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ── Локальный IP ─────────────────────────────────────────────
def get_local_ip() -> str:
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ── Запуск ───────────────────────────────────────────────────
from app import create_app, socketio
from app.ai_client import active_backend

application = create_app()
host     = os.getenv("HOST", "0.0.0.0")
port     = int(os.getenv("PORT", 5000))
debug    = os.getenv("DEBUG", "false").lower() == "true"
local_ip = get_local_ip()
ai_info  = active_backend()

W = 48  # ширина содержимого рамки

def row(text=""):
    # text может содержать emoji (2 символа ширины) — считаем визуальную ширину
    visual = sum(2 if ord(c) > 0x2E7F else 1 for c in text)
    pad = W - visual
    return f"  {text}{' ' * max(pad, 0)}"

print("")
print("+" + "-" * (W + 2) + "+")
print("|" + row("  BrainStorm  —  сервер запущен!") + "|")
print("+" + "-" * (W + 2) + "+")
print("|" + row(f"  Локально:  http://localhost:{port}") + "|")
print("|" + row(f"  По сети:   http://{local_ip}:{port}") + "|")
print("+" + "-" * (W + 2) + "+")
print("|" + row(f"  AI:    {ai_info}") + "|")
print("|" + row(f"  Логи:  {log_level_name}  (LOG_LEVEL=DEBUG для подробностей)") + "|")
print("+" + "-" * (W + 2) + "+")
print("|" + row("  Ctrl+C — остановить") + "|")
print("+" + "-" * (W + 2) + "+")
print("")

socketio.run(application, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
