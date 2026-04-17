@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   Content DNA - Universal Tracking System
echo    (Production-Grade - Enterprise - 2026)
echo ============================================================
echo.

:: Check for .env file
if not exist ".env" (
    echo [!] No .env file found.
    echo [!] Copying .env.example to .env ...
    copy ".env.example" ".env"
    echo [!] Please edit .env with your Supabase/NVIDIA keys later.
)

:: Create directories
echo [+] Ensuring data directories exist...
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\faiss" mkdir "data\faiss"

:: Choice: Docker or Local
echo.
echo Select Execution Mode:
echo [1] Docker (Complete Stack)
echo [2] Local (Backend only)
echo [3] Run Robustness Tests
echo [4] Exit
echo.

set /p choice="Enter choice [1-4]: "

if "%choice%"=="1" (
    echo [+] Starting Docker Compose...
    docker-compose up --build
) else if "%choice%"=="2" (
    echo [+] Checking Python Environment...
    if not exist "venv" (
        echo [+] Creating virtual environment...
        python -m venv venv
    )
    echo [+] Activating venv...
    call venv\Scripts\activate
    echo [+] Installing requirements...
    pip install -r requirements.txt
    echo [+] Starting FastAPI server...
    python main.py
) else if "%choice%"=="3" (
    echo [+] Starting Robustness Tests...
    if not exist "venv" (
        echo [!] No venv found. Creating one first...
        python -m venv venv
        call venv\Scripts\activate
        pip install -r requirements.txt
    ) else (
        call venv\Scripts\activate
    )
    echo [+] Running test matrix...
    python tests\test_attacks.py
    pause
) else (
    echo Exiting...
)

pause
