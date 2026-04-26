from fastapi import FastAPI
from googletrans import Translator
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
translator = Translator()

# Optional: Add CORS if you're calling this from a frontend or other backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/translate")
def translate_text(text: str, target: str = "en"):
    """
    Translate given text to target language using Google Translate API.
    Example: /translate?text=hello&target=mr
    """
    result = translator.translate(text, dest=target)
    return {
        "translated_text": result.text,
        "detected_lang": result.src
    }

# This lets you run the script directly using `python translator_service.py`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("translator_service:app", host="127.0.0.1", port=9000, reload=True)
