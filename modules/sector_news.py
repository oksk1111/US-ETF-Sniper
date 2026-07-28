"""
섹터별 뉴스 매핑 (v5.0 신규)

배경: 2026-07 중국발 반도체 규제 뉴스로 반도체 업종 전체가 붕괴했음에도,
     기존 봇은 "시장 전체" 단위의 뉴스만 확인(그마저도 v4.0에서 꺼져 있었음)하고
     "이 종목이 속한 섹터"의 뉴스는 전혀 확인하지 않아 SOXL/SMH 등을 계속 물타기 매수했다.

해결: 종목 → 섹터 매핑을 두고, 매수 직전 "해당 섹터"에 국한된 뉴스를 별도 조회하여
     섹터 단위로 크래시를 판별한다. 반도체만 나쁠 때 반도체 종목만 차단하고,
     관련 없는 다른 섹터/종목의 매수 기회는 그대로 유지한다 (전체 시장 차단과 다름).
"""

SECTOR_MAP = {
    "semiconductor": {
        "label_kr": "반도체",
        "query_en": "semiconductor chip stocks export ban China crash",
        "query_kr": "반도체 수출 규제 중국 반도체 업황 급락",
        "tickers": {
            # US
            "SOXL", "SOXX", "SMH", "NVDL", "NVDA", "AMD", "AMDL",
            # KR (개별주 + 반도체 테마 ETF)
            "005930", "000660", "091160", "0174B0", "381180", "0173Y0",
        },
    },
    "nasdaq_tech": {
        "label_kr": "나스닥/빅테크",
        "query_en": "nasdaq technology stocks big tech selloff Fed rate",
        "query_kr": "나스닥 기술주 미국 증시 연준 금리",
        "tickers": {
            "TQQQ", "QQQ", "TECL", "FNGU", "UPRO", "XLK",
            "426030", "0015B0", "133690", "456600", "0015B0",
        },
    },
    "broad_market": {
        "label_kr": "미국 증시 전반",
        "query_en": "US stock market S&P 500 crash selloff",
        "query_kr": "미국 증시 S&P500 급락",
        "tickers": {"SPY", "SPXL", "379800"},
    },
    "kr_broad": {
        "label_kr": "코스피/코스닥 전반",
        "query_en": "Korea stock market KOSPI crash",
        "query_kr": "코스피 코스닥 급락 증시",
        "tickers": {"069500", "292150", "495230", "0080G0", "0151P0"},
    },
    "battery": {
        "label_kr": "2차전지",
        "query_en": "battery EV stocks lithium crash",
        "query_kr": "2차전지 배터리 전기차 업황 급락",
        "tickers": {"305720", "364980"},
    },
}


def get_sector(ticker):
    """종목 코드가 속한 섹터 키를 반환. 매핑이 없으면 None (섹터 veto 미적용)."""
    if not ticker:
        return None
    t = str(ticker).upper()
    for key, meta in SECTOR_MAP.items():
        if t in meta["tickers"] or str(ticker) in meta["tickers"]:
            return key
    return None


def get_sector_meta(sector_key):
    return SECTOR_MAP.get(sector_key)
