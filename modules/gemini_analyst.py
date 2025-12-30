import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
import json
from config import GEMINI_API_KEY

class GeminiAnalyst:
    def __init__(self):
        if not GEMINI_API_KEY or "INSERT" in GEMINI_API_KEY:
            print("[Gemini] API Key is missing. AI analysis will be skipped (Defaulting to Neutral/Positive).")
            self.model = None
        else:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

    def fetch_news(self):
        """CNBC Finance RSS Feed Fetch"""
        url = "https://www.cnbc.com/id/10000664/device/rss/rss.html" # Finance
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            
            headlines = []
            for item in root.findall('./channel/item'):
                title = item.find('title').text
                description = item.find('description').text
                headlines.append(f"- {title}: {description}")
                if len(headlines) >= 10: # Top 10 only
                    break
            
            return "\n".join(headlines)
        except Exception as e:
            print(f"[Gemini] Failed to fetch news: {e}")
            return ""

    def check_market_sentiment(self, news_text):
        if not self.model:
            return {"risk_level": "LOW", "can_buy": True, "reason": "API Key missing, skipping AI check."}
        
        if not news_text:
            return {"risk_level": "LOW", "can_buy": True, "reason": "No news found, skipping AI check."}

        prompt = f"""
        Act as a aggressive stock trader.
        Here are the latest news headlines regarding US Tech Market & Fed:
        {news_text}

        Critical Check:
        1. Is there any MAJOR crash signal (e.g. War, Unexpected Rate Hike)?
        2. Is the sentiment predominantly Fear?

        Reply with JSON ONLY:
        {{
            "risk_level": "HIGH" or "LOW",
            "can_buy": boolean,
            "reason": "short summary"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            # Clean up markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            
            return json.loads(text)
        except Exception as e:
            print(f"[Gemini] AI Analysis failed: {e}")
            # Fail safe: Do not buy if AI fails? Or buy? 
            # Strategy says: "AI filters bad news". If AI fails, maybe we should be cautious.
            # But for now, let's return False to be safe.
            return {"risk_level": "UNKNOWN", "can_buy": False, "reason": f"AI Error: {e}"}
