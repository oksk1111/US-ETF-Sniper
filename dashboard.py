import streamlit as st
import pandas as pd
import os
import glob
import re
import time

st.set_page_config(
    page_title="US-ETF-Sniper Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 US-ETF-Sniper Dashboard")

# --- Sidebar ---
st.sidebar.header("Settings")
refresh_rate = st.sidebar.slider("Refresh Rate (sec)", 1, 60, 5)
auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)

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

log_file = get_latest_log_file()

if not log_file:
    st.warning("No log files found in `database/`. Is the bot running?")
else:
    st.info(f"Reading log file: `{log_file}`")
    
    lines = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Fallback to system encoding (cp949/euc-kr)
        with open(log_file, "r", encoding="cp949") as f:
            lines = f.readlines()
        
    parsed_lines = [parse_log_line(line) for line in lines]
    parsed_lines = [x for x in parsed_lines if x is not None]
    
    if not parsed_lines:
        st.warning("Log file is empty or invalid format.")
    else:
        df = pd.DataFrame(parsed_lines)
        
        # 1. Status
        last_log = parsed_lines[-1]
        status = get_bot_status(last_log['timestamp'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Bot Status", status)
        with col2:
            st.metric("Last Update", last_log['timestamp'])
        with col3:
            st.metric("Total Logs", len(parsed_lines))
            
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
        
        st.markdown("### 📊 Market Data")
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Current Price", f"${current_price}")
        m_col2.metric("Target Price", f"${target_price}")
        m_col3.metric("20 MA", f"${ma20}")

        # 3. Recent Logs
        st.markdown("### 📜 Recent Logs")
        st.dataframe(df.iloc[::-1], width=1000) # Show newest first

# Auto Refresh
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
