# WebSocket Debug - Найдена проблема!

## Проблема
WebSocket соединение работает корректно, но Gate.io возвращает ошибку:

```json
{
  "error": {
    "code": 2,
    "message": "unknown currency pair: wld_usdt"
  }
}
```

## Причина
Пара **WLD_USDT не существует на Gate.io** или называется по-другому.

## Решение

### 1. Проверить доступные пары для WLD
Нужно проверить на Gate.io, какие пары доступны для токена WLD (Worldcoin).

Возможные варианты:
- `WLD_USDT` - НЕ РАБОТАЕТ (unknown currency pair)
- `WLD_USD` - попробовать
- Возможно, WLD торгуется только против других валют

### 2. Как проверить доступные пары

#### Через REST API:
```bash
curl https://api.gateio.ws/api/v4/spot/currency_pairs | grep -i wld
```

#### Или через Python:
```python
import requests

response = requests.get('https://api.gateio.ws/api/v4/spot/currency_pairs')
pairs = response.json()

# Найти все пары с WLD
wld_pairs = [p for p in pairs if 'WLD' in p['id'].upper()]
for pair in wld_pairs:
    print(f"{pair['id']}: {pair['trade_status']}")
```

### 3. Тестирование с BTC_USDT
Для проверки работы WebSocket используйте известную пару BTC_USDT:

```bash
# Подписка
curl -X POST http://localhost:5000/api/pair/subscribe \
  -H "Content-Type: application/json" \
  -d '{"base_currency": "BTC", "quote_currency": "USDT"}'

# Проверка данных через несколько секунд
curl "http://localhost:5000/api/pair/data?base_currency=BTC&quote_currency=USDT"
```

## Следующие шаги

1. **Проверить доступность WLD на Gate.io**
2. **Если WLD есть** - найти правильный символ пары
3. **Если WLD нет** - заменить на другой токен или использовать другую биржу
4. **Протестировать с BTC_USDT** для подтверждения работы WebSocket

## Статус
✅ WebSocket соединение работает  
✅ Подписки отправляются корректно  
✅ Формат пары изменен на нижний регистр (`wld_usdt`)  
❌ Пара WLD_USDT не найдена на Gate.io  
⏳ Требуется проверка доступных пар

Дата: 6 ноября 2025
