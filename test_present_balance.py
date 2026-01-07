from modules.kis_api import KisOverseas
import requests
import json

kis = KisOverseas()
print("[TEST] Testing Present Balance (Deposit)")

# Focus on TTTS3018R
tr_ids = ["TTTS3018R"]

path = "/uapi/overseas-stock/v1/trading/inquire-present-balance"

for tr_id in tr_ids:
    print(f"\n--- Testing TR_ID: {tr_id} ---")
    headers = kis._get_headers(tr_id)
    
    # Guessing missing params
    params = {
        "CANO": kis.acc_no_prefix,
        "ACNT_PRDT_CD": kis.acc_no_suffix,
        "OVRS_EXCG_CD": "NAS",
        "TR_CRCY_CD": "USD",
        "SORT_SQN": "DS", # Guess
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": ""
    }
    
    try:
        res = requests.get(kis.url + path, headers=headers, params=params)
        print("Status:", res.status_code)
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print("Error:", e)
