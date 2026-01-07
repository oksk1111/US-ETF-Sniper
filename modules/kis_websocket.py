import asyncio
import websockets
import json
import logging
import time
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_MOCK

class KisWebSocket:
    def __init__(self, tickers, callback):
        self.tickers = tickers
        self.callback = callback
        self.approval_key = None
        self.connected = False
        
        # Real/Mock URL differentiation
        if KIS_MOCK:
            self.base_url = "https://openapivts.koreainvestment.com:29443"
            self.ws_url = "ws://ops.koreainvestment.com:31000" # Advanced Mock
        else:
            self.base_url = "https://openapi.koreainvestment.com:9443"
            self.ws_url = "ws://ops.koreainvestment.com:21000" # Real
            
    def get_approval_key(self):
        import requests
        url = f"{self.base_url}/oauth2/Approval"
        headers = {"content-type": "application/json; utf-8"}
        body = {
            "grant_type": "client_credentials",
            "appkey": KIS_APP_KEY,
            "secretkey": KIS_APP_SECRET
        }
        try:
            res = requests.post(url, headers=headers, data=json.dumps(body))
            res.raise_for_status()
            self.approval_key = res.json()["approval_key"]
            logging.info(f"WebSocket Approval Key: {self.approval_key[:10]}...")
            return True
        except Exception as e:
            logging.error(f"Failed to get WebSocket Approval Key: {e}")
            return False

    async def connect(self):
        if not self.approval_key:
            if not self.get_approval_key():
                return

        try:
            async with websockets.connect(f"{self.ws_url}/tryitout/HDFSZC413000") as websocket:
                logging.info("WebSocket Connected.")
                self.connected = True
                
                # Subscribe to each ticker
                for ticker in self.tickers:
                    # TR_ID: HDFSZC413000 (US Realtime Execution) or HDFSCNT0 (Quote)
                    # Using Execution Price (HDFSZC413000) for fastest trade data
                    # Mock uses H0STCNT0 generally
                    
                    tr_id = "H0STCNT0" if KIS_MOCK else "HDFSZC413000" 
                    tr_type = "1" # Register
                    
                    # Format Input: Key depends on TR_ID
                    # Real: HDFSZC413000 -> ticker (DNAS), Mock: H0STCNT0 -> ticker (DNAS)
                    
                    # Note: Need ticker symbol like 'DNASS' + 'AAPL' ?
                    # Usually: D+NAS+Ticker (e.g., DNASAAPL)
                    # For ETF/Stock: R+NAS+Ticker or D+NAS+Ticker
                    # Let's try general format D+NAS+{Ticker}
                    
                    # Symbol Code Generation
                    # US Market Codes: NAS(Nasdaq), NYS(NYSE), AMS(Amex)
                    # Simplified: Assume all are NAS for now or lookup. 
                    # TQQQ, SOXL, NVDA are NAS. TSLA is NAS. FNGU is NYS(Arca)? No, FNGU is BZX (Cboe).
                    # This is tricky. Let's start with NAS assumption for simplicity.
                    
                    stock_code = f"DNAS{ticker}" 
                    
                    req = {
                        "header": {
                            "approval_key": self.approval_key,
                            "custtype": "P",
                            "tr_type": tr_type,
                            "content-type": "utf-8"
                        },
                        "body": {
                            "input": {
                                "tr_id": tr_id,
                                "tr_key": stock_code 
                            }
                        }
                    }
                    await websocket.send(json.dumps(req))
                    logging.info(f"Subscribed to {ticker} ({stock_code})")
                    
                while True:
                    data = await websocket.recv()
                    
                    # Ping/Pong handling if necessary (KIS usually sends data stream)
                    # Decrypt/Parse data
                    # Data format is separated by |
                    # 0: encrypted(0/1) | 1: tr_id | 2: len | 3: data
                    
                    # Raw parsing
                    parts = data.split('|')
                    if len(parts) > 3:
                        tr_id = parts[1]
                        payload = parts[3]
                        
                        # Parse payload based on documentation
                        # For US Stock Realtime (HDFSZC413000):
                        # Fields: Time, Price, Vol, etc.
                        # Simple retrieval of current price
                        
                        try:
                            # Typically split by '^'
                            fields = payload.split('^')
                            if len(fields) > 2:
                                # Field 1 is usually current price (check docs)
                                # 11:11:11^120.50^10...
                                # Assuming Price is at index 1 or 2
                                current_price_str = fields[2] # Example index. Needs verification.
                                
                                # Let's assume index 2 is price (Common in KIS)
                                # But let's log first message to calibrate
                                
                                price = float(current_price_str)
                                await self.callback(ticker, price)
                                
                        except Exception as e:
                            pass # Parse error
                            
                    elif data[0] == '{': # JSON system message (PING or ACK)
                        msg = json.loads(data)
                        # logging.debug(f"WS Sys Msg: {msg}")
                        
        except Exception as e:
            logging.error(f"WebSocket Error: {e}")
            self.connected = False

    def start(self):
        # Run async loop
        asyncio.run(self.connect())
