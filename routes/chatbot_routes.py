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


# # routes/chatbot_routes.py
# from flask import Blueprint, request, jsonify
# from flask_jwt_extended import jwt_required, get_jwt_identity
# from models.chat import Chat, Message
# from models.user import User
# from datetime import datetime
# import os
# import openai
# from dotenv import load_dotenv
# from googletrans import Translator

# load_dotenv()

# chatbot_bp = Blueprint("chatbot_bp", __name__)

# # Optional OpenRouter config (fallback to echo if no key)
# openai.api_key = os.getenv("OPENROUTER_API_KEY")
# openai.api_base = "https://openrouter.ai/api/v1" if os.getenv("OPENROUTER_API_KEY") else None

# translator = Translator()

# def detect_and_translate_to_english(text: str):
#     detected = translator.detect(text).lang
#     translated = translator.translate(text, src=detected, dest="en").text
#     return translated, detected

# def translate_back(text: str, dest_lang: str):
#     if dest_lang == "en":
#         return text
#     return translator.translate(text, src="en", dest=dest_lang).text

# def ask_large_model(prompt: str) -> str:
#     if openai.api_key and openai.api_base:
#         try:
#             resp = openai.ChatCompletion.create(
#                 model="openai/gpt-3.5-turbo",
#                 messages=[
#                     {"role": "system", "content": "You are a supportive multilingual mental health chatbot."},
#                     {"role": "user", "content": prompt}
#                 ],
#                 timeout=30,
#             )
#             return resp["choices"][0]["message"]["content"]
#         except Exception as e:
#             # fallback to echo
#             return f"(fallback) You said: {prompt}"
#     else:
#         return f"(echo) You said: {prompt}"

# # ---- Routes ----

# @chatbot_bp.route("/chats", methods=["GET"])
# @jwt_required()
# def get_chats():
#     user_id = get_jwt_identity()
#     user = User.objects(id=user_id).first()
#     if not user:
#         return jsonify([]), 200
#     chats = Chat.objects(user=user).order_by("-updated_at")
#     return jsonify([c.to_dict() for c in chats]), 200

# @chatbot_bp.route("/new", methods=["POST"])
# @jwt_required()
# def new_chat():
#     user_id = get_jwt_identity()
#     user = User.objects(id=user_id).first()
#     if not user:
#         return jsonify({"error": "User not found"}), 404

#     chat = Chat(user=user, title="New Chat", messages=[])
#     chat.save()
#     return jsonify(chat.to_dict()), 201

# @chatbot_bp.route("/process", methods=["POST"])
# @jwt_required()
# def process():
#     data = request.get_json() or {}
#     text = (data.get("text") or "").strip()
#     chat_id = data.get("chatId")
#     user_id = get_jwt_identity()

#     if not text:
#         return jsonify({"error": "No input provided"}), 400

#     user = User.objects(id=user_id).first()
#     if not user:
#         return jsonify({"error": "User not found"}), 404

#     # If no chatId, start a new chat automatically
#     if chat_id:
#         chat = Chat.objects(id=chat_id, user=user).first()
#         if not chat:
#             return jsonify({"error": "Chat not found"}), 404
#     else:
#         chat = Chat(user=user, title="New Chat", messages=[])
#         chat.save()

#     # Translate -> LLM -> Translate back
#     translated_text, original_lang = detect_and_translate_to_english(text)
#     reply_en = ask_large_model(translated_text)
#     final_reply = translate_back(reply_en, original_lang)

#     # Save messages
#     chat.messages.append(Message(sender="user", text=text))
#     chat.messages.append(Message(sender="bot", text=final_reply))
#     chat.updated_at = datetime.utcnow()
#     chat.save()

#     return jsonify(chat.to_dict()), 200

# @chatbot_bp.route("/chats/<chat_id>", methods=["GET"])
# @jwt_required()
# def get_chat(chat_id):
#     user_id = get_jwt_identity()
#     user = User.objects(id=user_id).first()
#     chat = Chat.objects(id=chat_id, user=user).first()
#     if not chat:
#         return jsonify({"error": "Chat not found"}), 404
#     return jsonify(chat.to_dict()), 200



# routes/chatbot_routes.py
# routes/chatbot_routes.py
from flask_cors import CORS

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.chat import Chat, Message
from models.user import User
from models.doctor import Doctor
from datetime import datetime
import os
import openai
from dotenv import load_dotenv
import re
import tempfile
from gtts import gTTS  # for text-to-speech
from chatbot_engine import get_chatbot_response  # ✅ PDF QA
import requests
from urllib.parse import urlencode

load_dotenv()

chatbot_bp = Blueprint("chatbot_bp", __name__)


