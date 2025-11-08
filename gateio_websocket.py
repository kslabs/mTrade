"""
Gate.io WebSocket Module
Модуль для работы с WebSocket Gate.io API
Получение данных стакана и тикеров в реальном времени
"""

import json
import time
import hmac
import hashlib
import threading
import websocket
from datetime import datetime
from typing import Callable, Dict, Any, Optional
import logging
from data_limits import DataLimits

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GateIOWebSocket:
    """WebSocket клиент для Gate.io"""
    
    # WebSocket URLs
    WS_URL_SPOT = "wss://api.gateio.ws/ws/v4/"
    
    def __init__(self, api_key: str = None, api_secret: str = None, ws_url: str = None):
        """
        Инициализация WebSocket клиента
        
        Args:
            api_key: API ключ Gate.io (опционально для публичных данных)
            api_secret: API секрет Gate.io (опционально для публичных данных)
            ws_url: Полный WS URL (для testnet передаем wss://api-testnet.gateio.ws/ws/v4/)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws_url = ws_url or self.WS_URL_SPOT
        self.ws = None
        self.ws_thread = None
        self.ping_thread = None
        self.is_running = False
        self.subscriptions = {}
        self.callbacks = {}
        self.last_data_time = time.time()
        self.error: Optional[str] = None  # текст ошибки подключения
    
    def _sign_message(self, channel: str, event: str, timestamp: int) -> str:
        """
        Подпись сообщения для приватных каналов
        
        Args:
            channel: Название канала
            event: Событие (subscribe/unsubscribe)
            timestamp: Unix timestamp
            
        Returns:
            Подписанное сообщение
        """
        if not self.api_secret:
            return ""
        
        message = f"channel={channel}&event={event}&time={timestamp}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return signature
    
    def _on_message(self, ws, message):
        """Обработчик входящих сообщений"""
        try:
            data = json.loads(message)
            
            # Обработка различных типов сообщений
            if 'event' in data:
                event = data['event']
                
                if event == 'subscribe':
                    logger.info(f"Подписка успешна: {data.get('channel')}")
                    
                elif event == 'unsubscribe':
                    logger.info(f"Отписка успешна: {data.get('channel')}")
                    
                elif event == 'update':
                    channel = data.get('channel', '')
                    result = data.get('result', {})
                    
                    # Обновляем время последних данных
                    self.last_data_time = time.time()
                    
                    # Вызов callback для этого канала
                    if channel in self.callbacks:
                        self.callbacks[channel](result)
                        
            # Обработка ping-pong
            elif 'ping' in data:
                pong_message = json.dumps({"pong": data['ping']})
                ws.send(pong_message)
                logger.debug(f"Pong отправлен: {data['ping']}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}")
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
    
    def _ping_loop(self):
        """Поток для отправки ping каждые 20 секунд (если нет данных в течение 15 сек)"""
        while self.is_running:
            try:
                time.sleep(5)  # Проверяем каждые 5 секунд
                
                if not self.is_running:
                    break
                
                # Если данных не было более 15 секунд, отправляем ping
                time_since_last_data = time.time() - self.last_data_time
                
                if time_since_last_data > 15 and self.ws:
                    ping_message = json.dumps({"time": int(time.time()), "channel": "spot.ping"})
                    self.ws.send(ping_message)
                    logger.debug(f"Ping отправлен (нет данных {time_since_last_data:.1f} сек)")
                    
            except Exception as e:
                logger.error(f"Ошибка в ping loop: {e}")
    
    def _on_error(self, ws, error):
        """Обработчик ошибок"""
        logger.error(f"WebSocket ошибка: {error}")
        self.error = str(error)

    def _on_close(self, ws, close_status_code, close_msg):
        """Обработчик закрытия соединения"""
        logger.info(f"WebSocket соединение закрыто: {close_status_code} - {close_msg}")
        self.is_running = False
        if close_status_code or close_msg:
            self.error = f"closed {close_status_code} {close_msg}".strip()

    def _on_open(self, ws):
        """Обработчик открытия соединения"""
        logger.info("WebSocket соединение установлено")
        self.is_running = True
        self.error = None
        
        # Восстановление подписок после переподключения
        for channel, payload in self.subscriptions.items():
            ws.send(json.dumps(payload))
    
    def connect(self):
        """Установить WebSocket соединение (с защитой от исключений)"""
        if self.ws and self.is_running:
            logger.warning("WebSocket уже подключен")
            return
        try:
            websocket.enableTrace(False)
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            self.ws_thread.start()
            self.ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
            self.ping_thread.start()
            time.sleep(1)
        except Exception as e:
            self.error = f"connect exception: {e}"
            logging.error(f"WS connect failed: {e}")

    def status(self) -> Dict[str, Any]:
        """Краткий статус соединения"""
        return {
            'running': self.is_running,
            'error': self.error,
            'url': self.ws_url,
            'subs': list(self.subscriptions.keys()),
            'last_data_age': round(time.time() - self.last_data_time, 2)
        }

    def disconnect(self):
        """Закрыть WebSocket соединение"""
        if self.ws:
            self.is_running = False
            self.ws.close()
            if self.ws_thread:
                self.ws_thread.join(timeout=2)
            if self.ping_thread:
                self.ping_thread.join(timeout=2)
            logger.info("WebSocket отключен")
    
    def subscribe_ticker(self, currency_pair: str, callback: Callable):
        """
        Подписаться на тикер (цена, объем)
        
        Args:
            currency_pair: Торговая пара (например, BTC_USDT)
            callback: Функция обратного вызова для обработки данных
        """
        # Gate.io WebSocket требует ЗАГЛАВНЫЕ буквы для пар
        # Конвертируем в верхний регистр для гарантии правильного формата
        pair_formatted = currency_pair.upper()
        
        channel = "spot.tickers"
        payload = {
            "time": int(time.time()),
            "channel": channel,
            "event": "subscribe",
            "payload": [pair_formatted]
        }
        
        self.subscriptions[f"{channel}_{pair_formatted}"] = payload
        self.callbacks[channel] = callback
        
        if self.ws and self.is_running:
            self.ws.send(json.dumps(payload))
            logger.info(f"Подписка на тикер: {pair_formatted}")
    
    def subscribe_orderbook(self, currency_pair: str, level: str, interval: str, callback: Callable):
        """
        Подписаться на стакан ордеров
        
        Args:
            currency_pair: Торговая пара (например, BTC_USDT)
            level: Уровень глубины ("5", "10", "20", "50", "100")
            interval: Интервал обновления ("100ms", "1000ms") 
            callback: Функция обратного вызова для обработки данных
        """
        # Gate.io WebSocket требует ЗАГЛАВНЫЕ буквы для пар
        pair_formatted = currency_pair.upper()
        
        # Используем spot.order_book (snapshot) вместо spot.order_book_update
        # так как update требует инкрементальную обработку
        channel = "spot.order_book"
        payload = {
            "time": int(time.time()),
            "channel": channel,
            "event": "subscribe",
            "payload": [pair_formatted, level, interval]  # пара, глубина, интервал
        }
        
        self.subscriptions[f"{channel}_{pair_formatted}"] = payload
        self.callbacks[channel] = callback
        
        if self.ws and self.is_running:
            self.ws.send(json.dumps(payload))
            logger.info(f"Подписка на стакан: {pair_formatted} (level={level}, interval={interval})")
    
    def subscribe_trades(self, currency_pair: str, callback: Callable):
        """
        Подписаться на последние сделки
        
        Args:
            currency_pair: Торговая пара (например, BTC_USDT)
            callback: Функция обратного вызова для обработки данных
        """
        # Gate.io WebSocket требует ЗАГЛАВНЫЕ буквы для пар
        pair_formatted = currency_pair.upper()
        
        channel = "spot.trades"
        payload = {
            "time": int(time.time()),
            "channel": channel,
            "event": "subscribe",
            "payload": [pair_formatted]
        }
        
        self.subscriptions[f"{channel}_{pair_formatted}"] = payload
        self.callbacks[channel] = callback
        
        if self.ws and self.is_running:
            self.ws.send(json.dumps(payload))
            logger.info(f"Подписка на сделки: {pair_formatted}")
    
    def unsubscribe(self, channel: str, currency_pair: str):
        """
        Отписаться от канала
        
        Args:
            channel: Название канала
            currency_pair: Торговая пара
        """
        # Gate.io WebSocket требует ЗАГЛАВНЫЕ буквы для пар
        pair_formatted = currency_pair.upper()
        
        payload = {
            "time": int(time.time()),
            "channel": channel,
            "event": "unsubscribe",
            "payload": [pair_formatted]
        }
        
        subscription_key = f"{channel}_{pair_formatted}"
        if subscription_key in self.subscriptions:
            del self.subscriptions[subscription_key]
        
        if self.ws and self.is_running:
            self.ws.send(json.dumps(payload))
            logger.info(f"Отписка от канала: {channel} - {pair_formatted}")


class PairWebSocketManager:
    """Менеджер WebSocket соединений для торговых пар"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, ws_url: str = None):
        """
        Инициализация менеджера
        
        Args:
            api_key: API ключ Gate.io
            api_secret: API секрет Gate.io
            ws_url: Полный WS URL (work|test)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws_url = ws_url or GateIOWebSocket.WS_URL_SPOT
        self.connections: Dict[str, GateIOWebSocket] = {}
        self.data_cache: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.last_cleanup_time = time.time()
        self._created_at = time.time()
        
        # Запуск автоматической очистки
        self._start_cleanup_thread()
    
    def status(self) -> Dict[str, Any]:
        with self.lock:
            return {
                'ws_url': self.ws_url,
                'created_at': self._created_at,
                'connections': {pair: client.status() for pair, client in self.connections.items()},
                'cache_pairs': list(self.data_cache.keys())
            }
    
    def create_connection(self, currency_pair: str) -> GateIOWebSocket:
        """
        Создать WebSocket соединение для пары
        
        Args:
            currency_pair: Торговая пара (например, BTC_USDT или btc_usdt)
            
        Returns:
            WebSocket клиент
        """
        # Нормализуем формат пары в заглавные буквы с подчеркиванием
        pair_formatted = currency_pair.upper()
        
        with self.lock:
            if pair_formatted in self.connections:
                logger.warning(f"Соединение для {pair_formatted} уже существует")
                return self.connections[pair_formatted]
            
            ws_client = GateIOWebSocket(self.api_key, self.api_secret, self.ws_url)
            ws_client.connect()
            
            # Инициализация кэша данных для пары
            self.data_cache[pair_formatted] = {
                'ticker': {},
                'orderbook': {'asks': [], 'bids': []},
                'trades': [],
                'last_update': None
            }
            
            # Подписка на тикер
            def ticker_callback(data):
                with self.lock:
                    # Gate.io возвращает данные напрямую, а не в массиве
                    if isinstance(data, dict) and 'currency_pair' in data:
                        self.data_cache[pair_formatted]['ticker'] = data
                        self.data_cache[pair_formatted]['last_update'] = datetime.now().isoformat()
                        logger.debug(f"Тикер обновлен для {pair_formatted}: {data.get('last')}")
            
            # Подписка на стакан
            def orderbook_callback(data):
                with self.lock:
                    if isinstance(data, dict):
                        # Проверяем разные форматы ответа Gate.io
                        if 'asks' in data and 'bids' in data:
                            # Применяем ограничение размера
                            limited_orderbook = self._limit_orderbook_size({
                                'asks': data['asks'],
                                'bids': data['bids']
                            })
                            self.data_cache[pair_formatted]['orderbook'] = limited_orderbook
                            self.data_cache[pair_formatted]['last_update'] = datetime.now().isoformat()
                            logger.debug(f"Стакан обновлен для {pair_formatted}: {len(limited_orderbook['asks'])} asks, {len(limited_orderbook['bids'])} bids")
            
            # Подписка на сделки
            def trades_callback(data):
                with self.lock:
                    # Gate.io возвращает данные в разных форматах
                    if isinstance(data, dict):
                        # Одна сделка
                        if 'id' in data:
                            self.data_cache[pair_formatted]['trades'].insert(0, data)
                            # Ограничиваем размер истории
                            self.data_cache[pair_formatted]['trades'] = self.data_cache[pair_formatted]['trades'][:DataLimits.MAX_TRADES_HISTORY]
                            self.data_cache[pair_formatted]['last_update'] = datetime.now().isoformat()
                            logger.debug(f"Сделка добавлена для {pair_formatted}: {data.get('price')}")
                    elif isinstance(data, list):
                        # Список сделок - ограничиваем размер
                        self.data_cache[pair_formatted]['trades'] = data[:DataLimits.MAX_TRADES_HISTORY]
                        self.data_cache[pair_formatted]['last_update'] = datetime.now().isoformat()
                        logger.debug(f"Сделки обновлены для {pair_formatted}: {len(data)} сделок")
            
            ws_client.subscribe_ticker(pair_formatted, ticker_callback)
            ws_client.subscribe_orderbook(pair_formatted, "20", "100ms", orderbook_callback)
            ws_client.subscribe_trades(pair_formatted, trades_callback)
            
            self.connections[pair_formatted] = ws_client
            logger.info(f"WebSocket соединение создано для {pair_formatted}")
            
            return ws_client
    
    def close_connection(self, currency_pair: str):
        """
        Закрыть WebSocket соединение для пары
        
        Args:
            currency_pair: Торговая пара
        """
        pair_formatted = currency_pair.upper()
        
        with self.lock:
            if pair_formatted in self.connections:
                self.connections[pair_formatted].disconnect()
                del self.connections[pair_formatted]
                logger.info(f"WebSocket соединение закрыто для {pair_formatted}")
    
    def get_data(self, currency_pair: str) -> Optional[Dict[str, Any]]:
        """
        Получить данные для торговой пары
        
        Args:
            currency_pair: Торговая пара
            
        Returns:
            Словарь с данными тикера, стакана и сделок
        """
        pair_formatted = currency_pair.upper()
        
        with self.lock:
            return self.data_cache.get(pair_formatted, None)
    
    def close_all(self):
        """Закрыть все WebSocket соединения"""
        with self.lock:
            for currency_pair in list(self.connections.keys()):
                self.connections[currency_pair].disconnect()
            self.connections.clear()
            logger.info("Все WebSocket соединения закрыты")
    
    def _start_cleanup_thread(self):
        """Запуск потока автоматической очистки"""
        def cleanup_worker():
            while True:
                time.sleep(DataLimits.CLEANUP_INTERVAL_SECONDS)
                self._cleanup_old_cache()
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Поток автоматической очистки кэша запущен")
    
    def _cleanup_old_cache(self):
        """Очистка старого кэша"""
        with self.lock:
            current_time = time.time()
            pairs_to_remove = []
            
            # Находим пары для удаления
            for pair, data in self.data_cache.items():
                if 'last_update' in data and data['last_update']:
                    try:
                        last_update = datetime.fromisoformat(data['last_update'])
                        age_seconds = (datetime.now() - last_update).total_seconds()
                        
                        # Удаляем старые данные
                        if age_seconds > DataLimits.CACHE_TTL_SECONDS:
                            pairs_to_remove.append(pair)
                    except:
                        pass
            
            # Проверяем лимит количества пар
            if len(self.data_cache) > DataLimits.MAX_CURRENCY_PAIRS_CACHE:
                # Сортируем пары по времени последнего обновления
                sorted_pairs = sorted(
                    self.data_cache.items(),
                    key=lambda x: x[1].get('last_update', ''),
                    reverse=False
                )
                
                # Оставляем только N самых свежих
                excess_count = len(self.data_cache) - DataLimits.MAX_CURRENCY_PAIRS_CACHE
                for pair, _ in sorted_pairs[:excess_count]:
                    if pair not in pairs_to_remove:
                        pairs_to_remove.append(pair)
            
            # Удаляем неактивные пары
            for pair in pairs_to_remove:
                if len(self.data_cache) > DataLimits.MIN_PAIRS_TO_KEEP:
                    if pair in self.connections:
                        self.connections[pair].disconnect()
                        del self.connections[pair]
                    if pair in self.data_cache:
                        del self.data_cache[pair]
                    logger.info(f"Удалена неактивная пара из кэша: {pair}")
            
            if pairs_to_remove:
                logger.info(f"Очистка кэша: удалено {len(pairs_to_remove)} пар")
    
    def _limit_orderbook_size(self, orderbook: dict) -> dict:
        """Ограничение размера стакана"""
        if 'asks' in orderbook:
            orderbook['asks'] = orderbook['asks'][:DataLimits.MAX_ORDERBOOK_LEVELS]
        if 'bids' in orderbook:
            orderbook['bids'] = orderbook['bids'][:DataLimits.MAX_ORDERBOOK_LEVELS]
        return orderbook


# Глобальный менеджер (будет инициализирован в main приложении)
ws_manager: Optional[PairWebSocketManager] = None


def init_websocket_manager(api_key: str, api_secret: str, network_mode: str = 'work') -> PairWebSocketManager:
    """
    Инициализировать глобальный WebSocket менеджер с учетом сети
    
    Args:
        api_key: API ключ Gate.io
        api_secret: API секрет Gate.io
        network_mode: Режим сети ('work' или 'test')
        
    Returns:
        Экземпляр PairWebSocketManager
    """
    global ws_manager
    ws_url = "wss://api.gateio.ws/ws/v4/" if network_mode == 'work' else "wss://api-testnet.gateio.ws/ws/v4/"
    ws_manager = PairWebSocketManager(api_key, api_secret, ws_url)
    return ws_manager


def get_websocket_manager() -> Optional[PairWebSocketManager]:
    """
    Получить глобальный WebSocket менеджер
    
    Returns:
        Экземпляр PairWebSocketManager или None
    """
    return ws_manager
