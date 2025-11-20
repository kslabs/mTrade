"""
Data Limits Configuration
Конфигурация ограничений для предотвращения переполнения памяти и дискового пространства
"""

class DataLimits:
    """Конфигурация ограничений данных"""
    
    # WebSocket кэш
    MAX_CURRENCY_PAIRS_CACHE = 10  # Максимум валютных пар в кэше одновременно
    MAX_ORDERBOOK_LEVELS = 20      # Максимум уровней стакана (asks/bids каждый)
    MAX_TRADES_HISTORY = 50        # Максимум сделок в истории для пары
    CACHE_TTL_SECONDS = 300        # Время жизни кэша без обновлений (5 минут)
    
    # Файлы конфигурации
    MAX_CURRENCIES = 50            # Максимум валют в списке
    MAX_ACCOUNTS = 10              # Максимум аккаунтов
    
    # Логи и история
    MAX_LOG_SIZE_MB = 10           # Максимальный размер лог-файла (если будет)
    MAX_ORDER_HISTORY = 1000       # Максимум ордеров в истории
    MAX_TRADE_HISTORY = 1000       # Максимум сделок в истории
    
    # Очистка
    CLEANUP_INTERVAL_SECONDS = 600 # Интервал автоматической очистки (10 минут)
    MIN_PAIRS_TO_KEEP = 1          # Минимум пар для хранения (текущая активная)
    
    # Размеры JSON файлов (в килобайтах)
    MAX_CURRENCIES_FILE_SIZE_KB = 100
    MAX_ACCOUNTS_FILE_SIZE_KB = 500
    MAX_CONFIG_FILE_SIZE_KB = 100
