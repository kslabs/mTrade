"""
Trading Engine и Account Manager для mTrade
"""

import os
import json
from datetime import datetime
from typing import Optional, List
from data_limits import DataLimits


class TradingEngine:
    """Движок для управления торговлей"""
    
    def __init__(self, api_client, mode: str = "normal"):
        self.client = api_client
        self.mode = mode
        self.is_running = False
        self.active_orders = []
    
    def set_mode(self, mode: str):
        """Переключить режим торговли"""
        if mode in ["normal", "copy"]:
            self.mode = mode
            print(f"[INFO] Режим изменен на: {mode}")
            return True
        return False
    
    def get_mode(self) -> str:
        """Получить текущий режим"""
        return self.mode
    
    def start(self):
        """Запустить торговлю"""
        self.is_running = True
        print(f"[INFO] Торговля запущена в режиме: {self.mode}")
    
    def stop(self):
        """Остановить торговлю"""
        self.is_running = False
        print(f"[INFO] Торговля остановлена")
    
    def execute_trade(self, params: dict):
        """Выполнить сделку"""
        if self.mode == "normal":
            return self._execute_normal_trade(params)
        elif self.mode == "copy":
            return self._execute_copy_trade(params)
    
    def _execute_normal_trade(self, params: dict):
        """Выполнить обычную сделку"""
        try:
            result = self.client.create_spot_order(
                currency_pair=params.get('currency_pair'),
                side=params.get('side'),
                amount=params.get('amount'),
                price=params.get('price'),
                order_type=params.get('type', 'limit')
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_copy_trade(self, params: dict):
        """Выполнить копитрейдинг сделку"""
        return {
            "success": True,
            "message": "Copy trading функционал в разработке",
            "mode": "copy_trading"
        }


class AccountManager:
    """Менеджер для управления несколькими аккаунтами"""
    
    ACCOUNTS_FILE = "accounts.json"
    
    def __init__(self):
        self.accounts = self._load_accounts()
        self.active_account = None
    
    def _load_accounts(self) -> dict:
        """Загрузить аккаунты из файла"""
        if os.path.exists(self.ACCOUNTS_FILE):
            with open(self.ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_accounts(self):
        """Сохранить аккаунты в файл"""
        if len(self.accounts) > DataLimits.MAX_ACCOUNTS:
            print(f"[WARNING] Количество аккаунтов ({len(self.accounts)}) превышает лимит {DataLimits.MAX_ACCOUNTS}")
            sorted_accounts = sorted(
                self.accounts.items(),
                key=lambda x: x[1].get('created_at', ''),
                reverse=True
            )
            self.accounts = dict(sorted_accounts[:DataLimits.MAX_ACCOUNTS])
        
        with open(self.ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.accounts, f, indent=2, ensure_ascii=False)
        
        file_size_kb = os.path.getsize(self.ACCOUNTS_FILE) / 1024
        if file_size_kb > DataLimits.MAX_ACCOUNTS_FILE_SIZE_KB:
            print(f"[WARNING] Размер accounts.json ({file_size_kb:.2f} KB) превышает лимит")
    
    def add_account(self, name: str, api_key: str, api_secret: str):
        """Добавить новый аккаунт"""
        if len(self.accounts) >= DataLimits.MAX_ACCOUNTS:
            return {
                "success": False,
                "error": f"Достигнут максимальный лимит аккаунтов ({DataLimits.MAX_ACCOUNTS})"
            }
        
        self.accounts[name] = {
            "api_key": api_key,
            "api_secret": api_secret,
            "created_at": datetime.now().isoformat()
        }
        self._save_accounts()
        return {"success": True}
    
    def get_account(self, name: str) -> Optional[dict]:
        """Получить аккаунт по имени"""
        return self.accounts.get(name)
    
    def list_accounts(self) -> List[str]:
        """Список всех аккаунтов"""
        return list(self.accounts.keys())
    
    def set_active_account(self, name: str):
        """Установить активный аккаунт"""
        if name in self.accounts:
            self.active_account = name
            return True
        return False
