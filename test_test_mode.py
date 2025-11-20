import requests

response = requests.get('http://localhost:5000/api/pair/data?base_currency=BTC&quote_currency=USDT')
data = response.json()

print(f"Success: {data.get('success')}")
print(f"Network mode: TEST")

if 'data' in data:
    d = data['data']
    ob = d.get('orderbook', {})
    print(f"\nAsk count: {len(ob.get('asks', []))}")
    print(f"Bids count: {len(ob.get('bids', []))}")
    
    if ob.get('asks'):
        print(f"\nFirst 3 asks:")
        for ask in ob['asks'][:3]:
            print(f"  {ask}")
    else:
        print("\nNO ASKS!")
    
    if ob.get('bids'):
        print(f"\nFirst 3 bids:")
        for bid in ob['bids'][:3]:
            print(f"  {bid}")
    else:
        print("\nNO BIDS!")
