"""
Cerința 6 (opțional): Text-to-Speech.
Convertește recomandarea + rezumatul într-un fișier audio (mp3).
"""
from openai import OpenAI
from . import config


def synthesize_speech(text: str, client: OpenAI) -> bytes:
    """Returnează conținutul audio (mp3) ca bytes, gata de trimis către client."""
    response = client.audio.speech.create(
        model=config.TTS_MODEL,
        voice=config.TTS_VOICE,
        input=text,
    )
    return response.read()
