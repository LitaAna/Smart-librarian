"""
Cerința 7 (opțional): Speech-to-Text.
Transcrie mesajul vorbit al utilizatorului (mod vocal) folosind Whisper.
"""
import io
from openai import OpenAI
from . import config


def transcribe_audio(file_bytes: bytes, filename: str, client: OpenAI) -> str:
    """Primește bytes-ii unui fișier audio și returnează textul transcris."""
    audio_file = io.BytesIO(file_bytes)
    audio_file.name = filename or "recording.webm"

    transcript = client.audio.transcriptions.create(
        model=config.STT_MODEL,
        file=audio_file,
    )
    return transcript.text
