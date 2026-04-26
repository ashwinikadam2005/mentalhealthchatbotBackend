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
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.chat import Chat, Message
from models.user import User
from utils.encryption import encryption_service
from utils.youtube_service import youtube_service
import re

# Helper function to add encrypted message
def add_encrypted_message(chat, text, sender):
    encrypted_text = encryption_service.encrypt(text)
    chat.messages.append(Message(sender=sender, text=encrypted_text, encrypted=True))
    return chat

# Helper function to check if query is about videos or YouTube
def is_explicit_youtube_links_request(text):
    """
    Detect when the user EXPLICITLY wants YouTube links/URLs listed out.
    Examples: "suggest youtube videos", "give me youtube links", "show me youtube videos for headache"
    This takes priority over is_image_request so it never gets mis-routed.
    """
    text_lower = text.lower()

    # Strong explicit signals: user says 'youtube' or 'video links' or 'video link'
    explicit_youtube = any(k in text_lower for k in [
        'youtube', 'youtubelinks', 'video link', 'video links', 'videos link',
        'यूट्यूब', 'यूट्यूब लिंक', 'व्हिडिओ लिंक', 'यू ट्यूब'
    ])
    if not explicit_youtube:
        return False

    # Must also have an action/request word (to avoid catching mid-sentence mentions)
    request_signals = [
        'suggest', 'give', 'show', 'find', 'send', 'provide', 'recommend', 'share',
        'list', 'some', 'any', 'search', 'look',
        'सुझाव', 'दे', 'दिखा', 'भेज', 'खोज', 'द्या', 'दाखवा', 'पाठवा'
    ]
    if any(k in text_lower for k in request_signals):
        return True

    return False


def is_video_request(text):
    """Check if the user is asking for videos (general, non-explicit-link form)."""
    text_lower = text.lower()
    # If it's an explicit YouTube links request, handled separately
    if is_explicit_youtube_links_request(text):
        return False
    # Exclude pure animation/image/steps requests
    if any(k in text_lower for k in ["animated", "animation", "animate", "image", "gif"]):
        return False

    video_keywords = {
        'en': ['video', 'youtube', 'watch', 'videos', 'link', 'links'],
        'hi': ['वीडियो', 'यूट्यूब', 'देखें', 'लिंक', 'वीडियोज'],
        'mr': ['व्हिडिओ', 'यूट्यूब', 'पहा', 'लिंक', 'व्हिडिओज']
    }
    for lang, keywords in video_keywords.items():
        if any(k in text_lower for k in keywords):
            return True
    return False


def is_image_request(text):
    """Check if the user is asking for animations, steps, guides, or images.
    NEVER fires when the user explicitly asked for YouTube links.
    """
    text_lower = text.lower()

    # If user explicitly wants YouTube links, do NOT treat it as an image/animation request
    if is_explicit_youtube_links_request(text):
        return False

    # Core multimedia keywords
    image_keywords = {
        'en': ['image', 'picture', 'photo', 'animation', 'animate', 'animated', 'gif', 'drawing', 'visual', 'step', 'steps', 'guide', 'how to', 'show me'],
        'hi': ['चित्र', 'फोटो', 'एनिमेशन', 'एनिमेटेड', 'चरण', 'गाइड', 'राहत'],
        'mr': ['चित्र', 'फोटो', 'अॅनिमेशन', 'अॅनिमेटेड', 'पायऱ्या', 'मार्गदर्शन', 'आराम']
    }

    # Action keywords that imply wanting a visual/guide
    action_keywords = {
        'en': ['give', 'show', 'create', 'generate', 'want', 'need', 'send', 'provide', 'how to', 'steps', 'step', 'guide', 'demonstrate'],
        'hi': ['दे', 'दिखा', 'बना', 'चाहिए', 'भेज', 'कैसे'],
        'mr': ['द्या', 'दाखवा', 'बनवा', 'हवे', 'पाठवा', 'कसे']
    }

    for lang in image_keywords:
        has_img = any(k in text_lower for k in image_keywords[lang])
        has_act = any(k in text_lower for k in action_keywords[lang])
        if has_img and has_act:
            return True

    # Direct triggers for common relief/how-to requests
    direct_triggers = ["show me", "guide me", "show me how", "how to", "steps", "step by step", "calm me"]
    if any(p in text_lower for p in direct_triggers):
        return True

    return False


def format_youtube_links_response(videos, language="en", topic="mental health"):
    """
    Format a clean list of YouTube video links for explicit link requests.
    Returns only titles + URLs — no embedded iframes.
    """
    if isinstance(videos, dict) and "error" in videos:
        no_video_msgs = {
            "en": "I'm sorry, I couldn't find any videos at the moment. Please try again later.",
            "hi": "मुझे खेद है, मैं अभी कोई वीडियो नहीं ढूंढ सका। कृपया बाद में पुनः प्रयास करें।",
            "mr": "मला माफ करा, मला सध्या कोणतेही व्हिडिओ सापडले नाहीत. कृपया नंतर पुन्हा प्रयत्न करा."
        }
        return no_video_msgs.get(language, no_video_msgs["en"])

    # Handle both list-of-dicts from youtube_service and {results:[...]} from search_youtube_videos
    if isinstance(videos, dict) and "results" in videos:
        video_list = videos["results"]
    elif isinstance(videos, list):
        video_list = videos
    else:
        video_list = []

    if not video_list:
        no_video_msgs = {
            "en": "I couldn't find relevant videos right now. Please try again later.",
            "hi": "मुझे अभी कोई वीडियो नहीं मिला। कृपया बाद में पुनः प्रयास करें।",
            "mr": "मला आत्ता कोणतेही व्हिडिओ सापडले नाहीत. कृपया नंतर पुन्हा प्रयत्न करा."
        }
        return no_video_msgs.get(language, no_video_msgs["en"])

    intro_msgs = {
        "en": f"Here are some helpful YouTube videos for **{topic}**:\n\n",
        "hi": f"यहाँ **{topic}** के लिए कुछ उपयोगी YouTube वीडियो हैं:\n\n",
        "mr": f"येथे **{topic}** साठी काही उपयुक्त YouTube व्हिडिओ आहेत:\n\n"
    }
    outro_msgs = {
        "en": "\n\nI hope these videos help you feel better. Remember to consult a healthcare professional if your symptoms persist. 💙",
        "hi": "\n\nमुझे आशा है कि ये वीडियो आपको बेहतर महसूस करने में मदद करेंगे। यदि लक्षण बने रहें, तो किसी स्वास्थ्य पेशेवर से संपर्क करें। 💙",
        "mr": "\n\nमला आशा आहे की हे व्हिडिओ तुम्हाला बरे वाटण्यास मदत करतील. लक्षणे कायम राहिल्यास आरोग्य व्यावसायिकांशी संपर्क साधा. 💙"
    }

    response = intro_msgs.get(language, intro_msgs["en"])
    for i, video in enumerate(video_list, 1):
        title = video.get('title', 'Video')
        url = video.get('url', '')
        response += f"{i}. 🎬 **{title}**\n   🔗 {url}\n\n"
    response += outro_msgs.get(language, outro_msgs["en"])
    return response

