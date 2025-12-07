"""

State Manager - Управление состоянием приложения

Сохраняет и восстанавливает состояние UI, параметры торговли и т.д.

"""



import json

import os

from typing import Dict, Any, Optional

from threading import Lock



class StateManager:

    """Менеджер состояния приложения"""

    

    def __init__(self, state_file: str = "app_state.json"):

        self.state_file = state_file

        self.lock = Lock()

        self._state = self._load_state()

    

    def _load_state(self) -> Dict[str, Any]:

        """Загрузить состояние из файла"""

        if os.path.exists(self.state_file):

            try:

                with open(self.state_file, 'r', encoding='utf-8') as f:

                    return json.load(f)

            except Exception as e:

                print(f"[STATE] Ошибка загрузки состояния: {e}")

                return self._get_default_state()

        return self._get_default_state()

    

    def _save_state(self) -> bool:

        """Сохранить состояние в файл"""

        try:

            with self.lock:

                with open(self.state_file, 'w', encoding='utf-8') as f:

                    json.dump(self._state, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:

            print(f"[STATE] Ошибка сохранения состояния: {e}")

            return False

    

    def _get_default_state(self) -> Dict[str, Any]:

        """Получить состояние по умолчанию"""

        return {

            "trading_mode": "trade",  # trade или copy

            "auto_trade_enabled": True,

            "trading_permissions": {},  # {currency: enabled}

            "network_mode": "test",

            "breakeven_params": {}  # {currency: {steps, start_volume, ...}}

        }

    

    def get(self, key: str, default: Any = None) -> Any:

        """Получить значение из состояния"""

        with self.lock:

            return self._state.get(key, default)

    

    def set(self, key: str, value: Any, save: bool = True) -> bool:

        """Установить значение в состоянии"""

        with self.lock:

            self._state[key] = value

        if save:

            return self._save_state()

        return True

    

    def update(self, updates: Dict[str, Any], save: bool = True) -> bool:

        """Обновить несколько значений"""

        with self.lock:

            self._state.update(updates)

        if save:

            return self._save_state()

        return True

    

    def get_all(self) -> Dict[str, Any]:

        """Получить все состояние"""

        with self.lock:

            return self._state.copy()

    

    # Специфичные методы для различных типов состояний

    

    def get_trading_mode(self) -> str:

        """Получить режим торговли (trade/copy)"""

        return self.get("trading_mode", "trade")

    

    def set_trading_mode(self, mode: str) -> bool:

        """Установить режим торговли"""

        if mode not in ("trade", "copy"):

            return False

        return self.set("trading_mode", mode)

    

    def get_auto_trade_enabled(self) -> bool:

        """Получить статус автоторговли"""

        return self.get("auto_trade_enabled", True)

    

    def set_auto_trade_enabled(self, enabled: bool) -> bool:

        """Установить статус автоторговли"""

        return self.set("auto_trade_enabled", bool(enabled))

    

    def get_trading_permissions(self) -> Dict[str, bool]:

        """Получить разрешения торговли для всех валют"""

        return self.get("trading_permissions", {})

    

    def set_trading_permission(self, currency: str, enabled: bool) -> bool:

        """Установить разрешение торговли для валюты"""

        perms = self.get_trading_permissions()

        perms[currency.upper()] = bool(enabled)

        return self.set("trading_permissions", perms)

    

    def get_network_mode(self) -> str:

        """Получить режим сети"""

        return self.get("network_mode", "test")

    

    def set_network_mode(self, mode: str) -> bool:

        """Установить режим сети"""

        if mode not in ("work", "test"):

            return False

        return self.set("network_mode", mode)

    

    def get_active_base_currency(self) -> str:

        """Получить активную базовую валюту"""

        return self.get("active_base_currency", "BTC")

    

    def set_active_base_currency(self, currency: str) -> bool:

        """Установить активную базовую валюту"""

        return self.set("active_base_currency", currency.upper())

    

    def get_active_quote_currency(self) -> str:

        """Получить активную котировочную валюту"""

        return self.get("active_quote_currency", "USDT")

    

    def set_active_quote_currency(self, currency: str) -> bool:

        """Установить активную котировочную валюту"""

        return self.set("active_quote_currency", currency.upper())

    

    def get_breakeven_params(self, currency: str = None) -> Dict[str, Any]:

        """Получить параметры безубыточности

        Если currency указан - вернуть параметры для этой валюты

        Иначе - вернуть все параметры

        """

        all_params = self.get("breakeven_params", {})

        if currency:

            return all_params.get(currency.upper(), self._get_default_breakeven_params())

        return all_params

    

    def set_breakeven_params(self, currency: str, params: Dict[str, Any]) -> bool:

        """Установить параметры безубыточности для валюты"""

        all_params = self.get_breakeven_params()

        all_params[currency.upper()] = params

        return self.set("breakeven_params", all_params)

    

    def _get_default_breakeven_params(self) -> Dict[str, Any]:

        """Получить параметры безубыточности по умолчанию"""

        return {

            'steps': 16,

            'start_volume': 3.0,

            'start_price': 0.0,

            'pprof': 0.6,

            'kprof': 0.02,

            'target_r': 3.65,

            'rk': 0.0,  # Коэффициент изменения шага процента закупки

            'geom_multiplier': 2.0,

            'rebuy_mode': 'geometric',

            'keep': 0.0,  # Постоянная сумма на балансе

            'orderbook_level': 1.0  # По умолчанию используем 1-й уровень стакана (лучшая цена)

        }

    

    def init_currency_permissions(self, currencies: list) -> bool:

        """Инициализировать разрешения для новых валют (не перезаписывая существующие)"""

        # Получаем текущие разрешения

        perms = self.get_trading_permissions()

        

        # Добавляем только новые валюты (по умолчанию True)

        for currency in currencies:

            code = currency.get('code', '').upper()

            if code and code not in perms:

                perms[code] = True

        

        return self.set("trading_permissions", perms)





# Глобальный экземпляр менеджера состояния

_state_manager = None



def get_state_manager() -> StateManager:

    """Получить глобальный экземпляр менеджера состояния"""

    global _state_manager

    if _state_manager is None:

        _state_manager = StateManager()

    return _state_manager

