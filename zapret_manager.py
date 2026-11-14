from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

# Автозапуск без загрузки PyQt6
if "--background" in sys.argv[1:]:
    import zapret_core
    if not zapret_core.is_admin():
        zapret_core.relaunch_as_admin()
        sys.exit(0)
    sys.exit(zapret_core.run_autorun_background())

import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from PyQt6.QtCore import (
    QObject,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QDesktopServices,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import zapret_core as core


APP_TITLE = f"{core.APP_NAME} v{core.APP_VERSION}"
SINGLE_INSTANCE_KEY = "ZapretUltraStable_SingleInstance_v2"


def make_round_avatar(raw_bytes: bytes, size: int = 52) -> QPixmap | None:
    src = QPixmap()
    if not src.loadFromData(raw_bytes):
        return None
    scaled = src.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    clip = QPainterPath()
    clip.addEllipse(QRectF(2.0, 2.0, size - 4.0, size - 4.0))
    p.setClipPath(clip)
    x_off = (size - scaled.width()) // 2
    y_off = (size - scaled.height()) // 2
    p.drawPixmap(x_off, y_off, scaled)

    p.setClipping(False)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#FF1E42"), 2.0))
    p.drawEllipse(QRectF(1.5, 1.5, size - 3.0, size - 3.0))
    p.end()
    return out


def create_demon_crest_icon(active: bool = False, size: int = 128) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = float(size)
    cx, cy = s * 0.5, s * 0.5

    bg_grad = QRadialGradient(cx, cy, s * 0.48)
    if active:
        bg_grad.setColorAt(0.0, QColor("#2D0716"))
        bg_grad.setColorAt(0.7, QColor("#16081C"))
        bg_grad.setColorAt(1.0, QColor("#09050D"))
    else:
        bg_grad.setColorAt(0.0, QColor("#1D0E29"))
        bg_grad.setColorAt(0.75, QColor("#110917"))
        bg_grad.setColorAt(1.0, QColor("#08050C"))

    p.setBrush(bg_grad)
    ring_color = QColor("#FF1E42" if active else "#9333EA")
    p.setPen(QPen(ring_color, max(2.0, s * 0.045)))
    p.drawEllipse(QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88))

    inner_pen = QPen(QColor("#FBBF24" if active else "#7E22CE"), max(1.2, s * 0.02))
    p.setPen(inner_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72))

    tick_pen = QPen(QColor("#FF4D6D" if active else "#A855F7"), max(1.2, s * 0.025))
    tick_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(tick_pen)
    for k in range(8):
        ang = math.radians(k * 45.0)
        x1 = cx + math.cos(ang) * (s * 0.36)
        y1 = cy + math.sin(ang) * (s * 0.36)
        x2 = cx + math.cos(ang) * (s * 0.43)
        y2 = cy + math.sin(ang) * (s * 0.43)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    crest = QPainterPath()
    crest.moveTo(s * 0.25, s * 0.27)
    crest.lineTo(s * 0.38, s * 0.37)
    crest.lineTo(s * 0.50, s * 0.20)
    crest.lineTo(s * 0.62, s * 0.37)
    crest.lineTo(s * 0.75, s * 0.27)
    crest.lineTo(s * 0.69, s * 0.61)
    crest.quadTo(s * 0.50, s * 0.83, s * 0.50, s * 0.83)
    crest.quadTo(s * 0.50, s * 0.83, s * 0.31, s * 0.61)
    crest.closeSubpath()

    crest_grad = QLinearGradient(s * 0.25, s * 0.20, s * 0.75, s * 0.82)
    if active:
        crest_grad.setColorAt(0.0, QColor("#FF1E42"))
        crest_grad.setColorAt(0.55, QColor("#B91C1C"))
        crest_grad.setColorAt(1.0, QColor("#7C3AED"))
    else:
        crest_grad.setColorAt(0.0, QColor("#A855F7"))
        crest_grad.setColorAt(0.55, QColor("#581C87"))
        crest_grad.setColorAt(1.0, QColor("#9F1239"))

    p.setBrush(crest_grad)
    p.setPen(QPen(QColor("#FDE68A" if active else "#E9D5FF"), max(1.4, s * 0.025)))
    p.drawPath(crest)

    eye_outer = QPainterPath()
    eye_outer.moveTo(s * 0.34, s * 0.53)
    eye_outer.quadTo(s * 0.50, s * 0.41, s * 0.66, s * 0.53)
    eye_outer.quadTo(s * 0.50, s * 0.65, s * 0.34, s * 0.53)
    eye_outer.closeSubpath()
    p.setBrush(QColor("#0B0610"))
    p.setPen(QPen(QColor("#FBBF24" if active else "#C084FC"), max(1.2, s * 0.02)))
    p.drawPath(eye_outer)

    iris_grad = QRadialGradient(cx, s * 0.53, s * 0.08)
    iris_grad.setColorAt(0.0, QColor("#FEF08A" if active else "#F472B6"))
    iris_grad.setColorAt(0.5, QColor("#FF1E42"))
    iris_grad.setColorAt(1.0, QColor("#7F1D1D"))
    p.setBrush(iris_grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, s * 0.53), s * 0.075, s * 0.075)

    p.setBrush(QColor("#09040C"))
    p.drawEllipse(QPointF(cx, s * 0.53), s * 0.022, s * 0.058)

    p.end()
    return QIcon(pm)


def create_demon_cursors() -> dict[str, QCursor]:
    pm_arrow = QPixmap(32, 32)
    pm_arrow.fill(Qt.GlobalColor.transparent)
    pa = QPainter(pm_arrow)
    pa.setRenderHint(QPainter.RenderHint.Antialiasing)

    blade = QPolygonF([
        QPointF(3.0, 2.0),
        QPointF(21.0, 14.0),
        QPointF(13.5, 16.0),
        QPointF(17.5, 25.5),
        QPointF(14.5, 27.0),
        QPointF(10.0, 17.5),
        QPointF(4.5, 23.0),
    ])
    grad_b = QLinearGradient(3, 2, 20, 26)
    grad_b.setColorAt(0.0, QColor("#FF2A4B"))
    grad_b.setColorAt(0.5, QColor("#4C0519"))
    grad_b.setColorAt(1.0, QColor("#1E0B2B"))
    pa.setBrush(grad_b)
    pa.setPen(QPen(QColor("#FFE4E6"), 1.3))
    pa.drawPolygon(blade)

    pa.setPen(QPen(QColor("#FBBF24"), 1.2))
    pa.drawLine(QPointF(4.5, 4.0), QPointF(12.2, 14.5))
    pa.end()

    pm_ptr = QPixmap(32, 32)
    pm_ptr.fill(Qt.GlobalColor.transparent)
    pp = QPainter(pm_ptr)
    pp.setRenderHint(QPainter.RenderHint.Antialiasing)

    glow = QRadialGradient(5.0, 4.0, 9.0)
    glow.setColorAt(0.0, QColor(255, 42, 75, 190))
    glow.setColorAt(0.6, QColor(147, 51, 234, 90))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    pp.setBrush(glow)
    pp.setPen(Qt.PenStyle.NoPen)
    pp.drawEllipse(QPointF(5.0, 4.0), 9.0, 9.0)

    ptr_poly = QPolygonF([
        QPointF(4.0, 3.0),
        QPointF(22.0, 13.0),
        QPointF(14.0, 16.5),
        QPointF(19.0, 26.0),
        QPointF(15.5, 28.0),
        QPointF(10.5, 18.5),
        QPointF(5.0, 24.0),
    ])
    grad_p = QLinearGradient(4, 3, 22, 27)
    grad_p.setColorAt(0.0, QColor("#FDE047"))
    grad_p.setColorAt(0.45, QColor("#FF1E42"))
    grad_p.setColorAt(1.0, QColor("#9333EA"))
    pp.setBrush(grad_p)
    pp.setPen(QPen(QColor("#FFFBEB"), 1.4))
    pp.drawPolygon(ptr_poly)
    pp.end()

    pm_ibeam = QPixmap(24, 28)
    pm_ibeam.fill(Qt.GlobalColor.transparent)
    pi = QPainter(pm_ibeam)
    pi.setRenderHint(QPainter.RenderHint.Antialiasing)
    pi.setPen(QPen(QColor("#140814"), 3.6))
    pi.drawLine(12, 4, 12, 24)
    pi.drawLine(8, 4, 16, 4)
    pi.drawLine(8, 24, 16, 24)
    pi.setPen(QPen(QColor("#FF3355"), 1.8))
    pi.drawLine(12, 4, 12, 24)
    pi.setPen(QPen(QColor("#FBBF24"), 1.8))
    pi.drawLine(8, 4, 16, 4)
    pi.drawLine(8, 24, 16, 24)
    pi.end()

    return {
        "arrow": QCursor(pm_arrow, 3, 2),
        "pointer": QCursor(pm_ptr, 4, 3),
        "ibeam": QCursor(pm_ibeam, 12, 14),
    }


class DemonAuraWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RootWidget")
        self._phase = 0.0
        self._active_mode = False

        rng = random.Random(42)
        self._particles = [
            {
                "x": rng.random(),
                "y": rng.random(),
                "vy": 0.0012 + rng.random() * 0.0022,
                "vx": (rng.random() - 0.5) * 0.0008,
                "r": 1.3 + rng.random() * 2.4,
                "kind": rng.choice(["crimson", "crimson", "violet", "gold"]),
                "offset": rng.random() * 6.28,
            }
            for _ in range(26)
        ]

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)

    def set_active_mode(self, active: bool):
        if self._active_mode != active:
            self._active_mode = active
            self.update()

    def set_paused(self, paused: bool):
        if paused:
            self._anim_timer.stop()
        elif not self._anim_timer.isActive():
            self._anim_timer.start(36)

    def _tick(self):
        speed = 0.028 if self._active_mode else 0.014
        self._phase = (self._phase + speed) % (math.pi * 200)
        for pt in self._particles:
            pt["y"] -= pt["vy"] * (1.45 if self._active_mode else 0.85)
            pt["x"] += pt["vx"] + math.sin(self._phase + pt["offset"]) * 0.00035
            if pt["y"] < -0.05:
                pt["y"] = 1.05
            if pt["x"] < -0.05:
                pt["x"] = 1.05
            elif pt["x"] > 1.05:
                pt["x"] = -0.05
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())

        base_grad = QLinearGradient(0, 0, w, h)
        base_grad.setColorAt(0.0, QColor("#08060D"))
        base_grad.setColorAt(0.55, QColor("#0E0816"))
        base_grad.setColorAt(1.0, QColor("#120713"))
        p.fillRect(self.rect(), base_grad)

        pulse1 = 0.5 + 0.5 * math.sin(self._phase * 0.9)
        pulse2 = 0.5 + 0.5 * math.cos(self._phase * 0.7)

        crimson_alpha = int((48 if self._active_mode else 26) + pulse1 * (28 if self._active_mode else 14))
        violet_alpha = int((38 if self._active_mode else 28) + pulse2 * 22)

        g1 = QRadialGradient(w * (0.78 + 0.04 * math.sin(self._phase * 0.4)), h * 0.22, max(w, h) * 0.55)
        g1.setColorAt(0.0, QColor(220, 20, 60, crimson_alpha))
        g1.setColorAt(0.55, QColor(120, 10, 45, crimson_alpha // 3))
        g1.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g1)

        g2 = QRadialGradient(w * 0.28, h * (0.82 + 0.03 * math.cos(self._phase * 0.5)), max(w, h) * 0.52)
        g2.setColorAt(0.0, QColor(124, 58, 237, violet_alpha))
        g2.setColorAt(0.6, QColor(76, 29, 149, violet_alpha // 3))
        g2.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g2)

        cx, cy = w * 0.74, h * 0.62
        radius = min(w, h) * 0.36
        circle_alpha = int((32 if self._active_mode else 16) + pulse1 * 14)

        p.save()
        p.translate(cx, cy)
        p.rotate(math.degrees(self._phase * 0.25))

        ring_col = QColor(255, 30, 66, circle_alpha) if self._active_mode else QColor(147, 51, 234, circle_alpha)
        gold_col = QColor(251, 191, 36, int(circle_alpha * 0.75))

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(ring_col, 1.4))
        p.drawEllipse(QPointF(0, 0), radius, radius)
        p.drawEllipse(QPointF(0, 0), radius * 0.84, radius * 0.84)

        for i in range(16):
            ang = math.radians(i * 22.5)
            p.drawLine(
                QPointF(math.cos(ang) * radius * 0.84, math.sin(ang) * radius * 0.84),
                QPointF(math.cos(ang) * radius, math.sin(ang) * radius),
            )

        p.rotate(math.degrees(-self._phase * 0.55))
        p.setPen(QPen(gold_col, 1.1))
        for offset_deg in (0.0, 60.0):
            tri = QPolygonF([
                QPointF(
                    math.cos(math.radians(offset_deg + k * 120.0)) * radius * 0.80,
                    math.sin(math.radians(offset_deg + k * 120.0)) * radius * 0.80,
                )
                for k in range(3)
            ])
            p.drawPolygon(tri)
        p.restore()

        for pt in self._particles:
            px, py = pt["x"] * w, pt["y"] * h
            twinkle = 0.45 + 0.55 * math.sin(self._phase * 2.2 + pt["offset"])
            alpha = int((140 if self._active_mode else 80) * twinkle)
            if pt["kind"] == "crimson":
                col = QColor(255, 42, 75, alpha)
            elif pt["kind"] == "gold":
                col = QColor(251, 191, 36, alpha)
            else:
                col = QColor(168, 85, 247, alpha)
            p.setBrush(col)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(px, py), pt["r"], pt["r"])

        p.end()


# threading.Thread + QObject сигналы (для Nuitka)
class SimpleWorker(QObject):
    finished_res = pyqtSignal(object)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.finished_res.emit((True, res))
        except Exception as e:
            self.finished_res.emit((False, str(e)))


class AutoTuneWorker(QObject):
    log_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._stop_requested = False
        self._thread: threading.Thread | None = None

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def request_stop(self):
        self._stop_requested = True

    def _run(self):
        results = []
        core.kill_winws()
        core.ensure_files_exist()

        engine_bin = core.get_engine_binary()
        engine_name = engine_bin.name
        if not engine_bin.exists():
            self.log_msg.emit(f"[ОШИБКА] {engine_name} не найден в {core.BIN_DIR}")
            self.finished_all.emit(results, True)
            return

        if core.IS_LINUX:
            fw_ok, fw_err = core.setup_linux_firewall("443,19294-19344,50000-50100")
            if not fw_ok:
                self.log_msg.emit(f"[ОШИБКА] {fw_err}")
                self.finished_all.emit(results, True)
                return

        test_cfg = {"fake_sni": "www.google.com", "udp_mode": "narrow"}
        total = len(core.STRATEGIES)

        for idx, item in enumerate(core.STRATEGIES, 1):
            if self._stop_requested:
                break

            strat = item["args"]
            self.step_started.emit(idx, total, item["name"])
            self.log_msg.emit(f"[Тюнер {idx}/{total}] Тестируем: {item['name']}...")

            cmd = core.get_winws_args(strat, test_cfg)
            popen_kw = (
                {"creationflags": core.CREATE_NO_WINDOW}
                if core.IS_WINDOWS
                else {"start_new_session": True}
            )
            proc = None
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    cwd=str(core.BIN_DIR),
                    **popen_kw,
                )
            except Exception as e:
                self.log_msg.emit(f"  [Ошибка запуска] {e}")
                results.append({"index": idx, "strategy": strat, "yt": False, "ds": False, "note": "Ошибка запуска"})
                self.step_result.emit(idx, False, False, "Ошибка запуска")
                continue

            aborted = False
            for _ in range(11):
                if self._stop_requested:
                    aborted = True
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.2)

            if aborted:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass
                core.kill_winws()
                break

            if proc.poll() is not None:
                err_txt = ""
                try:
                    if proc.stderr:
                        err_txt = proc.stderr.read().decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass
                note = "Упал"
                self.log_msg.emit(f"  [{engine_name} упал] {err_txt[:100] if err_txt else 'без текста ошибки'}")
                results.append({"index": idx, "strategy": strat, "yt": False, "ds": False, "note": note})
                self.step_result.emit(idx, False, False, note)
                core.cleanup_windivert()
                if core.IS_LINUX:
                    core.setup_linux_firewall("443,19294-19344,50000-50100")
                time.sleep(0.3)
                continue

            with ThreadPoolExecutor(max_workers=2) as pool:
                f_yt = pool.submit(core.check_url, "https://www.youtube.com", 4)
                f_ds = pool.submit(core.check_url, "https://discord.com/api/v10/gateway", 4)
                yt_ok, yt_code = f_yt.result()
                ds_ok, ds_code = f_ds.result()

            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
            core.kill_winws(timeout=1.5)
            if core.IS_LINUX and idx < total and not self._stop_requested:
                core.setup_linux_firewall("443,19294-19344,50000-50100")

            if yt_ok and ds_ok:
                note = "Отлично"
            elif yt_ok or ds_ok:
                note = "Частично"
            else:
                note = "Не пробило"

            self.log_msg.emit(
                f"  -> YouTube: {'OK' if yt_ok else 'FAIL'} ({yt_code}) | Discord: {'OK' if ds_ok else 'FAIL'} ({ds_code})"
            )
            results.append({"index": idx, "strategy": strat, "yt": yt_ok, "ds": ds_ok, "note": note})
            self.step_result.emit(idx, yt_ok, ds_ok, note)

        core.kill_winws(timeout=1.5)
        self.finished_all.emit(results, self._stop_requested)


