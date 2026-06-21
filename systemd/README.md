# Panduan Deploy Discord Bot dengan Systemd

File service systemd ini digunakan untuk menjalankan Discord Bot secara otomatis di background server Linux Anda, memulai ulang bot jika terjadi crash, dan menyalakannya secara otomatis saat server booting.

## Langkah-langkah Deployment:

1. **Salin file service ke folder systemd sistem:**
   ```bash
   sudo cp weekly-discord-bot.service /etc/systemd/system/
   ```

2. **Sesuaikan Konfigurasi (Jika Diperlukan):**
   Buka file `/etc/systemd/system/weekly-discord-bot.service` menggunakan editor teks Anda (misal `nano` atau `vim`):
   ```bash
   sudo nano /etc/systemd/system/weekly-discord-bot.service
   ```
   Pastikan parameter berikut sudah sesuai:
   - `User`: Username Linux Anda di server (saat ini diset `akbarhann`).
   - `WorkingDirectory`: Path absolut ke folder `discord-bot-weekly` Anda.

3. **Reload daemon systemd:**
   Beritahu systemd bahwa ada file service baru:
   ```bash
   sudo systemctl daemon-reload
   ```

4. **Aktifkan Autostart saat Booting:**
   ```bash
   sudo systemctl enable weekly-discord-bot
   ```

5. **Nyalakan Bot Service:**
   ```bash
   sudo systemctl start weekly-discord-bot
   ```

## Perintah Manajemen Layanan:

* **Melihat Status Layanan (Aktif/Mati):**
  ```bash
  sudo systemctl status weekly-discord-bot
  ```

* **Mematikan Layanan:**
  ```bash
  sudo systemctl stop weekly-discord-bot
  ```

* **Memulai Ulang Layanan (Restart):**
  ```bash
  sudo systemctl restart weekly-discord-bot
  ```

* **Membaca Log Live dari Bot:**
  ```bash
  journalctl -u weekly-discord-bot -f
  ```
