import logging
import os
from datetime import datetime

# Ensure database directory exists for logs
if not os.path.exists('database'):
    os.makedirs('database')

def setup_logger():
    logger = logging.getLogger("US_ETF_Sniper")
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File Handler
    file_handler = logging.FileHandler(f"database/trading_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()
