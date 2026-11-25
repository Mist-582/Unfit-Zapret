from __future__ import annotations

import base64
import ctypes
import http.client
import ipaddress
import json
import os
import platform
import random
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from xml.sax.saxutils import escape as xml_escape

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    import winreg
    from ctypes import wintypes
    CREATE_NO_WINDOW = 0x08000000
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_BREAKAWAY_FROM_JOB = 0x01000000
    BACKGROUND_FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
else:
    CREATE_NO_WINDOW = 0
    DETACHED_PROCESS = 0
    CREATE_NEW_PROCESS_GROUP = 0
    CREATE_BREAKAWAY_FROM_JOB = 0
    BACKGROUND_FLAGS = 0

TASK_NAME = "ZapretUltraStable"
SYSTEMD_SERVICE = "unfit-zapret.service"
LINUX_NFQ_NUM = 200
LINUX_FWMARK = 0x40000000
LINUX_NFT_TABLE = "unfit_zapret"

APP_NAME = "Unfit Zapret"
APP_VERSION = "2.2.1"
GITHUB_OWNER = "Mist-582"
GITHUB_REPO = "Unfit-Zapret"
GITHUB_AVATAR_URL = f"https://avatars.githubusercontent.com/{GITHUB_OWNER}?s=128"

DNS_AI_TEMPLATE = "https://dns.dns-ai.ru/dns-query"
DNS_AI_TLS_HOST = "dns.dns-ai.ru"
DNS_AI_MANIFESTS = (
    "https://raw.githubusercontent.com/confeden/DNS-AI/main/endpoints.json",
    "https://dns-ai.ru/endpoints.json",
)
DNS_AI_BUILTIN_V4 = ("194.87.196.13", "45.151.102.219")
DNS_AI_BUILTIN_V6 = ("2a00:b700:5::3:62", "2a12:5940:d4ef::219")
DNS_AI_RETIRED = (
    "217.60.10.20", "94.232.43.149", "185.251.90.181", "2a0a:2b41:0:3840::53",
    "192.144.59.14", "2a0d:8480:0:67c::14", "186.246.49.127", "2a0a:2b41:0:500d::53",
)
DNS_AI_WIN_EXE_URL = "https://github.com/confeden/DNS-AI/releases/latest/download/DNS-AI.exe"


def detect_arch() -> str:
    m = platform.machine().lower()
    if m in ("amd64", "x86_64", "x64"):
        return "x86_64"
    if m in ("i386", "i486", "i586", "i686", "x86"):
        return "x86"
    if m in ("aarch64", "arm64", "armv8b", "armv8l"):
        return "arm64"
    if m.startswith("arm"):
        return "arm"
    return "x86_64"


def get_platform_label() -> str:
    os_name = "Windows" if IS_WINDOWS else ("Linux" if IS_LINUX else sys.platform)
    return f"{os_name} {detect_arch()}"


def _subproc_hidden_kwargs() -> dict:
    return {"creationflags": CREATE_NO_WINDOW} if IS_WINDOWS else {}


def get_embedded_assets_zip() -> Optional[Path]:
    candidates = [
        Path(__file__).resolve().parent / "embedded_assets.zip",
        Path(sys.executable).resolve().parent / "embedded_assets.zip",
    ]
    if sys.argv and sys.argv[0]:
        candidates.append(Path(sys.argv[0]).resolve().parent / "embedded_assets.zip")
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            pass
    return None


def is_compiled_binary() -> bool:
    if ("__compiled__" in globals()) or getattr(sys, "frozen", False):
        return True
    if IS_WINDOWS and sys.argv and sys.argv[0] and Path(sys.argv[0]).suffix.lower() == ".exe":
        return True
    return False


def get_real_executable() -> Path:
    for env_key in ("NUITKA_ONEFILE_BINARY", "APPIMAGE"):
        val = os.environ.get(env_key)
        if val and Path(val).exists():
            return Path(val).resolve()
    parent_pid = os.environ.get("NUITKA_ONEFILE_PARENT")
    if parent_pid and parent_pid.isdigit():
        if IS_WINDOWS:
            try:
                kernel32 = ctypes.windll.kernel32
                h_proc = kernel32.OpenProcess(0x1000, False, int(parent_pid))
                if h_proc:
                    try:
                        buf = ctypes.create_unicode_buffer(4096)
                        size = wintypes.DWORD(4096)
                        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                            p = Path(buf.value)
                            if p.exists():
                                return p.resolve()
                    finally:
                        kernel32.CloseHandle(h_proc)
            except Exception:
                pass
        elif IS_LINUX:
            try:
                p = Path(f"/proc/{parent_pid}/exe").resolve()
                if p.exists():
                    return p
            except Exception:
                pass
    if is_compiled_binary() and sys.argv and sys.argv[0]:
        arg_path = Path(sys.argv[0])
        if arg_path.exists():
            return arg_path.resolve()
        found = shutil.which(sys.argv[0])
        if found:
            return Path(found).resolve()
        return arg_path.resolve()
    return Path(sys.executable).resolve()


def get_work_dir() -> Path:
    if IS_WINDOWS:
        if is_compiled_binary() or (get_embedded_assets_zip() is not None and not (Path(__file__).resolve().parent / "bin" / "winws.exe").exists()):
            sys_drive = os.environ.get("SystemDrive", "C:").rstrip("\\/")
            return Path(f"{sys_drive}\\") / "UnfitZapret"
        return Path(__file__).resolve().parent

    if is_compiled_binary():
        sudo_user = os.environ.get("SUDO_USER", "").strip()
        if sudo_user:
            try:
                import pwd
                return Path(pwd.getpwnam(sudo_user).pw_dir) / "UnfitZapret"
            except Exception:
                pass
        return Path.home() / "UnfitZapret"
    return Path(__file__).resolve().parent


WORK_DIR = get_work_dir()
BIN_DIR = WORK_DIR / "bin"
LISTS_DIR = WORK_DIR / "lists"
CONFIG_FILE = WORK_DIR / "zapret_config.json"
AUTORUN_LOG_FILE = WORK_DIR / "autorun.log"
TG_PROXY_PID_FILE = WORK_DIR / "tg_proxy.pid"
DNS_AI_STATE_FILE = WORK_DIR / ".dns_ai_state.json"
if IS_WINDOWS:
    CURL_EXE = r"C:\Windows\System32\curl.exe" if os.path.exists(r"C:\Windows\System32\curl.exe") else "curl"
else:
    CURL_EXE = shutil.which("curl") or "curl"


def get_engine_binary() -> Path:
    if IS_WINDOWS:
        return BIN_DIR / "winws.exe"
    arch_bin = BIN_DIR / f"nfqws-linux-{detect_arch()}"
    if arch_bin.exists():
        return arch_bin
    plain = BIN_DIR / "nfqws"
    if plain.exists():
        return plain
    sys_bin = shutil.which("nfqws")
    return Path(sys_bin) if sys_bin else arch_bin


def get_engine_name() -> str:
    return "winws.exe" if IS_WINDOWS else get_engine_binary().name


STRATEGIES: list[dict[str, str]] = [
    {
        "name": "ALT13 Sochi + Hostfakesplit (2026)",
        "desc": "Лидер 2026: altorder hostfakesplit + TLS Sochi/STUN2 из белых списков РФ",
        "args": "--dpi-desync=fake,hostfakesplit --dpi-desync-fooling=ts --dpi-desync-hostfakesplit-mod=host=mail.ru,altorder=1 --dpi-desync-repeats=5 --dpi-desync-fake-tls={tls_sochi} --dpi-desync-fake-tls={stun2} --dpi-desync-fake-http={tls_sochi}",
    },
    {
        "name": "ALT11 Sferum Overlap 664 + STUN2 (2026)",
        "desc": "Overlap 664 под Sferum/STUN2 (Flowseal 1.10.4) против жёсткого ТСПУ",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=664 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=8 --dpi-desync-split-seqovl-pattern={tls_sferum} --dpi-desync-fake-tls={stun2} --dpi-desync-fake-tls={tls_sferum} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "EXP STUN2 Overlap 480 + Sferum (2026)",
        "desc": "Экспериментальный быстрый overlap 480 + Sferum для мобильных и проводных сетей",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=480 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=4 --dpi-desync-split-seqovl-pattern={stun2} --dpi-desync-fake-tls={tls_sferum} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "Fake TLS Auto (Multidisorder + Badseq)",
        "desc": "Двойной нулевой фейк TLS 0x00 + инверсия (!) и multidisorder по midsld",
        "args": "--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=0x00000000 --dpi-desync-fake-tls=! --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "Fake TLS Auto ALT (Fakedsplit + Badseq 2)",
        "desc": "Fakedsplit с автоподбором TLS и badseq=2",
        "args": "--dpi-desync=fake,fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=2 --dpi-desync-repeats=8 --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "Fake TLS Auto ALT2 (Overlap 681 + Badseq 10M)",
        "desc": "Глубокий overlap 681 + badseq 10M и Fake TLS Mod",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=10000000 --dpi-desync-repeats=8 --dpi-desync-split-seqovl-pattern={tls_google} --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "Fake TLS Auto ALT3 (Overlap 681 + TS)",
        "desc": "Overlap 681 с TCP timestamps и маскировкой SNI",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=8 --dpi-desync-split-seqovl-pattern={tls_google} --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "ALT9 Hostfakesplit Ozon (TS + MD5Sig)",
        "desc": "Без фейк-пакетов TLS: hostfakesplit под ozon.ru с ts+md5sig",
        "args": "--dpi-desync=hostfakesplit --dpi-desync-repeats=4 --dpi-desync-fooling=ts,md5sig --dpi-desync-hostfakesplit-mod=host=ozon.ru",
    },
    {
        "name": "ALT7 Multisplit SNIExt+1 (Overlap 679)",
        "desc": "Разрезание внутри расширения SNI (sniext+1) без фейков",
        "args": "--dpi-desync=multisplit --dpi-desync-split-pos=2,sniext+1 --dpi-desync-split-seqovl=679 --dpi-desync-split-seqovl-pattern={tls_google}",
    },
    {
        "name": "Simple Fake ALT2 (Sferum + STUN2)",
        "desc": "Лёгкий фейк Sferum/STUN2 без фрагментации (низкий пинг)",
        "args": "--dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fooling=ts --dpi-desync-fake-tls={stun2} --dpi-desync-fake-tls={tls_sferum} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "General Multisplit 568 (4PDA)",
        "desc": "Базовый чистый multisplit 568 с 4PDA ClientHello",
        "args": "--dpi-desync=multisplit --dpi-desync-split-seqovl=568 --dpi-desync-split-pos=1 --dpi-desync-split-seqovl-pattern={tls_4pda}",
    },
    {
        "name": "ALT Fakedsplit 0x00",
        "desc": "Классический fakedsplit 0x00 с timestamp fooling",
        "args": "--dpi-desync=fake,fakedsplit --dpi-desync-repeats=6 --dpi-desync-fooling=ts --dpi-desync-fakedsplit-pattern=0x00 --dpi-desync-fake-tls={stun} --dpi-desync-fake-tls={tls_google} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "[Unfit AI-1] Chaos Multidisorder (7-point SNI)",
        "desc": "7-точечное перемешивание сегментов SNI ломает ИИ-классификатор без фейков",
        "args": "--dpi-desync=multidisorder --dpi-desync-split-pos=1,sniext+1,host+1,midsld-2,midsld,midsld+2,endhost-1",
    },
    {
        "name": "[Unfit AI-2] Ghost FakeTLS + RndSNI + Padencap",
        "desc": "Случайный SNI + padencap + md5sig/badseq сбивает эвристику ТСПУ",
        "args": "--dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,sniext+1,midsld --dpi-desync-fooling=md5sig,badseq --dpi-desync-badseq-increment=10000 --dpi-desync-repeats=6 --dpi-desync-fake-tls=0x00000000 --dpi-desync-fake-tls={tls_sferum} --dpi-desync-fake-tls-mod=rnd,rndsni,dupsid,padencap --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "[Unfit AI-3] Whitelist 5ka + AutoTTL + Disorder",
        "desc": "AutoTTL до ближайшего ТСПУ + белый шаблон 5ka.ru и fakeddisorder",
        "args": "--dpi-desync=fake,fakeddisorder --dpi-desync-split-pos=1,midsld --dpi-desync-autottl=2:2-12 --dpi-desync-fooling=badseq,ts --dpi-desync-repeats=6 --dpi-desync-fakedsplit-pattern={tls_5ka} --dpi-desync-fake-tls={tls_5ka} --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-fake-http={tls_5ka}",
    },
    {
        "name": "[Unfit AI-4] Deep Hostfakesplit (Midhost + Badseq/Badsum)",
        "desc": "Подмена середины хоста (midhost) + overlap 654 под белый списочный домен",
        "args": "--dpi-desync=fake,hostfakesplit --dpi-desync-hostfakesplit-midhost=host-2 --dpi-desync-hostfakesplit-mod=host={fake_sni},altorder=1 --dpi-desync-split-seqovl=654 --dpi-desync-split-seqovl-pattern={tls_5ka} --dpi-desync-fooling=badseq,badsum --dpi-desync-badseq-increment=0 --dpi-desync-repeats=4 --dpi-desync-fake-tls={tls_5ka} --dpi-desync-fake-http={tls_5ka}",
    },
    {
        "name": "[Unfit AI-5] Dual-Fake Dup + MD5Sig (Anti-Stateful)",
        "desc": "Дублирование обманных пакетов (--dup) против stateful-анализаторов ТСПУ",
        "args": "--dpi-desync=fake,fakeddisorder --dpi-desync-split-pos=1,midsld --dpi-desync-fooling=md5sig,badseq --dpi-desync-repeats=5 --dup=1 --dup-cutoff=n2 --dup-fooling=md5sig --dpi-desync-fake-tls={tls_sochi} --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-fake-http={tls_sochi}",
    },
    {
        "name": "[Unfit AI-6] Syndata + Multidisorder",
        "desc": "Вброс TLS-данных на этапе TCP SYN + разрезание ClientHello",
        "args": "--dpi-desync=syndata,multidisorder --dpi-desync-split-pos=1,sniext+1,midsld --dpi-desync-fake-syndata={tls_sferum}",
    },
    {
        "name": "[Unfit AI-7] Stealth Overlap 517 (Badseq + MD5Sig)",
        "desc": "Стелс-перекрытие 517 байт с двойной десинхронизацией badseq+md5sig",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-pos=1,sniext+1 --dpi-desync-split-seqovl=517 --dpi-desync-split-seqovl-pattern={tls_google} --dpi-desync-fooling=badseq,md5sig --dpi-desync-repeats=6 --dpi-desync-fake-tls={tls_sferum} --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-fake-http={tls_sferum}",
    },
    {
        "name": "[Unfit AI-8] Triple-Fake + SeqOvl 336 (Strict ISP)",
        "desc": "Тройной фейк (0x00 + 0x0F + Sferum) с seqovl 336 для самых тяжёлых сетей",
        "args": "--dpi-desync=fake,multidisorder --dpi-desync-split-pos=10,midsld --dpi-desync-split-seqovl=336 --dpi-desync-split-seqovl-pattern={tls_sferum} --dpi-desync-fooling=badseq --dpi-desync-repeats=6 --dpi-desync-fake-tls=0x00000000 --dpi-desync-fake-tls=0x0F0F0F0F --dpi-desync-fake-tls={tls_sferum} --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-fake-http={tls_sferum}",
    },
]

