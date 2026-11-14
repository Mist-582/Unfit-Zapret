# Unfit Zapret

Графический менеджер обхода DPI для Windows (на базе [zapret / winws](https://github.com/bol-van/zapret) и PyQt6).

## Возможности
- Готовые стратегии обхода DPI для Discord, YouTube и других сервисов
- Встроенный **Авто-Тюнинг** с подбором оптимальной стратегии и Fake SNI
- **Надёжный автозапуск** через Планировщик задач Windows (Boot + Logon trigger)
- **Умные исключения**: домены (`list-exclude-user.txt`) и IP-подсети (`ipset-exclude-user.txt`), сканер активных подключений игр/VPN
- Проверка обновлений и автообновление из релизов GitHub

## Быстрый старт (для пользователей)
1. Скачайте `Unfit-Zapret.exe` из раздела [Releases](https://github.com/Mist-582/Unfit-Zapret/releases/latest).
2. Запустите `Unfit-Zapret.exe` (требуются права администратора для драйвера WinDivert).
3. Все рабочие компоненты автоматически распакуются в `C:\ProgramData\UnfitZapret`.

## Запуск из исходников и сборка `.exe`
Требуется Python 3.11+ и PyQt6 (`pip install PyQt6`). Для сборки одного `.exe` — Nuitka (`pip install nuitka`):

```powershell
python build_zip.py --assets
python -m nuitka --onefile --standalone --enable-plugin=pyqt6 --windows-console-mode=disable --windows-uac-admin --windows-icon-from-ico=app_icon.ico --include-data-files=embedded_assets.zip=embedded_assets.zip --output-filename=Unfit-Zapret.exe zapret_manager.py
```

## Ссылки
- GitHub: https://github.com/Mist-582
- Telegram: https://t.me/mist_582
- Канал: https://t.me/UnfitShop
- Discord: https://discord.gg/8RwY28XkY3
