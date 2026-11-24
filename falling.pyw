"""
Падающий снег / лепестки сакуры поверх рабочего стола (Windows).

Запуск:  python falling.pyw
Всё управление: иконка в трее (справа внизу, возможно за стрелкой "^").
Клик по иконке открывает меню: режим, плотность, пауза, автозапуск, выход.
"""
import math
import os
import random
import sys
import time

from PySide6.QtCore import Qt, QTimer, QPointF, QSettings
from PySide6.QtGui import (QAction, QActionGroup, QColor, QCursor, QIcon,
                           QLinearGradient, QPainter, QPainterPath, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

IS_WIN = sys.platform == "win32"
FPS = 30

DENSITY = {"Fewer": 0.6, "Normal": 1.0, "More": 1.6}
BASE_COUNT = {"snow": 70, "sakura": 40}

PETAL_COLORS = ["#FFC9D8", "#FFB7CC", "#FFD9E4"]
SNOW_SIZES = [3, 4, 5, 6, 8, 10]
PETAL_SIZES = [9, 11, 13, 15, 18]

APP_NAME = "FallingOverlay"


# ---------- Windows: полноэкранное окно, автозапуск, один экземпляр ----------

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]

    IGNORED_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

    def fullscreen_active():
        """True, если активное окно закрывает весь монитор (игра, видео, презентация)."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return False
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value in IGNORED_CLASSES:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return False
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        mon = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(mon, ctypes.byref(mi))
        m = mi.rcMonitor
        return (rect.left <= m.left and rect.top <= m.top and
                rect.right >= m.right and rect.bottom >= m.bottom)

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def autostart_command():
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        exe = pythonw if os.path.exists(pythonw) else sys.executable
        return f'"{exe}" "{os.path.abspath(__file__)}"'

    def autostart_enabled():
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, APP_NAME)
                return True
        except OSError:
            return False

    def set_autostart(on):
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass

    def already_running():
        kernel32.CreateMutexW(None, False, "Local\\" + APP_NAME + "Mutex")
        return kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
else:
    def fullscreen_active():
        return False

    def autostart_enabled():
        return False

    def set_autostart(on):
        pass

    def already_running():
        return False


# ---------- заранее отрисованные спрайты ----------

def make_snow_sprites(dpr):
    sprites = []
    for d in SNOW_SIZES:
        size = d + 4
        pm = QPixmap(int(size * dpr), int(size * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        c = size / 2
        g = QRadialGradient(c, c, size / 2)
        g.setColorAt(0.0, QColor(255, 255, 255, 255))
        g.setColorAt(0.55, QColor(255, 255, 255, 235))
        g.setColorAt(0.85, QColor(205, 225, 255, 90))
        g.setColorAt(1.0, QColor(205, 225, 255, 0))
        p.setBrush(g)
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, size, size)
        p.end()
        sprites.append((pm, size, size))
    return sprites


def petal_path(w, h):
    path = QPainterPath()
    path.moveTo(w * 0.5, h * 0.98)
    path.cubicTo(w * -0.05, h * 0.70, w * 0.02, h * 0.10, w * 0.42, h * 0.06)
    path.quadTo(w * 0.5, h * 0.24, w * 0.58, h * 0.06)
    path.cubicTo(w * 0.98, h * 0.10, w * 1.05, h * 0.70, w * 0.5, h * 0.98)
    path.closeSubpath()
    return path


def make_petal_sprites(dpr):
    sprites = []
    for s in PETAL_SIZES:
        row = []
        for col in PETAL_COLORS:
            pm = QPixmap(int(s * dpr), int(s * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            g = QLinearGradient(0, s, 0, 0)
            g.setColorAt(0.0, QColor("#FFF4F7"))
            g.setColorAt(1.0, QColor(col))
            p.setBrush(g)
            p.setPen(Qt.NoPen)
            p.drawPath(petal_path(s, s))
            p.end()
            row.append((pm, s, s))
        sprites.append(row)
    return sprites


# ---------- частица ----------

class Particle:
    __slots__ = ("x", "y", "depth", "vy", "sway_a", "sway_f", "phase",
                 "rot", "rot_v", "flip", "flip_v", "alpha", "si", "ci")

    def __init__(self, w, h, mode, scatter):
        self.reset(w, h, mode, scatter)

    def reset(self, w, h, mode, scatter):
        r = random.random
        self.depth = r()
        self.x = r() * w
        self.y = r() * h if scatter else -r() * 60 - 20
        self.phase = r() * math.tau
        self.sway_f = 0.4 + r() * 0.6
        self.alpha = 0.45 + 0.5 * self.depth
        if mode == "snow":
            self.vy = 22 + self.depth * 40
            self.sway_a = 6 + r() * 12
            self.si = min(int(self.depth * len(SNOW_SIZES)), len(SNOW_SIZES) - 1)
            self.rot = self.rot_v = self.flip = self.flip_v = 0.0
            self.ci = 0
        else:
            self.vy = 28 + self.depth * 32
            self.sway_a = 14 + r() * 26
            self.si = min(int(self.depth * len(PETAL_SIZES)), len(PETAL_SIZES) - 1)
            self.ci = random.randrange(len(PETAL_COLORS))
            self.rot = r() * 360
            self.rot_v = (r() - 0.5) * 70
            self.flip = r() * math.tau
            self.flip_v = 1.0 + r() * 1.8


# ---------- прозрачное окно на один монитор ----------

class Overlay(QWidget):
    def __init__(self, screen):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.Tool | Qt.WindowTransparentForInput |
                            Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(screen.geometry())
        self.dpr = screen.devicePixelRatio()
        self.mode = None
        self.particles = []
        self.sprites = []

    def configure(self, mode, density):
        if mode != self.mode:
            self.mode = mode
            self.sprites = (make_snow_sprites(self.dpr) if mode == "snow"
                            else make_petal_sprites(self.dpr))
        count = int(BASE_COUNT[mode] * density * (self.width() * self.height()) / (1920 * 1080))
        count = max(count, 15)
        w, h = self.width(), self.height()
        self.particles = [Particle(w, h, mode, True) for _ in range(count)]

    def step(self, dt, t):
        w, h = self.width(), self.height()
        wind = math.sin(t * 0.20) * 14 + math.sin(t * 0.07) * 8
        mode = self.mode
        for q in self.particles:
            q.y += q.vy * dt
            q.x += (wind * (0.4 + q.depth) + math.sin(t * q.sway_f + q.phase) * q.sway_a) * dt
            q.rot += q.rot_v * dt
            q.flip += q.flip_v * dt
            if q.y > h + 30:
                q.reset(w, h, mode, False)
            elif q.x < -30:
                q.x += w + 60
            elif q.x > w + 30:
                q.x -= w + 60
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.mode == "snow":
            for q in self.particles:
                pm, w, h = self.sprites[q.si]
                p.setOpacity(q.alpha)
                p.drawPixmap(QPointF(q.x - w / 2, q.y - h / 2), pm)
        else:
            for q in self.particles:
                pm, w, h = self.sprites[q.si][q.ci]
                p.setOpacity(q.alpha)
                p.save()
                p.translate(q.x, q.y)
                p.rotate(q.rot)
                p.scale(1.0, 0.35 + 0.65 * abs(math.cos(q.flip)))
                p.drawPixmap(QPointF(-w / 2, -h / 2), pm)
                p.restore()
        p.end()


# ---------- приложение с иконкой в трее ----------

class App:
    def __init__(self, forced_mode):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.settings = QSettings("FallingOverlay", "FallingOverlay")

        self.mode = forced_mode or self.settings.value("mode", "sakura")
        if self.mode not in BASE_COUNT:
            self.mode = "sakura"
        self.density = self.settings.value("density", "Normal")
        if self.density not in DENSITY:
            self.density = "Normal"
        self.hide_fs = self.settings.value("hide_fullscreen", True, type=bool)

        self.paused = False
        self.fs = False

        self.overlays = [Overlay(s) for s in self.app.screens()]
        self.apply()

        self.timer = QTimer()
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(1000 // FPS)
        self.timer.timeout.connect(self.tick)
        self.t0 = self.last = time.perf_counter()

        self.fs_timer = QTimer()
        self.fs_timer.setInterval(1000)
        self.fs_timer.timeout.connect(self.check_fullscreen)
        self.fs_timer.start()

        self.build_tray()
        self.update_visibility()
        self.tray.showMessage("Falling overlay is running",
                              "Use the tray icon (bottom right) to control it.",
                              QSystemTrayIcon.Information, 4000)

    # --- анимация ---
    def apply(self):
        for o in self.overlays:
            o.configure(self.mode, DENSITY[self.density])

    def tick(self):
        now = time.perf_counter()
        dt = min(now - self.last, 0.1)
        self.last = now
        t = now - self.t0
        for o in self.overlays:
            o.step(dt, t)

    def update_visibility(self):
        active = not self.paused and not self.fs
        if active and not self.timer.isActive():
            self.last = time.perf_counter()
            for o in self.overlays:
                o.show()
            self.timer.start()
        elif not active and self.timer.isActive():
            self.timer.stop()
            for o in self.overlays:
                o.hide()

    def check_fullscreen(self):
        fs = self.hide_fs and fullscreen_active()
        if fs != self.fs:
            self.fs = fs
            self.update_visibility()

    # --- трей ---
    def tray_icon(self):
        if self.mode == "sakura":
            pm = make_petal_sprites(4.0)[-1][0][0]
        else:
            pm = QPixmap(32, 32)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor("#9EC9FF"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(6, 6, 20, 20)
            p.end()
        return QIcon(pm)

    def build_tray(self):
        self.tray = QSystemTrayIcon(self.tray_icon())
        self.tray.setToolTip("Petals / snow - click for menu")
        menu = QMenu()

        mode_group = QActionGroup(menu)
        for key, title in (("sakura", "Sakura"), ("snow", "Snow")):
            a = QAction(title, menu, checkable=True)
            a.setChecked(key == self.mode)
            a.triggered.connect(lambda _=False, k=key: self.set_mode(k))
            mode_group.addAction(a)
            menu.addAction(a)
        menu.addSeparator()

        dens_group = QActionGroup(menu)
        for name in DENSITY:
            a = QAction(name, menu, checkable=True)
            a.setChecked(name == self.density)
            a.triggered.connect(lambda _=False, n=name: self.set_density(n))
            dens_group.addAction(a)
            menu.addAction(a)
        menu.addSeparator()

        fs_action = QAction("Hide in fullscreen apps", menu, checkable=True)
        fs_action.setChecked(self.hide_fs)
        fs_action.triggered.connect(self.set_hide_fs)
        menu.addAction(fs_action)

        if IS_WIN:
            auto = QAction("Start with Windows", menu, checkable=True)
            auto.setChecked(autostart_enabled())
            auto.triggered.connect(lambda c: set_autostart(c))
            menu.addAction(auto)

        pause = QAction("Pause", menu, checkable=True)
        pause.triggered.connect(self.toggle_pause)
        menu.addAction(pause)

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        self._keep = (menu, mode_group, dens_group, fs_action, pause)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_click)
        self.tray.show()

    def on_tray_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # обычный левый клик
            self.tray.contextMenu().popup(QCursor.pos())

    def set_mode(self, mode):
        self.mode = mode
        self.settings.setValue("mode", mode)
        self.apply()
        self.tray.setIcon(self.tray_icon())

    def set_density(self, name):
        self.density = name
        self.settings.setValue("density", name)
        self.apply()

    def set_hide_fs(self, checked):
        self.hide_fs = checked
        self.settings.setValue("hide_fullscreen", checked)
        self.check_fullscreen()

    def toggle_pause(self, checked):
        self.paused = checked
        self.update_visibility()

    def run(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    if already_running():
        sys.exit(0)
    arg = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in BASE_COUNT else None
    App(arg).run()
