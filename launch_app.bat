@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_CMD="

where python >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  where py >nul 2>nul
  if %errorlevel%==0 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  if exist "C:\Users\aksha\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_CMD=C:\Users\aksha\AppData\Local\Programs\Python\Python313\python.exe"
  )
)

if not defined PYTHON_CMD (
  echo Could not find Python.
  echo Please install Python or add it to PATH, then try again.
  pause
  exit /b 1
)

echo Starting CAS Mutual Fund Analyzer...
call %PYTHON_CMD% -m streamlit run streamlit_app.py

if errorlevel 1 (
  echo.
  echo Streamlit launch failed. Installing required packages and retrying...
  call %PYTHON_CMD% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
  )
  call %PYTHON_CMD% -m streamlit run streamlit_app.py
)

endlocal
