from modules.kis_api import KisOverseas
import requests
import json

kis = KisOverseas()
print("[TEST] Testing CTRP6504R (Domestic/Overseas Balance)")

headers = kis._get_headers("CTRP6504R")
path = "/uapi/domestic-stock/v1/trading/inquire-balance"

# WCRC_FRCR_DVSN_CD: 01-Won, 02-Foreign
params = {
    "CANO": kis.acc_no_prefix,
    "ACNT_PRDT_CD": kis.acc_no_suffix,
    "WCRC_FRCR_DVSN_CD": "02", 
    "CTX_AREA_FK100": "",
    "CTX_AREA_NK100": "",
    "INQR_DVSN": "02",
    "fund_sttl_icld_yn": "N",
    "fncg_amt_auto_rdpt_yn": "N",
    "prcs_dvsn": "00",
    "TR_MKET_CD": "00",
    "NATN_CD": "840",
    "INQR_DVSN_CD": "00"
}

try:
    res = requests.get(kis.url + path, headers=headers, params=params)
    print("Status:", res.status_code)
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print("Error:", e)