# Helper function to extract topic from query
def extract_video_topic(text):
    # Detect language first
    detected_lang = "en"
    try:
        # Try to use the YouTube service's language detection
        from utils import youtube_service
        yt_service = youtube_service.YouTubeService()
        detected_lang = yt_service.detect_language(text)
    except:
        # Fallback to simple detection
        if any(word in text.lower() for word in ["मराठी", "मला", "आहे", "नाही"]):
            detected_lang = "mr"
        elif any(word in text.lower() for word in ["हिंदी", "मुझे", "है", "नहीं"]):
            detected_lang = "hi"
    
    # Default topic if we can't determine one
    default_topics = {
        "en": "mental health",
        "hi": "मानसिक स्वास्थ्य",
        "mr": "मानसिक आरोग्य"
    }
    default_topic = default_topics.get(detected_lang, "mental health")
    
    # Multilingual mental health topics
    topics = {
        'stress': {
            'en': ['stress', 'tension', 'pressure', 'overwhelm', 'burnout'],
            'hi': ['तनाव', 'टेंशन', 'दबाव', 'परेशानी'],
            'mr': ['तणाव', 'ताण', 'दबाव', 'तणावातून', 'मुक्त']
        },
        'anxiety': {
            'en': ['anxiety', 'anxious', 'worry', 'panic', 'fear', 'phobia'],
            'hi': ['चिंता', 'घबराहट', 'डर', 'भय', 'फोबिया'],
            'mr': ['चिंता', 'काळजी', 'घाबरणे', 'भीती', 'फोबिया']
        },
        'depression': {
            'en': ['depression', 'depressed', 'sad', 'sadness', 'low mood', 'hopeless'],
            'hi': ['अवसाद', 'उदासी', 'दुःख', 'निराशा'],
            'mr': ['नैराश्य', 'उदासीनता', 'दुःख', 'निराशा']
        },
        'meditation': {
            'en': ['meditation', 'mindfulness', 'awareness', 'focus', 'concentrate'],
            'hi': ['ध्यान', 'माइंडफुलनेस', 'जागरूकता', 'एकाग्रता'],
            'mr': ['ध्यान', 'जागरूकता', 'एकाग्रता', 'लक्ष']
        },
        'relaxation': {
            'en': ['relax', 'calm', 'peace', 'tranquil', 'soothe', 'comfort'],
            'hi': ['आराम', 'शांति', 'सुकून', 'चैन'],
            'mr': ['आराम', 'शांतता', 'शांत', 'विश्रांती', 'उपाय']
        },
        'sleep': {
            'en': ['sleep', 'insomnia', 'rest', 'tired', 'fatigue', 'sleepless'],
            'hi': ['नींद', 'अनिद्रा', 'आराम', 'थकान'],
            'mr': ['झोप', 'अनिद्रा', 'विश्रांती', 'थकवा']
        },
        'yoga': {
            'en': ['yoga', 'stretch', 'flexibility', 'poses', 'asanas'],
            'hi': ['योग', 'योगासन', 'आसन', 'लचीलापन'],
            'mr': ['योग', 'योगासन', 'आसन', 'लवचिकता']
        },
        'breathing': {
            'en': ['breathing', 'breath', 'breathe', 'respiration', 'inhale', 'exhale'],
            'hi': ['सांस', 'श्वास', 'प्राणायाम'],
            'mr': ['श्वास', 'श्वासोच्छवास', 'प्राणायाम']
        },
        'addiction': {
            'en': ['addiction', 'substance', 'alcohol', 'drug', 'dependency'],
            'hi': ['लत', 'नशा', 'शराब', 'ड्रग्स', 'निर्भरता'],
            'mr': ['व्यसन', 'मद्य', 'अल्कोहोल', 'औषध', 'अवलंबित्व']
        },
        'relationships': {
            'en': ['relationship', 'marriage', 'partner', 'family', 'friend'],
            'hi': ['रिश्ता', 'शादी', 'पार्टनर', 'परिवार', 'दोस्त'],
            'mr': ['नाते', 'विवाह', 'जोडीदार', 'कुटुंब', 'मित्र']
        },
        'work': {
            'en': ['work', 'job', 'career', 'workplace', 'professional'],
            'hi': ['काम', 'नौकरी', 'करियर', 'कार्यस्थल', 'पेशेवर'],
            'mr': ['काम', 'नोकरी', 'करिअर', 'कार्यस्थळ', 'व्यावसायिक']
        },
        'study': {
            'en': ['study', 'school', 'college', 'university', 'academic', 'exam'],
            'hi': ['पढ़ाई', 'स्कूल', 'कॉलेज', 'विश्वविद्यालय', 'शैक्षिक', 'परीक्षा'],
            'mr': ['अभ्यास', 'शाळा', 'कॉलेज', 'विद्यापीठ', 'शैक्षणिक', 'परीक्षा']
        },
        'exercise': {
            'en': ['exercise', 'workout', 'fitness', 'physical activity', 'training'],
            'hi': ['व्यायाम', 'फिटनेस', 'शारीरिक गतिविधि', 'ट्रेनिंग'],
            'mr': ['व्यायाम', 'फिटनेस', 'शारीरिक हालचाल', 'प्रशिक्षण']
        }
    }

    text_lower = text.lower()
    
    # Check for topic keywords in the text based on detected language
    for topic, lang_keywords in topics.items():
        # First check keywords in detected language
        if detected_lang in lang_keywords:
            for keyword in lang_keywords[detected_lang]:
                if keyword in text_lower:
                    return f"{topic} mental health"
        
        # Fallback to English keywords
        if 'en' in lang_keywords:
            for keyword in lang_keywords['en']:
                if keyword in text_lower:
                    return f"{topic} mental health"
    
    return default_topic

