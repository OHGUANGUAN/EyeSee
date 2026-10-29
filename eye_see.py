import ctypes
from datetime import datetime, timedelta
import functools
import json
import math
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import uuid
from tkinter import font as tkfont, messagebox
import winreg
import winsound

APP_NAME = "EyeSee"
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
ICON_FILE = os.path.join(APP_DIR, "assets", "eyesee.ico")
LOGO_FILE = os.path.join(APP_DIR, "assets", "eyesee_logo_512.png")
DEFAULTS = {"work_minutes": 60, "rest_minutes": 10, "prompt": True, "alarm": False, "night_light": True}
WORK_MINUTES_RANGE = (1, 1440)
REST_MINUTES_RANGE = (1, 180)
# The work timer keeps counting until there has been no keyboard or mouse input for this long.
AWAY_AFTER_SECONDS = 5 * 60
NIGHT_LIGHT_KEY = r"Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.bluelightreduction.bluelightreductionstate\windows.data.bluelightreduction.bluelightreductionstate"

THEME = {
    "background": "#0f1716",
    "card": "#172220",
    "border": "#22302d",
    "control": "#22312e",
    "control_hover": "#2d403c",
    "control_pressed": "#1b2826",
    "text": "#eef4f1",
    "muted": "#93a69f",
    "subtle": "#5f726b",
    "accent": "#f2b85b",
    "accent_hover": "#f6c674",
    "accent_pressed": "#dca046",
    "on_accent": "#1d1608",
    "rest": "#5cc8a8",
    "danger": "#f07a62",
}
FONT = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"
FONT_LIGHT = "Segoe UI Light"
WINDOW_WIDTH = 260
SETTINGS_WINDOW_WIDTH = 280
PAGE_PADDING = 12
RING_SIZE = 140
RING_STROKE = 7
# (fill, hover, pressed, foreground)
PRIMARY_BUTTON = (THEME["accent"], THEME["accent_hover"], THEME["accent_pressed"], THEME["on_accent"])
SECONDARY_BUTTON = (THEME["control"], THEME["control_hover"], THEME["control_pressed"], THEME["text"])
GHOST_BUTTON = (THEME["background"], THEME["control"], THEME["control_pressed"], THEME["muted"])
GHOST_BUTTON_ACTIVE = (THEME["control"], THEME["control_hover"], THEME["control_pressed"], THEME["text"])
ICON_SETTINGS = ""
ICON_RESTART = ""
ICON_PAUSE = ""
ICON_PLAY = ""
ICON_PLUS = ""
ICON_MINUS = ""


def px(widget, value):
    return round(value * widget.winfo_fpixels("1i") / 96)


@functools.cache
def icon_font_family():
    return "Segoe Fluent Icons" if "Segoe Fluent Icons" in tkfont.families() else "Segoe MDL2 Assets"


