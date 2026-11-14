from __future__ import annotations

import ctypes
from ctypes import wintypes
import ipaddress
import json
import os
import random
import re
import subprocess
import sys
import tempfile
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


CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
BACKGROUND_FLAGS = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

TASK_NAME = "ZapretUltraStable"
APP_NAME = "Unfit Zapret"
APP_VERSION = "2.0.0"
GITHUB_OWNER = "Mist-582"
GITHUB_REPO = "Unfit-Zapret"
GITHUB_AVATAR_URL = f"https://avatars.githubusercontent.com/{GITHUB_OWNER}?s=128"


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


def get_work_dir() -> Path:
    # Единая рабочая папка для админа и службы SYSTEM
    is_compiled = ("__compiled__" in globals()) or bool(
        sys.argv and sys.argv[0] and Path(sys.argv[0]).suffix.lower() == ".exe"
    )
    if is_compiled or get_embedded_assets_zip() is not None and not (Path(__file__).resolve().parent / "bin" / "winws.exe").exists():
        prog_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        return prog_data / "UnfitZapret"

    return Path(__file__).resolve().parent


WORK_DIR = get_work_dir()
BIN_DIR = WORK_DIR / "bin"
LISTS_DIR = WORK_DIR / "lists"
CONFIG_FILE = WORK_DIR / "zapret_config.json"
AUTORUN_LOG_FILE = WORK_DIR / "autorun.log"
CURL_EXE = r"C:\Windows\System32\curl.exe" if os.path.exists(r"C:\Windows\System32\curl.exe") else "curl"


STRATEGIES: list[dict[str, str]] = [
    {
        "name": "Multisplit 681 (Google)",
        "desc": "Multisplit 681 (Google Client Hello) - рекомендуется для YouTube / Discord",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=8",
    },
    {
        "name": "Multisplit 664 (Max.ru)",
        "desc": "Multisplit 664 (Max.ru Client Hello) - альтернативный Multisplit",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=664 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=8",
    },
    {
        "name": "Fake TLS Mod (ALT3)",
        "desc": "Multisplit с Fake TLS Mod (маскировка SNI) - высокая обходимость",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=ts --dpi-desync-repeats=8 --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni}",
    },
    {
        "name": "Badseq + Fake TLS (ALT2)",
        "desc": "Multisplit с Badseq & Fake TLS Mod - пробивает жёсткие блоки",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=10000000 --dpi-desync-repeats=8 --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni}",
    },
    {
        "name": "Simple Fake TLS (ALT10)",
        "desc": "Simple Fake TLS - простой обход без фрагментации",
        "args": "--dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fooling=ts --dpi-desync-fake-tls-mod=none",
    },
    {
        "name": "Fakedsplit 0x00 (ALT)",
        "desc": "Fakedsplit 0x00 - классический сплит с фейком",
        "args": "--dpi-desync=fake,fakedsplit --dpi-desync-repeats=6 --dpi-desync-fooling=ts --dpi-desync-fakedsplit-pattern=0x00",
    },
    {
        "name": "Hostfakesplit (ALT3)",
        "desc": "Hostfakesplit - маскировка под Google / выбранный SNI",
        "args": "--dpi-desync=fake,hostfakesplit --dpi-desync-fake-tls-mod=rnd,dupsid,sni={fake_sni} --dpi-desync-hostfakesplit-mod=host={fake_sni},altorder=1 --dpi-desync-fooling=ts",
    },
    {
        "name": "Fake Badseq (ALT8)",
        "desc": "Fake Badseq - подмена последовательности TCP",
        "args": "--dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=2",
    },
    {
        "name": "Multisplit Badseq (ALT4)",
        "desc": "Multisplit Badseq - фрагментация с фейком и плохим seq",
        "args": "--dpi-desync=fake,multisplit --dpi-desync-repeats=6 --dpi-desync-fooling=badseq --dpi-desync-badseq-increment=1000",
    },
    {
        "name": "Multisplit Raw (ALT6)",
        "desc": "Multisplit Raw - чистый multisplit без фейковых пакетов",
        "args": "--dpi-desync=multisplit --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1",
    },
    {
        "name": "Multisplit Pos 2 (ALT2)",
        "desc": "Multisplit Pos 2 - разделение по второй позиции",
        "args": "--dpi-desync=multisplit --dpi-desync-split-seqovl=652 --dpi-desync-split-pos=2",
    },
]