# Helper function to format YouTube videos as a response
def format_youtube_response(videos, language="en"):
    if isinstance(videos, dict) and "error" in videos:
        error_messages = {
            "en": "I'm sorry, I couldn't find any videos at the moment. Please try again later.",
            "hi": "मुझे खेद है, मैं अभी कोई वीडियो नहीं ढूंढ सका। कृपया बाद में पुनः प्रयास करें।",
            "mr": "मला माफ करा, मला सध्या कोणतेही व्हिडिओ सापडले नाहीत. कृपया नंतर पुन्हा प्रयत्न करा."
        }
        return error_messages.get(language, error_messages["en"])
    
    intro_messages = {
        "en": "Here are some YouTube videos that might help you:\n\n",
        "hi": "यहां कुछ यूट्यूब वीडियो हैं जो आपकी मदद कर सकते हैं:\n\n",
        "mr": "येथे काही यूट्यूब व्हिडिओ आहेत जे आपल्याला मदत करू शकतात:\n\n"
    }
    
    outro_messages = {
        "en": "I hope these videos help you feel better. Remember that taking care of your mental health is important.",
        "hi": "मुझे आशा है कि ये वीडियो आपको बेहतर महसूस करने में मदद करेंगे। याद रखें कि अपने मानसिक स्वास्थ्य का ध्यान रखना महत्वपूर्ण है।",
        "mr": "मला आशा आहे की हे व्हिडिओ तुम्हाला बरे वाटण्यास मदत करतील. लक्षात ठेवा की तुमच्या मानसिक आरोग्याची काळजी घेणे महत्त्वाचे आहे."
    }
    
    response = intro_messages.get(language, intro_messages["en"])
    
    for i, video in enumerate(videos, 1):
        response += f"{i}. {video['title']}\n"
        response += f"   {video['url']}\n\n"
    
    response += outro_messages.get(language, outro_messages["en"])
    return response
# from datetime import datetime
# import os



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
import tempfile
from gtts import gTTS  # for text-to-speech
from chatbot_engine import get_chatbot_response  # ✅ PDF QA
import requests
from urllib.parse import urlencode, quote_plus
# Removed googletrans because it conflicts with groq's httpx version.
# Using our local FastAPI translator service (port 9000) instead.
class ServiceTranslator:
    def translate(self, text, src='auto', dest='en'):
        try:
            from urllib.parse import quote_plus
            r = requests.get(f"http://127.0.0.1:9000/translate?text={quote_plus(text)}&target={dest}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                from collections import namedtuple
                return namedtuple("Res", ["text", "src"])(data['translated_text'], data.get('detected_lang', src))
        except Exception as e:
            print(f"⚠️ Proxy translation error: {e}")
        from collections import namedtuple
        return namedtuple("Res", ["text", "src"])(text, src)

    def detect(self, text):
        try:
            from urllib.parse import quote_plus
            r = requests.get(f"http://127.0.0.1:9000/translate?text={quote_plus(text)}&target=en", timeout=5)
            if r.status_code == 200:
                data = r.json()
                from collections import namedtuple
                return namedtuple("Res", ["lang"])(data.get('detected_lang', 'en'))
        except Exception as e:
            print(f"⚠️ Proxy detection error: {e}")
        from collections import namedtuple
        return namedtuple("Res", ["lang"])("en")

translator = ServiceTranslator()
import json
from bs4 import BeautifulSoup

load_dotenv()

chatbot_bp = Blueprint("chatbot_bp", __name__)

# Google Search API configuration
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

def perform_google_search(query, num_results=3):
    """
    Perform a Google search for the given query and return the results.
    Falls back to a simple web scraping approach if API keys are not available.
    Includes robust error handling to prevent failures.
    """
    try:
        # Validate input
        if not query or not isinstance(query, str):
            print("Invalid search query provided")
            return []
            
        # Sanitize query
        sanitized_query = query.strip()
        if not sanitized_query:
            return []
            
        # First try using Google Custom Search API if keys are available
        if GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
            try:
                url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_SEARCH_API_KEY}&cx={GOOGLE_SEARCH_ENGINE_ID}&q={quote_plus(sanitized_query)}&num={num_results}"
                response = requests.get(url, timeout=5)  # Add timeout
                
                if response.status_code == 200:
                    results = response.json()
                    search_results = []
                    if "items" in results:
                        for item in results["items"]:
                            search_results.append({
                                "title": item.get("title", "No title available"),
                                "link": item.get("link", ""),
                                "snippet": item.get("snippet", "No description available")
                            })
                    return search_results
                else:
                    print(f"Google API error: Status code {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Google API request error: {str(e)}")
            except ValueError as e:
                print(f"Google API JSON parsing error: {str(e)}")
        
        # Fallback to a simple search approach with error handling
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            search_url = f"https://www.google.com/search?q={quote_plus(sanitized_query)}"
            response = requests.get(search_url, headers=headers, timeout=5)  # Add timeout
            
            if response.status_code == 200:
                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    search_results = []
                    
                    # Extract search results (this is simplified and may need adjustment)
                    for result in soup.select("div.g")[:num_results]:
                        try:
                            title_elem = result.select_one("h3")
                            link_elem = result.select_one("a")
                            snippet_elem = result.select_one("div.VwiC3b")
                            
                            title = title_elem.text if title_elem else "No title available"
                            link = link_elem.get("href") if link_elem else ""
                            snippet = snippet_elem.text if snippet_elem else "No description available"
                            
                            if link.startswith("/url?q="):
                                link = link.split("/url?q=")[1].split("&")[0]
                            
                            if title:  # Only require title to be present
                                search_results.append({
                                    "title": title,
                                    "link": link,
                                    "snippet": snippet
                                })
                        except Exception as e:
                            print(f"Error parsing search result: {str(e)}")
                            continue
                    
                    return search_results
                except Exception as e:
                    print(f"Error parsing search results: {str(e)}")
            else:
                print(f"Search request failed with status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Search request error: {str(e)}")
        
        # If all methods fail, return empty results
        return []
    except Exception as e:
        print(f"Unexpected error in Google search: {str(e)}")
        return []

