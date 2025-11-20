"""
API Routes Module
Содержит все API эндпоинты для mTrade приложения
"""

from flask import request, jsonify
from typing import Dict, Any
import traceback

from config import Config
from gate_api_client import GateAPIClient
from trading_engine import TradingEngine, AccountManager
from state_manager import get_state_manager


class APIRoutes:
    """Класс для управления API маршрутами"""
    
    def __init__(self, app, account_manager, trading_engines, current_network_mode_getter):
        """
        Инициализация API Routes
        
        Args:
            app: Flask приложение
            account_manager: Менеджер аккаунтов
            trading_engines: Словарь торговых движков
            current_network_mode_getter: Функция для получения текущего режима сети
        """
        self.app = app
        self.account_manager = account_manager
        self.trading_engines = trading_engines
        self.get_current_network_mode = current_network_mode_getter
        self.state_manager = get_state_manager()
        
        # Регистрация всех маршрутов
        self._register_routes()
    
    def _register_routes(self):
        """Регистрация всех API маршрутов"""
        # Accounts
        self.app.add_url_rule('/api/accounts', 'get_accounts', self.get_accounts, methods=['GET'])
        self.app.add_url_rule('/api/accounts', 'add_account', self.add_account, methods=['POST'])
        
        # Mode
        self.app.add_url_rule('/api/mode', 'get_mode', self.get_mode, methods=['GET'])
        self.app.add_url_rule('/api/mode', 'set_mode', self.set_mode, methods=['POST'])
        self.app.add_url_rule('/api/mode/legacy', 'get_mode_legacy', self.get_mode_legacy, methods=['GET'])
        
        # Currencies
        self.app.add_url_rule('/api/currencies', 'get_currencies', self.get_currencies, methods=['GET'])
        self.app.add_url_rule('/api/currencies', 'save_currencies', self.save_currencies, methods=['POST'])
        
        # Balance & Orders
        self.app.add_url_rule('/api/balance', 'get_balance', self.get_balance, methods=['GET'])
        self.app.add_url_rule('/api/orders', 'get_orders', self.get_orders, methods=['GET'])
        
        # Trade
        self.app.add_url_rule('/api/trade', 'execute_trade', self.execute_trade, methods=['POST'])
    
    # =============================================================================
    # ACCOUNTS
    # =============================================================================
    
    def get_accounts(self):
        """Получить список аккаунтов"""
        return jsonify({
            "accounts": self.account_manager.list_accounts(),
            "active": self.account_manager.active_account
        })
    
    def add_account(self):
        """Добавить новый аккаунт"""
        data = request.json
        self.account_manager.add_account(
            data['name'],
            data['api_key'],
            data['api_secret']
        )
        return jsonify({"success": True, "message": "Аккаунт добавлен"})
    
    # =============================================================================
    # MODE (TRADE/COPY)
    # =============================================================================
    
    def get_mode(self):
        """Получить текущий режим торговли (trade/copy)"""
        mode = self.state_manager.get_trading_mode()
        internal_mode = 'normal' if mode == 'trade' else 'copy'
        return jsonify({"mode": mode, "internal_mode": internal_mode, "success": True})
    
    def set_mode(self):
        """Переключить режим торговли (trade/copy)"""
        try:
            data = request.get_json(silent=True) or {}
            mode = str(data.get('mode', '')).lower().strip()
            if mode not in ('trade', 'copy'):
                return jsonify({"success": False, "error": "Неверный режим"}), 400
            
            self.state_manager.set_trading_mode(mode)
            stored = self.state_manager.get_trading_mode()
            
            # Применяем ко всем активным движкам
            internal_mode = 'normal' if stored == 'trade' else 'copy'
            for eng in self.trading_engines.values():
                try:
                    eng.set_mode(internal_mode)
                except Exception:
                    pass
            
            print(f"[MODE] Установлен режим: {stored} (internal={internal_mode})")
            return jsonify({"mode": stored, "internal_mode": internal_mode, "success": True})
        except Exception as e:
            print(f"[ERROR] set_mode: {e}\n{traceback.format_exc()}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def get_mode_legacy(self):
        """Legacy формат ответа только с полем mode"""
        return jsonify({"mode": self.state_manager.get_trading_mode()})
    
    # =============================================================================
    # CURRENCIES
    # =============================================================================
    
    def get_currencies(self):
        """Получить список базовых валют"""
        currencies = Config.load_currencies()
        return jsonify({"success": True, "currencies": currencies})
    
    def save_currencies(self):
        """Сохранить список базовых валют"""
        try:
            data = request.json
            currencies = data.get('currencies', [])
            
            # Валидация
            if not currencies or not isinstance(currencies, list):
                return jsonify({"success": False, "error": "Неверный формат данных"}), 400
            
            # Проверка на дубликаты
            codes = [c.get('code') for c in currencies]
            if len(codes) != len(set(codes)):
                return jsonify({"success": False, "error": "Обнаружены дублирующиеся коды валют"}), 400
            
            # Проверка на пустые значения
            for currency in currencies:
                if not currency.get('code') or not isinstance(currency.get('code'), str):
                    return jsonify({"success": False, "error": "Все валюты должны иметь код"}), 400
            
            # Сохранение
            if Config.save_currencies(currencies):
                return jsonify({"success": True, "message": "Валюты сохранены"})
            else:
                return jsonify({"success": False, "error": "Ошибка сохранения"}), 500
                
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    # =============================================================================
    # BALANCE & ORDERS
    # =============================================================================
    
    def get_balance(self):
        """Получить баланс"""
        if not self.account_manager.active_account:
            return jsonify({"error": "Нет активного аккаунта"}), 400
        
        account = self.account_manager.get_account(self.account_manager.active_account)
        current_network_mode = self.get_current_network_mode()
        client = GateAPIClient(account['api_key'], account['api_secret'], current_network_mode)
        
        try:
            balance = client.get_account_balance()
            return jsonify({"success": True, "data": balance})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    def get_orders(self):
        """Получить список ордеров"""
        if not self.account_manager.active_account:
            return jsonify({"error": "Нет активного аккаунта"}), 400
        
        account = self.account_manager.get_account(self.account_manager.active_account)
        current_network_mode = self.get_current_network_mode()
        client = GateAPIClient(account['api_key'], account['api_secret'], current_network_mode)
        currency_pair = request.args.get('currency_pair', 'BTC_USDT')
        
        try:
            orders = client.get_spot_orders(currency_pair)
            return jsonify({"success": True, "data": orders})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    # =============================================================================
    # TRADE
    # =============================================================================
    
    def execute_trade(self):
        """Выполнить сделку"""
        if not self.account_manager.active_account:
            return jsonify({"error": "Нет активного аккаунта"}), 400
        
        data = request.json
        
        # Получаем или создаем trading engine для аккаунта
        if self.account_manager.active_account not in self.trading_engines:
            acc = self.account_manager.get_account(self.account_manager.active_account)
            current_network_mode = self.get_current_network_mode()
            api_client = GateAPIClient(acc['api_key'], acc['api_secret'], current_network_mode)
            self.trading_engines[self.account_manager.active_account] = TradingEngine(api_client)
        
        engine = self.trading_engines[self.account_manager.active_account]
        trade_params = {
            'currency_pair': data.get('currency_pair'),
            'side': data.get('side'),
            'amount': data.get('amount'),
            'price': data.get('price'),
            'type': data.get('type', 'limit')
        }
        
        result = engine.execute_trade(trade_params)
        return jsonify(result)
