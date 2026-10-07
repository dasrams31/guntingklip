#!/usr/bin/env python3
"""
GuntingKlip — bot clipper otomatis.
Input : video panjang (review/podcast/live) + info campaign
Output: N klip vertikal 9:16 siap upload + caption format Ternak Klip

Pipeline:
  1. extract audio -> transcribe (faster-whisper, Bahasa Indonesia)
  2. LLM pilih momen terbaik (hook, emosi, opini tegas)
  3. ffmpeg: cut -> crop 9:16 -> subtitle otomatis -> hook text overlay
  4. tulis caption.txt format "[KLIP #n/N — STOCK KONTEN SIAP UPLOAD]"

Contoh:
  python3 guntingklip.py video_panjang.mp4 --topik "Rahasia Kahf Coklat" \\
      --campaign "Kahf Combat Trio FW" --rate "Rp 5.000 / 1k views" \\
      --join-link "https://ternakklip.com/campaign/xxxx" --clips 3
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

# --- Perbaikan env proxy VPS (2026-10-06) ---
# Variabel no_proxy/NO_PROXY bawaan runtime berisi entri IPv6 dalam kurung
# ([::1], [fd8b:...]) yang membuat httpx (dipakai huggingface_hub/faster-whisper)
# crash dengan "InvalidURL: Invalid port". Bersihkan entri rusak itu saja,
# proxy egress tetap dipakai untuk download model bila belum ada di cache.
for _k in ("no_proxy", "NO_PROXY"):
    _v = os.environ.get(_k)
    if _v:
        _clean = ",".join(p for p in _v.split(",") if "[" not in p and "]" not in p)
        os.environ[_k] = _clean
# Kalau model whisper sudah ter-cache lokal, paksa mode offline agar tidak
# ada panggilan jaringan sama sekali (lebih cepat + tahan proxy rusak).
from pathlib import Path as _P
if list((_P.home() / ".cache" / "huggingface" / "hub").glob("models--*faster-whisper-small*")):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
# --- akhir perbaikan env ---

WHISPER_MODEL = "small"  # cukup akurat untuk ID, ringan di CPU
FONT = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("GAGAL:", " ".join(cmd[:4]), r.stderr[-500:], file=sys.stderr)
        sys.exit(1)
    return r


def extract_audio(video, out_wav):
    r = subprocess.run(["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                        "-c:a", "pcm_s16le", out_wav],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("GAGAL extract audio:", r.stderr[-500:], file=sys.stderr)
        sys.exit(1)
    return out_wav


def transcribe(wav):
    from faster_whisper import WhisperModel
    print(f"[1/4] Transkrip audio ({WHISPER_MODEL})...", flush=True)
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, info = model.transcribe(wav, language="id", beam_size=5)
    segs = [{"start": round(s.start, 2), "end": round(s.end, 2),
             "text": s.text.strip()} for s in segments if s.text.strip()]
    print(f"      {len(segs)} segmen, durasi {info.duration:.0f}s", flush=True)
    return segs, info.duration


def nine_router_config():
    """Ambil URL + API key 9Router dari beberapa sumber (prioritas atas dulu).

    Key:  1) env NINE_ROUTER_KEY
          2) ~/.config/guntingklip/9router_key   (dibuat oleh install.sh)
          3) ~/workspace/agentarium/agents/.keys/.9router_key  (legacy, VPS ini)
    URL:  1) env NINE_ROUTER_URL
          2) ~/.config/guntingklip/9router_url
          3) default http://127.0.0.1:20128/v1
    """
    key = os.environ.get("NINE_ROUTER_KEY", "").strip()
    url = os.environ.get("NINE_ROUTER_URL", "").strip()
    cfg = os.path.expanduser("~/.config/guntingklip")
    if not key:
        for p in (os.path.join(cfg, "9router_key"),
                  os.path.expanduser("~/workspace/agentarium/agents/.keys/.9router_key")):
            if os.path.isfile(p):
                key = open(p).read().strip()
                if key:
                    break
    if not url:
        p = os.path.join(cfg, "9router_url")
        if os.path.isfile(p):
            url = open(p).read().strip()
    if not url:
        url = "http://127.0.0.1:20128/v1"
    return url.rstrip("/"), key


def llm_pick_moments(segments, duration, n_clips, min_dur, max_dur, topik, model):
    """Minta LLM pilih momen terbaik dari transkrip."""
    print("[2/4] AI pilih momen terbaik...", flush=True)
    # Ringkas transkrip jadi teks bernomor waktu
    lines = []
    for s in segments:
        mm = int(s["start"] // 60)
        ss = int(s["start"] % 60)
        lines.append(f"[{mm:02d}:{ss:02d}] {s['text']}")
    transcript = "\n".join(lines)

    key_url, key = nine_router_config()
    if not key:
        print("LLM: API key 9Router tidak ditemukan "
              "(env NINE_ROUTER_KEY / ~/.config/guntingklip/9router_key) — "
              "pakai fallback merata.", flush=True)
        return fallback_moments(duration, n_clips, min_dur, max_dur)
    prompt = (
        "Kamu editor konten clipper TikTok. Dari transkrip video berikut, pilih "
        f"{n_clips} momen TERBAIK untuk dijadikan klip pendek.\n"
        f"Topik video: {topik}\n"
        f"Setiap klip harus {min_dur}-{max_dur} detik. Pilih momen yang punya HOOK kuat: "
        "fakta mengejutkan, opini tegas, emosi, tips praktis, atau kalimat yang bikin penasaran. "
        "Jangan pilih opening/basa-basi/perkenalan. Momen boleh overlap sedikit tapi usahakan beda bagian.\n\n"
        "Jawab HANYA JSON valid, tanpa teks lain:\n"
        '[{"start": detik_mulai, "end": detik_selesai, '
        '"hook": "teks hook max 8 kata untuk overlay", '
        '"judul": "judul klip singkat"}]\n\n'
        f"TRANSKRIP:\n{transcript}"
    )
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system",
             "content": "Kamu mesin ekstraksi JSON. Jawab HANYA dengan JSON valid, tanpa teks pembuka/penutup, tanpa penjelasan."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1500,
        "temperature": 0.3,
    }).encode()
    req = urllib.request.Request(
        f"{key_url}/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        # 9Router/LLM kadang lambat atau gagal (fetch timeout ke model lokal) —
        # jangan crash, pakai fallback pembagian merata.
        print(f"LLM gagal dihubungi ({e}), pakai fallback merata.", flush=True)
        return fallback_moments(duration, n_clips, min_dur, max_dur)
    # 9Router menempelkan "data: [DONE]" di akhir body (kadang tanpa newline) — buang dulu
    raw_body = re.sub(r"data:\s*\[DONE\]\s*$", "", raw_body).strip()
    data = None
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        pass
    if not isinstance(data, dict):
        for line in raw_body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                    break
                except json.JSONDecodeError:
                    continue
    if not isinstance(data, dict):
        print("9Router tidak mengembalikan JSON, pakai fallback merata.", flush=True)
        return fallback_moments(duration, n_clips, min_dur, max_dur)
    raw = data["choices"][0]["message"]["content"]
    # Ambil JSON pertama dari respons
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        print("LLM tidak mengembalikan JSON, pakai fallback merata.", flush=True)
        return fallback_moments(duration, n_clips, min_dur, max_dur)
    moments = json.loads(m.group(0))
    # Validasi & clamp
    out = []
    for mo in moments[:n_clips]:
        s = max(0.0, float(mo.get("start", 0)))
        e = min(duration, float(mo.get("end", s + min_dur)))
        if e - s < 5:
            e = min(duration, s + min_dur)
        out.append({"start": s, "end": e,
                    "hook": str(mo.get("hook", ""))[:60],
                    "judul": str(mo.get("judul", ""))[:80]})
    print(f"      {len(out)} momen dipilih", flush=True)
    return out


def fallback_moments(duration, n_clips, min_dur, max_dur):
    """Bagi rata kalau LLM gagal."""
    span = duration / n_clips
    out = []
    for i in range(n_clips):
        s = i * span + span * 0.1
        e = min(duration, s + min(max_dur, span * 0.7))
        out.append({"start": round(s, 1), "end": round(e, 1),
                    "hook": "", "judul": f"Klip {i+1}"})
    return out


def write_srt(segments, start, end, path):
    """Tulis SRT subtitle untuk rentang klip (waktu relatif)."""
    def ts(t):
        h, m = int(t // 3600), int((t % 3600) // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")
    n = 0
    with open(path, "w") as f:
        for sg in segments:
            if sg["end"] < start or sg["start"] > end:
                continue
            n += 1
            f.write(f"{n}\n{ts(max(0, sg['start']-start))} --> "
                    f"{ts(min(end, sg['end'])-start)}\n{sg['text']}\n\n")
    return n > 0


def esc_drawtext(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def make_clip(video, moment, segments, idx, out_dir):
    """Cut -> crop 9:16 -> subtitle -> hook overlay -> yuv420p."""
    srt = os.path.join(out_dir, f"klip_{idx:02d}.srt")
    has_sub = write_srt(segments, moment["start"], moment["end"], srt)
    out = os.path.join(out_dir, f"klip_{idx:02d}.mp4")
    dur = moment["end"] - moment["start"]

    vf = ("crop=ih*9/16:ih,scale=1080:1920,setsar=1")
    if has_sub:
        vf += (",subtitles='" + srt.replace("'", "\\'") + "':force_style="
               "'FontName=Noto Sans,FontSize=13,PrimaryColour=&HFFFFFF,"
               "OutlineColour=&H90000000,BorderStyle=1,Outline=2,"
               "Alignment=2,MarginV=140'")
    hook = moment.get("hook", "").strip()
    if hook:
        vf += (",drawtext=fontfile=" + FONT + ":text='" + esc_drawtext(hook.upper()) + "'"
               ":fontcolor=white:fontsize=52:borderw=3:bordercolor=black"
               ":x=(w-text_w)/2:y=180:enable='lt(t,3)'"
               ":box=1:boxcolor=black@0.55:boxborderw=18")

    r = subprocess.run(["ffmpeg", "-y", "-ss", str(moment["start"]), "-i", video,
                        "-t", str(round(dur, 2)), "-vf", vf,
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
                        "-crf", "20", "-c:a", "aac", "-b:a", "128k",
                        "-movflags", "+faststart", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"GAGAL bikin klip {idx}:", r.stderr[-500:], file=sys.stderr)
        sys.exit(1)
    return out


def write_caption(moments, args, out_dir):
    n = len(moments)
    lines = []
    for i, mo in enumerate(moments, 1):
        lines.append(
            f"🎬 [KLIP #{i} / {n} — STOCK KONTEN SIAP UPLOAD] 🛒🔥\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 Topik: {mo.get('judul') or args.topik}\n"
            f"📦 Campaign: {args.campaign}\n"
            f"💰 Rate: {args.rate}\n"
            f"👉 Link Join Campaign:\n{args.join_link}\n"
            f"⏱️ Durasi: {mo['end']-mo['start']:.0f} detik\n"
        )
    path = os.path.join(out_dir, "caption.txt")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def main():
    ap = argparse.ArgumentParser(description="GuntingKlip — bot clipper otomatis")
    ap.add_argument("video", help="video panjang sumber")
    ap.add_argument("--topik", default="-", help="topik video")
    ap.add_argument("--campaign", default="-", help="nama campaign")
    ap.add_argument("--rate", default="-", help="rate mis. 'Rp 5.000 / 1k views'")
    ap.add_argument("--join-link", default="-", help="link join campaign")
    ap.add_argument("--clips", type=int, default=3, help="jumlah klip")
    ap.add_argument("--min-dur", type=int, default=15, help="durasi min klip (detik)")
    ap.add_argument("--max-dur", type=int, default=45, help="durasi max klip (detik)")
    ap.add_argument("--out", default="clips", help="folder output")
    ap.add_argument("--model", default="smollm2",
                    help="model LLM via 9Router (default: smollm2)")
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        sys.exit(f"File tidak ada: {args.video}")
    os.makedirs(args.out, exist_ok=True)

    wav = os.path.join(args.out, "_audio.wav")
    extract_audio(args.video, wav)
    segments, duration = transcribe(wav)
    if not segments:
        sys.exit("Transkrip kosong — pastikan video ada suara.")
    moments = llm_pick_moments(segments, duration, args.clips,
                               args.min_dur, args.max_dur, args.topik,
                               args.model)

    print("[3/4] Potong & edit klip...", flush=True)
    outs = []
    for i, mo in enumerate(moments, 1):
        out = make_clip(args.video, mo, segments, i, args.out)
        outs.append(out)
        print(f"      klip_{i:02d}.mp4 ({mo['end']-mo['start']:.0f}s) — {mo.get('judul','')}",
              flush=True)

    print("[4/4] Tulis caption...", flush=True)
    cap = write_caption(moments, args, args.out)
    try:
        os.remove(wav)
    except OSError:
        pass

    print(f"\n✅ Selesai! {len(outs)} klip siap upload di: {args.out}/")
    print(f"   Caption: {cap}")


if __name__ == "__main__":
    main()
