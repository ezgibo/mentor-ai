"""Builds the spoken cues that start a live interview: backend/voice/cues/{ready,back}.wav

Why audio: on Gemini 2.5 native audio with function tools, a session whose first turn is started by
TEXT closes with error 1007 a few seconds in. Starting it with a short spoken cue is stable.

Organizers only (the cues are committed):
    uv run python scripts/make_voice_cues.py
"""

import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from google.genai import types  # noqa: E402

import gemini  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "backend" / "voice" / "cues"
CUES = {
    "ready": "Hi, I'm here and ready to start the interview.",
    "back": "Hi, I'm back. Let's continue the interview.",
}


def to_16k(pcm_24k: bytes) -> bytes:
    samples = struct.unpack(f"<{len(pcm_24k) // 2}h", pcm_24k)
    out = [samples[int(i * 1.5)] for i in range(int(len(samples) / 1.5))]
    return struct.pack(f"<{len(out)}h", *out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = gemini.get_client()
    for name, text in CUES.items():
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=f"Say naturally and warmly: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck"))
                ),
            ),
        )
        pcm = to_16k(response.candidates[0].content.parts[0].inline_data.data)
        with wave.open(str(OUT / f"{name}.wav"), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(pcm)
        print(f"Wrote {OUT / f'{name}.wav'} ({len(pcm) / 32000:.1f} s)")


if __name__ == "__main__":
    main()