# Translator microservice endpoint (fallback to direct translation)
TRANSLATOR_URL = "http://127.0.0.1:9000/translate"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# triage flow questions in multiple languages
triage_questions = {
    "en": [
        {"key": "age", "question": "What is your age?"},
        {
            "key": "problem",
            "question": (
                "What mental health concern are you facing? "
                "Examples: anxiety, stress, sadness, insomnia, panic, headache."
            ),
        },
        {
            "key": "type",
            "question": (
                "Can you describe the type or pattern? "
                "Examples: for anxiety (general worry, social anxiety), for headaches (tension, migraine)."
            ),
        },
        {"key": "duration", "question": "How long have you been experiencing this? (e.g., hours, days, weeks)"},
        {"key": "triggers", "question": "Have you noticed any triggers or patterns? (e.g., lack of sleep, screens, arguments, caffeine)"},
        {"key": "impact", "question": "How is this affecting your daily life (work, study, relationships)?"},
        {"key": "coping", "question": "What have you tried so far (medication, rest, breathing, therapy)?"},
        {"key": "severity", "question": "On a scale of 1–10, how severe is it now?"},
    ],
    "hi": [
        {"key": "age", "question": "आपकी उम्र क्या है?"},
        {
            "key": "problem",
            "question": (
                "आप किस मानसिक स्वास्थ्य समस्या का सामना कर रहे हैं? "
                "उदाहरण: चिंता, तनाव, उदासी, अनिद्रा, घबराहट, सिरदर्द।"
            ),
        },
        {
            "key": "type",
            "question": (
                "क्या आप प्रकार या पैटर्न बता सकते हैं? "
                "उदाहरण: चिंता के लिए (सामान्य चिंता, सामाजिक चिंता), सिरदर्द के लिए (तनाव, माइग्रेन)।"
            ),
        },
        {"key": "duration", "question": "आप इसे कितने समय से अनुभव कर रहे हैं? (जैसे घंटे, दिन, सप्ताह)"},
        {"key": "triggers", "question": "क्या आपने कोई ट्रिगर या पैटर्न देखा है? (जैसे नींद की कमी, स्क्रीन, तर्क, कैफीन)"},
        {"key": "impact", "question": "यह आपके दैनिक जीवन (काम, अध्ययन, रिश्ते) को कैसे प्रभावित कर रहा है?"},
        {"key": "coping", "question": "आपने अब तक क्या कोशिश की है? (दवा, आराम, सांस लेने की तकनीक, थेरेपी)"},
        {"key": "severity", "question": "1-10 के पैमाने पर, अब यह कितना गंभीर है?"},
    ],
    "mr": [
        {"key": "age", "question": "तुमचे वय काय आहे?"},
        {
            "key": "problem",
            "question": (
                "तुम्ही कोणत्या मानसिक आरोग्य समस्येचा सामना करत आहात? "
                "उदाहरणे: चिंता, ताण, दुःख, अनिद्रा, घबराट, डोकेदुखी।"
            ),
        },
        {
            "key": "type",
            "question": (
                "तुम्ही प्रकार किंवा नमुना वर्णन करू शकता का? "
                "उदाहरणे: चिंतेसाठी (सामान्य काळजी, सामाजिक चिंता), डोकेदुखीसाठी (ताण, मायग्रेन)।"
            ),
        },
        {"key": "duration", "question": "तुम्ही हे किती काळ अनुभवत आहात? (जसे तास, दिवस, आठवडे)"},
        {"key": "triggers", "question": "तुम्ही काही ट्रिगर किंवा नमुने पाहिले आहेत का? (जसे झोपेची कमतरता, स्क्रीन, वाद, कॅफीन)"},
        {"key": "impact", "question": "हे तुमच्या दैनंदिन जीवनावर (काम, अभ्यास, नातेसंबंध) कसे परिणाम करत आहे?"},
        {"key": "coping", "question": "तुम्ही आतापर्यंत काय प्रयत्न केले आहेत? (औषध, विश्रांती, श्वासोच्छवास तंत्र, थेरपी)"},
        {"key": "severity", "question": "1-10 च्या प्रमाणात, आता ते किती गंभीर आहे?"},
    ]
}

def detect_user_language(text: str):
    """Detect user's language from their input with robust heuristics.
    - If mostly Latin letters → English
    - If Devanagari present → Hindi unless Marathi-specific chars present
    """
    if not text:
        return "en"

    latin_count = sum(1 for ch in text if ('a' <= ch.lower() <= 'z'))
    devanagari_count = sum(1 for ch in text if '\u0900' <= ch <= '\u097F')
    total_letters = latin_count + devanagari_count

    if total_letters == 0:
        return "en"

    # If majority Latin, prefer English
    if latin_count / max(1, total_letters) >= 0.6:
        return "en"

    if devanagari_count > 0:
        marathi_specific = {'ळ', 'ऱ', 'ॅ', 'य़', 'ॲ', 'ॐ'}
        if any(ch in marathi_specific for ch in text):
            return "mr"
        return "hi"

    return "en"

def next_triage_question(chat):
    """Return the next triage question or None if all answered"""
    user_lang = chat.metadata.get("user_language", "en")
    questions = triage_questions.get(user_lang, triage_questions["en"])
    
    for q in questions:
        if q["key"] not in chat.metadata:
            return q
    return None

# Optional OpenRouter config (fallback to echo if no key)
openai.api_key = os.getenv("OPENROUTER_API_KEY")
openai.api_base = "https://openrouter.ai/api/v1" if openai.api_key else None


# --- Translation helpers (with fallback) ---
def detect_and_translate_to_english(text: str):
    try:
        resp = requests.get(TRANSLATOR_URL, params={"text": text, "target": "en"})
        data = resp.json()
        return data["translated_text"], data["detected_lang"]
    except Exception as e:
        print(f"⚠️ Translator service error: {e}")
        # Fallback: simple language detection and translation
        return translate_with_fallback(text, "en")

def translate_back(text: str, dest_lang: str):
    if dest_lang == "en":
        return text
    try:
        resp = requests.get(TRANSLATOR_URL, params={"text": text, "target": dest_lang})
        data = resp.json()
        return data["translated_text"]
    except Exception as e:
        print(f"⚠️ Translator service error: {e}")
        # Fallback: simple translation
        return translate_with_fallback(text, dest_lang)

def translate_with_fallback(text: str, target_lang: str):
    """Simple fallback translation for common languages"""
    # Basic language detection
    if any(char in text for char in ['अ', 'आ', 'इ', 'ई', 'उ', 'ऊ', 'ए', 'ऐ', 'ओ', 'औ']):
        detected_lang = "hi"  # Hindi
    elif any(char in text for char in ['अ', 'आ', 'इ', 'ई', 'उ', 'ऊ', 'ए', 'ऐ', 'ओ', 'औ', 'क', 'ख', 'ग', 'घ']):
        detected_lang = "mr"  # Marathi
    else:
        detected_lang = "en"  # English
    
    # Simple keyword-based translation for mental health terms
    translations = {
        "hi": {
            "anxiety": "चिंता",
            "stress": "तनाव", 
            "depression": "अवसाद",
            "sadness": "उदासी",
            "headache": "सिरदर्द",
            "help": "मदद",
            "doctor": "डॉक्टर",
            "medicine": "दवा"
        },
        "mr": {
            "anxiety": "चिंता",
            "stress": "ताण",
            "depression": "नैराश्य",
            "sadness": "दुःख",
            "headache": "डोकेदुखी",
            "help": "मदत",
            "doctor": "डॉक्टर",
            "medicine": "औषध"
        }
    }
    
    if detected_lang == target_lang:
        return text
    
    # Simple translation using keyword mapping
    result = text
    if target_lang in translations:
        for eng, local in translations[target_lang].items():
            result = result.replace(eng, local)
    
    return result


