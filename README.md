# EyeSee

EyeSee is a small Windows desktop app that tracks active laptop use and enables the built-in Windows Night light after a configurable interval.

## Run

Open PowerShell in this folder and run:

```powershell
python eye_see.py
```

For a background launch without a console window, double-click `run_background.bat`. It starts EyeSee minimized while keeping its settings window available from the taskbar.

When tray support is installed, EyeSee also appears in the Windows system tray. Right-click the EyeSee tray icon to show the settings, pause/resume, or exit the app. The main window remains visible in the taskbar, and its `X` exits the app.

## Build A Standalone EXE

Double-click `build_exe.bat`. It installs the tray dependencies and PyInstaller if needed, then creates `dist\EyeSee.exe`. Run that executable to use EyeSee on a Windows laptop without Python installed.

To start it automatically when Windows logs in, press `Win+R`, enter `shell:startup`, and place a shortcut to `dist\EyeSee.exe` in that folder.

The app starts with a 60-minute work interval, a 10-minute rest, and a prompt enabled. Use **Save settings** to change the schedule. Use the window `X` or tray **Exit** to end the process.

The timer counts active input time, rather than time the laptop is idle. During a rest, Windows Night light changes the display without blocking keyboard or mouse activity. Closing the window ends the app process and restores Night light if EyeSee enabled it. Settings are saved as `settings.json` beside the script or executable.

EyeSee does not connect to the internet or send telemetry. It uses only local Windows APIs and the local settings file while running. The optional `build_exe.bat` script may download PyInstaller once during setup if PyInstaller is not already installed.