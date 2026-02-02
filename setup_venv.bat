@echo off
setlocal EnableExtensions EnableDelayedExpansion

set ROOT_DIR=%~dp0
cd /d "%ROOT_DIR%"

set PYTHON_CMD=python
set PYTHON_ARGS=
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  set PYTHON_CMD=py
  set PYTHON_ARGS=-3
)

%PYTHON_CMD% %PYTHON_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)"
if %ERRORLEVEL% NEQ 0 (
  echo Python 3.10+ required.
  exit /b 1
)

if not exist ".venv" (
  echo Creating virtual environment at .venv...
  %PYTHON_CMD% %PYTHON_ARGS% -m venv .venv
) else (
  echo Using existing virtual environment at .venv.
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip

if exist "requirements.txt" (
  python -m pip install -r requirements.txt
)
if exist "backend\requirements.txt" (
  python -m pip install -r backend\requirements.txt
)

python -m pip check

echo.
echo Venv ready. Activate with: .venv\Scripts\activate