# --- YouTube helper ---
def search_youtube_videos(query: str, max_results: int = 5):
    if not YOUTUBE_API_KEY:
        return {"error": "Missing YOUTUBE_API_KEY"}
    try:
        params = {
            "key": YOUTUBE_API_KEY,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": max_results,
            "safeSearch": "strict",
            "relevanceLanguage": "en",
        }
        url = f"https://www.googleapis.com/youtube/v3/search?{urlencode(params)}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        results = []
        for it in items:
            vid = it.get("id", {}).get("videoId")
            title = (it.get("snippet", {}) or {}).get("title", "")
            if vid:
                results.append({
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={vid}"
                })
        return {"results": results}
    except Exception as e:
        print(f"⚠️ YouTube search error: {e}")
        return {"error": str(e)}

# --- LLM helper (OpenRouter/OpenAI or echo fallback) ---
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
            print(f"⚠️ LLM error: {e}")
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

    # find or create chat
    if chat_id:
        chat = Chat.objects(id=chat_id, user=user).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
    else:
        chat = Chat(user=user, title="New Chat", messages=[], metadata={})
        chat.save()

    # save user msg
    chat.messages.append(Message(sender="user", text=text))

    # --- POST-TRIAGE CONFIRMATION HANDLER ---
    # If we previously asked whether to connect to a professional, interpret yes/no
    awaiting_confirm = chat.metadata.get("awaiting_connect_confirmation", False)
    if awaiting_confirm:
        normalized = text.strip().lower()
        yes_words = {"yes", "y", "yeah", "yup", "sure", "ok", "okay", "please", "connect"}
        no_words = {"no", "n", "nah", "not now", "later", "cancel"}

        if normalized in yes_words or any(w in normalized for w in ["yes", "sure", "ok", "connect"]):
            chat.metadata["awaiting_connect_confirmation"] = False
            # Fetch a few doctors from DB
            doctors = [d.to_dict() for d in Doctor.objects().limit(5)]
            helplines = [
                {"name": "Suicide & Crisis Lifeline (India)", "phone": "9152987821"},
                {"name": "Emergency", "phone": "112"},
            ]

            doctor_lines = [
                f"• {d['name']} — {d.get('qualification','')} — {d.get('phone','')}" for d in doctors
            ] or ["• (No doctors available right now)"]

            helpline_lines = [f"• {h['name']}: {h['phone']}" for h in helplines]

            reply_en = (
                "Okay. Here are available professionals you can contact:\n" +
                "\n".join(doctor_lines) +
                "\n\nHelplines:\n" +
                "\n".join(helpline_lines) +
                "\n\nPlease call your local emergency number if you're in immediate danger."
            )
            final_reply = translate_back(reply_en, "en")
            chat.messages.append(Message(sender="bot", text=final_reply))
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200
        if normalized in no_words or any(w in normalized for w in ["no", "later", "not now"]):
            chat.metadata["awaiting_connect_confirmation"] = False
            reply_en = (
                "Understood. I’ll be here if you need me. "
                "Meanwhile, consider breathing exercises, hydration, and short breaks. "
                "You can also ask me for coping techniques or resources."
            )
            final_reply = translate_back(reply_en, "en")
            chat.messages.append(Message(sender="bot", text=final_reply))
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200

    # --- YOUTUBE VIDEO SUGGESTION HANDLER ---
    # Only after triage is complete, and only if explicitly asked for videos
    if chat.metadata.get("triage_complete"):
        normalized_for_video = text.strip().lower()
        video_keywords = {
            "en": ["video", "videos", "youtube", "yoga", "exercise", "exercises", "workout", "breathing", "meditation", "sleep", "relaxation", "mindfulness", "stretching"],
            "hi": ["वीडियो", "विडियो", "वीडियोज", "यूट्यूब", "योग", "व्यायाम", "श्वसन", "सांस", "ध्यान", "नींद", "आराम", "माइंडफुलनेस"],
            "mr": ["व्हिडिओ", "विडिओ", "युट्युब", "योग", "व्यायाम", "श्वसन", "ध्यान", "झोप", "विश्रांती", "माइंडफुलनेस", "स्ट्रेचिंग"]
        }
        user_lang_for_video = chat.metadata.get("user_language", "en")
        keys = video_keywords.get(user_lang_for_video, video_keywords["en"]) + video_keywords["en"]
        if any(k in normalized_for_video for k in keys):
            # Build a query based on user's concern/type/triggers plus the text
            topic_parts = [
                str(chat.metadata.get("problem", "")),
                str(chat.metadata.get("type", "")),
                str(chat.metadata.get("triggers", "")),
            ]
            base_query = " ".join([p for p in topic_parts if p]).strip()
            if not base_query:
                base_query = "mental health"
            final_query = f"{base_query} {text} tutorial guidance"
            yt = search_youtube_videos(final_query, max_results=5)
            if yt.get("results"):
                lines = [f"• {item['title']}: {item['url']}" for item in yt["results"]]
                reply_en = "Here are some helpful YouTube videos:\n" + "\n".join(lines)
            else:
                err = yt.get("error")
                if err and "YOUTUBE_API_KEY" in err:
                    reply_en = "Video search is not configured on the server. Please set YOUTUBE_API_KEY."
                else:
                    reply_en = "Sorry, I couldn't find videos right now. Please try again later."
            final_reply = translate_back(reply_en, "en")
            chat.messages.append(Message(sender="bot", text=final_reply))
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200

    # --- ALTERNATIVE SUGGESTIONS HANDLER ---
    # If triage complete and user asks for another/different solution, rotate suggestions
    if chat.metadata.get("triage_complete"):
        normalized = text.strip().lower()
        alt_triggers = [
            "another", "alternative", "different", "more", "else", "other", "next",
            "not working", "didn't work", "did not work", "any other", "try something"
        ]
        if any(phrase in normalized for phrase in alt_triggers):
            severity_level = int(chat.metadata.get("severity_level", 0) or 0)

            mild_tips = [
                "Try a short walk or gentle stretching for 10–15 minutes.",
                "Practice 4-7-8 breathing for 2 minutes to lower stress.",
                "Limit caffeine for the next few hours and hydrate well.",
                "Use a warm compress on the neck/forehead for relaxation.",
            ]
            moderate_tips = [
                "Try progressive muscle relaxation for 5–10 minutes.",
                "Use guided mindfulness (e.g., body scan) via a free app.",
                "Schedule consistent sleep and reduce screen time before bed.",
                "Try over-the-counter pain relief if appropriate; follow label guidance.",
            ]
            severe_tips = [
                "Find a quiet, dark room and practice paced breathing for 5 minutes.",
                "Apply cold or warm compress based on comfort; avoid triggers (noise/light).",
                "If pain persists or worsens, consult a clinician promptly.",
                "Keep a brief log of triggers (food, sleep, stress) to discuss with a professional.",
            ]

            if severity_level <= 4:
                tips = mild_tips
            elif severity_level <= 7:
                tips = moderate_tips
            else:
                tips = severe_tips

            idx = int(chat.metadata.get("alt_tip_index", -1)) + 1
            idx = idx % len(tips)
            chat.metadata["alt_tip_index"] = idx

            alt_text = tips[idx]
            # Also try to get a different approach from LLM
            try:
                llm_extra = ask_large_model(
                    f"User says previous suggestion didn't work. Provide a DIFFERENT, practical, safe alternative for: {text}. Keep it short."
                )
            except Exception:
                llm_extra = ""

            reply_parts = [f"Another approach: {alt_text}"]
            if llm_extra:
                reply_parts.append(llm_extra)

            reply_en = "\n\n".join(reply_parts)
            final_reply = translate_back(reply_en, "en")
            chat.messages.append(Message(sender="bot", text=final_reply))
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200

    # --- SEVERITY UPDATE HANDLER (after triage complete) ---
    if chat.metadata.get("triage_complete") and not chat.metadata.get("awaiting_connect_confirmation"):
        # Check if user is providing a new severity rating
        try:
            match = re.search(r"\b(10|[1-9])\b", text.strip())
            new_severity = int(match.group(1)) if match else None
            if new_severity is not None and 1 <= new_severity <= 10:
                # Update severity and provide appropriate response
                chat.metadata["severity"] = new_severity
                chat.metadata["severity_level"] = new_severity
                
                user_lang = chat.metadata.get("user_language", "en")
                
                # Define advice texts for different severity levels
                advice_texts = {
                    "en": {
                        "mild": "Based on what you shared, this seems mild. Try deep breathing (4-7-8), short walks, hydration, limit screens, and good sleep hygiene. If symptoms persist or worsen, consider professional advice.",
                        "moderate": "This looks moderate. I can share coping tips now and also connect you with a professional. Would you like me to connect you?",
                        "severe": "This seems severe. I strongly recommend speaking with a professional immediately. Should I connect you now?"
                    },
                    "hi": {
                        "mild": "आपने जो साझा किया है, उसके आधार पर यह हल्का लगता है। गहरी सांस लेने (4-7-8), छोटी सैर, हाइड्रेशन, स्क्रीन सीमित करने और अच्छी नींद की आदतों को आजमाएं। यदि लक्षण बने रहते हैं या बिगड़ते हैं, तो पेशेवर सलाह पर विचार करें।",
                        "moderate": "यह मध्यम लगता है। मैं अभी सामना करने की युक्तियाँ साझा कर सकता हूँ और आपको एक पेशेवर से भी जोड़ सकता हूँ। क्या आप चाहते हैं कि मैं आपको जोड़ूं?",
                        "severe": "यह गंभीर लगता है। मैं दृढ़ता से सुझाव देता हूं कि तुरंत एक पेशेवर से बात करें। क्या मैं अब आपको जोड़ूं?"
                    },
                    "mr": {
                        "mild": "तुम्ही सामायिक केलेल्या माहितीच्या आधारे हे हलके वाटते. खोल श्वास घेणे (4-7-8), लहान चाल, हायड्रेशन, स्क्रीन मर्यादित करणे आणि चांगल्या झोपेच्या सवयी वापरा. जर लक्षणे टिकत राहतात किंवा वाढतात, तर व्यावसायिक सल्ला विचारात घ्या.",
                        "moderate": "हे मध्यम वाटते. मी आता सामना करण्याच्या युक्त्या सामायिक करू शकतो आणि तुम्हाला व्यावसायिकाशी देखील जोडू शकतो. तुम्हाला मी जोडायचे आहे का?",
                        "severe": "हे गंभीर वाटते. मी दृढपणे सुचवतो की त्वरित व्यावसायिकाशी बोला. मी आता तुम्हाला जोडू का?"
                    }
                }
                
                # Get appropriate response based on new severity
                if new_severity <= 4:
                    reply_text = advice_texts.get(user_lang, advice_texts["en"])["mild"]
                    chat.metadata["awaiting_connect_confirmation"] = False
                elif new_severity <= 7:
                    reply_text = advice_texts.get(user_lang, advice_texts["en"])["moderate"]
                    chat.metadata["awaiting_connect_confirmation"] = True
                else:
                    reply_text = advice_texts.get(user_lang, advice_texts["en"])["severe"]
                    chat.metadata["awaiting_connect_confirmation"] = True
                
                chat.messages.append(Message(sender="bot", text=reply_text))
                chat.updated_at = datetime.utcnow()
                chat.save()
                return jsonify(chat.to_dict()), 200
        except ValueError:
            pass  # Not a severity number, continue to other handlers

    # --- PERSONALIZED ALTERNATIVE SOLUTIONS HANDLER (after triage complete) ---
    if chat.metadata.get("triage_complete") and not chat.metadata.get("awaiting_connect_confirmation"):
        # Check if user is asking for different solutions
        alternative_keywords = {
            "en": ["different", "other", "alternative", "another", "new", "more", "else", "try", "suggest", "not working"],
            "hi": ["अलग", "दूसरा", "वैकल्पिक", "और", "नया", "अधिक", "अन्य", "कोशिश", "सुझाव", "काम नहीं"],
            "mr": ["वेगळे", "दुसरे", "पर्यायी", "आणखी", "नवीन", "अधिक", "इतर", "प्रयत्न", "सूचना", "काम नाही"]
        }
        
        user_lang = chat.metadata.get("user_language", "en")
        keywords = alternative_keywords.get(user_lang, alternative_keywords["en"])
        normalized = text.strip().lower()
        
        if any(keyword in normalized for keyword in keywords):
            # User wants alternative solutions → provide personalized alternatives
            user_context = f"""
            Patient Details:
            - Age: {chat.metadata.get('age', 'N/A')}
            - Problem: {chat.metadata.get('problem', 'N/A')} ({chat.metadata.get('type', 'N/A')})
            - Duration: {chat.metadata.get('duration', 'N/A')}
            - Triggers: {chat.metadata.get('triggers', 'N/A')}
            - Impact: {chat.metadata.get('impact', 'N/A')}
            - Previous attempts: {chat.metadata.get('coping', 'N/A')}
            - Severity: {chat.metadata.get('severity_level', 'N/A')}/10
            """
            
            try:
                alternative_prompt = f"Based on this person's specific situation: {user_context}\n\nThey tried the previous suggestions but need different alternatives. Provide 3-4 specific, personalized alternative coping strategies that are different from what they already tried. Be specific to their age, problem type, and triggers. Talk to them directly, not about them."
                alternative_advice = ask_large_model(alternative_prompt)
                
                if alternative_advice:
                    reply_text = f"💡 Here are some alternative strategies tailored to your situation:\n\n{alternative_advice}"
                else:
                    # Fallback to generic alternatives
                    generic_alternatives = {
                        "en": "Here are some alternative strategies you can try:\n• Progressive muscle relaxation\n• Mindfulness meditation\n• Journaling your thoughts\n• Physical exercise\n• Talking to a trusted friend",
                        "hi": "यहाँ कुछ वैकल्पिक रणनीतियाँ हैं जो आप आजमा सकते हैं:\n• प्रगतिशील मांसपेशी विश्राम\n• माइंडफुलनेस ध्यान\n• अपने विचारों को लिखना\n• शारीरिक व्यायाम\n• किसी भरोसेमंद दोस्त से बात करना",
                        "mr": "येथे काही पर्यायी रणनीती आहेत ज्या तुम्ही वापरू शकता:\n• प्रगतिशील स्नायू विश्रांती\n• माइंडफुलनेस ध्यान\n• तुमच्या विचारांची नोंद करणे\n• शारीरिक व्यायाम\n• विश्वासू मित्राशी बोलणे"
                    }
                    reply_text = generic_alternatives.get(user_lang, generic_alternatives["en"])
            except Exception as e:
                print(f"⚠️ Alternative advice error: {e}")
                reply_text = "I'm here to help. Could you tell me more about what specific support you need?"
            
            chat.messages.append(Message(sender="bot", text=reply_text))
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200

    # --- INTELLIGENT CONVERSATION HANDLER (after triage complete) ---
    if chat.metadata.get("triage_complete"):
        user_lang = chat.metadata.get("user_language", "en")
        
        # Create comprehensive user context for intelligent analysis
        user_context = f"""
        Patient Profile:
        - Age: {chat.metadata.get('age', 'N/A')} years old
        - Mental Health Concern: {chat.metadata.get('problem', 'N/A')} 
        - Specific Type: {chat.metadata.get('type', 'N/A')}
        - Duration: {chat.metadata.get('duration', 'N/A')}
        - Triggers: {chat.metadata.get('triggers', 'N/A')}
        - Impact on Life: {chat.metadata.get('impact', 'N/A')}
        - Previous Coping Attempts: {chat.metadata.get('coping', 'N/A')}
        - Current Severity: {chat.metadata.get('severity_level', 'N/A')}/10
        - Language: {user_lang}
        """
        
        try:
            # Create intelligent prompt that analyzes the user's specific situation
            intelligent_prompt = f"""
            You are an advanced mental health AI assistant with access to current research and evidence-based practices. 
            Analyze this person's specific situation and provide personalized, intelligent advice.
            
            PERSON'S SITUATION:
            {user_context}
            
            THEIR CURRENT REQUEST: "{text}"
            
            ANALYSIS INSTRUCTIONS:
            1. **Deep Analysis**: Analyze their specific mental health concern, age group, triggers, and current situation
            2. **Pattern Recognition**: Identify patterns in their symptoms, triggers, and coping attempts
            3. **Personalization**: Consider their age, lifestyle (study/work), and specific triggers (arguments)
            4. **Evidence-Based**: Provide current, evidence-based strategies and techniques
            5. **Practical Application**: Give step-by-step instructions for techniques they request
            6. **Severity Consideration**: Adjust advice based on their severity level (9/10 is severe)
            7. **Previous Attempts**: Consider what they've already tried and suggest alternatives
            8. **Contextual Relevance**: Tailor advice to their specific situation and triggers
            
            RESPONSE GUIDELINES:
            - Be empathetic and supportive
            - Provide actionable, evidence-based strategies
            - Talk directly to them, not about them
            - Keep responses practical and easy to follow
            - If asking for techniques, provide 3-4 specific methods with clear instructions
            - Consider their specific triggers (arguments) and impact (study)
            - Address their age-appropriate needs (40-year-old)
            - Provide alternatives to what they've already tried (rest)
            
            Respond with intelligent, personalized advice that directly addresses their specific needs and situation.
            """
            
            intelligent_response = ask_large_model(intelligent_prompt)
            
            if intelligent_response:
                # Translate response to user's language if needed
                if user_lang != "en":
                    try:
                        intelligent_response = translate_back(intelligent_response, user_lang)
                    except Exception as e:
                        print(f"⚠️ Translation error: {e}")
                        # Keep original response if translation fails
                
                chat.messages.append(Message(sender="bot", text=intelligent_response))
                chat.updated_at = datetime.utcnow()
                chat.save()
                return jsonify(chat.to_dict()), 200
        except Exception as e:
            print(f"⚠️ Intelligent conversation error: {e}")
            pass  # Continue to other handlers

    # --- GREETING HANDLER (before triage starts) ---
    if not chat.metadata:
        normalized_hi = text.strip().lower()
        greeting_words = {"hi", "hello", "hey", "hola", "namaste", "good morning", "good evening", "नमस्ते", "नमस्कार", "हाय", "हैलो"}
        if any(w in normalized_hi for w in greeting_words):
            # Detect user language from greeting
            user_lang = detect_user_language(text)
            chat.metadata["user_language"] = user_lang
            
            greetings = {
                "en": "Hello! I'm here to help. Let's begin with a few basics.\nWhat is your age?",
                "hi": "नमस्ते! मैं मदद के लिए यहाँ हूँ। आइए कुछ बुनियादी बातों से शुरू करते हैं।\nआपकी उम्र क्या है?",
                "mr": "नमस्कार! मी मदतीसाठी इथे आहे. काही मूलभूत गोष्टींपासून सुरुवात करूया.\nतुमचे वय काय आहे?"
            }
            
            reply_text = greetings.get(user_lang, greetings["en"])
            chat.messages.append(Message(sender="bot", text=reply_text))
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200

    # Refresh language each turn cautiously based on current message
    prev_lang = chat.metadata.get("user_language")
    # Determine if the message contains any language letters
    has_letters = bool(re.search(r"[A-Za-z\u0900-\u097F]", text))
    if has_letters:
        # If letters present, detect and update
        chat.metadata["user_language"] = detect_user_language(text)
    else:
        # For numeric/emoji-only inputs, preserve previous language if set
        if prev_lang:
            chat.metadata["user_language"] = prev_lang
        else:
            chat.metadata["user_language"] = "en"

    # --- TRIAGE FLOW ---
    q = next_triage_question(chat)
    if q:
        # validate and save answer for the *current* missing key
        key = q["key"]
        user_lang = chat.metadata.get("user_language", "en")
        
        if key == "age":
            try:
                age_val = int(text.strip())
                if age_val <= 0 or age_val > 120:
                    raise ValueError()
                chat.metadata["age"] = age_val
            except Exception:
                age_errors = {
                    "en": "Please enter your age as a number (e.g., 25).",
                    "hi": "कृपया अपनी उम्र एक संख्या के रूप में दर्ज करें (जैसे, 25)।",
                    "mr": "कृपया तुमचे वय संख्येच्या रूपात प्रविष्ट करा (जसे, 25)।"
                }
                reply_text = age_errors.get(user_lang, age_errors["en"])
                chat.messages.append(Message(sender="bot", text=reply_text))
                chat.updated_at = datetime.utcnow()
                chat.save()
                return jsonify(chat.to_dict()), 200
        elif key == "severity":
            try:
                sev = int(text.strip())
                if sev < 1 or sev > 10:
                    raise ValueError()
                chat.metadata["severity"] = sev
            except Exception:
                severity_errors = {
                    "en": "Please rate severity from 1 to 10 (e.g., 4).",
                    "hi": "कृपया गंभीरता को 1 से 10 के पैमाने पर रेट करें (जैसे, 4)।",
                    "mr": "कृपया गंभीरता 1 ते 10 च्या प्रमाणात रेट करा (जसे, 4)।"
                }
                reply_text = severity_errors.get(user_lang, severity_errors["en"])
                chat.messages.append(Message(sender="bot", text=reply_text))
                chat.updated_at = datetime.utcnow()
                chat.save()
                return jsonify(chat.to_dict()), 200
        else:
            chat.metadata[key] = text

        # move to next missing question
        next_q = next_triage_question(chat)
        if next_q:
            reply_text = next_q["question"]
            chat.messages.append(Message(sender="bot", text=reply_text))
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200
        else:
            # triage complete → build summary and severity-based guidance
            user_lang = chat.metadata.get("user_language", "en")
            
            summaries = {
                "en": (
                    f"Thanks, I've collected your details. Summary:\n"
                    f"• Age: {chat.metadata.get('age', 'N/A')}\n"
                    f"• Concern: {chat.metadata.get('problem', 'N/A')} ({chat.metadata.get('type', 'N/A')})\n"
                    f"• Duration: {chat.metadata.get('duration', 'N/A')}\n"
                    f"• Triggers: {chat.metadata.get('triggers', 'N/A')}\n"
                    f"• Impact: {chat.metadata.get('impact', 'N/A')}\n"
                    f"• Tried: {chat.metadata.get('coping', 'N/A')}\n"
                ),
                "hi": (
                    f"धन्यवाद, मैंने आपके विवरण एकत्र किए हैं। सारांश:\n"
                    f"• उम्र: {chat.metadata.get('age', 'N/A')}\n"
                    f"• समस्या: {chat.metadata.get('problem', 'N/A')} ({chat.metadata.get('type', 'N/A')})\n"
                    f"• अवधि: {chat.metadata.get('duration', 'N/A')}\n"
                    f"• ट्रिगर: {chat.metadata.get('triggers', 'N/A')}\n"
                    f"• प्रभाव: {chat.metadata.get('impact', 'N/A')}\n"
                    f"• कोशिश की: {chat.metadata.get('coping', 'N/A')}\n"
                ),
                "mr": (
                    f"धन्यवाद, मी तुमची माहिती गोळा केली आहे. सारांश:\n"
                    f"• वय: {chat.metadata.get('age', 'N/A')}\n"
                    f"• समस्या: {chat.metadata.get('problem', 'N/A')} ({chat.metadata.get('type', 'N/A')})\n"
                    f"• कालावधी: {chat.metadata.get('duration', 'N/A')}\n"
                    f"• ट्रिगर: {chat.metadata.get('triggers', 'N/A')}\n"
                    f"• परिणाम: {chat.metadata.get('impact', 'N/A')}\n"
                    f"• प्रयत्न केले: {chat.metadata.get('coping', 'N/A')}\n"
                )
            }
            
            summary = summaries.get(user_lang, summaries["en"])

            try:
                severity_val = int(chat.metadata.get("severity", 0))
            except Exception:
                severity_val = 0

            advice_texts = {
                "en": {
                    "mild": (
                        "Based on what you shared, this seems mild. "
                        "Try deep breathing (4-7-8), short walks, hydration, limit screens, and good sleep hygiene. "
                        "If symptoms persist or worsen, consider professional advice."
                    ),
                    "moderate": (
                        "This looks moderate. I can share coping tips and also connect you with a professional. "
                        "Would you like me to connect you?"
                    ),
                    "severe": (
                        "This seems severe. I strongly recommend speaking with a professional immediately. "
                        "Should I connect you now?"
                    )
                },
                "hi": {
                    "mild": (
                        "आपने जो साझा किया है, उसके आधार पर यह हल्का लगता है। "
                        "गहरी सांस लेने (4-7-8), छोटी सैर, हाइड्रेशन, स्क्रीन सीमित करने और अच्छी नींद की आदतों को आजमाएं। "
                        "यदि लक्षण बने रहते हैं या बिगड़ते हैं, तो पेशेवर सलाह पर विचार करें।"
                    ),
                    "moderate": (
                        "यह मध्यम लगता है। मैं मुकाबला करने के सुझाव साझा कर सकता हूं और आपको एक पेशेवर से जोड़ सकता हूं। "
                        "क्या आप चाहते हैं कि मैं आपको जोड़ूं?"
                    ),
                    "severe": (
                        "यह गंभीर लगता है। मैं दृढ़ता से सुझाव देता हूं कि तुरंत एक पेशेवर से बात करें। "
                        "क्या मैं अब आपको जोड़ूं?"
                    )
                },
                "mr": {
                    "mild": (
                        "तुम्ही सामायिक केलेल्या माहितीच्या आधारे, हे सौम्य वाटते. "
                        "खोल श्वासोच्छवास (4-7-8), छोट्या चाली, हायड्रेशन, स्क्रीन मर्यादित करणे आणि चांगल्या झोपेच्या सवयी वापरा. "
                        "जर लक्षणे टिकत राहतात किंवा वाढतात, तर व्यावसायिक सल्ला विचारात घ्या."
                    ),
                    "moderate": (
                        "हे मध्यम वाटते. मी सामना करण्याच्या टिप्स सामायिक करू शकतो आणि तुम्हाला व्यावसायिकाशी जोडू शकतो. "
                        "तुम्हाला मी जोडावे का?"
                    ),
                    "severe": (
                        "हे गंभीर वाटते. मी दृढपणे सुचवतो की त्वरित व्यावसायिकाशी बोला. "
                        "मी आता तुम्हाला जोडू का?"
                    )
                }
            }
            
            if severity_val <= 4:
                advice = advice_texts.get(user_lang, advice_texts["en"])["mild"]
                chat.metadata["awaiting_connect_confirmation"] = False
            elif severity_val <= 7:
                advice = advice_texts.get(user_lang, advice_texts["en"])["moderate"]
                chat.metadata["awaiting_connect_confirmation"] = True
            else:
                advice = advice_texts.get(user_lang, advice_texts["en"])["severe"]
                chat.metadata["awaiting_connect_confirmation"] = True

            chat.metadata["triage_complete"] = True
            chat.metadata["severity_level"] = severity_val

            # Create personalized context for LLM based on collected data
            user_context = f"""
            Patient Details:
            - Age: {chat.metadata.get('age', 'N/A')}
            - Problem: {chat.metadata.get('problem', 'N/A')} ({chat.metadata.get('type', 'N/A')})
            - Duration: {chat.metadata.get('duration', 'N/A')}
            - Triggers: {chat.metadata.get('triggers', 'N/A')}
            - Impact: {chat.metadata.get('impact', 'N/A')}
            - Previous attempts: {chat.metadata.get('coping', 'N/A')}
            - Severity: {severity_val}/10
            """
            
            # Optionally enrich with knowledge base and LLM
            pdf_answer = ""
            try:
                pdf_answer = get_chatbot_response(user_context) or ""
            except Exception as e:
                print(f"⚠️ PDF QA error: {e}")
            
            llm_answer = ""
            try:
                personalized_prompt = f"Based on this patient's specific situation: {user_context}\n\nProvide personalized mental health advice and coping strategies. Be specific to their age, problem type, duration, and triggers."
                llm_answer = ask_large_model(personalized_prompt) or ""
            except Exception as e:
                print(f"⚠️ LLM error: {e}")

            combined = advice
            extra_parts = []
            if pdf_answer.strip():
                extra_parts.append(f"📘 From our knowledge base: {pdf_answer}")
            if llm_answer.strip() and severity_val <= 7:
                # Avoid generic chit-chat for severe cases
                extra_parts.append(llm_answer)
            if extra_parts:
                combined = summary + "\n\n" + advice + "\n\n" + "\n\n".join(extra_parts)
            else:
                combined = summary + "\n\n" + advice

            chat.messages.append(Message(sender="bot", text=combined))
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200
    else:
        # ✅ all questions already answered → analyze severity
        try:
            severity = int(chat.metadata.get("severity", 0))
        except ValueError:
            severity = 0

        user_lang = chat.metadata.get("user_language", "en")
        
        # Define advice texts for different severity levels
        advice_texts = {
            "en": {
                "mild": "Based on what you shared, this seems mild. Try deep breathing (4-7-8), short walks, hydration, limit screens, and good sleep hygiene. If symptoms persist or worsen, consider professional advice.",
                "moderate": "This looks moderate. I can share coping tips now and also connect you with a professional. Would you like me to connect you?",
                "severe": "This seems severe. I strongly recommend speaking with a professional immediately. Should I connect you now?"
            },
            "hi": {
                "mild": "आपने जो साझा किया है, उसके आधार पर यह हल्का लगता है। गहरी सांस लेने (4-7-8), छोटी सैर, हाइड्रेशन, स्क्रीन सीमित करने और अच्छी नींद की आदतों को आजमाएं। यदि लक्षण बने रहते हैं या बिगड़ते हैं, तो पेशेवर सलाह पर विचार करें।",
                "moderate": "यह मध्यम लगता है। मैं अभी सामना करने की युक्तियाँ साझा कर सकता हूँ और आपको एक पेशेवर से भी जोड़ सकता हूँ। क्या आप चाहते हैं कि मैं आपको जोड़ूं?",
                "severe": "यह गंभीर लगता है। मैं दृढ़ता से सुझाव देता हूं कि तुरंत एक पेशेवर से बात करें। क्या मैं अब आपको जोड़ूं?"
            },
            "mr": {
                "mild": "तुम्ही सामायिक केलेल्या माहितीच्या आधारे हे हलके वाटते. खोल श्वास घेणे (4-7-8), लहान चाल, हायड्रेशन, स्क्रीन मर्यादित करणे आणि चांगल्या झोपेच्या सवयी वापरा. जर लक्षणे टिकत राहतात किंवा वाढतात, तर व्यावसायिक सल्ला विचारात घ्या.",
                "moderate": "हे मध्यम वाटते. मी आता सामना करण्याच्या युक्त्या सामायिक करू शकतो आणि तुम्हाला व्यावसायिकाशी देखील जोडू शकतो. तुम्हाला मी जोडायचे आहे का?",
                "severe": "हे गंभीर वाटते. मी दृढपणे सुचवतो की त्वरित व्यावसायिकाशी बोला. मी आता तुम्हाला जोडू का?"
            }
        }
        
        # Get appropriate response based on severity and language
        if severity <= 4:
            reply_text = advice_texts.get(user_lang, advice_texts["en"])["mild"]
            chat.metadata["awaiting_connect_confirmation"] = False
        elif severity <= 7:
            reply_text = advice_texts.get(user_lang, advice_texts["en"])["moderate"]
            chat.metadata["awaiting_connect_confirmation"] = True
        else:
            reply_text = advice_texts.get(user_lang, advice_texts["en"])["severe"]
            chat.metadata["awaiting_connect_confirmation"] = True

        # mark triage complete and, for moderate/severe, await confirmation
        chat.metadata["triage_complete"] = True
        chat.metadata["severity_level"] = severity

        # Create personalized context for LLM based on collected data
        user_context = f"""
        Patient Details:
        - Age: {chat.metadata.get('age', 'N/A')}
        - Problem: {chat.metadata.get('problem', 'N/A')} ({chat.metadata.get('type', 'N/A')})
        - Duration: {chat.metadata.get('duration', 'N/A')}
        - Triggers: {chat.metadata.get('triggers', 'N/A')}
        - Impact: {chat.metadata.get('impact', 'N/A')}
        - Previous attempts: {chat.metadata.get('coping', 'N/A')}
        - Severity: {severity}/10
        """
        
        # add intelligent knowledge sources
        pdf_answer = ""
        llm_answer = ""
        
        try:
            # Retrieve from PDF knowledge base with intelligent context
            intelligent_pdf_prompt = f"""
            Based on this person's mental health situation: {user_context}
            
            Provide specific, evidence-based information from your knowledge base that directly relates to:
            - Their specific condition: {chat.metadata.get('problem', 'N/A')} ({chat.metadata.get('type', 'N/A')})
            - Their age group: {chat.metadata.get('age', 'N/A')} years old
            - Their triggers: {chat.metadata.get('triggers', 'N/A')}
            - Their severity level: {severity}/10
            
            Focus on practical, actionable information that addresses their specific needs.
            """
            pdf_answer = get_chatbot_response(intelligent_pdf_prompt) or ""
        except Exception as e:
            print(f"⚠️ PDF QA error: {e}")

        try:
            # LLM answer with intelligent analysis
            intelligent_llm_prompt = f"""
            You are an advanced mental health AI with access to current research and evidence-based practices.
            
            PERSON'S SITUATION: {user_context}
            
            Provide intelligent, personalized mental health advice that:
            1. Analyzes their specific situation deeply
            2. Considers their age, triggers, and severity level
            3. Provides evidence-based strategies
            4. Addresses their specific needs and concerns
            5. Offers practical, actionable solutions
            6. Talks directly to them, not about them
            
            Be empathetic, professional, and provide current, research-backed advice.
            """
            llm_answer = ask_large_model(intelligent_llm_prompt)
        except Exception as e:
            print(f"⚠️ LLM error: {e}")
            llm_answer = ""

        # Intelligently combine answers
        combined_parts = []
        if pdf_answer.strip():
            combined_parts.append(f"📘 Evidence-based information: {pdf_answer}")
        if llm_answer.strip() and severity <= 7:
            # Avoid generic responses for severe cases
            combined_parts.append(f"💡 Personalized guidance: {llm_answer}")
        if combined_parts:
            reply_text += "\n\n" + "\n\n".join(combined_parts)

        # save bot msg
        chat.messages.append(Message(sender="bot", text=reply_text))
        chat.updated_at = datetime.utcnow()
        chat.save()

        return jsonify(chat.to_dict()), 200


