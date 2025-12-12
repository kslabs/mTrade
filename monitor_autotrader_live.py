#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для мониторинга работы автотрейдера в реальном времени
"""

import time
import json
import os
import sys
from datetime import datetime
from collections import defaultdict

STATE_FILE = r"c:\Users\Администратор\Documents\bGate.mTrade\autotrader_cycles_state.json"
CONFIG_FILE = r"c:\Users\Администратор\Documents\bGate.mTrade\app_state.json"

def load_state():
    """Загрузить состояние циклов"""
    try:
        if not os.path.exists(STATE_FILE):
            return {}
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def load_config():
    """Загрузить конфигурацию"""
    try:
        if not os.path.exists(CONFIG_FILE):
            return {}
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def get_enabled_currencies():
    """Получить список разрешённых валют"""
    config = load_config()
    perms = config.get('trading_permissions', {})
    return [curr for curr, enabled in perms.items() if enabled]

def monitor_loop():
    """Главный цикл мониторинга"""
    print("=" * 100)
    print("МОНИТОРИНГ АВТОТРЕЙДЕРА (LIVE)")
    print("=" * 100)
    print()
    print("Нажмите Ctrl+C для выхода")
    print()
    
    # Сохраняем предыдущее состояние для отслеживания изменений
    prev_state = load_state()
    prev_modified = os.path.getmtime(STATE_FILE) if os.path.exists(STATE_FILE) else 0
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            now = datetime.now().strftime("%H:%M:%S")
            
            # Проверяем, изменился ли файл состояния
            curr_modified = os.path.getmtime(STATE_FILE) if os.path.exists(STATE_FILE) else 0
            
            if curr_modified > prev_modified:
                # Файл изменился!
                curr_state = load_state()
                
                print(f"\n{'='*100}")
                print(f"[{now}] ОБНОВЛЕНИЕ #{iteration}")
                print(f"{'='*100}")
                
                # Ищем изменения
                enabled_currencies = get_enabled_currencies()
                
                changes = []
                for curr in enabled_currencies:
                    prev = prev_state.get(curr, {})
                    current = curr_state.get(curr, {})
                    
                    # Проверяем изменения
                    if prev.get('active') != current.get('active'):
                        changes.append(f"{curr}: active {prev.get('active')} → {current.get('active')}")
                    
                    if prev.get('active_step') != current.get('active_step'):
                        changes.append(f"{curr}: step {prev.get('active_step', -1)} → {current.get('active_step', -1)}")
                    
                    if prev.get('cycle_id') != current.get('cycle_id'):
                        changes.append(f"{curr}: cycle_id {prev.get('cycle_id', 0)} → {current.get('cycle_id', 0)}")
                    
                    if abs(prev.get('total_invested_usd', 0) - current.get('total_invested_usd', 0)) > 0.01:
                        changes.append(f"{curr}: invested ${prev.get('total_invested_usd', 0):.2f} → ${current.get('total_invested_usd', 0):.2f}")
                
                if changes:
                    print("\n🔔 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ:")
                    for change in changes:
                        print(f"  • {change}")
                else:
                    print("\n⏱️  Файл изменён, но значимых изменений не обнаружено")
                
                # Показываем текущее состояние
                print("\n📊 ТЕКУЩЕЕ СОСТОЯНИЕ:")
                active_count = 0
                inactive_count = 0
                
                for curr in enabled_currencies:
                    data = curr_state.get(curr, {})
                    active = data.get('active', False)
                    step = data.get('active_step', -1)
                    invested = data.get('total_invested_usd', 0)
                    
                    if active:
                        active_count += 1
                        print(f"  ✅ {curr:8s} | step={step:2d} | invested=${invested:.2f}")
                    else:
                        inactive_count += 1
                        print(f"  💤 {curr:8s} | inactive")
                
                print(f"\nАктивных: {active_count}, Неактивных: {inactive_count}")
                
                # Обновляем предыдущее состояние
                prev_state = curr_state
                prev_modified = curr_modified
            else:
                # Файл не изменился
                if iteration % 10 == 1:  # Показываем каждые 10 секунд
                    print(f"[{now}] Ожидание изменений... (итерация #{iteration})")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*100)
        print("МОНИТОРИНГ ОСТАНОВЛЕН")
        print("="*100)
        return 0

if __name__ == '__main__':
    sys.exit(monitor_loop())
