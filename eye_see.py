import ctypes
from datetime import datetime, timedelta
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import winreg


APP_NAME = "EyeSee"
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
APP_DATA_DIR = APP_DIR
SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")
DEFAULTS = {"work_minutes": 60, "rest_minutes": 10, "prompt": True, "enabled": True}
NIGHT_LIGHT_KEY = r"Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.bluelightreduction.bluelightreductionstate\windows.data.bluelightreduction.bluelightreductionstate"


class EyeSeeApp:
    def __init__(self):
        self.settings = self.load_settings()
        self.running = True
        self.settings["enabled"] = True
        self.resting = False
        self.active_seconds = 0.0
        self.rest_seconds = 0.0
        self.rest_started_at = None
        self.last_tick = time.monotonic()
        self.last_input = self.get_last_input_time()
        self.night_light_changed = False
        self.tray_icon = None

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("380x430")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.build_ui()
        self.setup_tray()
        self.root.after_idle(self.tick)

    def load_settings(self):
        settings = DEFAULTS.copy()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
                settings.update(json.load(settings_file))
        except (OSError, json.JSONDecodeError):
            pass
        return settings

    def save_settings(self):
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        temporary_file = SETTINGS_FILE + ".tmp"
        with open(temporary_file, "w", encoding="utf-8") as settings_file:
            json.dump(self.settings, settings_file, indent=2)
        os.replace(temporary_file, SETTINGS_FILE)

    def build_ui(self):
        background = "#182321"
        panel = "#22312e"
        text = "#edf4ef"
        muted_text = "#a9bbb3"
        border = "#3b514a"
        self.root.configure(bg=background)
        style = ttk.Style(self.root)
        available_themes = style.theme_names()
        style.theme_use("vista" if "vista" in available_themes else "clam")
        style.configure("TFrame", background=background)
        style.configure("TLabel", background=background, foreground=text, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=background, font=("Segoe UI Semibold", 25), foreground="#78d1b0")
        style.configure("Subtitle.TLabel", background=background, foreground=muted_text, font=("Segoe UI", 10))
        style.configure("Card.TLabelframe", background=panel, foreground=text, bordercolor=border)
        style.configure("Card.TLabelframe.Label", background=panel, foreground="#78d1b0", font=("Segoe UI Semibold", 11))
        style.configure("Card.TFrame", background=panel)
        style.configure("Card.TLabel", background=panel, foreground=text)
        style.configure("TEntry", fieldbackground="#17211f", foreground=text, insertcolor=text)
        style.configure("Accent.TButton", background="#c76543", foreground="#ffffff", padding=(8, 4), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#dd7954"), ("pressed", "#a94f35")], foreground=[("disabled", "#9aa8a3"), ("!disabled", "#ffffff")])
        style.configure("Save.TButton", background="#3f9a70", foreground="#ffffff", padding=(8, 4), borderwidth=0)
        style.map("Save.TButton", background=[("active", "#52b783"), ("pressed", "#327a59")], foreground=[("disabled", "#9aa8a3"), ("!disabled", "#ffffff")])

        page = ttk.Frame(self.root, padding=20)
        page.pack(fill="both", expand=True)
        header = ttk.Frame(page)
        header.pack(fill="x", anchor="w")
        ttk.Label(header, text="EyeSee", style="Title.TLabel").pack(anchor="center")
        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=(8, 0))
        button_row = ttk.Frame(actions)
        button_row.pack()
        self.toggle_button = self.add_action_button(
            button_row,
            "Pause" if self.running else "Resume",
            self.toggle_running,
            "#c76543",
            "#dd7954",
            (0, 6),
        )
        self.add_action_button(
            button_row,
            "Save settings",
            self.apply_settings,
            "#3f9a70",
            "#52b783",
            (0, 6),
        )
        self.add_action_button(
            button_row,
            "Restart",
            self.restart_app,
            "#3f6f9a",
            "#5087b8",
        )
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(page, textvariable=self.status_var, style="Subtitle.TLabel", wraplength=380)
        self.status_label.pack(fill="x", anchor="w", pady=(4, 12))
        self.timestamp_var = tk.StringVar(value="Next rest time will appear when the timer starts.")
        ttk.Label(page, textvariable=self.timestamp_var, style="Subtitle.TLabel", wraplength=380).pack(
            fill="x", anchor="w", pady=(0, 12)
        )
        page.bind("<Configure>", self.resize_status_text)

        settings_area = ttk.Frame(page)
        settings_area.pack(fill="x")
        settings_area.columnconfigure(0, weight=1)
        settings_area.columnconfigure(1, weight=1)

        schedule = ttk.LabelFrame(settings_area, text="  Schedule  ", style="Card.TLabelframe", padding=14)
        self.work_var = tk.StringVar(value=str(self.settings["work_minutes"]))
        self.rest_var = tk.StringVar(value=str(self.settings["rest_minutes"]))
        self.add_number_row(schedule, "Work Intervals", self.work_var, "minutes")
        self.add_number_row(schedule, "Night Light Rest", self.rest_var, "minutes")

        options = ttk.LabelFrame(settings_area, text="  Preferences  ", style="Card.TLabelframe", padding=14)
        self.prompt_var = tk.BooleanVar(value=self.settings["prompt"])
        ttk.Checkbutton(options, text="Prompt me before starting a rest", variable=self.prompt_var).pack(anchor="w")
        ttk.Label(options, text="Uses Windows Night light without affecting usage.", style="Card.TLabel").pack(anchor="w", pady=(9, 0))
        self.settings_area = settings_area
        self.schedule_panel = schedule
        self.options_panel = options
        self.settings_layout_is_wide = None
        page.bind("<Configure>", self.resize_settings_layout, add="+")
        self.resize_settings_layout()

    def add_action_button(self, parent, text, command, background, active_background, padx=(0, 0)):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg="#ffffff",
            activebackground=active_background,
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=4,
        )
        button.pack(side="left", padx=padx)
        return button

    def resize_status_text(self, event):
        self.status_label.configure(wraplength=max(280, event.width - 56))

    def resize_settings_layout(self, event=None):
        available_width = self.settings_area.winfo_width()
        is_wide = available_width >= 560
        if is_wide == self.settings_layout_is_wide:
            return
        self.settings_layout_is_wide = is_wide
        self.schedule_panel.grid_forget()
        self.options_panel.grid_forget()
        if is_wide:
            self.schedule_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            self.options_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        else:
            self.schedule_panel.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.options_panel.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def add_number_row(self, parent, label, variable, suffix):
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, style="Card.TLabel").pack(side="left")
        ttk.Label(row, text=suffix, style="Card.TLabel").pack(side="right")
        tk.Entry(
            row,
            textvariable=variable,
            width=7,
            justify="center",
            bg="#ffffff",
            fg="#000000",
            insertbackground="#000000",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#9aa39f",
            highlightcolor="#3f9a70",
        ).pack(side="right", padx=(0, 8))

    def apply_settings(self):
        try:
            work_minutes = max(1, min(1440, int(self.work_var.get())))
            rest_minutes = max(1, min(180, int(self.rest_var.get())))
        except ValueError:
            messagebox.showerror(APP_NAME, "Use whole numbers for the schedule.", parent=self.root)
            return False
        previous_settings = self.settings.copy()
        self.settings.update({"work_minutes": work_minutes, "rest_minutes": rest_minutes, "prompt": self.prompt_var.get()})
        try:
            self.save_settings()
        except OSError as error:
            self.settings = previous_settings
            messagebox.showerror(APP_NAME, f"Could not save settings:\n{error}", parent=self.root)
            return False
        self.work_var.set(str(work_minutes))
        self.rest_var.set(str(rest_minutes))
        self.status_var.set("Settings saved. EyeSee is watching your active time.")
        return True

    def restart_app(self):
        if not self.apply_settings():
            return
        self.close_overlay()
        if getattr(sys, "frozen", False):
            restart_command = [sys.executable, *sys.argv[1:]]
        else:
            restart_command = [sys.executable, os.path.abspath(__file__), *sys.argv[1:]]
        try:
            subprocess.Popen(restart_command, cwd=APP_DIR, close_fds=True)
        except OSError as error:
            messagebox.showerror(APP_NAME, f"Could not restart EyeSee:\n{error}", parent=self.root)
            return
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(100, self.close_app)

    def toggle_running(self):
        self.running = not self.running
        previous_running = not self.running
        self.settings["enabled"] = self.running
        try:
            self.save_settings()
        except OSError as error:
            self.running = previous_running
            self.settings["enabled"] = previous_running
            messagebox.showerror(APP_NAME, f"Could not save settings:\n{error}", parent=self.root)
            return
        self.toggle_button.configure(text="Pause" if self.running else "Resume")
        if not self.running:
            self.close_overlay()
            self.status_var.set("Paused. Your schedule will resume when you press Resume.")
        else:
            self.last_input = self.get_last_input_time()
            self.status_var.set("Active. Night light will start after your work interval.")

    def setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            self.status_var.set("Tray support is unavailable. Install requirements.txt to hide EyeSee.")
            return

        image = Image.new("RGBA", (64, 64), (23, 63, 59, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((15, 15, 49, 49), fill=(242, 184, 91, 255))
        draw.ellipse((27, 11, 52, 36), fill=(23, 63, 59, 255))
        menu = pystray.Menu(
            pystray.MenuItem("Show EyeSee", self.tray_show),
            pystray.MenuItem("Pause / Resume", self.tray_toggle),
            pystray.MenuItem("Exit", self.tray_exit),
        )
        self.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def tray_show(self, _icon=None, _item=None):
        self.root.after(0, self.show_window)

    def tray_toggle(self, _icon=None, _item=None):
        self.root.after(0, self.toggle_running)

    def tray_exit(self, _icon=None, _item=None):
        self.root.after(0, self.close_app)

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def get_last_input_time(self):
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            tick_count = ctypes.windll.kernel32.GetTickCount()
            return max(0.0, time.monotonic() - (tick_count - info.dwTime) / 1000.0)
        return time.monotonic()

    def rounded_time(self, seconds=0):
        target = datetime.now() + timedelta(seconds=seconds)
        rounded = target.replace(second=0, microsecond=0)
        if target.second or target.microsecond:
            rounded += timedelta(minutes=1)
        return rounded.strftime("%H:%M")

    def tick(self):
        now = time.monotonic()
        elapsed = max(0.0, now - self.last_tick)
        self.last_tick = now
        current_input = self.get_last_input_time()
        input_delta = max(0.0, current_input - self.last_input)
        self.last_input = current_input
        if self.running:
            if self.resting:
                self.rest_seconds += elapsed
                remaining = max(0, int(self.settings["rest_minutes"] * 60 - self.rest_seconds))
                resume_at = self.rounded_time(remaining)
                self.status_var.set(
                    f"Night light is on. Resume at {resume_at}. "
                    f"Time remaining: {remaining // 60}:{remaining % 60:02d}"
                )
                self.timestamp_var.set(f"Resume at: {resume_at}")
                if self.rest_seconds >= self.settings["rest_minutes"] * 60:
                    self.finish_rest()
            else:
                self.active_seconds += input_delta
                remaining = max(0, int(self.settings["work_minutes"] * 60 - self.active_seconds))
                rest_at = self.rounded_time(remaining)
                self.status_var.set(
                    f"Active use countdown: {remaining // 60}:{remaining % 60:02d}."
                )
                self.timestamp_var.set(f"Next rest at: {rest_at}")
                if self.active_seconds >= self.settings["work_minutes"] * 60:
                    self.begin_rest()
        self.root.after(1000, self.tick)

    def begin_rest(self):
        self.active_seconds = 0
        if self.settings["prompt"]:
            self.show_prompt()
        else:
            self.start_overlay()

    def show_prompt(self):
        message_flags = 0x00000004 | 0x00000040 | 0x00040000 | 0x00001000
        answer = ctypes.windll.user32.MessageBoxW(
            self.root.winfo_id(),
            "Your eyes have earned a pause.\n\nStart Windows Night light now?",
            "EyeSee - Time for a visual rest",
            message_flags,
        )
        if answer == 6:
            self.start_overlay()
        else:
            self.active_seconds = 0

    def start_overlay(self):
        if self.resting:
            return
        try:
            if not self.system_night_light_enabled():
                self.set_system_night_light(True)
                self.night_light_changed = True
        except RuntimeError as error:
            self.status_var.set(str(error))
            return
        self.resting = True
        self.rest_seconds = 0
        self.rest_started_at = self.rounded_time()
        self.timestamp_var.set(f"Rest started: {self.rest_started_at}")

    def close_overlay(self):
        if self.night_light_changed:
            try:
                self.set_system_night_light(False)
            except RuntimeError:
                pass
            self.night_light_changed = False
        self.resting = False
        self.rest_seconds = 0
        self.rest_started_at = None

    def finish_rest(self):
        self.close_overlay()
        completed_at = self.rounded_time()
        self.timestamp_var.set(f"Rest completed: {completed_at}")
        self.status_var.set(f"Rest complete at {completed_at}. Your active-use timer has started again.")

    def system_night_light_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, NIGHT_LIGHT_KEY, 0, winreg.KEY_READ) as key:
                data, _ = winreg.QueryValueEx(key, "Data")
            return len(data) > 18 and data[18] == 0x15
        except (FileNotFoundError, OSError):
            raise RuntimeError("Windows Night light is not available on this device.")

    def set_system_night_light(self, enabled):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, NIGHT_LIGHT_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
                data, _ = winreg.QueryValueEx(key, "Data")
                data = bytearray(data)
                currently_enabled = len(data) > 18 and data[18] == 0x15
                if currently_enabled == enabled:
                    return
                if enabled:
                    new_data = bytearray(43)
                    new_data[0:22] = data[0:min(22, len(data))]
                    if len(data) > 23:
                        copy_length = min(len(data) - 23, 18)
                        new_data[25:25 + copy_length] = data[23:23 + copy_length]
                    new_data[18] = 0x15
                    new_data[23] = 0x10
                    new_data[24] = 0x00
                else:
                    new_data = bytearray(41)
                    new_data[0:22] = data[0:min(22, len(data))]
                    if len(data) > 25:
                        copy_length = min(len(data) - 25, 18)
                        new_data[23:23 + copy_length] = data[25:25 + copy_length]
                    new_data[18] = 0x13
                for index in range(10, 15):
                    if new_data[index] != 0xFF:
                        new_data[index] = (new_data[index] + 1) % 256
                        break
                winreg.SetValueEx(key, "Data", 0, winreg.REG_BINARY, bytes(new_data))
        except (FileNotFoundError, OSError) as error:
            raise RuntimeError(f"Could not change Windows Night light: {error}") from error

    def close_app(self):
        self.close_overlay()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    EyeSeeApp().run()