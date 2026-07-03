#!/bin/bash

# Pastikan script dijalankan di dalam direktori tempat bot berada atau di systemd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")/discord-bot-weekly"

# Jika discord-bot-weekly tidak ada di parent, minta path manual
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Folder discord-bot-weekly tidak ditemukan di $PROJECT_DIR"
    echo "Silakan atur path secara manual di script ini."
    exit 1
fi

CURRENT_USER=$(whoami)
SERVICE_NAME="weekly-discord-bot.service"
SERVICE_TEMPLATE="$SCRIPT_DIR/weekly-discord-bot.service.template"
TARGET_FILE="/etc/systemd/system/$SERVICE_NAME"

echo "Membangun file service untuk user: $CURRENT_USER"
echo "Working Directory: $PROJECT_DIR"

# Buat file service dari template
cat > "$SCRIPT_DIR/$SERVICE_NAME" <<EOF
[Unit]
Description=Weekly Transaction Pipeline Discord Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/env node index.js
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=weekly-discord-bot

# Loads environment variables from the .env file
EnvironmentFile=$PROJECT_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

echo "File service berhasil dibuat di $SCRIPT_DIR/$SERVICE_NAME"

# Tanya apakah ingin menginstall langsung
read -p "Apakah Anda ingin menginstall dan menjalankan service ini sekarang? (Membutuhkan akses sudo) [y/N]: " install_choice
if [[ "$install_choice" =~ ^[Yy]$ ]]; then
    sudo cp "$SCRIPT_DIR/$SERVICE_NAME" "$TARGET_FILE"
    sudo systemctl daemon-reload
    sudo systemctl enable $SERVICE_NAME
    sudo systemctl start $SERVICE_NAME
    echo "Service $SERVICE_NAME telah diinstall dan dijalankan!"
    echo "Gunakan 'sudo systemctl status $SERVICE_NAME' untuk melihat status."
else
    echo "Instalasi dibatalkan. Anda dapat memindahkan file service secara manual ke /etc/systemd/system/"
fi
