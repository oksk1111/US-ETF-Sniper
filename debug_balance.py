from modules.kis_api import KisOverseas
import json

kis = KisOverseas()
balance = kis.get_balance()
print("--- BALANCE RESPONSE ---")
print(json.dumps(balance, indent=2, ensure_ascii=False))
