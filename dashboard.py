import streamlit as st
import pandas as pd
import os
import glob
import re
import time
from modules.kis_api import KisOverseas

st.set_page_config(
    page_title="US-ETF-Sniper Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 US-ETF-Sniper Dashboard")

# --- Initialize API ---
# @st.cache_resource  <-- Disabled caching for debugging
def get_kis_client():
    return KisOverseas()

try:
    kis = get_kis_client()
    api_status = "🟢 API Connected"
except Exception as e:
    kis = None
    api_status = f"🔴 API Error: {str(e)}"

# --- Sidebar ---
st.sidebar.header("Settings")
refresh_rate = st.sidebar.slider("Refresh Rate (sec)", 1, 60, 5)
auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
st.sidebar.markdown(f"**API Status**: {api_status}")

# --- Helper Functions ---
def get_latest_log_file():
    log_files = glob.glob("database/trading_*.log")
    if not log_files:
        return None
    # Sort by filename (date) descending
    return sorted(log_files)[-1]

def parse_log_line(line):
    # Simple parser to extract timestamp and message
    # Format: 2025-12-31 02:48:44,165 - INFO - Message
    match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3} - (\w+) - (.*)", line)
    if match:
        return {
            "timestamp": match.group(1),
            "level": match.group(2),
            "message": match.group(3)
        }
    return None

def get_bot_status(last_log_time_str):
    if not last_log_time_str:
        return "Unknown"
    
    try:
        last_time = pd.to_datetime(last_log_time_str)
        now = pd.Timestamp.now()
        diff = (now - last_time).total_seconds()
        
        if diff < 300: # 5 minutes
            return "🟢 Running"
        else:
            return "🔴 Stopped / Idle"
    except:
        return "Unknown"

# --- Main Content ---
tab1, tab2, tab3 = st.tabs(["📊 Overview", "💰 Account & Portfolio", "📜 Logs & History"])

log_file = get_latest_log_file()
parsed_lines = []

if log_file:
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Fallback to system encoding (cp949/euc-kr)
        with open(log_file, "r", encoding="cp949") as f:
            lines = f.readlines()
        
    parsed_lines = [parse_log_line(line) for line in lines]
    parsed_lines = [x for x in parsed_lines if x is not None]

# --- Tab 1: Overview ---
with tab1:
    if parsed_lines:
        # 1. Status
        last_log = parsed_lines[-1]
        status = get_bot_status(last_log['timestamp'])
        
        # 2. Key Metrics (Extract from logs)
        # Look for "Current: X, MA20: Y" and "Target Price: Z"
        current_price = "N/A"
        ma20 = "N/A"
        target_price = "N/A"
        
        for line in reversed(parsed_lines):
            msg = line['message']
            # "Current: 54.3839, MA20: 54.3137" or "Current: None, MA20: None"
            # Updated regex to handle 'None' or numbers
            m1 = re.search(r"Current: ([^,]+), MA20: (.+)", msg)
            if m1 and current_price == "N/A":
                current_price = m1.group(1).strip()
                ma20 = m1.group(2).strip()
            
            # "Target Price: 55.12"
            m2 = re.search(r"Target Price: ([^ ]+)", msg)
            if m2 and target_price == "N/A":
                target_price = m2.group(1).strip()
                
            if current_price != "N/A" and target_price != "N/A":
                break
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Bot Status", status)
        with col2:
            st.metric("Current Price", f"${current_price}")
        with col3:
            st.metric("Target Price", f"${target_price}")
        with col4:
            st.metric("20 MA", f"${ma20}")
        
        st.markdown(f"Last Update: `{last_log['timestamp']}`")
    else:
        st.warning("No logs found. Is the bot running?")

# --- Tab 2: Account ---
with tab2:
    if st.button("Refresh Account Info"):
        # Just to trigger rerun
        pass

    if kis:
        balance = kis.get_balance()
        foreign_balance = kis.get_foreign_balance()
        
        # --- Prepare Data ---
        deposit_usd = "N/A"
        if foreign_balance:
            if 'debug_raw' in foreign_balance:
                st.error(f"⚠️ USD Balance not found! Raw API Data: {foreign_balance['debug_raw']}")
            else:
                deposit_usd = str(foreign_balance['deposit'])
        
        # DEBUG: Show foreign balance raw
        with st.expander("DEBUG: Foreign Balance Response"):
            st.write(f"Raw Foreign Balance Object: {foreign_balance}")
            st.write(f"Derived Deposit USD: {deposit_usd}")

        buying_power = "N/A"
        total_profit = "0"
        total_return = "0"
        
        has_stock_balance = False
        if balance and 'output2' in balance and isinstance(balance['output2'], list) and len(balance['output2']) > 0:
            has_stock_balance = True
            summary = balance['output2'][0]
            buying_power = summary.get('ovrs_ord_psbl_amt', '0')
            total_profit = summary.get('tot_evlu_pfls_amt', '0')
            total_return = summary.get('ovrs_tot_pfls', '0')
            
            # Fallback buying power logic: if 0, use deposit
            if float(buying_power) == 0 and deposit_usd != "N/A":
                buying_power = deposit_usd + " (Est)"
        elif deposit_usd != "N/A":
             buying_power = deposit_usd + " (Est)"

        # --- Display Asset Status ---
        st.markdown("### 💰 Asset Status")
        ac_col1, ac_col2, ac_col3, ac_col4 = st.columns(4)
        ac_col1.metric("Cash (USD)", f"${deposit_usd}")
        ac_col2.metric("Buying Power (USD)", f"${buying_power}")
        ac_col3.metric("Total Profit", f"${total_profit}")
        ac_col4.metric("Total Return", f"{total_return}%")
        
        if not has_stock_balance:
             st.info("Stock balance summary (output2) empty or unavailable. Showing Cash only.")
             if balance:
                with st.expander("Raw Balance Data (Debug)"):
                    st.json(balance)

        # --- Display Holdings ---
        if balance and 'output1' in balance and balance['output1']:
            st.subheader("Current Holdings")
            holdings = balance['output1']
            df_h = pd.DataFrame(holdings)
            
            # Column Mapping
            col_map = {
                'pdno': 'Ticker',
                'prdt_name': 'Name',
                'ccld_qty_smtl1': 'Qty',
                'frcr_pchs_amt1': 'Avg Price',
                'ovrs_now_pric1': 'Cur Price',
                'evlu_pfls_rt': 'Return(%)',
                'evlu_pfls_amt': 'Profit($)'
            }
            
            # Filter & Rename
            valid_cols = [c for c in col_map.keys() if c in df_h.columns]
            df_h = df_h[valid_cols].rename(columns=col_map)
            
            st.dataframe(df_h, hide_index=True)
        else:
            st.info("No stocks currently held (Empty Portfolio).")

    else:
        st.error("API Client not initialized.")

# --- Tab 3: Logs ---
with tab3:
    st.subheader("Recent Trades")
    if parsed_lines:
        trades = []
        for line in parsed_lines:
            msg = line['message']
            if any(k in msg for k in ["Buy Order", "Sell Order", "Selling All", "Stop Loss"]):
                trades.append(line)
        
        if trades:
            st.dataframe(pd.DataFrame(trades)[['timestamp', 'message']], hide_index=True)
        else:
            st.info("No trade events found in logs.")
    
    st.subheader("System Logs")
    if parsed_lines:
        df = pd.DataFrame(parsed_lines)
        st.dataframe(df.iloc[::-1], hide_index=True) # Show newest first

# Auto Refresh logic
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
