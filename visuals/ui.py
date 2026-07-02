from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from mahiru.assistant import process_user_message
from mahiru.companion import companion
from mahiru.online_providers import get_runtime_status, sync_runtime_preferences
from mahiru.online_settings import MODEL_CATALOG, PROVIDER_LABELS, online_settings
from mahiru.response_types import MahiruReply
from mahiru.tts_settings import TTS_ENGINES, tts_settings
from mahiru.voice import cleanup_old_temp_files

from .avatar_state import AvatarState, build_avatar_state
from .live2d_frame import Live2DOpenGLFrame, dispose_live2d
from .model_loader import load_first_cubism_model

class MahiruDesktopApp:
    def __init__(self):
        cleanup_old_temp_files()
        self.root = tk.Tk()
        self.root.title('Mahiru Desktop Companion')
        self.root.geometry('1120x760')
        self.root.minsize(980, 680)
        self.root.configure(bg='#121826')

        self.model_info = load_first_cubism_model()
        self.renderer_ready = True

        self.ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker_lock = threading.Lock()
        self.mic_enabled = False
        self.mic_thread: threading.Thread | None = None
        self.running = True
        self.assistant_busy = False
        self.voice_enabled = True
        self.voice_process: subprocess.Popen[str] | None = None
        self.voice_process_lock = threading.Lock()
        self.settings_window: tk.Toplevel | None = None
        self.speaking_animation_job: str | None = None
        self.speaking_face_frames = ['(*^_^*)', '(*o_^*)', '(*O_^*)', '(*o_^*)']
        self.speaking_face_index = 0

        self.status_var = tk.StringVar(value='Booting Mahiru UI...')
        self.mode_var = tk.StringVar(value='Idle')
        self.mood_var = tk.StringVar(value='Mood: neutral')
        self.expression_var = tk.StringVar(value='Expression: neutral')
        self.mic_var = tk.StringVar(value='Mic: OFF')
        self.renderer_var = tk.StringVar(value='Renderer: Cubism shell ready')
        self.model_var = tk.StringVar(value=self.build_model_summary())
        self.avatar_face_var = tk.StringVar(value='(*^_^*)')
        self.voice_var = tk.StringVar(value='Voice: ON')
        self.ai_provider_var = tk.StringVar(value='AI Provider: loading...')
        self.ai_model_var = tk.StringVar(value='AI Model: loading...')
        self.ai_fallback_var = tk.StringVar(value='Fallback Provider: loading...')
        self.ai_reason_var = tk.StringVar(value='Provider Status: loading...')

        self.build_layout()
        self.refresh_online_provider_labels()
        self.refresh_tts_label()
        self.apply_avatar_state(build_avatar_state('idle', is_renderer_ready=self.renderer_ready))
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        self.root.after(120, self.process_ui_queue)
        self.root.after(2500, self.refresh_companion_state)
        self.bootstrap_greeting()

    def build_layout(self):
        container = tk.Frame(self.root, bg='#121826')
        container.pack(fill='both', expand=True, padx=18, pady=18)

        container.grid_columnconfigure(0, weight=4)
        container.grid_columnconfigure(1, weight=4)
        container.grid_rowconfigure(0, weight=1)

        self.build_avatar_panel(container)
        self.build_chat_panel(container)

    def build_avatar_panel(self, parent: tk.Widget):
        panel = tk.Frame(parent, bg='#1A2233', bd=0, highlightthickness=1, highlightbackground='#28324A')
        panel.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        panel.grid_rowconfigure(3, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        tk.Label(panel, text='LIVE2D SHELL // TEMP MODEL', fg='#F3F7FF', bg='#1A2233', font=('Consolas', 16, 'bold')).grid(row=0, column=0, sticky='w', padx=18, pady=(18, 8))
        tk.Label(
            panel,
            text='Hiyori sample model detected. Mahiru now uses online AI Groq.',
            fg='#B8C4D9',
            bg='#1A2233',
            wraplength=420,
            justify='left',
            font=('Consolas', 10),
        ).grid(row=1, column=0, sticky='ew', padx=18)

        avatar_box = tk.Frame(panel, bg='#0E1522', highlightthickness=1, highlightbackground='#34405B')
        avatar_box.grid(row=2, column=0, sticky='nsew', padx=18, pady=18)
        avatar_box.grid_columnconfigure(0, weight=1)
        avatar_box.grid_rowconfigure(0, weight=1)

        self.live2d_frame = Live2DOpenGLFrame(avatar_box, self.model_info, width=560, height=660)
        self.live2d_frame.grid(row=0, column=0, padx=14, pady=(14, 8), sticky='nsew')

        self.avatar_face_label = tk.Label(
            avatar_box,
            textvariable=self.avatar_face_var,
            fg='#FCE8A8',
            bg='#0E1522',
            font=('Consolas', 24, 'bold'),
        )
        self.avatar_face_label.grid(row=1, column=0, pady=(0, 12))

        status_block = tk.Frame(panel, bg='#1A2233')
        status_block.grid(row=3, column=0, sticky='nsew', padx=18, pady=(0, 18))
        status_block.grid_columnconfigure(0, weight=1)

        for row_index, variable in enumerate([
            self.status_var, self.mode_var, self.mood_var, self.expression_var, self.mic_var, self.voice_var, self.ai_provider_var, self.ai_model_var, self.ai_fallback_var, self.ai_reason_var, self.renderer_var, self.model_var,
        ]):
            tk.Label(
                status_block,
                textvariable=variable,
                fg='#D7E2F2',
                bg='#1A2233',
                justify='left',
                anchor='w',
                wraplength=420,
                font=('Consolas', 10),
            ).grid(row=row_index, column=0, sticky='ew', pady=4)

    def build_chat_panel(self, parent: tk.Widget):
        panel = tk.Frame(parent, bg='#141D2C', bd=0, highlightthickness=1, highlightbackground='#28324A')
        panel.grid(row=0, column=1, sticky='nsew')
        panel.grid_rowconfigure(2, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        top_bar = tk.Frame(panel, bg='#141D2C')
        top_bar.grid(row=0, column=0, sticky='ew', padx=18, pady=(18, 10))
        top_bar.grid_columnconfigure(1, weight=1)

        tk.Label(top_bar, text='CHAT + MIC CONTROL', fg='#F3F7FF', bg='#141D2C', font=('Consolas', 16, 'bold')).grid(row=0, column=0, sticky='w')
        ttk.Button(top_bar, text='? Settings', command=self.open_settings_window).grid(row=0, column=1, sticky='e', padx=(12, 0))
        ttk.Button(top_bar, text='?? Toggle Mic', command=self.toggle_mic).grid(row=0, column=2, sticky='e', padx=(12, 0))

        tk.Label(
            panel,
            text='Type below or turn the mic on. Mahiru can reply through Cerebras or Groq, and the avatar reacts using expression + motion metadata.',
            fg='#B8C4D9',
            bg='#141D2C',
            wraplength=600,
            justify='left',
            font=('Consolas', 10),
        ).grid(row=1, column=0, sticky='ew', padx=18)

        transcript_frame = tk.Frame(panel, bg='#0E1522', highlightthickness=1, highlightbackground='#34405B')
        transcript_frame.grid(row=2, column=0, sticky='nsew', padx=18, pady=18)
        transcript_frame.grid_rowconfigure(0, weight=1)
        transcript_frame.grid_columnconfigure(0, weight=1)

        self.chat_text = tk.Text(
            transcript_frame,
            wrap='word',
            bg='#0E1522',
            fg='#EAF1FF',
            insertbackground='#EAF1FF',
            relief='flat',
            bd=0,
            padx=14,
            pady=14,
            font=('Consolas', 11),
        )
        self.chat_text.grid(row=0, column=0, sticky='nsew')
        self.chat_text.tag_configure('system', foreground='#8DA5D1')
        self.chat_text.tag_configure('user', foreground='#9BE7C4')
        self.chat_text.tag_configure('mahiru', foreground='#FFD6E7')
        self.chat_text.tag_configure('error', foreground='#FF9EA1')
        self.chat_text.config(state='disabled')

        scrollbar = ttk.Scrollbar(transcript_frame, orient='vertical', command=self.chat_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.chat_text.configure(yscrollcommand=scrollbar.set)

        bottom_bar = tk.Frame(panel, bg='#141D2C')
        bottom_bar.grid(row=3, column=0, sticky='ew', padx=18, pady=(0, 18))
        bottom_bar.grid_columnconfigure(0, weight=1)

        self.user_entry = tk.Entry(bottom_bar, bg='#0E1522', fg='#F3F7FF', insertbackground='#F3F7FF', relief='flat', font=('Consolas', 11))
        self.user_entry.grid(row=0, column=0, sticky='ew', ipady=10)
        self.user_entry.bind('<Return>', self.submit_text_message)
        ttk.Button(bottom_bar, text='?? Send', command=self.submit_text_message).grid(row=0, column=1, padx=(12, 0))

    def bootstrap_greeting(self):
        greeting = companion.build_startup_greeting()
        self.add_chat_line('SYSTEM', 'Mahiru desktop shell is ready. Cubism assets loaded.', 'system')
        self.add_chat_line('MAHIRU', greeting, 'mahiru')
        self.apply_avatar_state(build_avatar_state('idle', mood='happy', expression='happy', status_text='Model loaded and ready', is_mic_enabled=self.mic_enabled, is_renderer_ready=self.renderer_ready))
        self.live2d_frame.queue_motion('happy_bounce')

    def build_model_summary(self) -> str:
        motion_count = sum(len(entries) for entries in self.model_info.motion_groups.values())
        lip_sync = ', '.join(self.model_info.lip_sync_ids) if self.model_info.lip_sync_ids else 'none'
        return f'Model: {self.model_info.name} | motions: {motion_count} | params: {len(self.model_info.parameters)} | lip sync: {lip_sync}'

    def submit_text_message(self, _event=None):
        text = self.user_entry.get().strip()
        if not text:
            return
        self.user_entry.delete(0, 'end')
        self.handle_user_message(text, source='text')

    def handle_user_message(self, text: str, *, source: str):
        if not self.running:
            return
        self.assistant_busy = True
        self.add_chat_line('YOU', text, 'user')
        busy_label = 'Listening request from mic' if source == 'mic' else 'Processing typed request'
        self.apply_avatar_state(build_avatar_state('thinking', mood='thinking', expression='thinking', status_text=busy_label, is_mic_enabled=self.mic_enabled, is_renderer_ready=self.renderer_ready))
        self.live2d_frame.queue_motion('thinking')
        threading.Thread(target=self.process_message_worker, args=(text,), daemon=True).start()

    def process_message_worker(self, text: str):
        try:
            should_continue, reply = process_user_message(text)
            self.ui_queue.put(('assistant_response', (should_continue, reply, get_runtime_status())))
        except Exception as exc:
            print(f"ERROR in process_message_worker: {exc}")
            import traceback
            traceback.print_exc()
            self.ui_queue.put(('error', f'Message processing error: {exc}'))

    def process_ui_queue(self):
        # Process all events in the queue at once
        while True:
            try:
                event_name, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            if event_name == 'assistant_response':
                should_continue, reply, provider_status = payload
                self.refresh_online_provider_labels(provider_status)
                if reply.text:
                    self.add_chat_line('MAHIRU', reply.text, 'mahiru')
                    self.apply_avatar_state(build_avatar_state('speaking', mood=reply.mood, expression=reply.expression, status_text=reply.status_text or 'Speaking right now', is_mic_enabled=self.mic_enabled, is_renderer_ready=self.renderer_ready))
                    self.live2d_frame.queue_motion(reply.motion)
                    self.run_speech_async(reply)
                else:
                    self.assistant_busy = False
                    self.apply_avatar_state(build_avatar_state('idle', is_mic_enabled=self.mic_enabled, is_renderer_ready=self.renderer_ready))
                if not should_continue:
                    self.add_chat_line('SYSTEM', 'Mahiru received a sleep/exit request. The app will stay open until you close it manually.', 'system')
            elif event_name == 'speech_done':
                self.assistant_busy = False
                self.stop_speaking_animation()
                self.apply_avatar_state(build_avatar_state('idle', is_mic_enabled=self.mic_enabled, is_renderer_ready=self.renderer_ready))
            elif event_name == 'mic_heard':
                self.handle_user_message(payload, source='mic')
            elif event_name == 'mic_idle':
                if self.mic_enabled:
                    self.apply_avatar_state(build_avatar_state('listening', mood='neutral', expression='neutral', status_text='Mic is on and waiting for you', is_mic_enabled=True, is_renderer_ready=self.renderer_ready))
            elif event_name == 'error':
                self.add_chat_line('SYSTEM', str(payload), 'error')
                self.apply_avatar_state(build_avatar_state('error', mood='concerned', expression='concerned', status_text=str(payload), is_mic_enabled=self.mic_enabled, is_renderer_ready=self.renderer_ready))

        # Only schedule next run if queue is not empty
        if self.running and not self.ui_queue.empty():
            self.root.after(100, self.process_ui_queue)

    def refresh_companion_state(self):
        if not self.running:
            return

        due_reminders = companion.consume_due_reminders()
        for reminder_text in due_reminders:
            self.add_chat_line('MAHIRU', reminder_text, 'mahiru')
            if not self.assistant_busy:
                reminder_reply = MahiruReply(
                    text=reminder_text,
                    expression='caring',
                    mood='caring',
                    motion='tap_body',
                    status_text='Delivering reminder',
                )
                self.assistant_busy = True
                self.apply_avatar_state(build_avatar_state('speaking', mood='caring', expression='caring', status_text='Delivering reminder', is_mic_enabled=self.mic_enabled, is_renderer_ready=self.renderer_ready))
                self.live2d_frame.queue_motion('tap_body')
                self.run_speech_async(reminder_reply)

        if not self.assistant_busy and not self.mic_enabled:
            mode, expression, status_text = companion.get_presence_state()
            self.apply_avatar_state(
                build_avatar_state(
                    mode,
                    mood=expression,
                    expression=expression,
                    status_text=status_text,
                    is_mic_enabled=False,
                    is_renderer_ready=self.renderer_ready,
                )
            )

        self.root.after(2500, self.refresh_companion_state)

    def run_speech_async(self, reply: MahiruReply):
        if not self.voice_enabled:
            self.assistant_busy = False
            self.apply_avatar_state(build_avatar_state('idle', mood=reply.mood, expression=reply.expression, status_text='Voice output is turned off', is_mic_enabled=self.mic_enabled, is_renderer_ready=self.renderer_ready))
            return

        self.start_speaking_animation(reply.expression)

        def worker():
            try:
                self.speak_through_voice_service(reply.text)
            except Exception as exc:
                self.ui_queue.put(('error', f'Voice error: {exc}'))
            finally:
                self.ui_queue.put(('speech_done', None))

        threading.Thread(target=worker, daemon=True).start()

    def ensure_voice_process(self) -> subprocess.Popen[str]:
        with self.voice_process_lock:
            if self.voice_process and self.voice_process.poll() is None:
                return self.voice_process

            self.voice_process = subprocess.Popen(
                [sys.executable, '-m', 'mahiru.voice_worker', '--service'],
                cwd=self.project_root(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding='utf-8',
                bufsize=1,
            )

            ready_line = self.voice_process.stdout.readline().strip() if self.voice_process.stdout else ''
            if not ready_line:
                raise RuntimeError('Voice service did not start correctly.')

            try:
                payload = json.loads(ready_line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f'Voice service returned an invalid startup response: {ready_line}') from exc

            if payload.get('status') != 'ready':
                raise RuntimeError(f"Voice service failed to initialize: {payload}")

            return self.voice_process

    def speak_through_voice_service(self, text: str):
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                process = self.ensure_voice_process()
                if process.stdin is None or process.stdout is None:
                    raise RuntimeError('Voice service streams are not available.')

                request_payload = json.dumps({"command": "speak", "text": text})
                process.stdin.write(request_payload + '\n')
                process.stdin.flush()

                response_line = process.stdout.readline().strip()
                if not response_line:
                    raise RuntimeError('Voice service stopped before sending a response.')

                response_payload = json.loads(response_line)
                if response_payload.get('status') == 'done':
                    return
                raise RuntimeError(response_payload.get('message') or 'Voice service failed to speak.')
            except Exception as exc:
                last_error = exc
                self.shutdown_voice_process()
        raise RuntimeError(str(last_error) if last_error else 'Voice service failed.')

    def shutdown_voice_process(self):
        with self.voice_process_lock:
            process = self.voice_process
            self.voice_process = None
            if process is None:
                return

            try:
                if process.poll() is None and process.stdin:
                    process.stdin.write(json.dumps({"command": "shutdown"}) + '\n')
                    process.stdin.flush()
            except Exception:
                pass

            try:
                process.wait(timeout=1.5)
            except Exception:
                try:
                    process.terminate()
                except Exception:
                    pass

    def toggle_mic(self):
        self.mic_enabled = not self.mic_enabled
        if self.mic_enabled:
            self.apply_avatar_state(build_avatar_state('listening', mood='neutral', expression='neutral', status_text='Mic is on and waiting for you', is_mic_enabled=True, is_renderer_ready=self.renderer_ready))
            self.start_mic_loop()
        else:
            self.apply_avatar_state(build_avatar_state('idle', is_mic_enabled=False, is_renderer_ready=self.renderer_ready))

    def start_mic_loop(self):
        if self.mic_thread and self.mic_thread.is_alive():
            return

        def mic_worker():
            while self.running and self.mic_enabled:
                if self.assistant_busy:
                    threading.Event().wait(0.25)
                    continue
                try:
                    from mahiru.listener import listen_to_you
                    heard_text = listen_to_you()
                except Exception as exc:
                    self.ui_queue.put(('error', f'Mic error: {exc}'))
                    break
                if not self.running or not self.mic_enabled:
                    break
                if heard_text:
                    self.ui_queue.put(('mic_heard', heard_text))
                else:
                    self.ui_queue.put(('mic_idle', None))

        self.mic_thread = threading.Thread(target=mic_worker, daemon=True)
        self.mic_thread.start()

    def apply_avatar_state(self, state: AvatarState):
        self.status_var.set(f'Status: {state.status_text}')
        self.mode_var.set(f'Mode: {state.mode.upper()}')
        self.mood_var.set(f'Mood: {state.mood}')
        self.expression_var.set(f'Expression: {state.expression}')
        self.mic_var.set(f"Mic: {'ON' if state.is_mic_enabled else 'OFF'}")
        self.renderer_var.set('Renderer: Live2D active' if state.is_renderer_ready else 'Renderer: preview shell active | Cubism runtime bridge pending')
        self.avatar_face_var.set(state.emoji)
        self.voice_var.set(f"Voice: {'ON' if self.voice_enabled else 'OFF'}")
        self.live2d_frame.set_mode(state.mode)
        self.live2d_frame.set_speaking(state.mode == 'speaking')

    def refresh_tts_label(self):
        engine_label = tts_settings.get_engine_label()
        self.voice_var.set(f"Voice: {'ON' if self.voice_enabled else 'OFF'} | {engine_label}")

    def refresh_online_provider_labels(self, provider_status=None):
        status = provider_status or get_runtime_status()
        primary_label = PROVIDER_LABELS.get(status.primary_provider, status.primary_provider.title())
        active_label = PROVIDER_LABELS.get(status.active_provider, status.active_provider.title())
        fallback_label = PROVIDER_LABELS.get(status.fallback_provider, status.fallback_provider.title())
        self.ai_provider_var.set(f'AI Provider: {active_label} (primary: {primary_label})')
        self.ai_model_var.set(f'AI Model: {status.active_model}')
        self.ai_fallback_var.set(f'Fallback Provider: {fallback_label}')
        self.ai_reason_var.set(f'Provider Status: {status.last_switch_reason}')

    def start_speaking_animation(self, expression: str):
        expression_frames = {
            'happy': ['(^_^)/', '(^o^)/', '(^_^)/', '(^-^)/'],
            'caring': ['(^-^*)', '(^o^*)', '(^-^*)', '(^_^*)'],
            'shy': ['(>_<*)', '(>o<*)', '(>_<*)', '(._.*)'],
            'playful': ['(*^o^*)', '(*O^*)', '(*^o^*)', '(^_~)'],
            'concerned': ['(;_;)', '(;o_;)', '(;_;)', '(._.)'],
            'thinking': ['(._. )', '(o_o )', '(._. )', '(-_- )'],
            'surprised': ['(o_O)!', '(O_O)!', '(o_O)!', '(0_0)!'],
            'sleepy': ['(-_-) zZ', '(-.-) zZ', '(-_-) zZ', '(~_~)'],
            'neutral': ['(*^_^*)', '(*o_^*)', '(*O_^*)', '(*o_^*)'],
        }
        self.speaking_face_frames = expression_frames.get(expression, expression_frames['neutral'])
        self.stop_speaking_animation()
        self.speaking_face_index = 0
        self._tick_speaking_animation()

    def _tick_speaking_animation(self):
        if not self.running or not self.assistant_busy:
            self.speaking_animation_job = None
            return
        frame = self.speaking_face_frames[self.speaking_face_index % len(self.speaking_face_frames)]
        self.avatar_face_var.set(frame)
        self.speaking_face_index += 1
        self.speaking_animation_job = self.root.after(120, self._tick_speaking_animation)

    def stop_speaking_animation(self):
        if self.speaking_animation_job is not None:
            try:
                self.root.after_cancel(self.speaking_animation_job)
            except Exception:
                pass
            self.speaking_animation_job = None

    def add_chat_line(self, speaker: str, text: str, tag: str):
        # Use after to schedule the UI update in the main thread
        self.root.after(0, lambda: self._add_chat_line_immediate(speaker, text, tag))

    def _add_chat_line_immediate(self, speaker: str, text: str, tag: str):
        self.chat_text.config(state='normal')
        self.chat_text.insert('end', f'[{speaker}] {text}\n\n', tag)
        self.chat_text.see('end')
        self.chat_text.config(state='disabled')

    def on_close(self):
        self.running = False
        self.mic_enabled = False
        self.assistant_busy = False
        self.stop_speaking_animation()
        self.shutdown_voice_process()
        self.live2d_frame.animate = 0
        cleanup_old_temp_files()
        self.root.after(50, self._finish_close)

    def _finish_close(self):
        try:
            dispose_live2d()
        finally:
            self.root.destroy()

    def open_settings_window(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        window = tk.Toplevel(self.root)
        window.title('Mahiru Settings')
        window.geometry('500x610')
        window.configure(bg='#141D2C')
        window.resizable(False, False)
        self.settings_window = window

        tk.Label(window, text='? MAHIRU SETTINGS', fg='#F3F7FF', bg='#141D2C', font=('Consolas', 16, 'bold')).pack(anchor='w', padx=18, pady=(18, 10))
        tk.Label(window, text='Use these controls to adjust the temporary model, voice output, and the online AI provider/model selection.', fg='#B8C4D9', bg='#141D2C', wraplength=440, justify='left', font=('Consolas', 10)).pack(anchor='w', padx=18)

        scale_var = tk.DoubleVar(value=self.live2d_frame.scale)
        offset_var = tk.DoubleVar(value=self.live2d_frame.offset_y)

        tk.Label(window, text='Model Size', fg='#EAF1FF', bg='#141D2C', font=('Consolas', 11, 'bold')).pack(anchor='w', padx=18, pady=(18, 4))
        ttk.Scale(window, from_=0.12, to=1.40, variable=scale_var, command=lambda _value: self.live2d_frame.set_scale_value(scale_var.get())).pack(fill='x', padx=18)

        tk.Label(window, text='Model Vertical Position', fg='#EAF1FF', bg='#141D2C', font=('Consolas', 11, 'bold')).pack(anchor='w', padx=18, pady=(18, 4))
        ttk.Scale(window, from_=-0.65, to=0.10, variable=offset_var, command=lambda _value: self.live2d_frame.set_offset_y(offset_var.get())).pack(fill='x', padx=18)

        provider_frame = tk.LabelFrame(window, text='Change Online Model', fg='#F3F7FF', bg='#141D2C', font=('Consolas', 11, 'bold'))
        provider_frame.pack(fill='x', padx=18, pady=(18, 6))

        settings = online_settings.get()
        provider_var = tk.StringVar(value=PROVIDER_LABELS.get(settings.primary_provider, settings.primary_provider.title()))
        tk.Label(provider_frame, text='Primary Online Provider', fg='#EAF1FF', bg='#141D2C', font=('Consolas', 10, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
        provider_combo = ttk.Combobox(
            provider_frame,
            state='readonly',
            values=[PROVIDER_LABELS[name] for name in MODEL_CATALOG],
            textvariable=provider_var,
        )
        provider_combo.pack(fill='x', padx=12)
        provider_combo.bind('<<ComboboxSelected>>', lambda _event: self.change_primary_provider(self.provider_key_from_label(provider_var.get())))

        for provider, models in MODEL_CATALOG.items():
            provider_label = PROVIDER_LABELS.get(provider, provider.title())
            model_var = tk.StringVar(value=online_settings.get_selected_model(provider))
            tk.Label(provider_frame, text=f'{provider_label} Models', fg='#EAF1FF', bg='#141D2C', font=('Consolas', 10, 'bold')).pack(anchor='w', padx=12, pady=(12, 4))
            combo = ttk.Combobox(provider_frame, state='readonly', values=models, textvariable=model_var)
            combo.pack(fill='x', padx=12)
            combo.bind('<<ComboboxSelected>>', lambda _event, p=provider, var=model_var: self.change_online_model(p, var.get()))

        tts_frame = tk.LabelFrame(window, text='Voice Engine', fg='#F3F7FF', bg='#141D2C', font=('Consolas', 11, 'bold'))
        tts_frame.pack(fill='x', padx=18, pady=(12, 6))

        tts_var = tk.StringVar(value=TTS_ENGINES.get(tts_settings.get_engine(), TTS_ENGINES['edge']))
        tk.Label(tts_frame, text='Select TTS Backend', fg='#EAF1FF', bg='#141D2C', font=('Consolas', 10, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
        tts_combo = ttk.Combobox(
            tts_frame,
            state='readonly',
            values=list(TTS_ENGINES.values()),
            textvariable=tts_var,
        )
        tts_combo.pack(fill='x', padx=12)
        tts_combo.bind('<<ComboboxSelected>>', lambda _event: self.change_tts_engine(self.tts_key_from_label(tts_var.get())))

        buttons = tk.Frame(window, bg='#141D2C')
        buttons.pack(fill='x', padx=18, pady=(22, 8))
        ttk.Button(buttons, text='?? Toggle Voice', command=self.toggle_voice).pack(side='left')
        ttk.Button(buttons, text='? Test Voice', command=lambda: self.run_speech_async(MahiruReply(text='Can you hear me clearly now, Aakash?', expression='happy', mood='happy', motion='happy_bounce', status_text='Testing voice'))).pack(side='left', padx=(10, 0))
        ttk.Button(buttons, text='? Recenter Model', command=self.reset_model_position).pack(side='left', padx=(10, 0))

    def toggle_voice(self):
        self.voice_enabled = not self.voice_enabled
        self.refresh_tts_label()
        self.status_var.set(f"Status: {'Voice output turned on' if self.voice_enabled else 'Voice output turned off'}")

    def reset_model_position(self):
        self.live2d_frame.set_scale_value(0.42)
        self.live2d_frame.set_offset_y(-0.16)
        self.status_var.set('Status: Model position reset')

    def change_primary_provider(self, provider: str):
        if provider not in MODEL_CATALOG:
            return
        online_settings.set_primary_provider(provider)
        sync_runtime_preferences()
        self.refresh_online_provider_labels()
        fallback = online_settings.get_fallback_provider()
        self.status_var.set(
            f"Status: Primary online provider set to {PROVIDER_LABELS.get(provider, provider.title())} | fallback: {PROVIDER_LABELS.get(fallback, fallback.title())}"
        )

    def change_online_model(self, provider: str, model: str):
        online_settings.set_selected_model(provider, model)
        sync_runtime_preferences()
        self.refresh_online_provider_labels()
        self.status_var.set(f'Status: {PROVIDER_LABELS.get(provider, provider.title())} model set to {model}')

    def provider_key_from_label(self, label: str) -> str:
        for key, display in PROVIDER_LABELS.items():
            if display == label:
                return key
        return label.strip().lower()

    def change_tts_engine(self, engine: str):
        if engine not in TTS_ENGINES:
            return
        tts_settings.set_engine(engine)
        self.refresh_tts_label()
        self.status_var.set(f"Status: Voice engine set to {TTS_ENGINES[engine]}")

    def tts_key_from_label(self, label: str) -> str:
        for key, display in TTS_ENGINES.items():
            if display == label:
                return key
        return label.strip().lower()

    def project_root(self) -> str:
        return str(__import__('pathlib').Path(__file__).resolve().parent.parent)

    def run(self):
        self.root.mainloop()


def launch_desktop_ui():
    app = MahiruDesktopApp()
    app.run()