# translator is already initialized above as a ServiceTranslator proxy

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
    - If Devanagari present → Check for Marathi-specific words/chars else Hindi
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
        # Marathi specific characters or common Marathi words
        marathi_specific = {'ळ', 'ऱ', 'ॅ', 'य़', 'ॲ', 'ॐ'}
        marathi_words = [
            "मी", "माझा", "माझी", "माझे", "आहे", "आहेत", "नाही", "होते", "होती",
            "आला", "आली", "आले",
            "मला", "तुला", "आपल्याला", "कसे", "काय", "कुठे", "केव्हा", "जेव्हा", "तेव्हा",
            "हवे", "हवी", "केले", "केली", "केल्या", "तुमचे", "करायचे", "पाहिजे",
            # common health words
            "डोके", "दुखत", "दुखी", "ताण", "तणाव", "चिंता"
        ]
        
        if any(ch in marathi_specific for ch in text):
            return "mr"
            
        text_words = text.split()
        if any(word in marathi_words for word in text_words):
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
    """Detect user language and translate input to English using googletrans with robust fallback."""
    try:
        detected = translator.detect(text).lang
    except Exception as e:
        print(f"⚠️ Language detection error: {e}")
        detected = detect_user_language(text)
    try:
        if detected == "en":
            return text, "en"
        translated = translator.translate(text, src=detected, dest="en").text
        return translated, detected
    except Exception as e:
        print(f"⚠️ Translation error: {e}")
        # Fallback: return original text and detected language
        return text, detected

def translate_back(text: str, dest_lang: str):
    """Translate English text back to target language using googletrans; fallback to original on failure."""
    if dest_lang == "en":
        return text
    try:
        return translator.translate(text, src="en", dest=dest_lang).text
    except Exception as e:
        print(f"⚠️ Translation back error: {e}")
        return text

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


# --- Animation intent helper ---
def detect_animation_intent(text: str, topic_hint: str = ""):
    tl = (text or "").lower()
    th = (topic_hint or "").lower()
    combined = tl + " " + th

    # Head / scalp massage
    if any(k in combined for k in ["head massage", "scalp massage", "head pain", "massage", "temple", "डोके मालिश", "सिर की मालिश", "माथा"]):
        return "head_massage"
    # Headache / pain relief
    if any(k in combined for k in ["headache", "migraine", "head pain", "सिरदर्द", "डोकेदुखी", "relief", "pain relief"]):
        return "pain_relief"
    # Breathing patterns
    if "4-7-8" in combined or any(k in combined for k in ["breath", "breathing", "inhale", "exhale", "सांस", "श्वसन", "श्वास", "प्राणायाम"]):
        return "breathing_478"
    if ("box breathing" in combined) or ("box" in combined and "breath" in combined) or ("बॉक्स" in combined and "श्वास" in combined):
        return "breathing_box"
    if any(k in combined for k in ["paced", "resonant", "5/5", "5-5", "equal breathing"]):
        return "breathing_paced_55"
    if any(k in combined for k in ["physiological sigh", "huberman", "stress downshift"]):
        return "breathing_sigh"
    # Grounding
    if "grounding" in combined or "5-4-3-2-1" in combined or "ग्राउंडिंग" in combined:
        return "grounding_54321"
    # Stretching / chest
    if any(k in combined for k in ["chest", "shoulder", "posture", "tight chest", "खांदे"]):
        return "stretching_chest"
    if any(k in combined for k in ["stretch", "neck", "neck stiffness", "neck pain", "मान"]):
        return "stretching_neck"
    # Yoga
    if any(k in combined for k in ["yoga", "surya namaskar", "sun salutation", "आसन", "योग"]):
        return "yoga_flow"
    # Meditation
    if any(k in combined for k in ["meditate", "meditation", "mindfulness", "dhyan", "ध्यान"]):
        return "meditation_breath"
    # Relaxation / stress
    if any(k in combined for k in ["relax", "stress", "calm", "anxiety", "tension", "तनाव", "ताण", "चिंता"]):
        return "relaxation_wave"
    # Sleep / insomnia
    if any(k in combined for k in ["sleep", "insomnia", "tired", "fatigue", "rest", "झोप", "नींद"]):
        return "sleep_calm"
    # Sadness / depression
    if any(k in combined for k in ["sad", "sadness", "depress", "low mood", "hopeless", "उदास", "नैराश्य"]):
        return "emotional_calm"
    return None


def pick_animation_for_topic(topic: str, user_text: str = "") -> str:
    """Always return a sensible animation_type based on detected topic, never None."""
    anim = detect_animation_intent(user_text, topic_hint=topic)
    if anim:
        return anim
    # Topic-based fallback map
    topic_map = {
        "headache": "head_massage",
        "migraine": "pain_relief",
        "stress": "relaxation_wave",
        "anxiety": "breathing_478",
        "depression": "emotional_calm",
        "sleep": "sleep_calm",
        "insomnia": "sleep_calm",
        "yoga": "yoga_flow",
        "meditation": "meditation_breath",
        "breathing": "breathing_478",
        "relaxation": "relaxation_wave",
        "sadness": "emotional_calm",
        "pain": "pain_relief",
        "massage": "head_massage",
    }
    tl = topic.lower()
    for key, val in topic_map.items():
        if key in tl:
            return val
    return "relaxation_wave"  # universal safe fallback

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

