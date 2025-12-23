# 🚀 БЫСТРЫЙ СТАРТ: Диагностика нулевых логов

## Одной командой

```powershell
# 1. Добавить диагностику (если ещё не добавлена)
python add_detailed_diagnostics.py

# 2. Перезапустить autotrader.py
# Ctrl+C в окне с autotrader.py, затем:
python autotrader.py

# 3. Мониторить (в новом окне)
python monitor_diagnostics.py
```

---

## Быстрая проверка

### Есть ли проблема?
```powershell
python check_zero_logs.py
```
→ Покажет статистику нулевых значений

### Запущены ли процессы?
```powershell
python check_processes_status.py
```
→ Покажет статус и рекомендации

---

## Что ждать в мониторинге

### ✅ Всё хорошо:
```
[DIAG_LOG_BUY][XRP] real_decrease_step_pct=3.84, real_cumulative_drop_pct=10.71
[DIAG_LOG_BUY][XRP] last_buy=2.60000000, start_price=2.80000000
```

### ⚠️ Проблема:
```
[DIAG_LOG_BUY][ADA] real_decrease_step_pct=0.00, real_cumulative_drop_pct=0.00
[DIAG_LOG_BUY][ADA] last_buy=0.00000000, start_price=0.00000000
```

---

## Если проблема не решена

```powershell
# Проверить файлы состояния
python diagnose_zero_logs.py

# Исправить состояние
python fix_cycles_prices.py
```

---

## Полная документация
📖 Читать: `ZERO_LOGS_FINAL_SUMMARY.md`
