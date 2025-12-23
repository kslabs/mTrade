# Анализ времени продаж - показывает статистику по длительности операций
Write-Host "`n=== АНАЛИЗ ВРЕМЕНИ ПРОДАЖ ===" -ForegroundColor Cyan

$sales = @()

Get-ChildItem ".\trade_logs\*_logs.jsonl" | Where-Object { $_.Name -notlike "EXPORT_*" } | ForEach-Object {
    $currency = $_.BaseName -replace '_logs$', ''
    Get-Content $_.FullName -Tail 20 | ForEach-Object {
        try {
            $entry = $_ | ConvertFrom-Json
            if ($entry.type -eq "sell" -and $entry.time_from_detection) {
                $sales += [PSCustomObject]@{
                    Currency = $currency
                    Time = $entry.time
                    Duration = [math]::Round($entry.time_from_detection, 2)
                    Price = $entry.price
                    Volume = $entry.volume
                }
            }
        } catch {}
    }
}

if ($sales.Count -eq 0) {
    Write-Host "`nНет продаж с временными метками" -ForegroundColor Yellow
    exit
}

Write-Host "`nВсего продаж с временными метками: $($sales.Count)" -ForegroundColor Green

Write-Host "`n=== СТАТИСТИКА ДЛИТЕЛЬНОСТИ ===" -ForegroundColor Yellow
$durations = $sales | Select-Object -ExpandProperty Duration
$avg = [math]::Round(($durations | Measure-Object -Average).Average, 2)
$min = ($durations | Measure-Object -Minimum).Minimum
$max = ($durations | Measure-Object -Maximum).Maximum

Write-Host "Средняя: $avg сек" -ForegroundColor White
Write-Host "Минимум: $min сек" -ForegroundColor Green
Write-Host "Максимум: $max сек" -ForegroundColor Red

Write-Host "`n=== ПОСЛЕДНИЕ 10 ПРОДАЖ ===" -ForegroundColor Yellow
$sales | Sort-Object Time -Descending | Select-Object -First 10 | 
    Format-Table Currency, Time, Duration, Price, Volume -AutoSize

Write-Host "`n=== ТОП-5 САМЫХ БЫСТРЫХ ===" -ForegroundColor Green
$sales | Sort-Object Duration | Select-Object -First 5 | 
    Format-Table Currency, Time, Duration, Price -AutoSize

Write-Host "`n=== ТОП-5 САМЫХ МЕДЛЕННЫХ ===" -ForegroundColor Red
$sales | Sort-Object Duration -Descending | Select-Object -First 5 | 
    Format-Table Currency, Time, Duration, Price -AutoSize

Write-Host ""
