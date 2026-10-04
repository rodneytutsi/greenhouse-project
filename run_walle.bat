@echo off
rem Double-click to start WALL-E as your cursor. Quit with Ctrl+Shift+Q.
where pythonw >nul 2>nul && (start "" pythonw "%~dp0walle_cursor.py") || (python "%~dp0walle_cursor.py")
