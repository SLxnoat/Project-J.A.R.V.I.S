from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget, QProgressBar,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 148
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


class C:
    # ── Deep-space base tones ──
    BG        = "#03060b"
    PANEL     = "#060c14"
    PANEL2    = "#08101a"
    BORDER    = "#12253a"
    BORDER_B  = "#1e4468"
    BORDER_A  = "#162e50"
    # ── Primary: Luminous teal / cyan ──
    PRI       = "#00e5ff"
    PRI_DIM   = "#006e85"
    PRI_GHO   = "#001822"
    # ── Accent: Warm amber / gold ──
    ACC       = "#ff9f1c"
    ACC2      = "#ffd166"
    # ── Status tones ──
    GREEN     = "#00e676"
    GREEN_D   = "#00a152"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    # ── Text spectrum ──
    TEXT      = "#b0ecf5"
    TEXT_DIM  = "#3a7a90"
    TEXT_MED  = "#6abcce"
    WHITE     = "#e0f4ff"
    DARK      = "#040a12"
    BAR_BG    = "#0a1520"

    # ── Ambient mode palettes (HUD glow colors per state) ──
    # Speaking: warm coral-orange energy
    SPEAK_PRI    = "#ff6b3d"
    SPEAK_SEC    = "#ff9f1c"
    SPEAK_GLOW   = "#ff5722"
    # Thinking: electric violet/indigo cognition
    THINK_PRI    = "#b388ff"
    THINK_SEC    = "#7c4dff"
    THINK_GLOW   = "#651fff"
    # Listening: serene teal-aqua readiness
    LISTEN_PRI   = "#00e5ff"
    LISTEN_SEC   = "#18ffff"
    LISTEN_GLOW  = "#00b8d4"
    # Idle: muted steel-blue
    IDLE_PRI     = "#546e7a"
    IDLE_SEC     = "#37474f"
    IDLE_GLOW    = "#263238"


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


class GlassStatusBadge(QWidget):
    def __init__(self, title: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._value = value
        self._color = color
        self.setFixedHeight(38)
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(500)
        self._led_on = True

    def _step(self):
        self._led_on = not self._led_on
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        
        # Background glass card
        bg_grad = QLinearGradient(0, 0, W, H)
        bg_grad.setColorAt(0.0, QColor(10, 22, 38, 110))
        bg_grad.setColorAt(1.0, QColor(4, 9, 16, 150))
        p.setBrush(QBrush(bg_grad))
        
        b_col = QColor(self._color)
        p.setPen(QPen(QColor(b_col.red(), b_col.green(), b_col.blue(), 60), 0.8))
        p.drawRoundedRect(QRectF(1, 1, W-2, H-2), 4, 4)
        
        # Flashing LED status dot
        led_col = QColor(self._color)
        if not self._led_on:
            led_col.setAlpha(60)
        p.setBrush(QBrush(led_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(8, H/2 - 4, 8, 8))
        
        # Drawing tech text
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(22, 3, W - 30, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)
        
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor(self._color), 1))
        p.drawText(QRectF(22, 16, W - 30, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._value)


class TechHeader(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self.setFixedHeight(18)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        metrics = p.fontMetrics()
        txt_w = metrics.horizontalAdvance(self._title) + 12
        
        # Futuristic left bracket line
        p.setPen(QPen(QColor(C.PRI), 1.2))
        p.drawLine(QPointF(0, H/2), QPointF(10, H/2))
        p.drawLine(QPointF(10, H/2), QPointF(14, H/2 - 4))
        p.drawLine(QPointF(14, H/2 - 4), QPointF(20, H/2 - 4))
        
        # Section text
        p.setPen(QPen(qcol(C.TEXT), 1))
        p.drawText(QRectF(24, 0, txt_w, H), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)
        
        # Futuristic right line
        rx = 24 + txt_w
        p.setPen(QPen(QColor(C.PRI_DIM), 1.0))
        p.drawLine(QPointF(rx, H/2 - 4), QPointF(rx + 6, H/2 - 4))
        p.drawLine(QPointF(rx + 6, H/2 - 4), QPointF(rx + 10, H/2))
        p.drawLine(QPointF(rx + 10, H/2), QPointF(W - 8, H/2))
        
        # End dot marker
        p.setBrush(QBrush(qcol(C.PRI)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(W - 5, H/2 - 2, 4, 4))


class LogTerminalHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        self._blink = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(600)

    def _step(self):
        self._blink = not self._blink
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        
        # Terminal-style top bar background
        p.fillRect(self.rect(), QColor(6, 12, 22, 230))
        p.setPen(QPen(QColor(C.BORDER_A), 1))
        p.drawLine(0, H - 1, W, H - 1)
        
        # Recording status dot
        if self._blink:
            p.setBrush(QBrush(qcol(C.RED)))
        else:
            p.setBrush(QBrush(QColor(150, 0, 30, 80)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(8, H/2 - 4, 8, 8))
        
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT), 1))
        p.drawText(QRectF(22, 0, 120, H), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "LOG_STREAM: LIVE")
        
        # Port designation
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 0, W - 8, H), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "PORT: COM-4 (9600)")


