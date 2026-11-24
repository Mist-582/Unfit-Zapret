import io
import shutil
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

WORK_DIR = Path(__file__).resolve().parent
ROOT_PARENT = WORK_DIR.parent
OUTPUT_ZIP = ROOT_PARENT / "Unfit-Zapret.zip"
EMBEDDED_ZIP = WORK_DIR / "embedded_assets.zip"
NUITKA_EXE = ROOT_PARENT / "_nuitka_out" / "Unfit-Zapret.exe"
WIN_X86_BIN = ROOT_PARENT / "_nuitka_out" / "win_x86_bin"
RELEASE_DIR = ROOT_PARENT / "_release_assets"
ZAPRET_ZIP_URL = "https://github.com/bol-van/zapret/releases/download/v72.13/zapret-v72.13.zip"

COMMON_SOURCES = [
    "zapret_core.py",
    "zapret_manager.py",
    "tg_proxy.py",
    "zapret_config.json",
    "app_icon.ico",
    "README.md",
]

LINUX_ARCHES = ("x86_64", "arm64", "arm", "x86")


def _bin_payloads() -> list[Path]:
    bin_dir = WORK_DIR / "bin"
    if not bin_dir.exists():
        return []
    return [f for f in sorted(bin_dir.iterdir()) if f.is_file() and f.suffix.lower() == ".bin"]


def _list_files() -> list[Path]:
    lists_dir = WORK_DIR / "lists"
    if not lists_dir.exists():
        return []
    return [f for f in sorted(lists_dir.iterdir()) if f.is_file()]