APP_STYLESHEET = """
QMainWindow {
    background-color: #08060D;
    color: #F3EEFA;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #F3EEFA;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QFrame#Sidebar {
    background-color: rgba(13, 8, 20, 225);
    border-right: 1px solid #321636;
}

QLabel#BrandTitle {
    color: #FFF1F2;
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 1.5px;
}

QLabel#BrandSub {
    color: #F43F5E;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.1px;
}

QPushButton#NavBtn {
    background-color: transparent;
    color: #A79AB8;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#NavBtn:hover {
    background-color: rgba(255, 30, 66, 26);
    color: #FFE4E6;
    border: 1px solid rgba(255, 30, 66, 55);
}

QPushButton#NavBtn:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(220, 20, 60, 75), stop:1 rgba(124, 58, 237, 45));
    color: #FFFFFF;
    border: 1px solid #FF1E42;
    border-left: 4px solid #FBBF24;
}

QFrame#Card {
    background-color: rgba(18, 12, 27, 212);
    border: 1px solid #35193D;
    border-radius: 14px;
}

QFrame#StatusBannerActive {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(127, 17, 46, 220), stop:0.6 rgba(46, 16, 66, 215), stop:1 rgba(20, 12, 32, 215));
    border: 1.5px solid #FF1E42;
    border-radius: 14px;
}

QFrame#StatusBannerStopped {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(25, 14, 34, 215), stop:1 rgba(16, 11, 24, 215));
    border: 1px solid #3F2147;
    border-radius: 14px;
}

QFrame#MiniCard {
    background-color: rgba(24, 15, 36, 205);
    border: 1px solid #3A1D44;
    border-radius: 10px;
}

QLabel#PageTitle {
    color: #FFF5F7;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 0.3px;
}

QLabel#PageSub {
    color: #A79AB8;
    font-size: 12px;
}

QLabel#SectionTitle {
    color: #FDE68A;
    font-size: 14px;
    font-weight: 700;
}

QLabel#Muted {
    color: #A79AB8;
    font-size: 12px;
}

QPushButton#PrimaryStart {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #E11D48, stop:1 #9333EA);
    color: #FFFFFF;
    border: 1px solid #FB7185;
    border-radius: 10px;
    padding: 11px 22px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#PrimaryStart:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF1E42, stop:1 #A855F7);
    border-color: #FBBF24;
}
QPushButton#PrimaryStart:disabled {
    background-color: #2A162B;
    border-color: #3D203F;
    color: #7D6D8A;
}

QPushButton#DangerStop {
    background-color: #2B0D16;
    color: #FDA4AF;
    border: 1px solid #E11D48;
    border-radius: 10px;
    padding: 11px 22px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#DangerStop:hover {
    background-color: #9F1239;
    color: #FFFFFF;
    border-color: #FB7185;
}
QPushButton#DangerStop:disabled {
    background-color: #1E1019;
    border-color: #381A2A;
    color: #6E5668;
}

QPushButton#AccentBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #C026D3);
    color: #FFFFFF;
    border: 1px solid #A855F7;
    border-radius: 10px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#AccentBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #E11D48);
    border-color: #FBBF24;
}
QPushButton#AccentBtn:disabled {
    background-color: #261638;
    border-color: #3A2254;
    color: #7D6D8A;
}

QPushButton#SecondaryBtn {
    background-color: rgba(30, 19, 44, 220);
    color: #F3EEFA;
    border: 1px solid #4A2557;
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#SecondaryBtn:hover {
    background-color: rgba(58, 25, 68, 235);
    border-color: #FF1E42;
    color: #FFFFFF;
}
QPushButton#SecondaryBtn:disabled {
    color: #6B5B7B;
    border-color: #2B1734;
}

QComboBox, QLineEdit {
    background-color: rgba(12, 8, 19, 230);
    color: #F8F5FF;
    border: 1px solid #43204E;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}
QComboBox:focus, QLineEdit:focus {
    border-color: #FF1E42;
}
QComboBox::drop-down {
    border: none;
    width: 26px;
}
QComboBox QAbstractItemView {
    background-color: #130B1D;
    color: #F8F5FF;
    border: 1px solid #FF1E42;
    selection-background-color: #9F1239;
    padding: 4px;
}

QRadioButton, QCheckBox {
    color: #EFE8F8;
    spacing: 8px;
    font-size: 13px;
}
QRadioButton::indicator, QCheckBox::indicator {
    width: 16px;
    height: 16px;
}

QTableWidget {
    background-color: rgba(13, 8, 20, 220);
    alternate-background-color: rgba(22, 13, 33, 220);
    color: #F3EEFA;
    border: 1px solid #3A1C42;
    border-radius: 10px;
    gridline-color: #271330;
    selection-background-color: rgba(225, 29, 72, 110);
    selection-color: #FFFFFF;
}
QHeaderView::section {
    background-color: #190F26;
    color: #FDE68A;
    border: none;
    border-bottom: 1px solid #4A1E4E;
    padding: 8px 10px;
    font-weight: 700;
    font-size: 12px;
}

QProgressBar {
    background-color: #0D0814;
    border: 1px solid #3D1C44;
    border-radius: 7px;
    text-align: center;
    color: #FFFBEB;
    font-size: 11px;
    font-weight: 700;
    height: 18px;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF1E42, stop:0.55 #9333EA, stop:1 #FBBF24);
    border-radius: 6px;
}

QPlainTextEdit {
    background-color: rgba(10, 6, 15, 230);
    color: #E2D9F0;
    border: 1px solid #3A1C42;
    border-radius: 10px;
    padding: 10px;
    font-family: 'Consolas', 'Cascadia Mono', monospace;
    font-size: 12px;
}

QScrollBar:vertical {
    background: #0B0712;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #581C5E;
    min-height: 28px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #E11D48;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QMenu {
    background-color: #140B1F;
    color: #F3EEFA;
    border: 1px solid #FF1E42;
    padding: 4px;
}
QMenu::item:selected {
    background-color: #9F1239;
    color: #FFFFFF;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(950, 650)
        self.setMinimumSize(850, 570)

        self._active_workers: list[SimpleWorker] = []
        self._tune_worker: AutoTuneWorker | None = None
        self._is_running: bool = False
        self._tray_notified_once: bool = False
        self._force_quit: bool = False

        self.cursors = create_demon_cursors()
        self.icon_idle = create_demon_crest_icon(active=False, size=96)
        self.icon_active = create_demon_crest_icon(active=True, size=96)
        self.setWindowIcon(self.icon_idle)

        self._build_ui()
        self._apply_theme_cursors(self)
        self._setup_tray()
        self._setup_timers()

        core.ensure_files_exist()
        self.append_log(f"Unfit Zapret v{core.APP_VERSION} запущен. Рабочая папка: {core.WORK_DIR}")
        self.refresh_all_state()
        self._auto_repair_autorun_if_needed()
        self._start_startup_network_tasks()

    def showEvent(self, event):
        super().showEvent(event)
        self.root_canvas.set_paused(False)

    def hideEvent(self, event):
        self.root_canvas.set_paused(True)
        super().hideEvent(event)

    def _apply_theme_cursors(self, widget: QWidget):
        self.setCursor(self.cursors["arrow"])
        for btn in widget.findChildren(QPushButton):
            btn.setCursor(self.cursors["pointer"])
        for rb in widget.findChildren(QRadioButton):
            rb.setCursor(self.cursors["pointer"])
        for cb in widget.findChildren(QCheckBox):
            cb.setCursor(self.cursors["pointer"])
        for cmb in widget.findChildren(QComboBox):
            cmb.setCursor(self.cursors["pointer"])
            if cmb.view():
                cmb.view().setCursor(self.cursors["pointer"])
        for le in widget.findChildren(QLineEdit):
            le.setCursor(self.cursors["ibeam"])
        for te in widget.findChildren(QPlainTextEdit):
            te.viewport().setCursor(self.cursors["ibeam"])
        for tbl in widget.findChildren(QTableWidget):
            tbl.viewport().setCursor(self.cursors["pointer"])

    def _build_ui(self):
        self.root_canvas = DemonAuraWidget()
        self.setCentralWidget(self.root_canvas)
        main_layout = QHBoxLayout(self.root_canvas)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame(objectName="Sidebar")
        sidebar.setFixedWidth(232)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(14, 18, 14, 16)
        sb_layout.setSpacing(6)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        self.brand_icon_lbl = QLabel()
        self.brand_icon_lbl.setPixmap(self.icon_idle.pixmap(42, 42))
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_text.addWidget(QLabel("UNFIT ZAPRET", objectName="BrandTitle"))
        brand_text.addWidget(QLabel(f"DEMON LORD • v{core.APP_VERSION}", objectName="BrandSub"))
        brand_row.addWidget(self.brand_icon_lbl)
        brand_row.addLayout(brand_text)
        brand_row.addStretch()
        sb_layout.addLayout(brand_row)
        sb_layout.addSpacing(16)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        nav_items = [
            ("  Главная", 0),
            ("  Авто-Тюнинг", 1),
            ("  Настройки", 2),
            ("  Исключения", 3),
            ("  Логи и файлы", 4),
            ("  Об авторе", 5),
        ]
        self.nav_buttons: list[QPushButton] = []
        for label, idx in nav_items:
            btn = QPushButton(label, objectName="NavBtn")
            btn.setCheckable(True)
            if idx == 0:
                btn.setChecked(True)
            self.nav_group.addButton(btn, idx)
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.nav_group.idClicked.connect(self._switch_page)
        sb_layout.addWidget(btn_spacer := QWidget())
        btn_spacer.hide()
        sb_layout.addStretch()

        self.btn_sb_update = QPushButton("Обновление!", objectName="PrimaryStart")
        self.btn_sb_update.setVisible(False)
        self.btn_sb_update.clicked.connect(self._on_open_update_release)
        sb_layout.addWidget(self.btn_sb_update)

        sb_status_card = QFrame(objectName="MiniCard")
        sb_st_lay = QVBoxLayout(sb_status_card)
        sb_st_lay.setContentsMargins(12, 10, 12, 10)
        sb_st_lay.setSpacing(6)

        self.sb_status_lbl = QLabel("● Печать снята")
        self.sb_status_lbl.setStyleSheet("color: #FB7185; font-weight: 700; font-size: 12px;")
        self.sb_autorun_lbl = QLabel("Автостарт: -")
        self.sb_autorun_lbl.setStyleSheet("color: #A79AB8; font-size: 11px;")
        self.sb_strat_lbl = QLabel("Стратегия: -")
        self.sb_strat_lbl.setStyleSheet("color: #A79AB8; font-size: 11px;")

        sb_st_lay.addWidget(self.sb_status_lbl)
        sb_st_lay.addWidget(self.sb_autorun_lbl)
        sb_st_lay.addWidget(self.sb_strat_lbl)
        sb_layout.addWidget(sb_status_card)

        main_layout.addWidget(sidebar)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_dashboard_page())
        self.pages.addWidget(self._build_autotune_page())
        self.pages.addWidget(self._build_settings_page())
        self.pages.addWidget(self._build_exclusions_page())
        self.pages.addWidget(self._build_logs_page())
        self.pages.addWidget(self._build_about_page())
        main_layout.addWidget(self.pages, 1)

    def _switch_page(self, idx: int):
        self.pages.setCurrentIndex(idx)
        if idx == 2:
            self._load_settings_into_ui()
        elif idx == 3:
            self._load_exclusion_editor()
        elif idx == 4:
            self._refresh_diagnostics()

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(2)
        header.addWidget(QLabel("Цитадель обхода - Unfit Edition", objectName="PageTitle"))
        header.addWidget(QLabel(f"Папка: {core.WORK_DIR}  •  Платформа: {core.get_platform_label()}", objectName="PageSub"))
        lay.addLayout(header)

        self.status_banner = QFrame(objectName="StatusBannerStopped")
        banner_lay = QHBoxLayout(self.status_banner)
        banner_lay.setContentsMargins(20, 18, 20, 18)
        banner_lay.setSpacing(14)

        left_info = QVBoxLayout()
        left_info.setSpacing(4)
        self.dash_status_title = QLabel("ОБХОД ОСТАНОВЛЕН")
        self.dash_status_title.setStyleSheet("color: #FB7185; font-size: 17px; font-weight: 800;")
        self.dash_status_desc = QLabel("Нажмите «Активировать обход», чтобы пробудить DPI-защиту.")
        self.dash_status_desc.setStyleSheet("color: #E2D9F0; font-size: 12px;")
        self.dash_status_desc.setWordWrap(True)
        left_info.addWidget(self.dash_status_title)
        left_info.addWidget(self.dash_status_desc)
        banner_lay.addLayout(left_info, 1)

        btn_col = QHBoxLayout()
        btn_col.setSpacing(10)
        self.btn_toggle_bypass = QPushButton("Активировать обход", objectName="PrimaryStart")
        self.btn_toggle_bypass.clicked.connect(self._on_toggle_bypass)

        self.btn_restart_bypass = QPushButton("Перезапустить", objectName="SecondaryBtn")
        self.btn_restart_bypass.clicked.connect(self._on_restart_bypass)

        btn_col.addWidget(self.btn_toggle_bypass)
        btn_col.addWidget(self.btn_restart_bypass)
        banner_lay.addLayout(btn_col)
        lay.addWidget(self.status_banner)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(14)

        cfg_card = QFrame(objectName="Card")
        cfg_lay = QVBoxLayout(cfg_card)
        cfg_lay.setContentsMargins(18, 16, 18, 16)
        cfg_lay.setSpacing(8)
        cfg_lay.addWidget(QLabel("Магический профиль", objectName="SectionTitle"))
        self.dash_cfg_strat = QLabel("Стратегия: -")
        self.dash_cfg_udp = QLabel("Режим UDP: -")
        self.dash_cfg_sni = QLabel("Fake SNI: -")
        for lbl in (self.dash_cfg_strat, self.dash_cfg_udp, self.dash_cfg_sni):
            lbl.setStyleSheet("color: #E2D9F0; font-size: 12px;")
            lbl.setWordWrap(True)
            cfg_lay.addWidget(lbl)
        cfg_lay.addStretch()
        btn_go_settings = QPushButton("Изменить параметры", objectName="SecondaryBtn")
        btn_go_settings.clicked.connect(lambda: self._select_nav(2))
        cfg_lay.addWidget(btn_go_settings)
        mid_row.addWidget(cfg_card, 1)

        auto_card = QFrame(objectName="Card")
        auto_lay = QVBoxLayout(auto_card)
        auto_lay.setContentsMargins(18, 16, 18, 16)
        auto_lay.setSpacing(8)
        auto_lay.addWidget(QLabel("Автозапуск с Windows" if core.IS_WINDOWS else "Автозапуск (systemd)", objectName="SectionTitle"))
        self.dash_autorun_status = QLabel("Проверка...")
        self.dash_autorun_status.setStyleSheet("font-size: 13px; font-weight: 700;")
        self.dash_autorun_hint = QLabel(
            "Запускает обход автоматически при включении и входе в систему (включая Fast Startup), от имени SYSTEM без окон UAC."
            if core.IS_WINDOWS
            else "Регистрирует systemd-сервис unfit-zapret.service для автоматического запуска при старте Linux."
        )
        self.dash_autorun_hint.setStyleSheet("color: #A79AB8; font-size: 11px;")
        self.dash_autorun_hint.setWordWrap(True)
        auto_lay.addWidget(self.dash_autorun_status)
        auto_lay.addWidget(self.dash_autorun_hint)
        auto_lay.addStretch()

        auto_btns = QHBoxLayout()
        auto_btns.setSpacing(8)
        self.btn_toggle_autorun = QPushButton("Включить автозапуск", objectName="AccentBtn")
        self.btn_toggle_autorun.clicked.connect(self._on_toggle_autorun)
        auto_btns.addWidget(self.btn_toggle_autorun)
        auto_lay.addLayout(auto_btns)
        mid_row.addWidget(auto_card, 1)

        lay.addLayout(mid_row)

        test_card = QFrame(objectName="Card")
        test_lay = QVBoxLayout(test_card)
        test_lay.setContentsMargins(18, 16, 18, 16)
        test_lay.setSpacing(12)

        test_top = QHBoxLayout()
        test_title_col = QVBoxLayout()
        test_title_col.setSpacing(2)
        test_title_col.addWidget(QLabel("Проверка доступности сайтов", objectName="SectionTitle"))
        self.test_summary_lbl = QLabel("Параллельная проверка Discord, YouTube, Telegram и X за ~4 сек")
        self.test_summary_lbl.setObjectName("Muted")
        test_title_col.addWidget(self.test_summary_lbl)
        test_top.addLayout(test_title_col, 1)

        self.btn_run_tests = QPushButton("Проверить сайты", objectName="AccentBtn")
        self.btn_run_tests.clicked.connect(self._on_run_site_tests)
        test_top.addWidget(self.btn_run_tests)
        test_lay.addLayout(test_top)

        sites_grid = QGridLayout()
        sites_grid.setSpacing(10)
        self.site_badges: dict[str, tuple[QLabel, QLabel]] = {}
        for col_idx, (key, title, _) in enumerate(core.TEST_TARGETS):
            mc = QFrame(objectName="MiniCard")
            mc_lay = QVBoxLayout(mc)
            mc_lay.setContentsMargins(12, 10, 12, 10)
            mc_lay.setSpacing(4)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("color: #FFF5F7; font-weight: 700; font-size: 13px;")
            s_lbl = QLabel("Ожидание")
            s_lbl.setStyleSheet("color: #8E7DA3; font-size: 12px; font-weight: 600;")
            mc_lay.addWidget(t_lbl)
            mc_lay.addWidget(s_lbl)
            sites_grid.addWidget(mc, 0, col_idx)
            self.site_badges[key] = (t_lbl, s_lbl)

        test_lay.addLayout(sites_grid)
        lay.addWidget(test_card)
        lay.addStretch()
        return page

    def _build_autotune_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)

        header = QHBoxLayout()
        h_text = QVBoxLayout()
        h_text.setSpacing(2)
        h_text.addWidget(QLabel("Авто-Тюнинг стратегий", objectName="PageTitle"))
        h_text.addWidget(
            QLabel("Автоматический перебор всех 11 стратегий для поиска лучшего обхода у вашего провайдера", objectName="PageSub")
        )
        header.addLayout(h_text, 1)

        self.btn_tune_start = QPushButton("Начать подбор", objectName="AccentBtn")
        self.btn_tune_start.clicked.connect(self._on_start_autotune)

        self.btn_tune_stop = QPushButton("Стоп", objectName="DangerStop")
        self.btn_tune_stop.setEnabled(False)
        self.btn_tune_stop.clicked.connect(self._on_stop_autotune)

        header.addWidget(self.btn_tune_start)
        header.addWidget(self.btn_tune_stop)
        lay.addLayout(header)

        prog_card = QFrame(objectName="Card")
        prog_lay = QVBoxLayout(prog_card)
        prog_lay.setContentsMargins(16, 12, 16, 12)
        prog_lay.setSpacing(8)
        self.tune_status_lbl = QLabel("Нажмите «Начать подбор», чтобы проверить все стратегии.")
        self.tune_status_lbl.setStyleSheet("color: #E2D9F0; font-size: 12px;")
        self.tune_progress = QProgressBar()
        self.tune_progress.setRange(0, len(core.STRATEGIES))
        self.tune_progress.setValue(0)
        prog_lay.addWidget(self.tune_status_lbl)
        prog_lay.addWidget(self.tune_progress)
        lay.addWidget(prog_card)

        self.tune_table = QTableWidget(len(core.STRATEGIES), 5)
        self.tune_table.setHorizontalHeaderLabels(["#", "Стратегия", "YouTube", "Discord", "Результат"])
        self.tune_table.setAlternatingRowColors(True)
        self.tune_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tune_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tune_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tune_table.verticalHeader().setVisible(False)
        hdr = self.tune_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        for i, item in enumerate(core.STRATEGIES):
            num_item = QTableWidgetItem(f"#{i + 1}")
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tune_table.setItem(i, 0, num_item)
            self.tune_table.setItem(i, 1, QTableWidgetItem(f"{item['name']} - {item['desc']}"))
            for col in (2, 3, 4):
                cell = QTableWidgetItem("-")
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tune_table.setItem(i, col, cell)

        self.tune_table.itemDoubleClicked.connect(lambda _: self._on_apply_selected_tune())
        lay.addWidget(self.tune_table, 1)

        bottom_row = QHBoxLayout()
        hint = QLabel("Подсказка: выберите любую строку и нажмите «Применить выбранную» (или двойной клик).")
        hint.setObjectName("Muted")
        bottom_row.addWidget(hint, 1)
        self.btn_tune_apply = QPushButton("Применить выбранную и запустить", objectName="PrimaryStart")
        self.btn_tune_apply.clicked.connect(self._on_apply_selected_tune)
        bottom_row.addWidget(self.btn_tune_apply)
        lay.addLayout(bottom_row)

        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)

        lay.addWidget(QLabel("Настройка параметров", objectName="PageTitle"))
        lay.addWidget(QLabel("Выберите стратегию DPI-обхода, порты UDP и маскировку TLS SNI", objectName="PageSub"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_lay = QVBoxLayout(scroll_content)
        scroll_lay.setContentsMargins(0, 0, 6, 0)
        scroll_lay.setSpacing(14)

        s_card = QFrame(objectName="Card")
        s_lay = QVBoxLayout(s_card)
        s_lay.setContentsMargins(18, 16, 18, 16)
        s_lay.setSpacing(10)
        s_lay.addWidget(QLabel("1. Стратегия обхода DPI", objectName="SectionTitle"))
        self.combo_strategy = QComboBox()
        for i, item in enumerate(core.STRATEGIES, 1):
            self.combo_strategy.addItem(f"#{i}  {item['name']} - {item['desc']}", i)
        s_lay.addWidget(self.combo_strategy)
        scroll_lay.addWidget(s_card)

        u_card = QFrame(objectName="Card")
        u_lay = QVBoxLayout(u_card)
        u_lay.setContentsMargins(18, 16, 18, 16)
        u_lay.setSpacing(8)
        u_lay.addWidget(QLabel("2. Диапазон UDP портов (Discord Voice)", objectName="SectionTitle"))
        self.udp_group = QButtonGroup(self)
        self.rb_udp_narrow = QRadioButton("NARROW (50000–50100) - рекомендуется: низкий пинг в играх и совместимость с VPN")
        self.rb_udp_wide = QRadioButton("WIDE (50000–65535) - полный диапазон, если голос в Discord не подключается")
        self.rb_udp_disabled = QRadioButton("DISABLED - отключить UDP-обход голоса")
        for rb in (self.rb_udp_narrow, self.rb_udp_wide, self.rb_udp_disabled):
            self.udp_group.addButton(rb)
            u_lay.addWidget(rb)
        scroll_lay.addWidget(u_card)

        sni_card = QFrame(objectName="Card")
        sni_lay = QVBoxLayout(sni_card)
        sni_lay.setContentsMargins(18, 16, 18, 16)
        sni_lay.setSpacing(10)
        sni_lay.addWidget(QLabel("3. Fake TLS SNI (цифровой отпечаток)", objectName="SectionTitle"))
        sni_row = QHBoxLayout()
        sni_row.setSpacing(10)
        self.combo_sni = QComboBox()
        for sni in core.POPULAR_SNIS:
            label = "random (случайный при каждом запуске)" if sni == "random" else sni
            self.combo_sni.addItem(label, sni)
        self.combo_sni.addItem("Свой домен вручную...", "__custom__")
        self.combo_sni.currentIndexChanged.connect(self._on_sni_combo_changed)
        self.edit_custom_sni = QLineEdit()
        self.edit_custom_sni.setPlaceholderText("Например: example.com")
        self.edit_custom_sni.setVisible(False)
        sni_row.addWidget(self.combo_sni, 1)
        sni_row.addWidget(self.edit_custom_sni, 1)
        sni_lay.addLayout(sni_row)
        scroll_lay.addWidget(sni_card)

        ui_card = QFrame(objectName="Card")
        ui_lay = QVBoxLayout(ui_card)
        ui_lay.setContentsMargins(18, 16, 18, 16)
        ui_lay.setSpacing(8)
        ui_lay.addWidget(QLabel("4. Поведение окна", objectName="SectionTitle"))
        self.chk_minimize_tray = QCheckBox("Сворачивать в системный трей при нажатии на крестик (обход продолжит работать)")
        ui_lay.addWidget(self.chk_minimize_tray)
        scroll_lay.addWidget(ui_card)

        scroll_lay.addStretch()
        scroll.setWidget(scroll_content)
        lay.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_save_settings = QPushButton("Сохранить и применить", objectName="PrimaryStart")
        self.btn_save_settings.clicked.connect(self._on_save_settings)
        btn_row.addWidget(self.btn_save_settings)
        lay.addLayout(btn_row)

        return page

    def _build_exclusions_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)

        lay.addWidget(QLabel("Исключения VPN, игр и доменов", objectName="PageTitle"))
        lay.addWidget(
            QLabel("Автоматический поиск IP запущенных VPN/игр и быстрое редактирование пользовательских списков", objectName="PageSub")
        )

        scan_card = QFrame(objectName="Card")
        scan_lay = QHBoxLayout(scan_card)
        scan_lay.setContentsMargins(18, 14, 18, 14)
        scan_lay.setSpacing(12)
        sc_text = QVBoxLayout()
        sc_text.setSpacing(2)
        sc_text.addWidget(QLabel("Сканер активных подключений", objectName="SectionTitle"))
        self.scan_result_lbl = QLabel("Запустите VPN или игру и нажмите «Сканировать», чтобы добавить их IP в исключения.")
        self.scan_result_lbl.setObjectName("Muted")
        self.scan_result_lbl.setWordWrap(True)
        sc_text.addWidget(self.scan_result_lbl)
        scan_lay.addLayout(sc_text, 1)

        self.btn_scan_vpn = QPushButton("Сканировать VPN и игры", objectName="AccentBtn")
        self.btn_scan_vpn.clicked.connect(self._on_scan_exclusions)
        scan_lay.addWidget(self.btn_scan_vpn)
        lay.addWidget(scan_card)

        ed_card = QFrame(objectName="Card")
        ed_lay = QVBoxLayout(ed_card)
        ed_lay.setContentsMargins(18, 14, 18, 14)
        ed_lay.setSpacing(10)

        top_ed = QHBoxLayout()
        top_ed.addWidget(QLabel("Редактор списка:", objectName="SectionTitle"))
        self.combo_list_file = QComboBox()
        self.combo_list_file.addItem("ipset-exclude-user.txt (Исключённые IP)", "ipset-exclude-user.txt")
        self.combo_list_file.addItem("list-exclude-user.txt (Исключённые домены)", "list-exclude-user.txt")
        self.combo_list_file.addItem("list-general-user.txt (Дополнительные домены для обхода)", "list-general-user.txt")
        self.combo_list_file.currentIndexChanged.connect(self._load_exclusion_editor)
        top_ed.addWidget(self.combo_list_file, 1)

        btn_reload_list = QPushButton("Обновить", objectName="SecondaryBtn")
        btn_reload_list.clicked.connect(self._load_exclusion_editor)
        top_ed.addWidget(btn_reload_list)
        ed_lay.addLayout(top_ed)

        self.list_editor = QPlainTextEdit()
        ed_lay.addWidget(self.list_editor, 1)

        bot_ed = QHBoxLayout()
        bot_ed.addStretch()
        btn_save_list = QPushButton("Сохранить список", objectName="PrimaryStart")
        btn_save_list.clicked.connect(self._on_save_list_file)
        bot_ed.addWidget(btn_save_list)
        ed_lay.addLayout(bot_ed)

        lay.addWidget(ed_card, 1)
        return page

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)

        top = QHBoxLayout()
        t_col = QVBoxLayout()
        t_col.setSpacing(2)
        t_col.addWidget(QLabel("Журнал и диагностика", objectName="PageTitle"))
        t_col.addWidget(QLabel("Состояние компонентов bin/ и логи автозапуска", objectName="PageSub"))
        top.addLayout(t_col, 1)

        btn_open_dir = QPushButton("Открыть папку", objectName="SecondaryBtn")
        btn_open_dir.clicked.connect(self._on_open_work_dir)
        btn_clear_log = QPushButton("Очистить журнал", objectName="SecondaryBtn")
        btn_clear_log.clicked.connect(lambda: self.log_view.clear())
        top.addWidget(btn_open_dir)
        top.addWidget(btn_clear_log)
        lay.addLayout(top)

        diag_card = QFrame(objectName="Card")
        diag_lay = QVBoxLayout(diag_card)
        diag_lay.setContentsMargins(16, 12, 16, 12)
        diag_lay.setSpacing(6)
        self.diag_label = QLabel("Проверка файлов...")
        self.diag_label.setStyleSheet("color: #E2D9F0; font-size: 12px;")
        self.diag_label.setWordWrap(True)
        diag_lay.addWidget(self.diag_label)
        lay.addWidget(diag_card)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        lay.addWidget(self.log_view, 1)
        return page

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)

        lay.addWidget(QLabel("Об авторе и проекте", objectName="PageTitle"))
        lay.addWidget(QLabel("Полезные ссылки, обновления и резервный VPN-сервис", objectName="PageSub"))

        dev_card = QFrame(objectName="Card")
        dev_lay = QVBoxLayout(dev_card)
        dev_lay.setContentsMargins(18, 16, 18, 16)
        dev_lay.setSpacing(14)

        dev_head = QHBoxLayout()
        dev_head.setSpacing(14)
        self.author_avatar_lbl = QLabel()
        self.author_avatar_lbl.setFixedSize(54, 54)
        self.author_avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.author_avatar_lbl.setPixmap(self.icon_active.pixmap(52, 52))
        dev_head.addWidget(self.author_avatar_lbl)

        dev_info = QVBoxLayout()
        dev_info.setSpacing(2)
        dev_name = QLabel(f"Mist-582  •  Unfit Zapret v{core.APP_VERSION}")
        dev_name.setStyleSheet("color: #FFF5F7; font-size: 16px; font-weight: 800;")
        dev_desc = QLabel("Разработка и поддержка Unfit Zapret. Обновления, новости и помощь - в наших каналах.")
        dev_desc.setObjectName("Muted")
        dev_desc.setWordWrap(True)
        dev_info.addWidget(dev_name)
        dev_info.addWidget(dev_desc)
        dev_head.addLayout(dev_info, 1)
        dev_lay.addLayout(dev_head)

        upd_row = QHBoxLayout()
        upd_row.setSpacing(10)
        self.lbl_update_status = QLabel(f"Текущая версия: v{core.APP_VERSION}")
        self.lbl_update_status.setObjectName("Muted")
        self.btn_check_update = QPushButton("Проверить обновления", objectName="SecondaryBtn")
        self.btn_check_update.clicked.connect(lambda: self._on_check_updates(silent=False))
        self.btn_open_release = QPushButton("Обновить на GitHub", objectName="PrimaryStart")
        self.btn_open_release.setVisible(False)
        self.btn_open_release.clicked.connect(self._on_open_update_release)
        upd_row.addWidget(self.lbl_update_status, 1)
        upd_row.addWidget(self.btn_open_release)
        upd_row.addWidget(self.btn_check_update)
        dev_lay.addLayout(upd_row)

        links_grid = QGridLayout()
        links_grid.setSpacing(10)
        links = [
            ("GitHub • Mist-582", "https://github.com/Mist-582", "SecondaryBtn"),
            ("Telegram канал • @UnfitShop", "https://t.me/UnfitShop", "SecondaryBtn"),
            ("Discord сервер • Сообщество", "https://discord.gg/8RwY28XkY3", "SecondaryBtn"),
            ("Связаться в Telegram • @mist_582", "https://t.me/mist_582", "SecondaryBtn"),
        ]
        for idx, (text, url, obj_name) in enumerate(links):
            btn = QPushButton(text, objectName=obj_name)
            btn.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))
            links_grid.addWidget(btn, idx // 2, idx % 2)
        dev_lay.addLayout(links_grid)
        lay.addWidget(dev_card)

        vpn_card = QFrame(objectName="Card")
        vpn_lay = QVBoxLayout(vpn_card)
        vpn_lay.setContentsMargins(18, 16, 18, 16)
        vpn_lay.setSpacing(12)

        vpn_top = QHBoxLayout()
        vpn_title = QLabel("Unfit VPN  •  Протокол VLESS")
        vpn_title.setStyleSheet("color: #FDE68A; font-size: 15px; font-weight: 800;")
        vpn_badge = QLabel("Резервный обход")
        vpn_badge.setStyleSheet(
            "background-color: rgba(225, 29, 72, 65); color: #FFE4E6; "
            "border: 1px solid #FF1E42; border-radius: 6px; padding: 3px 9px; font-size: 11px; font-weight: 700;"
        )
        vpn_top.addWidget(vpn_title)
        vpn_top.addStretch()
        vpn_top.addWidget(vpn_badge)
        vpn_lay.addLayout(vpn_top)

        vpn_sub = QLabel(
            "Если провайдер включает жёсткие белые списки или нужна защита на телефоне - "
            "попробуйте Unfit VPN на базе VLESS без падения скорости."
        )
        vpn_sub.setObjectName("Muted")
        vpn_sub.setWordWrap(True)
        vpn_lay.addWidget(vpn_sub)

        tiers_row = QHBoxLayout()
        tiers_row.setSpacing(12)

        free_box = QFrame(objectName="MiniCard")
        free_lay = QVBoxLayout(free_box)
        free_lay.setContentsMargins(14, 12, 14, 12)
        free_lay.setSpacing(6)
        free_hdr = QLabel("Бесплатно навсегда")
        free_hdr.setStyleSheet("color: #34D399; font-size: 13px; font-weight: 700;")
        free_items = QLabel("• Личный ключ VLESS\n• Безлимитный трафик\n• Стабильная скорость")
        free_items.setStyleSheet("color: #E2D9F0; font-size: 12px; line-height: 1.4;")
        free_lay.addWidget(free_hdr)
        free_lay.addWidget(free_items)
        free_lay.addStretch()
        tiers_row.addWidget(free_box, 1)

        prem_box = QFrame(objectName="MiniCard")
        prem_lay = QVBoxLayout(prem_box)
        prem_lay.setContentsMargins(14, 12, 14, 12)
        prem_lay.setSpacing(6)
        prem_hdr = QLabel("Premium - 100 ₽/мес · 800 ₽/год")
        prem_hdr.setStyleSheet("color: #FBBF24; font-size: 13px; font-weight: 700;")
        prem_items = QLabel("• Полный обход белых списков\n• 30+ серверов в разных странах\n• Турбо-скорость для 4K и игр")
        prem_items.setStyleSheet("color: #E2D9F0; font-size: 12px; line-height: 1.4;")
        prem_lay.addWidget(prem_hdr)
        prem_lay.addWidget(prem_items)
        prem_lay.addStretch()
        tiers_row.addWidget(prem_box, 1)

        vpn_lay.addLayout(tiers_row)

        vpn_btns = QHBoxLayout()
        vpn_btns.setSpacing(10)
        btn_vpn_bot = QPushButton("Забрать ключ в @UnfitShopVPN_BOT", objectName="PrimaryStart")
        btn_vpn_bot.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/UnfitShopVPN_BOT")))
        btn_vpn_chan = QPushButton("Канал Unfit VPN", objectName="AccentBtn")
        btn_vpn_chan.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/unfitvpn")))
        vpn_btns.addWidget(btn_vpn_bot, 1)
        vpn_btns.addWidget(btn_vpn_chan)
        vpn_lay.addLayout(vpn_btns)

        lay.addWidget(vpn_card)
        lay.addStretch()
        return page

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self.icon_idle, self)
        self.tray_icon.setToolTip(APP_TITLE)
        self.tray_icon.activated.connect(self._on_tray_activated)

        menu = QMenu()
        act_show = menu.addAction("Открыть окно")
        act_show.triggered.connect(self.show_and_focus)
        menu.addSeparator()
        self.tray_act_toggle = menu.addAction("Активировать обход")
        self.tray_act_toggle.triggered.connect(self._on_toggle_bypass)
        act_restart = menu.addAction("Перезапустить обход")
        act_restart.triggered.connect(self._on_restart_bypass)
        menu.addSeparator()
        act_exit_only = menu.addAction("Выйти (оставить обход работать)")
        act_exit_only.triggered.connect(self._quit_app_keep_bypass)
        act_stop_exit = menu.addAction("Остановить обход и выйти")
        act_stop_exit.triggered.connect(self._quit_app_stop_bypass)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _setup_timers(self):
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._poll_winws_status)
        self.status_timer.start(2000)

    def _select_nav(self, idx: int):
        self.nav_buttons[idx].setChecked(True)
        self._switch_page(idx)

    def append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{ts}] {msg}")

    def _poll_winws_status(self):
        running = core.is_winws_running()
        if running != self._is_running:
            self._is_running = running
            self._apply_running_visuals(running)

    def _apply_running_visuals(self, running: bool):
        icon = self.icon_active if running else self.icon_idle
        self.setWindowIcon(icon)
        self.tray_icon.setIcon(icon)
        self.brand_icon_lbl.setPixmap(icon.pixmap(42, 42))
        self.root_canvas.set_active_mode(running)

        if running:
            self.status_banner.setObjectName("StatusBannerActive")
            self.dash_status_title.setText("СИЛА АКТИВНА • ОБХОД ВКЛЮЧЁН")
            self.dash_status_title.setStyleSheet("color: #FDE68A; font-size: 17px; font-weight: 800;")
            pids = core.get_winws_pids()
            pid_str = f" (PID: {', '.join(map(str, pids))})" if pids else ""
            self.dash_status_desc.setText(f"Процесс {core.get_engine_name()} защищает трафик в фоне{pid_str}.")
            self.btn_toggle_bypass.setText("Остановить обход")
            self.btn_toggle_bypass.setObjectName("DangerStop")
            self.sb_status_lbl.setText("● Активен")
            self.sb_status_lbl.setStyleSheet("color: #FBBF24; font-weight: 700; font-size: 12px;")
            self.tray_act_toggle.setText("Остановить обход")
            self.tray_icon.setToolTip(f"{APP_TITLE}\nСтатус: Активен")
        else:
            self.status_banner.setObjectName("StatusBannerStopped")
            self.dash_status_title.setText("ОБХОД ОСТАНОВЛЕН")
            self.dash_status_title.setStyleSheet("color: #FB7185; font-size: 17px; font-weight: 800;")
            self.dash_status_desc.setText("Нажмите «Активировать обход», чтобы пробудить DPI-защиту.")
            self.btn_toggle_bypass.setText("Активировать обход")
            self.btn_toggle_bypass.setObjectName("PrimaryStart")
            self.sb_status_lbl.setText("● Остановлен")
            self.sb_status_lbl.setStyleSheet("color: #FB7185; font-weight: 700; font-size: 12px;")
            self.tray_act_toggle.setText("Активировать обход")
            self.tray_icon.setToolTip(f"{APP_TITLE}\nСтатус: Остановлен")

        for w in (self.status_banner, self.btn_toggle_bypass):
            w.style().unpolish(w)
            w.style().polish(w)

    def refresh_all_state(self):
        self._is_running = core.is_winws_running()
        self._apply_running_visuals(self._is_running)

        cfg = core.load_config()
        idx = cfg.get("index", 0)
        strat_str = cfg.get("strategy", "")
        strat_label = f"#{idx}" if idx else "Кастомная"
        if 1 <= idx <= len(core.STRATEGIES) and core.STRATEGIES[idx - 1]["args"] == strat_str:
            strat_label = f"#{idx} ({core.STRATEGIES[idx - 1]['name']})"

        self.dash_cfg_strat.setText(f"Стратегия: {strat_label}")
        self.dash_cfg_udp.setText(f"Режим UDP: {cfg.get('udp_mode', 'narrow').upper()}")
        self.dash_cfg_sni.setText(f"Fake SNI: {cfg.get('fake_sni', 'www.google.com')}")
        self.sb_strat_lbl.setText(f"Стратегия: #{idx if idx else '?'}")

        info = core.get_autorun_info()
        if info["enabled"]:
            if info["path_matches"]:
                self.dash_autorun_status.setText("ВКЛЮЧЁН (Boot + Logon)" if core.IS_WINDOWS else "ВКЛЮЧЁН (systemd)")
                self.dash_autorun_status.setStyleSheet("color: #FBBF24; font-size: 13px; font-weight: 700;")
                self.sb_autorun_lbl.setText("Автостарт: ВКЛ")
                self.sb_autorun_lbl.setStyleSheet("color: #FBBF24; font-size: 11px;")
            else:
                self.dash_autorun_status.setText("ВКЛЮЧЁН (требуется обновление пути)")
                self.dash_autorun_status.setStyleSheet("color: #FB923C; font-size: 13px; font-weight: 700;")
                self.sb_autorun_lbl.setText("Автостарт: УСТАРЕЛ")
                self.sb_autorun_lbl.setStyleSheet("color: #FB923C; font-size: 11px;")
            self.btn_toggle_autorun.setText("Отключить автозапуск")
            self.btn_toggle_autorun.setObjectName("SecondaryBtn")
        else:
            self.dash_autorun_status.setText("ОТКЛЮЧЁН")
            self.dash_autorun_status.setStyleSheet("color: #A79AB8; font-size: 13px; font-weight: 700;")
            self.sb_autorun_lbl.setText("Автостарт: ВЫКЛ")
            self.sb_autorun_lbl.setStyleSheet("color: #A79AB8; font-size: 11px;")
            self.btn_toggle_autorun.setText("Включить автозапуск")
            self.btn_toggle_autorun.setObjectName("AccentBtn")

        self.btn_toggle_autorun.style().unpolish(self.btn_toggle_autorun)
        self.btn_toggle_autorun.style().polish(self.btn_toggle_autorun)

    def _start_startup_network_tasks(self):
        self._latest_release_url = f"https://github.com/{core.GITHUB_OWNER}/{core.GITHUB_REPO}/releases"
        self._latest_asset_url = ""
        self._run_bg(core.fetch_github_avatar, self._on_avatar_loaded)
        self._on_check_updates(silent=True)

    def _on_avatar_loaded(self, res):
        ok_call, raw = res
        if ok_call and isinstance(raw, (bytes, bytearray)):
            pm = make_round_avatar(bytes(raw), size=52)
            if pm is not None:
                self.author_avatar_lbl.setPixmap(pm)

    def _on_check_updates(self, silent: bool = False):
        if hasattr(self, "btn_check_update"):
            self.btn_check_update.setEnabled(False)
        if not silent and hasattr(self, "lbl_update_status"):
            self.lbl_update_status.setText("Проверка обновлений на GitHub...")
        self._run_bg(core.check_github_update, lambda r: self._after_check_updates(r, silent))

    def _after_check_updates(self, res, silent: bool):
        if hasattr(self, "btn_check_update"):
            self.btn_check_update.setEnabled(True)
        ok_call, info = res
        if not ok_call or not isinstance(info, dict):
            if not silent:
                self.lbl_update_status.setText("Не удалось проверить обновления.")
            return

        if info.get("has_update"):
            latest = info["latest"]
            self._latest_release_url = info["url"]
            self._latest_asset_url = info.get("asset_url", "")
            self.btn_sb_update.setText(f"Обновление v{latest}")
            self.btn_sb_update.setVisible(True)
            self.btn_open_release.setText(f"Обновить до v{latest}")
            self.btn_open_release.setVisible(True)
            self.lbl_update_status.setText(f"Доступна новая версия: v{latest} (текущая v{core.APP_VERSION})")
            self.lbl_update_status.setStyleSheet("color: #FBBF24; font-size: 12px; font-weight: 700;")
            self.append_log(f"Найдено обновление Unfit Zapret: v{latest}")

            prompt_text = (
                f"Вышла новая версия Unfit Zapret v{latest} (у вас v{core.APP_VERSION}).\n\nСкачать и установить сейчас?"
                if self._latest_asset_url
                else f"Вышла новая версия Unfit Zapret v{latest} (у вас v{core.APP_VERSION}).\n\nОткрыть страницу релиза на GitHub?"
            )
            ans = QMessageBox.question(
                self,
                "Доступно обновление",
                prompt_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.Yes:
                self._on_open_update_release()
        elif info.get("ok"):
            self.lbl_update_status.setText(f"Установлена актуальная версия: v{core.APP_VERSION}")
            self.lbl_update_status.setStyleSheet("color: #34D399; font-size: 12px; font-weight: 600;")
        else:
            if not silent:
                self.lbl_update_status.setText(f"Версия v{core.APP_VERSION} ({info.get('error', 'офлайн')})")

    def _on_open_update_release(self):
        if core.IS_WINDOWS and self._latest_asset_url.lower().endswith(".exe") and Path(sys.argv[0]).suffix.lower() == ".exe":
            self.btn_sb_update.setEnabled(False)
            self.btn_open_release.setEnabled(False)
            self.btn_open_release.setText("Скачивание...")
            self.lbl_update_status.setText("Скачивание обновления с GitHub...")
            self.append_log("Скачивание обновления с GitHub...")
            self._run_bg(core.download_and_apply_update, self._after_apply_update, self._latest_asset_url)
        else:
            QDesktopServices.openUrl(QUrl(self._latest_release_url))

    def _after_apply_update(self, res):
        self.btn_sb_update.setEnabled(True)
        self.btn_open_release.setEnabled(True)
        ok_call, payload = res
        if ok_call:
            ok, msg = payload
            if ok:
                self.append_log(msg)
                self._quit_app_keep_bypass()
                return
            QMessageBox.warning(self, "Обновление", f"{msg}\nОткроем страницу релиза в браузере.")
        QDesktopServices.openUrl(QUrl(self._latest_release_url))

    def _auto_repair_autorun_if_needed(self):
        info = core.get_autorun_info()
        if info["enabled"] and not info["path_matches"]:
            self.append_log(f"Обнаружен устаревший путь автозапуска ({info.get('command')}). Обновляем задачу...")
            ok, msg = core.enable_autorun()
            self.append_log(msg)
            self.refresh_all_state()

    def _run_bg(self, fn, on_done, *args):
        w = SimpleWorker(fn, *args)
        self._active_workers.append(w)

        def _cleanup(res):
            if w in self._active_workers:
                self._active_workers.remove(w)
            w.deleteLater()
            on_done(res)

        w.finished_res.connect(_cleanup, Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_toggle_bypass(self):
        self.btn_toggle_bypass.setEnabled(False)
        self.btn_restart_bypass.setEnabled(False)
        engine_name = core.get_engine_name()
        if core.is_winws_running():
            self.append_log(f"Остановка {engine_name}...")
            self._run_bg(core.kill_winws, self._after_stop_bypass)
        else:
            self.append_log(f"Запуск обхода {engine_name}...")
            self._run_bg(core.start_bypass_background, self._after_start_bypass)

    def _on_restart_bypass(self):
        self.btn_toggle_bypass.setEnabled(False)
        self.btn_restart_bypass.setEnabled(False)
        self.append_log(f"Перезапуск обхода {core.get_engine_name()}...")
        self._run_bg(core.start_bypass_background, self._after_start_bypass)

    def _after_start_bypass(self, res):
        self.btn_toggle_bypass.setEnabled(True)
        self.btn_restart_bypass.setEnabled(True)
        ok_call, payload = res
        if ok_call:
            ok, msg = payload
            self.append_log(msg)
            if not ok:
                QMessageBox.warning(self, "Ошибка запуска", msg)
        else:
            self.append_log(f"Ошибка: {payload}")
            QMessageBox.critical(self, "Ошибка", str(payload))
        self.refresh_all_state()

    def _after_stop_bypass(self, res):
        self.btn_toggle_bypass.setEnabled(True)
        self.btn_restart_bypass.setEnabled(True)
        self.append_log("Обход остановлен.")
        self.refresh_all_state()

    def _on_toggle_autorun(self):
        self.btn_toggle_autorun.setEnabled(False)
        info = core.get_autorun_info()
        if info["enabled"] and info["path_matches"]:
            self.append_log("Отключение автозапуска...")
            self._run_bg(core.disable_autorun, self._after_autorun_change)
        else:
            self.append_log("Настройка автозапуска (Boot + Logon XML)..." if core.IS_WINDOWS else "Настройка systemd-автозапуска...")
            self._run_bg(core.enable_autorun, self._after_autorun_change)

    def _after_autorun_change(self, res):
        self.btn_toggle_autorun.setEnabled(True)
        ok_call, payload = res
        if ok_call:
            ok, msg = payload
            self.append_log(msg)
            if not ok:
                QMessageBox.warning(self, "Автозапуск", msg)
        else:
            self.append_log(f"Ошибка автозапуска: {payload}")
        self.refresh_all_state()

    def _on_run_site_tests(self):
        self.btn_run_tests.setEnabled(False)
        self.test_summary_lbl.setText("Идёт параллельная проверка сайтов...")
        for key, (_, s_lbl) in self.site_badges.items():
            s_lbl.setText("Проверка...")
            s_lbl.setStyleSheet("color: #C084FC; font-size: 12px; font-weight: 600;")
        self.append_log("Запущена проверка доступности сайтов...")
        self._run_bg(core.check_sites_parallel, self._after_site_tests)

    def _after_site_tests(self, res):
        self.btn_run_tests.setEnabled(True)
        ok_call, payload = res
        if not ok_call:
            self.test_summary_lbl.setText(f"Ошибка проверки: {payload}")
            return

        results: dict[str, tuple[bool, str]] = payload
        ok_count = 0
        for key, title, _ in core.TEST_TARGETS:
            ok, code = results.get(key, (False, "ERR"))
            _, s_lbl = self.site_badges[key]
            if ok:
                ok_count += 1
                s_lbl.setText(f"OK (HTTP {code})")
                s_lbl.setStyleSheet("color: #34D399; font-size: 12px; font-weight: 700;")
            else:
                s_lbl.setText(f"FAIL ({code})")
                s_lbl.setStyleSheet("color: #FB7185; font-size: 12px; font-weight: 700;")
            self.append_log(f"  {title}: {'OK' if ok else 'FAIL'} ({code})")

        if ok_count == len(core.TEST_TARGETS):
            self.test_summary_lbl.setText("Все сайты доступны - соединение работает отлично!")
        else:
            self.test_summary_lbl.setText(f"Доступно {ok_count} из {len(core.TEST_TARGETS)} сайтов.")

    def _on_start_autotune(self):
        if self._tune_worker and self._tune_worker.isRunning():
            return
        self.btn_tune_start.setEnabled(False)
        self.btn_tune_stop.setEnabled(True)
        self.btn_tune_apply.setEnabled(False)
        self.tune_progress.setValue(0)

        for row in range(self.tune_table.rowCount()):
            for col in (2, 3, 4):
                it = self.tune_table.item(row, col)
                it.setText("-")
                it.setForeground(QColor("#A79AB8"))

        self._tune_worker = AutoTuneWorker()
        self._tune_worker.step_started.connect(self._on_tune_step_started, Qt.ConnectionType.QueuedConnection)
        self._tune_worker.step_result.connect(self._on_tune_step_result, Qt.ConnectionType.QueuedConnection)
        self._tune_worker.log_msg.connect(self.append_log, Qt.ConnectionType.QueuedConnection)
        self._tune_worker.finished_all.connect(self._on_tune_finished, Qt.ConnectionType.QueuedConnection)
        self._tune_worker.start()

    def _on_stop_autotune(self):
        if self._tune_worker and self._tune_worker.isRunning():
            self.tune_status_lbl.setText("Остановка подбора...")
            self._tune_worker.request_stop()
            self.btn_tune_stop.setEnabled(False)

    def _on_tune_step_started(self, idx: int, total: int, name: str):
        self.tune_status_lbl.setText(f"Тест {idx}/{total}: {name}...")
        self.tune_progress.setValue(idx - 1)
        self.tune_table.selectRow(idx - 1)

    def _on_tune_step_result(self, idx: int, yt_ok: bool, ds_ok: bool, note: str):
        row = idx - 1
        self.tune_progress.setValue(idx)

        yt_item = self.tune_table.item(row, 2)
        yt_item.setText("OK" if yt_ok else "FAIL")
        yt_item.setForeground(QColor("#34D399" if yt_ok else "#FB7185"))

        ds_item = self.tune_table.item(row, 3)
        ds_item.setText("OK" if ds_ok else "FAIL")
        ds_item.setForeground(QColor("#34D399" if ds_ok else "#FB7185"))

        st_item = self.tune_table.item(row, 4)
        st_item.setText(note)
        if yt_ok and ds_ok:
            st_item.setForeground(QColor("#FBBF24"))
        elif yt_ok or ds_ok:
            st_item.setForeground(QColor("#C084FC"))
        else:
            st_item.setForeground(QColor("#FB7185"))

    def _on_tune_finished(self, results: list, stopped_early: bool):
        self.btn_tune_start.setEnabled(True)
        self.btn_tune_stop.setEnabled(False)
        self.btn_tune_apply.setEnabled(True)

        best_idx = None
        for r in results:
            if r["yt"] and r["ds"]:
                best_idx = r["index"]
                break
        if best_idx is None:
            for r in results:
                if r["yt"]:
                    best_idx = r["index"]
                    break
        if best_idx is None and results:
            best_idx = min(3, len(results))

        if best_idx is not None:
            self.tune_table.selectRow(best_idx - 1)
            msg = (
                f"Подбор остановлен. Лучшая из проверенных: #{best_idx}."
                if stopped_early
                else f"Готово! Рекомендуемая стратегия: #{best_idx}. Нажмите «Применить выбранную и запустить»."
            )
            self.tune_status_lbl.setText(msg)
        else:
            self.tune_status_lbl.setText("Подбор завершён без результатов.")

        self.refresh_all_state()

    def _on_apply_selected_tune(self):
        row = self.tune_table.currentRow()
        if row < 0 or row >= len(core.STRATEGIES):
            QMessageBox.information(self, "Выбор стратегии", "Выберите строку в таблице стратегий.")
            return

        idx = row + 1
        cfg = core.load_config()
        cfg["strategy"] = core.STRATEGIES[row]["args"]
        cfg["index"] = idx
        core.save_config(cfg)
        self.append_log(f"Сохранена стратегия #{idx} ({core.STRATEGIES[row]['name']}). Запуск обхода...")
        self.btn_tune_apply.setEnabled(False)
        self._run_bg(core.start_bypass_background, self._after_apply_tune)

    def _after_apply_tune(self, res):
        self.btn_tune_apply.setEnabled(True)
        ok_call, payload = res
        if ok_call:
            ok, msg = payload
            self.append_log(msg)
            if ok:
                self.tune_status_lbl.setText("Стратегия применена, обход запущен!")
            else:
                QMessageBox.warning(self, "Ошибка запуска", msg)
        self.refresh_all_state()

    def _load_settings_into_ui(self):
        cfg = core.load_config()
        idx = cfg.get("index", 1)
        pos = max(0, min(idx - 1, self.combo_strategy.count() - 1))
        self.combo_strategy.setCurrentIndex(pos)

        udp = cfg.get("udp_mode", "narrow")
        if udp == "wide":
            self.rb_udp_wide.setChecked(True)
        elif udp == "disabled":
            self.rb_udp_disabled.setChecked(True)
        else:
            self.rb_udp_narrow.setChecked(True)

        sni = cfg.get("fake_sni", "www.google.com")
        found_sni = self.combo_sni.findData(sni)
        if found_sni >= 0:
            self.combo_sni.setCurrentIndex(found_sni)
            self.edit_custom_sni.setVisible(False)
        else:
            self.combo_sni.setCurrentIndex(self.combo_sni.count() - 1)
            self.edit_custom_sni.setText(sni)
            self.edit_custom_sni.setVisible(True)

        self.chk_minimize_tray.setChecked(cfg.get("minimize_to_tray", True))

    def _on_sni_combo_changed(self):
        self.edit_custom_sni.setVisible(self.combo_sni.currentData() == "__custom__")

    def _on_save_settings(self):
        idx = self.combo_strategy.currentData()
        udp_mode = "narrow"
        if self.rb_udp_wide.isChecked():
            udp_mode = "wide"
        elif self.rb_udp_disabled.isChecked():
            udp_mode = "disabled"

        sni_data = self.combo_sni.currentData()
        if sni_data == "__custom__":
            sni_val = self.edit_custom_sni.text().strip() or "www.google.com"
        else:
            sni_val = sni_data

        cfg = core.load_config()
        cfg["index"] = idx
        cfg["strategy"] = core.STRATEGIES[idx - 1]["args"]
        cfg["udp_mode"] = udp_mode
        cfg["fake_sni"] = sni_val
        cfg["minimize_to_tray"] = self.chk_minimize_tray.isChecked()
        core.save_config(cfg)

        self.append_log(f"Настройки сохранены: стратегия #{idx}, UDP={udp_mode.upper()}, SNI={sni_val}")
        if core.is_winws_running():
            self.append_log("Перезапускаем обход для применения новых настроек...")
            self.btn_save_settings.setEnabled(False)
            self._run_bg(core.start_bypass_background, self._after_save_settings_restart)
        else:
            self.refresh_all_state()
            QMessageBox.information(self, "Настройки", "Параметры сохранены.")

    def _after_save_settings_restart(self, res):
        self.btn_save_settings.setEnabled(True)
        ok_call, payload = res
        if ok_call:
            _, msg = payload
            self.append_log(msg)
        self.refresh_all_state()

    def _load_exclusion_editor(self):
        core.ensure_files_exist()
        fname = self.combo_list_file.currentData()
        fpath = core.LISTS_DIR / fname
        try:
            self.list_editor.setPlainText(fpath.read_text(encoding="utf-8"))
        except Exception as e:
            self.list_editor.setPlainText(f"# Ошибка чтения {fpath}: {e}")

    def _on_save_list_file(self):
        fname = self.combo_list_file.currentData()
        fpath = core.LISTS_DIR / fname
        try:
            fpath.write_text(self.list_editor.toPlainText(), encoding="utf-8")
            self.append_log(f"Сохранён файл списка: {fname}")
            if core.is_winws_running():
                self.append_log("Перезапускаем обход для применения списка...")
                self._run_bg(core.start_bypass_background, lambda _: self.refresh_all_state())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {e}")

    def _on_scan_exclusions(self):
        self.btn_scan_vpn.setEnabled(False)
        self.scan_result_lbl.setText("Сканирование процессов и сетевых подключений...")
        self.append_log("Запущено сканирование активных подключений VPN и игр...")
        self._run_bg(core.scan_and_exclude_active_connections, self._after_scan_exclusions)

    def _after_scan_exclusions(self, res):
        self.btn_scan_vpn.setEnabled(True)
        ok_call, payload = res
        if not ok_call:
            self.scan_result_lbl.setText(f"Ошибка: {payload}")
            return
        if not payload["ok"]:
            self.scan_result_lbl.setText(payload["error"])
            return

        added = payload["added"]
        total = payload["found_total"]
        if added:
            for ip_str, cat, proc in added:
                self.append_log(f"  [+] Исключён IP {ip_str} ({cat}: {proc})")
            self.scan_result_lbl.setText(f"Добавлено новых IP: {len(added)} (всего обнаружено: {total}).")
        elif total > 0:
            self.scan_result_lbl.setText(f"Обнаружено подключений: {total}, но все эти IP уже были в списке исключений.")
        else:
            self.scan_result_lbl.setText("Активных VPN или игровых подключений не обнаружено.")

        self._load_exclusion_editor()
        self.refresh_all_state()

    def _refresh_diagnostics(self):
        if core.IS_WINDOWS:
            drv = "WinDivert32.sys" if (core.BIN_DIR / "WinDivert32.sys").exists() and not (core.BIN_DIR / "WinDivert64.sys").exists() else "WinDivert64.sys"
            checks = [
                ("winws.exe", (core.BIN_DIR / "winws.exe").exists()),
                ("WinDivert.dll", (core.BIN_DIR / "WinDivert.dll").exists()),
                (drv, (core.BIN_DIR / drv).exists()),
                ("cygwin1.dll", (core.BIN_DIR / "cygwin1.dll").exists()),
                ("zapret_config.json", core.CONFIG_FILE.exists()),
            ]
        else:
            import shutil as _shutil
            engine_bin = core.get_engine_binary()
            checks = [
                (engine_bin.name, engine_bin.exists()),
                ("nft/iptables", bool(_shutil.which("nft") or _shutil.which("iptables"))),
                ("curl", bool(_shutil.which("curl"))),
                ("zapret_config.json", core.CONFIG_FILE.exists()),
            ]
        parts = [f"{name}: {'OK' if ok else 'НЕТ'}" for name, ok in checks]
        autorun_log_info = ""
        if core.AUTORUN_LOG_FILE.exists():
            try:
                lines = core.AUTORUN_LOG_FILE.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
                if lines:
                    autorun_log_info = f"\nПоследняя запись автозапуска: {lines[-1]}"
            except Exception:
                pass
        self.diag_label.setText(f"[{core.get_platform_label()}]  " + "   |   ".join(parts) + autorun_log_info)

    def _on_open_work_dir(self):
        try:
            if core.IS_WINDOWS:
                os.startfile(str(core.WORK_DIR))
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.WORK_DIR)))
        except Exception as e:
            self.append_log(f"Не удалось открыть папку: {e}")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self.show_and_focus()

    def show_and_focus(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_app_keep_bypass(self):
        self._force_quit = True
        self.tray_icon.hide()
        QApplication.quit()

    def _quit_app_stop_bypass(self):
        core.kill_winws(timeout=2.0)
        self._quit_app_keep_bypass()

    def closeEvent(self, event):
        cfg = core.load_config()
        if not self._force_quit and cfg.get("minimize_to_tray", True) and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_notified_once:
                self._tray_notified_once = True
                self.tray_icon.showMessage(
                    "Unfit Zapret",
                    "Приложение свёрнуто в трей и продолжает работу.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
            return
        self.tray_icon.hide()
        super().closeEvent(event)


def _signal_existing_instance() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SINGLE_INSTANCE_KEY)
    if sock.waitForConnected(250):
        sock.write(b"SHOW")
        sock.waitForBytesWritten(250)
        sock.disconnectFromServer()
        return True
    return False


def main():
    if not core.is_admin():
        core.relaunch_as_admin()
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyleSheet(APP_STYLESHEET)

    if _signal_existing_instance():
        sys.exit(0)

    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
    server = QLocalServer()
    server.listen(SINGLE_INSTANCE_KEY)

    win = MainWindow()

    def _on_new_conn():
        client = server.nextPendingConnection()
        if client:
            client.waitForReadyRead(200)
            client.close()
        win.show_and_focus()

    server.newConnection.connect(_on_new_conn)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