class GlassPanel(QFrame):
    def __init__(self, parent=None, border_color=None, border_width=1.0, corner_brackets=True, grid_overlay=True):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._border_color = border_color or C.BORDER
        self._border_width = border_width
        self._corner_brackets = corner_brackets
        self._grid_overlay = grid_overlay
        self._hovered = False
        
        # Glow breathing animation
        self._glow_alpha = 100
        self._glow_dir = 1
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_glow)
        self._timer.start(50)

    def _update_glow(self):
        self._glow_alpha += 3 * self._glow_dir
        if self._glow_alpha >= 180:
            self._glow_alpha = 180
            self._glow_dir = -1
        elif self._glow_alpha <= 70:
            self._glow_alpha = 70
            self._glow_dir = 1
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        rect = QRectF(1, 1, W - 2, H - 2)
        
        # 1. Frosted Glass semi-transparent background
        bg_grad = QLinearGradient(0, 0, W, H)
        bg_grad.setColorAt(0.0, QColor(8, 16, 28, 130))
        bg_grad.setColorAt(0.5, QColor(4, 9, 16, 165))
        bg_grad.setColorAt(1.0, QColor(2, 4, 8, 195))
        p.setBrush(QBrush(bg_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 8, 8)
        
        # 2. Tech dot grid
        if self._grid_overlay:
            p.setPen(QPen(QColor(0, 229, 255, 8), 1))
            grid_size = 18
            for x in range(12, W - 12, grid_size):
                for y in range(12, H - 12, grid_size):
                    p.drawPoint(x, y)
                    
        # 3. Glowing Glass Border
        border_grad = QLinearGradient(0, 0, W, H)
        base_b_col = QColor(self._border_color)
        alpha_val = self._glow_alpha if self._hovered else 50
        pulse_color = QColor(base_b_col.red(), base_b_col.green(), base_b_col.blue(), alpha_val)
        dim_color = QColor(base_b_col.red(), base_b_col.green(), base_b_col.blue(), 25)
        
        border_grad.setColorAt(0.0, pulse_color)
        border_grad.setColorAt(0.4, pulse_color)
        border_grad.setColorAt(0.8, dim_color)
        border_grad.setColorAt(1.0, QColor(0, 0, 0, 15))
        
        p.setPen(QPen(border_grad, self._border_width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 8, 8)
        
        # 4. Corner Brackets (classic sci-fi design)
        if self._corner_brackets:
            bl = 10  # bracket length
            p.setPen(QPen(QColor(self._border_color), 1.5))
            
            # Top-Left
            p.drawLine(QPointF(2, 2), QPointF(2 + bl, 2))
            p.drawLine(QPointF(2, 2), QPointF(2, 2 + bl))
            # Top-Right
            p.drawLine(QPointF(W - 2, 2), QPointF(W - 2 - bl, 2))
            p.drawLine(QPointF(W - 2, 2), QPointF(W - 2, 2 + bl))
            # Bottom-Left
            p.drawLine(QPointF(2, H - 2), QPointF(2 + bl, H - 2))
            p.drawLine(QPointF(2, H - 2), QPointF(2, H - 2 - bl))
            # Bottom-Right
            p.drawLine(QPointF(W - 2, H - 2), QPointF(W - 2 - bl, H - 2))
            p.drawLine(QPointF(W - 2, H - 2), QPointF(W - 2, H - 2 - bl))


class SpaceBackgroundWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stars = []
        self._glow_anim = 0.0
        self._glow_dir = 1
        
        # Generate random stars
        for _ in range(70):
            self._stars.append({
                "x": random.uniform(0.01, 0.99),
                "y": random.uniform(0.01, 0.99),
                "size": random.uniform(0.8, 2.2),
                "speed": random.uniform(0.015, 0.065),
                "brightness": random.uniform(80, 255),
                "pulse_dir": random.choice([-1, 1])
            })
            
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)

    def _step(self):
        for s in self._stars:
            s["brightness"] += s["pulse_dir"] * s["speed"] * 45
            if s["brightness"] >= 255:
                s["brightness"] = 255
                s["pulse_dir"] = -1
            elif s["brightness"] <= 40:
                s["brightness"] = 40
                s["pulse_dir"] = 1
                
        self._glow_anim += 0.004 * self._glow_dir
        if self._glow_anim >= 1.0:
            self._glow_anim = 1.0
            self._glow_dir = -1
        elif self._glow_anim <= 0.0:
            self._glow_anim = 0.0
            self._glow_dir = 1
            
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        W, H = self.width(), self.height()
        
        # Radial background gradient with nebula tint
        bg_grad = QRadialGradient(W / 2, H / 2, max(W, H) * 0.7)
        bg_grad.setColorAt(0.0, QColor(4, 14, 28))
        nebula_alpha = int(14 + 12 * self._glow_anim)
        bg_grad.setColorAt(0.45, QColor(18, 6, 30, nebula_alpha))
        bg_grad.setColorAt(0.9, QColor(3, 5, 8))
        bg_grad.setColorAt(1.0, QColor(1, 2, 4))
        p.fillRect(self.rect(), bg_grad)
        
        # Draw starfield
        for s in self._stars:
            sx = int(s["x"] * W)
            sy = int(s["y"] * H)
            col = QColor(180, 242, 255, int(s["brightness"]))
            p.setPen(QPen(col, s["size"]))
            p.drawPoint(sx, sy)
            
        # Tactical HUD grid lines
        grid_col = QColor(0, 229, 255, 12)
        p.setPen(QPen(grid_col, 0.5))
        grid_size = 90
        for x in range(0, W, grid_size):
            p.drawLine(x, 0, x, H)
        for y in range(0, H, grid_size):
            p.drawLine(0, y, W, y)
            
        # Compass ring marking
        p.setPen(QPen(QColor(0, 229, 255, 8), 0.7))
        p.drawEllipse(QRectF(W/2 - 180, H/2 - 180, 360, 360))
        p.drawEllipse(QRectF(W/2 - 360, H/2 - 360, 720, 720))
        
        # Center crosshair
        p.setPen(QPen(QColor(0, 229, 255, 20), 1))
        cx, cy = W/2, H/2
        p.drawLine(QPointF(cx - 12, cy), QPointF(cx + 12, cy))
        p.drawLine(QPointF(cx, cy - 12), QPointF(cx, cy + 12))
        
        # Diagnostics printouts
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(QColor(0, 229, 255, 30), 1))
        p.drawText(20, 70, "SYS.LOC: GRID-39X-OMEGA")
        p.drawText(20, 84, "ANTENNA: RX-9982 (STABLE)")
        p.drawText(W - 180, 70, "INTEL: TAC-HUD v3.9")
        p.drawText(W - 180, 84, "ORBIT: LEO-288.94S")