def rounded_rect(canvas, x1, y1, x2, y2, radius, **options):
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    corners = ((x2 - radius, y1 + radius, 90), (x1 + radius, y1 + radius, 180), (x1 + radius, y2 - radius, 270), (x2 - radius, y2 - radius, 0))
    points = []
    for center_x, center_y, start_angle in corners:
        for step in range(13):
            angle = math.radians(start_angle - 90 + step * 7.5)
            points += [center_x + radius * math.cos(angle), center_y - radius * math.sin(angle)]
    return canvas.create_polygon(points, **options)


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        self.pending = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress-1>", self.hide, add="+")

    def schedule(self, _event=None):
        self.pending = self.widget.after(500, self.show)

    def show(self):
        self.pending = None
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        tk.Label(
            self.window,
            text=self.text,
            font=(FONT, 9),
            bg=THEME["control_hover"],
            fg=THEME["text"],
            padx=px(self.widget, 8),
            pady=px(self.widget, 4),
        ).pack()
        self.window.update_idletasks()
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() - self.window.winfo_reqwidth()) // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + px(self.widget, 6)
        self.window.geometry(f"+{x}+{y}")

    def hide(self, _event=None):
        if self.pending:
            self.widget.after_cancel(self.pending)
            self.pending = None
        if self.window:
            self.window.destroy()
            self.window = None


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent,
        command,
        palette,
        text="",
        icon="",
        width=None,
        height=36,
        background=THEME["background"],
        font_size=10,
        icon_size=11,
        tooltip=None,
    ):
        super().__init__(parent, bg=background, highlightthickness=0, borderwidth=0, cursor="hand2", takefocus=1)
        self.command = command
        self.palette = palette
        self.text = text
        self.icon = icon
        self.fixed_width = width
        self.button_height = px(self, height)
        self.text_font = tkfont.Font(family=FONT_SEMIBOLD, size=font_size)
        self.icon_font = tkfont.Font(family=icon_font_family(), size=icon_size)
        self.hovered = False
        self.pressed = False
        self.focused = False
        self.bind("<Enter>", lambda _event: self.set_state(hovered=True))
        self.bind("<Leave>", lambda _event: self.set_state(hovered=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda _event: self.set_state(pressed=True))
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<FocusIn>", lambda _event: self.set_state(focused=True))
        self.bind("<FocusOut>", lambda _event: self.set_state(focused=False))
        self.bind("<Return>", lambda _event: self.command())
        self.bind("<space>", lambda _event: self.command())
        if tooltip:
            Tooltip(self, tooltip)
        self.redraw()

    def set_state(self, **state):
        for name, value in state.items():
            setattr(self, name, value)
        self.redraw()

    def set_content(self, text=None, icon=None, palette=None):
        self.text = self.text if text is None else text
        self.icon = self.icon if icon is None else icon
        self.palette = self.palette if palette is None else palette
        self.redraw()

    def release(self, _event):
        clicked = self.pressed and self.hovered
        self.set_state(pressed=False)
        if clicked:
            self.command()

    def redraw(self):
        fill, hover, pressed, foreground = self.palette
        height = self.button_height
        icon_width = self.icon_font.measure(self.icon) if self.icon else 0
        text_width = self.text_font.measure(self.text) if self.text else 0
        gap = px(self, 8) if self.icon and self.text else 0
        content_width = icon_width + gap + text_width
        width = px(self, self.fixed_width) if self.fixed_width else height
        self.configure(width=width, height=height)
        self.delete("all")
        color = pressed if self.pressed else hover if self.hovered else fill
        rounded_rect(self, 0, 0, width, height, height / 2, fill=color, outline=color)
        if self.focused:
            rounded_rect(self, 1, 1, width - 2, height - 2, height / 2, fill="", outline=THEME["muted"])
        x = (width - content_width) / 2
        if self.icon:
            self.create_text(x, height / 2, text=self.icon, font=self.icon_font, fill=foreground, anchor="w")
        if self.text:
            self.create_text(x + icon_width + gap, height / 2, text=self.text, font=self.text_font, fill=foreground, anchor="w")


class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable, command, background):
        self.switch_width = px(parent, 40)
        self.switch_height = px(parent, 20)
        super().__init__(
            parent,
            width=self.switch_width,
            height=self.switch_height,
            bg=background,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
            takefocus=1,
        )
        self.variable = variable
        self.command = command
        self.focused = False
        trace = variable.trace_add("write", lambda *_args: self.redraw())
        self.bind("<Destroy>", lambda _event: variable.trace_remove("write", trace))
        self.bind("<ButtonRelease-1>", self.toggle)
        self.bind("<space>", self.toggle)
        self.bind("<Return>", self.toggle)
        self.bind("<FocusIn>", lambda _event: self.set_focused(True))
        self.bind("<FocusOut>", lambda _event: self.set_focused(False))
        self.redraw()

    def set_focused(self, focused):
        self.focused = focused
        self.redraw()

    def toggle(self, _event=None):
        self.variable.set(not self.variable.get())
        self.command()

    def redraw(self):
        self.delete("all")
        enabled = self.variable.get()
        width, height = self.switch_width, self.switch_height
        track = THEME["accent"] if enabled else THEME["control_hover"]
        outline = THEME["muted"] if self.focused else track
        rounded_rect(self, 1, 1, width - 1, height - 1, height / 2, fill=track, outline=outline)
        inset = px(self, 4)
        knob = height - 2 * inset
        x = width - inset - knob if enabled else inset
        self.create_oval(x, inset, x + knob, inset + knob, fill=THEME["on_accent"] if enabled else THEME["muted"], outline="")


