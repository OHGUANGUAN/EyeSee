@echo off
set "APP_DIR=%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
	echo Python was not found. Install Python 3 from python.org and select "Add python.exe to PATH", then run EyeSee.bat again.
	pause
	exit /b 1
)
start "EyeSee" pythonw "%APP_DIR%eye_see.py"