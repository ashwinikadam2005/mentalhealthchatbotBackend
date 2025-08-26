# # chatbot_routes.py
# from flask import Blueprint, render_template, request, jsonify
# import os
# import openai
# import speech_recognition as sr
# from dotenv import load_dotenv
# from googletrans import Translator   # ✅ use googletrans

# # Load environment variables
# load_dotenv()

# chatbot_bp = Blueprint("chatbot_bp", __name__)

# # Configure OpenRouter API
# openai.api_key = os.getenv("OPENROUTER_API_KEY")
# openai.api_base = "https://openrouter.ai/api/v1"

# # Initialize translator
# translator = Translator()

# # === Helper Functions ===
# def transcribe_audio(file_path):
#     recognizer = sr.Recognizer()
#     with sr.AudioFile(file_path) as source:
#         audio = recognizer.record(source)
#     return recognizer.recognize_google(audio)

# def detect_and_translate_to_english(text: str):
#     """Detect user language & translate to English"""
#     detected = translator.detect(text).lang
#     translated = translator.translate(text, src=detected, dest="en").text
#     return translated, detected

# def translate_back(text: str, dest_lang: str):
#     """Translate reply back to user’s original language"""
#     if dest_lang == "en":
#         return text
#     return translator.translate(text, src="en", dest=dest_lang).text

# def ask_openai(prompt: str):
#     """Query OpenAI via OpenRouter"""
#     response = openai.ChatCompletion.create(
#         model="openai/gpt-3.5-turbo",  
#         messages=[
#             {"role": "system", "content": "You are a supportive multilingual mental health chatbot."},
#             {"role": "user", "content": prompt}
#         ]
#     )
#     return response["choices"][0]["message"]["content"]

# # === Routes ===
# @chatbot_bp.route("/")
# def home():
#     return render_template("index.html")

# @chatbot_bp.route("/process", methods=["POST"])
# def process():
#     user_input = None
#     audio_file = request.files.get("audio")

#     if audio_file:  # 🎤 Voice message
#         audio_path = "temp.wav"
#         audio_file.save(audio_path)
#         try:
#             user_input = transcribe_audio(audio_path)
#         except Exception as e:
#             return jsonify({"error": f"Could not transcribe audio: {str(e)}"}), 400
#         finally:
#             os.remove(audio_path)
#     else:  # ⌨️ Text message
#         data = request.get_json()
#         if data:
#             user_input = data.get("text")
#             chat_id = data.get("chatId")

#     if not user_input:
#         return jsonify({"error": "No input provided"}), 400

#     translated_text, original_lang = detect_and_translate_to_english(user_input)
#     reply_en = ask_openai(translated_text)
#     final_reply = translate_back(reply_en, original_lang)

#     return jsonify({
#         "reply": final_reply,
#         "language": original_lang,
#         "chat": {
#             "_id": chat_id if chat_id else "temp",
#             "messages": [
#                 {"sender": "user", "text": user_input},
#                 {"sender": "bot", "text": final_reply}
#             ]
#         }
#     })


# routes/chatbot_routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.chat import Chat, Message
from models.user import User
from datetime import datetime
import os
import openai
from dotenv import load_dotenv
from googletrans import Translator

load_dotenv()

chatbot_bp = Blueprint("chatbot_bp", __name__)

# Optional OpenRouter config (fallback to echo if no key)
openai.api_key = os.getenv("OPENROUTER_API_KEY")
openai.api_base = "https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None

translator = Translator()

def detect_and_translate_to_english(text: str):
    detected = translator.detect(text).lang
    translated = translator.translate(text, src=detected, dest="en").text
    return translated, detected

def translate_back(text: str, dest_lang: str):
    if dest_lang == "en":
        return text
    return translator.translate(text, src="en", dest=dest_lang).text

def ask_large_model(prompt: str) -> str:
    if openai.api_key and openai.api_base:
        try:
            resp = openai.ChatCompletion.create(
                model="openai/gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a supportive multilingual mental health chatbot."},
                    {"role": "user", "content": prompt}
                ],
                timeout=30,
            )
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            # fallback to echo
            return f"(fallback) You said: {prompt}"
    else:
        return f"(echo) You said: {prompt}"

# ---- Routes ----

@chatbot_bp.route("/chats", methods=["GET"])
@jwt_required()
def get_chats():
    user_id = get_jwt_identity()
    user = User.objects(id=user_id).first()
    if not user:
        return jsonify([]), 200
    chats = Chat.objects(user=user).order_by("-updated_at")
    return jsonify([c.to_dict() for c in chats]), 200

@chatbot_bp.route("/new", methods=["POST"])
@jwt_required()
def new_chat():
    user_id = get_jwt_identity()
    user = User.objects(id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    chat = Chat(user=user, title="New Chat", messages=[])
    chat.save()
    return jsonify(chat.to_dict()), 201

@chatbot_bp.route("/process", methods=["POST"])
@jwt_required()
def process():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    chat_id = data.get("chatId")
    user_id = get_jwt_identity()

    if not text:
        return jsonify({"error": "No input provided"}), 400

    user = User.objects(id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # If no chatId, start a new chat automatically
    if chat_id:
        chat = Chat.objects(id=chat_id, user=user).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
    else:
        chat = Chat(user=user, title="New Chat", messages=[])
        chat.save()

    # Translate -> LLM -> Translate back
    translated_text, original_lang = detect_and_translate_to_english(text)
    reply_en = ask_large_model(translated_text)
    final_reply = translate_back(reply_en, original_lang)

    # Save messages
    chat.messages.append(Message(sender="user", text=text))
    chat.messages.append(Message(sender="bot", text=final_reply))
    chat.updated_at = datetime.utcnow()
    chat.save()

    return jsonify(chat.to_dict()), 200

@chatbot_bp.route("/chats/<chat_id>", methods=["GET"])
@jwt_required()
def get_chat(chat_id):
    user_id = get_jwt_identity()
    user = User.objects(id=user_id).first()
    chat = Chat.objects(id=chat_id, user=user).first()
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    return jsonify(chat.to_dict()), 200
