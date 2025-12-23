#!/usr/bin/env python3
"""
🔄 Live-мониторинг автотрейдера
Обновляется каждые 5 секунд, показывает изменения в реальном времени
"""

import json
import time
import os
import requests
from datetime import datetime
from colorama import init, Fore, Style
init(autoreset=True)

API_URL = "http://localhost:3001"

def clear_screen():
    """Очистка экрана"""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_cycles():
    """Загрузка состояния циклов"""
    try:
        with open('autotrader_cycles_state.json', 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def get_api_status():
    """Статус автотрейдера через API"""
    try:
        response = requests.get(f"{API_URL}/api/autotrade/status", timeout=2)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def get_current_prices():
    """Текущие цены валют"""
    try:
        response = requests.get(f"{API_URL}/api/balance", timeout=2)
        if response.status_code == 200:
            data = response.json()
            prices = {}
            for item in data:
                currency = item.get('currency')
                price = item.get('price', 0)
                if currency and price:
                    prices[currency] = price
            return prices
        return {}
    except Exception:
        return {}

def calculate_pnl(cycle, current_price):
    """Расчёт P&L цикла"""
    invested = cycle.get('total_invested_usd', 0)
    volume = cycle.get('base_volume', 0)
    
    if volume > 0 and current_price > 0:
        current_value = volume * current_price
        pnl = current_value - invested
        pnl_percent = (pnl / invested) * 100 if invested > 0 else 0
        return pnl, pnl_percent, current_value
    
    return 0, 0, 0

def format_price(price):
    """Форматирование цены"""
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.4f}"
    else:
        return f"${price:.6f}"

