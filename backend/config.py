"""
Configurare centrală: citește cheia API și numele modelelor din .env
"""
import os
from pathlib import Path
#incarca variabilele de mediu din fișierul .env
from dotenv import load_dotenv

# Încarcă .env din rădăcina proiectului
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
#modelele folosite cu valori implicite daca nu sunt setate in .env
TTS_MODEL = os.getenv("TTS_MODEL", "tts-1")
TTS_VOICE = os.getenv("TTS_VOICE", "alloy")
STT_MODEL = os.getenv("STT_MODEL", "whisper-1")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-1")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1536")
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "medium")
#pagina de administrare
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")

BOOK_SUMMARIES_PATH = Path(__file__).resolve().parent / "book_summaries.json"
QDRANT_DB_PATH = str(ROOT_DIR / "data" / "qdrant_db")

if not OPENAI_API_KEY:
    print(
        "[WARN] OPENAI_API_KEY nu este setat. Adaugă-l în fișierul .env "
        "(vezi .env.example) înainte de a rula aplicația."
    )