class EyeSeeApp:
    def __init__(self):
        self.settings = self.load_settings()
        self.running = True
        self.resting = False
        self.active_seconds = 0.0
        self.rest_seconds = 0.0
        self.last_tick = time.monotonic()
        self.night_light_changed = False
        self.tray_icon = None
        self.notice = ""
        self.pending_schedule_save = None
        self.pending_save_state_clear = None
        self.card_resizers = []
        self.settings_window = None
        self.save_state_label = None
        self.drag_offset = (0, 0)

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_NAME)
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.set_window_icon()
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.build_ui()
        self.fit_window()
        self.apply_dark_title_bar()
        self.set_taskbar_identity()
        self.setup_tray()
        self.root.after_idle(self.tick)

    def load_settings(self):
        settings = DEFAULTS.copy()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
                saved = json.load(settings_file)
            settings.update({key: saved[key] for key in DEFAULTS if key in saved})
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return settings

    def save_settings(self):
        temporary_file = SETTINGS_FILE + ".tmp"
        with open(temporary_file, "w", encoding="utf-8") as settings_file:
            json.dump(self.settings, settings_file, indent=2)
        os.replace(temporary_file, SETTINGS_FILE)

    def build_ui(self):
        background = THEME["background"]
        self.root.configure(bg=background)
        page = tk.Frame(self.root, bg=background, padx=px(self.root, PAGE_PADDING), pady=px(self.root, 10))
        page.pack(fill="both", expand=True)

        header = tk.Frame(page, bg=background)
        header.pack(fill="x")
        self.header_logo = self.load_logo(20)
        logo_label = tk.Label(header, image=self.header_logo, bg=background)
        if self.header_logo:
            logo_label.pack(side="left")
        name_label = tk.Label(header, text=APP_NAME, font=(FONT_SEMIBOLD, 10), fg=THEME["text"], bg=background)
        name_label.pack(side="left", padx=(px(self.root, 6), 0))
        self.settings_button = RoundedButton(
            header,
            self.open_settings,
            GHOST_BUTTON,
            icon=ICON_SETTINGS,
            height=26,
            icon_size=9,
            tooltip="Settings",
        )
        self.settings_button.pack(side="right")
        restart_button = RoundedButton(
            header,
            self.restart_app,
            GHOST_BUTTON,
            icon=ICON_RESTART,
            height=26,
            icon_size=9,
            tooltip="Restart EyeSee",
        )
        restart_button.pack(side="right")

        ring_size = px(self.root, RING_SIZE)
        self.ring = tk.Canvas(page, width=ring_size, height=ring_size, bg=background, highlightthickness=0, borderwidth=0)
        self.ring.pack(pady=(px(self.root, 8), px(self.root, 8)))
        inset = px(self.root, RING_STROKE) / 2 + 1
        self.ring.create_oval(
            inset,
            inset,
            ring_size - inset,
            ring_size - inset,
            outline=THEME["control"],
            width=px(self.root, RING_STROKE),
        )
        # Progress items are created once and updated in place; recreating them every tick leaks memory in Tk.
        stroke = px(self.root, RING_STROKE)
        self.ring_full = self.ring.create_oval(inset, inset, ring_size - inset, ring_size - inset, width=stroke, state="hidden")
        self.ring_arc = self.ring.create_arc(
            inset,
            inset,
            ring_size - inset,
            ring_size - inset,
            start=90,
            style="arc",
            width=stroke,
            state="hidden",
        )
        self.ring_caps = [self.ring.create_oval(0, 0, 0, 0, outline="", state="hidden") for _ in range(2)]
        self.ring_time_font_size = None
        center = ring_size / 2
        self.ring_phase = self.ring.create_text(center, center - px(self.root, 25), font=(FONT_SEMIBOLD, 7))
        self.ring_time = self.ring.create_text(center, center, font=(FONT_LIGHT, 18), fill=THEME["text"])
        self.ring_caption = self.ring.create_text(center, center + px(self.root, 24), font=(FONT, 8), fill=THEME["muted"])

        self.notice_label = tk.Label(
            page,
            font=(FONT, 9),
            fg=THEME["danger"],
            bg=background,
            wraplength=ring_size,
            justify="center",
        )
        self.toggle_button = RoundedButton(
            page,
            self.toggle_running,
            SECONDARY_BUTTON,
            width=100,
            height=28,
            font_size=8,
            icon_size=8,
        )
        self.toggle_button.pack(pady=(0, px(self.root, 2)))
        self.update_toggle_button()
        for widget in (page, header, logo_label, name_label, self.ring, self.notice_label):
            widget.bind("<ButtonPress-1>", self.start_window_drag)
            widget.bind("<B1-Motion>", self.drag_window)

        self.work_var = tk.StringVar(value=str(self.settings["work_minutes"]))
        self.rest_var = tk.StringVar(value=str(self.settings["rest_minutes"]))
        self.prompt_var = tk.BooleanVar(value=self.settings["prompt"])
        self.alarm_var = tk.BooleanVar(value=self.settings["alarm"])
        self.night_light_var = tk.BooleanVar(value=self.settings["night_light"])

    def build_settings_window(self):
        background = THEME["background"]
        window = tk.Toplevel(self.root, bg=background)
        window.title("Settings")
        window.resizable(False, False)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self.close_settings)
        window.bind("<Escape>", lambda _event: self.close_settings())
        self.settings_window = window
        self.card_resizers = []
        page = tk.Frame(window, bg=background, padx=px(self.root, PAGE_PADDING), pady=px(self.root, 12))
        page.pack(fill="both", expand=True)

        schedule_heading = self.add_section_label(page, "Schedule")
        self.save_state_label = tk.Label(schedule_heading, text="", font=(FONT, 8), fg=THEME["muted"], bg=background)
        self.save_state_label.pack(side="right")
        schedule = self.add_card(page)
        self.add_stepper_row(schedule, "Work interval", "Active use before a rest", self.work_var, *WORK_MINUTES_RANGE, 5)
        self.add_divider(schedule)
        self.add_stepper_row(schedule, "Rest break", "Rest length", self.rest_var, *REST_MINUTES_RANGE, 1)

        tk.Frame(page, bg=background, height=px(self.root, 12)).pack(fill="x")
        self.add_section_label(page, "Preferences")
        preferences = self.add_card(page)
        self.add_switch_row(preferences, "Night light during rest", "Filter blue light while resting", self.night_light_var)
        self.add_divider(preferences)
        self.add_switch_row(preferences, "Ask before resting", "Confirm before a rest starts", self.prompt_var)
        self.add_divider(preferences)
        self.add_switch_row(preferences, "Beep when rest ends", "A short sound calls you back", self.alarm_var)
        return window

    def start_window_drag(self, event):
        self.drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def drag_window(self, event):
        offset_x, offset_y = self.drag_offset
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def load_logo(self, size):
        try:
            from PIL import Image, ImageDraw, ImageTk

            size = px(self.root, size)
            logo = Image.open(LOGO_FILE).convert("RGBA").resize((size * 4, size * 4), Image.LANCZOS)
            mask = Image.new("L", logo.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, *logo.size), radius=logo.size[0] // 4, fill=255)
            logo.putalpha(mask)
            return ImageTk.PhotoImage(logo.resize((size, size), Image.LANCZOS))
        except (ImportError, OSError):
            return None

    def launch_command(self):
        if getattr(sys, "frozen", False):
            return [sys.executable]
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        return [pythonw if os.path.exists(pythonw) else sys.executable, os.path.abspath(__file__)]

    def set_taskbar_identity(self):
        # Without these window properties, a taskbar pin points at pythonw.exe and shows the Python icon.
        class GUID(ctypes.Structure):
            _fields_ = [("data", ctypes.c_ubyte * 16)]

        class PROPERTYKEY(ctypes.Structure):
            _fields_ = [("fmtid", GUID), ("pid", ctypes.c_ulong)]

        class PROPVARIANT(ctypes.Structure):
            _fields_ = [("vt", ctypes.c_ushort), ("reserved", ctypes.c_ushort * 3), ("value", ctypes.c_void_p), ("padding", ctypes.c_void_p)]

        def guid(text):
            return GUID.from_buffer_copy(uuid.UUID(text).bytes_le)

        app_model_properties = guid("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3")
        properties = (
            (5, APP_NAME),
            (2, subprocess.list2cmdline(self.launch_command())),
            (3, f"{ICON_FILE},0"),
            (4, APP_NAME),
        )
        try:
            window = ctypes.windll.user32.GetParent(self.root.winfo_id())
            store = ctypes.c_void_p()
            interface_id = guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")
            if ctypes.windll.shell32.SHGetPropertyStoreForWindow(window, ctypes.byref(interface_id), ctypes.byref(store)) or not store:
                return
            methods = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
            set_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))(methods[6])
            release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(methods[2])
            for property_id, value in properties:
                text = ctypes.create_unicode_buffer(value)
                variant = PROPVARIANT(vt=31, value=ctypes.cast(text, ctypes.c_void_p))
                set_value(store, ctypes.byref(PROPERTYKEY(app_model_properties, property_id)), ctypes.byref(variant))
            release(store)
        except (AttributeError, OSError):
            pass

    def apply_dark_title_bar(self, window=None):
        window = window or self.root
        try:
            window.update_idletasks()
            window = ctypes.windll.user32.GetParent(window.winfo_id())
            red, green, blue = (int(THEME["background"][index:index + 2], 16) for index in (1, 3, 5))
            for attribute, value in ((20, 1), (35, blue << 16 | green << 8 | red)):
                value = ctypes.c_int(value)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(window, attribute, ctypes.byref(value), ctypes.sizeof(value))
        except (AttributeError, OSError):
            pass

    def fit_window(self, window=None):
        window = window or self.root
        window.update_idletasks()
        if window is self.settings_window:
            for resize_card in self.card_resizers:
                resize_card()
            window.update_idletasks()
            width = px(self.root, SETTINGS_WINDOW_WIDTH)
        else:
            width = max(px(self.root, WINDOW_WIDTH), window.winfo_reqwidth())
        window.geometry(f"{width}x{window.winfo_reqheight()}")

    def add_section_label(self, parent, text):
        row = tk.Frame(parent, bg=THEME["background"])
        row.pack(fill="x", padx=px(self.root, 4), pady=(0, px(self.root, 4)))
        tk.Label(row, text=text.upper(), font=(FONT_SEMIBOLD, 8), fg=THEME["subtle"], bg=THEME["background"]).pack(side="left")
        return row

    def add_card(self, parent):
        padding = px(self.root, 12)
        width = px(self.root, SETTINGS_WINDOW_WIDTH - 2 * PAGE_PADDING)
        canvas = tk.Canvas(parent, width=width, height=1, bg=THEME["background"], highlightthickness=0, borderwidth=0)
        canvas.pack()
        content = tk.Frame(canvas, bg=THEME["card"])
        canvas.create_window(padding, padding, window=content, anchor="nw", width=width - 2 * padding)

        def resize(_event=None):
            height = content.winfo_reqheight() + 2 * padding
            canvas.configure(height=height)
            canvas.delete("card")
            rounded_rect(canvas, 0, 0, width - 1, height - 1, px(self.root, 12), fill=THEME["card"], outline=THEME["border"], tags="card")
            canvas.tag_lower("card")

        content.bind("<Configure>", resize)
        self.card_resizers.append(resize)
        return content

    def add_divider(self, parent):
        tk.Frame(parent, bg=THEME["border"], height=max(1, px(self.root, 1))).pack(fill="x", pady=px(self.root, 8))

    def add_row_text(self, row, title, hint):
        text_column = tk.Frame(row, bg=THEME["card"])
        text_column.pack(side="left", fill="x", expand=True)
        labels = [
            tk.Label(text_column, text=title, font=(FONT_SEMIBOLD, 9), fg=THEME["text"], bg=THEME["card"], anchor="w"),
            tk.Label(text_column, text=hint, font=(FONT, 8), fg=THEME["muted"], bg=THEME["card"], anchor="w"),
        ]
        for label in labels:
            label.pack(fill="x")
        return labels

    def add_stepper_row(self, parent, title, hint, variable, minimum, maximum, step):
        row = tk.Frame(parent, bg=THEME["card"])
        row.pack(fill="x")
        controls = tk.Frame(row, bg=THEME["card"])
        controls.pack(side="right")
        RoundedButton(
            controls,
            lambda: self.step_schedule(variable, -step, minimum, maximum),
            SECONDARY_BUTTON,
            icon=ICON_MINUS,
            height=24,
            icon_size=7,
            background=THEME["card"],
        ).pack(side="left")
        value_column = tk.Frame(controls, bg=THEME["card"])
        value_column.pack(side="left", padx=px(self.root, 2))
        entry = tk.Entry(
            value_column,
            textvariable=variable,
            width=4,
            justify="center",
            font=(FONT_SEMIBOLD, 10),
            bg=THEME["card"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=THEME["card"],
            highlightcolor=THEME["accent"],
        )
        entry.pack()
        entry.bind("<Return>", lambda _event: entry.winfo_toplevel().focus_set())
        entry.bind("<FocusOut>", lambda _event: self.save_schedule())
        tk.Label(value_column, text="min", font=(FONT, 8), fg=THEME["muted"], bg=THEME["card"]).pack()
        RoundedButton(
            controls,
            lambda: self.step_schedule(variable, step, minimum, maximum),
            SECONDARY_BUTTON,
            icon=ICON_PLUS,
            height=24,
            icon_size=7,
            background=THEME["card"],
        ).pack(side="left")
        self.add_row_text(row, title, hint)

    def add_switch_row(self, parent, title, hint, variable):
        row = tk.Frame(parent, bg=THEME["card"])
        row.pack(fill="x")
        switch = ToggleSwitch(row, variable, self.save_preferences, THEME["card"])
        switch.pack(side="right", padx=(px(self.root, 8), 0))
        for label in self.add_row_text(row, title, hint):
            label.configure(cursor="hand2")
            label.bind("<ButtonRelease-1>", switch.toggle)

    def step_schedule(self, variable, delta, minimum, maximum):
        try:
            value = int(variable.get())
        except ValueError:
            value = minimum
        variable.set(str(max(minimum, min(maximum, value + delta))))
        if self.pending_schedule_save:
            self.root.after_cancel(self.pending_schedule_save)
        self.pending_schedule_save = self.root.after(400, self.save_schedule)

    def show_save_state(self, text, color=THEME["muted"]):
        if self.pending_save_state_clear:
            self.root.after_cancel(self.pending_save_state_clear)
            self.pending_save_state_clear = None
        if not self.settings_window:
            return
        self.save_state_label.configure(text=text, fg=color)
        self.pending_save_state_clear = self.root.after(2000, lambda: self.show_save_state(""))

    def update_toggle_button(self):
        if self.running:
            self.toggle_button.set_content(text="Pause", icon=ICON_PAUSE, palette=SECONDARY_BUTTON)
        else:
            self.toggle_button.set_content(text="Resume", icon=ICON_PLAY, palette=PRIMARY_BUTTON)

    def open_settings(self):
        if self.settings_window:
            self.close_settings()
            return
        window = self.build_settings_window()
        self.fit_window(window)
        gap = px(self.root, 12)
        x = self.root.winfo_x() + self.root.winfo_width() + gap
        if x + window.winfo_width() > self.root.winfo_screenwidth():
            x = max(0, self.root.winfo_x() - window.winfo_width() - gap)
        window.geometry(f"+{x}+{self.root.winfo_y()}")
        self.apply_dark_title_bar(window)
        window.focus_set()
        self.settings_button.set_content(palette=GHOST_BUTTON_ACTIVE)

    def close_settings(self):
        if not self.settings_window:
            return
        if self.pending_schedule_save:
            self.root.after_cancel(self.pending_schedule_save)
        self.save_schedule()
        window, self.settings_window = self.settings_window, None
        self.show_save_state("")
        window.destroy()
        self.save_state_label = None
        self.settings_button.set_content(palette=GHOST_BUTTON)

    def read_schedule(self):
        try:
            work_minutes = max(WORK_MINUTES_RANGE[0], min(WORK_MINUTES_RANGE[1], int(self.work_var.get())))
            rest_minutes = max(REST_MINUTES_RANGE[0], min(REST_MINUTES_RANGE[1], int(self.rest_var.get())))
        except ValueError:
            return None
        return work_minutes, rest_minutes

    def save_schedule(self):
        self.pending_schedule_save = None
        schedule = self.read_schedule()
        if schedule is None:
            self.work_var.set(str(self.settings["work_minutes"]))
            self.rest_var.set(str(self.settings["rest_minutes"]))
            self.show_save_state("Whole numbers only", THEME["danger"])
            return False
        work_minutes, rest_minutes = schedule
        self.work_var.set(str(work_minutes))
        self.rest_var.set(str(rest_minutes))
        if (work_minutes, rest_minutes) == (self.settings["work_minutes"], self.settings["rest_minutes"]):
            return True
        previous_settings = self.settings.copy()
        self.settings.update({"work_minutes": work_minutes, "rest_minutes": rest_minutes})
        try:
            self.save_settings()
        except OSError:
            self.settings = previous_settings
            self.work_var.set(str(self.settings["work_minutes"]))
            self.rest_var.set(str(self.settings["rest_minutes"]))
            self.show_save_state("Could not save", THEME["danger"])
            return False
        self.show_save_state("Saved")
        self.update_status()
        return True

    def save_preferences(self):
        previous_settings = self.settings.copy()
        self.settings.update({"prompt": self.prompt_var.get(), "alarm": self.alarm_var.get(), "night_light": self.night_light_var.get()})
        try:
            self.save_settings()
        except OSError:
            self.settings = previous_settings
            self.prompt_var.set(self.settings["prompt"])
            self.alarm_var.set(self.settings["alarm"])
            self.night_light_var.set(self.settings["night_light"])
            self.show_save_state("Could not save", THEME["danger"])
            return False
        if not self.settings["night_light"]:
            self.restore_night_light()
        self.show_save_state("Saved")
        return True

    def restart_app(self):
        self.close_settings()
        try:
            subprocess.Popen(self.launch_command(), cwd=APP_DIR, close_fds=True)
        except OSError as error:
            messagebox.showerror(APP_NAME, f"Could not restart EyeSee:\n{error}", parent=self.root)
            return
        self.close_app()

    def toggle_running(self):
        self.running = not self.running
        self.notice = ""
        self.update_toggle_button()
        if not self.running:
            self.stop_rest()
        self.update_status()

    def set_window_icon(self):
        try:
            from PIL import Image, ImageTk

            logo = Image.open(LOGO_FILE)
            # Pre-scaled copies let Windows pick a crisp size for the title bar and taskbar.
            self.window_icons = [
                ImageTk.PhotoImage(logo.resize((size, size), Image.LANCZOS))
                for size in (256, 128, 64, 48, 32, 16)
            ]
            self.root.iconphoto(True, *self.window_icons)
        except (ImportError, OSError, tk.TclError):
            try:
                self.root.iconbitmap(default=ICON_FILE)
            except tk.TclError:
                pass

    def setup_tray(self):
        try:
            import pystray
            from PIL import Image

            image = Image.open(ICON_FILE)
        except (ImportError, OSError):
            return
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

    def get_idle_seconds(self):
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        tick_count = ctypes.c_uint(ctypes.windll.kernel32.GetTickCount()).value
        # Both counters are 32-bit milliseconds that wrap after ~49.7 days.
        return ((tick_count - info.dwTime) & 0xFFFFFFFF) / 1000.0

    def rounded_time(self, seconds):
        target = datetime.now() + timedelta(seconds=seconds)
        rounded = target.replace(second=0, microsecond=0)
        if target.second or target.microsecond:
            rounded += timedelta(minutes=1)
        return rounded.strftime("%H:%M")

    def draw_ring(self, fraction, color):
        extent = 359.99 * max(0.0, min(1.0, fraction))
        full = extent >= 359
        partial = 0.5 <= extent < 359
        self.ring.itemconfigure(self.ring_full, state="normal" if full else "hidden", outline=color)
        self.ring.itemconfigure(self.ring_arc, state="normal" if partial else "hidden", extent=-extent, outline=color)
        size = px(self.root, RING_SIZE)
        stroke = px(self.root, RING_STROKE)
        radius = size / 2 - stroke / 2 - 1
        for cap, angle in zip(self.ring_caps, (90, 90 - extent)):
            x = size / 2 + radius * math.cos(math.radians(angle))
            y = size / 2 - radius * math.sin(math.radians(angle))
            self.ring.coords(cap, x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2)
            self.ring.itemconfigure(cap, state="normal" if partial else "hidden", fill=color)

    def update_status(self):
        if self.resting:
            total = self.settings["rest_minutes"] * 60
            remaining = max(0, int(total - self.rest_seconds))
            color, phase = THEME["rest"], "RESTING"
            caption = f"back to work at {self.rounded_time(remaining)}"
        else:
            total = self.settings["work_minutes"] * 60
            remaining = max(0, int(total - self.active_seconds))
            color, phase = THEME["accent"], "FOCUS"
            caption = f"next rest at {self.rounded_time(remaining)}"
        if not self.running:
            color, phase, caption = THEME["subtle"], "PAUSED", "press Resume"
        hours, minutes, seconds = remaining // 3600, remaining // 60 % 60, remaining % 60
        countdown = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
        self.draw_ring(remaining / total if total else 0, color)
        self.ring.itemconfigure(self.ring_phase, text=phase, fill=color)
        self.ring.itemconfigure(self.ring_time, text=countdown)
        font_size = 14 if hours else 18
        if font_size != self.ring_time_font_size:
            self.ring_time_font_size = font_size
            self.ring.itemconfigure(self.ring_time, font=(FONT_LIGHT, font_size))
        self.ring.itemconfigure(self.ring_caption, text=caption)
        if self.notice_label.cget("text") != self.notice:
            self.notice_label.configure(text=self.notice)
            if self.notice:
                self.notice_label.pack(after=self.ring, pady=(0, px(self.root, 12)))
            else:
                self.notice_label.pack_forget()
            self.fit_window()

    def tick(self):
        now = time.monotonic()
        elapsed = max(0.0, now - self.last_tick)
        self.last_tick = now
        if self.running:
            if self.resting:
                self.rest_seconds += elapsed
                if self.rest_seconds >= self.settings["rest_minutes"] * 60:
                    self.finish_rest()
            else:
                if self.get_idle_seconds() < AWAY_AFTER_SECONDS:
                    self.active_seconds += elapsed
                if self.active_seconds >= self.settings["work_minutes"] * 60:
                    self.begin_rest()
        self.update_status()
        self.root.after(1000, self.tick)

    def begin_rest(self):
        self.active_seconds = 0
        if self.settings["prompt"]:
            self.show_prompt()
        else:
            self.start_rest()

    def show_prompt(self):
        message_flags = 0x00000004 | 0x00000040 | 0x00040000 | 0x00001000
        question = "Start Windows Night light now?" if self.settings["night_light"] else "Start your rest now?"
        answer = ctypes.windll.user32.MessageBoxW(
            self.root.winfo_id(),
            f"Your eyes have earned a pause.\n\n{question}",
            "EyeSee - Time for a visual rest",
            message_flags,
        )
        if answer == 6:
            self.start_rest()

    def start_rest(self):
        if self.resting:
            return
        if self.settings["night_light"]:
            try:
                if not self.system_night_light_enabled():
                    self.set_system_night_light(True)
                    self.night_light_changed = True
            except RuntimeError as error:
                self.notice = str(error)
                return
        self.notice = ""
        self.resting = True
        self.rest_seconds = 0
        self.update_status()

    def restore_night_light(self):
        if self.night_light_changed:
            try:
                self.set_system_night_light(False)
            except RuntimeError:
                pass
            self.night_light_changed = False

    def stop_rest(self):
        self.restore_night_light()
        self.resting = False
        self.rest_seconds = 0

    def finish_rest(self):
        self.stop_rest()
        self.update_status()
        if self.settings["alarm"]:
            threading.Thread(target=self.play_completion_alarm, daemon=True).start()

    @staticmethod
    def play_completion_alarm():
        try:
            winsound.Beep(888, 500)
        except (RuntimeError, OSError):
            pass

    def system_night_light_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, NIGHT_LIGHT_KEY, 0, winreg.KEY_READ) as key:
                data, _ = winreg.QueryValueEx(key, "Data")
            return len(data) > 18 and data[18] == 0x15
        except OSError:
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
        except OSError as error:
            raise RuntimeError(f"Could not change Windows Night light: {error}") from error

    def close_app(self):
        self.close_settings()
        self.stop_rest()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    EyeSeeApp().run()
