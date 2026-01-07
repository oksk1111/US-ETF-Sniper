from modules.kis_api import KisOverseas
import requests
import json
import os

# Create a mock instance manually
class MockKis(KisOverseas):
    def __init__(self):
        self.url = "https://openapivts.koreainvestment.com:29443"
        self.app_key = "YOUR_MOCK_KEY" # I don't have mock key.
        # Can't test mock without key.
        pass

# I can't test mock easily if I don't have creds.
# Let's try to hit the URL with random token just to see 404 or 401.
paths = [
    "/uapi/overseas-stock/v1/trading/inquire-present-balance",
    "/uapi/overseas-stock/v1/trading/inquire-oh-psbl-order",
    "/uapi/overseas-stock/v1/trading/inquire-balance-list",
    "/uapi/domestic-stock/v1/trading/inquire-balance" # Just to compare
]

headers = {"content-type": "application/json"}
for p in paths:
    url = "https://openapi.koreainvestment.com:9443" + p
    res = requests.get(url, headers=headers)
    print(f"Path: {p} -> Status: {res.status_code}")
