@echo off
rem Double-click to start the spider cursor. Quit with Ctrl+Shift+Q.
where pythonw >nul 2>nul && (start "" pythonw "%~dp0spider_cursor.py") || (python "%~dp0spider_cursor.py")
