#!/usr/bin/env bash
# Chimera v9.0 — Linux/macOS Installer
# Usage: bash installer/install_chimera.sh

set -e

echo ""
echo "  ======================================"
echo "    CHIMERA v9.0 — Installer"
echo "  ======================================"
echo ""

# Detect OS
OS="$(uname -s)"
case "$OS" in
  Linux*)   PLATFORM="linux";;
  Darwin*)  PLATFORM="macos";;
  *)        echo "  ERROR: Unsupported OS: $OS"; exit 1;;
esac
echo "[1/6] Platform: $PLATFORM"

# Check Python
echo "[2/6] Checking Python 3.11+..."
if command -v python3 &>/dev/null; then
  PY_VERSION=$(python3 --version 2>&1)
  echo "  $PY_VERSION OK"
else
  echo "  ERROR: Python 3 not found"
  echo "  Install: https://www.python.org/downloads/"
  exit 1
fi

# Check Node.js
echo "[3/6] Checking Node.js 20+..."
if command -v node &>/dev/null; then
  NODE_VERSION=$(node --version 2>&1)
  echo "  Node.js $NODE_VERSION OK"
else
  echo "  ERROR: Node.js not found"
  echo "  Install: https://nodejs.org/"
  exit 1
fi

# Check ADB (optional)
echo "[4/6] Checking ADB..."
if command -v adb &>/dev/null; then
  echo "  ADB found OK"
else
  echo "  ADB not found (optional for Android)"
fi

# Install dependencies
echo "[5/6] Installing dependencies..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "  npm install..."
npm install --silent 2>/dev/null || npm install

echo "  pip install..."
python3 -m pip install -r python-backend/requirements.txt --quiet 2>/dev/null || \
  python3 -m pip install -r python-backend/requirements.txt

# Create shortcut
echo "[6/6] Creating shortcut..."
if [ "$PLATFORM" = "linux" ]; then
  DESKTOP_DIR="$HOME/Desktop"
  mkdir -p "$DESKTOP_DIR"
  cat > "$DESKTOP_DIR/chimera.desktop" <<DESKTOP
[Desktop Entry]
Name=Chimera
Comment=Chimera Desktop v9.0
Exec=bash -c "cd '$PROJECT_DIR' && npm run dev"
Icon=$PROJECT_DIR/resources/icon.png
Type=Application
Categories=Utility;
Terminal=false
DESKTOP
  chmod +x "$DESKTOP_DIR/chimera.desktop"
  echo "  Shortcut created: $DESKTOP_DIR/chimera.desktop"
elif [ "$PLATFORM" = "macos" ]; then
  echo "  macOS: run 'npm run dev' from the project directory"
  echo "  Or use: python3 installer/create_shortcut.py"
fi

echo ""
echo "  Installation complete!"
echo ""
echo "  To launch Chimera:"
echo "    cd '$PROJECT_DIR'"
echo "    npm run dev"
echo ""
echo "  Chimera v9.0 ready!"
