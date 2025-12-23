"""
Модуль для синхронизации символов валют с Gate.io API
Получает официальные данные о валютах и их символах
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from gate_api_client import GateAPIClient


# Встроенные символы для основных криптовалют (fallback)
FALLBACK_SYMBOLS = {
    "BTC": "₿",
    "ETH": "Ξ",
    "USDT": "₮",
    "USDC": "$",
    "BNB": "🔶",
    "XRP": "✕",
    "ADA": "₳",
    "DOGE": "Ð",
    "SOL": "◎",
    "DOT": "●",
    "MATIC": "⬡",
    "LTC": "Ł",
    "TRX": "⊤",
    "AVAX": "🔺",
    "LINK": "🔗",
    "ATOM": "⚛",
    "XMR": "ɱ",
    "XLM": "*",
    "ETC": "⟠",
    "FIL": "⨎",
    "NEAR": "Ⓝ",
    "ALGO": "Å",
    "VET": "⚡",
    "ICP": "∞",
    "HBAR": "ℏ",
    "APT": "🅰",
    "QNT": "Q",
    "AAVE": "👻",
    "UNI": "🦄",
    "TON": "💎",
    "SUI": "〰",
}


class CurrencySync:
    """Класс для синхронизации символов валют с Gate.io"""
    
    def __init__(self, currencies_file: str = "currencies.json", 
                 full_db_file: str = "currencies_full.json"):
        self.currencies_file = currencies_file  # Файл для UI (ограниченный список)
        self.full_db_file = full_db_file  # Полная база данных всех валют
        self.currencies_data = self._load_currencies()
        self.full_db_data = self._load_full_db()
    
    def _load_currencies(self) -> Dict:
        """Загрузить текущие данные о валютах из файла"""
        if os.path.exists(self.currencies_file):
            try:
                with open(self.currencies_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Если это старый формат (просто список), конвертируем
                    if isinstance(data, list):
                        return {
                            "currencies": data,
                            "last_update": None,
                            "network_mode": "unknown"
                        }
                    return data
            except Exception as e:
                print(f"Ошибка загрузки currencies.json: {e}")
                return {"currencies": [], "last_update": None}
        return {"currencies": [], "last_update": None}
    
    def _save_currencies(self):
        """Сохранить данные о валютах в файл"""
        try:
            with open(self.currencies_file, 'w', encoding='utf-8') as f:
                json.dump(self.currencies_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения currencies.json: {e}")
            return False
    
    def _load_full_db(self) -> Dict:
        """Загрузить полную базу данных валют"""
        if os.path.exists(self.full_db_file):
            try:
                with open(self.full_db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                print(f"Ошибка загрузки {self.full_db_file}: {e}")
        return {"currencies": {}, "last_update": None}
    
    def _save_full_db(self):
        """Сохранить полную базу данных валют"""
        try:
            with open(self.full_db_file, 'w', encoding='utf-8') as f:
                json.dump(self.full_db_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения {self.full_db_file}: {e}")
            return False
    
    def sync_from_gateio(self, api_key: str = None, api_secret: str = None, network_mode: str = 'work') -> Dict:
        """
        Синхронизировать список валют с Gate.io API
        
        Args:
            api_key: API ключ (необязательно для публичных endpoints)
            api_secret: API секрет (необязательно для публичных endpoints)
            network_mode: режим сети ('work' или 'test')
        
        Returns:
            dict: результат синхронизации с количеством добавленных/обновленных валют
        """
        try:
            # Создаём клиент (для публичных endpoints ключи необязательны)
            client = GateAPIClient(
                api_key=api_key or "",
                api_secret=api_secret or "",
                network_mode=network_mode
            )
            
            # Получаем список всех валют
            currencies_response = client.get_currencies()
            
            if isinstance(currencies_response, dict) and "error" in currencies_response:
                return {
                    "success": False,
                    "error": currencies_response["error"],
                    "added": 0,
                    "updated": 0
                }
            
            # Получаем текущий список валют для UI (ограниченный)
            ui_currencies = {c["code"]: c for c in self.currencies_data.get("currencies", [])}
            
            # Получаем полную базу данных
            full_db_currencies = self.full_db_data.get("currencies", {})
            
            added_count = 0
            updated_count = 0
            total_in_db = 0
            
            # Обрабатываем каждую валюту из API
            for currency_info in currencies_response:
                code = currency_info.get("currency", "").upper()
                name = currency_info.get("name", code)
                
                if not code:
                    continue
                
                # Определяем символ для валюты
                symbol = self._get_currency_symbol(code, currency_info)
                
                currency_data = {
                    "code": code,
                    "name": name,
                    "symbol": symbol,
                    "chain": currency_info.get("chain", ""),
                    "delisted": currency_info.get("delisted", False),
                    "withdraw_disabled": currency_info.get("withdraw_disabled", False),
                    "withdraw_delayed": currency_info.get("withdraw_delayed", False),
                    "deposit_disabled": currency_info.get("deposit_disabled", False),
                    "trade_disabled": currency_info.get("trade_disabled", False),
                }
                
                # Сохраняем в полную базу
                if code not in full_db_currencies:
                    added_count += 1
                else:
                    updated_count += 1
                full_db_currencies[code] = currency_data
                total_in_db += 1
                
                # Обновляем только если валюта уже есть в UI списке
                if code in ui_currencies:
                    # Сохраняем пользовательский символ если был
                    old_symbol = ui_currencies[code].get("symbol")
                    if ui_currencies[code].get("custom_symbol"):
                        currency_data["symbol"] = old_symbol
                        currency_data["custom_symbol"] = True
                    ui_currencies[code] = currency_data
            
            # Обновляем метаданные
            timestamp = datetime.now().isoformat()
            
            # Сохраняем полную базу данных
            self.full_db_data = {
                "currencies": full_db_currencies,
                "last_update": timestamp,
                "network_mode": network_mode,
                "total": total_in_db
            }
            self._save_full_db()
            
            # Обновляем UI список (только существующие валюты)
            self.currencies_data["currencies"] = list(ui_currencies.values())
            self.currencies_data["last_update"] = timestamp
            self.currencies_data["network_mode"] = network_mode
            
            # Сохраняем UI список
            if self._save_currencies():
                return {
                    "success": True,
                    "added": added_count,
                    "updated": updated_count,
                    "total": total_in_db,
                    "ui_currencies": len(ui_currencies),
                    "timestamp": timestamp
                }
            else:
                return {
                    "success": False,
                    "error": "Не удалось сохранить данные",
                    "added": 0,
                    "updated": 0
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "added": 0,
                "updated": 0
            }
    
    def _get_currency_symbol(self, code: str, currency_info: Dict) -> str:
        """
        Определить символ для валюты
        
        Приоритеты:
        1. Fallback символы (известные криптовалюты)
        2. Первая буква кода валюты
        """
        # Проверяем fallback символы
        if code in FALLBACK_SYMBOLS:
            return FALLBACK_SYMBOLS[code]
        
        # Для стейблкоинов используем $
        if any(stable in code for stable in ["USD", "USDT", "USDC", "DAI", "BUSD"]):
            return "$"
        
        # По умолчанию - первая буква
        return code[0] if code else "?"
    
    def get_currency(self, code: str) -> Optional[Dict]:
        """Получить информацию о валюте по коду"""
        for currency in self.currencies_data.get("currencies", []):
            if currency["code"] == code.upper():
                return currency
        return None
    
    def get_all_currencies(self) -> List[Dict]:
        """Получить список всех валют"""
        return self.currencies_data.get("currencies", [])
    
    def update_currency_symbol(self, code: str, symbol: str) -> bool:
        """
        Обновить символ валюты (пользовательская настройка)
        
        Args:
            code: код валюты
            symbol: новый символ
        
        Returns:
            bool: успех операции
        """
        for currency in self.currencies_data.get("currencies", []):
            if currency["code"] == code.upper():
                currency["symbol"] = symbol
                currency["custom_symbol"] = True
                return self._save_currencies()
        return False
    
    def get_sync_info(self) -> Dict:
        """Получить информацию о последней синхронизации"""
        return {
            "last_update": self.currencies_data.get("last_update"),
            "network_mode": self.currencies_data.get("network_mode", "unknown"),
            "total_currencies": len(self.currencies_data.get("currencies", [])),
            "custom_symbols": sum(1 for c in self.currencies_data.get("currencies", []) 
                                 if c.get("custom_symbol", False))
        }


# Удобная функция для быстрой синхронизации
def sync_currencies(api_key: str = None, api_secret: str = None, network_mode: str = 'work') -> Dict:
    """
    Синхронизировать валюты с Gate.io
    
    Args:
        api_key: API ключ (необязательно)
        api_secret: API секрет (необязательно)
        network_mode: режим сети
    
    Returns:
        dict: результат синхронизации
    """
    sync = CurrencySync()
    return sync.sync_from_gateio(api_key, api_secret, network_mode)


if __name__ == "__main__":
    # Тестовый запуск синхронизации
    print("Синхронизация валют с Gate.io...")
    result = sync_currencies()
    
    if result["success"]:
        print(f"✅ Успешно!")
        print(f"   Добавлено: {result['added']}")
        print(f"   Обновлено: {result['updated']}")
        print(f"   Всего: {result['total']}")
        print(f"   Время: {result['timestamp']}")
    else:
        print(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
