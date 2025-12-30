import os
from dotenv import load_dotenv

load_dotenv()

# KIS API Config
KIS_APP_KEY = os.getenv("KIS_APP_KEY")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET")
KIS_CANO = os.getenv("KIS_CANO")
KIS_ACNT_PRDT_CD = os.getenv("KIS_ACNT_PRDT_CD")
KIS_MOCK = os.getenv("KIS_MOCK", "True").lower() == "true"

# Gemini API Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Base URLs
KIS_URL_REAL = "https://openapi.koreainvestment.com:9443"
KIS_URL_MOCK = "https://openapivts.koreainvestment.com:29443"
KIS_BASE_URL = KIS_URL_MOCK if KIS_MOCK else KIS_URL_REAL
