"""
Vector store local bazat pe Qdrant + embeddings OpenAI.

Cerința 2 din temă: încarcă rezumatele într-o bază vectorială (NU OpenAI
vector store) și expune un retriever pentru căutare semantică după temă
sau context.
"""
import json
import uuid #folosit pentru a genera un ID unic și stabil pentru fiecare carte

from openai import OpenAI #folosit pt text -embeddings

#ste clientul prin care comunicăm cu baza vectorială Qdrant
from qdrant_client import QdrantClient

#clase Qdrant folosite pentru configurarea colecției și inserarea vectorilor
from qdrant_client.models import Distance, PointStruct, VectorParams 

from . import config

COLLECTION_NAME = "book_summaries"

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Inițializează o singură dată clientul Qdrant local și persistent."""
    global _client
    if _client is None:
        _client = QdrantClient(path=config.QDRANT_DB_PATH)
    return _client


def _get_openai_client() -> OpenAI:
    """Construiește clientul OpenAI folosit pentru embeddings."""
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY nu este setat. Adaugă cheia în fișierul .env."
        )
    return OpenAI(api_key=config.OPENAI_API_KEY)


def _create_embeddings(texts: list[str]) -> list[list[float]]:
    """Transformă textele în vectori cu modelul de embeddings configurat."""
    response = _get_openai_client().embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def _stable_point_id(title: str) -> str:
    """Generează același UUID pentru același titlu la fiecare indexare."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, title))

#citeste fisierul book_summaries.json si returneaza un dictionar cu titlurile si rezumatele cartilor
def load_books() -> dict:
    """Citește fișierul book_summaries.json -> {title: summary}."""
    with open(config.BOOK_SUMMARIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# functia de indexare a cartilor in baza de date Qdrant, cu optiunea de a forta stergerea si recrearea colectiei

def ingest_books(force: bool = False) -> int:
    """
    Populează colecția Qdrant cu rezumatele cărților.

    Cu force=True, colecția existentă este ștearsă și recreată.
    Returnează numărul total de cărți indexate.
    """
    client = _get_client() #obtine clientul Qdrant
    books = load_books() # citeste cartile din fisierul book_summaries.json

    if not books:
        return 0

    collection_exists = client.collection_exists(COLLECTION_NAME)

    if force and collection_exists:
        client.delete_collection(COLLECTION_NAME)
        collection_exists = False

    if collection_exists:
        existing_count = client.count(
            collection_name=COLLECTION_NAME,
            exact=True,
        ).count
        if existing_count > 0:
            return existing_count

    titles = list(books.keys())
    summaries = [books[title] for title in titles]
    #embeddingul e facuut dupa rezumat nu dupa titlu, pentru ca rezumatul e mai relevant pentru cautarea semantica
    embeddings = _create_embeddings(summaries)

    if not embeddings:
        return 0

#crearea colectiei qdrant daca nu exista, cu dimensiunea vectorilor egala cu dimensiunea embeddingului creat
    if not collection_exists:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=len(embeddings[0]), #qdrant trebuie sa stie dimensiunea vectorilor pentru a crea colectia
                distance=Distance.COSINE, #pt comparea vectorilor folosim cosine similarity, care e mai potrivit pentru embeddings
            ),
        )

    points = [
        PointStruct(
            id=_stable_point_id(title),
            vector=embedding,
            payload={"title": title, "summary": books[title]},
        )
        for title, embedding in zip(titles, embeddings)
        # zip face titles[0] ↔ embeddings[0], ca sa nu se piarda legatura intre titlu si embedding

    ]

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )
    return len(points)
    #upsert= update + insert, daca exista deja un punct cu acelasi id, il updateaza, altfel il insereaza


def retrieve_relevant_books(query: str, n_results: int = 3) -> list[dict]:
    """
    Căutare semantică după întrebarea sau tema introdusă de utilizator.
    Returnează o listă de dicționare cu title, summary și distance.
    """
    client = _get_client()

    if not client.collection_exists(COLLECTION_NAME):
        ingest_books()

    count = client.count(
        collection_name=COLLECTION_NAME,
        exact=True,
    ).count

    if count == 0:
        count = ingest_books(force=True)

    if count == 0:
        return []
#transform query-ul in embedding pentru a putea fi comparat cu vectorii din baza de date
    query_embedding = _create_embeddings([query])[0]
    result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=min(n_results, count),
        with_payload=True, # fara asta qdrant nu returneaza titlul si rezumatul cartilor, ci doar vectorii
    )
#     vectorul întrebării
#          ↓
#     compară cu toți vectorii cărților
#          ↓
#      cosine similarity
#          ↓
#      sortează
#          ↓
#      returnează cele mai apropiate


#construirea rezultatelor într-o listă de dicționare cu titlu, rezumat și distanță (1 - scor)
    matches = []
    for point in result.points:
        payload = point.payload or {}
        score = float(point.score)
        matches.append(
            {
                "title": payload.get("title", ""),
                "summary": payload.get("summary", ""),
                # Păstrăm cheia "distance" pentru compatibilitate cu restul
                # proiectului. Pentru cosine similarity, scor mai mare = mai bun.
                "distance": 1.0 - score, #codul meu foloseste distance ca sa fie compatibil cu restul proiectului, dar in realitate e
                # 1 - cosine similarity, pentru ca qdrant returneaza scorul de similaritate, nu distanta
            }
        )

    return matches

# Fișierul citește rezumatele cărților din JSON, generează embeddings cu text-embedding-3-small,
#  le salvează persistent în Qdrant împreună cu titlul și rezumatul ca payload, iar când utilizatorul pune o întrebare transformă 
#  și întrebarea într-un embedding și folosește cosine similarity pentru a recupera cele mai relevante cărți.