STRATEGY_STRINGS = [s["args"] for s in STRATEGIES]

POPULAR_SNIS = [
    "www.sferum.ru",
    "ozon.ru",
    "mail.ru",
    "ya.ru",
    "5ka.ru",
    "rutube.ru",
    "max.ru",
    "gosuslugi.ru",
    "vk.com",
    "yandex.ru",
    "www.google.com",
    "www.cloudflare.com",
    "www.apple.com",
    "random",
]

TEST_TARGETS = [
    ("ds", "Discord", "https://discord.com/api/v10/gateway"),
    ("yt", "YouTube", "https://www.youtube.com"),
    ("tg", "Telegram", "https://t.me"),
    ("tw", "X / Twitter", "https://x.com"),
]

REQUIRED_LIST_FILES = [
    "list-general.txt",
    "list-general-user.txt",
    "list-exclude.txt",
    "list-exclude-user.txt",
    "ipset-exclude.txt",
    "ipset-exclude-user.txt",
    "list-google.txt",
    "list-gemini.txt",
    "list-telegram.txt",
    "ipset-telegram.txt",
    "ipset-all.txt",
]

VPN_KEYWORDS = (
    "vpn", "wireguard", "wg", "openvpn", "nekoray", "sing-box", "v2ray", "clash",
    "amnezia", "outline", "shadowsocks", "tun2socks", "qv2ray", "v2rayn", "warp",
    "cloudflare-warp", "windscribe", "protonvpn", "nordvpn", "expressvpn", "mullvad",
    "hiddify", "throne", "bye",
)

GAME_KEYWORDS = (
    "steam", "epicgameslauncher", "riotclient", "origin", "uplay", "ubisoft",
    "gaijin", "warthunder", "cs2", "dota2", "valorant", "league of legends",
    "rust", "gta", "fivem", "battle.net", "ea desktop", "roblox", "minecraft",
)


def is_admin() -> bool:
    if IS_WINDOWS:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def relaunch_as_admin() -> None:
    if IS_WINDOWS:
        if is_compiled_binary():
            exe_path = get_real_executable()
            extra_args = " ".join(f'"{a}"' for a in sys.argv[1:]) if len(sys.argv) > 1 else None
            ctypes.windll.shell32.ShellExecuteW(None, "runas", str(exe_path), extra_args, str(exe_path.parent), 1)
        else:
            script_path = (
                Path(sys.argv[0]).resolve()
                if (sys.argv and sys.argv[0] and Path(sys.argv[0]).exists())
                else (Path(__file__).resolve().parent / "zapret_manager.py").resolve()
            )
            py_exe = sys.executable
            pyw = Path(py_exe).with_name("pythonw.exe")
            if pyw.exists() and "--console" not in sys.argv:
                py_exe = str(pyw)
            args = f'"{script_path}"'
            if len(sys.argv) > 1:
                args += " " + " ".join(f'"{a}"' for a in sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", py_exe, args, str(script_path.parent), 1)
        return

    extra_args = [a for a in sys.argv[1:] if a != "--elevated"]
    if is_compiled_binary():
        target_cmd = [str(get_real_executable()), *extra_args, "--elevated"]
    else:
        script = str((Path(__file__).resolve().parent / "zapret_manager.py").resolve())
        target_cmd = [sys.executable, script, *extra_args, "--elevated"]
    try:
        has_tty = bool(sys.stdin and sys.stdin.isatty())
        if not has_tty and shutil.which("pkexec") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            env_pairs = [
                f"{k}={os.environ[k]}"
                for k in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "QT_QPA_PLATFORM")
                if os.environ.get(k)
            ]
            os.execvp("pkexec", ["pkexec", "env", *env_pairs, *target_cmd] if env_pairs else ["pkexec", *target_cmd])
        elif shutil.which("sudo"):
            os.execvp("sudo", ["sudo", "-E", *target_cmd])
        elif shutil.which("pkexec"):
            os.execvp("pkexec", ["pkexec", *target_cmd])
    except Exception:
        pass


if IS_WINDOWS:
    _TH32CS_SNAPPROCESS = 0x00000002
    _INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    _kernel32.Process32FirstW.restype = wintypes.BOOL
    _kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    _kernel32.Process32NextW.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
else:
    _kernel32 = None


