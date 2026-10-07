#!/bin/bash
# GuntingKlip auto-installer — Ubuntu/Debian (VPS).
# Cara pakai:  bash install.sh
# Yang dilakukan:
#   1. cek python3 + ffmpeg (install via apt kalau belum ada & punya sudo)
#   2. bikin venv .venv + install requirements.txt (pinned)
#   3. simpan URL + API key 9Router ke ~/.config/guntingklip/ (chmod 600)
#   4. (opsional) pre-download model Whisper `small` (~500MB)
set -e
cd "$(dirname "$0")"

echo "✂️  GuntingKlip installer"
echo ""

# --- 1. dependensi sistem ---
need_apt=0
command -v python3 >/dev/null || { echo "❌ python3 tidak ada."; need_apt=1; }
command -v ffmpeg >/dev/null || { echo "❌ ffmpeg tidak ada."; need_apt=1; }
if [ "$need_apt" = 1 ]; then
  if command -v sudo >/dev/null && sudo -n true 2>/dev/null; then
    echo "📦 Install python3 + ffmpeg via apt..."
    sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-venv ffmpeg
  else
    echo "❌ Butuh python3 & ffmpeg. Install manual: sudo apt install python3 python3-venv ffmpeg"
    exit 1
  fi
fi
echo "✅ python3 + ffmpeg OK"

# --- 2. venv + pip ---
if [ ! -d .venv ]; then
  echo "📦 Bikin virtualenv..."
  python3 -m venv .venv
fi
echo "📦 Install Python packages (pinned)..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
echo "✅ Python packages OK"

# --- 3. config 9Router ---
CFG="$HOME/.config/guntingklip"
mkdir -p "$CFG"
chmod 700 "$HOME/.config" 2>/dev/null || true
chmod 700 "$CFG"

cur_url=""
[ -f "$CFG/9router_url" ] && cur_url=$(cat "$CFG/9router_url")
read -p "🌐 9Router URL [${cur_url:-http://127.0.0.1:20128/v1}]: " in_url
echo "${in_url:-${cur_url:-http://127.0.0.1:20128/v1}}" > "$CFG/9router_url"

if [ -f "$CFG/9router_key" ]; then
  read -p "🔑 API key 9Router sudah tersimpan. Ganti? (y/N): " ganti
  if [ "$ganti" != "y" ] && [ "$ganti" != "Y" ]; then
    echo "   (key lama dipertahankan)"
  else
    read -s -p "🔑 API key 9Router baru: " in_key; echo ""
    [ -n "$in_key" ] && echo "$in_key" > "$CFG/9router_key"
  fi
else
  read -s -p "🔑 API key 9Router: " in_key; echo ""
  [ -n "$in_key" ] && echo "$in_key" > "$CFG/9router_key"
fi
chmod 600 "$CFG/9router_key" 2>/dev/null || true
echo "✅ Config tersimpan di $CFG (chmod 600)"

# --- 4. pre-download model whisper (opsional) ---
read -p "⬇️  Download model Whisper 'small' sekarang? (~500MB, sekali aja) (Y/n): " dl
if [ "$dl" != "n" ] && [ "$dl" != "N" ]; then
  echo "⬇️  Download model..."
  .venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
  echo "✅ Model siap"
fi

chmod +x klip.sh guntingklip.py 2>/dev/null || true
echo ""
echo "🎉 Selesai! Cara pakai:"
echo "   bash klip.sh video.mp4"
echo "   (atau kirim video + info campaign ke chat, biar asisten yang jalanin)"
