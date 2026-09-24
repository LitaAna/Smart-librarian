"""
Cerința 3 + 4: chatbot AI care integrează OpenAI GPT, face RAG peste
vector store-ul de rezumate, și apelează automat tool-ul
get_summary_by_title după ce oferă o recomandare.
"""
import json
from openai import OpenAI

from . import config, vector_store, tools, moderation

SYSTEM_PROMPT = """\
You are "Smart Librarian", a friendly and helpful AI librarian.

The user will describe the type of story, theme, or atmosphere they are looking for.

You have a list of relevant books retrieved through semantic search (RAG).
Use them as your main source of truth. Do not invent books that are not
present in the context.

Instructions:
1. Choose ONE book that best matches the user's request from the retrieved context.
2. Recommend it conversationally and briefly explain why it matches.
3. You MUST call the get_summary_by_title tool using the exact title
   of the selected book.
4. If none of the books match the request, politely ask the user for more details.

5. Only answer questions related to books, reading, literature, authors,
   book recommendations, or the current book recommendation.

6. If the user asks about an unrelated topic, do NOT answer that question.
   Politely explain that you are Smart Librarian and can only help with
   books and reading-related topics.

7. You may respond naturally to simple greetings such as "hello", "hi",
   or "how are you?", but guide the conversation back to books.

8. Always respond in English.

Context (relevant books retrieved through semantic search):
{context}
"""

def _build_context_block(matches: list[dict]) -> str:
    if not matches:
        return "(niciun rezultat relevant găsit)"
    lines = []
    for m in matches:
        lines.append(f"## {m['title']}\n{m['summary']}")
    return "\n\n".join(lines)


def _get_client() -> OpenAI:
    return OpenAI(api_key=config.OPENAI_API_KEY)


def chat(user_message: str, history: list[dict] | None = None) -> dict:
    """
    Orchestrează un tur de conversație complet:
    moderare -> RAG retrieval -> GPT (+ tool calling) -> răspuns final.

    `history` = listă de mesaje anterioare [{role, content}, ...] (opțional).

    Returnează:
    {
        "reply": str,               # răspunsul conversațional al chatbotului
        "book_title": str | None,   # titlul cărții recomandate (dacă e cazul)
        "full_summary": str | None, # rezumatul complet obținut prin tool
        "blocked": bool,            # True dacă mesajul a fost blocat de filtru
    }
    """
    client = _get_client()

    # 1. Filtru de limbaj nepotrivit (cerința 5) - nu trimite promptul la LLM
    if moderation.is_inappropriate(user_message, client):
        return {
            "reply": moderation.POLITE_REPLY_EN,
            "book_title": None,
            "full_summary": None,
            "blocked": True,
        }

    # 2. RAG: căutare semantică în vector store
    matches = vector_store.retrieve_relevant_books(user_message, n_results=3)
    context_block = _build_context_block(matches)

    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context_block)}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_message})

    # 3. Primul apel către GPT, cu tool-ul disponibil
    response = client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=messages,
        tools=[tools.GET_SUMMARY_TOOL_SCHEMA],
        tool_choice="auto",
    )

    assistant_msg = response.choices[0].message
    book_title = None
    full_summary = None

    # 4. Dacă GPT a decis să apeleze tool-ul get_summary_by_title
    if assistant_msg.tool_calls:
        messages.append(assistant_msg.model_dump(exclude_unset=True))

        for tool_call in assistant_msg.tool_calls:
            if tool_call.function.name == "get_summary_by_title":
                args = json.loads(tool_call.function.arguments or "{}")
                title_arg = args.get("title", "")
                summary = tools.get_summary_by_title(title_arg)

                book_title = title_arg
                full_summary = summary

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": summary,
                })

        # 5. Al doilea apel: GPT formulează răspunsul final ținând cont de rezumat
        final_response = client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=messages,
        )
        reply_text = final_response.choices[0].message.content
    else:
        reply_text = assistant_msg.content

    return {
        "reply": reply_text,
        "book_title": book_title,
        "full_summary": full_summary,
        "blocked": False,
    }