# ---- Voice Routes ----

@chatbot_bp.route("/voice", methods=["POST"])
@jwt_required()
def voice_chat():
    if "file" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["file"]
    user_id = get_jwt_identity()
    user = User.objects(id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Save temp audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_path = tmp.name
        audio_file.save(audio_path)

    # ---- Transcribe speech → text ----
    try:
        transcript = openai.Audio.transcriptions.create(
            model="whisper-1",
            file=open(audio_path, "rb")
        )
        user_text = transcript["text"].strip()
    except Exception as e:
        return jsonify({"error": f"Transcription failed: {str(e)}"}), 500

    translated_text, original_lang = detect_and_translate_to_english(user_text)

    pdf_answer, llm_answer = "", ""
    try:
        pdf_answer = get_chatbot_response(translated_text)
    except Exception as e:
        print(f"⚠️ PDF QA error: {e}")
    try:
        llm_answer = ask_large_model(translated_text)
    except Exception as e:
        print(f"⚠️ LLM error: {e}")

    if pdf_answer and llm_answer:
        reply_en = f"{llm_answer}\n\n📘 Based on our knowledge base: {pdf_answer}"
    elif pdf_answer:
        reply_en = f"📘 From our knowledge base: {pdf_answer}"
    else:
        reply_en = llm_answer or "(Sorry, I couldn’t generate a response.)"

    final_reply = translate_back(reply_en, original_lang)

    # Save chat
    chat = Chat(user=user, title="Voice Chat", messages=[])
    chat.messages.append(Message(sender="user", text=user_text))
    chat.messages.append(Message(sender="bot", text=final_reply))
    chat.updated_at = datetime.utcnow()
    chat.save()

    # ---- Convert reply to speech ----
    tts = gTTS(final_reply, lang=original_lang)
    audio_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(audio_out.name)

    return send_file(audio_out.name, mimetype="audio/mpeg")
