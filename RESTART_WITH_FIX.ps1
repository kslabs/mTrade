# КРИТИЧЕСКИЙ ПЕРЕЗАПУСК СЕРВЕРА mTrade
# Останавливает старый процесс и запускает новый с исправлениями

Write-Host "================================================================================" -ForegroundColor Yellow
Write-Host "КРИТИЧЕСКИЙ ПЕРЕЗАПУСК СЕРВЕРА" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "ВНИМАНИЕ: Сервер будет остановлен и перезапущен!" -ForegroundColor Red
Write-Host ""

$confirmation = Read-Host "Продолжить? (yes/no)"
if ($confirmation -notin @('yes', 'y', 'да', 'д')) {
    Write-Host "Отменено" -ForegroundColor Yellow
    exit
}

# Остановка процессов
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "ШАГ 1: ОСТАНОВКА СТАРОГО СЕРВЕРА" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -like "*mTrade*" -or 
    (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" | Select-Object -ExpandProperty CommandLine) -like "*mTrade.py*"
}

if ($processes) {
    Write-Host "Найдено процессов: $($processes.Count)" -ForegroundColor Yellow
    foreach ($proc in $processes) {
        Write-Host "  Остановка PID=$($proc.Id)..." -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  Ожидание завершения (3 секунды)..." -ForegroundColor Gray
    Start-Sleep -Seconds 3
    Write-Host "  ✓ Процессы остановлены" -ForegroundColor Green
} else {
    Write-Host "  ✓ Процессы mTrade не найдены" -ForegroundColor Green
}

# Проверка кода
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "ШАГ 2: ПРОВЕРКА ИСПРАВЛЕНИЙ В КОДЕ" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$autotraderPath = Join-Path $PSScriptRoot "autotrader.py"
if (Test-Path $autotraderPath) {
    $code = Get-Content $autotraderPath -Raw
    
    $checks = @{
        "Мастер-Lock в __init__" = $code -match "_locks_creation_lock = Lock\(\)"
        "Использование with _locks_creation_lock" = $code -match "with self\._locks_creation_lock:"
        "Логирование [LOCK_INIT]" = $code -match "\[LOCK_INIT\]"
    }
    
    $allOk = $true
    foreach ($check in $checks.GetEnumerator()) {
        if ($check.Value) {
            Write-Host "  ✅ $($check.Key)" -ForegroundColor Green
        } else {
            Write-Host "  ❌ $($check.Key)" -ForegroundColor Red
            $allOk = $false
        }
    }
    
    if (-not $allOk) {
        Write-Host ""
        Write-Host "❌ КРИТИЧНО: Исправления не найдены в коде!" -ForegroundColor Red
        Write-Host "Код не был изменён или файл был перезаписан!" -ForegroundColor Red
        Write-Host "НЕ ЗАПУСКАЙТЕ СЕРВЕР без исправлений!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "✅ Все исправления на месте!" -ForegroundColor Green
} else {
    Write-Host "  ❌ Файл autotrader.py не найден!" -ForegroundColor Red
    exit 1
}

# Запуск нового сервера
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "ШАГ 3: ЗАПУСК НОВОГО СЕРВЕРА" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$mtradePath = Join-Path $PSScriptRoot "mTrade.py"
if (Test-Path $mtradePath) {
    Write-Host "  🚀 Запуск mTrade с исправленным кодом..." -ForegroundColor Yellow
    
    # Запускаем в новом окне
    Start-Process python -ArgumentList $mtradePath -WindowStyle Normal
    
    Start-Sleep -Seconds 2
    
    Write-Host "  ✓ Сервер запущен" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "ПРОВЕРЬТЕ ЛОГИ СЕРВЕРА!" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Ищите сообщения:" -ForegroundColor Yellow
    Write-Host "  [LOCK_INIT][XXX] Создан новый Lock для валюты" -ForegroundColor Gray
    Write-Host "  [PROTECTION][XXX] ... УСТАНОВЛЕН И СОХРАНЁН" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Если этих сообщений нет - сообщите об этом!" -ForegroundColor Red
    Write-Host "================================================================================" -ForegroundColor Green
} else {
    Write-Host "  ❌ Файл mTrade.py не найден!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "✅ ПЕРЕЗАПУСК ЗАВЕРШЁН" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "СЛЕДУЮЩИЕ ШАГИ:" -ForegroundColor Yellow
Write-Host "1. Проверьте логи сервера на наличие [LOCK_INIT]" -ForegroundColor Gray
Write-Host "2. Проведите тест: продажа → сброс цикла → проверка покупок" -ForegroundColor Gray
Write-Host "3. Если проблема повторится - запустите диагностику:" -ForegroundColor Gray
Write-Host "   python diagnose_double_start_buy.py" -ForegroundColor Gray
Write-Host ""
