# EyeSee

EyeSee is a small Windows desktop app that tracks active laptop use and enables the built-in Windows Night light after a configurable interval.

The timer starts automatically when EyeSee opens. The window is 350 pixels wide and resizes its height to fit the settings panel.

When the rest timer ends, EyeSee will provide a beep to inform the user that the rest time is over.

## Download

1. Install Python 3 from [python.org](https://www.python.org/downloads/windows/). In the installer, select **Add python.exe to PATH** so EyeSee can find `python` and `pythonw`.
2. Download EyeSee in one of two ways:
   - **ZIP:** on the [EyeSee GitHub page](https://github.com/OHGUANGUAN/EyeSee), click **Code** > **Download ZIP**, then right-click the downloaded file and choose **Extract All...**.
   - **Git:** run `git clone https://github.com/OHGUANGUAN/EyeSee.git`.
3. Move the EyeSee folder somewhere permanent, such as `C:\Users\<you>\EyeSee`. Keep it there if you set EyeSee to start at log on (see below), because the task points to this folder.

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

## Start Automatically at Log On

EyeSee works best when it starts as soon as you log on. That way the timer is always running in the background, and you never have to remember to open it. The steps below set this up with Windows Task Scheduler.

> **Note:** EyeSee is Windows-only. It uses the Windows registry to control Night light and Win32 APIs to detect idle time, so it does not run on macOS or Linux.

### Windows (Task Scheduler)

1. Open **Task Scheduler** and click **Create Task...** (not *Create Basic Task*).
2. **General** tab: name the task `EyeSee` and select **Run only when user is logged on**.
3. **Triggers** tab: click **New...**, set *Begin the task* to **At log on**, choose **Specific user** (your account), and click **OK**.
4. **Actions** tab: click **New...** and set:
   - *Program/script*: the full path to `EyeSee.bat`, for example `C:\Users\<you>\EyeSee\EyeSee.bat`
   - *Start in*: the EyeSee folder, for example `C:\Users\<you>\EyeSee`

   Point the task at `EyeSee.bat`, not `eye_see.py`. The batch file checks that Python is installed and starts EyeSee with `pythonw`, so no console window stays open. A console window may flash briefly at log on while the batch file runs.
5. **Conditions** tab: clear **Start the task only if the computer is on AC power**, or EyeSee will not start when your laptop is on battery.
6. **Settings** tab: clear **Stop the task if it runs longer than 3 days**, so Windows does not close EyeSee during long sessions.
7. Click **OK**. To test the task, right-click it and choose **Run**.

## Settings

The default schedule is a 60-minute work interval, a 10-minute rest, and a prompt before Night light starts. Use **Save schedule** to change the intervals. Click the ⚙ button to show the preferences (prompt before rest, beep when rest ends) and use **Save preferences** to keep them. Work intervals can be 1 to 1440 minutes; rests can be 1 to 180 minutes.

The timer counts active input time, rather than time the laptop is idle. During a rest, Windows Night light changes the display without blocking keyboard or mouse activity. Closing the window ends the app process and restores Night light if EyeSee enabled it. Settings are saved as `settings.json` beside the script. This file is created on first save and is excluded from git, so each user keeps their own preferences.

## Privacy

EyeSee does not connect to the internet or send telemetry. It uses local Windows APIs and the local settings file while running. The optional tray packages are downloaded only when you install them yourself with `pip`.