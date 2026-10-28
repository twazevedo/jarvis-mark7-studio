"""Motor de Voz Oficial do J.A.R.V.I.S. — Voz Humana Natural de Estúdio (Sem Efeito Robótico).

Modos disponíveis:
- "jarvis_br"      : Voz neural humana ultra-natural (timbre clássico da dublagem brasileira do J.A.R.V.I.S.)
- "jarvis_original": Voz original do ator Paul Bettany nos filmes (modelo neural jarvis-high.onnx)
- "jarvis_offline" : Voz neural 100% offline em português (Piper pt_BR-faber-medium)
"""
from collections import OrderedDict
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import backends as B

ROOT = B.ROOT
TTS_LOCK = threading.Lock()
_TTS_CACHE: "OrderedDict[tuple[str, str], bytes]" = OrderedDict()
_TTS_CACHE_MAX = 24

# Equalização limpa de estúdio (broadcast): sem eco metálico/robótico,
# apenas encorpamento suave nos médio-graves (170 Hz) e nitidez natural de voz humana.
STUDIO_NATURAL_FILTER = (
    "highpass=f=85,"
    "equalizer=f=170:t=q:w=1.1:g=1.8,"
    "equalizer=f=3400:t=q:w=1.5:g=1.5,"
    "alimiter=limit=0.96"
)


def clean_for_speech(text: str) -> str:
    """Remove blocos de código, emojis e marcações Markdown para leitura fluida e natural."""
    t = re.sub(r"```[\s\S]*?```", " Deixei o código pronto no seu visor, senhor. ", text or "")
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"https?://\S+", " link na tela ", t)
    # Remove emojis e símbolos gráficos para não ler nomes de emojis em voz alta
    t = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf]+", " ", t)
    t = re.sub(r"[\*\#_~>\[\]\|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _to_clean_wav(in_audio: Path, out_wav: Path):
    """Converte para WAV 44.1 kHz com equalização limpa de estúdio (zero efeito robótico)."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(in_audio),
        "-af", STUDIO_NATURAL_FILTER,
        "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le",
        str(out_wav),
    ]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0 or not out_wav.exists():
        raise RuntimeError("Falha ao processar áudio do Jarvis: " + p.stderr.decode(errors="replace")[-300:])


def _synth_edge_br(text: str, raw_mp3: Path) -> bool:
    """Sintetiza com a voz neural humana masculina mais natural do português brasileiro."""
    cmd = [
        sys.executable, "-m", "edge_tts",
        "--voice", "pt-BR-AntonioNeural",
        "--rate=+3%",
        "--pitch=-2Hz",
        "--text", text,
        "--write-media", str(raw_mp3),
    ]
    p = subprocess.run(cmd, capture_output=True, timeout=25)
    return p.returncode == 0 and raw_mp3.exists() and raw_mp3.stat().st_size > 200


def _synth_piper(text: str, model_rel: str, raw_wav: Path):
    model_path = ROOT / model_rel
    if not model_path.is_file():
        raise RuntimeError(f"Modelo de voz não encontrado: {model_rel}")
    p = subprocess.run(
        [sys.executable, "-m", "piper", "-m", str(model_path), "-f", str(raw_wav)],
        input=text.encode("utf-8"),
        capture_output=True,
    )
    if p.returncode != 0 or not raw_wav.exists():
        raise RuntimeError("Falha no Piper TTS: " + p.stderr.decode(errors="replace")[-300:])


def synthesize_to_wav(text: str, out_wav: Path, voice_mode: str = "jarvis_br"):
    """Gera o arquivo WAV final com voz 100% natural e limpa."""
    clean = clean_for_speech(text)
    if not clean:
        clean = "Pois não, senhor."

    key = (clean, voice_mode)
    with TTS_LOCK:
        cached = _TTS_CACHE.get(key)
        if cached:
            _TTS_CACHE.move_to_end(key)
            out_wav.write_bytes(cached)
            return

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            done = False
            if voice_mode == "jarvis_original":
                raw = tmp / "raw.wav"
                model = (
                    "voices/jarvis-high.onnx"
                    if (ROOT / "voices/jarvis-high.onnx").is_file()
                    else "voices/pt_BR-faber-medium.onnx"
                )
                _synth_piper(clean, model, raw)
                _to_clean_wav(raw, out_wav)
                done = True
            elif voice_mode == "jarvis_br":
                raw_mp3 = tmp / "raw.mp3"
                try:
                    if _synth_edge_br(clean, raw_mp3):
                        _to_clean_wav(raw_mp3, out_wav)
                        done = True
                except Exception:
                    done = False

            if not done:
                raw_wav = tmp / "raw.wav"
                _synth_piper(clean, B.CFG["long_video"]["piper_model"], raw_wav)
                _to_clean_wav(raw_wav, out_wav)

        wav_bytes = out_wav.read_bytes()
        _TTS_CACHE[key] = wav_bytes
        if len(_TTS_CACHE) > _TTS_CACHE_MAX:
            _TTS_CACHE.popitem(last=False)


def synthesize_bytes(text: str, voice_mode: str = "jarvis_br") -> bytes:
    """Retorna os bytes WAV prontos para tocar no navegador (com cache instantâneo)."""
    clean = clean_for_speech(text) or "Pois não, senhor."
    key = (clean, voice_mode)
    with TTS_LOCK:
        cached = _TTS_CACHE.get(key)
        if cached:
            _TTS_CACHE.move_to_end(key)
            return cached
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "jarvis.wav"
        synthesize_to_wav(clean, out, voice_mode=voice_mode)
        return out.read_bytes()
