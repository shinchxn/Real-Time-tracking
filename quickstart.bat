@echo off
REM Quick start script for local development (Windows)

echo 🚀 Digital Asset Protection System - Quick Start
echo ================================================
echo.

REM Check dependencies
echo 📋 Checking dependencies...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Install from https://www.python.org/downloads/
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo ✓ Python found: %%i

node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js not found. Install from https://nodejs.org/
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo ✓ Node.js found: %%i

echo.
echo 🔧 Setting up backend...
cd backend

REM Create venv
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate

REM Copy .env if not exists
if not exist ".env" (
    copy .env.example .env
    echo ✓ Created .env file (using defaults)
)

REM Install dependencies
echo Installing Python dependencies (this may take a few minutes)...
pip install -q -r requirements.txt

echo ✓ Backend ready
cd ..

echo.
echo 🎨 Setting up frontend...
cd frontend

REM Copy .env if not exists
if not exist ".env" (
    copy .env.example .env
    echo ✓ Created .env file
)

REM Install dependencies
echo Installing Node dependencies...
npm install --silent

echo ✓ Frontend ready
cd ..

echo.
echo 📁 Creating data directories...
if not exist "data\samples" mkdir data\samples
if not exist "data\uploads" mkdir data\uploads
if not exist "tests\results" mkdir tests\results

echo.
echo 🎯 Generating sample images...
cd tests
python generate_samples.py
cd ..

echo.
echo ================================================
echo ✅ Setup complete!
echo ================================================
echo.
echo 📚 Next steps:
echo.
echo 1. Start backend (Terminal 1):
echo    cd backend
echo    venv\Scripts\activate
echo    python -m uvicorn main:app --reload
echo.
echo 2. Start frontend (Terminal 2):
echo    cd frontend
echo    npm run dev
echo.
echo 3. Open browser:
echo    Frontend: http://localhost:3000
echo    Backend API: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo 4. Run tests:
echo    cd tests
echo    python test_robustness.py
echo.
echo ================================================
echo 📖 Documentation:
echo    - README.md (Project overview)
echo    - DEPLOYMENT_GUIDE.md (Google Cloud setup)
echo ================================================
