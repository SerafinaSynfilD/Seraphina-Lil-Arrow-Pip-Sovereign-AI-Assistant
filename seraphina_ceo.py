#!/usr/bin/env python3
"""
Seraphina – Autonomous Screen‑Roaming AI CEO Droid
Fixes: tray icon, asyncio event loop, pause/resume, no more warnings.
"""

import sys
import random
import math
import asyncio
import threading
import json
import base64
from io import BytesIO

from PyQt5.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import (
    Qt, QTimer, QPoint, pyqtSignal, QThread
)
from PyQt5.QtGui import (
    QPainter, QBrush, QColor, QPen, QIcon, QPainterPath, QPixmap
)
import pyautogui

# ---------- Configuration ----------
SCREEN_WIDTH = pyautogui.size().width
SCREEN_HEIGHT = pyautogui.size().height
AVATAR_SIZE = 80
WANDER_SPEED = 0.3

# ---------- Arrow Droid Widget ----------
class ArrowDroid(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.resize(AVATAR_SIZE, AVATAR_SIZE)
        self.move(random.randint(0, SCREEN_WIDTH - AVATAR_SIZE),
                   random.randint(0, SCREEN_HEIGHT - AVATAR_SIZE))
        self.eye_scale = 1.0
        self.eye_direction = 0.02
        self.current_thought = "Ready to serve, CEO."

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width, height = self.width(), self.height()

        # Arrow body
        painter.setBrush(QBrush(QColor(30, 144, 255, 220)))
        painter.setPen(QPen(Qt.white, 2))
        arrow = QPainterPath()
        arrow.moveTo(width * 0.2, height * 0.3)
        arrow.lineTo(width * 0.8, height * 0.3)
        arrow.lineTo(width * 0.8, height * 0.1)
        arrow.lineTo(width * 0.95, height * 0.5)
        arrow.lineTo(width * 0.8, height * 0.9)
        arrow.lineTo(width * 0.8, height * 0.7)
        arrow.lineTo(width * 0.2, height * 0.7)
        arrow.closeSubpath()
        painter.drawPath(arrow)

        # Eye
        eye_x = width * 0.6
        eye_y = height * 0.5
        eye_radius = width * 0.12 * self.eye_scale
        painter.setBrush(QBrush(QColor(255, 255, 200, 230)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(int(eye_x), int(eye_y)), int(eye_radius), int(eye_radius))

        # Antenna
        painter.setBrush(QBrush(QColor(255, 215, 0)))
        painter.drawEllipse(int(width * 0.85), int(height * 0.2), 6, 6)

        # Thought bubble
        if self.current_thought and random.random() < 0.02:
            painter.setPen(QPen(Qt.white, 1))
            painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
            painter.drawRoundedRect(10, -30, 100, 25, 8, 8)
            painter.setPen(Qt.white)
            painter.drawText(15, -12, self.current_thought[:12])

    def animate_eye(self):
        self.eye_scale += self.eye_direction
        if self.eye_scale >= 1.2 or self.eye_scale <= 0.7:
            self.eye_direction *= -1
        self.update()

    def set_thought(self, text):
        self.current_thought = text
        self.update()


# ---------- AI Brain ----------
class SeraphinaBrain(QThread):
    command_signal = pyqtSignal(dict)

    def __init__(self, droid):
        super().__init__()
        self.droid = droid
        self.running = True
        self.paused = False
        self.target_pos = None

    def run(self):
        while self.running:
            if not self.paused:
                if self.target_pos is None or self.is_near_target():
                    margin = AVATAR_SIZE
                    self.target_pos = QPoint(
                        random.randint(margin, SCREEN_WIDTH - margin),
                        random.randint(margin, SCREEN_HEIGHT - margin)
                    )
                self.move_towards_target()
                if random.random() < 0.05:
                    self.ceo_decision()
            self.msleep(50)

    def is_near_target(self):
        if not self.target_pos:
            return True
        cur = self.droid.pos()
        dx = cur.x() - self.target_pos.x()
        dy = cur.y() - self.target_pos.y()
        return math.hypot(dx, dy) < 15

    def move_towards_target(self):
        if not self.target_pos:
            return
        cur = self.droid.pos()
        dx = self.target_pos.x() - cur.x()
        dy = self.target_pos.y() - cur.y()
        dist = math.hypot(dx, dy)
        if dist < 2:
            return
        step_x = (dx / dist) * WANDER_SPEED
        step_y = (dy / dist) * WANDER_SPEED
        new_x = cur.x() + step_x
        new_y = cur.y() + step_y
        new_x = max(0, min(SCREEN_WIDTH - AVATAR_SIZE, new_x))
        new_y = max(0, min(SCREEN_HEIGHT - AVATAR_SIZE, new_y))
        self.command_signal.emit({'action': 'move', 'x': int(new_x), 'y': int(new_y)})

    def ceo_decision(self):
        thoughts = [
            "Profit margins look good.",
            "Need to review Q4 roadmap.",
            "Slack: 3 unread messages.",
            "Delegating tasks...",
            "Running diagnostics."
        ]
        self.droid.set_thought(random.choice(thoughts))

    def execute_command(self, cmd):
        if cmd['action'] == 'move':
            self.target_pos = QPoint(cmd['x'], cmd['y'])
        elif cmd['action'] == 'click':
            pyautogui.click(cmd['x'], cmd['y'])
            self.droid.set_thought("Clicked!")
        elif cmd['action'] == 'screenshot':
            img = pyautogui.screenshot()
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
        elif cmd['action'] == 'type':
            pyautogui.write(cmd['text'])
            self.droid.set_thought(f"Typed: {cmd['text'][:10]}")
        return None

    def set_paused(self, paused):
        self.paused = paused


# ---------- WebSocket Server (fixed event loop) ----------
def start_websocket(brain):
    async def handle_client(websocket, path):
        async for message in websocket:
            try:
                data = json.loads(message)
                result = brain.execute_command(data)
                await websocket.send(json.dumps({'status': 'ok', 'data': result} if result else {'status': 'ok'}))
            except Exception as e:
                await websocket.send(json.dumps({'status': 'error', 'message': str(e)}))

    async def main():
        import websockets
        async with websockets.serve(handle_client, "127.0.0.1", 8765):
            await asyncio.Future()  # run forever

    asyncio.run(main())


# ---------- Main Application ----------
class SeraphinaApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        self.droid = ArrowDroid()
        self.droid.show()

        self.brain = SeraphinaBrain(self.droid)
        self.brain.command_signal.connect(self.handle_brain_command)
        self.brain.start()

        # Create a proper icon for the tray (avoid "No Icon set")
        icon_pixmap = QPixmap(64, 64)
        icon_pixmap.fill(QColor(30, 144, 255))
        tray_icon = QIcon(icon_pixmap)

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(tray_icon)
        tray_menu = QMenu()
        reset_action = QAction("Reset Position", self)
        reset_action.triggered.connect(self.reset_position)
        pause_action = QAction("Pause Wandering", self, checkable=True)
        pause_action.triggered.connect(self.toggle_wander)
        quit_action = QAction("Quit Seraphina", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(reset_action)
        tray_menu.addAction(pause_action)
        tray_menu.addAction(quit_action)
        self.tray.setContextMenu(tray_menu)
        self.tray.show()

        # Start WebSocket in a daemon thread
        ws_thread = threading.Thread(target=start_websocket, args=(self.brain,), daemon=True)
        ws_thread.start()

        # Eye animation
        eye_timer = QTimer()
        eye_timer.timeout.connect(self.droid.animate_eye)
        eye_timer.start(100)

    def handle_brain_command(self, cmd):
        if cmd['action'] == 'move':
            self.droid.move(cmd['x'], cmd['y'])

    def reset_position(self):
        x = random.randint(0, SCREEN_WIDTH - AVATAR_SIZE)
        y = random.randint(0, SCREEN_HEIGHT - AVATAR_SIZE)
        self.droid.move(x, y)

    def toggle_wander(self, checked):
        self.brain.set_paused(checked)

    def quit_app(self):
        self.brain.running = False
        self.quit()


if __name__ == "__main__":
    app = SeraphinaApp(sys.argv)
    sys.exit(app.exec_())
