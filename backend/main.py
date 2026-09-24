"""
Smart Librarian - FastAPI backend.

Rulare:
    uvicorn backend.main:app --reload
"""
import json
import secrets
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import Response, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from openai import OpenAI

from . import config, chat_engine, vector_store, tts as tts_module, stt as stt_module

app = FastAPI(title="Smart Librarian API")
security = HTTPBasic()
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class TTSRequest(BaseModel):
    text: str


class CoverRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=10000)


class BookRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=10, max_length=10000)




def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    valid_user = secrets.compare_digest(credentials.username, config.ADMIN_USERNAME)
    valid_password = secrets.compare_digest(credentials.password, config.ADMIN_PASSWORD)
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Date de autentificare invalide.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _write_books(books: dict[str, str]) -> None:
    with open(config.BOOK_SUMMARIES_PATH, "w", encoding="utf-8") as file:
        json.dump(books, file, ensure_ascii=False, indent=2)


@app.on_event("startup")
def on_startup():
    try:
        count = vector_store.ingest_books()
        print(f"[startup] Vector store gata, {count} cărți indexate.")
    except Exception as e:
        print(f"[startup] Nu am putut indexa vector store-ul: {e}")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/books")
def api_list_books(_: str = Depends(require_admin)):
    books = vector_store.load_books()
    return {
        "count": len(books),
        "books": [
            {"title": title, "summary": summary}
            for title, summary in sorted(books.items(), key=lambda item: item[0].lower())
        ],
    }


@app.post("/api/books")
def api_add_book(req: BookRequest, _: str = Depends(require_admin)):
    title = req.title.strip()
    summary = req.summary.strip()
    books = vector_store.load_books()

    if any(existing.lower() == title.lower() for existing in books):
        raise HTTPException(409, "Există deja o carte cu acest titlu.")

    books[title] = summary
    _write_books(books)

    try:
        count = vector_store.ingest_books(force=True)
    except Exception as exc:
        raise HTTPException(500, f"Cartea a fost salvată, dar reindexarea a eșuat: {exc}")

    return {"message": "Cartea a fost adăugată și indexată.", "count": count}


@app.put("/api/books/{title}")
def api_update_book(title: str, req: BookRequest, _: str = Depends(require_admin)):
    books = vector_store.load_books()
    existing_title = next((item for item in books if item.lower() == title.lower()), None)
    if existing_title is None:
        raise HTTPException(404, "Cartea nu a fost găsită.")

    new_title = req.title.strip()
    new_summary = req.summary.strip()
    collision = next(
        (item for item in books if item.lower() == new_title.lower() and item != existing_title),
        None,
    )
    if collision:
        raise HTTPException(409, "Există deja o altă carte cu noul titlu.")

    del books[existing_title]
    books[new_title] = new_summary
    _write_books(books)
    count = vector_store.ingest_books(force=True)
    return {"message": "Cartea a fost actualizată și reindexată.", "count": count}


@app.delete("/api/books/{title}")
def api_delete_book(title: str, _: str = Depends(require_admin)):
    books = vector_store.load_books()
    existing_title = next((item for item in books if item.lower() == title.lower()), None)
    if existing_title is None:
        raise HTTPException(404, "Cartea nu a fost găsită.")

    del books[existing_title]
    _write_books(books)
    count = vector_store.ingest_books(force=True) if books else 0
    return {"message": "Cartea a fost ștearsă.", "count": count}


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    if not config.OPENAI_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY nu este configurat pe server.")
    history = [m.model_dump() for m in req.history]
    try:
        return chat_engine.chat(req.message, history)
    except Exception as e:
        raise HTTPException(500, f"Eroare chat: {e}")


@app.post("/api/tts")
def api_tts(req: TTSRequest):
    if not config.OPENAI_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY nu este configurat pe server.")
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        audio_bytes = tts_module.synthesize_speech(req.text, client)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(500, f"Eroare TTS: {e}")


@app.post("/api/stt")
async def api_stt(file: UploadFile = File(...)):
    if not config.OPENAI_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY nu este configurat pe server.")
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        content = await file.read()
        text = stt_module.transcribe_audio(content, file.filename, client)
        return {"text": text}
    except Exception as e:
        raise HTTPException(500, f"Eroare STT: {e}")


@app.post("/api/cover")
def api_cover(req: CoverRequest):
    if not config.OPENAI_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY nu este configurat pe server.")

    title = req.title.strip()
    summary = req.summary.strip()
    if not title:
        raise HTTPException(422, "Titlul cărții este obligatoriu.")

    prompt = (
        "Create a polished vertical editorial book cover. "
        f"The exact book title is: \"{title}\". "
        "Render the title clearly and prominently on the cover. "
        "Use a tasteful abstract illustration inspired by the title. "
        "Do not include people, faces, weapons, violence, gore, dangerous acts, "
        "sexual content, political symbols, logos, barcodes, author names, or any extra text. "
        "Use elegant typography and a refined color palette."
    )

    fallback_prompt = (
        "Create a minimal, abstract vertical book cover using only elegant geometric shapes, "
        "paper texture, and a refined color palette. "
        f"Place only this exact title on the cover: \"{title}\". "
        "Do not depict people, animals, places, events, violence, weapons, politics, "
        "sexual content, logos, barcodes, author names, or any other text."
    )

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        try:
            result = client.images.generate(
                model=config.IMAGE_MODEL,
                prompt=prompt,
                size=config.IMAGE_SIZE,
                quality=config.IMAGE_QUALITY,
            )
        except Exception as first_error:
            if "moderation_blocked" not in str(first_error):
                raise
            result = client.images.generate(
                model=config.IMAGE_MODEL,
                prompt=fallback_prompt,
                size=config.IMAGE_SIZE,
                quality=config.IMAGE_QUALITY,
            )
        image_data = None
        if result.data:
            image_data = result.data[0].b64_json or result.data[0].url
        if not image_data:
            raise RuntimeError("API-ul nu a returnat imaginea copertei.")
        if image_data.startswith("http"):
            return {"image": image_data}
        return {"image": f"data:image/png;base64,{image_data}"}
    except Exception as e:
        if "moderation_blocked" in str(e):
            raise HTTPException(
                400,
                "Coperta nu a putut fi generată deoarece titlul a fost blocat de filtrul de siguranță al serviciului de imagini.",
            )
        raise HTTPException(500, f"Eroare la generarea copertei: {e}")



app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/books")
def serve_books(_: str = Depends(require_admin)):
    return FileResponse(str(FRONTEND_DIR / "books.html"))
