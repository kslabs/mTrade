"""
Конфигурация приложения Gate.io Multi-Trading
Управление настройками, секретами, валютами и состоянием UI
"""

import os
import json
import time
from data_limits import DataLimits


class Config:
    """Конфигурация приложения"""
    
    # API Gate.io
    API_HOST = "https://api.gateio.ws"
    API_PREFIX = "/api/v4"
    
    # Режимы работы
    MODE_NORMAL = "normal"  # Обычный трейдинг
    MODE_COPY = "copy"      # Копитрейдинг
    
    # Настройки по умолчанию
    DEFAULT_MODE = MODE_NORMAL
    DEFAULT_MARKET = "spot"  # spot, futures
    
    # Файл для хранения настроек
    CONFIG_FILE = "config.json"
    ACCOUNTS_FILE = "accounts.json"
    # Перенос секретов в папку config/
    SECRETS_FILE = os.path.join('config', 'secrets.json')
    CURRENCIES_FILE = "currencies.json"
    UI_STATE_FILE = "ui_state.json"  # Файл для сохранения состояния UI
    WORK_SECRETS_FILE = os.path.join('config', 'secrets.json')        # рабочая сеть
    TEST_SECRETS_FILE = os.path.join('config', 'secrets_test1.json')  # тестовая сеть (новые ключи)
    TEST_API_HOST = "https://api-testnet.gateapi.io"  # Правильный домен тестовой сети Gate.io
    NETWORK_CONFIG_FILE = "network_mode.json"

    @staticmethod
    def load_network_mode() -> str:
        try:
            if os.path.exists(Config.NETWORK_CONFIG_FILE):
                with open(Config.NETWORK_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    js = json.load(f)
                    m = str(js.get('mode', 'work')).lower()
                    return 'test' if m == 'test' else 'work'
        except Exception:
            pass
        return 'work'

    @staticmethod
    def save_network_mode(mode: str) -> bool:
        try:
            if mode not in ('work','test'): return False
            with open(Config.NETWORK_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'mode': mode, 'saved_at': time.time()}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def load_secrets():
        """Загрузить API ключи из secrets.json"""
        if os.path.exists(Config.SECRETS_FILE):
            try:
                with open(Config.SECRETS_FILE, 'r') as f:
                    secrets = json.load(f)
                    return secrets.get('GATEIO_API_KEY'), secrets.get('GATEIO_API_SECRET')
            except Exception as e:
                print(f"[ERROR] Ошибка загрузки secrets.json: {e}")
        return None, None
    
    @staticmethod
    def load_secrets_by_mode(mode: str):
        """Загрузить ключи по режиму work|test, учитывая новые пути config/ и старые имена для обратной совместимости."""
        candidates = []
        if mode == 'work':
            candidates = [
                Config.WORK_SECRETS_FILE,
                Config.SECRETS_FILE,
                'secret.json',           # старое имя
                'secrets.json'           # возможный вариант
            ]
        else:
            candidates = [
                Config.TEST_SECRETS_FILE,   # config/secrets_test1.json (новые ключи)
                os.path.join('config', 'secrets_test.json'),  # старые тестовые ключи
                'secret_test.json',         # старое имя
                'secrets_test.json'         # возможный вариант
            ]
        for file in candidates:
            try:
                if os.path.exists(file):
                    with open(file,'r',encoding='utf-8') as f:
                        j = json.load(f)
                        ak = j.get('GATEIO_API_KEY')
                        sk = j.get('GATEIO_API_SECRET')
                        if ak and sk:
                            return ak, sk
            except Exception as e:
                print(f"[ERROR] Ошибка загрузки {file}: {e}")
        return None, None
    
    @staticmethod
    def load_currencies():
        """Загрузить список базовых валют из currencies.json"""
        default_currencies = [
            { "code": "WLD", "symbol": "🌐" },
            { "code": "BTC", "symbol": "₿" },
            { "code": "ETH", "symbol": "Ξ" },
            { "code": "SOL", "symbol": "◎" },
            { "code": "BNB", "symbol": "🔶" },
            { "code": "XRP", "symbol": "✕" },
            { "code": "ADA", "symbol": "₳" },
            { "code": "AVAX", "symbol": "🔺" },
            { "code": "DOT", "symbol": "⬤" },
            { "code": "MATIC", "symbol": "🔷" }
        ]
        
        if os.path.exists(Config.CURRENCIES_FILE):
            try:
                with open(Config.CURRENCIES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Поддержка нового формата (объект с ключом currencies)
                    if isinstance(data, dict) and 'currencies' in data:
                        currencies = data['currencies']
                    else:
                        # Старый формат (просто массив)
                        currencies = data
                    return currencies if currencies else default_currencies
            except Exception as e:
                print(f"[ERROR] Ошибка загрузки currencies.json: {e}")
                return default_currencies
        else:
            # Создать файл с дефолтными валютами
            Config.save_currencies(default_currencies)
            return default_currencies
    
    @staticmethod
    def save_currencies(currencies):
        """Сохранить список базовых валют в currencies.json"""
        try:
            # Ограничиваем количество валют
            if len(currencies) > DataLimits.MAX_CURRENCIES:
                currencies = currencies[:DataLimits.MAX_CURRENCIES]
                print(f"[WARNING] Количество валют ограничено до {DataLimits.MAX_CURRENCIES}")
            
            with open(Config.CURRENCIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(currencies, f, ensure_ascii=False, indent=2)
            
            # Проверка размера файла
            file_size_kb = os.path.getsize(Config.CURRENCIES_FILE) / 1024
            if file_size_kb > DataLimits.MAX_CURRENCIES_FILE_SIZE_KB:
                print(f"[WARNING] Размер currencies.json ({file_size_kb:.2f} KB) превышает лимит")
            
            return True
        except Exception as e:
            print(f"[ERROR] Ошибка сохранения currencies.json: {e}")
            return False

    @staticmethod
    def load_ui_state():
        """Загрузить состояние UI из файла"""
        default_state = {
            "enabled_currencies": {},  # {BASE_CURRENCY: true/false}
            "auto_trade_enabled": False,
            "network_mode": "work",
            "active_base_currency": "BTC",
            "active_quote_currency": "USDT",
            "theme": "dark",
            "show_indicators": True,
            "show_orderbook": True,
            "show_trades": True,
            "orderbook_depth": 20,
            "last_updated": None
        }
        
        if os.path.exists(Config.UI_STATE_FILE):
            try:
                with open(Config.UI_STATE_FILE, 'r', encoding='utf-8') as f:
                    saved_state = json.load(f)
                    # Объединяем с дефолтными значениями
                    default_state.update(saved_state)
                    return default_state
            except Exception as e:
                print(f"[ERROR] Ошибка загрузки ui_state.json: {e}")
                return default_state
        else:
            # Создаем файл с дефолтными настройками
            Config.save_ui_state(default_state)
            return default_state
    
    @staticmethod
    def save_ui_state(state):
        """Сохранить состояние UI в файл"""
        try:
            state['last_updated'] = time.time()
            with open(Config.UI_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[ERROR] Ошибка сохранения ui_state.json: {e}")
            return False
