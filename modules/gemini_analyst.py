import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
import json
import urllib.parse
from config import GEMINI_API_KEY

class GeminiAnalyst:
    def __init__(self):
        if not GEMINI_API_KEY or "INSERT" in GEMINI_API_KEY:
            print("[Gemini] API Key is missing. AI analysis will be skipped (Defaulting to Neutral/Positive).")
            self.model = None
            self.available = False
        else:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            self.available = True

    def health_check(self):
        """API 연결 상태 확인 (최소 비용 요청)"""
        if not self.model:
            return False
        try:
            response = self.model.generate_content("hi", request_options={"timeout": 15})
            _ = response.text
            print("[Gemini] Health check PASSED ✓")
            return True
        except Exception as e:
            error_str = str(e)
            # 429 quota exceeded는 일시적 → available 유지하되 경고
            if "429" in error_str or "quota" in error_str.lower():
                print(f"[Gemini] Health check WARNING: 일일 할당량 초과 (일시적). 투표에는 포함하되 실패 시 제외됩니다.")
                return True  # 일시적이므로 available 유지
            print(f"[Gemini] Health check FAILED: {e}")
            self.available = False
            return False

    def fetch_news(self):
        """CNBC Finance RSS Feed Fetch"""
        url = "https://www.cnbc.com/id/10000664/device/rss/rss.html" # Finance
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            
            headlines = []
            for item in root.findall('./channel/item'):
                title_el = item.find('title')
                desc_el = item.find('description')
                title = title_el.text if title_el is not None else ""
                description = desc_el.text if desc_el is not None else ""
                if title:
                    headlines.append(f"- {title}: {description}")
                if len(headlines) >= 10: # Top 10 only
                    break
            
            return "\n".join(headlines)
        except Exception as e:
            print(f"[Gemini] Failed to fetch news: {e}")
            return ""

    def fetch_topic_news(self, query, lang="en"):
        """[v5.0 신규] 특정 주제/섹터(예: 반도체) 뉴스만 골라 수집 (Google News RSS, API 키 불필요).

        전체 시장 뉴스(fetch_news)와 달리, query로 좁힌 섹터/테마 뉴스만 가져와
        섹터 단위 위험 판별(check_sector_crash)에 사용한다.
        """
        if lang == "ko":
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
        else:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            headlines = []
            for item in root.findall('./channel/item'):
                title_el = item.find('title')
                title = title_el.text if title_el is not None else ""
                if title:
                    headlines.append(f"- {title}")
                if len(headlines) >= 8:  # Top 8 only (섹터 뉴스는 소수 헤드라인으로 충분)
                    break

            return "\n".join(headlines)
        except Exception as e:
            print(f"[Gemini] Failed to fetch topic news ({query}): {e}")
            return ""

    def check_sector_crash(self, sector_label, news_text):
        """[v5.0 신규] 섹터 특화 크래시 판별 — 트레이딩 페르소나(공격적/중립/보수)와 무관하게
        항상 엄격/객관적으로 판단한다.

        목적: "전체 시장은 괜찮지만 이 섹터만 무너지는" 상황(예: 반도체 수출규제)을
        페르소나에 관계없이 감지하기 위한 자본보호 전용 게이트. aggressive 페르소나가
        "핵전쟁 수준 아니면 사라"고 지시하는 것과 별개로 동작해야 하므로 페르소나 인자를
        받지 않는다.
        """
        if not self.model:
            return {"risk_level": "LOW", "can_buy": True, "market_condition": "NEUTRAL",
                     "reason": "API Key missing, skipping sector check.", "source": "gemini"}
        if not news_text:
            return {"risk_level": "LOW", "can_buy": True, "market_condition": "NEUTRAL",
                     "reason": "No sector news found, skipping sector check.", "source": "gemini"}

        prompt = f"""
        Act as a conservative risk-control officer for an automated trading system.
        Your ONLY job is capital preservation for ONE specific sector: "{sector_label}".
        Ignore general trading opportunism — you are a circuit breaker, not a trader.

        Here are the latest news headlines specifically about the "{sector_label}" sector:
        {news_text}

        Critical Check (sector-specific, not whole-market):
        1. Is there a severe negative shock specific to this sector (e.g. export ban,
           regulatory crackdown, demand collapse, major sell-off, oversupply crisis)?
        2. Would a reasonable risk manager pause NEW buying in this sector right now?

        Reply with JSON ONLY:
        {{
            "risk_level": "HIGH" or "LOW",
            "can_buy": boolean,
            "market_condition": "CRASH" or "BEARISH" or "NEUTRAL" or "BULLISH",
            "reason": "short summary"
        }}
        """

        try:
            response = self.model.generate_content(prompt, request_options={"timeout": 15})
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]

            result = json.loads(text)
            result["source"] = "gemini"
            if "market_condition" not in result:
                result["market_condition"] = "BEARISH" if result.get("risk_level") == "HIGH" else "NEUTRAL"
            return result
        except Exception as e:
            print(f"[Gemini] Sector crash check failed ({sector_label}): {e}")
            return {"risk_level": "UNKNOWN", "can_buy": False, "market_condition": "UNKNOWN",
                     "reason": f"AI Error: {e}", "source": "gemini"}

    def check_market_sentiment(self, news_text, persona="aggressive"):
        if not self.model:
            return {"risk_level": "LOW", "can_buy": True, "market_condition": "NEUTRAL", "reason": "API Key missing, skipping AI check.", "source": "gemini"}
        
        if not news_text:
            return {"risk_level": "LOW", "can_buy": True, "market_condition": "NEUTRAL", "reason": "No news found, skipping AI check.", "source": "gemini"}

        # Define Persona Prompts
        persona_instructions = {
            "aggressive": "You are an AGGRESSIVE trader. You ignore minor fears and focus on momentum. Only stop buying if there is a CONFIRMED GLOBAL CATASTROPHE (Nuclear War, Great Depression). Volatility is opportunity.",
            "neutral": "You are a BALANCED trader. Weigh risks and rewards equally. Avoid buying during clear downtrends or major bad news, but don't panic over small corrections.",
            "conservative": "You are a CONSERVATIVE trader. Preservation of capital is priority #1. If there is ANY hint of instability, rate hikes, or uncertainty, recommend HOLD or SELL. Do not buy unless the market is perfectly calm."
        }
        
        selected_instruction = persona_instructions.get(persona, persona_instructions["aggressive"])

        prompt = f"""
        Act as a stock trading AI assistant.
        Persona: {selected_instruction}

        Here are the latest news headlines regarding US Tech Market & Fed:
        {news_text}

        Critical Check:
        1. Is there any MAJOR crash signal matching your persona's risk tolerance?
        2. Is the sentiment predominantly Fear?

        Reply with JSON ONLY:
        {{
            "risk_level": "HIGH" or "LOW",
            "can_buy": boolean,
            "market_condition": "CRASH" or "BEARISH" or "NEUTRAL" or "BULLISH",
            "reason": "short summary"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt, request_options={"timeout": 15})
            text = response.text.strip()
            # Clean up markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            
            result = json.loads(text)
            # 일관성을 위해 source/market_condition 보장
            result["source"] = "gemini"
            if "market_condition" not in result:
                result["market_condition"] = "BEARISH" if result.get("risk_level") == "HIGH" else "NEUTRAL"
            return result
        except Exception as e:
            print(f"[Gemini] AI Analysis failed: {e}")
            return {"risk_level": "UNKNOWN", "can_buy": False, "market_condition": "UNKNOWN", "reason": f"AI Error: {e}", "source": "gemini"}
