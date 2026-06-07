from __future__ import annotations

import time

from OpenGL import GL
from pyopengltk import OpenGLFrame

import live2d.v3 as live2d

from .model_loader import CubismModelInfo


_LIVE2D_INITIALIZED = False


class Live2DOpenGLFrame(OpenGLFrame):
    def __init__(self, master, model_info: CubismModelInfo, **kwargs):
        super().__init__(master, **kwargs)
        self.model_info = model_info
        self.model = None
        self.animate = 33
        self.is_speaking = False
        self.drag_x = 0.0
        self.drag_y = 0.0
        self.scale = 0.42
        self.offset_y = -0.16
        self._last_idle_restart = 0.0
        self.pending_motion: str | None = None
        self.model_lipsync_enabled = False

    def initgl(self):
        global _LIVE2D_INITIALIZED

        GL.glClearColor(0.055, 0.082, 0.133, 1.0)

        if not _LIVE2D_INITIALIZED:
            live2d.setLogEnable(False)
            live2d.init()
            live2d.glewInit()
            _LIVE2D_INITIALIZED = True

        if self.model is None:
            self.model = live2d.LAppModel()
            self.model.LoadModelJson(str(self.model_info.model_json_path))
            self.model.SetAutoBlinkEnable(True)
            self.model.SetAutoBreathEnable(True)
            self.model.SetScale(self.scale)
            self.model.SetOffset(0.0, self.offset_y)
            self.start_idle_motion(force=True)

        self.model.Resize(self.width, self.height)

    def redraw(self):
        live2d.clearBuffer()
        if self.model is None:
            return

        self.model.Drag(self.drag_x, self.drag_y)
        self.play_pending_motion()
        self.start_idle_motion()
        self.model.Update()
        self.model.Draw()

    def set_speaking(self, speaking: bool):
        self.is_speaking = speaking

    def set_scale_value(self, scale: float):
        self.scale = scale
        if self.model is not None:
            try:
                self.model.SetScale(self.scale)
            except Exception:
                pass

    def set_offset_y(self, offset_y: float):
        self.offset_y = offset_y
        if self.model is not None:
            try:
                self.model.SetOffset(0.0, self.offset_y)
            except Exception:
                pass

    def set_mode(self, mode: str):
        if self.model is None:
            return

        if mode == 'listening':
            self.drag_x = 0.18
            self.drag_y = -0.08
        elif mode == 'thinking':
            self.drag_x = -0.2
            self.drag_y = 0.04
        else:
            self.drag_x = 0.0
            self.drag_y = 0.0

    def queue_motion(self, motion_name: str):
        self.pending_motion = motion_name

    def play_pending_motion(self):
        if self.model is None or not self.pending_motion:
            return

        motion_name = self.pending_motion
        self.pending_motion = None
        motion_map = {
            'happy_bounce': 'Tap',
            'tap_body': 'Tap@Body',
            'flick': 'Flick',
            'flick_down': 'FlickDown',
            'thinking': 'Flick',
            'idle': 'Idle',
            'speaking': 'Idle',
            'listening': 'Idle',
        }
        target_group = motion_map.get(motion_name, 'Idle')
        try:
            self.model.StartRandomMotion(target_group, live2d.MotionPriority.NORMAL)
        except Exception:
            pass

    def start_idle_motion(self, force: bool = False):
        if self.model is None:
            return
        now = time.time()
        if not force and now - self._last_idle_restart < 2.5:
            return
        try:
            if force or self.model.IsMotionFinished():
                self.model.StartRandomMotion(live2d.MotionGroup.IDLE, live2d.MotionPriority.IDLE)
                self._last_idle_restart = now
        except Exception:
            pass


def dispose_live2d():
    global _LIVE2D_INITIALIZED
    if not _LIVE2D_INITIALIZED:
        return
    try:
        live2d.dispose()
    except Exception:
        pass
    _LIVE2D_INITIALIZED = False
