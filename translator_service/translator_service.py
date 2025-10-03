from fastapi import FastAPI
from googletrans import Translator

app = FastAPI()
translator = Translator()

@app.get("/translate")
def translate_text(text: str, target: str = "en"):
    result = translator.translate(text, dest=target)
    return {
        "translated_text": result.text,
        "detected_lang": result.src
    }
