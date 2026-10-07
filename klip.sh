#!/bin/bash
# GuntingKlip versi gampang — tinggal jawab pertanyaan, script yang jalanin.
# Cara pakai: bash klip.sh [video.mp4 / URL video]
set -e
cd "$(dirname "$0")"

VIDEO="$1"
CONFIG=".klip-config"

# 1. Video: argumen, atau tanya
if [ -z "$VIDEO" ]; then
  read -p "📹 Path file video / URL: " VIDEO
fi
[ -z "$VIDEO" ] && { echo "❌ Video wajib diisi."; exit 1; }

# Kalau URL, download dulu
if [[ "$VIDEO" =~ ^https?:// ]]; then
  echo "⬇️  Download video..."
  fname="source_$(date +%Y%m%d_%H%M%S).mp4"
  curl -L -o "$fname" "$VIDEO"
  VIDEO="$fname"
fi
[ -f "$VIDEO" ] || { echo "❌ File tidak ditemukan: $VIDEO"; exit 1; }

# 2. Load default dari config sebelumnya (biar nggak ketik ulang)
if [ -f "$CONFIG" ]; then
  source "$CONFIG"
fi

tanya() { # tanya <var> <label> <default>
  local val
  read -p "$2 [$3]: " val
  printf -v "$1" "%s" "${val:-$3}"
}

echo ""
echo "📋 Info campaign (Enter = pakai default):"
tanya TOPIK   "🏷️  Topik video"        "${TOPIK:-}"
tanya CAMPAIGN "📢 Nama campaign"      "${CAMPAIGN:-}"
tanya RATE    "💰 Rate (cth: Rp 5.000 / 1k views)" "${RATE:-}"
tanya LINK    "🔗 Link join campaign" "${LINK:-}"
tanya NCLIP   "✂️  Jumlah klip"       "${NCLIP:-3}"

# Simpan sebagai default berikutnya
cat > "$CONFIG" <<EOF
TOPIK="$TOPIK"
CAMPAIGN="$CAMPAIGN"
RATE="$RATE"
LINK="$LINK"
NCLIP="$NCLIP"
EOF

echo ""
echo "🚀 Gas! Bikin $NCLIP klip dari $VIDEO ..."
.venv/bin/python guntingklip.py "$VIDEO" \
  --topik "$TOPIK" \
  --campaign "$CAMPAIGN" \
  --rate "$RATE" \
  --join-link "$LINK" \
  --clips "$NCLIP"

echo ""
echo "✅ Selesai! Klip ada di clips/, caption di clips/caption.txt"
echo "📱 Download klip ke HP, upload manual ke TikTok, tempel hashtag + Keranjang Kuning."
