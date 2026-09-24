"""
Requirement 5 (optional): inappropriate language filter.

If the user's message contains offensive or inappropriate language,
the chatbot responds politely and does NOT send the prompt further
to the main LLM.

We primarily use OpenAI's Moderation API
(omni-moderation-latest).

As a local fallback, we also check a short blocklist.
"""

from openai import OpenAI

from . import config


_LOCAL_BLOCKLIST = {
    # Romanian words
    "prost",
    "proasta",
    "idiot",
    "idioata",
    "tampit",
    "cretin",

    # English words
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "bastard",
}


POLITE_REPLY_EN = (
    "I can't respond to messages that contain inappropriate or abusive language. "
    "Please rephrase your request, and I'll be happy to help you find a suitable book. 📚"
)


def _local_check(message: str) -> bool:
    """
    Performs a simple local check against the blocklist.
    """
    words = {
        word.strip(".,!?\"'()[]{}:;").lower()
        for word in message.split()
    }

    return bool(words & _LOCAL_BLOCKLIST)


def is_inappropriate(
    message: str,
    client: OpenAI | None = None,
) -> bool:
    """
    Returns True if the user's message should be blocked.
    """

    # First, check the local fallback list.
    if _local_check(message):
        return True

    # If the OpenAI client or API key is unavailable,
    # rely only on the local check.
    if client is None or not config.OPENAI_API_KEY:
        return False

    try:
        result = client.moderations.create(
            model="omni-moderation-latest",
            input=message,
        )

        return bool(
            result.results[0].flagged
        )

    except Exception as error:
        print(
            f"[moderation] Moderation API failed: {error}"
        )

        # If the moderation API fails,
        # rely only on the local blocklist.
        return False