STRATEGY_STRINGS = [s["args"] for s in STRATEGIES]

POPULAR_SNIS = [
    "www.google.com",
    "www.microsoft.com",
    "www.cloudflare.com",
    "www.apple.com",
    "www.wikipedia.org",
    "yandex.ru",
    "vk.com",
    "gosuslugi.ru",
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
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    argv0 = Path(sys.argv[0]).resolve() if sys.argv else None
    is_compiled = argv0 is not None and argv0.suffix.lower() == ".exe"
    if is_compiled:
        extra_args = " ".join(f'"{a}"' for a in sys.argv[1:]) if len(sys.argv) > 1 else None
        ctypes.windll.shell32.ShellExecuteW(None, "runas", str(argv0), extra_args, str(argv0.parent), 1)
    else:
        script_path = os.path.abspath(sys.argv[0])
        py_exe = sys.executable
        pyw = Path(py_exe).with_name("pythonw.exe")
        if pyw.exists() and "--console" not in sys.argv:
            py_exe = str(pyw)
        args = f'"{script_path}"'
        if len(sys.argv) > 1:
            args += " " + " ".join(f'"{a}"' for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", py_exe, args, str(Path(script_path).parent), 1)


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


def iter_processes() -> dict[int, str]:
    pids: dict[int, str] = {}
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


def is_winws_running() -> bool:
    try:
        return "winws.exe" in iter_processes().values()
    except Exception:
        return False


def get_winws_pids() -> list[int]:
    try:
        return [pid for pid, name in iter_processes().items() if name == "winws.exe"]
    except Exception:
        return []


def kill_winws(timeout: float = 3.0) -> bool:
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

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_winws_running():
            return True
        time.sleep(0.1)
    return not is_winws_running()


def cleanup_windivert() -> None:
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


def default_config() -> dict:
    return {
        "strategy": STRATEGIES[2]["args"],
        "index": 3,
        "udp_mode": "narrow",
        "fake_sni": "www.google.com",
        "minimize_to_tray": True,
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
        except Exception:
            pass
    return cfg


def save_config(config: dict) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def ensure_files_exist() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    LISTS_DIR.mkdir(parents=True, exist_ok=True)

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
                        dst = BIN_DIR / fname
                        if not dst.exists() or (need_update and not winws_busy):
                            try:
                                dst.write_bytes(zf.read(member))
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
            if not winws_busy or not current_marker:
                try:
                    marker_file.write_text(APP_VERSION, encoding="utf-8")
                except OSError:
                    pass
        except Exception:
            pass

    for filename in REQUIRED_LIST_FILES:
        file_path = LISTS_DIR / filename
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Автоматически созданный файл: {filename}\n")


def get_winws_args(strategy_str: str, config: dict, log_cb: Optional[Callable[[str], None]] = None) -> list[str]:
    fake_sni = config.get("fake_sni", "www.google.com")
    udp_mode = config.get("udp_mode", "narrow")

    if fake_sni == "random":
        available = [s for s in POPULAR_SNIS if s != "random"]
        resolved_sni = random.choice(available)
        if log_cb:
            log_cb(f"[SNI] Выбран случайный отпечаток: {resolved_sni}")
    else:
        resolved_sni = fake_sni

    resolved_strategy = strategy_str.replace("{fake_sni}", resolved_sni)

    if udp_mode == "wide":
        udp_ports = "443,19294-19344,50000-65535"
        udp_voice_filter = "19294-19344,50000-65535"
    elif udp_mode == "narrow":
        udp_ports = "443,19294-19344,50000-50100"
        udp_voice_filter = "19294-19344,50000-50100"
    else:
        udp_ports = "443,19294-19344,12"
        udp_voice_filter = "19294-19344,12"

    strat_parts = resolved_strategy.split()

    if "--dpi-desync-split-seqovl=681" in resolved_strategy and not any(
        x.startswith("--dpi-desync-split-seqovl-pattern") for x in strat_parts
    ):
        strat_parts.append(f'--dpi-desync-split-seqovl-pattern={BIN_DIR / "tls_clienthello_www_google_com.bin"}')
    elif "--dpi-desync-split-seqovl=664" in resolved_strategy and not any(
        x.startswith("--dpi-desync-split-seqovl-pattern") for x in strat_parts
    ):
        strat_parts.append(f'--dpi-desync-split-seqovl-pattern={BIN_DIR / "tls_clienthello_max_ru.bin"}')

    args = [
        str(BIN_DIR / "winws.exe"),
        "--wf-tcp=80,443,2053,2083,2087,2096,8443",
        f"--wf-udp={udp_ports}",
        # UDP Discord Voice & STUN
        f"--filter-udp={udp_voice_filter}",
        "--filter-l7=discord,stun",
        "--dpi-desync=fake",
        "--dpi-desync-repeats=6",
        f'--dpi-desync-fake-discord={BIN_DIR / "quic_initial_www_google_com.bin"}',
        f'--dpi-desync-fake-stun={BIN_DIR / "quic_initial_www_google_com.bin"}',
        "--new",
        # UDP 443 General
        "--filter-udp=443",
        f'--hostlist={LISTS_DIR / "list-general.txt"}',
        f'--hostlist={LISTS_DIR / "list-general-user.txt"}',
        f'--hostlist-exclude={LISTS_DIR / "list-exclude.txt"}',
        f'--hostlist-exclude={LISTS_DIR / "list-exclude-user.txt"}',
        f'--ipset-exclude={LISTS_DIR / "ipset-exclude.txt"}',
        f'--ipset-exclude={LISTS_DIR / "ipset-exclude-user.txt"}',
        "--dpi-desync=fake",
        "--dpi-desync-repeats=11",
        f'--dpi-desync-fake-quic={BIN_DIR / "quic_initial_www_google_com.bin"}',
        "--new",
        # TCP Discord Media
        "--filter-tcp=2053,2083,2087,2096,8443",
        "--hostlist-domains=discord.media",
        f'--dpi-desync-fake-tls={BIN_DIR / "tls_clienthello_www_google_com.bin"}',
        *strat_parts,
        "--new",
        # TCP Google & Gemini
        "--filter-tcp=443",
        f'--hostlist={LISTS_DIR / "list-google.txt"}',
        f'--hostlist={LISTS_DIR / "list-gemini.txt"}',
        "--ip-id=zero",
        f'--dpi-desync-fake-tls={BIN_DIR / "tls_clienthello_www_google_com.bin"}',
        *strat_parts,
        "--new",
        # TCP General (HTTP/HTTPS)
        "--filter-tcp=80,443",
        f'--hostlist={LISTS_DIR / "list-general.txt"}',
        f'--hostlist={LISTS_DIR / "list-general-user.txt"}',
        f'--hostlist-exclude={LISTS_DIR / "list-exclude.txt"}',
        f'--hostlist-exclude={LISTS_DIR / "list-exclude-user.txt"}',
        f'--ipset-exclude={LISTS_DIR / "ipset-exclude.txt"}',
        f'--ipset-exclude={LISTS_DIR / "ipset-exclude-user.txt"}',
        f'--dpi-desync-fake-tls={BIN_DIR / "stun.bin"}',
        f'--dpi-desync-fake-tls={BIN_DIR / "tls_clienthello_www_google_com.bin"}',
        f'--dpi-desync-fake-http={BIN_DIR / "tls_clienthello_max_ru.bin"}',
        *strat_parts,
        "--new",
        # UDP Fallback (ipset-all)
        "--filter-udp=443",
        f'--ipset={LISTS_DIR / "ipset-all.txt"}',
        f'--hostlist-exclude={LISTS_DIR / "list-exclude.txt"}',
        f'--hostlist-exclude={LISTS_DIR / "list-exclude-user.txt"}',
        f'--ipset-exclude={LISTS_DIR / "ipset-exclude.txt"}',
        f'--ipset-exclude={LISTS_DIR / "ipset-exclude-user.txt"}',
        "--dpi-desync=fake",
        "--dpi-desync-repeats=11",
        f'--dpi-desync-fake-quic={BIN_DIR / "quic_initial_www_google_com.bin"}',
        "--new",
        # TCP Fallback (ipset-all)
        "--filter-tcp=80,443,8443",
        f'--ipset={LISTS_DIR / "ipset-all.txt"}',
        f'--hostlist-exclude={LISTS_DIR / "list-exclude.txt"}',
        f'--hostlist-exclude={LISTS_DIR / "list-exclude-user.txt"}',
        f'--ipset-exclude={LISTS_DIR / "ipset-exclude.txt"}',
        f'--ipset-exclude={LISTS_DIR / "ipset-exclude-user.txt"}',
        f'--dpi-desync-fake-tls={BIN_DIR / "stun.bin"}',
        f'--dpi-desync-fake-tls={BIN_DIR / "tls_clienthello_www_google_com.bin"}',
        f'--dpi-desync-fake-http={BIN_DIR / "tls_clienthello_max_ru.bin"}',
        *strat_parts,
        "--new",
    ]
    return args


def start_bypass_background(log_cb: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
    # Запуск без PIPE, при стартовом сбое чистим WinDivert и повторяем
    cfg = load_config()
    strat = cfg.get("strategy", "") or STRATEGIES[2]["args"]
    winws_exe = BIN_DIR / "winws.exe"
    if not winws_exe.exists():
        return False, f"winws.exe не найден в {BIN_DIR}"

    ensure_files_exist()
    kill_winws()
    cmd = get_winws_args(strat, cfg, log_cb=log_cb)

    def _spawn(capture_err: bool = False) -> tuple[Optional[subprocess.Popen], str]:
        kwargs = dict(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture_err else subprocess.DEVNULL,
            cwd=str(BIN_DIR),
            close_fds=True,
        )
        for flags in (BACKGROUND_FLAGS | CREATE_BREAKAWAY_FROM_JOB, BACKGROUND_FLAGS):
            try:
                proc = subprocess.Popen(cmd, creationflags=flags, **kwargs)
                return proc, ""
            except FileNotFoundError:
                return None, f"winws.exe не найден в {BIN_DIR}"
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
                return None, f"Ошибка запуска winws.exe: {e}"
        return None, "Не удалось запустить winws.exe"

    proc, err_msg = _spawn(capture_err=False)
    if proc is None:
        return False, err_msg

    for _ in range(6):
        time.sleep(0.2)
        if proc.poll() is not None:
            cleanup_windivert()
            time.sleep(0.5)
            diag_proc, diag_err = _spawn(capture_err=True)
            if diag_proc is None:
                return False, diag_err
            time.sleep(1.0)
            if diag_proc.poll() is not None:
                err_out = ""
                try:
                    if diag_proc.stderr:
                        err_out = diag_proc.stderr.read().decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass
                return False, f"winws.exe завершился сразу после запуска{': ' + err_out[:200] if err_out else ''}"
        # Повтор без PIPE, чтобы буфер не забился
            kill_winws()
            clean_proc, clean_err = _spawn(capture_err=False)
            if clean_proc is None:
                return False, clean_err
            time.sleep(0.8)
            if clean_proc.poll() is not None:
                return False, "winws.exe повторно завершился после запуска"
            return True, "Обход успешно запущен (после сброса WinDivert)"

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
                "nul",
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
            creationflags=CREATE_NO_WINDOW,
            timeout=timeout + 2,
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


def get_self_launch_spec() -> tuple[str, str, str]:
    argv0 = Path(sys.argv[0]).resolve() if sys.argv else Path(sys.executable).resolve()
    if argv0.suffix.lower() == ".exe":
        return str(argv0), "--background", str(argv0.parent)

    py_exe = Path(sys.executable).resolve()
    pyw_exe = py_exe.with_name("pythonw.exe")
    chosen_py = str(pyw_exe if pyw_exe.exists() else py_exe)
    return chosen_py, f'"{argv0}" --background', str(argv0.parent)


def _normalize_path_str(p: str) -> str:
    return os.path.normcase(os.path.normpath(p.strip().strip('"')))


def get_autorun_info() -> dict:
    expected_cmd, expected_args, expected_wd = get_self_launch_spec()
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
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
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
      <Interval>PT15S</Interval>
      <Count>3</Count>
    </RestartOnFailure>
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


def run_autorun_background() -> int:
    # Мьютекс от параллельного запуска триггеров при старте
    mutex = _kernel32.CreateMutexW(None, False, "Global\\ZapretUltraStableAutoStart")
    last_err = ctypes.get_last_error()
    if last_err == 183:  # ERROR_ALREADY_EXISTS
        _write_autorun_log("Другой экземпляр --background уже запускает обход, выход.")
        if mutex:
            _kernel32.CloseHandle(mutex)
        return 0

    try:
        ensure_files_exist()
        if is_winws_running():
            _write_autorun_log("winws.exe уже запущен, повторный запуск не требуется.")
            return 0

        for attempt in range(1, 6):
            ok, msg = start_bypass_background(log_cb=_write_autorun_log)
            _write_autorun_log(f"Попытка {attempt}/5: ok={ok}, msg={msg}")
            if ok:
                return 0
            cleanup_windivert()
            time.sleep(3)

        _write_autorun_log("Не удалось запустить обход после 5 попыток.")
        return 1
    except Exception as e:
        _write_autorun_log(f"Исключение в --background: {type(e).__name__}: {e}")
        return 1
    finally:
        if mutex:
            _kernel32.CloseHandle(mutex)


def scan_and_exclude_active_connections() -> dict:
    pids_to_name = iter_processes()
    if not pids_to_name:
        return {"ok": False, "error": "Не удалось получить список процессов", "added": [], "found_total": 0}

    ips_to_exclude: set[tuple[str, str, str, int]] = set()
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

            proc_name = pids_to_name.get(pid)
            if not proc_name:
                continue

            is_vpn = any(kw in proc_name for kw in VPN_KEYWORDS)
            is_game = any(kw in proc_name for kw in GAME_KEYWORDS)
            if not (is_vpn or is_game):
                continue

            ip_part = foreign_addr.rsplit(":", 1)[0].strip("[] ")
            try:
                ip_obj = ipaddress.ip_address(ip_part)
            except ValueError:
                continue

            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_unspecified
                or ip_obj.is_reserved
            ):
                continue

            prefix = 32 if ip_obj.version == 4 else 128
            category = "VPN" if is_vpn else "ИГРА"
            ips_to_exclude.add((str(ip_obj), proc_name, category, prefix))
    except Exception as e:
        return {"ok": False, "error": f"Ошибка netstat: {e}", "added": [], "found_total": 0}

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
        asset_url = ""
        for asset in data.get("assets") or []:
            aname = str(asset.get("name", "")).lower()
            if aname.endswith(".exe"):
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


def download_and_apply_update(asset_url: str) -> tuple[bool, str]:
    if not asset_url:
        return False, "В релизе нет .exe файла"

    is_compiled = ("__compiled__" in globals()) or bool(
        sys.argv and sys.argv[0] and Path(sys.argv[0]).suffix.lower() == ".exe"
    )
    if not is_compiled:
        return False, "Автообновление доступно только в скомпилированном .exe"

    target_exe = Path(sys.argv[0]).resolve()
    new_exe = target_exe.with_suffix(".exe.new")

    try:
        req = urllib.request.Request(asset_url, headers={"User-Agent": f"Unfit-Zapret/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if len(data) < 1_000_000 or not data.startswith(b"MZ"):
            return False, "Скачанный файл повреждён"
        new_exe.write_bytes(data)
    except Exception as e:
        return False, f"Ошибка скачивания: {e}"

    bat_path = Path(tempfile.gettempdir()) / "unfit_zapret_update.bat"
    pid = os.getpid()
    bat_content = (
        "@echo off\r\n"
        f':waitloop\r\ntasklist /fi "PID eq {pid}" | find "{pid}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "    timeout /t 1 /nobreak >nul\r\n"
        "    goto waitloop\r\n"
        ")\r\n"
        f'move /y "{new_exe}" "{target_exe}" >nul\r\n'
        f'start "" "{target_exe}"\r\n'
        'del "%~f0"\r\n'
    )
    try:
        bat_path.write_text(bat_content, encoding="cp1251")
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_path)],
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, "Обновление скачано, перезапуск..."
    except Exception as e:
        return False, f"Не удалось запустить обновление: {e}"
