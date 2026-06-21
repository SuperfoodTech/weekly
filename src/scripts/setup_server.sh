#!/bin/bash
# scripts/setup_server.sh - Best Practice Setup with UV, Venv, & Docker

set -e
echo "🚀 Starting Modern Server Setup (UV + Docker)..."

# 1. Update & Install Basic Tools
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get install -y curl git wget unzip gnupg2 ca-certificates

# 2. Install Docker (V2)
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    # Adding current user to docker group so sudo isn't needed later
    sudo usermod -aG docker $USER
    echo "✅ Docker installed."
else
    echo "✅ Docker already installed."
fi

# 3. Install UV (Modern Python Package Manager)
if ! command -v uv &> /dev/null; then
    echo "⚡ Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Ensure uv is in the path for the rest of the script
    export PATH="$HOME/.local/bin:$PATH"
    source $HOME/.cargo/env || true
fi

# 4. Install Google Chrome (Headless for Scrapers)
if ! command -v google-chrome &> /dev/null; then
    echo "🌐 Installing Google Chrome..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
    sudo apt-get update
    sudo apt-get install -y google-chrome-stable
    echo "✅ Chrome installed."
else
    echo "✅ Chrome already installed."
fi

# 5. Setup Virtual Environment & Dependencies
echo "🐍 Creating Virtual Environment and installing dependencies..."
# Create venv if not exists
if [ ! -d ".venv" ]; then
    uv venv
fi

# Install dependencies into the venv
uv pip install pandas requests sqlalchemy psycopg2-binary selenium python-dotenv openpyxl

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ SETUP SELESAI!"
echo "  1. Jalankan 'source .venv/bin/activate' sebelum running script."
echo "  2. PENTING: Silakan LOGOUT dan LOGIN kembali ke SSH agar"
echo "     izin Docker ($USER) aktif tanpa sudo."
echo "  3. Terakhir, jalankan: docker compose up -d"
echo "═══════════════════════════════════════════════════════════════"
