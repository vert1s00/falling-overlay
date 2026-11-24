# Falling Overlay 🌸❄

A minimalist, lightweight desktop overlay for Windows: soft sakura petals or snowflakes slowly falling over your desktop.

- Two modes: **Sakura** and **Snow**
- Transparent and click-through, it never gets in your way
- Hides itself automatically when a fullscreen app (game, video, presentation) is active
- Low CPU usage: sprites are pre-rendered, animation runs at 30 FPS
- Multi-monitor support
- Tray icon menu: mode, density, pause, autostart, quit
- Remembers your settings

## Run from source

1. Install [Python 3.9+](https://www.python.org/downloads/) (tick **Add Python to PATH**)
2. Install the dependency:
   ```
   python -m pip install -r requirements.txt
   ```
3. Run:
   ```
   python falling.pyw
   ```

Optional: `python falling.pyw snow` starts in snow mode.

## Build a standalone .exe

Double-click `build.bat`. When it finishes, `dist\Sakura.exe` is ready. Python is not needed to run it.

## Controls

Click the tray icon (bottom right, maybe behind the `^` arrow) to open the menu.

## License

MIT

---

## По-русски

Минималистичные падающие лепестки сакуры или снег поверх рабочего стола (Windows). Окно прозрачное и пропускает клики, в полноэкранных приложениях скрывается само. Управление через иконку в трее. Запуск: `python -m pip install -r requirements.txt`, затем `python falling.pyw`. Для сборки `.exe` запусти `build.bat`.
