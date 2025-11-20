"""
Тестовый скрипт для проверки WebSocket Gate.io
Проверяет, приходят ли данные для пары WLD_USDT
"""

import websocket
import json
import time
import threading

def on_message(ws, message):
    """Обработчик сообщений"""
    print(f"\n{'='*60}")
    print(f"Получено сообщение:")
    print(f"{'='*60}")
    try:
        data = json.loads(message)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(message)
    print(f"{'='*60}\n")

def on_error(ws, error):
    """Обработчик ошибок"""
    print(f"❌ Ошибка: {error}")

def on_close(ws, close_status_code, close_msg):
    """Обработчик закрытия"""
    print(f"🔴 Соединение закрыто: {close_status_code} - {close_msg}")

def on_open(ws):
    """Обработчик открытия соединения"""
    print("✅ WebSocket соединение установлено!")
    
    # Подписка на тикер
    ticker_sub = {
        "time": int(time.time()),
        "channel": "spot.tickers",
        "event": "subscribe",
        "payload": ["WLD_USDT"]
    }
    print(f"\n📤 Отправка подписки на тикер: {json.dumps(ticker_sub)}")
    ws.send(json.dumps(ticker_sub))
    
    # Подписка на стакан
    orderbook_sub = {
        "time": int(time.time()),
        "channel": "spot.order_book_update",
        "event": "subscribe",
        "payload": ["WLD_USDT", "20", "100ms"]
    }
    print(f"📤 Отправка подписки на стакан: {json.dumps(orderbook_sub)}")
    ws.send(json.dumps(orderbook_sub))
    
    # Подписка на сделки
    trades_sub = {
        "time": int(time.time()),
        "channel": "spot.trades",
        "event": "subscribe",
        "payload": ["WLD_USDT"]
    }
    print(f"📤 Отправка подписки на сделки: {json.dumps(trades_sub)}\n")
    ws.send(json.dumps(trades_sub))

def on_pong(ws, data):
    """Обработчик pong"""
    print(f"🏓 Pong получен: {data}")

if __name__ == "__main__":
    print("🚀 Запуск тестового WebSocket клиента для Gate.io")
    print("📊 Тестируемая пара: WLD_USDT")
    print(f"🔗 URL: wss://api.gateio.ws/ws/v4/")
    print("⏱️  Ожидание данных в течение 30 секунд...\n")
    
    # Включаем отладку
    websocket.enableTrace(True)
    
    # Создаем WebSocket
    ws = websocket.WebSocketApp(
        "wss://api.gateio.ws/ws/v4/",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
        on_pong=on_pong
    )
    
    # Запускаем в отдельном потоке
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()
    
    # Ждем 30 секунд
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        print("\n⏹️  Прервано пользователем")
    
    # Закрываем соединение
    ws.close()
    print("\n✅ Тест завершен")
