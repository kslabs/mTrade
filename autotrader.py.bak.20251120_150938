"""
Автотрейдер для mTrade (переработан для per-currency параметров)
"""

import random
import time
from threading import Thread
from typing import Dict, List, Optional


class AutoTrader:
    """Автоматический трейдер с поддержкой усреднения и продажи
    Обновлено: использует индивидуальные параметры для каждой валюты
    через state_manager (breakeven_params) и trading_permissions.
    """
    
    def __init__(self, api_client_provider, ws_manager, state_manager):
        # api_client_provider: функция, возвращающая актуальный GateAPIClient или None
        self.running = False
        self._thread: Optional[Thread] = None
        self.api_client_provider = api_client_provider
        self.ws_manager = ws_manager
        self.state_manager = state_manager
        self.buys: Dict[str, List[float]] = {}  # накопленные покупки (цены) по базе
        self.stats = {
            'total_profit': 0.0,
            'trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'per_base': {},  # {BASE: {cycles, avg_buy, last_price}}
        }
        self._sleep_interval = 5.0

    def start(self):
        if self.running:
            return False
        self.running = True
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[AutoTrader] Запущен (per-currency)")
        return True

    def stop(self):
        self.running = False
        print("[AutoTrader] Остановлен")
        return True

    def _get_price(self, base: str, quote: str = 'USDT') -> float:
        """Получить текущую цену из ws_manager либо вернуться к псевдо-данным"""
        if self.ws_manager:
            data = self.ws_manager.get_data(f"{base}_{quote}")
            if data and data.get('ticker') and data['ticker'].get('last'):
                try:
                    return float(data['ticker']['last'])
                except Exception:
                    pass
        # fallback псевдо-цена
        return 100.0 + random.uniform(-2, 2)

    def _get_params(self, base: str) -> dict:
        """Получить текущие параметры для базы"""
        return self.state_manager.get_breakeven_params(base)

    def _start_new_cycle(self, base: str, price: float, quote: str = 'USDT'):
        """Стартовая покупка новой позиции по базе"""
        params = self._get_params(base)
        start_volume = params.get('start_volume', 3.0)
        self.buys.setdefault(base, [])
        if self.buys[base]:  # уже есть активный цикл
            return
        buy_amount_usd = start_volume
        amount = str(buy_amount_usd / price) if price > 0 else '0.001'
        buy_price = round(price * 0.995, 8)
        api_client = self.api_client_provider()
        if api_client:
            try:
                currency_pair = f"{base}_{quote}"
                api_client.create_spot_order(
                    currency_pair=currency_pair,
                    side='buy',
                    amount=amount,
                    price=str(buy_price),
                    order_type='limit'
                )
                print(f"[AutoTrader] NEW CYCLE BUY {base}: {buy_price}")
                self.buys[base].append(buy_price)
                self.stats['trades'] += 1
                self.stats['successful_trades'] += 1
            except Exception as e:
                print(f"[AutoTrader] Ошибка стартовой покупки {base}: {e}")
                self.stats['failed_trades'] += 1
        else:
            print(f"[AutoTrader] (SIM) NEW CYCLE BUY {base}: {buy_price}")
            self.buys[base].append(buy_price)
            self.stats['successful_trades'] += 1
        self.stats['per_base'].setdefault(base, {'cycles': 0, 'avg_buy': 0, 'last_price': 0})
        self.stats['per_base'][base]['cycles'] += 1
        self.stats['per_base'][base]['avg_buy'] = buy_price

    def _maybe_add_buy(self, base: str, price: float, quote: str = 'USDT'):
        """Усреднение позиции"""
        params = self._get_params(base)
        if not self.buys.get(base):
            return
        max_stages = params.get('steps', 16)
        if len(self.buys[base]) >= max_stages:
            return
        # простое вероятностное условие (заглушка стратегии)
        if random.random() < 0.20:
            start_volume = params.get('start_volume', 3.0)
            amount = str(start_volume / price) if price > 0 else '0.001'
            add_price = round(price * 0.995, 8)
            api_client = self.api_client_provider()
            if api_client:
                try:
                    currency_pair = f"{base}_{quote}"
                    api_client.create_spot_order(
                        currency_pair=currency_pair,
                        side='buy',
                        amount=amount,
                        price=str(add_price),
                        order_type='limit'
                    )
                    print(f"[AutoTrader] AVERAGE BUY {base}: {add_price}")
                    self.buys[base].append(add_price)
                    self.stats['successful_trades'] += 1
                except Exception as e:
                    print(f"[AutoTrader] Ошибка усреднения {base}: {e}")
                    self.stats['failed_trades'] += 1
            else:
                print(f"[AutoTrader] (SIM) AVERAGE BUY {base}: {add_price}")
                self.buys[base].append(add_price)
                self.stats['successful_trades'] += 1
            # обновление avg_buy
            avg = sum(self.buys[base]) / len(self.buys[base])
            self.stats['per_base'].setdefault(base, {'cycles': 0, 'avg_buy': 0, 'last_price': 0})
            self.stats['per_base'][base]['avg_buy'] = avg

    def _maybe_sell_cycle(self, base: str, price: float, quote: str = 'USDT'):
        """Продажа при достижении целевого профита"""
        params = self._get_params(base)
        if not self.buys.get(base):
            return
        avg = sum(self.buys[base]) / len(self.buys[base])
        pprof_pct = params.get('pprof', 0.6) / 100.0
        target = avg * (1 + pprof_pct)
        if price >= target:
            sell_price = round(price, 8)
            buy_amount = sum([float(b) for b in self.buys[base]])
            net_profit = (sell_price - avg) * buy_amount * 0.998
            api_client = self.api_client_provider()
            if api_client:
                try:
                    currency_pair = f"{base}_{quote}"
                    api_client.create_spot_order(
                        currency_pair=currency_pair,
                        side='sell',
                        amount=str(buy_amount),
                        price=str(sell_price),
                        order_type='limit'
                    )
                    print(f"[AutoTrader] SELL {base}: {sell_price}, profit={net_profit}")
                    self.stats['successful_trades'] += 1
                except Exception as e:
                    print(f"[AutoTrader] Ошибка продажи {base}: {e}")
                    self.stats['failed_trades'] += 1
                    return
            else:
                print(f"[AutoTrader] (SIM) SELL {base}: {sell_price}, profit={net_profit}")
                self.stats['successful_trades'] += 1
            self.stats['total_profit'] += net_profit
            self.buys[base] = []  # цикл завершен
            self.stats['per_base'].setdefault(base, {'cycles': 0, 'avg_buy': 0, 'last_price': 0})
            self.stats['per_base'][base]['avg_buy'] = 0

    def _run(self):
        """Основной цикл автоторговли (пер-валютный)"""
        while self.running:
            try:
                if not self.state_manager.get_auto_trade_enabled():
                    time.sleep(self._sleep_interval)
                    continue
                perms = self.state_manager.get_trading_permissions()  # {BASE: bool}
                for base, enabled in perms.items():
                    if not enabled:
                        continue
                    base = base.upper()
                    current_price = self._get_price(base)
                    if current_price <= 0:
                        continue
                    # старт цикла если нет активных покупок
                    if not self.buys.get(base):
                        self._start_new_cycle(base, current_price)
                    else:
                        self._maybe_add_buy(base, current_price)
                        self._maybe_sell_cycle(base, current_price)
                    # обновляем last_price в статистике
                    self.stats['per_base'].setdefault(base, {'cycles': 0, 'avg_buy': 0, 'last_price': 0})
                    self.stats['per_base'][base]['last_price'] = current_price
                time.sleep(self._sleep_interval)
            except Exception as e:
                print(f"[AutoTrader] Ошибка цикла: {e}")
                time.sleep(self._sleep_interval)

# Конец файла
