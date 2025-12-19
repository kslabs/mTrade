# Check timestamps in trade logs
$logDir = "c:\Users\Администратор\Documents\bGate.mTrade\trade_logs"

Write-Host "Checking timestamps..." -ForegroundColor Cyan

$count = 0
Get-ChildItem "$logDir\*_logs.jsonl" | Where-Object { $_.Name -notlike "EXPORT_*" } | ForEach-Object {
    $currency = $_.BaseName -replace '_logs$', ''
    $lastLine = Get-Content $_.FullName -Tail 1 -ErrorAction SilentlyContinue
    
    if ($lastLine) {
        try {
            $entry = $lastLine | ConvertFrom-Json
            if ($entry.type -eq "sell") {
                if ($entry.detection_time) {
                    $count++
                    Write-Host "$currency : HAS timestamps" -ForegroundColor Green
                    Write-Host "  Detect: $($entry.detection_time)" -ForegroundColor Gray
                    Write-Host "  Complete: $($entry.completion_time)" -ForegroundColor Gray
                    Write-Host "  Duration: $($entry.time_from_detection)s" -ForegroundColor Gray
                }
            }
        } catch {}
    }
}

if ($count -eq 0) {
    Write-Host "No sales with timestamps yet." -ForegroundColor Yellow
    Write-Host "Restart autotrader and wait for next sale." -ForegroundColor Yellow
} else {
    Write-Host "Found $count sales with timestamps!" -ForegroundColor Green
}
