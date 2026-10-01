#!/bin/bash
# ==============================================================================
# The Summit of Realms - Startup Script
# Designed for Facilitator's laptop (offline local Wi-Fi, 0.0.0.0:5000)
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "================================================================="
echo "        THE SUMMIT OF REALMS - GEOPOLITICAL WORKSHOP             "
echo "================================================================="

# Check Python3 availability
if ! command -v python3 &> /dev/null; then
    echo "[-] Error: python3 is not installed or not in PATH."
    exit 1
fi

# Set up virtual environment if not present
if [ ! -d "venv" ]; then
    echo "[+] Initializing Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install required dependencies
echo "[+] Checking dependencies..."
pip install -r requirements.txt --quiet

echo "[+] Launching local simulation server..."
python3 app.py
