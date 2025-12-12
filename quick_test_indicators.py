import requests

r = requests.get('http://localhost:5000/api/trade/indicators?base_currency=WLD&quote_currency=USDT&include_table=1')
d = r.json()
t = d.get('autotrade_levels', {}).get('table', [])

print(f'Таблица: {len(t)} строк')
if t:
    row0 = t[0]
    print(f'Первая строка keys: {list(row0.keys())}')
    print(f'total_invested: {row0.get("total_invested", "НЕТ")}')
    print(f'breakeven_pct: {row0.get("breakeven_pct", "НЕТ")}')
    print(f'orderbook_level: {row0.get("orderbook_level", "НЕТ")}')
else:
    print('Таблица пустая!')