# --- Response formatting helper ---
def format_response_for_display(text):
    """
    Format the chatbot response for better readability and user experience.
    - Ensures proper line breaks for tips and lists
    - Makes URLs clickable
    - Formats doctor information clearly
    """
    if not text:
        return text
    
    # First, handle backtick-wrapped URLs (like `http://example.com`)
    backtick_url_pattern = r'`(https?://[^\s`]+)`'
    text = re.sub(backtick_url_pattern, r'<a href="\1" target="_blank" style="color:#0066cc; text-decoration:underline;">\1</a>', text)
    
    # Then handle regular URLs
    url_pattern = r'(?<![`"\'])(https?://[^\s]+)(?![`"\'])'
    text = re.sub(url_pattern, r'<a href="\1" target="_blank" style="color:#0066cc; text-decoration:underline;">\1</a>', text)
    
    # Format YouTube links specially with more visible styling
    youtube_pattern = r'<a href="(https?://(?:www\.)?youtube\.com/[^\s]+)"[^>]*>([^<]+)</a>'
    text = re.sub(youtube_pattern, r'<a href="\1" target="_blank" style="color:#ff0000; font-weight:bold; text-decoration:underline;">🎬 YouTube: \2</a>', text)
    
    # Ensure numbered list items are on separate lines with proper spacing
    numbered_list_pattern = r'([•\*-]|\d+\.)\s+(.*?)(?=\n[•\*-]|\d+\.|\n\n|$)'
    
    def list_item_replacement(match):
        marker = match.group(1)
        content = match.group(2)
        return f"\n{marker} {content}\n"
    
    text = re.sub(numbered_list_pattern, list_item_replacement, text, flags=re.DOTALL)
    
    # Ensure bullet points are properly formatted
    bullet_patterns = [
        (r'•\s+', r'\n• '),  # Bullet points
        (r'\*\s+', r'\n* '),  # Asterisk bullets
        (r'-\s+', r'\n- '),   # Dash bullets
    ]
    
    for pattern, replacement in bullet_patterns:
        text = re.sub(pattern, replacement, text)
    
    # Format doctor information blocks
    doctor_pattern = r'(Dr\.\s+[A-Za-z\s]+)(\n|:)'
    text = re.sub(doctor_pattern, r'\n\n\1\2', text)
    
    # Ensure "Tip" formatting
    tip_pattern = r'(Tip\s*\d*\s*:)'
    text = re.sub(tip_pattern, r'\n\1', text)
    
    # Ensure proper spacing between sections
    section_pattern = r'([.!?])\s*\n([A-Z])'
    text = re.sub(section_pattern, r'\1\n\n\2', text)
    
    # Clean up excessive newlines while preserving intentional spacing
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = re.sub(r'^\n+', '', text)  # Remove leading newlines
    
    return text

# --- LLM helper: uses Groq (fast) with OpenRouter as fallback ---
def ask_large_model(prompt: str) -> str:
    try:
        if not prompt or not isinstance(prompt, str):
            return "I couldn't understand your question. Please try again."

        system_content = (
            "You are a compassionate, multilingual mental health assistant. "
            "Give accurate, empathetic, evidence-based advice. "
            "Be concise and practical. Format lists with line breaks. "
            "Always suggest consulting a professional for serious concerns."
        )

        # ── 1. Try Groq first (fast) ──────────────────────────────────────
        from chatbot_engine import fast_llm_response
        groq_reply = fast_llm_response(system_content, prompt, max_tokens=512)
        if groq_reply:
            return format_response_for_display(groq_reply)

        # ── 2. Fall back to OpenRouter / OpenAI ──────────────────────────
        if openai.api_key and openai.api_base:
            try:
                resp = openai.ChatCompletion.create(
                    model="openai/gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt}
                    ],
                    timeout=12,
                )
                
                # Get the raw response
                response_text = resp["choices"][0]["message"]["content"]
                
                response_text = resp["choices"][0]["message"]["content"]
                return format_response_for_display(response_text)
            except Exception as e:
                print(f"⚠️ OpenRouter fallback error: {e}")
                return format_response_for_display("I'm sorry, I'm unable to respond right now. Please consult a healthcare professional.")
        else:
            return format_response_for_display("I'm sorry, I'm unable to process your request. Please consult a healthcare professional.")
    except Exception as e:
        print(f"⚠️ ask_large_model error: {str(e)}")
        return "I'm sorry, I encountered an error. Please try again."


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

