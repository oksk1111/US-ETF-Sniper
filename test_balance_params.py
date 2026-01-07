from modules.kis_api import KisOverseas
import requests
import json

kis = KisOverseas()

# Try 1: FK200/NK200
print("--- TEST 1: FK200/NK200 ---")
tr_id = "VTTS3012R" if "openapivts" in kis.url else "TTTS3012R"
path = "/uapi/overseas-stock/v1/trading/inquire-balance"
headers = kis._get_headers(tr_id)
params = {
    "CANO": kis.acc_no_prefix,
    "ACNT_PRDT_CD": kis.acc_no_suffix,
    "OVRS_EXCG_CD": "NAS",
    "TR_CRCY_CD": "USD",
    "CTX_AREA_FK200": "",
    "CTX_AREA_NK200": ""
}
res = requests.get(kis.url + path, headers=headers, params=params)
print(res.text[:300])

# Try 2: TTTS3012R with FK100/NK100 (Original) - Just to confirm error
print("\n--- TEST 2: FK100/NK100 (Original) ---")
params2 = {
    "CANO": kis.acc_no_prefix,
    "ACNT_PRDT_CD": kis.acc_no_suffix,
    "OVRS_EXCG_CD": "NAS",
    "TR_CRCY_CD": "USD",
    "CTX_AREA_FK100": "",
    "CTX_AREA_NK100": ""
}
res2 = requests.get(kis.url + path, headers=headers, params=params2)
print(res2.text[:300])
