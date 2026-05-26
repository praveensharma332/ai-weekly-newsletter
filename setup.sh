#!/usr/bin/env bash

# ==============================================================================
# AI Weekly Newsletter Setup and Dependency Installer
# ==============================================================================

set -euo pipefail

# Text color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0;3m' # No Color
BOLD='\033[1m'

echo -e "${BLUE}${BOLD}======================================================================"
echo -e "         AI WEEKLY NEWSLETTER GENERATOR - INITIALIZATION"
echo -e "======================================================================${NC}"

# 1. Create directory structure
echo -e "\n${BLUE}[1/5] Setting up local directory structures...${NC}"
mkdir -p app/collectors app/summarizers app/generators app/clustering app/storage app/scheduler app/prompts app/templates app/config app/providers app/utils
mkdir -p data/newsletters data/raw_articles data/embeddings data/database logs
echo -e "${GREEN}✔ Storage directories successfully configured.${NC}"

# 2. Check for Python 3.12 or general python3
echo -e "\n${BLUE}[2/5] Checking Python environment...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✘ Error: Python3 is not installed on your system.${NC}"
    echo -e "Please install Python 3.12+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✔ Found Python ${PYTHON_VERSION}${NC}"

# 3. Create virtual environment
echo -e "\n${BLUE}[3/5] Setting up Virtual Environment (venv)...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✔ Virtual environment successfully initialized.${NC}"
else
    echo -e "${YELLOW}ℹ Virtual environment already exists. Skipping creation.${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# 4. Install dependencies
echo -e "\n${BLUE}[4/5] Installing project dependencies...${NC}"
# Check if uv is installed for blazing-fast dependency compilation
if command -v uv &> /dev/null; then
    echo -e "${GREEN}✔ Found 'uv' package manager. Compiling dependencies with uv...${NC}"
    uv pip install --system -r requirements.txt || uv pip install -r requirements.txt
else
    echo -e "${YELLOW}ℹ 'uv' not found. Upgrading pip and compiling dependencies standard...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
fi
echo -e "${GREEN}✔ Dependencies successfully compiled and installed.${NC}"

# 5. Handle environment variables file .env
echo -e "\n${BLUE}[5/5] Checking .env configuration file...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠ Created new '.env' from '.env.example'.${NC}"
    echo -e "${YELLOW}⚠ Please edit '.env' and insert your actual GEMINI_API_KEY.${NC}"
else
    echo -e "${GREEN}✔ '.env' configuration file detected.${NC}"
fi

# 6. Initialize SQLite Database Tables
echo -e "\n${BLUE}[+] Initializing SQLite database tables...${NC}"
python3 -c "from app.storage.database import init_db; init_db()"
echo -e "${GREEN}✔ Database tables successfully initialized in 'data/database/newsletter.db'.${NC}"

# 7. Validate Gemini API setup
echo -e "\n${BLUE}[+] Verifying Gemini API credentials...${NC}"
if [ -f ".env" ]; then
    API_KEY=$(grep -E "^GEMINI_API_KEY=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    if [ -z "$API_KEY" ] || [ "$API_KEY" == "YOUR_GEMINI_API_KEY_HERE" ]; then
        echo -e "${RED}⚠ Warning: GEMINI_API_KEY is not yet configured.${NC}"
        echo -e "Please replace 'YOUR_GEMINI_API_KEY_HERE' in your .env file with your key from Google AI Studio."
    else
        echo -e "${GREEN}✔ GEMINI_API_KEY detected in .env.${NC}"
        # Validate connection using python quick-run
        echo -e "Testing Google GenAI module import..."
        python3 -c "import google.generativeai as genai; print('Import check: OK')"
    fi
fi

echo -e "\n${GREEN}${BOLD}======================================================================"
echo -e "              SETUP AND INITIALIZATION COMPLETE!"
echo -e "======================================================================${NC}"
echo -e "To get started:"
echo -e " 1. ${BOLD}source venv/bin/activate${NC} (Activate virtual environment)"
echo -e " 2. Configure your actual ${BOLD}GEMINI_API_KEY${NC} inside '.env'"
echo -e " 3. Run a manual dry-run: ${BOLD}python run.py --dry-run${NC}"
echo -e " 4. Launch the local Dashboard: ${BOLD}python run.py${NC}"
echo -e "======================================================================"
