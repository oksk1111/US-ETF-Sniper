import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv("KIS_APP_KEY")
APP_SECRET = os.getenv("KIS_APP_SECRET")

def test_connection(is_mock):
    base_url = "https://openapivts.koreainvestment.com:29443" if is_mock else "https://openapi.koreainvestment.com:9443"
    path = "/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    
    print(f"Testing {'MOCK' if is_mock else 'REAL'} server...")
    try:
        res = requests.post(base_url + path, headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            print(f"✅ {'MOCK' if is_mock else 'REAL'} Connection Successful!")
            return True
        else:
            print(f"❌ {'MOCK' if is_mock else 'REAL'} Failed: {res.status_code} {res.text}")
            return False
    except Exception as e:
        print(f"❌ {'MOCK' if is_mock else 'REAL'} Error: {e}")
        return False

if __name__ == "__main__":
    print("--- KIS API Connection Test (REAL ONLY) ---")
    # Test Real
    real_success = test_connection(False)
    
    if real_success:
        print("\n✅ REAL Server Connected Successfully!")
    else:
        print("\n❌ REAL Server Connection Failed.")
