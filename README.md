# ✂️ GuntingKlip — Bot Clipper Otomatis

Video panjang → stok klip vertikal siap upload. Khusus buat workflow **clipper affiliate** (Ternak Klip & sejenisnya).

## Cara kerja

```
video_panjang.mp4
    │  1. extract audio (ffmpeg)
    ▼
🎙️  2. transkrip otomatis (faster-whisper, Bahasa Indonesia)
    │     → teks + timestamp per kalimat
    ▼
🧠  3. AI pilih momen terbaik (LLM lokal via 9Router)
    │     → hook kuat, emosi, opini tegas, tips praktis
    │     → BUKAN opening/basa-basi
    ▼
✂️  4. auto-edit per klip (ffmpeg)
    │     → cut → crop 9:16 → scale 1080x1920
    │     → subtitle otomatis (burn-in)
    │     → hook text overlay 3 detik pertama
    │     → encode yuv420p (aman buat TikTok/IG)
    ▼
📦  clips/  (default; bisa diganti via --out)
      klip_01.mp4, klip_02.mp4, klip_03.mp4
      caption.txt  ← format "[KLIP #n/N — STOCK KONTEN SIAP UPLOAD]"
```

## Install

```bash
git clone https://github.com/dasrams31/guntingklip.git
cd guntingklip
bash install.sh
```

Installer otomatis: cek `python3` + `ffmpeg`, bikin venv, install dependency (pinned),
minta URL + API key 9Router (disimpan di `~/.config/guntingklip/`, chmod 600),
opsional pre-download model Whisper `small` (~500MB).

Butuh 9Router yang jalan (lokal / remote) — model default `smollm2`, bisa diganti via `--model`.
Tanpa API key pun tetap jalan (fallback: klip dibagi merata).

## Cara pakai (gampang)

```bash
cd ~/workspace/guntingklip
bash klip.sh video.mp4
# atau: bash klip.sh "https://..." (URL langsung di-download)
```

Tinggal jawab 5 pertanyaan (topik, campaign, rate, link join, jumlah klip) — jawaban tersimpan jadi default buat berikutnya. Klip jadi di `clips/`, caption di `clips/caption.txt`.

## Cara pakai (manual, full control)

Install manual tanpa `install.sh`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# API key: env NINE_ROUTER_KEY, atau ~/.config/guntingklip/9router_key
```

Download model whisper sekali (otomatis saat pertama jalan, ~500MB untuk `small`).

## Pakai

```bash
.venv/bin/python guntingklip.py video_panjang.mp4 \
  --topik "Rahasia Kahf Coklat Energizing & Brightening" \
  --campaign "Kahf Combat Trio FW" \
  --rate "Rp 5.000 / 1k views" \
  --join-link "https://ternakklip.com/campaign/xxxx" \
  --clips 3 --out clips_kahf
```

## Workflow clipper affiliate (lengkap)

1. **Join campaign** di Ternak Klip → catat brief, hashtag wajib, rate, link join
2. **Download video sumber** dari campaign
3. **Jalankan GuntingKlip** dengan info campaign → dapat N klip + caption
4. **Cek cepat** tiap klip (30 detik/klip) — pastikan produk kelihatan & hook nendang
5. **Upload manual dari HP** ke TikTok: tempel caption, hashtag wajib, pasang **Keranjang Kuning**
6. **Views organik terakumulasi** → payout per 1k views sesuai rate campaign

> ⚠️ Baca brief campaign dulu! Beberapa campaign melarang AI clipping tools.
> Upload tetap manual — jangan otomasi login TikTok (risiko akun kena flag).

## Catatan teknis

- Whisper model `small` int8: cukup akurat untuk Bahasa Indonesia, jalan di CPU (~0.3x durasi video)
- LLM pakai combo `smollm2` lokal via 9Router (gratis, offline)
- Butuh API key 9Router di `~/workspace/agentarium/agents/.keys/.9router_key`
