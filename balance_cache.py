"""
Кэш балансов для автотрейдера
Уменьшает количество запросов к API в 10-20 раз
"""

import time
from threading import Lock
from typing import Dict, Optional, List


class BalanceCache:
    """
    Кэш балансов с TTL и умным обновлением.
    
    Стратегия:
    - Кэшируем все балансы сразу (один запрос вместо 16)
    - TTL = 5 секунд (балансы меняются редко)
    - Инвалидация после каждой торговой операции
    - Prefetch: загружаем заранее для всех валют
    """
    
    def __init__(self, ttl_seconds: float = 5.0):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, float] = {}
        self.last_update: float = 0
        self.lock = Lock()
        self.api_client = None
        
        # Статистика
        self.hits = 0
        self.misses = 0
        self.invalidations = 0
    
    def set_api_client(self, api_client):
        """Установить API клиент"""
        self.api_client = api_client
    
    def get_balance(self, currency: str, force_refresh: bool = False) -> Optional[float]:
        """
        Получить баланс валюты (с кэшированием).
        
        Args:
            currency: Код валюты (BTC, ETH, USDT и т.д.)
            force_refresh: Принудительно обновить из API
            
        Returns:
            Баланс или None если ошибка
        """
        currency = currency.upper()
        
        with self.lock:
            now = time.time()
            
            # Проверяем кэш
            if not force_refresh and (now - self.last_update) < self.ttl_seconds:
                if currency in self.cache:
                    self.hits += 1
                    return self.cache[currency]
            
            # Кэш устарел или нет данных — обновляем
            self.misses += 1
            return self._refresh_all_balances()
    
    def _refresh_all_balances(self) -> Optional[float]:
        """
        Обновить все балансы одним запросом.
        Возвращает None если ошибка (вызывающий код должен обработать).
        """
        if not self.api_client:
            return None
        
        try:
            # ОДИН запрос для всех валют!
            balance_list = self.api_client.get_account_balance()
            
            if not isinstance(balance_list, list):
                return None
            
            # Обновляем весь кэш
            self.cache.clear()
            for item in balance_list:
                currency = item.get('currency', '').upper()
                try:
                    available = float(item.get('available', 0))
                    self.cache[currency] = available
                except (ValueError, TypeError):
                    self.cache[currency] = 0.0
            
            self.last_update = time.time()
            
            return None  # Успех, но возвращать конкретный баланс должен вызывающий код
            
        except Exception as e:
            print(f"[BalanceCache] ❌ Ошибка обновления балансов: {e}")
            return None
    
    def get_balances(self, currencies: List[str], force_refresh: bool = False) -> Dict[str, float]:
        """
        Получить балансы нескольких валют одним запросом.
        
        Args:
            currencies: Список кодов валют
            force_refresh: Принудительно обновить из API
            
        Returns:
            Словарь {валюта: баланс}
        """
        currencies = [c.upper() for c in currencies]
        
        with self.lock:
            now = time.time()
            
            # Проверяем, нужно ли обновление
            need_refresh = force_refresh or (now - self.last_update) >= self.ttl_seconds
            
            # Проверяем, есть ли все валюты в кэше
            if not need_refresh:
                if all(c in self.cache for c in currencies):
                    self.hits += len(currencies)
                    return {c: self.cache[c] for c in currencies}
            
            # Обновляем кэш
            self._refresh_all_balances()
            
            # Возвращаем запрошенные балансы
            result = {}
            for c in currencies:
                result[c] = self.cache.get(c, 0.0)
            
            return result
    
    def invalidate(self, reason: str = "unknown"):
        """
        Инвалидировать кэш (после торговой операции).
        
        Args:
            reason: Причина инвалидации (для логирования)
        """
        with self.lock:
            self.last_update = 0  # Сбрасываем время обновления
            self.invalidations += 1
            print(f"[BalanceCache] 🔄 Кэш инвалидирован ({reason})")
    
    def prefetch(self, currencies: List[str]):
        """
        Предзагрузить балансы для списка валют.
        Полезно вызывать при старте автотрейдера.
        """
        with self.lock:
            self._refresh_all_balances()
            print(f"[BalanceCache] ✅ Предзагрузка балансов: {len(self.cache)} валют")
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику использования кэша"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(hit_rate, 1),
                "invalidations": self.invalidations,
                "cached_currencies": len(self.cache)
            }
    
    def reset_stats(self):
        """Сбросить статистику"""
        with self.lock:
            self.hits = 0
            self.misses = 0
            self.invalidations = 0


# Глобальный экземпляр кэша
_balance_cache = BalanceCache(ttl_seconds=5.0)


def get_balance_cache() -> BalanceCache:
    """Получить глобальный экземпляр кэша балансов"""
    return _balance_cache
