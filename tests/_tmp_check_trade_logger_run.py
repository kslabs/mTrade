import sys
import os
# Ensure repo root is on sys.path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from trade_logger import get_trade_logger
l=get_trade_logger()
print('--- Simulating log_buy ---')
l.log_buy('ETH', 0.0037, 2719.58, 0.00, 0.00, 10.0592)
print('--- Simulating log_sell ---')
l.log_sell('ETH', 0.0037, 2719.99, 0.05, 0.0047)
print('--- Done ---')
