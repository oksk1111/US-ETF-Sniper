import requests
import json
import time
from config import KIS_BASE_URL, KIS_APP_KEY, KIS_APP_SECRET, KIS_CANO, KIS_ACNT_PRDT_CD

class KisOverseas:
    def __init__(self):
        self.url = KIS_BASE_URL
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self.acc_no_prefix = KIS_CANO
        self.acc_no_suffix = KIS_ACNT_PRDT_CD
        self.access_token = None
        self.token_expiry = 0
        
        self._refresh_token()

    def _refresh_token(self):
        """Access Token 발급"""
        if time.time() < self.token_expiry:
            return

        path = "/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            res = requests.post(self.url + path, headers=headers, data=json.dumps(body))
            res.raise_for_status()
            data = res.json()
            self.access_token = data['access_token']
            self.token_expiry = time.time() + int(data['expires_in']) - 60 # 1분 여유
            print(f"[KIS] Token refreshed. Expires in {data['expires_in']} seconds.")
        except Exception as e:
            print(f"[KIS] Token refresh failed: {e}")
            raise

    def _get_headers(self, tr_id):
        self._refresh_token()
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }

    def get_current_price(self, ticker):
        """해외주식 현재가 조회 (NAS: 나스닥)"""
        path = "/uapi/overseas-price/v1/quotations/price"
        headers = self._get_headers("HHDFS00000300")
        params = {
            "AUTH": "",
            "EXCD": "NAS",
            "SYMB": ticker
        }
        
        try:
            res = requests.get(self.url + path, headers=headers, params=params)
            res.raise_for_status()
            data = res.json()
            if data['rt_cd'] != '0':
                print(f"[KIS] Error getting price: {data['msg1']}")
                return None
            return float(data['output']['last'])
        except Exception as e:
            print(f"[KIS] Exception getting price: {e}")
            return None

    def get_quote(self, ticker):
        """해외주식 현재가 상세 조회 (시가, 고가, 저가 포함)"""
        path = "/uapi/overseas-price/v1/quotations/price"
        headers = self._get_headers("HHDFS00000300")
        params = {
            "AUTH": "",
            "EXCD": "NAS",
            "SYMB": ticker
        }
        
        try:
            res = requests.get(self.url + path, headers=headers, params=params)
            res.raise_for_status()
            data = res.json()
            if data['rt_cd'] != '0':
                print(f"[KIS] Error getting quote: {data['msg1']}")
                return None
            return data['output'] # last, open, high, low, base, etc.
        except Exception as e:
            print(f"[KIS] Exception getting quote: {e}")
            return None

    def get_daily_ohlc(self, ticker, period="D"):
        """해외주식 기간별 시세 (일봉)"""
        # HHDFS76240000 : 해외주식 기간별시세(일/주/월/년)
        path = "/uapi/overseas-price/v1/quotations/dailyprice"
        headers = self._get_headers("HHDFS76240000")
        
        # 오늘 날짜 기준
        import datetime
        today = datetime.datetime.now().strftime("%Y%m%d")
        
        params = {
            "AUTH": "",
            "EXCD": "NAS",
            "SYMB": ticker,
            "GUBN": "0", # 0:일, 1:주, 2:월
            "BYMD": today,
            "MODP": "1" # 0:수정주가미반영, 1:수정주가반영
        }
        
        try:
            res = requests.get(self.url + path, headers=headers, params=params)
            res.raise_for_status()
            data = res.json()
            if data['rt_cd'] != '0':
                print(f"[KIS] Error getting OHLC: {data['msg1']}")
                return None
            return data['output2'] # 일별 데이터 리스트
        except Exception as e:
            print(f"[KIS] Exception getting OHLC: {e}")
            return None

    def buy_market_order(self, ticker, qty):
        """해외주식 시장가 매수"""
        # 모의투자/실전투자 TR_ID 구분 필요
        # 실전: TTTT1002U (미국 매수 주문) / 모의: VTTT1002U
        tr_id = "VTTT1002U" if "openapivts" in self.url else "TTTT1002U"
        
        path = "/uapi/overseas-stock/v1/trading/order"
        headers = self._get_headers(tr_id)
        
        data = {
            "CANO": self.acc_no_prefix,
            "ACNT_PRDT_CD": self.acc_no_suffix,
            "OVRS_EXCG_CD": "NAS",
            "PDNO": ticker,
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": "0", # 시장가는 0
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": "00" # 00: 지정가, 32: 시장가 (미국주식 시장가 주문은 보통 지원 안하거나 제한적일 수 있음. 여기서는 기획서대로 진행하되 확인 필요)
            # *주의*: KIS API에서 미국주식 시장가(32)가 안될 경우 지정가로 현재가보다 높게 쏘는 방식 사용해야 함.
            # 일단 기획서의 '시장가' 의도를 살려 00(지정가) + 높은 가격 or 32 시도. 
            # API 문서상 미국주식은 지정가(00), LOO(32), LOC(34) 등임. 장중 시장가는 보통 지원 안함.
            # 따라서 "최유리 지정가" 혹은 "현재가 + alpha"로 주문해야 함.
            # 여기서는 편의상 00(지정가)로 하되 가격을 0으로 두면 에러날 수 있음.
            # 기획서에는 "시장가"라고 되어있으나 API 구현상 수정 필요.
            # -> 수정: 현재가 조회 후 +1% 가격으로 지정가 주문 (시장가 효과)
        }
        
        # 현재가 조회
        current_price = self.get_current_price(ticker)
        if not current_price:
            return None
            
        # 매수 주문 가격 (현재가 * 1.01)
        buy_price = round(current_price * 1.01, 2)
        data["OVRS_ORD_UNPR"] = str(buy_price)
        
        try:
            res = requests.post(self.url + path, headers=headers, data=json.dumps(data))
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"[KIS] Order failed: {e}")
            return None

    def sell_market_order(self, ticker, qty):
        """해외주식 시장가 매도"""
        tr_id = "VTTT1006U" if "openapivts" in self.url else "TTTT1006U"
        path = "/uapi/overseas-stock/v1/trading/order"
        headers = self._get_headers(tr_id)
        
        # 현재가 조회
        current_price = self.get_current_price(ticker)
        if not current_price:
            return None
            
        # 매도 주문 가격 (현재가 * 0.99) - 즉시 체결 유도
        sell_price = round(current_price * 0.99, 2)
        
        data = {
            "CANO": self.acc_no_prefix,
            "ACNT_PRDT_CD": self.acc_no_suffix,
            "OVRS_EXCG_CD": "NAS",
            "PDNO": ticker,
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": str(sell_price),
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": "00" 
        }
        
        try:
            res = requests.post(self.url + path, headers=headers, data=json.dumps(data))
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"[KIS] Sell Order failed: {e}")
            return None

    def get_balance(self):
        """잔고 조회"""
        # HHDFS76410000 : 해외주식 잔고지원
        tr_id = "VTTS3012R" if "openapivts" in self.url else "TTTS3012R" # 모의/실전 TR ID 확인 필요. 
        # 문서상: 해외주식 체결기준잔고 (TTTS3012R)
        
        path = "/uapi/overseas-stock/v1/trading/inquire-balance"
        headers = self._get_headers(tr_id)
        
        params = {
            "CANO": self.acc_no_prefix,
            "ACNT_PRDT_CD": self.acc_no_suffix,
            "OVRS_EXCG_CD": "NAS",
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        try:
            res = requests.get(self.url + path, headers=headers, params=params)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"[KIS] Balance check failed: {e}")
            return None
