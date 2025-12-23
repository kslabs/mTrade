# Check timestamps in trade logs
$logDir = "c:\Users\Администратор\Documents\bGate.mTrade\trade_logs"

Write-Host "`nChecking timestamps in trade logs..." -ForegroundColor Cyan

$logFiles = Get-ChildItem "$logDir\*_logs.jsonl" | Where-Object { $_.Name -notlike "EXPORT_*" }

$salesWithTimestamps = 0
$salesWithoutTimestamps = 0

foreach ($file in $logFiles) {
    $currency = $file.BaseName -replace '_logs$', ''
    $lastLine = Get-Content $file.FullName -Tail 1 -ErrorAction SilentlyContinue
    
    if ($lastLine) {
        try {
            $entry = $lastLine | ConvertFrom-Json
            if ($entry.type -eq "sell") {
                $hasTimestamps = ($null -ne $entry.detection_time) -and ($null -ne $entry.completion_time)
                if ($hasTimestamps) {
                    $salesWithTimestamps++
                    Write-Host "✓ $currency : Last sale HAS timestamps" -ForegroundColor Green
                    Write-Host "  Detection: $($entry.detection_time)" -ForegroundColor Gray
                    Write-Host "  Completion: $($entry.completion_time)" -ForegroundColor Gray
                    Write-Host "  Duration: $($entry.time_from_detection)s" -ForegroundColor Gray
                } else {
                    $salesWithoutTimestamps++
                }
            }
        } catch {}
    }
}

Write-Host "`nSummary:" -ForegroundColor Yellow
Write-Host "  Sales WITH timestamps: $salesWithTimestamps" -ForegroundColor Green
Write-Host "  Sales WITHOUT timestamps: $salesWithoutTimestamps" -ForegroundColor Red

if ($salesWithTimestamps -eq 0) {
    Write-Host "`nNo sales with timestamps yet. Restart autotrader and wait for next sale." -ForegroundColor Yellow
}

Write-Host "`nDone!`n" -ForegroundColor Green
