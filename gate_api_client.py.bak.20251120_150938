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
        
        response = requests.request(
            method,
            full_url,
            headers=headers,
            data=payload if data else None
        )
        
        return response.json()
    
    # -------------------------------------------------------------------------
    # SPOT TRADING (Обычный трейдинг)
    # -------------------------------------------------------------------------
    
    def get_account_balance(self):
        """Получить баланс спот счета"""
        return self._request('GET', '/spot/accounts')
    
    def create_spot_order(self, currency_pair: str, side: str, amount: str, price: str = None, order_type: str = "limit"):
        """Создать спотовый ордер"""
        order_data = {
            "currency_pair": currency_pair,
            "side": side,  # buy или sell
            "amount": amount,
            "type": order_type  # limit или market
        }
        
        if price and order_type == "limit":
            order_data["price"] = price
        
        return self._request('POST', '/spot/orders', data=order_data)
    
    def get_spot_orders(self, currency_pair: str, status: str = "open"):
        """Получить список ордеров"""
        params = {
            "currency_pair": currency_pair,
            "status": status
        }
        return self._request('GET', '/spot/orders', params=params)
    
    def cancel_spot_order(self, order_id: str, currency_pair: str):
        """Отменить ордер"""
        return self._request('DELETE', f'/spot/orders/{order_id}', params={"currency_pair": currency_pair})
    
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
