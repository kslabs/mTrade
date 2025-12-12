"""Utility to collect SOL-related logs from workspace log files and produce a small summary file.

Usage: run from repo root: python scripts/collect_sol_logs.py
It will create ./tests/tmp_logs/sol_logs_summary.json and print a short summary.
"""
import os
import json
import glob


ROOT = os.path.dirname(os.path.dirname(__file__))
LOG_FILE = os.path.join(ROOT, 'system_trader.log')
TRADE_LOG_DIR = os.path.join(ROOT, 'trade_logs')
OUT_DIR = os.path.join(ROOT, 'tests', 'tmp_logs')


def collect_from_system_log():
    if not os.path.exists(LOG_FILE):
        return []
    res = []
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            if 'SOL' in line and ('SELL' in line or 'Sell-DIAG' in line or 'SELL-DIAG' in line):
                res.append({'source': 'system_trader.log', 'line_no': i+1, 'text': line.rstrip('\n')})
    return res


def collect_from_trade_logs():
    res = []
    if not os.path.exists(TRADE_LOG_DIR):
        return res

    for path in glob.glob(os.path.join(TRADE_LOG_DIR, 'EXPORT_SOL*.jsonl')) + glob.glob(os.path.join(TRADE_LOG_DIR, 'SOL_logs.jsonl')):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    # pick buy/sell events
                    if obj.get('currency', '').upper() == 'SOL':
                        res.append({'source': os.path.basename(path), 'line_no': i+1, 'entry': obj})
        except Exception:
            continue

    return res


def main():
    entries = []
    entries.extend(collect_from_system_log())
    entries.extend(collect_from_trade_logs())

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'sol_logs_summary.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(entries)} SOL-related entries to {out_path}")
    for e in entries:
        if 'text' in e:
            print(e['text'])
        else:
            print(e['source'], e['entry'].get('type'), e['entry'].get('time'), e['entry'].get('price'))


if __name__ == '__main__':
    main()
