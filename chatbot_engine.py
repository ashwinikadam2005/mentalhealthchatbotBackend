"""
chatbot_engine.py
-----------------
Fast LLM responses via Groq (llama3-70b-8192).
Groq is ~10-20x faster than OpenRouter/GPT-3.5 for inference.
get_chatbot_response() is kept for backward compatibility but returns ""
so callers skip it and go straight to fast_llm_response().
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Groq client (fast inference)
# ---------------------------------------------------------------------------
_groq_client = None

def _get_groq_client():
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    try:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            _groq_client = Groq(api_key=api_key)
            print("✅ Groq client initialized (fast mode).")
        else:
            print("⚠️ GROQ_API_KEY not set — Groq unavailable.")
    except Exception as e:
        print(f"⚠️ Failed to init Groq client: {e}")
    return _groq_client


def fast_llm_response(system_prompt: str, user_message: str, max_tokens: int = 512) -> str:
    """
    Call Groq's llama3-70b-8192 for a fast response.
    Falls back to empty string if unavailable so the caller can use its own fallback.
    """
    client = _get_groq_client()
    if not client:
        return ""
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=max_tokens,
            timeout=12,   # fail fast — don't block the user
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Groq fast_llm_response error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Legacy stub — kept so chatbot_routes.py import doesn't break.
# Returns "" immediately so callers skip it and call fast_llm_response() instead.
# ---------------------------------------------------------------------------
def get_chatbot_response(user_query: str) -> str:
    """Stub: PDF/ChromaDB QA is disabled (returns '' instantly)."""
    return ""
