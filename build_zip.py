import sys
import zipfile
from pathlib import Path

WORK_DIR = Path(__file__).resolve().parent
OUTPUT_ZIP = WORK_DIR.parent / "Unfit-Zapret.zip"
EMBEDDED_ZIP = WORK_DIR / "embedded_assets.zip"


def build_embedded_assets() -> Path:
    with zipfile.ZipFile(EMBEDDED_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        bin_dir = WORK_DIR / "bin"
        if bin_dir.exists():
            for f in sorted(bin_dir.iterdir()):
                if f.is_file() and f.name != "]":
                    zf.write(f, f"bin/{f.name}")
        lists_dir = WORK_DIR / "lists"
        if lists_dir.exists():
            for f in sorted(lists_dir.iterdir()):
                if f.is_file():
                    zf.write(f, f"lists/{f.name}")
    print(f"[OK] Встроенные ресурсы: {EMBEDDED_ZIP} ({EMBEDDED_ZIP.stat().st_size / 1024:.0f} KB)")
    return EMBEDDED_ZIP


def build_zip():
    exe_path = WORK_DIR / "Unfit-Zapret.exe"
    if not exe_path.exists():
        print("[ОШИБКА] Unfit-Zapret.exe не найден!")
        print("Сначала подготовьте embedded_assets.zip и скомпилируйте exe через Nuitka:")
        print("  python build_zip.py --assets")
        print("  python -m nuitka --onefile --standalone --enable-plugin=pyqt6 --windows-console-mode=disable --windows-uac-admin --windows-icon-from-ico=app_icon.ico --include-data-files=embedded_assets.zip=embedded_assets.zip --output-filename=Unfit-Zapret.exe zapret_manager.py")
        sys.exit(1)

    print(f"[*] Сборка архива: {OUTPUT_ZIP}")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(exe_path, "Unfit-Zapret.exe")
        print(f"  [+] Unfit-Zapret.exe  ({exe_path.stat().st_size / 1024:.0f} KB)")

    total_kb = OUTPUT_ZIP.stat().st_size / 1024
    print(f"\n[OK] Архив готов: {OUTPUT_ZIP} ({total_kb / 1024:.1f} MB)")


if __name__ == "__main__":
    if "--assets" in sys.argv[1:]:
        build_embedded_assets()
    else:
        build_zip()
