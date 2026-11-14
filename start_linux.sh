#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 не найден. Установите Python 3.10+ и PyQt6."
    exit 1
fi

if ! python3 -c "import PyQt6" >/dev/null 2>&1; then
    echo "[*] Установка PyQt6..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3-pyqt6 curl || true
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --noconfirm python-pyqt6 curl || true
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3-qt6 curl || true
    fi
    if ! python3 -c "import PyQt6" >/dev/null 2>&1; then
        python3 -m pip install --user PyQt6 || {
            echo "[ERROR] Не удалось установить PyQt6. Установите вручную: pip install PyQt6"
            exit 1
        }
    fi
fi

# Запуск с правами root нужен для nftables/iptables NFQUEUE и nfqws
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    if command -v pkexec >/dev/null 2>&1 && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
        exec pkexec env \
            DISPLAY="${DISPLAY:-}" \
            WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" \
            XAUTHORITY="${XAUTHORITY:-}" \
            XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}" \
            python3 "$DIR/zapret_manager.py" "$@"
    else
        exec sudo -E python3 "$DIR/zapret_manager.py" "$@"
    fi
fi

exec python3 "$DIR/zapret_manager.py" "$@"
