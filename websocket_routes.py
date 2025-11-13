"""
WebSocket Routes Module
Содержит эндпоинты для работы с WebSocket соединениями и multi-pairs watcher
"""

import time
from flask import request, jsonify
from threading import Thread
from typing import List, Set, Dict

from config import Config
from gate_api_client import GateAPIClient
from gateio_websocket import get_websocket_manager
from trading_engine import AccountManager


class WebSocketRoutes:
    """Класс для управления WebSocket маршрутами"""
    
    def __init__(self, app, account_manager, current_network_mode_getter):
        """
        Инициализация WebSocket Routes
        
        Args:
            app: Flask приложение
            account_manager: Менеджер аккаунтов
            current_network_mode_getter: Функция для получения текущего режима сети
        """
        self.app = app
        self.account_manager = account_manager
        self.get_current_network_mode = current_network_mode_getter
        
        # Multi-pairs watcher переменные
        self.watched_pairs: Set[str] = set()
        self.multi_pairs_cache: Dict = {}
        self.pair_info_cache: Dict = {}
        self.pair_info_cache_ttl: int = 3600  # 1 час
        
        # Регистрация всех маршрутов
        self._register_routes()
        
        # Запуск фонового потока обновления пар
        self._start_pairs_updater()
    
    def _register_routes(self):
        """Регистрация всех WebSocket маршрутов"""
        # Pair subscription
        self.app.add_url_rule('/api/pair/subscribe', 'subscribe_pair', self.subscribe_pair, methods=['POST'])
        self.app.add_url_rule('/api/pair/data', 'get_pair_data', self.get_pair_data, methods=['GET'])
        self.app.add_url_rule('/api/pair/unsubscribe', 'unsubscribe_pair', self.unsubscribe_pair, methods=['POST'])
        self.app.add_url_rule('/api/pair/balances', 'get_pair_balances', self.get_pair_balances, methods=['GET'])
        self.app.add_url_rule('/api/pair/info', 'get_pair_info', self.get_pair_info, methods=['GET'])
        
        # Multi-pairs watcher
        self.app.add_url_rule('/api/pairs/watchlist', 'api_get_watchlist', self.api_get_watchlist, methods=['GET'])
        self.app.add_url_rule('/api/pairs/watch', 'api_watch_pairs', self.api_watch_pairs, methods=['POST'])
        self.app.add_url_rule('/api/pairs/unwatch', 'api_unwatch_pairs', self.api_unwatch_pairs, methods=['POST'])
        self.app.add_url_rule('/api/pairs/data', 'api_get_pairs_data', self.api_get_pairs_data, methods=['GET'])
    
    # =============================================================================
    # PAIR SUBSCRIPTION
    # =============================================================================
    
    def subscribe_pair(self):
        """Подписаться на данные торговой пары через WebSocket"""
        try:
            data = request.json
            base_currency = data.get('base_currency', 'BTC')
            quote_currency = data.get('quote_currency', 'USDT')
            currency_pair = f"{base_currency}_{quote_currency}"
            
            ws_manager = get_websocket_manager()
            # Ленивая инициализация менеджера даже без ключей (публичный режим)
            if not ws_manager:
                from gateio_websocket import init_websocket_manager
                current_network_mode = self.get_current_network_mode()
                ak, sk = Config.load_secrets_by_mode(current_network_mode)
                init_websocket_manager(ak, sk, current_network_mode)
                ws_manager = get_websocket_manager()
                self._init_default_watchlist()
                print(f"[WEBSOCKET] Lazy init manager (mode={current_network_mode}, keys={'yes' if ak and sk else 'no'})")
            
            if not ws_manager:
                return jsonify({"success": False, "error": "WebSocket менеджер не инициализирован"})
            
            ws_manager.create_connection(currency_pair)
            return jsonify({"success": True, "pair": currency_pair, "message": f"Подписка на {currency_pair} создана"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    def get_pair_data(self):
        """Получить данные торговой пары из WebSocket кэша, с REST fallback"""
        try:
            base_currency = request.args.get('base_currency', 'BTC')
            quote_currency = request.args.get('quote_currency', 'USDT')
            force_refresh = request.args.get('force', '0') == '1'
            currency_pair = f"{base_currency}_{quote_currency}"
            
            ws_manager = get_websocket_manager()
            data = None
            
            if ws_manager:
                data = ws_manager.get_data(currency_pair)
                # Если force=1 или данных нет, создаём новое соединение
                if data is None or force_refresh:
                    print(f"[PAIR_DATA] Creating/refreshing connection for {currency_pair} (force={force_refresh})")
                    ws_manager.create_connection(currency_pair)
                    # Ждём немного, чтобы получить первые данные
                    time.sleep(0.5)
                    data = ws_manager.get_data(currency_pair)
            
            if not data:
                # REST fallback: используем основной API даже в тестовом режиме для рыночных данных
                current_network_mode = self.get_current_network_mode()
                api_key, api_secret = Config.load_secrets_by_mode(current_network_mode)
                # Для публичных данных используем 'work' режим (основной API)
                market_data_client = GateAPIClient(api_key, api_secret, 'work')
                try:
                    # Запрос реальных рыночных данных из основного API
                    ob = market_data_client._request('GET', '/spot/order_book', params={'currency_pair': currency_pair.upper(), 'limit': 20})
                    ticker = market_data_client._request('GET', '/spot/tickers', params={'currency_pair': currency_pair.upper()})
                    
                    data = {
                        'ticker': ticker[0] if isinstance(ticker, list) and ticker else {},
                        'orderbook': {'asks': ob.get('asks', []), 'bids': ob.get('bids', [])} if isinstance(ob, dict) else ob,
                        'trades': []
                    }
                    
                    print(f"[PAIR_DATA] Loaded real market data for {currency_pair} (mode={current_network_mode}, asks={len(data['orderbook'].get('asks',[]))}, bids={len(data['orderbook'].get('bids',[]))})")
                except Exception as rest_err:
                    print(f"[ERROR] Failed to load real market data for {currency_pair}: {rest_err}")
                    return jsonify({'success': False, 'error': f'Не удалось загрузить данные рынка: {str(rest_err)}'})
            
            return jsonify({'success': True, 'pair': currency_pair, 'data': data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    def unsubscribe_pair(self):
        """Отписаться от данных торговой пары"""
        try:
            data = request.json
            base_currency = data.get('base_currency', 'BTC')
            quote_currency = data.get('quote_currency', 'USDT')
            currency_pair = f"{base_currency}_{quote_currency}"
            
            ws_manager = get_websocket_manager()
            if not ws_manager:
                return jsonify({"success": False, "error": "WebSocket менеджер не инициализирован"})
            
            # Закрыть соединение для пары
            ws_manager.close_connection(currency_pair)
            
            return jsonify({
                "success": True,
                "pair": currency_pair,
                "message": f"Отписка от {currency_pair} выполнена"
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    def get_pair_balances(self):
        """Получить балансы для конкретной торговой пары (с поддержкой симуляции в test)"""
        try:
            base_currency = request.args.get('base_currency', 'BTC')
            quote_currency = request.args.get('quote_currency', 'USDT')
            current_network_mode = self.get_current_network_mode()
            
            api_key = None
            api_secret = None
            if self.account_manager.active_account:
                account = self.account_manager.get_account(self.account_manager.active_account)
                api_key = account['api_key']
                api_secret = account['api_secret']
            else:
                api_key, api_secret = Config.load_secrets_by_mode(current_network_mode)
            
            no_keys = (not api_key or not api_secret)
            client = None
            balance_response = []
            
            if not no_keys:
                client = GateAPIClient(api_key, api_secret, current_network_mode)
                try:
                    balance_response = client.get_account_balance()
                except Exception:
                    balance_response = []
            
            base_balance = {"currency": base_currency, "available": "0", "locked": "0"}
            quote_balance = {"currency": quote_currency, "available": "0", "locked": "0"}
            
            if isinstance(balance_response, list):
                for item in balance_response:
                    cur = item.get('currency', '').upper()
                    if cur == base_currency.upper():
                        base_balance = {"currency": base_currency, "available": item.get('available', '0'), "locked": item.get('locked', '0')}
                    elif cur == quote_currency.upper():
                        quote_balance = {"currency": quote_currency, "available": item.get('available', '0'), "locked": item.get('locked', '0')}
            
            ws_manager = get_websocket_manager()
            current_price = 0
            if ws_manager:
                pair_data = ws_manager.get_data(f"{base_currency}_{quote_currency}")
                if pair_data and pair_data.get('ticker') and pair_data['ticker'].get('last'):
                    try:
                        current_price = float(pair_data['ticker']['last'])
                    except Exception:
                        current_price = 0
            
            try:
                base_available = float(base_balance['available'])
            except Exception:
                base_available = 0.0
            base_equivalent = base_available * current_price if current_price > 0 else 0
            
            try:
                quote_available = float(quote_balance['available'])
            except Exception:
                quote_available = 0.0
            quote_equivalent = quote_available
            
            if quote_currency.upper() != 'USDT' and ws_manager:
                usdt_data = ws_manager.get_data(f"{quote_currency}_USDT")
                if usdt_data and usdt_data.get('ticker') and usdt_data['ticker'].get('last'):
                    try:
                        quote_equivalent = quote_available * float(usdt_data['ticker']['last'])
                    except Exception:
                        pass
            
            return jsonify({
                "success": True,
                "balances": {"base": base_balance, "quote": quote_balance},
                "price": current_price,
                "base_equivalent": base_equivalent,
                "quote_equivalent": quote_equivalent
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    def get_pair_info(self):
        """Получить параметры точности и минимальных квот торговой пары (кеш)"""
        base_currency = request.args.get('base_currency', 'BTC').upper()
        quote_currency = request.args.get('quote_currency', 'USDT').upper()
        currency_pair = f"{base_currency}_{quote_currency}".upper()
        force = str(request.args.get('force', '0')).lower() in ('1', 'true', 'yes')
        ttl_override = request.args.get('ttl')
        short = str(request.args.get('short', '0')).lower() in ('1', 'true', 'yes')
        debug = str(request.args.get('debug', '0')).lower() in ('1', 'true', 'yes')
        
        now = time.time()
        ttl = self.pair_info_cache_ttl
        if short:
            ttl = 10
        try:
            if ttl_override is not None:
                ttl = max(0, int(ttl_override))
        except Exception:
            pass
        
        cached = self.pair_info_cache.get(currency_pair)
        if not force and cached and (now - cached['ts'] < ttl):
            resp = {"success": True, "pair": currency_pair, "data": cached['data'], "cached": True}
            if debug:
                resp['debug'] = cached.get('debug')
            return jsonify(resp)
        
        # API ключи (необязательны для публичных эндпойнтов)
        current_network_mode = self.get_current_network_mode()
        api_key = None
        api_secret = None
        if self.account_manager.active_account:
            acc = self.account_manager.get_account(self.account_manager.active_account)
            api_key = acc['api_key']
            api_secret = acc['api_secret']
        else:
            api_key, api_secret = Config.load_secrets_by_mode(current_network_mode)
        
        client = GateAPIClient(api_key, api_secret, current_network_mode)
        
        raw_exact = client.get_currency_pair_details_exact(currency_pair)
        pair_info = {"min_quote_amount": None, "min_base_amount": None, "amount_precision": None, "price_precision": None}
        
        used_source = 'exact'
        if isinstance(raw_exact, dict) and raw_exact.get('id') and str(raw_exact.get('id')).upper() == currency_pair:
            pair_info = {
                "min_quote_amount": raw_exact.get('min_quote_amount'),
                "min_base_amount": raw_exact.get('min_base_amount'),
                "amount_precision": raw_exact.get('amount_precision'),
                "price_precision": raw_exact.get('precision')
            }
        else:
            # fallback на список
            raw_list = client.get_currency_pair_details(currency_pair)
            used_source = 'list'
            if isinstance(raw_list, list):
                for item in raw_list:
                    if str(item.get('id', '')).upper() == currency_pair:
                        pair_info = {
                            "min_quote_amount": item.get('min_quote_amount'),
                            "min_base_amount": item.get('min_base_amount'),
                            "amount_precision": item.get('amount_precision'),
                            "price_precision": item.get('precision')
                        }
                        break
            elif isinstance(raw_list, dict) and raw_list.get('error'):
                return jsonify({"success": False, "pair": currency_pair, "data": pair_info, "error": raw_list.get('error')})
        
        warn = None
        if pair_info['price_precision'] is None:
            warn = 'price_precision_not_found'
        elif pair_info['price_precision'] == 5 and base_currency in ('BTC', 'WLD'):
            warn = 'suspect_same_precision_for_BTC_WLD'
        
        debug_block = {
            'source': used_source,
            'raw_exact_keys': list(raw_exact.keys()) if isinstance(raw_exact, dict) else None,
            'warn': warn
        }
        
        self.pair_info_cache[currency_pair] = {"ts": now, "data": pair_info, "debug": debug_block}
        
        resp = {"success": True, "pair": currency_pair, "data": pair_info, "cached": False}
        if debug:
            resp['debug'] = debug_block
            resp['raw_exact'] = raw_exact
        return jsonify(resp)
    
    # =============================================================================
    # MULTI-PAIRS WATCHER
    # =============================================================================
    
    def _init_default_watchlist(self):
        """Инициализирует watchlist валютными парами по умолчанию из currencies.json"""
        try:
            bases = Config.load_currencies()
            default_pairs = []
            for c in bases:
                code = (c or {}).get('code')
                if code:
                    default_pairs.append(f"{str(code).upper()}_USDT")
            if default_pairs:
                for pair in default_pairs:
                    self.watched_pairs.add(pair)
        except Exception as e:
            print(f"[WATCHLIST] Ошибка инициализации: {e}")
    
    def _add_pairs_to_watchlist(self, pairs: List[str]):
        """Добавить пары в watchlist"""
        ws = get_websocket_manager()
        for p in (pairs or []):
            pair = str(p).upper()
            self.watched_pairs.add(pair)
            try:
                if ws:
                    ws.create_connection(pair)
            except Exception:
                pass
    
    def _remove_pairs_from_watchlist(self, pairs: List[str]):
        """Удалить пары из watchlist"""
        ws = get_websocket_manager()
        for p in (pairs or []):
            pair = str(p).upper()
            self.watched_pairs.discard(pair)
            try:
                if ws:
                    ws.close_connection(pair)
            except Exception:
                pass
    
    def _start_pairs_updater(self):
        """Запуск фонового потока обновления пар"""
        def updater_loop():
            while True:
                try:
                    ws = get_websocket_manager()
                    if ws:
                        for pair in list(self.watched_pairs):
                            try:
                                # гарантируем наличие соединения
                                ws.create_connection(pair)
                                data = ws.get_data(pair)
                                if data is not None:
                                    self.multi_pairs_cache[pair] = {"ts": time.time(), "data": data}
                            except Exception:
                                # игнорируем точечные ошибки по конкретной паре
                                pass
                    time.sleep(1.0)
                except Exception:
                    # защитный блок, чтобы поток не падал
                    time.sleep(1.0)
        
        updater_thread = Thread(target=updater_loop, daemon=True)
        updater_thread.start()
    
    def api_get_watchlist(self):
        """Получить список отслеживаемых пар"""
        return jsonify({"success": True, "pairs": sorted(list(self.watched_pairs))})
    
    def api_watch_pairs(self):
        """Добавить пары в watchlist"""
        try:
            payload = request.get_json(silent=True) or {}
            pairs = payload.get('pairs', [])
            if not pairs:
                return jsonify({"success": False, "error": "pairs[] пуст"}), 400
            self._add_pairs_to_watchlist(pairs)
            return jsonify({"success": True, "added": [p.upper() for p in pairs]})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def api_unwatch_pairs(self):
        """Удалить пары из watchlist"""
        try:
            payload = request.get_json(silent=True) or {}
            pairs = payload.get('pairs', [])
            if not pairs:
                return jsonify({"success": False, "error": "pairs[] пуст"}), 400
            self._remove_pairs_from_watchlist(pairs)
            return jsonify({"success": True, "removed": [p.upper() for p in pairs]})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def api_get_pairs_data(self):
        """Получить данные для всех отслеживаемых пар"""
        try:
            result = {}
            for pair in list(self.watched_pairs):
                cached = self.multi_pairs_cache.get(pair)
                if cached:
                    result[pair] = cached['data']
            return jsonify({"success": True, "data": result, "count": len(result)})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