@chatbot_bp.route("/chat/<chat_id>", methods=["DELETE"])
@jwt_required()
def delete_chat(chat_id):
    try:
        user_id = get_jwt_identity()
        user = User.objects(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        chat = Chat.objects(id=chat_id, user=user).first()
        if not chat:
            return jsonify({"error": "Chat not found or not authorized"}), 404
            
        chat.delete()
        return jsonify({"message": "Chat deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting chat: {e}")
        return jsonify({"error": "Failed to delete chat"}), 500
        
@chatbot_bp.route("/chats/all", methods=["DELETE"])
@jwt_required()
def delete_all_chats():
    try:
        user_id = get_jwt_identity()
        user = User.objects(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        deleted_count = Chat.objects(user=user).delete()
        return jsonify({"message": f"All chats deleted successfully", "count": deleted_count}), 200
    except Exception as e:
        print(f"Error deleting all chats: {e}")
        return jsonify({"error": "Failed to delete all chats"}), 500


@chatbot_bp.route("/new", methods=["POST"])
@jwt_required()
def new_chat():
    try:
        user_id = get_jwt_identity()
        user = User.objects(id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        chat = Chat(user=user, title="New Chat", messages=[])
        chat.save()
        return jsonify(chat.to_dict()), 201
    except Exception as e:
        print(f"Error creating new chat: {e}")
        return jsonify({"error": "Failed to create chat"}), 500

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

    # Use existing chat if chat_id is provided
    if chat_id:
        chat = Chat.objects(id=chat_id, user=user).first()
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
    else:
        # Only create a new chat if absolutely necessary
        chat = Chat(user=user, title="New Chat", messages=[], metadata={})
        chat.save()

    # save user msg - encrypt the message
    add_encrypted_message(chat, text, "user")

    # ── Detect language ONCE and reuse throughout this request ──────────
    detected_lang = chat.metadata.get("user_language", "en")  # start with cached
    prev_lang = detected_lang
    # If the user sent numeric-only (or nearly numeric) text, preserve previous language.
    has_any_letters = bool(re.search(r"[A-Za-z\u0900-\u097F]", text or ""))
    if not has_any_letters:
        detected_lang = prev_lang or "en"
    else:
        try:
            detected_lang = translator.detect(text).lang or detected_lang
        except Exception:
            detected_lang = detect_user_language(text) or detected_lang
    chat.metadata["user_language"] = detected_lang

    # ── Translate text to English once (reused by every handler below) ─
    text_en = text
    if detected_lang != "en":
        try:
            text_en = translator.translate(text, src=detected_lang, dest="en").text or text
        except Exception as te:
            print(f"⚠️ translate-to-en error: {te}")

    # --- EXPLICIT YOUTUBE LINKS REQUEST HANDLER (HIGHEST PRIORITY) ---
    # Fires when user says "suggest youtube links", "give me youtube videos", etc.
    # Returns ONLY a formatted list of video titles + URLs — no iframes/animations.
    if is_explicit_youtube_links_request(text_en) or is_explicit_youtube_links_request(text):
        chat.metadata["triage_complete"] = True
        topic = extract_video_topic(text_en or text)
        search_query = f"{topic} relief tips"
        # Fetch up to 5 videos
        yt_results = search_youtube_videos(search_query, max_results=5)
        video_list = yt_results.get("results", []) if isinstance(yt_results, dict) else []
        if not video_list:
            # Fallback to youtube_service
            try:
                video_list = youtube_service.search_videos(search_query, language=detected_lang, max_results=5)
            except Exception:
                video_list = []
        links_reply = format_youtube_links_response(video_list, language="en", topic=topic)
        if detected_lang != "en":
            try:
                links_reply = translator.translate(links_reply, dest=detected_lang).text
            except Exception:
                pass
        if chat.title == "New Chat":
            chat.title = f"{topic.capitalize()} Videos"
        add_encrypted_message(chat, links_reply, "bot")
        chat.updated_at = datetime.utcnow()
        chat.save()
        return jsonify(chat.to_dict()), 200

    # --- MULTIMEDIA / ANIMATION REQUEST HANDLER (STEPS + VISUAL + ONE VIDEO LINK) ---
    # Fires for "give me steps", "show me how to", "animation", "guide", etc.
    if is_image_request(text_en) or is_image_request(text):
        chat.metadata["triage_complete"] = True

        # --- BUILD CONVERSATION MEMORY (last 5 decrypted messages) ---
        recent_memory = ""
        try:
            recent_msgs = chat.messages[-10:]  # last 10 entries
            memory_lines = []
            for m in recent_msgs:
                raw_text = m.text or ""
                try:
                    raw_text = encryption_service.decrypt(raw_text)
                except Exception:
                    pass
                # Strip HTML tags for a clean snippet
                plain = re.sub(r'<[^>]+>', '', raw_text).strip()
                if plain and len(plain) > 5:
                    memory_lines.append(f"{m.sender.upper()}: {plain[:200]}")
            if memory_lines:
                recent_memory = "\n".join(memory_lines[-6:])  # last 6 lines
        except Exception:
            pass

        # Build topic context from triage metadata
        triage_context = ", ".join(filter(None, [
            f"problem: {chat.metadata.get('problem', '')}",
            f"type: {chat.metadata.get('type', '')}",
            f"duration: {chat.metadata.get('duration', '')}",
            f"severity: {chat.metadata.get('severity', '')}",
        ]))

        # Force the model to reply in the user's language to avoid English leakage
        lang_name = {"en": "English", "hi": "Hindi", "mr": "Marathi"}.get(detected_lang, "English")
        system_prompt = (
            "You are an intelligent, compassionate mental health assistant with multimedia generation capabilities.\n"
            "Analyze the user message carefully, considering their specific problem and conversation history.\n"
            "Generate a PERSONALIZED response tailored to their exact situation.\n\n"
            f"IMPORTANT: Reply in {lang_name}. Do not switch languages.\n\n"
            "Return ONLY valid JSON. Do not include any other text before or after the JSON.\n"
            "If the user asks for steps, animations, or 'show me how', respond with this JSON:\n"
            "{\n"
            "  \"type\": \"animation\" | \"video\" | \"image\",\n"
            "  \"title\": \"<short descriptive title>\",\n"
            "  \"text_response\": \"<warm, empathetic intro text>\",\n"
            "  \"steps\": [\n"
            "    {\"step\": 1, \"instruction\": \"<clear action step>\", \"animation_hint\": \"<visual motion hint>\"}\n"
            "  ],\n"
            "  \"image_prompt\": \"<DALL-E style prompt — be specific to the user's topic, e.g. 'gentle head massage illustration, soft blue tones, step 1: fingertips on temples'>\",\n"
            "  \"video_query\": \"<YouTube search query specific to user's topic>\"\n"
            "}"
        )

        memory_section = f"\n\nConversation history:\n{recent_memory}" if recent_memory else ""
        context_section = f"\n\nUser triage info: {triage_context}" if triage_context else ""
        user_input_to_llm = (
            f"User Request: '{text_en}'"
            f"{context_section}"
            f"{memory_section}"
        )
        reply_raw = ask_large_model(f"{system_prompt}\n\n{user_input_to_llm}")
        
        import json

        def _extract_first_json_object(s: str):
            """Extract first balanced {...} JSON object substring, else ''."""
            if not s:
                return ""
            start = s.find("{")
            if start == -1:
                return ""
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(s)):
                ch = s[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == "\"":
                        in_str = False
                    continue
                else:
                    if ch == "\"":
                        in_str = True
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            return s[start : i + 1]
            return ""

        try:
            # Try to extract JSON from the response (robust balanced-brace extraction)
            json_blob = _extract_first_json_object(reply_raw)
            if json_blob:
                data = json.loads(json_blob)
                reply_en = data.get("text_response", "I'm here to help you through this.")
                steps = data.get("steps", [])
                if steps:
                    reply_en += "\n\n**Step-by-Step Guide:**\n"
                    for s in steps:
                        reply_en += f"**Step {s['step']}:** {s['instruction']}\n"
            else:
                # Fallback: strip anything that looks like a JSON section
                cut_markers = ["json", "JSON", "{"]
                cut_idx = min([reply_raw.find(m) for m in cut_markers if reply_raw.find(m) != -1] or [-1])
                reply_en = reply_raw[:cut_idx].strip() if cut_idx != -1 else reply_raw
        except Exception:
            # If parsing failed, return only non-JSON part
            cut_idx = reply_raw.find("{")
            reply_en = reply_raw[:cut_idx].strip() if cut_idx != -1 else reply_raw

        # Append one real YouTube link for the user to open externally
        _related_topic = extract_video_topic(text_en or text)
        try:
            _yt_one = search_youtube_videos(f"{_related_topic} tutorial", max_results=1)
            _one_results = _yt_one.get("results", []) if isinstance(_yt_one, dict) else []
            if not _one_results:
                _yt_fb = youtube_service.search_videos(f"{_related_topic} tutorial", language="en", max_results=1)
                _one_results = _yt_fb if isinstance(_yt_fb, list) else []
            if _one_results:
                _v = _one_results[0]
                _vt = _v.get('title', 'Watch on YouTube')
                _vu = _v.get('url', '')
                reply_en += f"\n\n🎬 **Recommended video:** [{_vt}]({_vu})\n🔗 {_vu}"
        except Exception:
            pass

        if detected_lang != "en":
            try:
                final_reply = translator.translate(reply_en, dest=detected_lang).text
            except Exception: final_reply = reply_en
        else: final_reply = reply_en
        
        # Frontend renders message as HTML; preserve intended line breaks
        final_reply = (final_reply or "").replace("\n", "<br />")

        # Pick a contextually appropriate animation (UI renders it) — never None
        _topic_hint = chat.metadata.get("problem", "")
        _anim_type = pick_animation_for_topic(_topic_hint, user_text=text)

        chat.messages.append(Message(sender="bot", text=final_reply, animation_type=_anim_type))
        chat.updated_at = datetime.utcnow()
        chat.save()
        return jsonify(chat.to_dict()), 200

    # --- YOUTUBE VIDEO REQUEST CHECK (FALLBACK) ---
    if is_video_request(text):
        topic = extract_video_topic(text)
        search_query = f"{topic} videos"
        videos = youtube_service.search_videos(search_query, language=detected_lang)
        response = format_youtube_response(videos, language=detected_lang)
        if chat.title == "New Chat":
            chat.title = f"{topic.capitalize()} Videos"
        add_encrypted_message(chat, response, "bot")
        chat.save()
        return jsonify(chat.to_dict()), 200

    # --- DOCTOR INFORMATION HANDLER (PRIORITY CHECK) ---
    normalized_for_doctor = text.strip().lower()
    doctor_keywords = {
        "en": ["doctor", "doctors", "therapist", "therapists", "psychiatrist", "psychologist", "counselor", "professional", "specialist", "mental health expert"],
        "hi": ["डॉक्टर", "चिकित्सक", "मनोचिकित्सक", "मनोवैज्ञानिक", "परामर्शदाता", "विशेषज्ञ", "पेशेवर"],
        "mr": ["डॉक्टर", "चिकित्सक", "मानसोपचारतज्ञ", "मानसशास्त्रज्ञ", "समुपदेशक", "तज्ञ", "व्यावसायिक"]
    }
    doctor_action_keywords = {
        "en": ["details", "suggest", "recommend", "contact", "information", "info", "list", "find", "need", "want"],
        "hi": ["विवरण", "सुझाव", "अनुशंसा", "संपर्क", "जानकारी", "सूची", "खोजें", "चाहिए"],
        "mr": ["तपशील", "सूचवा", "शिफारस", "संपर्क", "माहिती", "यादी", "शोधा", "हवे"]
    }
    
    doctor_keys = doctor_keywords.get(detected_lang, doctor_keywords["en"]) + doctor_keywords["en"]
    action_keys = doctor_action_keywords.get(detected_lang, doctor_action_keywords["en"]) + doctor_action_keywords["en"]
    
    # Check if this is a request for doctor information - must contain both a doctor keyword AND an action keyword
    # or explicitly asking for doctor/therapist with phrases like "give me doctor" or "show me therapist"
    if (any(k in normalized_for_doctor for k in doctor_keys) and any(k in normalized_for_doctor for k in action_keys)) or any(f"give me {k}" in normalized_for_doctor or f"show me {k}" in normalized_for_doctor or f"tell me {k}" in normalized_for_doctor for k in doctor_keys):
        # Fetch doctors from database
        doctors = [d.to_dict() for d in Doctor.objects().limit(5)]
        
        if doctors:
            doctor_lines = [
                f"• {d['name']} — {d.get('qualification','')} — {d.get('phone','')}" for d in doctors
            ]
            reply_en = "Here are some mental health professionals who can help you:\n" + "\n".join(doctor_lines) + "\n\nThese professionals can provide personalized support and guidance tailored to your specific needs. Reaching out to a mental health professional is an important step in taking care of your wellbeing."
        else:
            reply_en = "I don't have any doctor information in my database at the moment. You can find therapists through online directories like Psychology Today, ask your primary care physician for a referral, or check with your health insurance provider for covered therapists. Please consult your local healthcare provider for professional mental health support."
        
        # Translate response to user's language
        try:
            if detected_lang != "en":
                final_reply = translator.translate(reply_en, src='en', dest=detected_lang).text
            else:
                final_reply = reply_en
        except Exception as e:
            print(f"⚠️ Doctor info translation error: {e}")
            final_reply = reply_en
            
        chat.messages.append(Message(sender="bot", text=final_reply))
        chat.updated_at = datetime.utcnow()
        chat.save()
        return jsonify(chat.to_dict()), 200
    
    # --- DIRECT QUESTION HANDLER ---
    # Only run if triage is not currently expecting an answer.
    # This prevents "age/severity/etc" responses from getting mis-routed.
    try:
        _pending_q = None
        try:
            _pending_q = next_triage_question(chat)
        except Exception:
            _pending_q = None
        pending_key = (_pending_q or {}).get("key")
        if _pending_q and not chat.metadata.get("triage_complete"):
            # Never bypass numeric collection steps
            if pending_key in {"age", "severity"}:
                raise StopIteration()
            # Allow bypass if user clearly describes a problem / asks what to do
            tl1 = (text or "").lower()
            tl2 = (text_en or "").lower()
            combined_tl = f"{tl1} {tl2}"
            strong_problem_signals = any(k in combined_tl for k in [
                "what should i do", "what can i do", "help me", "i have", "i'm having",
                "relief", "headache", "migraine", "anxiety", "stress", "panic", "insomnia",
                # Marathi/Hindi common asks
                "मी काय करू", "काय करू", "मला मदत",
                "माझं डोकं", "डोकं दुखत", "डोक दुखत", "डोके दुखत", "डोकेदुखी", "डोके दुखी",
                "स्ट्रेस", "तणाव", "ताण", "घालव", "कमी", "शांत",
                "सिरदर्द", "क्या करूँ", "मुझे मदद"
            ])
            if not strong_problem_signals:
                raise StopIteration()

        direct_question_indicators = [
            "how", "what", "why", "can", "could", "would", "should", "is", "are", "do", "does",
            "tell me", "give me", "help me", "need help", "advice", "suggest", "recommend",
            "help with", "relief from", "suffering from", "ways to", "how to", "tips for",
            "facing", "having", "got", "get"
        ]
        mental_health_terms = [
            "stress", "anxiety", "depression", "mental health", "therapy", "counseling",
            "panic", "worry", "fear", "trauma", "ptsd", "ocd", "bipolar",
            "insomnia", "sleep", "mood", "emotion", "feeling", "suicide", "self-harm",
            "addiction", "alcohol", "drug", "headache", "pain", "tired", "fatigue",
            "health", "unwell", "problem", "issue", "symptom", "relief"
        ]
        is_direct_request = (
            "?" in text_en or
            any(ind in text_en.lower() for ind in direct_question_indicators) or
            any(term in text_en.lower() for term in mental_health_terms)
        )
        if is_direct_request:
            chat.metadata["direct_question"] = True
            chat.metadata["triage_complete"] = True

            is_short = any(t in text_en.lower() for t in ["short", "brief", "quick", "concise"])
            if is_short:
                llm_prompt = f'User asked: "{text_en}"\nGive a brief, practical answer with 2-3 quick tips. Max 3-4 sentences.'
            else:
                llm_prompt = (
                    f'User asked: "{text_en}"\n'
                    'Give a compassionate, concise response:\n'
                    '1. Clear answer to their concern\n'
                    '2. 2-3 evidence-based coping strategies\n'
                    '3. Gentle reminder to seek professional help if needed'
                )

            # Single LLM call (Groq is fast; no PDF call needed)
            final_res = ask_large_model(llm_prompt)
            if not final_res:
                final_res = "I'm here for you. Please speak with a mental health professional for personalised guidance."

            # Translate back once using already-cached detected_lang
            if detected_lang != "en":
                try:
                    final_res = translator.translate(final_res, src="en", dest=detected_lang).text or final_res
                except Exception as te:
                    print(f"⚠️ translate-back error: {te}")

            add_encrypted_message(chat, final_res, "bot")
            chat.updated_at = datetime.utcnow()
            chat.save()
            return jsonify(chat.to_dict()), 200
    except StopIteration:
        pass
    except Exception as e:
        print(f"⚠️ Direct question handler error: {e}")

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
            # Translate the response to user's language
            user_lang = chat.metadata.get("user_language", "en")
            try:
                if user_lang != "en":
                    final_reply = translator.translate(reply_en, src='en', dest=user_lang).text
                else:
                    final_reply = reply_en
            except Exception as e:
                print(f"⚠️ YouTube translation error: {e}")
                final_reply = reply_en
                
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
            # Detect language from the current request
            detected_lang = "en"
            try:
                detected_lang = translator.detect(text).lang
                # Update the user's language in metadata
                chat.metadata["user_language"] = detected_lang
            except Exception as e:
                print(f"⚠️ YouTube language detection error: {e}")
                # Fall back to previously stored language if available
                detected_lang = chat.metadata.get("user_language", "en")
                
            # Translate the response to the detected language
            try:
                if detected_lang != "en":
                    final_reply = translator.translate(reply_en, src='en', dest=detected_lang).text
                else:
                    final_reply = reply_en
            except Exception as e:
                print(f"⚠️ YouTube translation error: {e}")
                final_reply = reply_en
            
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
                
                add_encrypted_message(chat, reply_text, "bot")
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
    # Check if triage has actually started (minimal metadata beyond user_language)
    triage_keys = ["age", "problem", "triage_complete", "duration", "triggers"]
    triage_started = any(k in chat.metadata for k in triage_keys)
    
    if not triage_started:
        normalized_hi = text.strip().lower()
        # Handle "reset" or "restart" to allow user to start over
        if any(w in normalized_hi for w in ["reset", "restart", "start over", "reinit", "नवनिर्मिती", "पुन्हा सुरू करा"]):
            chat.metadata = {}
            chat.save()
            return jsonify(chat.to_dict()), 200

        # More robust greeting words in multiple languages
        greeting_words = {
            "hi", "hello", "hey", "hola", "namaste", "good morning", "good evening", 
            "नमस्ते", "नमस्कार", "हाय", "हैलो", "प्रणाम",
            "नमस्कारा", "सुप्रभात", "शुभ संध्या", "हाय", "हॅलो", "मदत",
            "शुभ सकाळ", "शुभ दुपार", "शुभ रात्री", "कसे आहात", "कसे आहेस"
        }
        # Only treat as greeting if it matches a word or is very short AND NOT a number
        is_greeting = any(w in normalized_hi for w in greeting_words)
        is_short_non_numeric = len(text.strip()) < 4 and not text.strip().isdigit()
        
        if is_greeting or is_short_non_numeric:
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

    # Refresh language each turn cautiously based on current message.
    # IMPORTANT: during numeric triage steps (age/severity), do NOT flip language
    # even if the user types English letters (e.g., "25 years").
    prev_lang = chat.metadata.get("user_language")
    _expecting = None
    try:
        _expecting = next_triage_question(chat)
    except Exception:
        _expecting = None
    expecting_key = (_expecting or {}).get("key")

    if expecting_key in {"age", "severity"}:
        # Keep language stable for numeric collection
        chat.metadata["user_language"] = prev_lang or "en"
    else:
        has_letters = bool(re.search(r"[A-Za-z\u0900-\u097F]", text))
        if has_letters:
            chat.metadata["user_language"] = detect_user_language(text)
        else:
            chat.metadata["user_language"] = prev_lang or "en"

    # --- TRIAGE FLOW ---
    q = next_triage_question(chat)
    if q:
        # validate and save answer for the *current* missing key
        key = q["key"]
        user_lang = chat.metadata.get("user_language", "en")
        
        if key == "age":
            try:
                # Accept "माझे वय 25 आहे" style answers too
                m = re.search(r"\b(\d{1,3})\b", text)
                age_val = int(m.group(1)) if m else int(text.strip())
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
                m = re.search(r"\b(10|[1-9])\b", text.strip())
                sev = int(m.group(1)) if m else int(text.strip())
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