def build_embedded_assets() -> Path:
    with zipfile.ZipFile(EMBEDDED_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        bin_dir = WORK_DIR / "bin"
        if bin_dir.exists():
            for f in sorted(bin_dir.iterdir()):
                if f.is_file() and f.name != "]":
                    zf.write(f, f"bin/{f.name}")
        for f in _list_files():
            zf.write(f, f"lists/{f.name}")
        ico = WORK_DIR / "app_icon.ico"
        if ico.is_file():
            zf.write(ico, "app_icon.ico")
    print(f"[OK] Встроенные ресурсы: {EMBEDDED_ZIP} ({EMBEDDED_ZIP.stat().st_size / 1024:.0f} KB)")
    return EMBEDDED_ZIP


def _resolve_win64_exe() -> Path:
    if NUITKA_EXE.exists():
        return NUITKA_EXE
    local_exe = WORK_DIR / "Unfit-Zapret.exe"
    if local_exe.exists():
        return local_exe
    return NUITKA_EXE


def build_zip() -> Path:
    exe_path = _resolve_win64_exe()
    if not exe_path.exists():
        print("[ОШИБКА] Unfit-Zapret.exe не найден!")
        sys.exit(1)

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(exe_path, "Unfit-Zapret.exe")
    print(f"[OK] Архив Windows x64: {OUTPUT_ZIP} ({OUTPUT_ZIP.stat().st_size / (1024 * 1024):.1f} MB)")
    return OUTPUT_ZIP


def _add_tar_bytes(tf: tarfile.TarFile, arcname: str, data: bytes, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mode = mode
    info.mtime = int(time.time())
    tf.addfile(info, io.BytesIO(data))


def build_linux_tarball(arch: str, out_dir: Path) -> Path:
    out_path = out_dir / f"Unfit-Zapret-linux-{arch}.tar.gz"
    nfqws_bin = WORK_DIR / "bin" / f"nfqws-linux-{arch}"
    if not nfqws_bin.exists():
        raise FileNotFoundError(f"Бинарник не найден: {nfqws_bin}")

    prefix = f"Unfit-Zapret-linux-{arch}"
    with tarfile.open(out_path, "w:gz") as tf:
        for fname in COMMON_SOURCES:
            src = WORK_DIR / fname
            if src.exists():
                _add_tar_bytes(tf, f"{prefix}/{fname}", src.read_bytes(), 0o644)
        sh_src = WORK_DIR / "start_linux.sh"
        if sh_src.exists():
            sh_data = sh_src.read_bytes().replace(b"\r\n", b"\n")
            _add_tar_bytes(tf, f"{prefix}/start_linux.sh", sh_data, 0o755)
        _add_tar_bytes(tf, f"{prefix}/bin/nfqws-linux-{arch}", nfqws_bin.read_bytes(), 0o755)
        for p in _bin_payloads():
            _add_tar_bytes(tf, f"{prefix}/bin/{p.name}", p.read_bytes(), 0o644)
        for p in _list_files():
            _add_tar_bytes(tf, f"{prefix}/lists/{p.name}", p.read_bytes(), 0o644)
    print(f"[OK] Архив Linux ({arch}): {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")
    return out_path


def _ensure_win_x86_bins(target_dir: Path) -> None:
    req_bins = ("winws.exe", "WinDivert.dll", "WinDivert32.sys", "cygwin1.dll")
    if all((target_dir / b).exists() for b in req_bins):
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(ZAPRET_ZIP_URL, headers={"User-Agent": "Unfit-Zapret-Builder"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        buf = io.BytesIO(resp.read())
    with zipfile.ZipFile(buf) as zf:
        for b in req_bins:
            (target_dir / b).write_bytes(zf.read(f"zapret-v72.13/binaries/windows-x86/{b}"))


def build_win_x86_zip(out_dir: Path, fetch: bool = False) -> Path:
    out_path = out_dir / "Unfit-Zapret-win-x86.zip"
    req_bins = ("winws.exe", "WinDivert.dll", "WinDivert32.sys", "cygwin1.dll")
    if fetch:
        _ensure_win_x86_bins(WIN_X86_BIN)
    for b in req_bins:
        if not (WIN_X86_BIN / b).exists():
            raise FileNotFoundError(f"32-bit компонент не найден: {WIN_X86_BIN / b}")

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fname in COMMON_SOURCES + ["ЗАПУСК_МЕНЮ.bat"]:
            src = WORK_DIR / fname
            if src.exists():
                zf.write(src, fname)
        for b in req_bins:
            zf.write(WIN_X86_BIN / b, f"bin/{b}")
        for p in _bin_payloads():
            zf.write(p, f"bin/{p.name}")
        for p in _list_files():
            zf.write(p, f"lists/{p.name}")
    print(f"[OK] Архив Windows x86: {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")
    return out_path


def _parse_out_dir() -> Path:
    if "--out-dir" in sys.argv[1:]:
        idx = sys.argv.index("--out-dir")
        if idx + 1 < len(sys.argv):
            return Path(sys.argv[idx + 1]).resolve()
    return RELEASE_DIR


def build_all_platforms() -> None:
    out_dir = _parse_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    exe_src = _resolve_win64_exe()
    if not exe_src.exists():
        print("[ОШИБКА] Unfit-Zapret.exe не найден!")
        sys.exit(1)

    shutil.copy2(exe_src, out_dir / "Unfit-Zapret.exe")
    print(f"[OK] Windows x64/ARM64 exe: {out_dir / 'Unfit-Zapret.exe'}")

    build_zip()
    if WIN_X86_BIN.exists() or "--fetch-win-x86" in sys.argv[1:]:
        build_win_x86_zip(out_dir, fetch="--fetch-win-x86" in sys.argv[1:])
    for arch in LINUX_ARCHES:
        build_linux_tarball(arch, out_dir)


if __name__ == "__main__":
    out_dir = _parse_out_dir()
    if "--assets" in sys.argv[1:]:
        build_embedded_assets()
    elif "--linux-all" in sys.argv[1:]:
        out_dir.mkdir(parents=True, exist_ok=True)
        for arch in LINUX_ARCHES:
            build_linux_tarball(arch, out_dir)
    elif "--win-x86" in sys.argv[1:]:
        out_dir.mkdir(parents=True, exist_ok=True)
        build_win_x86_zip(out_dir, fetch=True)
    elif "--all-platforms" in sys.argv[1:]:
        build_all_platforms()
    else:
        build_zip()