class GlassButton(QPushButton):
    def __init__(self, text: str, color: str = C.PRI, parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._color = color
        self._hovered = False
        self._pressed = False
        self._glow_alpha = 100
        self._glow_dir = 1
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_glow)
        self._timer.start(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _update_glow(self):
        if self._hovered:
            self._glow_alpha += 6 * self._glow_dir
            if self._glow_alpha >= 230:
                self._glow_alpha = 230
                self._glow_dir = -1
            elif self._glow_alpha <= 110:
                self._glow_alpha = 110
                self._glow_dir = 1
        else:
            self._glow_alpha = 100
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        rect = QRectF(1, 1, W - 2, H - 2)

        bg_col = QColor(self._color)
        if self._pressed:
            bg_val = QColor(bg_col.red(), bg_col.green(), bg_col.blue(), 75)
        elif self._hovered:
            bg_val = QColor(bg_col.red(), bg_col.green(), bg_col.blue(), 40)
        else:
            bg_val = QColor(8, 16, 28, 85)

        p.setBrush(QBrush(bg_val))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 4, 4)

        b_alpha = self._glow_alpha if self._hovered else 50
        border_pen = QPen(QColor(bg_col.red(), bg_col.green(), bg_col.blue(), b_alpha), 1.1)
        p.setPen(border_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 4, 4)

        # corner highlight lines on hover
        if self._hovered:
            p.setPen(QPen(QColor(255, 255, 255, 180), 1.2))
            bl = 3
            p.drawLine(QPointF(1, 1), QPointF(1 + bl, 1))
            p.drawLine(QPointF(1, 1), QPointF(1, 1 + bl))
            p.drawLine(QPointF(W - 1, 1), QPointF(W - 1 - bl, 1))
            p.drawLine(QPointF(W - 1, 1), QPointF(W - 1, 1 + bl))

        p.setFont(self.font())
        txt_col = QColor(C.WHITE) if self._hovered else QColor(C.TEXT_MED)
        if self._color in (C.RED, C.MUTED_C):
            txt_col = QColor(C.MUTED_C) if not self._hovered else QColor(C.WHITE)
        elif self._color == C.GREEN:
            txt_col = QColor(C.GREEN) if not self._hovered else QColor(C.WHITE)
            
        p.setPen(QPen(txt_col, 1))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())


