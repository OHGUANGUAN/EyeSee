# EyeSee

EyeSee is a small Windows desktop app that tracks active laptop use and enables the built-in Windows Night light after a configurable interval.

The timer starts automatically when EyeSee opens. The window is fixed at 380x430 pixels.

## Run

Double-click `EyeSee.bat` to start EyeSee without opening a console window. The batch file launches `eye_see.py` with `pythonw`.

You can also run the app from PowerShell:

```powershell
python eye_see.py
```

Python must be installed and available as `python` and `pythonw`.

When `pystray` and `Pillow` are installed, EyeSee also appears in the Windows system tray. Right-click the EyeSee tray icon to show the settings, pause/resume, or exit the app. Without those optional packages, the main window still works normally.

## Optional Tray Support

Install the optional tray dependencies with:

```powershell
python -m pip install pystray Pillow
```

## Settings

The default schedule is a 30-minute work interval, a 10-minute rest, and a prompt before Night light starts. Use **Save settings** to change the schedule. Work intervals can be 1 to 1440 minutes; rests can be 1 to 180 minutes.

The timer counts active input time, rather than time the laptop is idle. During a rest, Windows Night light changes the display without blocking keyboard or mouse activity. Closing the window ends the app process and restores Night light if EyeSee enabled it. Settings are saved as `settings.json` beside the script.

## Privacy

EyeSee does not connect to the internet or send telemetry. It uses local Windows APIs and the local settings file while running. The optional tray packages are downloaded only when you install them yourself with `pip`.