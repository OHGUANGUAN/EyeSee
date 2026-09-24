@echo off
set "APP_DIR=%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
	echo Python was not found. Build and run dist\EyeSee.exe instead, or install Python.
	pause
	exit /b 1
)
start "EyeSee" pythonw "%APP_DIR%eye_see.py"