def iter_processes() -> dict[int, str]:
    pids: dict[int, str] = {}
    if IS_WINDOWS:
        snap = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        if snap == _INVALID_HANDLE_VALUE or snap is None:
            return pids
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
            if _kernel32.Process32FirstW(snap, ctypes.byref(entry)):
                while True:
                    pids[int(entry.th32ProcessID)] = entry.szExeFile.lower()
                    if not _kernel32.Process32NextW(snap, ctypes.byref(entry)):
                        break
        finally:
            _kernel32.CloseHandle(snap)
        return pids

    proc_dir = Path("/proc")
    if not proc_dir.is_dir():
        return pids
    for entry in proc_dir.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            raw_cmd = (entry / "cmdline").read_bytes()
            if raw_cmd:
                exe = Path(raw_cmd.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")).name.lower()
                if exe:
                    pids[pid] = exe
                    continue
            comm = (entry / "comm").read_text(encoding="utf-8", errors="ignore").strip().lower()
            if comm:
                pids[pid] = comm
        except OSError:
            continue
    return pids


def _is_engine_proc_name(name: str) -> bool:
    if IS_WINDOWS:
        return name == "winws.exe"
    return name == "nfqws" or name.startswith("nfqws-linux-")


def is_winws_running() -> bool:
    try:
        return any(_is_engine_proc_name(n) for n in iter_processes().values())
    except Exception:
        return False


def get_winws_pids() -> list[int]:
    try:
        return [pid for pid, name in iter_processes().items() if _is_engine_proc_name(name)]
    except Exception:
        return []


def cleanup_linux_firewall() -> None:
    if not IS_LINUX:
        return
    if shutil.which("nft"):
        try:
            subprocess.run(["nft", "delete", "table", "inet", LINUX_NFT_TABLE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except Exception:
            pass
    for ipt in ("iptables", "ip6tables"):
        if not shutil.which(ipt):
            continue
        for proto, dports in (
            ("tcp", "80,443,2053,2083,2087,2096,5222,8443"),
            ("tcp", "80,443,2053,2083,2087,2096,8443"),
            ("udp", "443,19294:19344,50000:50100"),
            ("udp", "443,19294:19344,50000:65535"),
            ("udp", "443,19294:19344,12"),
        ):
            for _ in range(3):
                try:
                    res = subprocess.run(
                        [
                            ipt, "-t", "mangle", "-D", "POSTROUTING",
                            "-p", proto, "-m", "multiport", "--dports", dports,
                            "-m", "mark", "!", "--mark", f"{LINUX_FWMARK:#x}/{LINUX_FWMARK:#x}",
                            "-j", "NFQUEUE", "--queue-num", str(LINUX_NFQ_NUM), "--queue-bypass",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=3,
                    )
                    if res.returncode != 0:
                        break
                except Exception:
                    break


def setup_linux_firewall(udp_ports: str) -> tuple[bool, str]:
    if not IS_LINUX:
        return True, ""
    cleanup_linux_firewall()

    nft_udp = udp_ports.replace(",", ", ")
    if shutil.which("nft"):
        script = (
            f"add table inet {LINUX_NFT_TABLE}\n"
            f"add chain inet {LINUX_NFT_TABLE} postrouting {{ type filter hook postrouting priority mangle; policy accept; }}\n"
            f"add rule inet {LINUX_NFT_TABLE} postrouting meta mark & {LINUX_FWMARK:#x} != 0 return\n"
            f"add rule inet {LINUX_NFT_TABLE} postrouting tcp dport {{ 80, 443, 2053, 2083, 2087, 2096, 5222, 8443 }} queue num {LINUX_NFQ_NUM} bypass\n"
            f"add rule inet {LINUX_NFT_TABLE} postrouting udp dport {{ {nft_udp} }} queue num {LINUX_NFQ_NUM} bypass\n"
        )
        try:
            res = subprocess.run(["nft", "-f", "-"], input=script, text=True, capture_output=True, timeout=5)
            if res.returncode == 0:
                return True, "nftables"
        except Exception:
            pass

    ipt_udp = udp_ports.replace("-", ":")
    ok_any = False
    last_err = ""
    for ipt in ("iptables", "ip6tables"):
        if not shutil.which(ipt):
            continue
        ok_family = True
        for proto, dports in (("tcp", "80,443,2053,2083,2087,2096,5222,8443"), ("udp", ipt_udp)):
            res = subprocess.run(
                [
                    ipt, "-t", "mangle", "-I", "POSTROUTING",
                    "-p", proto, "-m", "multiport", "--dports", dports,
                    "-m", "mark", "!", "--mark", f"{LINUX_FWMARK:#x}/{LINUX_FWMARK:#x}",
                    "-j", "NFQUEUE", "--queue-num", str(LINUX_NFQ_NUM), "--queue-bypass",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                ok_family = False
                last_err = (res.stderr or res.stdout or "").strip()
        if ipt == "iptables" and ok_family:
            ok_any = True

    if ok_any:
        return True, "iptables"
    return False, last_err or "Не найден nftables (nft) или iptables для перехвата NFQUEUE"


def kill_winws(timeout: float = 3.0) -> bool:
    if IS_WINDOWS:
        if not is_winws_running():
            return True
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", "winws.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=5,
            )
        except Exception:
            pass
    else:
        for pid in get_winws_pids():
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        if is_winws_running():
            time.sleep(0.3)
            for pid in get_winws_pids():
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        cleanup_linux_firewall()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_winws_running():
            return True
        time.sleep(0.1)
    return not is_winws_running()


def cleanup_windivert() -> None:
    if not IS_WINDOWS:
        cleanup_linux_firewall()
        return
    for svc in ("WinDivert", "WinDivert14"):
        try:
            subprocess.run(
                ["sc", "stop", svc],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=3,
            )
        except Exception:
            pass


def ensure_tg_secret(cfg: dict) -> str:
    raw = str(cfg.get("tg_proxy_secret", "") or "").strip().lower()
    if raw.startswith("dd") and len(raw) == 34:
        raw = raw[2:]
    if len(raw) == 32 and all(c in "0123456789abcdef" for c in raw):
        cfg["tg_proxy_secret"] = raw
        return raw
    secret = os.urandom(16).hex()
    cfg["tg_proxy_secret"] = secret
    return secret


def default_config() -> dict:
    return {
        "strategy": STRATEGIES[0]["args"],
        "index": 1,
        "udp_mode": "narrow",
        "fake_sni": "www.sferum.ru",
        "minimize_to_tray": True,
        "tg_dpi_bypass": True,
        "tg_proxy_enabled": True,
        "tg_proxy_port": 1443,
        "tg_proxy_secret": "",
        "desktop_shortcut_created": False,
    }


def load_config() -> dict:
    cfg = default_config()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if data.get("strategy"):
                    cfg["strategy"] = str(data["strategy"])
                if isinstance(data.get("index"), int):
                    cfg["index"] = data["index"]
                if data.get("udp_mode") in ("narrow", "wide", "disabled"):
                    cfg["udp_mode"] = data["udp_mode"]
                if data.get("fake_sni"):
                    cfg["fake_sni"] = str(data["fake_sni"])
                if isinstance(data.get("minimize_to_tray"), bool):
                    cfg["minimize_to_tray"] = data["minimize_to_tray"]
                if isinstance(data.get("tg_dpi_bypass"), bool):
                    cfg["tg_dpi_bypass"] = data["tg_dpi_bypass"]
                if isinstance(data.get("tg_proxy_enabled"), bool):
                    cfg["tg_proxy_enabled"] = data["tg_proxy_enabled"]
                if isinstance(data.get("tg_proxy_port"), int) and 1024 <= data["tg_proxy_port"] <= 65535:
                    cfg["tg_proxy_port"] = data["tg_proxy_port"]
                if data.get("tg_proxy_secret"):
                    raw_s = str(data.get("tg_proxy_secret")).strip().lower()
                    if raw_s.startswith("dd") and len(raw_s) == 34:
                        raw_s = raw_s[2:]
                    if len(raw_s) == 32 and all(c in "0123456789abcdef" for c in raw_s):
                        cfg["tg_proxy_secret"] = raw_s
                if isinstance(data.get("desktop_shortcut_created"), bool):
                    cfg["desktop_shortcut_created"] = data["desktop_shortcut_created"]
        except Exception:
            pass
    return cfg


def save_config(config: dict) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def _migrate_legacy_programdata() -> None:
    if not IS_WINDOWS:
        return
    legacy_dir = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "UnfitZapret"
    if legacy_dir == WORK_DIR or not legacy_dir.is_dir() or CONFIG_FILE.exists():
        return
    try:
        old_cfg = legacy_dir / "zapret_config.json"
        if old_cfg.is_file():
            shutil.copy2(old_cfg, CONFIG_FILE)
        old_lists = legacy_dir / "lists"
        if old_lists.is_dir():
            for item in old_lists.iterdir():
                if item.is_file() and item.name.endswith("-user.txt"):
                    dst = LISTS_DIR / item.name
                    if not dst.exists():
                        shutil.copy2(item, dst)
    except OSError:
        pass


def _grant_work_dir_user_access() -> None:
    if not IS_WINDOWS or not WORK_DIR.exists():
        return
    marker = WORK_DIR / ".acl_ready"
    if marker.exists():
        return
    try:
        res = subprocess.run(
            ["icacls", str(WORK_DIR), "/grant", "*S-1-5-32-545:(OI)(CI)M", "/T", "/Q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=8,
        )
        if res.returncode == 0:
            marker.write_text("1", encoding="utf-8")
    except Exception:
        pass


def ensure_files_exist() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    LISTS_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_programdata()

    emb_zip = get_embedded_assets_zip()
    if emb_zip is not None:
        marker_file = WORK_DIR / ".assets_version"
        current_marker = ""
        if marker_file.exists():
            try:
                current_marker = marker_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        need_update = (current_marker != APP_VERSION)
        winws_busy = is_winws_running()

        try:
            with zipfile.ZipFile(emb_zip, "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    rel = member.filename.replace("\\", "/").lstrip("/")
                    if rel.startswith("bin/"):
                        fname = rel[4:]
                        if not fname or "/" in fname or fname == "]":
                            continue
                        if IS_WINDOWS and fname.startswith("nfqws"):
                            continue
                        if IS_LINUX and fname.lower().endswith((".exe", ".dll", ".sys")):
                            continue
                        dst = BIN_DIR / fname
                        if not dst.exists() or (need_update and not winws_busy):
                            try:
                                dst.write_bytes(zf.read(member))
                                if IS_LINUX and fname.startswith("nfqws"):
                                    os.chmod(dst, 0o755)
                            except OSError:
                                pass
                    elif rel.startswith("lists/"):
                        fname = rel[6:]
                        if not fname or "/" in fname:
                            continue
                        dst = LISTS_DIR / fname
                        is_user_list = fname.endswith("-user.txt")
                        if not dst.exists() or (need_update and not is_user_list):
                            try:
                                dst.write_bytes(zf.read(member))
                            except OSError:
                                pass
                    elif rel == "app_icon.ico":
                        dst = WORK_DIR / "app_icon.ico"
                        if not dst.exists() or need_update:
                            try:
                                dst.write_bytes(zf.read(member))
                            except OSError:
                                pass
            if not winws_busy or not current_marker:
                try:
                    marker_file.write_text(APP_VERSION, encoding="utf-8")
                except OSError:
                    pass
        except Exception:
            pass

    if IS_LINUX and BIN_DIR.exists():
        # На Linux даём права на запуск бинарникам nfqws
        for p in BIN_DIR.iterdir():
            if p.is_file() and p.name.startswith("nfqws"):
                try:
                    os.chmod(p, 0o755)
                except OSError:
                    pass

    for filename in REQUIRED_LIST_FILES:
        file_path = LISTS_DIR / filename
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Автоматически созданный файл: {filename}\n")
    _grant_work_dir_user_access()


def resolve_udp_ports(udp_mode: str) -> tuple[str, str]:
    if udp_mode == "wide":
        return "443,19294-19344,50000-65535", "19294-19344,50000-65535"
    if udp_mode == "narrow":
        return "443,19294-19344,50000-50100", "19294-19344,50000-50100"
    return "443,19294-19344,12", "19294-19344,12"


def _bin_asset(name: str, fallback: str = "") -> str:
    p = BIN_DIR / name
    if p.exists() or not fallback:
        return p.as_posix()
    fb = BIN_DIR / fallback
    return fb.as_posix() if fb.exists() else p.as_posix()


def get_winws_args(strategy_str: str, config: dict, log_cb: Optional[Callable[[str], None]] = None) -> list[str]:
    fake_sni = config.get("fake_sni", "www.sferum.ru")
    udp_mode = config.get("udp_mode", "narrow")
    tg_dpi_bypass = bool(config.get("tg_dpi_bypass", True))

    if fake_sni == "random":
        available = [s for s in POPULAR_SNIS if s != "random"]
        resolved_sni = random.choice(available)
        if log_cb:
            log_cb(f"[SNI] Выбран случайный отпечаток: {resolved_sni}")
    else:
        resolved_sni = fake_sni

    tls_google = _bin_asset("tls_clienthello_www_google_com.bin")
    tls_sferum = _bin_asset("tls_clienthello_www_sferum_ru.bin", "tls_clienthello_max_ru.bin")
    tls_sochi = _bin_asset("tls_clienthello_sochi_park.bin", "tls_clienthello_www_google_com.bin")
    tls_5ka = _bin_asset("tls_clienthello_5ka_ru.bin", "tls_clienthello_max_ru.bin")
    tls_max = _bin_asset("tls_clienthello_max_ru.bin")
    tls_4pda = _bin_asset("tls_clienthello_4pda_to.bin")
    stun2 = _bin_asset("stun2.bin", "stun.bin")
    stun = _bin_asset("stun.bin")
    quic_google = _bin_asset("quic_initial_www_google_com.bin")
    quic_5ka = _bin_asset("quic_initial_5ka_ru.bin", "quic_initial_www_google_com.bin")
    discord_udp = _bin_asset("ACTIVE_DISCORD_UDP.bin", "quic_initial_www_google_com.bin")
    game_udp = _bin_asset("ACTIVE_GAME_UDP.bin", "quic_initial_www_google_com.bin")

    resolved_strategy = (
        strategy_str
        .replace("{fake_sni}", resolved_sni)
        .replace("{tls_google}", tls_google)
        .replace("{tls_sferum}", tls_sferum)
        .replace("{tls_sochi}", tls_sochi)
        .replace("{tls_5ka}", tls_5ka)
        .replace("{tls_max}", tls_max)
        .replace("{tls_4pda}", tls_4pda)
        .replace("{stun2}", stun2)
        .replace("{stun}", stun)
        .replace("{quic_google}", quic_google)
        .replace("{quic_5ka}", quic_5ka)
        .replace("{discord_udp}", discord_udp)
        .replace("{game_udp}", game_udp)
    )
    udp_ports, udp_voice_filter = resolve_udp_ports(udp_mode)
    strat_parts = resolved_strategy.split()

    if "--dpi-desync-split-seqovl=681" in resolved_strategy and not any(
        x.startswith("--dpi-desync-split-seqovl-pattern") for x in strat_parts
    ):
        strat_parts.append(f"--dpi-desync-split-seqovl-pattern={tls_google}")
    elif "--dpi-desync-split-seqovl=664" in resolved_strategy and not any(
        x.startswith("--dpi-desync-split-seqovl-pattern") for x in strat_parts
    ):
        strat_parts.append(f"--dpi-desync-split-seqovl-pattern={tls_sferum}")

    desync_modes = next((x.split("=", 1)[1].split(",") for x in strat_parts if x.startswith("--dpi-desync=")), [])
    uses_fake = any(m in ("fake", "fakedsplit", "fakeddisorder", "fakeknown") for m in desync_modes)
    has_fake_tls = any(x.startswith("--dpi-desync-fake-tls=") for x in strat_parts)
    has_fake_http = any(x.startswith("--dpi-desync-fake-http=") for x in strat_parts)

    google_fake_args = [f"--dpi-desync-fake-tls={tls_google}"] if (uses_fake and not has_fake_tls) else []
    gen_fake_args: list[str] = []
    if uses_fake and not has_fake_tls:
        gen_fake_args.extend((f"--dpi-desync-fake-tls={stun2}", f"--dpi-desync-fake-tls={tls_sferum}"))
    if uses_fake and not has_fake_http:
        gen_fake_args.append(f"--dpi-desync-fake-http={tls_sferum}")

    engine_bin = str(get_engine_binary())
    if IS_WINDOWS:
        prefix = [
            engine_bin,
            "--wf-tcp=80,443,2053,2083,2087,2096,5222,8443",
            f"--wf-udp={udp_ports}",
        ]
    else:
        # Fwmark чтобы nfqws не зацикливал собственные пакеты в очереди
        prefix = [
            engine_bin,
            f"--qnum={LINUX_NFQ_NUM}",
            f"--dpi-desync-fwmark={LINUX_FWMARK}",
            "--uid=0:0",
        ]

    args = [
        *prefix,
        # UDP Discord Voice & STUN
        f"--filter-udp={udp_voice_filter}",
        "--filter-l7=discord,stun",
        "--dpi-desync=fake",
        "--dpi-desync-repeats=6",
        f"--dpi-desync-fake-discord={discord_udp}",
        f"--dpi-desync-fake-stun={discord_udp}",
        "--new",
        # UDP 443 General
        "--filter-udp=443",
        f'--hostlist={(LISTS_DIR / "list-general.txt").as_posix()}',
        f'--hostlist={(LISTS_DIR / "list-general-user.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude-user.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude-user.txt").as_posix()}',
        "--dpi-desync=fake",
        "--dpi-desync-repeats=11",
        f"--dpi-desync-fake-quic={quic_google}",
        "--new",
        # TCP Discord Media
        "--filter-tcp=2053,2083,2087,2096,8443",
        "--hostlist-domains=discord.media",
        *google_fake_args,
        *strat_parts,
        "--new",
        # TCP Google & Gemini
        "--filter-tcp=443",
        f'--hostlist={(LISTS_DIR / "list-google.txt").as_posix()}',
        f'--hostlist={(LISTS_DIR / "list-gemini.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude-user.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude-user.txt").as_posix()}',
        "--ip-id=zero",
        *google_fake_args,
        *strat_parts,
        "--new",
    ]

    if tg_dpi_bypass:
        tg_unknown_fake = [f"--dpi-desync-fake-unknown={tls_sferum}"] if uses_fake else []
        args.extend([
            # Telegram QUIC UDP 443
            "--filter-udp=443",
            f'--hostlist={(LISTS_DIR / "list-telegram.txt").as_posix()}',
            "--dpi-desync=fake",
            "--dpi-desync-repeats=11",
            f"--dpi-desync-fake-quic={quic_5ka}",
            "--new",
            # Telegram Web/WS TCP
            "--filter-tcp=80,443",
            f'--hostlist={(LISTS_DIR / "list-telegram.txt").as_posix()}',
            *gen_fake_args,
            *strat_parts,
            "--new",
            # Telegram Direct DC MTProto TCP
            "--filter-tcp=80,443,5222",
            f'--ipset={(LISTS_DIR / "ipset-telegram.txt").as_posix()}',
            "--dpi-desync-any-protocol=1",
            "--dpi-desync-cutoff=n4",
            *gen_fake_args,
            *tg_unknown_fake,
            *strat_parts,
            "--new",
        ])

    args.extend([
        # TCP General (HTTP/HTTPS)
        "--filter-tcp=80,443",
        f'--hostlist={(LISTS_DIR / "list-general.txt").as_posix()}',
        f'--hostlist={(LISTS_DIR / "list-general-user.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude-user.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude-user.txt").as_posix()}',
        *gen_fake_args,
        *strat_parts,
        "--new",
        # UDP Fallback (ipset-all)
        "--filter-udp=443",
        f'--ipset={(LISTS_DIR / "ipset-all.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude-user.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude-user.txt").as_posix()}',
        "--dpi-desync=fake",
        "--dpi-desync-repeats=11",
        f"--dpi-desync-fake-quic={quic_google}",
        "--new",
        # TCP Fallback (ipset-all)
        "--filter-tcp=80,443,8443",
        f'--ipset={(LISTS_DIR / "ipset-all.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude.txt").as_posix()}',
        f'--hostlist-exclude={(LISTS_DIR / "list-exclude-user.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude.txt").as_posix()}',
        f'--ipset-exclude={(LISTS_DIR / "ipset-exclude-user.txt").as_posix()}',
        *gen_fake_args,
        *strat_parts,
        "--new",
    ])
    return args


def start_bypass_background(log_cb: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
    # Запуск без PIPE, при стартовом сбое чистим драйвер/правила и повторяем
    ensure_files_exist()
    cfg = load_config()
    strat = cfg.get("strategy", "") or STRATEGIES[0]["args"]
    engine_bin = get_engine_binary()
    engine_name = engine_bin.name
    if not engine_bin.exists():
        return False, f"{engine_name} не найден в {BIN_DIR}"

    kill_winws()
    udp_ports, _ = resolve_udp_ports(cfg.get("udp_mode", "narrow"))
    if IS_LINUX:
        fw_ok, fw_info = setup_linux_firewall(udp_ports)
        if not fw_ok:
            return False, f"Ошибка настройки фаервола (нужен root и nft/iptables): {fw_info}"

    cmd = get_winws_args(strat, cfg, log_cb=log_cb)

    def _spawn(capture_err: bool = False) -> tuple[Optional[subprocess.Popen], str]:
        kwargs = dict(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture_err else subprocess.DEVNULL,
            cwd=str(BIN_DIR),
            close_fds=True,
        )
        if not IS_WINDOWS:
            try:
                proc = subprocess.Popen(cmd, start_new_session=True, **kwargs)
                return proc, ""
            except PermissionError:
                return None, "Требуются права root для запуска nfqws и NFQUEUE"
            except Exception as e:
                return None, f"Ошибка запуска {engine_name}: {e}"

        for flags in (BACKGROUND_FLAGS | CREATE_BREAKAWAY_FROM_JOB, BACKGROUND_FLAGS):
            try:
                proc = subprocess.Popen(cmd, creationflags=flags, **kwargs)
                return proc, ""
            except FileNotFoundError:
                return None, f"{engine_name} не найден в {BIN_DIR}"
            except PermissionError:
                # Job object может запрещать breakaway
                if flags != BACKGROUND_FLAGS:
                    continue
                return None, "Требуются права Администратора для запуска WinDivert"
            except OSError as e:
                if flags != BACKGROUND_FLAGS and getattr(e, "winerror", None) == 5:
                    continue
                if "740" in str(e):
                    return None, "Требуются права Администратора для запуска WinDivert"
                return None, f"Ошибка запуска {engine_name}: {e}"
        return None, f"Не удалось запустить {engine_name}"

    proc, err_msg = _spawn(capture_err=False)
    if proc is None:
        if IS_LINUX:
            cleanup_linux_firewall()
        return False, err_msg

    for _ in range(6):
        time.sleep(0.2)
        if proc.poll() is not None:
            cleanup_windivert()
            if IS_LINUX:
                setup_linux_firewall(udp_ports)
            time.sleep(0.5)
            diag_proc, diag_err = _spawn(capture_err=True)
            if diag_proc is None:
                if IS_LINUX:
                    cleanup_linux_firewall()
                return False, diag_err
            time.sleep(1.0)
            if diag_proc.poll() is not None:
                err_out = ""
                try:
                    if diag_proc.stderr:
                        err_out = diag_proc.stderr.read().decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass
                if IS_LINUX:
                    cleanup_linux_firewall()
                return False, f"{engine_name} завершился сразу после запуска{': ' + err_out[:200] if err_out else ''}"
            # Повтор без PIPE, чтобы буфер не забился
            kill_winws()
            if IS_LINUX:
                setup_linux_firewall(udp_ports)
            clean_proc, clean_err = _spawn(capture_err=False)
            if clean_proc is None:
                if IS_LINUX:
                    cleanup_linux_firewall()
                return False, clean_err
            time.sleep(0.8)
            if clean_proc.poll() is not None:
                if IS_LINUX:
                    cleanup_linux_firewall()
                return False, f"{engine_name} повторно завершился после запуска"
            return True, "Обход успешно запущен (после сброса фильтра)"

    return True, "Обход успешно запущен в фоне"


def check_url(url: str, timeout: int = 4) -> tuple[bool, str]:
    try:
        res = subprocess.run(
            [
                CURL_EXE,
                "-k",
                "-4",
                "-s",
                "-o",
                os.devnull,
                "-w",
                "%{http_code}",
                "--max-time",
                str(timeout),
                "--connect-timeout",
                str(timeout),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            **_subproc_hidden_kwargs(),
        )
        code = res.stdout.strip()
        ok = code in {"200", "204", "301", "302", "307", "308", "403"}
        return ok, code if code and code != "000" else "TIMEOUT"
    except Exception as e:
        return False, str(e)


def check_sites_parallel(timeout: int = 4) -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=len(TEST_TARGETS)) as pool:
        future_map = {pool.submit(check_url, url, timeout): key for key, _, url in TEST_TARGETS}
        for fut in as_completed(future_map):
            key = future_map[fut]
            try:
                results[key] = fut.result()
            except Exception as e:
                results[key] = (False, str(e))
    return results


def _run_powershell(script: str, timeout: int = 20) -> tuple[int, str, str]:
    full = (
        "$ErrorActionPreference = 'Stop'\n"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "$OutputEncoding = [System.Text.Encoding]::UTF8\n"
        + script
    )
    encoded = base64.b64encode(full.encode("utf-16le")).decode("ascii")
    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
        out = res.stdout.decode("utf-8", errors="ignore").strip()
        err = res.stderr.decode("utf-8", errors="ignore").strip()
        return res.returncode, out, err
    except Exception as e:
        return 1, "", str(e)


def get_installed_executable() -> Path:
    if IS_WINDOWS and is_compiled_binary():
        return WORK_DIR / "Unfit-Zapret.exe"
    return get_real_executable()


def install_binary_to_work_dir() -> tuple[bool, Path, str]:
    real_exe = get_real_executable()
    if not (IS_WINDOWS and is_compiled_binary()):
        return True, real_exe, ""
    target = get_installed_executable()
    if os.path.normcase(os.path.normpath(str(real_exe))) == os.path.normcase(os.path.normpath(str(target))):
        return True, target, ""
    if not real_exe.is_file():
        return False, target, ""
    try:
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            st_src = real_exe.stat()
            st_dst = target.stat()
            if st_src.st_size == st_dst.st_size and abs(st_src.st_mtime - st_dst.st_mtime) < 2.0:
                return True, target, ""
        tmp = target.with_name("Unfit-Zapret.exe.tmp")
        shutil.copy2(real_exe, tmp)
        os.replace(tmp, target)
        return True, target, f"Программа скопирована в {target}"
    except OSError:
        return False, real_exe, ""


def get_desktop_dir() -> Path:
    if IS_WINDOWS:
        rc, out, _ = _run_powershell("Write-Output ([Environment]::GetFolderPath('Desktop'))", timeout=5)
        if rc == 0 and out:
            p = Path(out.splitlines()[-1].strip())
            if p.exists():
                return p
        return Path.home() / "Desktop"

    sudo_user = os.environ.get("SUDO_USER", "").strip()
    if sudo_user:
        try:
            import pwd
            home_dir = Path(pwd.getpwnam(sudo_user).pw_dir)
            d = home_dir / "Desktop"
            if d.is_dir():
                return d
            ru_d = home_dir / "Рабочий стол"
            if ru_d.is_dir():
                return ru_d
            return d
        except Exception:
            pass
    if shutil.which("xdg-user-dir"):
        try:
            res = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                return Path(res.stdout.strip())
        except Exception:
            pass
    return Path.home() / "Desktop"


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def create_desktop_shortcut(
    target_exe: Optional[Path] = None,
    desktop_dir: Optional[Path] = None,
) -> tuple[bool, str]:
    desk = desktop_dir or get_desktop_dir()
    desk.mkdir(parents=True, exist_ok=True)

    if IS_WINDOWS:
        if target_exe is not None:
            exe_path = Path(target_exe)
        elif is_compiled_binary():
            inst = get_installed_executable()
            exe_path = inst if inst.exists() else get_real_executable()
        else:
            py_exe = Path(sys.executable).resolve()
            pyw = py_exe.with_name("pythonw.exe")
            exe_path = pyw if pyw.exists() else py_exe

        lnk_path = desk / "Unfit Zapret.lnk"
        ico_candidate = WORK_DIR / "app_icon.ico"
        if not ico_candidate.is_file():
            ico_candidate = Path(__file__).resolve().parent / "app_icon.ico"
        icon_loc = str(ico_candidate) if ico_candidate.is_file() else f"{exe_path},0"
        args_str = "" if (is_compiled_binary() or target_exe is not None) else f'"{(Path(__file__).resolve().parent / "zapret_manager.py").resolve()}"'
        ps = (
            "$ws = New-Object -ComObject WScript.Shell\n"
            f"$sc = $ws.CreateShortcut({_ps_quote(str(lnk_path))})\n"
            f"$sc.TargetPath = {_ps_quote(str(exe_path))}\n"
            f"$sc.Arguments = {_ps_quote(args_str)}\n"
            f"$sc.WorkingDirectory = {_ps_quote(str(WORK_DIR))}\n"
            f"$sc.IconLocation = {_ps_quote(icon_loc)}\n"
            f"$sc.Description = {_ps_quote('Unfit Zapret — обход DPI, Telegram WS-Мост и DNS-AI')}\n"
            "$sc.Save()\n"
        )
        rc, _, err = _run_powershell(ps, timeout=10)
        if rc == 0 and lnk_path.is_file():
            return True, f"Ярлык создан на рабочем столе: {lnk_path}"
        return False, f"Не удалось создать ярлык: {err or 'ошибка WScript.Shell'}"

    desktop_file = desk / "Unfit-Zapret.desktop"
    script_or_bin = (
        str(get_real_executable())
        if is_compiled_binary()
        else f"bash {Path(__file__).resolve().parent / 'start_linux.sh'}"
    )
    entry = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Unfit Zapret\n"
        "Comment=DPI bypass, Telegram WS-Proxy & DNS-AI\n"
        f"Exec={script_or_bin}\n"
        f"Path={WORK_DIR}\n"
        "Terminal=false\n"
        "Categories=Network;\n"
    )
    try:
        desktop_file.write_text(entry, encoding="utf-8")
        os.chmod(desktop_file, 0o755)
        sudo_user = os.environ.get("SUDO_USER", "").strip()
        if sudo_user:
            try:
                import pwd
                pw = pwd.getpwnam(sudo_user)
                os.chown(desktop_file, pw.pw_uid, pw.pw_gid)
            except Exception:
                pass
        return True, f"Ярлык создан на рабочем столе: {desktop_file}"
    except OSError as e:
        return False, f"Не удалось создать ярлык: {e}"


def ensure_installed_and_shortcut() -> list[str]:
    notes: list[str] = []
    if not (IS_WINDOWS and is_compiled_binary()):
        return notes
    ok_inst, target, msg_inst = install_binary_to_work_dir()
    if msg_inst:
        notes.append(msg_inst)
    cfg = load_config()
    if not cfg.get("desktop_shortcut_created", False):
        ok_lnk, msg_lnk = create_desktop_shortcut(target if ok_inst else None)
        if ok_lnk:
            cfg["desktop_shortcut_created"] = True
            try:
                save_config(cfg)
            except OSError:
                pass
        notes.append(msg_lnk)
    return notes


def get_self_launch_spec() -> tuple[str, str, str]:
    if is_compiled_binary():
        installed_exe = get_installed_executable()
        exe_path = installed_exe if (IS_WINDOWS and installed_exe.exists()) else get_real_executable()
        return str(exe_path), "--background", str(exe_path.parent)
    script_path = (
        Path(sys.argv[0]).resolve()
        if (sys.argv and sys.argv[0] and Path(sys.argv[0]).exists())
        else (Path(__file__).resolve().parent / "zapret_manager.py").resolve()
    )
    py_exe = Path(sys.executable).resolve()
    if IS_WINDOWS:
        pyw_exe = py_exe.with_name("pythonw.exe")
        chosen_py = str(pyw_exe if pyw_exe.exists() else py_exe)
        return chosen_py, f'"{script_path}" --background', str(script_path.parent)
    return str(py_exe), f'"{script_path}" --background', str(script_path.parent)


def _normalize_path_str(p: str) -> str:
    return os.path.normcase(os.path.normpath(p.strip().strip('"')))


def _linux_unit_path() -> Path:
    return Path(f"/etc/systemd/system/{SYSTEMD_SERVICE}")


def get_autorun_info() -> dict:
    expected_cmd, expected_args, expected_wd = get_self_launch_spec()
    if not IS_WINDOWS:
        unit_file = _linux_unit_path()
        if not unit_file.exists():
            return {"enabled": False, "path_matches": False, "command": "", "error": ""}
        exec_line = ""
        try:
            for line in unit_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("ExecStart="):
                    exec_line = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
        enabled = False
        if shutil.which("systemctl"):
            try:
                res = subprocess.run(["systemctl", "is-enabled", SYSTEMD_SERVICE], capture_output=True, text=True, timeout=5)
                enabled = res.returncode == 0 and res.stdout.strip() in ("enabled", "static")
            except Exception:
                pass
        expected_full = f"{expected_cmd} {expected_args}".strip()
        path_matches = enabled and (expected_cmd in exec_line) and (expected_args in exec_line)
        return {
            "enabled": enabled,
            "path_matches": path_matches,
            "command": exec_line,
            "expected": expected_full,
            "error": "",
        }

    try:
        res = subprocess.run(
            ["schtasks", "/query", "/tn", TASK_NAME, "/xml"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=5,
        )
    except Exception as e:
        return {"enabled": False, "path_matches": False, "command": "", "error": str(e)}

    if res.returncode != 0:
        err_bytes = res.stderr or res.stdout or b""
        err_text = err_bytes.decode("cp866", errors="ignore").strip()
        return {
            "enabled": False,
            "path_matches": False,
            "command": "",
            "error": "access_denied" if "denied" in err_text.lower() or "отказано" in err_text.lower() else "",
        }

    xml_bytes = res.stdout
    xml_text = ""
    for enc in ("utf-16", "utf-8-sig", "utf-8", "cp1251"):
        try:
            xml_text = xml_bytes.decode(enc)
            if "<Task" in xml_text:
                break
        except Exception:
            continue

    cmd_val = ""
    args_val = ""
    path_matches = False
    try:
        root = ET.fromstring(xml_text)
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        cmd_el = root.find(".//t:Exec/t:Command", ns)
        args_el = root.find(".//t:Exec/t:Arguments", ns)
        if cmd_el is not None and cmd_el.text:
            cmd_val = cmd_el.text.strip()
        if args_el is not None and args_el.text:
            args_val = args_el.text.strip()

        if cmd_val:
            cmd_norm = _normalize_path_str(cmd_val)
            exp_norm = _normalize_path_str(expected_cmd)
            path_matches = (cmd_norm == exp_norm) and ("--background" in args_val)
    except Exception:
        pass

    return {
        "enabled": True,
        "path_matches": path_matches,
        "command": f"{cmd_val} {args_val}".strip(),
        "expected": f"{expected_cmd} {expected_args}".strip(),
        "error": "",
    }


def _build_task_xml(command: str, arguments: str, working_dir: str) -> str:
    cmd_esc = xml_escape(command)
    args_esc = xml_escape(arguments)
    wd_esc = xml_escape(working_dir)
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Unfit Zapret - автоматический запуск обхода DPI при старте Windows и входе в систему</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT10S</Delay>
    </BootTrigger>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT3S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>false</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{cmd_esc}</Command>
      <Arguments>{args_esc}</Arguments>
      <WorkingDirectory>{wd_esc}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def enable_autorun() -> tuple[bool, str]:
    cmd, args, wd = get_self_launch_spec()
    if not IS_WINDOWS:
        if not shutil.which("systemctl"):
            return False, "systemd (systemctl) не найден в системе"
        stop_args = args.replace("--background", "--stop") if "--background" in args else f"{args} --stop".strip()
        unit_content = (
            "[Unit]\n"
            "Description=Unfit Zapret DPI Bypass\n"
            "After=network-online.target\n"
            "Wants=network-online.target\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            "RemainAfterExit=yes\n"
            f"WorkingDirectory={wd}\n"
            f"ExecStart={cmd} {args}\n"
            f"ExecStop={cmd} {stop_args}\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        try:
            _linux_unit_path().write_text(unit_content, encoding="utf-8")
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=10)
            res = subprocess.run(["systemctl", "enable", SYSTEMD_SERVICE], capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                return True, f"Автозапуск включён ({SYSTEMD_SERVICE})"
            return False, f"Ошибка systemctl enable: {(res.stderr or res.stdout).strip()}"
        except PermissionError:
            return False, "Нужны права root для настройки systemd-сервиса"
        except Exception as e:
            return False, f"Ошибка настройки systemd: {e}"

    xml_content = _build_task_xml(cmd, args, wd)

    old_bat = WORK_DIR / "autorun_helper.bat"
    if old_bat.exists():
        try:
            old_bat.unlink()
        except Exception:
            pass

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".xml", encoding="utf-16", delete=False) as tf:
            tf.write(xml_content)
            tmp_path = tf.name

        res = subprocess.run(
            ["schtasks", "/create", "/tn", TASK_NAME, "/xml", tmp_path, "/f"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
        )
        if res.returncode == 0:
            return True, "Автозапуск включён (Boot + Logon, с правами SYSTEM)"
        err = (res.stderr or res.stdout or b"").decode("cp866", errors="ignore").strip()
        return False, f"Ошибка Планировщика задач: {err or res.returncode}"
    except Exception as e:
        return False, f"Не удалось настроить автозапуск: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def disable_autorun() -> tuple[bool, str]:
    if not IS_WINDOWS:
        try:
            if shutil.which("systemctl"):
                subprocess.run(["systemctl", "disable", SYSTEMD_SERVICE], capture_output=True, timeout=10)
            unit_file = _linux_unit_path()
            if unit_file.exists():
                unit_file.unlink()
            if shutil.which("systemctl"):
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=10)
            return True, "Автозапуск (systemd) отключён"
        except PermissionError:
            return False, "Нужны права root для отключения автозапуска"
        except Exception as e:
            return False, f"Ошибка отключения автозапуска: {e}"

    try:
        res = subprocess.run(
            ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
        )
        if res.returncode == 0:
            return True, "Автозапуск отключён"
        err = (res.stderr or res.stdout or b"").decode("cp866", errors="ignore").strip()
        return False, f"Ошибка удаления задачи: {err or res.returncode}"
    except Exception as e:
        return False, f"Ошибка отключения автозапуска: {e}"


def _write_autorun_log(message: str) -> None:
    try:
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        if AUTORUN_LOG_FILE.exists() and AUTORUN_LOG_FILE.stat().st_size > 102_400:
            AUTORUN_LOG_FILE.unlink()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(AUTORUN_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass


def is_tg_proxy_port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.3):
            return True
    except OSError:
        return False


def is_tg_proxy_detached_running() -> bool:
    if not TG_PROXY_PID_FILE.exists():
        return False
    try:
        pid = int(TG_PROXY_PID_FILE.read_text(encoding="utf-8").strip())
        return pid > 0 and pid in iter_processes()
    except Exception:
        return False


def stop_tg_proxy_detached() -> None:
    if TG_PROXY_PID_FILE.exists():
        try:
            pid = int(TG_PROXY_PID_FILE.read_text(encoding="utf-8").strip())
            if pid > 0 and pid in iter_processes():
                if IS_WINDOWS:
                    subprocess.run(
                        ["taskkill", "/f", "/t", "/pid", str(pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=CREATE_NO_WINDOW,
                        timeout=4,
                    )
                else:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass
        except Exception:
            pass
        try:
            TG_PROXY_PID_FILE.unlink()
        except OSError:
            pass


def start_tg_proxy_detached(port: Optional[int] = None) -> tuple[bool, str]:
    ensure_files_exist()
    cfg = load_config()
    target_port = int(port or cfg.get("tg_proxy_port", 1443) or 1443)
    if is_tg_proxy_port_open(target_port):
        return True, f"Telegram WS-Мост уже работает на 127.0.0.1:{target_port}"

    if not cfg.get("tg_proxy_secret"):
        ensure_tg_secret(cfg)
        save_config(cfg)

    cmd_exe, _, wd = get_self_launch_spec()
    if is_compiled_binary():
        spawn_cmd = [cmd_exe, "--tg-proxy"]
    else:
        script = str((Path(__file__).resolve().parent / "zapret_manager.py").resolve())
        spawn_cmd = [cmd_exe, script, "--tg-proxy"]

    kwargs = dict(
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=wd,
        close_fds=True,
    )
    try:
        if IS_WINDOWS:
            proc = subprocess.Popen(spawn_cmd, creationflags=BACKGROUND_FLAGS, **kwargs)
        else:
            proc = subprocess.Popen(spawn_cmd, start_new_session=True, **kwargs)
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        TG_PROXY_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    except Exception as e:
        return False, f"Ошибка запуска TG-Моста: {e}"

    for _ in range(10):
        time.sleep(0.2)
        if is_tg_proxy_port_open(target_port):
            return True, f"Telegram WS-Мост запущен в фоне на 127.0.0.1:{target_port}"
    return proc.poll() is None, f"Telegram WS-Мост запущен (порт {target_port})"


def run_autorun_background() -> int:
    mutex = None
    lock_fd = None
    if IS_WINDOWS and _kernel32 is not None:
        # Мьютекс от параллельного запуска триггеров при старте
        mutex = _kernel32.CreateMutexW(None, False, "Global\\ZapretUltraStableAutoStart")
        last_err = ctypes.get_last_error()
        if last_err == 183:  # ERROR_ALREADY_EXISTS
            _write_autorun_log("Другой экземпляр --background уже запускает обход, выход.")
            if mutex:
                _kernel32.CloseHandle(mutex)
            return 0
    elif IS_LINUX:
        import fcntl
        lock_path = Path(tempfile.gettempdir()) / "unfit-zapret-autostart.lock"
        try:
            lock_fd = open(lock_path, "w")
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if lock_fd:
                lock_fd.close()
            return 0

    try:
        ensure_files_exist()
        cfg = load_config()
        if is_winws_running():
            _write_autorun_log(f"{get_engine_name()} уже запущен, повторный запуск не требуется.")
            if cfg.get("tg_proxy_enabled", True):
                tg_ok, tg_msg = start_tg_proxy_detached()
                _write_autorun_log(f"TG-Мост: ok={tg_ok}, msg={tg_msg}")
            return 0

        for attempt in range(1, 6):
            ok, msg = start_bypass_background(log_cb=_write_autorun_log)
            _write_autorun_log(f"Попытка {attempt}/5: ok={ok}, msg={msg}")
            if ok:
                if cfg.get("tg_proxy_enabled", True):
                    tg_ok, tg_msg = start_tg_proxy_detached()
                    _write_autorun_log(f"TG-Мост: ok={tg_ok}, msg={tg_msg}")
                return 0
            cleanup_windivert()
            time.sleep(3)

        _write_autorun_log("Не удалось запустить обход после 5 попыток.")
        return 1
    except Exception as e:
        _write_autorun_log(f"Исключение в --background: {type(e).__name__}: {e}")
        return 1
    finally:
        if mutex and _kernel32 is not None:
            _kernel32.CloseHandle(mutex)
        if lock_fd is not None:
            try:
                lock_fd.close()
            except Exception:
                pass


def _extract_exclude_ip(
    foreign_addr: str,
    pid: int,
    pids_to_name: dict[int, str],
) -> Optional[tuple[str, str, str, int]]:
    proc_name = pids_to_name.get(pid)
    if not proc_name:
        return None
    is_vpn = any(kw in proc_name for kw in VPN_KEYWORDS)
    is_game = any(kw in proc_name for kw in GAME_KEYWORDS)
    if not (is_vpn or is_game):
        return None

    ip_part = foreign_addr.rsplit(":", 1)[0].strip("[] ")
    try:
        ip_obj = ipaddress.ip_address(ip_part)
    except ValueError:
        return None

    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
        or ip_obj.is_reserved
    ):
        return None

    prefix = 32 if ip_obj.version == 4 else 128
    category = "VPN" if is_vpn else "ИГРА"
    return (str(ip_obj), proc_name, category, prefix)


def _parse_linux_connections(pids_to_name: dict[int, str]) -> tuple[Optional[set[tuple[str, str, str, int]]], str]:
    ips_to_exclude: set[tuple[str, str, str, int]] = set()
    ss_bin = shutil.which("ss")
    if not ss_bin:
        return None, "Утилита ss не найдена"
    try:
        res = subprocess.run([ss_bin, "-tunp", "-H"], capture_output=True, text=True, timeout=10)
        for line in res.stdout.splitlines():
            tokens = line.split()
            if len(tokens) < 6:
                continue
            m_pid = re.search(r"pid=(\d+)", line)
            if not m_pid:
                continue
            item = _extract_exclude_ip(tokens[5], int(m_pid.group(1)), pids_to_name)
            if item:
                ips_to_exclude.add(item)
        return ips_to_exclude, ""
    except Exception as e:
        return None, f"Ошибка ss: {e}"


def scan_and_exclude_active_connections() -> dict:
    pids_to_name = iter_processes()
    if not pids_to_name:
        return {"ok": False, "error": "Не удалось получить список процессов", "added": [], "found_total": 0}

    ips_to_exclude: set[tuple[str, str, str, int]] = set()
    if IS_WINDOWS:
        try:
            res = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=10,
            )
            output = res.stdout.decode("utf-8", errors="ignore")
            for line in output.splitlines():
                tokens = line.strip().split()
                if not tokens or tokens[0] not in ("TCP", "UDP"):
                    continue

                proto = tokens[0]
                if proto == "TCP" and len(tokens) >= 5:
                    foreign_addr, pid_str = tokens[2], tokens[4]
                elif proto == "UDP" and len(tokens) >= 4:
                    foreign_addr, pid_str = tokens[2], tokens[3]
                else:
                    continue

                if foreign_addr in ("*:*", "0.0.0.0:0", "[::]:", ""):
                    continue

                try:
                    pid = int(pid_str)
                except ValueError:
                    continue

                item = _extract_exclude_ip(foreign_addr, pid, pids_to_name)
                if item:
                    ips_to_exclude.add(item)
        except Exception as e:
            return {"ok": False, "error": f"Ошибка netstat: {e}", "added": [], "found_total": 0}
    else:
        parsed_ips, err = _parse_linux_connections(pids_to_name)
        if parsed_ips is None:
            return {"ok": False, "error": err, "added": [], "found_total": 0}
        ips_to_exclude = parsed_ips

    ensure_files_exist()
    exclude_file = LISTS_DIR / "ipset-exclude-user.txt"
    existing_ips: set[str] = set()
    if exclude_file.exists():
        try:
            with open(exclude_file, "r", encoding="utf-8") as f:
                for line in f:
                    clean = line.strip()
                    if clean and not clean.startswith("#"):
                        existing_ips.add(clean.split("/")[0].split("#")[0].strip())
        except Exception:
            pass

    added: list[tuple[str, str, str]] = []
    if ips_to_exclude:
        try:
            with open(exclude_file, "a", encoding="utf-8") as f:
                for ip_str, proc, category, prefix in sorted(ips_to_exclude):
                    if ip_str not in existing_ips:
                        f.write(f"{ip_str}/{prefix} # Авто-исключение: {category} ({proc})\n")
                        existing_ips.add(ip_str)
                        added.append((ip_str, category, proc))
        except Exception as e:
            return {"ok": False, "error": f"Не удалось записать {exclude_file}: {e}", "added": [], "found_total": len(ips_to_exclude)}

    restarted = False
    if added and is_winws_running():
        restarted, _ = start_bypass_background()

    return {
        "ok": True,
        "error": "",
        "added": added,
        "found_total": len(ips_to_exclude),
        "file": str(exclude_file),
        "restarted": restarted,
    }


class _PinnedGitHubHandler(urllib.request.HTTPSHandler):
    _HOSTS = {
        "raw.githubusercontent.com": "185.199.109.133",
        "release-assets.githubusercontent.com": "185.199.109.133",
    }

    def https_open(self, req):
        host = req.host.split(":")[0]
        pinned = self._HOSTS.get(host)
        if not pinned:
            return super().https_open(req)

        class _Conn(http.client.HTTPSConnection):
            def connect(self):
                self.sock = socket.create_connection((pinned, self.port or 443), self.timeout, self.source_address)
                if self._tunnel_host:
                    self._tunnel()
                self.sock = self._context.wrap_socket(self.sock, server_hostname=self._tunnel_host or self.host)

        try:
            return self.do_open(_Conn, req, context=self._context)
        except Exception:
            return super().https_open(req)


def _valid_ips(items: object, version: int, limit: int = 2) -> list[str]:
    out: list[str] = []
    if not isinstance(items, list):
        return out
    for raw in items:
        s = str(raw or "").strip()
        try:
            ip = ipaddress.ip_address(s)
            if ip.version == version and s not in out:
                out.append(s)
                if len(out) >= limit:
                    break
        except ValueError:
            continue
    return out


def fetch_dns_ai_endpoints(timeout: int = 8) -> dict:
    opener = urllib.request.build_opener(_PinnedGitHubHandler(context=ssl.create_default_context()))
    for url in DNS_AI_MANIFESTS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"Unfit-Zapret/{APP_VERSION}"})
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            v4 = _valid_ips(data.get("v4"), 4, limit=2)
            v6 = _valid_ips(data.get("v6"), 6, limit=2)
            retired = [str(x).strip() for x in (data.get("retired") or []) if str(x).strip()]
            if v4:
                return {"v4": v4, "v6": v6, "retired": retired, "source": url}
        except Exception:
            continue
    return {
        "v4": list(DNS_AI_BUILTIN_V4),
        "v6": list(DNS_AI_BUILTIN_V6),
        "retired": list(DNS_AI_RETIRED),
        "source": "builtin",
    }


def get_windows_build_number() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as k:
            val, _ = winreg.QueryValueEx(k, "CurrentBuildNumber")
            return int(str(val).strip())
    except Exception:
        return 0


def _load_dns_ai_known_ips() -> list[str]:
    ips = list(DNS_AI_BUILTIN_V4)
    if DNS_AI_STATE_FILE.exists():
        try:
            st = json.loads(DNS_AI_STATE_FILE.read_text(encoding="utf-8"))
            for ip in st.get("v4") or []:
                if ip not in ips:
                    ips.append(str(ip))
        except Exception:
            pass
    return ips


def _save_dns_ai_state(v4: list[str], v6: list[str], retired: list[str]) -> None:
    try:
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        DNS_AI_STATE_FILE.write_text(
            json.dumps({"v4": v4, "v6": v6, "retired": retired}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def get_dns_ai_status() -> dict:
    if IS_WINDOWS:
        build = get_windows_build_number()
        if build >= 22000:
            known_v4 = set(_load_dns_ai_known_ips())
            base_key = r"SYSTEM\CurrentControlSet\Services\Dnscache\InterfaceSpecificParameters"
            enabled = False
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_key) as root_k:
                    cnt = winreg.QueryInfoKey(root_k)[0]
                    for i in range(cnt):
                        guid = winreg.EnumKey(root_k, i)
                        ns_tokens: set[str] = set()
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{guid}") as ik:
                                ns_val, _ = winreg.QueryValueEx(ik, "NameServer")
                                ns_tokens = {p.strip() for p in re.split(r"[\s,;]+", str(ns_val)) if p.strip()}
                        except OSError:
                            pass
                        for ip in known_v4:
                            if ip not in ns_tokens:
                                continue
                            try:
                                with winreg.OpenKey(root_k, rf"{guid}\DohInterfaceSettings\Doh\{ip}") as dk:
                                    flags, _ = winreg.QueryValueEx(dk, "DohFlags")
                                    if int(flags) & 1:
                                        enabled = True
                                        break
                            except OSError:
                                continue
                        if enabled:
                            break
            except OSError:
                pass
            return {"enabled": enabled, "mode": "Win11 DoH", "template": DNS_AI_TEMPLATE, "build": build}

        exe_pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "DNS-AI" / "DNS-AI.exe"
        svc_exists = False
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\DNS-AI"):
                svc_exists = True
        except OSError:
            pass
        return {"enabled": svc_exists and exe_pf.exists(), "mode": "DNS-AI Client", "template": DNS_AI_TEMPLATE, "build": build}

    resolved_dropin = Path("/etc/systemd/resolved.conf.d/dns-ai.conf")
    stubby_cfg = Path("/etc/stubby/stubby.yml")
    if resolved_dropin.is_file():
        return {"enabled": True, "mode": "DoT (resolved)", "template": DNS_AI_TLS_HOST, "build": 0}
    if stubby_cfg.is_file() and "DNS-AI" in stubby_cfg.read_text(encoding="utf-8", errors="ignore"):
        return {"enabled": True, "mode": "DoT (stubby)", "template": DNS_AI_TLS_HOST, "build": 0}
    return {"enabled": False, "mode": "DoT", "template": DNS_AI_TLS_HOST, "build": 0}


def _ps_array_literal(items: list[str]) -> str:
    if not items:
        return "@()"
    return "@(" + ", ".join(_ps_quote(x) for x in items) + ")"


def _build_win11_enable_ps(v4: list[str], v6: list[str]) -> str:
    return (
        f"$Template = {_ps_quote(DNS_AI_TEMPLATE)}\n"
        f"$V4 = {_ps_array_literal(v4)}\n"
        f"$V6 = {_ps_array_literal(v6)}\n"
        "$DohKey = 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Dnscache\\InterfaceSpecificParameters'\n"
        "$SkipName = 'Hyper-V|VMware|VirtualBox|WSL|vEthernet|TAP|WireGuard|Wintun|Tailscale|ZeroTier|Amnezia|OpenVPN|Loopback|Virtual'\n"
        "$adapters = @(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and -not $_.Virtual -and $_.Name -notmatch $SkipName -and $_.InterfaceDescription -notmatch $SkipName })\n"
        "if ($adapters.Count -eq 0) { throw 'Не найдено активных физических сетевых адаптеров' }\n"
        "foreach ($ip in $V4 + $V6) {\n"
        "    if (Get-DnsClientDohServerAddress -ServerAddress $ip -ErrorAction SilentlyContinue) {\n"
        "        Set-DnsClientDohServerAddress -ServerAddress $ip -DohTemplate $Template -AllowFallbackToUdp $false -AutoUpgrade $true | Out-Null\n"
        "    } else {\n"
        "        Add-DnsClientDohServerAddress -ServerAddress $ip -DohTemplate $Template -AllowFallbackToUdp $false -AutoUpgrade $true | Out-Null\n"
        "    }\n"
        "}\n"
        "$names = @()\n"
        "foreach ($a in $adapters) {\n"
        "    $hasV6 = $false\n"
        "    $b = Get-NetAdapterBinding -Name $a.Name -ComponentID ms_tcpip6 -ErrorAction SilentlyContinue\n"
        "    if ($b -and $b.Enabled) { $hasV6 = $true }\n"
        "    $servers = if ($hasV6 -and $V6.Count -gt 0) { @($V4 + $V6) } else { @($V4) }\n"
        "    Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses $servers\n"
        "    $sets = @(@{ Fam = 'Doh'; Ips = $V4 })\n"
        "    if ($hasV6 -and $V6.Count -gt 0) { $sets += @{ Fam = 'Doh6'; Ips = $V6 } }\n"
        "    foreach ($s in $sets) {\n"
        "        $k = Join-Path $DohKey (\"{0}\\DohInterfaceSettings\\{1}\" -f $a.InterfaceGuid, $s.Fam)\n"
        "        if (Test-Path $k) {\n"
        "            Get-ChildItem $k | Where-Object { $s.Ips -notcontains $_.PSChildName } | Remove-Item -Recurse -Force\n"
        "        }\n"
        "        foreach ($ip in $s.Ips) {\n"
        "            $ik = Join-Path $k $ip\n"
        "            if (-not (Test-Path $ik)) { New-Item -Path $ik -Force | Out-Null }\n"
        "            New-ItemProperty -Path $ik -Name 'DohFlags' -PropertyType QWord -Value 1 -Force | Out-Null\n"
        "        }\n"
        "    }\n"
        "    Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses $servers\n"
        "    $names += $a.Name\n"
        "}\n"
        "Clear-DnsClientCache\n"
        "Write-Output ($names -join ', ')\n"
    )


def _build_win11_disable_ps(ours: list[str]) -> str:
    return (
        f"$Ours = {_ps_array_literal(ours)}\n"
        "$DohKey = 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Dnscache\\InterfaceSpecificParameters'\n"
        "$SkipName = 'Hyper-V|VMware|VirtualBox|WSL|vEthernet|TAP|WireGuard|Wintun|Tailscale|ZeroTier|Amnezia|OpenVPN|Loopback|Virtual'\n"
        "$adapters = @(Get-NetAdapter | Where-Object { -not $_.Virtual -and $_.Name -notmatch $SkipName -and $_.InterfaceDescription -notmatch $SkipName })\n"
        "$names = @()\n"
        "foreach ($a in $adapters) {\n"
        "    $touched = $false\n"
        "    if ($a.Status -eq 'Up') {\n"
        "        Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ResetServerAddresses\n"
        "        $touched = $true\n"
        "    }\n"
        "    foreach ($fam in 'Doh', 'Doh6') {\n"
        "        $k = Join-Path $DohKey (\"{0}\\DohInterfaceSettings\\{1}\" -f $a.InterfaceGuid, $fam)\n"
        "        foreach ($ip in $Ours) {\n"
        "            $ik = Join-Path $k $ip\n"
        "            if (Test-Path $ik) {\n"
        "                Remove-Item $ik -Recurse -Force\n"
        "                $touched = $true\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    if ($touched) { $names += $a.Name }\n"
        "}\n"
        "foreach ($ip in $Ours) {\n"
        "    if (Get-DnsClientDohServerAddress -ServerAddress $ip -ErrorAction SilentlyContinue) {\n"
        "        Remove-DnsClientDohServerAddress -ServerAddress $ip -ErrorAction SilentlyContinue\n"
        "    }\n"
        "}\n"
        "Clear-DnsClientCache\n"
        "Write-Output ($names -join ', ')\n"
    )


def _download_dns_ai_exe(dst: Path) -> tuple[bool, str]:
    opener = urllib.request.build_opener(_PinnedGitHubHandler(context=ssl.create_default_context()))
    try:
        req = urllib.request.Request(DNS_AI_WIN_EXE_URL, headers={"User-Agent": f"Unfit-Zapret/{APP_VERSION}"})
        with opener.open(req, timeout=60) as resp:
            data = resp.read()
        if len(data) < 200_000 or not data.startswith(b"MZ"):
            return False, "Скачанный DNS-AI.exe повреждён"
        dst.write_bytes(data)
        return True, ""
    except Exception as e:
        res = subprocess.run(
            [CURL_EXE, "-fL", "--silent", "--show-error", "--max-time", "60", "-o", str(dst), DNS_AI_WIN_EXE_URL],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW if IS_WINDOWS else 0,
            timeout=65,
        )
        if res.returncode == 0 and dst.exists() and dst.stat().st_size >= 200_000:
            return True, ""
        return False, str(e)


def _check_dns_ai_reachable(ips: list[str], timeout: float = 4.0) -> bool:
    ctx = ssl.create_default_context()
    for ip in ips:
        try:
            with socket.create_connection((ip, 443), timeout=timeout) as raw:
                with ctx.wrap_socket(raw, server_hostname=DNS_AI_TLS_HOST):
                    return True
        except OSError:
            continue
    return False


def enable_dns_ai() -> tuple[bool, str]:
    ensure_files_exist()
    ep = fetch_dns_ai_endpoints()
    v4, v6, retired = ep["v4"], ep["v6"], ep["retired"]
    if not _check_dns_ai_reachable(v4):
        return False, "Серверы dns.dns-ai.ru сейчас недоступны по TLS:443 — системный DNS не изменён, чтобы не потерять доступ к сети."
    _save_dns_ai_state(v4, v6, retired)

    if IS_WINDOWS:
        if not is_admin():
            return False, "Нужны права Администратора для настройки DNS-AI"
        build = get_windows_build_number()
        if build >= 22000:
            rc, out, err = _run_powershell(_build_win11_enable_ps(v4, v6), timeout=30)
            if rc == 0:
                return True, f"DNS-AI (Win11 DoH) включён для: {out or 'активных адаптеров'}. Проверьте dns-ai.ru/ip"
            return False, f"Ошибка настройки Win11 DoH: {err or out or rc}"

        exe_pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "DNS-AI" / "DNS-AI.exe"
        exe_tmp = WORK_DIR / "DNS-AI-installer.exe"
        runner = exe_pf if exe_pf.is_file() else exe_tmp
        if not runner.is_file():
            ok_dl, err_dl = _download_dns_ai_exe(exe_tmp)
            if not ok_dl:
                return False, f"Не удалось скачать DNS-AI.exe: {err_dl}"
            runner = exe_tmp
        try:
            res = subprocess.run(
                [str(runner), "setup"],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
                stdin=subprocess.DEVNULL,
                timeout=45,
            )
            if res.returncode == 0:
                return True, "Клиент DNS-AI установлен и запущен для Windows 10"
            msg = (res.stderr or res.stdout or b"").decode("utf-8", errors="ignore").strip()
            return False, f"DNS-AI setup завершился с кодом {res.returncode}: {msg}"
        except Exception as e:
            return False, f"Ошибка запуска DNS-AI.exe: {e}"

    # Linux DoT через systemd-resolved + NetworkManager
    if not is_admin():
        return False, "Требуются права root для настройки systemd-resolved"
    state_dir = Path("/etc/dns-ai")
    dropin = Path("/etc/systemd/resolved.conf.d/dns-ai.conf")
    resolv = Path("/etc/resolv.conf")
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        dropin.parent.mkdir(parents=True, exist_ok=True)
        has_v6 = False
        ip_bin = shutil.which("ip")
        if ip_bin:
            r6 = subprocess.run([ip_bin, "-6", "addr", "show", "scope", "global"], capture_output=True, text=True, timeout=3)
            has_v6 = bool(r6.stdout.strip())
        srv_ips = list(v4) + (list(v6) if has_v6 else [])
        srv_str = " ".join(f"{ip}#{DNS_AI_TLS_HOST}" for ip in srv_ips)
        dropin.write_text(f"# DNS-AI\n[Resolve]\nDNS={srv_str}\nDNSOverTLS=yes\nDomains=~.\nFallbackDNS=\n", encoding="utf-8")

        if shutil.which("nmcli"):
            nm_res = subprocess.run(["nmcli", "-t", "-f", "UUID,TYPE,DEVICE", "connection", "show", "--active"], capture_output=True, text=True, timeout=5)
            saved_uuids = state_dir / "nm-connections"
            existing = set(saved_uuids.read_text(encoding="utf-8").splitlines()) if saved_uuids.exists() else set()
            for row in nm_res.stdout.splitlines():
                parts = row.split(":", 2)
                if len(parts) < 3:
                    continue
                uuid, ctype, dev = parts
                if any(bad in ctype for bad in ("loopback", "bridge", "tun", "wireguard", "vpn", "docker", "dummy")) or not ctype:
                    continue
                subprocess.run(["nmcli", "connection", "modify", uuid, "ipv4.ignore-auto-dns", "yes", "ipv6.ignore-auto-dns", "yes"], capture_output=True, timeout=5)
                if dev:
                    subprocess.run(["nmcli", "device", "reapply", dev], capture_output=True, timeout=5)
                existing.add(uuid)
            if existing:
                saved_uuids.write_text("\n".join(sorted(existing)) + "\n", encoding="utf-8")

        subprocess.run(["systemctl", "enable", "systemd-resolved"], capture_output=True, timeout=10)
        subprocess.run(["systemctl", "restart", "systemd-resolved"], capture_output=True, timeout=15)
        if not (resolv.is_symlink() and "systemd/resolve" in str(os.readlink(resolv))):
            if resolv.is_symlink() and not (state_dir / "resolv.conf.link").exists():
                (state_dir / "resolv.conf.link").write_text(os.readlink(resolv), encoding="utf-8")
            elif resolv.is_file() and not (state_dir / "resolv.conf.bak").exists():
                shutil.copy2(resolv, state_dir / "resolv.conf.bak")
            resolv.unlink(missing_ok=True)
            os.symlink("/run/systemd/resolve/stub-resolv.conf", resolv)
        return True, "DNS-AI (systemd-resolved DoT) включён"
    except Exception as e:
        return False, f"Ошибка настройки DNS-AI на Linux (см. https://dns-ai.ru/#setup): {e}"


def disable_dns_ai() -> tuple[bool, str]:
    ours = list(dict.fromkeys(list(DNS_AI_BUILTIN_V4) + list(DNS_AI_BUILTIN_V6) + list(DNS_AI_RETIRED)))
    if DNS_AI_STATE_FILE.exists():
        try:
            st = json.loads(DNS_AI_STATE_FILE.read_text(encoding="utf-8"))
            for key in ("v4", "v6", "retired"):
                for ip in st.get(key) or []:
                    if ip not in ours:
                        ours.append(str(ip))
        except Exception:
            pass

    if IS_WINDOWS:
        if not is_admin():
            return False, "Нужны права Администратора для отключения DNS-AI"
        build = get_windows_build_number()
        if build >= 22000:
            rc, out, err = _run_powershell(_build_win11_disable_ps(ours), timeout=30)
            if rc == 0:
                return True, f"Настройки DNS-AI удалены ({out or 'возвращён DHCP'})"
            return False, f"Ошибка отключения DNS-AI: {err or out or rc}"

        exe_pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "DNS-AI" / "DNS-AI.exe"
        exe_tmp = WORK_DIR / "DNS-AI-installer.exe"
        runner = exe_pf if exe_pf.is_file() else exe_tmp
        if not runner.is_file():
            return False, "Не найден DNS-AI.exe для удаления службы"
        res = subprocess.run([str(runner), "remove"], capture_output=True, creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL, timeout=30)
        if res.returncode == 0:
            return True, "Служба DNS-AI удалена"
        return False, f"Ошибка удаления DNS-AI ({res.returncode})"

    if not is_admin():
        return False, "Требуются права root"
    state_dir = Path("/etc/dns-ai")
    dropin = Path("/etc/systemd/resolved.conf.d/dns-ai.conf")
    resolv = Path("/etc/resolv.conf")
    try:
        dropin.unlink(missing_ok=True)
        subprocess.run(["systemctl", "restart", "systemd-resolved"], capture_output=True, timeout=15)
        nm_file = state_dir / "nm-connections"
        if nm_file.exists() and shutil.which("nmcli"):
            for uuid in nm_file.read_text(encoding="utf-8").splitlines():
                uuid = uuid.strip()
                if not uuid:
                    continue
                subprocess.run(["nmcli", "connection", "modify", uuid, "ipv4.ignore-auto-dns", "no", "ipv6.ignore-auto-dns", "no"], capture_output=True, timeout=5)
        if (state_dir / "resolv.conf.link").exists():
            resolv.unlink(missing_ok=True)
            os.symlink((state_dir / "resolv.conf.link").read_text(encoding="utf-8").strip(), resolv)
        elif (state_dir / "resolv.conf.bak").exists():
            resolv.unlink(missing_ok=True)
            shutil.copy2(state_dir / "resolv.conf.bak", resolv)
        shutil.rmtree(state_dir, ignore_errors=True)
        return True, "Настройки DNS-AI удалены"
    except Exception as e:
        return False, f"Ошибка отключения DNS-AI: {e}"


def fetch_github_avatar(timeout: int = 4) -> Optional[bytes]:
    try:
        req = urllib.request.Request(
            GITHUB_AVATAR_URL,
            headers={"User-Agent": f"Unfit-Zapret/{APP_VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except Exception:
        pass
    return None


def _parse_version(ver: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", ver or "")
    return tuple(int(n) for n in nums) if nums else (0,)


def _fetch_json(url: str, timeout: int = 5) -> tuple[int, Optional[dict | list]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"Unfit-Zapret/{APP_VERSION}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def check_github_update(timeout: int = 5) -> dict:
    base_res = {
        "ok": False,
        "has_update": False,
        "current": APP_VERSION,
        "latest": APP_VERSION,
        "url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases",
        "asset_url": "",
        "notes": "",
        "error": "",
    }

    candidate_repos = [f"{GITHUB_OWNER}/{GITHUB_REPO}"]
    code, data = _fetch_json(f"https://api.github.com/repos/{candidate_repos[0]}/releases/latest", timeout=timeout)

    if code == 404:
        rc, repos = _fetch_json(f"https://api.github.com/users/{GITHUB_OWNER}/repos?sort=updated&per_page=20", timeout=timeout)
        if rc == 200 and isinstance(repos, list):
            for r in repos:
                name = str(r.get("name", "")).lower()
                if "zapret" in name or "unfit" in name:
                    full = r.get("full_name")
                    if full and full not in candidate_repos:
                        code, data = _fetch_json(f"https://api.github.com/repos/{full}/releases/latest", timeout=timeout)
                        if code == 200:
                            break

    if code == 200 and isinstance(data, dict):
        tag = str(data.get("tag_name") or data.get("name") or "").strip()
        clean_latest = tag.lstrip("vV") or APP_VERSION
        has_upd = _parse_version(clean_latest) > _parse_version(APP_VERSION)
        arch = detect_arch()
        assets = data.get("assets") or []
        asset_url = ""
        if IS_WINDOWS:
            if arch == "x86":
                for asset in assets:
                    aname = str(asset.get("name", "")).lower()
                    if "win-x86" in aname:
                        asset_url = str(asset.get("browser_download_url") or "")
                        break
            if not asset_url:
                for asset in assets:
                    aname = str(asset.get("name", "")).lower()
                    if aname.endswith(".exe"):
                        asset_url = str(asset.get("browser_download_url") or "")
                        break
        else:
            target_tag = f"linux-{arch}"
            for asset in assets:
                aname = str(asset.get("name", "")).lower()
                if target_tag in aname:
                    asset_url = str(asset.get("browser_download_url") or "")
                    break
        base_res.update({
            "ok": True,
            "has_update": has_upd,
            "latest": clean_latest,
            "url": str(data.get("html_url") or base_res["url"]),
            "asset_url": asset_url,
            "notes": str(data.get("name") or tag),
        })
        return base_res

    if code == 404:
        base_res["ok"] = True
        base_res["error"] = "no_releases"
        return base_res

    base_res["error"] = f"HTTP {code}" if code else "Нет подключения к GitHub"
    return base_res


def _format_mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} МБ"


def _format_speed(bps: float) -> str:
    if bps >= 1024 * 1024:
        return f"{bps / (1024 * 1024):.1f} МБ/с"
    return f"{bps / 1024:.0f} КБ/с"


def _format_progress(downloaded: int, total: int, elapsed: float) -> str:
    speed = _format_speed(downloaded / max(0.1, elapsed))
    if total > 0:
        pct = min(100, int(downloaded * 100 / total))
        return f"Скачивание: {_format_mb(downloaded)} / {_format_mb(total)} ({pct}%, {speed})"
    return f"Скачивание: {_format_mb(downloaded)} ({speed})"


def _validate_downloaded_exe(dst: Path, expected_size: int = 0) -> tuple[bool, str]:
    if not dst.exists():
        return False, "Файл обновления не сохранён"
    size = dst.stat().st_size
    if size < 1_000_000 or (expected_size > 0 and size != expected_size):
        dst.unlink(missing_ok=True)
        return False, "Скачанный файл неполный"
    try:
        with open(dst, "rb") as f:
            head = f.read(2)
    except OSError as e:
        dst.unlink(missing_ok=True)
        return False, f"Ошибка чтения файла: {e}"
    if head != b"MZ":
        dst.unlink(missing_ok=True)
        return False, "Скачанный файл повреждён"
    return True, ""


def _download_update_urllib(
    asset_url: str,
    dst: Path,
    progress_cb: Optional[Callable[[int, int, str], None]],
    cancel_event: Optional[threading.Event],
) -> tuple[bool, int, str]:
    req = urllib.request.Request(asset_url, headers={"User-Agent": f"Unfit-Zapret/{APP_VERSION}"})
    total_bytes = 0
    downloaded = 0
    started = time.monotonic()
    last_emit = 0.0
    window_start = started
    window_bytes = 0
    dst.unlink(missing_ok=True)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw_len = (resp.headers.get("Content-Length") or "").strip()
            if raw_len.isdigit():
                total_bytes = int(raw_len)
            with open(dst, "wb") as out:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        dst.unlink(missing_ok=True)
                        return False, total_bytes, "cancelled"
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
                    clen = len(chunk)
                    downloaded += clen
                    window_bytes += clen
                    now = time.monotonic()
                    if now - started > 180.0:
                        dst.unlink(missing_ok=True)
                        return False, total_bytes, "Превышено время ожидания загрузки (180 сек)"
                    win_dt = now - window_start
                    if win_dt >= 20.0:
                        if window_bytes / win_dt < 4096.0:
                            dst.unlink(missing_ok=True)
                            return False, total_bytes, "Слишком низкая скорость загрузки (возможно замедление GitHub)"
                        window_start = now
                        window_bytes = 0
                    if progress_cb and (now - last_emit >= 0.2 or (total_bytes > 0 and downloaded >= total_bytes)):
                        last_emit = now
                        progress_cb(downloaded, total_bytes, _format_progress(downloaded, total_bytes, now - started))
    except Exception as e:
        dst.unlink(missing_ok=True)
        if cancel_event is not None and cancel_event.is_set():
            return False, total_bytes, "cancelled"
        return False, total_bytes, str(e)

    if cancel_event is not None and cancel_event.is_set():
        dst.unlink(missing_ok=True)
        return False, total_bytes, "cancelled"

    ok, err = _validate_downloaded_exe(dst, total_bytes)
    if not ok:
        return False, total_bytes, err
    if progress_cb:
        final_total = total_bytes or downloaded
        progress_cb(downloaded, final_total, _format_progress(downloaded, final_total, time.monotonic() - started))
    return True, total_bytes, ""


def _download_update_curl(
    asset_url: str,
    dst: Path,
    total_hint: int,
    progress_cb: Optional[Callable[[int, int, str], None]],
    cancel_event: Optional[threading.Event],
) -> tuple[bool, str]:
    dst.unlink(missing_ok=True)
    cmd = [
        CURL_EXE,
        "-fL",
        "--silent",
        "--show-error",
        "--connect-timeout", "15",
        "--speed-limit", "4096",
        "--speed-time", "20",
        "--max-time", "180",
        "--retry", "1",
        "-A", f"Unfit-Zapret/{APP_VERSION}",
        "-o", str(dst),
        asset_url,
    ]
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd,
            creationflags=CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        dst.unlink(missing_ok=True)
        return False, f"curl не запущен: {e}"

    try:
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    pass
                dst.unlink(missing_ok=True)
                return False, "cancelled"
            if progress_cb and dst.exists():
                try:
                    cur_size = dst.stat().st_size
                except OSError:
                    cur_size = 0
                if cur_size > 0:
                    progress_cb(cur_size, total_hint, _format_progress(cur_size, total_hint, time.monotonic() - started))
            time.sleep(0.25)

        _, err_bytes = proc.communicate(timeout=5)
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        dst.unlink(missing_ok=True)
        return False, f"Ошибка curl: {e}"

    if cancel_event is not None and cancel_event.is_set():
        dst.unlink(missing_ok=True)
        return False, "cancelled"

    if proc.returncode != 0:
        err_txt = ""
        if err_bytes:
            err_txt = err_bytes.decode("utf-8", errors="ignore").strip()
            if not err_txt:
                err_txt = err_bytes.decode("cp866", errors="ignore").strip()
        dst.unlink(missing_ok=True)
        return False, f"curl ({proc.returncode}): {err_txt or 'ошибка загрузки'}"

    ok, err = _validate_downloaded_exe(dst, total_hint)
    if not ok:
        return False, err
    size = dst.stat().st_size
    if progress_cb:
        final_total = total_hint or size
        progress_cb(size, final_total, _format_progress(size, final_total, time.monotonic() - started))
    return True, ""


def _escape_bat_val(val: str) -> str:
    return val.replace("%", "%%")


def _build_update_bat(new_exe: Path, target_exe: Path, child_pid: int, parent_pid: Optional[int]) -> str:
    log_path = _escape_bat_val(str(Path(tempfile.gettempdir()) / "unfit_zapret_update.log"))
    new_s = _escape_bat_val(str(new_exe))
    target_s = _escape_bat_val(str(target_exe))
    target_dir_s = _escape_bat_val(str(target_exe.parent))
    ping_cmd = r"%SystemRoot%\System32\ping.exe -n 2 127.0.0.1 >nul"

    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "setlocal EnableExtensions",
        f'set "NEW_EXE={new_s}"',
        f'set "TARGET_EXE={target_s}"',
        f'set "TARGET_DIR={target_dir_s}"',
        f'set "LOG_FILE={log_path}"',
        'echo [%DATE% %TIME%] Updater started > "%LOG_FILE%"',
    ]

    def _append_pid_wait(tag: str, pid: int, next_label: str) -> None:
        lines.extend([
            f"set /a wait_{tag}=0",
            f":wait_{tag}_loop",
            'set "ALIVE="',
            f'for /f "tokens=2 delims=," %%P in (\'%SystemRoot%\\System32\\tasklist.exe /nh /fo csv /fi "PID eq {pid}" 2^>nul\') do if "%%~P"=="{pid}" set "ALIVE=1"',
            f"if not defined ALIVE goto {next_label}",
            f"set /a wait_{tag}+=1",
            f"if %wait_{tag}% GEQ 30 goto {next_label}",
            ping_cmd,
            f"goto wait_{tag}_loop",
        ])

    has_parent = parent_pid is not None and parent_pid != child_pid
    _append_pid_wait("child", child_pid, "wait_parent_init" if has_parent else "after_wait")
    if has_parent:
        lines.append(":wait_parent_init")
        _append_pid_wait("parent", parent_pid, "after_wait")

    lines.extend([
        ":after_wait",
        ping_cmd,
        "set /a tries=0",
        ":replace_loop",
        'move /y "%NEW_EXE%" "%TARGET_EXE%" >nul 2>&1',
        'if not exist "%NEW_EXE%" if exist "%TARGET_EXE%" goto launch_new',
        'copy /y "%NEW_EXE%" "%TARGET_EXE%" >nul 2>&1',
        "if not errorlevel 1 (",
        '    del /f /q "%NEW_EXE%" >nul 2>&1',
        "    goto launch_new",
        ")",
        "set /a tries+=1",
        "if %tries% GEQ 30 goto replace_fail",
        ping_cmd,
        "goto replace_loop",
        ":launch_new",
        'echo [%DATE% %TIME%] Replaced OK >> "%LOG_FILE%"',
        'cd /d "%TARGET_DIR%"',
        'start "" "%TARGET_EXE%"',
        ping_cmd,
        '(goto) 2>nul & del /f /q "%~f0" >nul 2>&1',
        ":replace_fail",
        'echo [%DATE% %TIME%] Replace failed after 30 attempts >> "%LOG_FILE%"',
        'if exist "%TARGET_EXE%" start "" "%TARGET_EXE%"',
        '(goto) 2>nul & del /f /q "%~f0" >nul 2>&1',
    ])
    return "\r\n".join(lines) + "\r\n"


def download_and_apply_update(
    asset_url: str,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> tuple[bool, str]:
    if not IS_WINDOWS:
        return False, "На Linux обновитесь через архив со страницы релиза"
    if not asset_url or not asset_url.lower().endswith(".exe"):
        return False, "В релизе нет подходящего .exe файла"

    if not is_compiled_binary():
        return False, "Автообновление доступно только в скомпилированном .exe"

    target_exe = get_real_executable()
    new_exe = target_exe.with_name(target_exe.name + ".new")

    # Проверяем права записи в папку программы до начала скачивания
    probe_file = target_exe.with_name(f".unfit_upd_probe_{os.getpid()}.tmp")
    try:
        new_exe.unlink(missing_ok=True)
        probe_file.write_bytes(b"ok")
        probe_file.unlink(missing_ok=True)
    except OSError as e:
        return False, f"Нет прав на запись в папку {target_exe.parent}: {e}"

    ok, total_hint, err_msg = _download_update_urllib(asset_url, new_exe, progress_cb, cancel_event)
    if not ok:
        if err_msg == "cancelled":
            return False, "Скачивание отменено"
        if progress_cb:
            progress_cb(0, total_hint, "Повтор через системный curl...")
        ok_curl, err_curl = _download_update_curl(asset_url, new_exe, total_hint, progress_cb, cancel_event)
        if not ok_curl:
            new_exe.unlink(missing_ok=True)
            if err_curl == "cancelled":
                return False, "Скачивание отменено"
            last_err = err_curl or err_msg
            return False, f"Ошибка скачивания: {last_err}. Попробуйте включить обход или скачать вручную."

    raw_parent = (os.environ.get("NUITKA_ONEFILE_PARENT") or "").strip()
    parent_pid = int(raw_parent) if raw_parent.isdigit() and int(raw_parent) != os.getpid() else None

    bat_path = Path(tempfile.gettempdir()) / "unfit_zapret_update.bat"
    bat_content = _build_update_bat(new_exe, target_exe, os.getpid(), parent_pid)
    try:
        bat_path.write_text(bat_content, encoding="utf-8")
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_path)],
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True, "Обновление скачано! Выполняется замена и автоперезапуск..."
    except Exception as e:
        return False, f"Не удалось запустить обновление: {e}"
