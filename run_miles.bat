@echo off
rem Double-click to start Miles hanging from the top of your screen. Quit with Ctrl+Shift+Q.
where pythonw >nul 2>nul && (start "" pythonw "%~dp0miles_hanging.py") || (python "%~dp0miles_hanging.py")
