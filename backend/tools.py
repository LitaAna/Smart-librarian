"""
Cerința 4: tool get_summary_by_title(title) înregistrat ca function calling
în OpenAI Chat API.
"""
from . import vector_store

_books_cache: dict | None = None


def _books() -> dict:
    global _books_cache
    if _books_cache is None:
        _books_cache = vector_store.load_books()
    return _books_cache


def get_summary_by_title(title: str) -> str:
    """Caută titlul (exact sau cel mai apropiat) și returnează rezumatul complet."""
    books = _books()

    # Potrivire exactă
    if title in books:
        return books[title]

    # Potrivire case-insensitive
    for t, summary in books.items():
        if t.lower() == title.lower():
            return summary

    # Potrivire parțială (best-effort), în caz că LLM-ul trimite titlul ușor diferit
    for t, summary in books.items():
        if title.lower() in t.lower() or t.lower() in title.lower():
            return summary

    return f"Nu am găsit un rezumat pentru titlul '{title}' în baza de date."


# Schema JSON expusă către OpenAI Chat API (function calling / tools)
GET_SUMMARY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_summary_by_title",
        "description": (
            "Returnează rezumatul complet și detaliat al unei cărți, "
            "pe baza titlului exact. Folosește acest tool imediat după ce "
            "recomanzi o carte utilizatorului, pentru a-i oferi detalii "
            "suplimentare despre acea carte."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Titlul exact al cărții recomandate, ex: '1984' sau 'The Hobbit'.",
                }
            },
            "required": ["title"],
        },
    },
}

AVAILABLE_TOOLS = {
    "get_summary_by_title": get_summary_by_title,
}
