# Unfit Zapret

Кроссплатформенный графический менеджер обхода DPI для **Windows** и **Linux** (на базе [zapret](https://github.com/bol-van/zapret) `winws` / `nfqws` и PyQt6).

## Возможности (v2.2.0)
- **20 актуальных стратегий обхода DPI 2026 года:** 12 свежих пресетов (`ALT13 Sochi`, `ALT11 Sferum 664 + STUN2`, `EXP 480`, `Fake TLS Auto`, `ALT9 Ozon`, `ALT7 SNIExt+1`) и 8 кастомных стратегий `[Unfit AI-1..8]` против ML/ИИ-анализаторов ТСПУ
- **Двойной обход Telegram:** DPI-десинхронизация (`list-telegram.txt`, `ipset-telegram.txt`, порт `5222`) + улучшенный **Telegram WS-Мост** (`127.0.0.1:1443`, пре-пул WebSocket, обход блокировок по Cloudflare на порту 443/80 и кнопка самопроверки)
- **Встроенный DNS-AI (`dns-ai.ru`):** включение шифрованного DNS (DoH на Windows 11 / клиент DNS-AI на Windows 10 / DoT на Linux) в один клик для работы ChatGPT, Claude, Gemini и других нейросетей без VPN
- **Удобная установка:** все рабочие файлы хранятся в открытой папке `C:\UnfitZapret` с автоматическим созданием ярлыка на рабочем столе и миграцией настроек
- **Авто-Тюнинг** с параллельной проверкой YouTube, Discord и Telegram и подбором Fake SNI
- **Кроссплатформенный автозапуск:** Планировщик задач Windows (`SYSTEM`) и `systemd`-сервис Linux
- **Умные исключения** и автоматическое обновление прямо из интерфейса

## Поддерживаемые ОС и архитектуры

| Платформа | Архитектура | Файл в Releases | Движок |
| :--- | :--- | :--- | :--- |
| Windows 10/11 | `x86_64` (64-bit) / `ARM64` | `Unfit-Zapret.exe` | `winws.exe` + `WinDivert64` |
| Windows 10/11 | `x86` (32-bit) | `Unfit-Zapret-win-x86.zip` | `winws.exe` + `WinDivert32` |
| Linux | `x86_64` (`amd64`) | `Unfit-Zapret-linux-x86_64.tar.gz` | `nfqws` + `nftables`/`iptables` |
| Linux | `arm64` (`aarch64`, Raspberry Pi / серверы) | `Unfit-Zapret-linux-arm64.tar.gz` | `nfqws` + `nftables`/`iptables` |
| Linux | `armv7` (`armhf`, 32-bit ARM) | `Unfit-Zapret-linux-arm.tar.gz` | `nfqws` + `nftables`/`iptables` |
| Linux | `x86` (`i686`, 32-bit) | `Unfit-Zapret-linux-x86.tar.gz` | `nfqws` + `nftables`/`iptables` |

## Быстрый старт

### Windows (64-bit / ARM64)
1. Скачайте `Unfit-Zapret.exe` из [Releases](https://github.com/Mist-582/Unfit-Zapret/releases/latest).
2. Запустите файл от имени администратора — приложение установится в `C:\UnfitZapret` и создаст ярлык на рабочем столе.

### Windows (32-bit x86)
1. Скачайте и распакуйте `Unfit-Zapret-win-x86.zip` (требуется Python 3.10+ и `pip install PyQt6`).
2. Запустите `ЗАПУСК_МЕНЮ.bat` от имени администратора.

### Linux (`x86_64`, `arm64`, `armv7`, `x86`)
```bash
tar -xzf Unfit-Zapret-linux-x86_64.tar.gz   # выберите свою архитектуру
cd Unfit-Zapret-linux-x86_64
chmod +x start_linux.sh
./start_linux.sh
```
Для Linux нужны `nftables` (или `iptables`), `curl`, `python3` и `PyQt6` (`start_linux.sh` проверит и поможет поставить `PyQt6` при первом запуске).

## Сборка из исходников
```powershell
python build_zip.py --assets
python -m nuitka --onefile --standalone --enable-plugin=pyqt6 --windows-console-mode=disable --windows-uac-admin --windows-icon-from-ico=app_icon.ico --include-data-files=embedded_assets.zip=embedded_assets.zip --output-filename=Unfit-Zapret.exe zapret_manager.py
python build_zip.py --all-platforms
```

## Ссылки
- GitHub: https://github.com/Mist-582
- Telegram: https://t.me/mist_582
- Канал: https://t.me/UnfitShop
- Discord: https://discord.gg/8RwY28XkY3
