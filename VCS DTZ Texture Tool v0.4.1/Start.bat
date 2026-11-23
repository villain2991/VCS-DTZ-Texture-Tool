@echo off
cd /d "%~dp0"
set "PYC="
set "PYW="
where py >nul 2>nul && (set "PYC=py -3" & set "PYW=pyw -3")
if not defined PYC where python >nul 2>nul && (set "PYC=python" & set "PYW=pythonw")
if not defined PYC (
  echo Python was not found. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer, then run Start.bat again.
  pause
  exit /b 1
)
%PYC% -c "import PIL, tkinter" >nul 2>nul
if errorlevel 1 (
  echo Installing the Pillow image library ^(one time^)...
  %PYC% -m pip install pillow
  %PYC% -c "import PIL, tkinter" >nul 2>nul
  if errorlevel 1 (
    echo.
    echo Setup failed. Make sure Python was installed with tcl/tk support and you are online.
    pause
    exit /b 1
  )
)
start "" %PYW% dtz_gui.py
exit /b 0
