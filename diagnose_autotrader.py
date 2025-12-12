#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностический скрипт для проверки, почему автотрейдер не торгует
"""

import json
import sys
import os

def main():
    # Пути к файлам
    state_file = r"c:\Users\Администратор\Documents\bGate.mTrade\autotrader_cycles_state.json"
    config_file = r"c:\Users\Администратор\Documents\bGate.mTrade\app_state.json"
    
    print("=" * 80)
    print("ДИАГНОСТИКА АВТОТРЕЙДЕРА")
    print("=" * 80)
    print()
    
    # 1. Проверяем app_state.json
    print("1️⃣  ПРОВЕРКА ГЛОБАЛЬНЫХ НАСТРОЕК (app_state.json)")
    print("-" * 80)
    
    try:
        if not os.path.exists(config_file):
            print(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Файл {config_file} не найден!")
            return 1
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Проверяем активную квоту
        active_quote = config.get('active_quote_currency', 'UNKNOWN')
        print(f"  Активная котировочная валюта: {active_quote}")
        
        # Проверяем автоторговлю
        auto_trade_enabled = config.get('auto_trade_enabled', False)
        print(f"  Автоторговля включена: {auto_trade_enabled}")
        
        if not auto_trade_enabled:
            print("  ❌ ПРОБЛЕМА: Автоторговля ВЫКЛЮЧЕНА!")
            print("     Включите автоторговлю в интерфейсе или установите 'auto_trade_enabled': true")
            return 1
        
        # Проверяем разрешения на торговлю
        trading_perms = config.get('trading_permissions', {})
        enabled_currencies = [curr for curr, enabled in trading_perms.items() if enabled]
        
        print(f"  Разрешений на торговлю: {len(enabled_currencies)}/{len(trading_perms)}")
        
        if not enabled_currencies:
            print("  ❌ ПРОБЛЕМА: Нет валют с разрешением на торговлю!")
            print("     Включите хотя бы одну валюту в интерфейсе")
            return 1
        
        print(f"  Разрешённые валюты: {', '.join(enabled_currencies)}")
        print()
        
    except json.JSONDecodeError as e:
        print(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Ошибка чтения JSON в {config_file}")
        print(f"   {e}")
        return 1
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: {e}")
        return 1
    
    # 2. Проверяем autotrader_cycles_state.json
    print("2️⃣  ПРОВЕРКА СОСТОЯНИЯ ЦИКЛОВ (autotrader_cycles_state.json)")
    print("-" * 80)
    
    try:
        if not os.path.exists(state_file):
            print(f"⚠️  Файл {state_file} не найден (будет создан при первом запуске)")
            print()
        else:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            active_cycles = []
            inactive_cycles = []
            broken_cycles = []
            
            for currency in enabled_currencies:
                if currency not in state:
                    print(f"  ⚠️  {currency}: Нет данных (будет инициализирован при запуске)")
                    continue
                
                data = state[currency]
                active = data.get('active', False)
                active_step = data.get('active_step', -1)
                cycle_id = data.get('cycle_id', 0)
                total_invested = data.get('total_invested_usd', 0)
                
                if active and active_step == -1:
                    broken_cycles.append((currency, cycle_id))
                elif active:
                    active_cycles.append((currency, active_step, cycle_id, total_invested))
                else:
                    inactive_cycles.append((currency, cycle_id))
            
            if broken_cycles:
                print("  ❌ СЛОМАННЫЕ ЦИКЛЫ (active=true, active_step=-1):")
                for curr, cycle_id in broken_cycles:
                    print(f"     {curr} (cycle_id={cycle_id})")
                print("     РЕШЕНИЕ: Установите active=false для этих валют")
                print()
            
            if active_cycles:
                print(f"  ✅ АКТИВНЫЕ ЦИКЛЫ: {len(active_cycles)}")
                for curr, step, cycle_id, invested in active_cycles:
                    print(f"     {curr:8s} | step={step:2d} | cycle_id={cycle_id:3d} | invested=${invested:.2f}")
                print()
            
            if inactive_cycles:
                print(f"  💤 НЕАКТИВНЫЕ ЦИКЛЫ: {len(inactive_cycles)}")
                for curr, cycle_id in inactive_cycles:
                    print(f"     {curr:8s} | cycle_id={cycle_id:3d}")
                print()
    
    except json.JSONDecodeError as e:
        print(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Ошибка чтения JSON в {state_file}")
        print(f"   {e}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1
    
    # 3. Проверяем параметры торговли
    print("3️⃣  ПРОВЕРКА ПАРАМЕТРОВ ТОРГОВЛИ")
    print("-" * 80)
    
    try:
        breakeven_params = config.get('breakeven_params', {})
        
        if not breakeven_params:
            print("  ❌ ПРОБЛЕМА: Нет параметров торговли (breakeven_params пуст)!")
            print("     Настройте параметры для каждой валюты в интерфейсе")
            return 1
        
        print(f"  Параметры настроены для {len(breakeven_params)} валют:")
        
        for currency in enabled_currencies:
            if currency not in breakeven_params:
                print(f"  ❌ {currency}: Нет параметров!")
            else:
                params = breakeven_params[currency]
                start_volume = params.get('start_volume', 0)
                print(f"  ✅ {currency}: start_volume={start_volume} USDT")
        
        print()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1
    
    # Итоговая проверка
    print("=" * 80)
    print("ИТОГОВАЯ ПРОВЕРКА")
    print("=" * 80)
    
    checks = {
        "Автоторговля включена": auto_trade_enabled,
        "Есть разрешённые валюты": len(enabled_currencies) > 0,
        "Нет сломанных циклов": len(broken_cycles) == 0 if 'broken_cycles' in locals() else True,
        "Есть параметры торговли": len(breakeven_params) > 0 if 'breakeven_params' in locals() else False
    }
    
    all_ok = all(checks.values())
    
    for check, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {check}")
    
    print("=" * 80)
    
    if all_ok:
        print()
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print()
        print("Если автотрейдер не торгует, проверьте:")
        print("  1. Запущен ли процесс autotrader_v2.py")
        print("  2. Есть ли ошибки в консоли/логах")
        print("  3. Достаточно ли баланса USDT для начальной покупки")
        print("  4. Выполняются ли условия торговли (цены, пороги)")
        return 0
    else:
        print()
        print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
        print("   Исправьте перечисленные проблемы и запустите диагностику снова")
        return 1

if __name__ == '__main__':
    sys.exit(main())
