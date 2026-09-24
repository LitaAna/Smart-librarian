# 📚 Smart Librarian — AI cu RAG + Tool Completion

Chatbot care recomandă cărți pe baza intereselor utilizatorului, folosind
**RAG** (căutare semantică într-un vector store Qdrant local) + **OpenAI GPT**,
apoi completează recomandarea cu un rezumat detaliat obținut printr-un
**tool call** separat (`get_summary_by_title`).

Interfața este o pagină web (FastAPI + HTML/CSS/JS simplu, fără build step)
care rulează local în browser.

---

## 1. Arhitectură & flow (partea importantă de înțeles)

```
                         ┌─────────────────────────┐
                         │   frontend (browser)     │
                         │   index.html / app.js     │
                         └────────────┬─────────────┘
                                      │ fetch() JSON / audio
                                      ▼
                         ┌─────────────────────────┐
                         │   FastAPI (backend/main.py) │
                         │   /api/chat /api/tts ...  │
                         └────────────┬─────────────┘
                                      ▼
                            backend/chat_engine.py
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
 1. moderation.py              2. vector_store.py             3. OpenAI Chat API
 (filtru limbaj —              (RAG: caută în Qdrant local          (gpt-4o-mini)
  Moderation API)               top-k rezumate relevante          + tools=[get_summary_by_title]
                                 pt. embedding-ul query-ului)
                                                                     │
                                                     LLM alege o carte + cere tool call
                                                                     ▼
                                                          4. tools.py: get_summary_by_title(title)
                                                             caută în book_summaries.json
                                                                     │
                                                     rezultatul e trimis înapoi la LLM
                                                     (al doilea apel chat.completions.create)
                                                                     ▼
                                                     5. LLM formulează răspunsul final
                                                        -> {reply, book_title, full_summary}
```

**Pas cu pas, la fiecare mesaj al utilizatorului:**

1. **Filtru de limbaj** (`moderation.py`) — mesajul e trimis mai întâi la
   `client.moderations.create(...)`. Dacă e marcat ca ofensator, chatbotul
   răspunde politicos direct și **nu** mai apelează LLM-ul principal.
2. **RAG / retrieval** (`vector_store.py`) — mesajul utilizatorului e
   transformat în embedding (`text-embedding-3-small`) și căutat prin
   similaritate cosinus în colecția Qdrant local `book_summaries`, care conține
   cele 12 cărți din `book_summaries.json`. Se întorc top 3 cele mai
   relevante cărți.
3. **Primul apel GPT** (`chat_engine.py`) — trimitem system prompt +
   cele 3 cărți relevante (context) + istoricul conversației + mesajul nou,
   împreună cu definiția tool-ului `get_summary_by_title` (schema JSON din
   `tools.py`). GPT alege o carte și decide să apeleze tool-ul.
4. **Tool execution** — backend-ul execută local funcția Python
   `get_summary_by_title(title)`, care caută titlul exact în dicționar și
   returnează rezumatul complet.
5. **Al doilea apel GPT** — rezultatul tool-ului e trimis înapoi la model
   (mesaj cu `role: "tool"`), iar GPT formulează răspunsul conversațional
   final pentru utilizator.
6. Backend-ul returnează `{reply, book_title, full_summary}` către frontend,
   care afișează recomandarea în chat **și** o "fișă de carte" în panoul
   din stânga (cu titlu, rezumat complet, buton de ascultare TTS și
   generare de copertă).

Funcțiile opționale (5-8 din temă) sunt module separate, apelate din
`main.py` prin endpoint-uri dedicate, ca să rămână izolate de fluxul
principal RAG + tool calling:

| Cerință opțională | Fișier | Endpoint |
|---|---|---|
| 5. Filtru de limbaj | `moderation.py` | (integrat în `/api/chat`) |
| 6. Text-to-Speech | `tts.py` | `POST /api/tts` |
| 7. Speech-to-text (mod vocal) | `stt.py` | `POST /api/stt` |
| 9. Backend + Frontend separate | `backend/` + `frontend/` | FastAPI servește API + fișiere statice |

---

## 2. Structura proiectului

```
smart-librarian/
├── backend/
│   ├── main.py            # FastAPI: endpoint-uri + servește frontend-ul
│   ├── chat_engine.py      # orchestrare RAG + tool calling (inima proiectului)
│   ├── vector_store.py     # Qdrant local + embeddings OpenAI + retriever
│   ├── tools.py             # get_summary_by_title() + schema function-calling
│   ├── moderation.py        # filtru de limbaj nepotrivit
│   ├── tts.py                # text-to-speech
│   ├── stt.py                 # speech-to-text
│   ├── config.py               # citește .env
│   └── book_summaries.json     # baza de date cu 12 cărți (cerința 1)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── data/qdrant_db/          # (generat automat la prima rulare)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 3. Instalare și rulare

Necesită Python 3.10+ și o cheie API OpenAI validă (cu credit disponibil
pentru chat, embeddings, TTS/STT/imagini dacă vrei să testezi și acele
funcții opționale).

```bash
# 1. Creează un mediu virtual
py -m venv .venv
.venv\Scripts\activate          # Windows CMD
# Linux/macOS: source .venv/bin/activate

# 2. Instalează dependințele
pip install -r requirements.txt

# 3. Configurează cheia API
copy .env.example .env            # Windows CMD
# Linux/macOS: cp .env.example .env
# deschide .env și pune OPENAI_API_KEY=sk-...

# 4. Rulează serverul (din rădăcina proiectului)
uvicorn backend.main:app --reload
```

Apoi deschide **http://localhost:8000** în browser.

La primul start, backend-ul indexează automat cele 12 cărți din
`book_summaries.json` în Qdrant local (persistat în `data/qdrant_db/`) —
se întâmplă o singură dată, apoi doar reutilizează colecția existentă.

---

## 4. Testare rapidă

Întrebări de încercat în chat (exemplele din temă):

- „Vreau o carte despre prietenie și magie”
- „Ce recomanzi pentru cineva care iubește povești de război?”
- „Vreau o carte despre libertate și control social.”
- „Ce-mi recomanzi dacă iubesc poveștile fantastice?”
- „Ce este 1984?”

Pentru modul vocal: apasă pe iconița de microfon, vorbește, iar mesajul se
transcrie automat și se trimite ca întrebare. Pentru audio: după o
recomandare, apasă „Ascultă” în fișa cărții din stânga. Pentru copertă:
apasă „Generează copertă” în aceeași fișă.

---

## 5. Note despre implementare

- **Vector store**: Qdrant local, persistent pe disc (`QdrantClient(path=...)`),
  **nu** OpenAI vector store — conform cerinței explicite din temă.
- **Embeddings**: `text-embedding-3-small`, apelate prin
  `OpenAI.embeddings.create(...)`, iar vectorii sunt stocați și interogați prin `QdrantClient`.
- **Function/tool calling**: implementat cu API-ul standard `tools=[...]`
  din OpenAI Chat Completions (nu function_call, care e deprecated).
- **Filtrul de limbaj** folosește Moderation API-ul oficial OpenAI
  (`omni-moderation-latest`) ca sursă principală, cu o listă locală minimă
  ca fallback dacă apelul de rețea eșuează.
- Dacă vrei să adaugi cărți noi, editează doar
  `backend/book_summaries.json` — la următorul restart, cărțile noi sunt
  indexate automat (cele deja existente nu sunt re-indexate).


## Administrare cărți
Pagina `/books` este protejată cu HTTP Basic Auth. Configurează în `.env`:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=parola-ta
```
