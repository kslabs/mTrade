#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Помощник для перезапуска autotrader.py после применения исправлений
"""
import subprocess
import sys

print("=" * 80)
print("🔄 ПЕРЕЗАПУСК AUTOTRADER.PY")
print("=" * 80)
print()

print("📋 ВАЖНО:")
print("   Логирование идёт в КОНСОЛЬ, а не в файлы!")
print("   Вы должны увидеть:")
print("   - [DIAG_LOG_*] сообщения")
print("   - ⚡ INITIALIZED start_price")
print("   - ⚡ Using start_price for step_pct")
print()
print("=" * 80)
print()

# Проверяем запущенные процессы
print("1️⃣  Проверка запущенных процессов...")
try:
    result = subprocess.run(
        ['powershell', '-Command', 
         "Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.Path -like '*python*'} | Select-Object Id, StartTime"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.stdout.strip() and 'Id' in result.stdout:
        print("   ⚠️  Найдены запущенные Python процессы:")
        print(result.stdout)
        print()
        print("   🛑 ДЕЙСТВИЯ:")
        print("      1. Найдите окно терминала с autotrader.py")
        print("      2. Нажмите Ctrl+C для остановки")
        print("      3. Запустите: python autotrader.py")
        print()
        print("   Или принудительно:")
        print("      Get-Process python | Stop-Process -Force")
        print("      python autotrader.py")
    else:
        print("   ✅ Python процессы не запущены")
        print()
        print("   🚀 Запустите:")
        print("      python autotrader.py")
except Exception as e:
    print(f"   ⚠️  Ошибка проверки: {e}")
    print("   Проверьте вручную через диспетчер задач")

print()
print("=" * 80)
print()

print("2️⃣  После запуска autotrader.py:")
print("   ✅ Следите за консолью (НЕ за файлами логов!)")
print("   ✅ Ищите сообщения [DIAG_LOG_*]")
print("   ✅ Ищите сообщения ⚡ INITIALIZED")
print()

print("=" * 80)
print()

print("3️⃣  Проверка результатов:")
print("   После первых сделок проверьте:")
print("   - ↓Δ% и ↓% должны быть ненулевыми для BUY")
print("   - ↑Δ% и PnL должны быть ненулевыми для SELL")
print()

print("=" * 80)
print()

print("📖 Полная инструкция:")
print("   ENHANCED_FIX_APPLIED.md")
print()

print("=" * 80)
