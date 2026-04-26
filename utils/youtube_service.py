import os
import requests
from dotenv import load_dotenv

load_dotenv()

class YouTubeService:
    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3/search"
        
    def detect_language(self, text):
        """
        Detect language from text input
        Currently supports English, Hindi, and Marathi
        Returns language code: 'en', 'hi', or 'mr'
        """
        # Ensure text is a string
        if not isinstance(text, str):
            try:
                text = str(text)
            except:
                return "en"  # Default to English if conversion fails
                
        text = text.lower()
        
        # Marathi-specific words (check these first)
        marathi_words = [
            "आहे", "नाही", "मला", "तुला", "आम्ही", "तुम्ही", "काय", "कसे", "कधी", 
            "का", "कोण", "कुठे", "कोणता", "कोणती", "कोणते", "आणि", "परंतु", "किंवा",
            "तणावातून", "मुक्त", "होण्यासाठी", "उपाय", "असलेले", "यूट्यूब", "व्हिडिओज", "द्या"
        ]
        
        # Hindi words
        hindi_words = [
            "है", "नहीं", "मैं", "तुम", "हम", "आप", "क्या", "कैसे", "कब", 
            "क्यों", "कौन", "कहां", "कौनसा", "कौनसी", "कौनसे", "और", "लेकिन", "या",
            "तनाव", "मुक्ति", "उपाय", "वीडियो", "दिखाओ", "बताओ"
        ]
        
        # Count matches for each language
        marathi_count = sum(1 for word in marathi_words if word in text)
        hindi_count = sum(1 for word in hindi_words if word in text)
        
        # Determine language based on word count
        if marathi_count > hindi_count:
            return "mr"
        elif hindi_count > 0:
            return "hi"
        else:
            return "en"
    
    def search_videos(self, query, max_results=5, language=None):
        """
        Search for YouTube videos based on a query
        Returns a list of dictionaries with video information
        
        Parameters:
        - query: Search query
        - max_results: Maximum number of results to return
        - language: Language code (en, hi, mr) for relevance language
        """
        if not self.api_key:
            return {"error": "YouTube API key not configured"}
            
        params = {
            "part": "snippet",
            "q": query,
            "key": self.api_key,
            "maxResults": max_results,
            "type": "video",
            "videoEmbeddable": "true"
        }
        
        # Add relevanceLanguage parameter based on detected language
        if language:
            # Map our language codes to YouTube API language codes
            language_map = {
                "en": "en",
                "hi": "hi",
                "mr": "mr"  # YouTube API supports Marathi
            }
            params["relevanceLanguage"] = language_map.get(language, "en")
            
            # Add regionCode for better localized results
            region_map = {
                "en": "US",
                "hi": "IN",
                "mr": "IN"  # India for Marathi
            }
            params["regionCode"] = region_map.get(language, "US")
            
            # Add language to query for better results
            if language == "mr":
                # Append "मराठी" to query for Marathi videos
                params["q"] = f"{query} मराठी"
            elif language == "hi":
                # Append "हिंदी" to query for Hindi videos
                params["q"] = f"{query} हिंदी"
        
        try:
            response = requests.get(self.base_url, params=params)
            data = response.json()
            
            if response.status_code != 200:
                return {"error": f"YouTube API error: {data.get('error', {}).get('message', 'Unknown error')}"}
                
            videos = []
            for item in data.get("items", []):
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                description = item["snippet"]["description"]
                thumbnail = item["snippet"]["thumbnails"]["medium"]["url"]
                
                videos.append({
                    "id": video_id,
                    "title": title,
                    "description": description,
                    "thumbnail": thumbnail,
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
                
            return videos
        except Exception as e:
            return {"error": f"Error searching YouTube: {str(e)}"}

# Create a singleton instance
youtube_service = YouTubeService()