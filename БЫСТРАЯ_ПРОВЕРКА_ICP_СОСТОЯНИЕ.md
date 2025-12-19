# 🚀 Быстрая проверка: Текущее состояние ICP

## Проверить текущую цену и уровень докупки

```powershell
# Получить актуальные данные
$r = Invoke-WebRequest -Uri "http://localhost:5000/api/trade/indicators?base_currency=ICP&quote_currency=USDT"
$j = $r.Content | ConvertFrom-Json

# Показать ключевые параметры
$currentPrice = $j.indicators.price
$lastBuy = $j.autotrade_levels.last_buy_price
$rebuyLevel = $lastBuy * (1 - 0.0099)

Write-Host "=== ICP ТЕКУЩЕЕ СОСТОЯНИЕ ==="
Write-Host "Текущая цена:       $currentPrice USDT"
Write-Host "Последняя покупка:  $lastBuy USDT"
Write-Host "Уровень докупки:    $rebuyLevel USDT"
Write-Host ""
if ($currentPrice -lt $rebuyLevel) {
    Write-Host "✅ УСЛОВИЕ ДОКУПКИ ВЫПОЛНЕНО!" -ForegroundColor Green
    Write-Host "Автотрейдер должен совершить докупку на шаге 1."
} else {
    $diff = (($currentPrice - $rebuyLevel) / $rebuyLevel) * 100
    Write-Host "⏳ Ожидание падения цены..." -ForegroundColor Yellow
    Write-Host "До докупки: -$([math]::Round($diff, 2))%"
}
```

## Проверить логи докупки

```powershell
Get-Content server_debug.log -Tail 200 | Select-String -Pattern "\[BLOCK_|\[ICP\]|попытка докупки"
```

## Проверить актуальное состояние в файле

```powershell
Get-Content autotrader_cycles_state.json | ConvertFrom-Json | Select-Object -ExpandProperty ICP | Select-Object cycle_id, active_step, last_buy_price, total_invested_usd, base_volume
```

## Проверить отладочные файлы

```powershell
# Загрузка состояния при старте
Get-Content autotrader_load_debug.txt -Tail 20

# Чтение состояния в API
Get-Content get_indicators_debug.txt -Tail 20
```

---

**Быстрая справка:**
- **Last buy price:** 3.039 USDT
- **Rebuy level:** ~3.009 USDT (3.039 - 0.99%)
- **Current step:** 0
- **Next step:** 1 (при падении цены)
