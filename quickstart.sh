#!/bin/bash
# Quick start script for local development

set -e

echo "🚀 Digital Asset Protection System - Quick Start"
echo "================================================"
echo ""

# Check dependencies
echo "📋 Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install from https://www.python.org/downloads/"
    exit 1
fi
echo "✓ Python 3 found: $(python3 --version)"

if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Install from https://nodejs.org/"
    exit 1
fi
echo "✓ Node.js found: $(node --version)"

if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker not found (optional for local dev)"
fi

echo ""
echo "🔧 Setting up backend..."
cd backend

# Create venv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate || . venv/Scripts/activate

# Copy .env if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ Created .env file (using defaults)"
fi

# Install dependencies
echo "Installing Python dependencies (this may take a few minutes)..."
pip install -q -r requirements.txt

echo "✓ Backend ready"
cd ..

echo ""
echo "🎨 Setting up frontend..."
cd frontend

# Copy .env if not exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ Created .env file"
fi

# Install dependencies
echo "Installing Node dependencies..."
npm install --silent

echo "✓ Frontend ready"
cd ..

echo ""
echo "📁 Creating data directories..."
mkdir -p data/samples data/uploads
mkdir -p tests/results

echo ""
echo "🎯 Generated sample images..."
cd tests
python3 generate_samples.py
cd ..

echo ""
echo "================================================"
echo "✅ Setup complete!"
echo "================================================"
echo ""
echo "📚 Next steps:"
echo ""
echo "1. Start backend (Terminal 1):"
echo "   cd backend && source venv/bin/activate && python -m uvicorn main:app --reload"
echo ""
echo "2. Start frontend (Terminal 2):"
echo "   cd frontend && npm run dev"
echo ""
echo "3. Open browser:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "4. Run tests:"
echo "   cd tests && python test_robustness.py"
echo ""
echo "================================================"
echo "📖 Documentation:"
echo "   - README.md (Project overview)"
echo "   - DEPLOYMENT_GUIDE.md (Google Cloud setup)"
echo "================================================"