def print_dashboard(cycles, api_status, prices, prev_cycles=None):
    """Отображение dashboard"""
    clear_screen()
    
    # Заголовок
    print("=" * 140)
    print(f"{Fore.CYAN}{'🔄 LIVE-МОНИТОРИНГ АВТОТРЕЙДЕРА':^140}{Style.RESET_ALL}")
    print("=" * 140)
    print(f"{Fore.YELLOW}⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Обновление каждые 5 секунд{Style.RESET_ALL}")
    
    # Статус API
    if api_status:
        running = api_status.get('running', False)
        enabled = api_status.get('enabled', False)
        stats = api_status.get('stats', {})
        
        status_icon = "🟢" if running and enabled else "🔴"
        status_text = "РАБОТАЕТ" if running and enabled else "ОСТАНОВЛЕН"
        
        print(f"\n{status_icon} Статус: {Fore.GREEN if running else Fore.RED}{status_text}{Style.RESET_ALL}")
        print(f"📊 Статистика: Циклы={stats.get('cycler_processed', 0)} | Срочные={stats.get('urgent_processed', 0)} | Очередь={stats.get('reactor_queued', 0)}")
    else:
        print(f"\n{Fore.RED}❌ API недоступен{Style.RESET_ALL}")
    
    print("=" * 140)
    
    # Активные циклы
    active_cycles = [(k, v) for k, v in cycles.items() if v.get('active', False)]
    active_cycles.sort(key=lambda x: x[1].get('active_step', 0), reverse=True)
    
    if not active_cycles:
        print(f"\n{Fore.RED}❌ Нет активных циклов{Style.RESET_ALL}")
        return
    
    print(f"\n{Fore.GREEN}✅ Активных циклов: {len(active_cycles)}{Style.RESET_ALL}\n")
    
    # Таблица
    header = (f"{'Валюта':<8} | {'Шаг':<4} | {'Старт':<12} | {'Текущая':<12} | "
             f"{'Δ%':<8} | {'Инвест.$':<10} | {'Текущ.$':<10} | {'P&L':<12} | {'Статус':<20}")
    print(Fore.CYAN + header + Style.RESET_ALL)
    print("-" * 140)
    
    total_invested = 0
    total_current = 0
    total_pnl = 0
    
    for currency, cycle in active_cycles:
        step = cycle.get('active_step', 0)
        start_price = cycle.get('start_price', 0)
        invested = cycle.get('total_invested_usd', 0)
        
        # Текущая цена
        current_price = prices.get(currency, cycle.get('last_buy_price', 0))
        
        # P&L
        pnl, pnl_percent, current_value = calculate_pnl(cycle, current_price)
        
        total_invested += invested
        total_current += current_value
        total_pnl += pnl
        
        # Изменение цены
        if start_price > 0:
            price_change = ((current_price - start_price) / start_price) * 100
        else:
            price_change = 0
        
        # Цвета
        if price_change > 0:
            change_color = Fore.GREEN
            change_str = f"+{price_change:.2f}%"
        else:
            change_color = Fore.RED
            change_str = f"{price_change:.2f}%"
        
        if pnl > 0:
            pnl_color = Fore.GREEN
            pnl_str = f"+${pnl:.2f} ({pnl_percent:+.2f}%)"
        else:
            pnl_color = Fore.RED
            pnl_str = f"${pnl:.2f} ({pnl_percent:.2f}%)"
        
        # Иконка шага
        if step >= 5:
            step_color = Fore.RED
            step_icon = "🔴"
        elif step >= 3:
            step_color = Fore.YELLOW
            step_icon = "🟡"
        elif step >= 1:
            step_color = Fore.CYAN
            step_icon = "🔵"
        else:
            step_color = Fore.GREEN
            step_icon = "🟢"
        
        # Статус изменений
        status = ""
        if prev_cycles and currency in prev_cycles:
            prev_step = prev_cycles[currency].get('active_step', 0)
            if step > prev_step:
                status = f"{Fore.YELLOW}⬇️ Усреднение!{Style.RESET_ALL}"
            elif step == 0 and prev_cycles[currency].get('active', False) == False:
                status = f"{Fore.GREEN}🆕 Новый цикл!{Style.RESET_ALL}"
        
        # Форматирование
        start_str = format_price(start_price)
        current_str = format_price(current_price)
        invested_str = f"${invested:.2f}"
        current_val_str = f"${current_value:.2f}"
        
        print(f"{currency:<8} | {step_color}{step_icon} {step:<2}{Style.RESET_ALL} | {start_str:<12} | {current_str:<12} | "
              f"{change_color}{change_str:<8}{Style.RESET_ALL} | {invested_str:<10} | {current_val_str:<10} | "
              f"{pnl_color}{pnl_str:<12}{Style.RESET_ALL} | {status:<20}")
    
    print("-" * 140)
    
    # Итоги
    total_pnl_percent = ((total_current - total_invested) / total_invested * 100) if total_invested > 0 else 0
    total_pnl_color = Fore.GREEN if total_pnl > 0 else Fore.RED
    
    print(f"\n{Fore.YELLOW}💰 ИТОГО:{Style.RESET_ALL}")
    print(f"  Инвестировано: ${total_invested:.2f}")
    print(f"  Текущая стоимость: ${total_current:.2f}")
    print(f"  {total_pnl_color}P&L: ${total_pnl:+.2f} ({total_pnl_percent:+.2f}%){Style.RESET_ALL}")
    
    # Сводка по шагам
    steps_count = {}
    for currency, cycle in active_cycles:
        step = cycle.get('active_step', 0)
        steps_count[step] = steps_count.get(step, 0) + 1
    
    print(f"\n{Fore.CYAN}📊 Распределение по шагам:{Style.RESET_ALL}")
    for step in sorted(steps_count.keys()):
        count = steps_count[step]
        if step == 0:
            print(f"  🟢 Шаг {step}: {count} валют")
        elif step <= 2:
            print(f"  🔵 Шаг {step}: {count} валют")
        elif step <= 4:
            print(f"  🟡 Шаг {step}: {count} валют")
        else:
            print(f"  🔴 Шаг {step}: {count} валют (РИСК!)")
    
    print("\n" + "=" * 140)
    print(f"{Fore.GREEN}✅ Мониторинг активен. Нажмите Ctrl+C для выхода.{Style.RESET_ALL}")
    print("=" * 140)

def main():
    """Основной цикл мониторинга"""
    prev_cycles = None
    
    print(f"{Fore.CYAN}🔄 Запуск live-мониторинга автотрейдера...{Style.RESET_ALL}")
    time.sleep(1)
    
    try:
        while True:
            cycles = load_cycles()
            api_status = get_api_status()
            prices = get_current_prices()
            
            print_dashboard(cycles, api_status, prices, prev_cycles)
            
            prev_cycles = cycles.copy()
            time.sleep(5)
            
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}👋 Мониторинг остановлен{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
