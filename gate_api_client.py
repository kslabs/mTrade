"""
Клиент для работы с Gate.io API
Поддержка spot trading, futures и copy trading
"""
import json
import time
import hmac
import hashlib
import requests
class GateAPIClient:
    """Клиент для работы с Gate.io API"""
    def __init__(self, api_key: str, api_secret: str, network_mode: str = 'work'):
        from config import Config
        self.api_key = api_key
        self.api_secret = api_secret
        self.network_mode = network_mode
        # Выбор хоста по режиму
        self.host = Config.API_HOST if network_mode == 'work' else Config.TEST_API_HOST
        self.prefix = Config.API_PREFIX
    def _generate_sign(self, method: str, url: str, query_string: str = '', payload: str = ''):
        """Генерация подписи для API запроса"""
        t = str(int(time.time()))
        m = hashlib.sha512()
        m.update(payload.encode('utf-8'))
        hashed_payload = m.hexdigest()
        s = f"{method}\n{url}\n{query_string}\n{hashed_payload}\n{t}"
        sign = hmac.new(
            self.api_secret.encode('utf-8'),
            s.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        return {
            'KEY': self.api_key,
            'Timestamp': t,
            'SIGN': sign
        }
    def _request(self, method: str, endpoint: str, params: dict = None, data: dict = None):
        """Выполнение API запроса"""
        url = f"{self.prefix}{endpoint}"
        query_string = ''
        payload = ''
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        if data:
            payload = json.dumps(data)
            print(f"[DEBUG] _request: payload = {payload}")
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        # Подпись добавляем только при наличии ключей (публичные эндпойнты работают без подписи)
        if self.api_key and self.api_secret:
            headers.update(self._generate_sign(method, url, query_string, payload))
        full_url = f"{self.host}{url}"
        if query_string:
            full_url += f"?{query_string}"
        
        try:
            response = requests.request(
                method,
                full_url,
                headers=headers,
                data=payload if data else None,
                timeout=15  # ✅ ДОБАВЛЕН ТАЙМАУТ 15 секунд
            )
            
            # Логируем статус ответа
            print(f"[DEBUG] _request: HTTP {response.status_code} для {method} {endpoint}")
            
            # Проверяем статус код
            if response.status_code >= 400:
                print(f"[ERROR] _request: Ошибка API {response.status_code}: {response.text[:500]}")
            
            return response.json()
            
        except requests.Timeout:
            print(f"[ERROR] _request: Таймаут (>15 сек) для {method} {endpoint}")
            return {"error": "timeout", "message": "API request timeout"}
            
        except requests.RequestException as e:
            print(f"[ERROR] _request: Ошибка запроса для {method} {endpoint}: {e}")
            return {"error": "request_failed", "message": str(e)}
            
        except Exception as e:
            print(f"[ERROR] _request: Неожиданная ошибка для {method} {endpoint}: {e}")
            import traceback
            traceback.print_exc()
            return {"error": "unknown", "message": str(e)}
    # -------------------------------------------------------------------------
    # SPOT TRADING (Обычный трейдинг)
    # -------------------------------------------------------------------------
    def get_account_balance(self):
        """Получить баланс спот счета"""
        return self._request('GET', '/spot/accounts')
    def get_ticker(self, currency_pair: str):
        """Получить текущий тикер для торговой пары"""
        return self._request('GET', f'/spot/tickers', params={'currency_pair': currency_pair})
    def get_spot_orderbook(self, currency_pair: str, limit: int = 10):
        """Получить стакан ордеров (order book) для торговой пары
        Args:
            currency_pair: Торговая пара (например, BTC_USDT)
            limit: Количество уровней стакана (по умолчанию 10)
        Returns:
            dict: {'asks': [[price, amount], ...], 'bids': [[price, amount], ...]}
        """
        return self._request('GET', '/spot/order_book', params={
            'currency_pair': currency_pair.upper(),
            'limit': limit
        })
    def create_spot_order(self, currency_pair: str, side: str, amount: str, price: str = None, order_type: str = "limit", time_in_force: str = None):
        """Создать спотовый ордер
        Добавлено: поддержка time_in_force (gtc, fok, ioc)
        Args:
            currency_pair: Пара вида BASE_QUOTE
            side: 'buy' или 'sell'
            amount: Кол-во BASE (строка)
            price: Лимитная цена (для limit)
            order_type: 'limit' или 'market'
            time_in_force: gtc | fok | ioc (для лимитных ордеров)
        """
        order_data = {
            "currency_pair": currency_pair,
            "side": side,
            "amount": amount,
            "type": order_type
        }
        # Устанавливаем account для spot ордеров
        order_data["account"] = "spot"
        # Для лимитных ордеров добавляем цену, time_in_force
        if order_type == "limit":
            if price:
                order_data["price"] = price
            # Валидируем time_in_force
            tif = time_in_force
            if tif:
                order_data["time_in_force"] = tif
        elif order_type == "market":
            # Для market ордеров устанавливаем time_in_force='ioc' чтобы избежать ошибки gtc
            order_data["time_in_force"] = "ioc"
        
        print(f"[DEBUG] create_spot_order: order_data = {order_data}")
        print(f"[DEBUG] create_spot_order: Отправка запроса к API...")
        
        result = self._request('POST', '/spot/orders', data=order_data)
        
        print(f"[DEBUG] create_spot_order: Ответ получен")
        print(f"[DEBUG] create_spot_order: result = {result}")
        
        # Проверяем наличие ошибки в ответе
        if result and isinstance(result, dict):
            if 'error' in result:
                print(f"[ERROR] create_spot_order: API вернул ошибку: {result.get('error')} - {result.get('message')}")
            elif 'id' in result:
                print(f"[SUCCESS] create_spot_order: Ордер создан успешно, ID={result['id']}")
        
        return result
    def get_spot_orders(self, currency_pair: str, status: str = "open"):
        """Получить список ордеров"""
        params = {
            "currency_pair": currency_pair,
            "status": status
        }
        return self._request('GET', '/spot/orders', params=params)
    def get_spot_order(self, order_id: str, currency_pair: str):
        """Получить информацию об ордере по ID"""
        return self._request('GET', f'/spot/orders/{order_id}', params={"currency_pair": currency_pair})
    def cancel_spot_order(self, order_id: str, currency_pair: str):
        """Отменить ордер"""
        return self._request('DELETE', f'/spot/orders/{order_id}', params={"currency_pair": currency_pair})
    def cancel_all_open_orders(self, currency_pair: str):
        """Отменить все открытые ордера для пары"""
        try:
            # Получаем список открытых ордеров
            open_orders = self.get_spot_orders(currency_pair, status="open")
            cancelled = []
            if isinstance(open_orders, list):
                for order in open_orders:
                    try:
                        order_id = order.get('id')
                        if order_id:
                            result = self.cancel_spot_order(order_id, currency_pair)
                            cancelled.append(order_id)
                            print(f"[INFO] Отменён ордер {order_id}")
                    except Exception as e:
                        print(f"[WARNING] Не удалось отменить ордер {order.get('id')}: {e}")
            return {"success": True, "cancelled": cancelled, "count": len(cancelled)}
        except Exception as e:
            print(f"[ERROR] cancel_all_open_orders: {e}")
            return {"success": False, "error": str(e)}
    # -------------------------------------------------------------------------
    # FUTURES TRADING
    # -------------------------------------------------------------------------
    def get_futures_balance(self, settle: str = "usdt"):
        """Получить баланс фьючерсного счета"""
        return self._request('GET', f'/futures/{settle}/accounts')
    def create_futures_order(self, contract: str, size: int, price: str = None, settle: str = "usdt"):
        """Создать фьючерсный ордер"""
        order_data = {
            "contract": contract,
            "size": size,
        }
        if price:
            order_data["price"] = price
        return self._request('POST', f'/futures/{settle}/orders', data=order_data)
    # -------------------------------------------------------------------------
    # COPY TRADING (Копитрейдинг)
    # -------------------------------------------------------------------------
    def get_account_detail(self):
        """Получить детали аккаунта (включая copy_trading_role)"""
        return self._request('GET', '/account/detail')
    def transfer_to_copy_trading(self, currency: str, amount: str, direction: str = "to"):
        """
        Перевод средств в/из копитрейдинг аккаунта
        direction: 'to' - в копитрейдинг, 'from' - из копитрейдинга
        """
        # Для фьючерсного копитрейдинга используем специальные endpoints
        # Примечание: точный endpoint может отличаться, нужно проверить в документации
        transfer_data = {
            "currency": currency,
            "amount": amount,
            "from": "spot" if direction == "to" else "copy_trading",
            "to": "copy_trading" if direction == "to" else "spot"
        }
        return self._request('POST', '/wallet/transfers', data=transfer_data)
    def get_currency_pair_details_exact(self, currency_pair: str):
        """Точный запрос одной пары через endpoint /spot/currency_pairs/{pair}."""
        try:
            ep = f"/spot/currency_pairs/{currency_pair.upper()}"
            return self._request('GET', ep)
        except Exception as e:
            return {"error": str(e)}
    def get_currency_pair_details(self, currency_pair: str):
        """Старый метод (возвращает список)."""
        try:
            params = {"currency_pair": currency_pair.upper()}
            return self._request('GET', '/spot/currency_pairs', params=params)
        except Exception as e:
            return {"error": str(e)}
    # -------------------------------------------------------------------------
    # CURRENCIES INFO (Информация о валютах)
    # -------------------------------------------------------------------------
    def get_currencies(self):
        """
        Получить список всех доступных валют с Gate.io
        Возвращает список валют с детальной информацией
        """
        try:
            return self._request('GET', '/spot/currencies')
        except Exception as e:
            return {"error": str(e)}
    def get_currency_details(self, currency: str):
        """
        Получить детальную информацию о конкретной валюте
        Args:
            currency: код валюты (например, BTC, ETH, USDT)
        """
        try:
            return self._request('GET', f'/spot/currencies/{currency.upper()}')
        except Exception as e:
            return {"error": str(e)}
    def get_currency_pairs(self):
        """
        Получить список всех торговых пар
        Возвращает информацию о доступных торговых парах
        """
        try:
            return self._request('GET', '/spot/currency_pairs')
        except Exception as e:
            return {"error": str(e)}
