from modules.kis_api import KisOverseas
import requests
import json

kis = KisOverseas()
print("[TEST] Testing Buying Power (TTTS3007R)")

tr_id = "VTTS3007R" if "openapivts" in kis.url else "TTTS3007R"
path = "/uapi/overseas-stock/v1/trading/inquire-psbl-order"
headers = kis._get_headers(tr_id)

params = {
    "CANO": kis.acc_no_prefix,
    "ACNT_PRDT_CD": kis.acc_no_suffix,
    "OVRS_EXCG_CD": "NAS",
    "OVRS_ORD_UNPR": "0",
    "ITEM_CD": "TQQQ" # Dummy ticker
}

paths = [
    "/uapi/overseas-stock/v1/trading/inquire-psbl-order",
    "/uapi/overseas-stock/v1/trading/psbl-order",
    "/uapi/overseas-stock/v1/trading/inquire-orderable-amount"
]

for p in paths:
    print(f"\n--- Testing Path: {p} ---")
    try:
        res = requests.get(kis.url + p, headers=headers, params=params)
        print("Status:", res.status_code)
        if res.status_code != 404:
            print("Response:", res.text[:200])
    except Exception as e:
        print("Error:", e)
