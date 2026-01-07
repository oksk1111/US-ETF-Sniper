from modules.kis_api import KisOverseas
import json

kis = KisOverseas()
balance = kis.get_balance()

print("--- BALANCE RESPONSE (output2) ---")
if balance and 'output2' in balance:
    out2 = balance['output2']
    print(f"Type of output2: {type(out2)}")
    print(json.dumps(out2, indent=2, ensure_ascii=False))
else:
    print("No output2 in balance")

print("\n--- FULL RESPONSE ---")
print(json.dumps(balance, indent=2, ensure_ascii=False))