class GlassLineEdit(QLineEdit):
    def __init__(self, parent=None, accent_color=C.PRI):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._accent_color = accent_color
        self._hovered = False
        self._error = False
        self._anim_progress = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step_anim)
        self._timer.start(25)
        self.setFixedHeight(30)

    def set_error(self, err: bool):
        self._error = err
        self.update()

    def _step_anim(self):
        target = 1.0 if self.hasFocus() else (0.4 if self._hovered else 0.0)
        self._anim_progress += (target - self._anim_progress) * 0.2
        if abs(target - self._anim_progress) < 0.01:
            self._anim_progress = target
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self._error = False  # clear error on focus
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        rect = QRectF(1, 1, W - 2, H - 2)

        bg_col = QColor(4, 9, 18, 110 if self.hasFocus() else 75)
        p.setBrush(QBrush(bg_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 4, 4)

        if self._error:
            act_col = QColor(C.RED)
            r, g, b = act_col.red(), act_col.green(), act_col.blue()
            alpha = 200
        else:
            base_col = QColor(C.BORDER)
            act_col = QColor(self._accent_color)
            r = int(base_col.red() + (act_col.red() - base_col.red()) * self._anim_progress)
            g = int(base_col.green() + (act_col.green() - base_col.green()) * self._anim_progress)
            b = int(base_col.blue() + (act_col.blue() - base_col.blue()) * self._anim_progress)
            alpha = int(120 + 135 * self._anim_progress)
        
        p.setPen(QPen(QColor(r, g, b, alpha), 1.0 + 0.5 * (1.0 if self._error else self._anim_progress)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 4, 4)

        if self.hasFocus() or self._error:
            p.setPen(QPen(act_col, 1.5))
            p.drawLine(QPointF(4, H - 4), QPointF(10, H - 4))
            p.drawLine(QPointF(4, H - 4), QPointF(4, H - 10))

        p.end()
        super().paintEvent(event)


class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()

        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # NVIDIA
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass

        # AMD (Linux)
        if _OS == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass

            # Intel GPU (Linux)
            try:
                r = subprocess.run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        # macOS — powermetrics (GPU Engine)
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries:
                        return entries[0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass

        if _OS == "Windows":
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass

        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

class HudCanvas(QWidget):
    """Tactical Intelligence Interface – Ambient HUD Core Visualiser."""

    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        # ── animation state ──
        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()

        # ── wireware ring rotations ──
        self._wire_angles  = [0.0, 120.0, 240.0]
        # ── orbital data ring angles ──
        self._orbit_angles = [0.0, 90.0, 180.0, 270.0]
        # ── scan sweep ──
        self._scan       = 0.0
        self._scan2      = 180.0
        # ── pulse rings ──
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        # ── breathing core ──
        self._breath     = 0.0
        self._breath_dir = 1
        # ── particle nebula ──
        self._particles: list[list[float]] = []
        # ── blink state ──
        self._blink      = True
        self._blink_tick = 0
        # ── ambient glow transition ──
        self._glow_r = 0; self._glow_g = 229; self._glow_b = 255  # start teal
        self._tgt_r  = 0; self._tgt_g  = 229; self._tgt_b  = 255
        # ── hex wireware mesh points (precomputed) ──
        self._hex_cache: list[list[tuple[float, float]]] = []

        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    # ── ambient color helpers ──
    def _ambient_colors(self) -> tuple[str, str, str]:
        """Return (primary, secondary, glow) hex based on current state."""
        if self.muted:
            return (C.MUTED_C, C.RED, "#3d0015")
        elif self.speaking:
            return (C.SPEAK_PRI, C.SPEAK_SEC, C.SPEAK_GLOW)
        elif self.state == "THINKING" or self.state == "PROCESSING":
            return (C.THINK_PRI, C.THINK_SEC, C.THINK_GLOW)
        elif self.state == "LISTENING":
            return (C.LISTEN_PRI, C.LISTEN_SEC, C.LISTEN_GLOW)
        else:
            return (C.IDLE_PRI, C.IDLE_SEC, C.IDLE_GLOW)

    def _ambient_qcolors(self) -> tuple[QColor, QColor, QColor]:
        pri, sec, glow = self._ambient_colors()
        return qcol(pri), qcol(sec), qcol(glow)

    def _step(self):
        self._tick += 1
        now = time.time()

        # ── update targets based on state ──
        if now - self._last_t > (0.10 if self.speaking else 0.45):
            if self.speaking:
                self._tgt_scale = random.uniform(1.04, 1.12)
                self._tgt_halo  = random.uniform(160, 220)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(12, 22)
            elif self.state in ("THINKING", "PROCESSING"):
                self._tgt_scale = random.uniform(1.01, 1.04)
                self._tgt_halo  = random.uniform(90, 130)
            elif self.state == "LISTENING":
                self._tgt_scale = random.uniform(1.001, 1.015)
                self._tgt_halo  = random.uniform(55, 80)
            else:
                self._tgt_scale = random.uniform(1.000, 1.005)
                self._tgt_halo  = random.uniform(30, 50)
            self._last_t = now

        # ── smooth interpolation ──
        sp = 0.35 if self.speaking else 0.12
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        # ── wireware ring rotation ──
        if self.speaking:
            wire_speeds = [1.8, -1.2, 2.5]
        elif self.state in ("THINKING", "PROCESSING"):
            wire_speeds = [1.2, -0.8, 1.6]
        else:
            wire_speeds = [0.4, -0.25, 0.55]
        for i, spd in enumerate(wire_speeds):
            self._wire_angles[i] = (self._wire_angles[i] + spd) % 360

        # ── orbital data rings ──
        orbit_base = 1.5 if self.speaking else (0.9 if self.state in ("THINKING", "PROCESSING") else 0.4)
        for i in range(4):
            direction = 1 if i % 2 == 0 else -1
            self._orbit_angles[i] = (self._orbit_angles[i] + direction * orbit_base * (1 + i * 0.25)) % 360

        # ── scan sweep ──
        self._scan  = (self._scan  + (3.5 if self.speaking else 1.1)) % 360
        self._scan2 = (self._scan2 + (-2.2 if self.speaking else -0.65)) % 360

        # ── pulse rings ──
        fw  = min(self.width(), self.height())
        lim = fw * 0.72
        pulse_spd = 3.5 if self.speaking else (2.2 if self.state in ("THINKING", "PROCESSING") else 1.4)
        self._pulses = [r + pulse_spd for r in self._pulses if r + pulse_spd < lim]
        spawn_chance = 0.08 if self.speaking else (0.04 if self.state in ("THINKING", "PROCESSING") else 0.018)
        if len(self._pulses) < 4 and random.random() < spawn_chance:
            self._pulses.append(0.0)

        # ── breathing core ──
        breath_speed = 0.04 if self.speaking else 0.018
        self._breath += breath_speed * self._breath_dir
        if self._breath >= 1.0:
            self._breath = 1.0; self._breath_dir = -1
        elif self._breath <= 0.0:
            self._breath = 0.0; self._breath_dir = 1

        # ── particle nebula ──
        if (self.speaking and random.random() < 0.35) or \
           (self.state in ("THINKING", "PROCESSING") and random.random() < 0.15) or \
           (self.state == "LISTENING" and random.random() < 0.06):
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.26
            speed_mult = 2.2 if self.speaking else (1.4 if self.state in ("THINKING", "PROCESSING") else 0.8)
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.5, speed_mult),
                math.sin(ang) * random.uniform(0.5, speed_mult) - 0.2,
                1.0,
                random.uniform(1.5, 4.0),  # radius
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.022, p[5]]
            for p in self._particles if p[4] > 0
        ]

        # ── ambient glow color smooth transition ──
        pri_hex, _, _ = self._ambient_colors()
        tc = QColor(pri_hex)
        self._tgt_r, self._tgt_g, self._tgt_b = tc.red(), tc.green(), tc.blue()
        glow_lerp = 0.06
        self._glow_r += int((self._tgt_r - self._glow_r) * glow_lerp)
        self._glow_g += int((self._tgt_g - self._glow_g) * glow_lerp)
        self._glow_b += int((self._tgt_b - self._glow_b) * glow_lerp)

        # ── blink ──
        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0

        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)
        r_core = fw * 0.24  # core radius – everything else stays OUTSIDE

        pri_col, sec_col, glow_col = self._ambient_qcolors()

        # ═══════════════════════════════════════════════
        # LAYER 0: Glassmorphic panel background
        # ═══════════════════════════════════════════════
        rect = QRectF(1, 1, W - 2, H - 2)
        bg_grad = QLinearGradient(0, 0, W, H)
        bg_grad.setColorAt(0.0, QColor(8, 16, 28, 120))
        bg_grad.setColorAt(0.5, QColor(4, 9, 16, 150))
        bg_grad.setColorAt(1.0, QColor(2, 4, 8, 180))
        p.setBrush(QBrush(bg_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 8, 8)
        
        # Central HUD glowing border
        border_col = QColor(self._glow_r, self._glow_g, self._glow_b, 60)
        p.setPen(QPen(border_col, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 8, 8)

        # Subtle hex dot grid – very faint, almost subliminal
        grid_a = max(8, min(30, int(self._halo * 0.08)))
        p.setPen(QPen(QColor(self._glow_r, self._glow_g, self._glow_b, grid_a), 1))
        spacing = 52
        for x in range(0, W, spacing):
            for y in range(0, H, spacing):
                # skip dots near core to avoid clutter
                dx, dy = x - cx, y - cy
                if math.sqrt(dx*dx + dy*dy) > r_core * 1.8:
                    p.drawPoint(x, y)

        # ═══════════════════════════════════════════════
        # LAYER 1: Ambient radial glow (behind everything)
        # ═══════════════════════════════════════════════
        glow_radius = fw * (0.55 + self._breath * 0.08)
        grad = QRadialGradient(cx, cy, glow_radius)
        grad.setColorAt(0.0, QColor(self._glow_r, self._glow_g, self._glow_b, max(0, min(60, int(self._halo * 0.25)))))
        grad.setColorAt(0.4, QColor(self._glow_r, self._glow_g, self._glow_b, max(0, min(25, int(self._halo * 0.10)))))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - glow_radius, cy - glow_radius, glow_radius * 2, glow_radius * 2))

        # ═══════════════════════════════════════════════
        # LAYER 2: Pulse rings (expanding outward from core)
        # ═══════════════════════════════════════════════
        for pr in self._pulses:
            frac = 1.0 - pr / (fw * 0.72)
            a = max(0, int(120 * frac * frac))
            ring_col = QColor(self._glow_r, self._glow_g, self._glow_b, a)
            p.setPen(QPen(ring_col, 1.0 + frac))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # ═══════════════════════════════════════════════
        # LAYER 3: Wireware visualiser mesh (outer ring zone)
        # ═══════════════════════════════════════════════
        self._draw_wireware(p, cx, cy, fw, r_core)

        # ═══════════════════════════════════════════════
        # LAYER 4: Orbital data rings (tactical arcs)
        # ═══════════════════════════════════════════════
        self._draw_orbital_rings(p, cx, cy, fw, r_core)

        # ═══════════════════════════════════════════════
        # LAYER 5: Scan sweep lines
        # ═══════════════════════════════════════════════
        self._draw_scan_sweeps(p, cx, cy, fw, r_core)

        # ═══════════════════════════════════════════════
        # LAYER 6: Tick marks (outer perimeter)
        # ═══════════════════════════════════════════════
        t_out = fw * 0.485
        t_in  = fw * 0.465
        tick_a = max(40, min(140, int(self._halo * 0.55)))
        p.setPen(QPen(QColor(self._glow_r, self._glow_g, self._glow_b, tick_a), 1))
        for deg in range(0, 360, 6):
            rad = math.radians(deg)
            is_major = deg % 30 == 0
            inn = t_in - (4 if is_major else 0)
            w_pen = 1.5 if is_major else 0.8
            p.setPen(QPen(QColor(self._glow_r, self._glow_g, self._glow_b, tick_a if is_major else tick_a // 2), w_pen))
            p.drawLine(
                QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad)),
            )

        # ═══════════════════════════════════════════════
        # LAYER 7: Corner brackets (tactical framing)
        # ═══════════════════════════════════════════════
        bl = 28
        bc_a = max(100, min(210, int(self._halo * 0.8)))
        bc = QColor(self._glow_r, self._glow_g, self._glow_b, bc_a)
        hl, hr = cx - fw // 2 + 8, cx + fw // 2 - 8
        ht, hb = cy - fw // 2 + 8, cy + fw // 2 - 8
        p.setPen(QPen(bc, 2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

        # ═══════════════════════════════════════════════
        # LAYER 8: Core – face/orb (NO elements overlap this)
        # ═══════════════════════════════════════════════

        # Core rim glow (soft ring at edge of core)
        for i in range(6):
            rim_r = r_core * (1.08 + i * 0.03)
            rim_a = max(0, min(100, int(self._halo * 0.18 * (1 - i / 6))))
            p.setPen(QPen(QColor(self._glow_r, self._glow_g, self._glow_b, rim_a), 1.5 - i * 0.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - rim_r, cy - rim_r, rim_r * 2, rim_r * 2))

        if self._face_px:
            fsz    = int(fw * 0.48 * self._scale)
            scaled = self._face_px.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(int(cx - fsz / 2), int(cy - fsz / 2), scaled)
        else:
            # Orb fallback – elegant radial gradient
            orb_r = int(fw * 0.22 * self._scale)
            orb_grad = QRadialGradient(cx, cy, orb_r)
            orb_grad.setColorAt(0.0, QColor(self._glow_r, self._glow_g, self._glow_b, min(255, int(self._halo * 1.5))))
            orb_grad.setColorAt(0.5, QColor(self._glow_r // 3, self._glow_g // 3, self._glow_b // 3, min(200, int(self._halo * 0.9))))
            orb_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(orb_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - orb_r, cy - orb_r, orb_r * 2, orb_r * 2))

            # Core text
            p.setPen(QPen(QColor(self._glow_r, self._glow_g, self._glow_b, min(255, int(self._halo * 2))), 1))
            p.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
            p.drawText(QRectF(cx - 80, cy - 14, 160, 28),
                       Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")

        # ═══════════════════════════════════════════════
        # LAYER 9: Particle nebula (around core, never ON core)
        # ═══════════════════════════════════════════════
        for pt in self._particles:
            # cull particles inside core
            dx, dy = pt[0] - cx, pt[1] - cy
            if math.sqrt(dx*dx + dy*dy) < r_core * 0.95:
                continue
            a = max(0, min(255, int(pt[4] * 200)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(self._glow_r, self._glow_g, self._glow_b, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), pt[5], pt[5])

        # ═══════════════════════════════════════════════
        # LAYER 10: Status text & waveform
        # ═══════════════════════════════════════════════
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "⊘  MUTED",     qcol(C.MUTED_C)
        elif self.speaking:
            sym = "◉" if self._blink else "◎"
            txt, col = f"{sym}  SPEAKING",  qcol(C.SPEAK_PRI)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.THINK_PRI)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.THINK_SEC)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  LISTENING",  qcol(C.LISTEN_PRI)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.IDLE_PRI)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 22), Qt.AlignmentFlag.AlignCenter, txt)

        # ── Waveform visualiser (ambient audio bars) ──
        wy = sy + 26
        N, bw = 42, 6
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt = 2
                cl  = qcol(C.MUTED_C, 60)
            elif self.speaking:
                hgt = random.randint(3, 22)
                intensity = min(255, 80 + hgt * 8)
                cl  = QColor(self._glow_r, self._glow_g, self._glow_b, intensity)
            elif self.state in ("THINKING", "PROCESSING"):
                hgt = int(3 + 4 * abs(math.sin(self._tick * 0.06 + i * 0.4)))
                cl  = QColor(self._glow_r, self._glow_g, self._glow_b, 100)
            else:
                hgt = int(2 + 2 * math.sin(self._tick * 0.05 + i * 0.5))
                cl  = QColor(self._glow_r, self._glow_g, self._glow_b, 50)
            p.fillRect(QRectF(wx0 + i * bw, wy + 22 - hgt, bw - 2, hgt), cl)

    # ─── Wireware Visualiser ─────────────────────────
    def _draw_wireware(self, p: QPainter, cx: float, cy: float, fw: float, r_core: float):
        """Draw a rotating wireware mesh around the core – stays OUTSIDE core bounds."""
        wire_zone_inner = r_core * 1.25  # inner edge of wireware zone
        wire_zone_outer = fw * 0.44      # outer edge

        wire_a = max(20, min(180, int(self._halo * 0.55)))

        for ring_idx, (r_frac_inner, r_frac_outer, seg_count) in enumerate([
            (0.58, 0.68, 6),   # outer wire ring
            (0.45, 0.54, 8),   # middle wire ring
            (0.35, 0.42, 10),  # inner wire ring
        ]):
            r_in  = fw * r_frac_inner * 0.5
            r_out = fw * r_frac_outer * 0.5

            # Ensure wireware stays outside core
            r_in  = max(r_in, wire_zone_inner)

            base_angle = self._wire_angles[ring_idx]
            seg_arc = 360 / seg_count

            alpha = max(10, int(wire_a * (0.9 - ring_idx * 0.2)))
            col = QColor(self._glow_r, self._glow_g, self._glow_b, alpha)
            p.setPen(QPen(col, 1.0 - ring_idx * 0.15))
            p.setBrush(Qt.BrushStyle.NoBrush)

            for s in range(seg_count):
                ang_start = math.radians(base_angle + s * seg_arc)
                ang_end   = math.radians(base_angle + s * seg_arc + seg_arc * 0.65)

                # Draw segment: two radial lines + two arcs
                x1i = cx + r_in  * math.cos(ang_start)
                y1i = cy - r_in  * math.sin(ang_start)
                x1o = cx + r_out * math.cos(ang_start)
                y1o = cy - r_out * math.sin(ang_start)
                x2i = cx + r_in  * math.cos(ang_end)
                y2i = cy - r_in  * math.sin(ang_end)
                x2o = cx + r_out * math.cos(ang_end)
                y2o = cy - r_out * math.sin(ang_end)

                # Radial spokes
                p.drawLine(QPointF(x1i, y1i), QPointF(x1o, y1o))
                p.drawLine(QPointF(x2i, y2i), QPointF(x2o, y2o))

                # Arc segments (inner and outer)
                arc_span_deg = seg_arc * 0.65
                arc_start_deg = -(base_angle + s * seg_arc)  # negate for Qt's coord system

                rect_in  = QRectF(cx - r_in, cy - r_in, r_in * 2, r_in * 2)
                rect_out = QRectF(cx - r_out, cy - r_out, r_out * 2, r_out * 2)
                p.drawArc(rect_in, int(arc_start_deg * 16), int(-arc_span_deg * 16))
                p.drawArc(rect_out, int(arc_start_deg * 16), int(-arc_span_deg * 16))

                # Cross-wire inside segments (diagonal structure)
                mid_ang = (ang_start + ang_end) / 2
                xmi = cx + r_in  * math.cos(mid_ang)
                ymi = cy - r_in  * math.sin(mid_ang)
                xmo = cx + r_out * math.cos(mid_ang)
                ymo = cy - r_out * math.sin(mid_ang)

                faint_col = QColor(self._glow_r, self._glow_g, self._glow_b, alpha // 3)
                p.setPen(QPen(faint_col, 0.5))
                p.drawLine(QPointF(x1i, y1i), QPointF(xmo, ymo))
                p.drawLine(QPointF(x2i, y2i), QPointF(xmo, ymo))
                p.setPen(QPen(col, 1.0 - ring_idx * 0.15))

    # ─── Orbital Data Rings ──────────────────────────
    def _draw_orbital_rings(self, p: QPainter, cx: float, cy: float, fw: float, r_core: float):
        """Spinning tactical data arcs – orbit around core without overlapping it."""
        configs = [
            (0.47, 2.5, 90, 45),   # outermost
            (0.42, 2.0, 65, 35),
            (0.37, 1.5, 50, 28),
            (0.32, 1.0, 38, 22),   # innermost – but still outside core
        ]
        for idx, (r_frac, width, arc_len, gap) in enumerate(configs):
            ring_r = fw * r_frac
            # Safety: ensure ring doesn't overlap core
            if ring_r < r_core * 1.15:
                continue
            base = self._orbit_angles[idx]
            a_val = max(15, min(200, int(self._halo * (0.8 - idx * 0.12))))
            col = QColor(self._glow_r, self._glow_g, self._glow_b, a_val)
            p.setPen(QPen(col, width))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            angle = base
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_len * 16))
                angle += arc_len + gap

        # Accent orbit: secondary color, thin, fast
        accent_r = fw * 0.44
        accent_a = max(20, min(150, int(self._halo * 0.5)))
        _, sec_hex, _ = self._ambient_colors()
        sc = qcol(sec_hex, accent_a)
        p.setPen(QPen(sc, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        accent_rect = QRectF(cx - accent_r, cy - accent_r, accent_r * 2, accent_r * 2)
        p.drawArc(accent_rect, int(self._orbit_angles[0] * 16 + 180 * 16), int(45 * 16))

    # ─── Scan Sweeps ─────────────────────────────────
    def _draw_scan_sweeps(self, p: QPainter, cx: float, cy: float, fw: float, r_core: float):
        """Rotating scan lines that sweep around the outer zone."""
        sr = fw * 0.49
        sweep_extent = 60 if self.speaking else 38

        # Primary sweep
        sa = min(200, int(self._halo * 1.2))
        sweep_col = QColor(self._glow_r, self._glow_g, self._glow_b, sa)
        p.setPen(QPen(sweep_col, 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.drawArc(srect, int(self._scan * 16), int(sweep_extent * 16))

        # Secondary sweep (accent color, opposing direction)
        _, sec_hex, _ = self._ambient_colors()
        p.setPen(QPen(qcol(sec_hex, sa // 3), 1.5))
        p.drawArc(srect, int(self._scan2 * 16), int(sweep_extent * 16))

class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0–100
        self._text  = "--"
        self._hovered = False
        self.setFixedHeight(40)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def enterEvent(self, e):
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Draw glass-like background card
        bg_opacity = 35 if self._hovered else 20
        bg_col = QColor(10, 22, 38, bg_opacity)
        p.setBrush(QBrush(bg_col))
        border_opacity = 80 if self._hovered else 40
        b_col = QColor(self._color)
        p.setPen(QPen(QColor(b_col.red(), b_col.green(), b_col.blue(), border_opacity), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        # Draw progress bar track
        bar_h   = 4
        bar_y   = H - bar_h - 6
        bar_w   = W - 16
        bar_x   = 8
        fill_w  = int(bar_w * self._value / 100)

        # Track background
        p.setBrush(QBrush(QColor(6, 12, 20, 200)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        # Dynamic bar color based on percentage
        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            # Draw glow under the fill
            p.setBrush(QBrush(QColor(bar_col.red(), bar_col.green(), bar_col.blue(), 180)))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)
            
            # Draw light reflection dot at the end of progress
            if fill_w > 4:
                p.setBrush(QBrush(QColor(255, 255, 255, 230)))
                p.drawEllipse(QRectF(bar_x + fill_w - 3, bar_y - 1, 4, 4))

        # Text labels
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_MED if self._hovered else C.TEXT_DIM), 1))
        p.drawText(QRectF(10, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 10, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)
        
        # Tech decoration lines (small diagnostic ticks below bar)
        p.setPen(QPen(QColor(bar_col.red(), bar_col.green(), bar_col.blue(), 30), 0.5))
        for tick_idx in range(6):
            tx = bar_x + (bar_w // 5) * tick_idx
            p.drawLine(QPointF(tx, bar_y + bar_h + 1), QPointF(tx, bar_y + bar_h + 3))

class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(4, 9, 18, 100);
                color: {C.TEXT};
                border: 1px solid rgba(0, 229, 255, 30);
                border-radius: 6px;
                padding: 6px;
                selection-background-color: rgba(0, 229, 255, 40);
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 2px 2px 2px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(0, 229, 255, 60);
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 229, 255, 120);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
                border: none;
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):    self._tag = "you"
        elif tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("file:"):   self._tag = "file"
        elif "err" in tl:              self._tag = "err"
        else:                          self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol(C.PRI),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys":  qcol(C.ACC2),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for JARVIS", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        # Glassmorphic background
        if z._current_file:
            bg_col = QColor(0, 230, 118, 15)  # slight green glow
            border_col = qcol(C.GREEN, 180)
        elif z._drag_over:
            bg_col = QColor(0, 229, 255, 30)  # active cyan glow
            border_col = qcol(C.PRI, 230)
        elif z._hovering:
            bg_col = QColor(0, 229, 255, 12)  # subtle hover cyan glow
            border_col = qcol(C.BORDER_B, 200)
        else:
            bg_col = QColor(8, 16, 28, 70)  # idle glass
            border_col = qcol(C.BORDER, 140)

        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        # Dash border
        pen = QPen(border_col, 1.2, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        # Sci-fi corner brackets in the drop zone
        if z._hovering or z._drag_over:
            p.setPen(QPen(border_col, 1.2))
            bl = 6
            # Top-Left
            p.drawLine(QPointF(pad+1, pad+1), QPointF(pad+1+bl, pad+1))
            p.drawLine(QPointF(pad+1, pad+1), QPointF(pad+1, pad+1+bl))
            # Bottom-Right
            p.drawLine(QPointF(W-pad-1, H-pad-1), QPointF(W-pad-1-bl, H-pad-1))
            p.drawLine(QPointF(W-pad-1, H-pad-1), QPointF(W-pad-1, H-pad-1-bl))

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
        # Draw tech upload icon
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 2))
        p.drawLine(QPointF(cx - 6, cy - 8), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 6, cy - 8), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 12, cy + 5), QPointF(cx + 12, cy + 5))
        
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT if hover else C.TEXT_MED), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "DROP FILE  or  CLICK TO BROWSE")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, cy + 26, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⚡")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 10, W, 16), Qt.AlignmentFlag.AlignCenter, "SYS LINK: READY TO LOAD")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 12, True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.", 8, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: rgba(0, 229, 255, 20); border: none; height: 1px;"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 7, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = GlassLineEdit(accent_color=C.PRI)
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 9))
        self._key_input.setFixedHeight(30)
        layout.addWidget(self._key_input)
        layout.addSpacing(6)

        layout.addWidget(_lbl("OPENROUTER API KEY", 7, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._or_input = GlassLineEdit(accent_color=C.ACC2)
        self._or_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_input.setPlaceholderText("sk-or-…")
        self._or_input.setFont(QFont("Courier New", 9))
        self._or_input.setFixedHeight(30)
        layout.addWidget(self._or_input)

        layout.addSpacing(8)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background: rgba(0, 229, 255, 20); border: none; height: 1px;"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 7, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 7, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(10)

        init_btn = GlassButton("▸  INITIALISE SYSTEMS", color=C.PRI)
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":C.PRI, "mac":C.ACC2, "linux":C.GREEN}
        for k, btn in self._os_btns.items():
            if k == key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba({qcol(pal[k]).red()}, {qcol(pal[k]).green()}, {qcol(pal[k]).blue()}, 40);
                        color: {pal[k]};
                        border: 1px solid {pal[k]};
                        border-radius: 4px;
                        font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(8, 16, 28, 80);
                        color: {C.TEXT_DIM};
                        border: 1px solid rgba(0, 229, 255, 30);
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        color: {C.TEXT};
                        border: 1px solid rgba(0, 229, 255, 70);
                    }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        or_key = self._or_input.text().strip()
        if not key:
            self._key_input.set_error(True)
            return
        if not or_key:
            self._or_input.set_error(True)
            return
        self.done.emit(key, or_key, self._sel_os)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        rect = QRectF(1, 1, W - 2, H - 2)
        
        # Frosted glass background
        bg_grad = QLinearGradient(0, 0, W, H)
        bg_grad.setColorAt(0.0, QColor(8, 18, 30, 220))
        bg_grad.setColorAt(1.0, QColor(3, 6, 12, 248))
        p.setBrush(QBrush(bg_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 8, 8)
        
        # Tech dots grid overlay
        p.setPen(QPen(QColor(0, 229, 255, 12), 1))
        for x in range(15, W, 20):
            for y in range(15, H, 20):
                p.drawPoint(x, y)
                
        # Neon cyan border
        p.setPen(QPen(QColor(C.PRI), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 8, 8)
        
        # Tech brackets on corners
        bl = 24
        p.setPen(QPen(QColor(C.PRI_DIM), 2))
        p.drawLine(QPointF(2, 2), QPointF(2 + bl, 2))
        p.drawLine(QPointF(2, 2), QPointF(2, 2 + bl))
        p.drawLine(QPointF(W - 2, 2), QPointF(W - 2 - bl, 2))
        p.drawLine(QPointF(W - 2, 2), QPointF(W - 2, 2 + bl))
        p.drawLine(QPointF(2, H - 2), QPointF(2 + bl, H - 2))
        p.drawLine(QPointF(2, H - 2), QPointF(2, H - 2 - bl))
        p.drawLine(QPointF(W - 2, H - 2), QPointF(W - 2 - bl, H - 2))
        p.drawLine(QPointF(W - 2, H - 2), QPointF(W - 2, H - 2 - bl))


class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — MARK XXXIX")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self._muted           = False
        self._current_file: str | None = None

        central = SpaceBackgroundWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metrik güncelleme timer'ı
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            cw = self.centralWidget()
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )

    def _update_metrics(self):
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")


    def _build_header(self) -> QWidget:
        w = GlassPanel(border_color=C.BORDER_B, corner_brackets=True, grid_overlay=False)
        w.setFixedHeight(54)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_badge("MARK XXXIX", C.PRI_DIM))
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        title = QLabel("J.A.R.V.I.S")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 17, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(title)
        sub = QLabel("Just A Rather Very Intelligent System")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Courier New", 7))
        sub.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        mid.addWidget(sub)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        w = GlassPanel(border_color=C.BORDER, corner_brackets=True, grid_overlay=True)
        w.setFixedWidth(_LEFT_W)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 12, 8, 12)
        lay.setSpacing(6)

        # High-tech divider section header
        lay.addWidget(TechHeader("SYS MONITOR"))
        lay.addSpacing(4)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(6)

        # OS Information block redesigned as tech card
        info_panel = QFrame()
        info_panel.setStyleSheet(
            "background: rgba(8, 16, 28, 140); border: 1px solid rgba(0, 229, 255, 25); border-radius: 5px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(8, 6, 8, 6)
        ip_lay.setSpacing(4)

        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addStretch()

        # Custom high-tech status badges with flashing indicators
        self._badge_core = GlassStatusBadge("AI CORE", "ACTIVE", C.GREEN)
        self._badge_sec  = GlassStatusBadge("SEC STATUS", "CLEARED", C.PRI)
        self._badge_link = GlassStatusBadge("COMM LINK", "ESTABLISHED", C.ACC2)
        
        lay.addWidget(self._badge_core)
        lay.addWidget(self._badge_sec)
        lay.addWidget(self._badge_link)

        return w
    def _build_right_panel(self) -> QWidget:
        w = GlassPanel(border_color=C.BORDER, corner_brackets=True, grid_overlay=True)
        w.setFixedWidth(_RIGHT_W)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 12, 8, 12)
        lay.setSpacing(6)

        # ── Section 1: Holographic Log Terminal ──
        lay.addWidget(TechHeader("ACTIVITY LOG"))
        lay.addSpacing(2)

        # Log Terminal Container
        log_term = QFrame()
        log_term.setStyleSheet(
            "background: transparent; border: 1px solid rgba(0, 229, 255, 30); border-radius: 6px;"
        )
        lt_lay = QVBoxLayout(log_term)
        lt_lay.setContentsMargins(0, 0, 0, 0)
        lt_lay.setSpacing(0)

        # Add LIVE status terminal header
        self._term_hdr = LogTerminalHeader()
        lt_lay.addWidget(self._term_hdr)

        self._log = LogWidget()
        # remove border from LogWidget since container has a border
        self._log.setStyleSheet(self._log.styleSheet() + " QTextEdit { border: none; border-radius: 0px; }")
        lt_lay.addWidget(self._log)
        
        lay.addWidget(log_term, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: rgba(0, 229, 255, 20); border: none; height: 1px; margin: 2px 0;")
        lay.addWidget(sep)

        # ── Section 2: Scanning Bay ──
        lay.addWidget(TechHeader("FILE SCANNERS"))
        lay.addSpacing(2)
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: rgba(0, 229, 255, 20); border: none; height: 1px; margin: 2px 0;")
        lay.addWidget(sep2)

        # ── Section 3: Input & Systems Grid ──
        lay.addWidget(TechHeader("SYSTEM COMMANDS"))
        lay.addSpacing(2)
        lay.addLayout(self._build_input_row())

        # Grid-like action buttons side-by-side
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._mute_btn = GlassButton("🎙  MIC ACTIVE", color=C.GREEN)
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        btn_row.addWidget(self._mute_btn, stretch=1)

        fs_btn = GlassButton("⛶  FULLSCREEN", color=C.PRI)
        fs_btn.setFixedHeight(30)
        fs_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        fs_btn.clicked.connect(self._toggle_fullscreen)
        btn_row.addWidget(fs_btn, stretch=1)
        
        lay.addLayout(btn_row)

        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        
        # Terminal-style prefix label
        prefix = QLabel("SYS>")
        prefix.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        prefix.setStyleSheet(f"color: {C.PRI}; background: transparent; padding-left: 2px;")
        row.addWidget(prefix)

        self._input = GlassLineEdit(accent_color=C.PRI)
        self._input.setPlaceholderText("Type command...")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(30)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input, stretch=1)

        send = GlassButton("▸", color=C.PRI)
        send.setFixedSize(30, 30)
        send.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_footer(self) -> QWidget:
        w = GlassPanel(border_color=C.BORDER, corner_brackets=False, grid_overlay=False)
        w.setFixedHeight(26)
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F4] Mute  ·  [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl("FatihMakes Industries  ·  MARK XXXIX  ·  CLASSIFIED"))
        lay.addStretch()
        lay.addWidget(_fl("© STARK INDUSTRIES", C.PRI_DIM))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell JARVIS what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MIC MUTED")
            self._mute_btn._color = C.MUTED_C
        else:
            self._mute_btn.setText("🎙  MIC ACTIVE")
            self._mute_btn._color = C.GREEN
        self._mute_btn.update()

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return (bool(d.get("gemini_api_key")) and
                    bool(d.get("openrouter_api_key")) and
                    bool(d.get("os_system")))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 430
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    # Change signature:
    def _on_setup_done(self, key: str, or_key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(
            json.dumps({
                "gemini_api_key":    key,
                "openrouter_api_key": or_key,
                "os_system":         os_name,
            }, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. JARVIS online.")

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")