import json
from pathlib import Path
p = Path('trade_logs/SOL_logs.jsonl')
if not p.exists():
    print('NO_FILE')
    raise SystemExit(1)

buys_vol = 0.0
sells_vol = 0.0
buy_invest_sum = 0.0
last_price = None
last_entry = None
lines = list(p.read_text(encoding='utf-8').strip().splitlines())
for i,l in enumerate(lines):
    try:
        obj = json.loads(l)
    except Exception:
        continue
    last_entry = obj
    t = obj.get('type')
    vol = float(obj.get('volume',0) or 0)
    price = float(obj.get('price',0) or 0)
    invest = float(obj.get('investment',0) or 0)
    if t == 'buy':
        buys_vol += vol
        buy_invest_sum += invest
    elif t == 'sell':
        sells_vol += vol
    last_price = price if price else last_price

net = buys_vol - sells_vol
print(f"lines={len(lines)}")
print(f"buys_vol={buys_vol:.8f}")
print(f"sells_vol={sells_vol:.8f}")
print(f"net_base={net:.8f}")
print(f"buy_invest_sum_total={buy_invest_sum:.8f}")
if last_entry:
    print('last_entry_time', last_entry.get('time'), 'last_price', last_price)

# detect suspicious buys where volume > 1 or volume approx equals price
suspicious = []
for l in lines:
    try:
        o = json.loads(l)
    except Exception:
        continue
    if o.get('type')=='buy':
        vol = float(o.get('volume',0) or 0)
        price = float(o.get('price',0) or 0)
        if vol > 1 or abs(vol-price) < 1e-6:
            suspicious.append((o.get('time'), vol, price, o.get('investment')))

print('\nSuspicious buys (time, volume, price, investment) count=', len(suspicious))
for s in suspicious[-20:]:
    print(s)

# compute last total_invested field from last buy/sell
last_total_invested = None
for l in reversed(lines):
    try:
        o = json.loads(l)
    except Exception:
        continue
    if 'total_invested' in o:
        last_total_invested = o.get('total_invested')
        break
print('\nlast_total_invested_field=', last_total_invested)

# compute net base by iterating and tracking cumulative base (buys add vol, sells subtract vol)
cum = 0.0
for l in lines:
    try:
        o = json.loads(l)
    except Exception:
        continue
    if o.get('type')=='buy':
        cum += float(o.get('volume',0) or 0)
    elif o.get('type')=='sell':
        cum -= float(o.get('volume',0) or 0)
print('cum_by_iter=', cum)

# print last 10 lines
print('\nLast 10 log lines:')
for l in lines[-10:]:
    print(l)
