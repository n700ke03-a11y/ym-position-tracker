#!/usr/bin/env bash
# Установка трекера позиций на чистый Ubuntu 24.04 (запускать под root)
set -euo pipefail
REPO=https://github.com/n700ke03-a11y/ym-position-tracker.git
DIR=/opt/ym-position-tracker

# файл подкачки 2 ГБ — страховка для сервера с 1 ГБ памяти
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

apt-get update -y
apt-get install -y python3-venv git
timedatectl set-timezone Europe/Moscow

if [ -d "$DIR/.git" ]; then git -C "$DIR" pull; else git clone "$REPO" "$DIR"; fi
cd "$DIR"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium

# запуск каждый час в :17
cat > /etc/cron.d/ym-tracker <<CRON
17 * * * * root cd $DIR && git pull -q; SHEET_ID=\$(cat $DIR/sheet_id) GOOGLE_CREDENTIALS="\$(cat $DIR/credentials.json)" $DIR/.venv/bin/python tracker.py >> $DIR/run.log 2>&1
CRON
chmod 644 /etc/cron.d/ym-tracker

echo
echo "Готово. Проверка парсера без записи в таблицу:"
.venv/bin/python test_local.py
