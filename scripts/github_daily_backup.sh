#!/bin/bash
# Backup harian GuntingKlip ke GitHub (dasrams31/guntingklip)
# Dijalankan via cron muse tiap hari. Token dibaca dari config/github_token (chmod 600).
# Repo GuntingKlip langsung di-push dari working directory (tidak pakai staging).
# .gitignore mengecualikan: .venv/, clips*/ output, video/audio sumber, cache.
set -e
cd "$HOME/workspace/guntingklip"
TOKEN_FILE="$HOME/workspace/mc-portal/config/github_token"

git add -A
if git diff --cached --quiet; then
  echo "no changes to push"
  exit 0
fi
git -c user.name="dasrams31" -c user.email="ramadanadipa176@gmail.com" \
  commit -qm "Daily backup $(date +%F)"

TOKEN="$(cat "$TOKEN_FILE")"
git push "https://dasrams31:${TOKEN}@github.com/dasrams31/guntingklip.git" main 2>&1 | tail -2
unset TOKEN
echo "pushed $(date -Is)"
