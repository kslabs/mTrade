# Анализ размеров функций в app.js

$functions = @(
    @{Name='updateVisualIndicatorScale'; Start=289; End=402},
    @{Name='updateNetworkUI'; Start=403; End=416},
    @{Name='setNetworkConnectionState'; Start=417; End=431},
    @{Name='loadNetworkMode'; Start=432; End=455},
    @{Name='loadCurrenciesFromServer'; Start=456; End=477},
    @{Name='forceApplyInactiveColors'; Start=478; End=537},
    @{Name='loadTradingPermissions'; Start=538; End=557},
    @{Name='toggleTradingPermission'; Start=558; End=589},
    @{Name='renderCurrencyTabs'; Start=590; End=666},
    @{Name='updatePairNameUI'; Start=667; End=678},
    @{Name='updateTabsPermissionsUI'; Start=679; End=828},
    @{Name='switchBaseCurrency'; Start=829; End=853},
    @{Name='changeQuoteCurrency'; Start=854; End=870},
    @{Name='switchQuoteCurrency'; Start=871; End=893},
    @{Name='loadPairParams'; Start=894; End=962},
    @{Name='updateCurrencyTabWSStatus'; Start=963; End=976},
    @{Name='subscribeToPairData'; Start=977; End=1011},
    @{Name='loadMarketData'; Start=1012; End=1057},
    @{Name='editQuoteBalance'; Start=1058; End=1062},
    @{Name='loadTestBalance'; Start=1063; End=1063},
    @{Name='updateHeaderQuoteBalance'; Start=1066; End=1086},
    @{Name='loadPerBaseIndicators'; Start=1087; End=1102},
    @{Name='loadAllIndicators'; Start=1103; End=1133},
    @{Name='loadPairBalances'; Start=1134; End=1161},
    @{Name='renderBreakEvenTable'; Start=1162; End=1249},
    @{Name='loadBreakEvenTable'; Start=1250; End=1375},
    @{Name='loadTradeParams'; Start=1376; End=1424},
    @{Name='saveTradeParams'; Start=1425; End=1476},
    @{Name='switchNetworkMode'; Start=1477; End=1537},
    @{Name='toggleNetworkMode'; Start=1538; End=1545},
    @{Name='switchTradingMode'; Start=1546; End=1578},
    @{Name='updateTradingModeUI'; Start=1579; End=1600},
    @{Name='loadTradingMode'; Start=1601; End=1619},
    @{Name='toggleAutoTrade'; Start=1620; End=1647},
    @{Name='updateAutoTradeUI'; Start=1648; End=1660},
    @{Name='loadUIState'; Start=1661; End=1739},
    @{Name='openCurrencyManager'; Start=1740; End=1740},
    @{Name='closeCurrencyManager'; Start=1741; End=1741},
    @{Name='showEmojiPicker'; Start=1753; End=1772},
    @{Name='showEmojiPickerFallback'; Start=1773; End=1795},
    @{Name='selectEmoji'; Start=1796; End=1805},
    @{Name='selectCustomEmoji'; Start=1806; End=1812},
    @{Name='closeEmojiPicker'; Start=1813; End=1818},
    @{Name='buildCurrencyManagerRows'; Start=1819; End=1819},
    @{Name='addCurrencyRow'; Start=1820; End=1820},
    @{Name='deleteCurrencyRow'; Start=1821; End=1821},
    @{Name='saveCurrenciesList'; Start=1822; End=1824},
    @{Name='syncCurrenciesFromGateIO'; Start=1825; End=1858},
    @{Name='updateSyncInfo'; Start=1859; End=1895},
    @{Name='subscribeToAllCurrencies'; Start=1896; End=1918},
    @{Name='handleServerRestart'; Start=1919; End=1932},
    @{Name='handleServerShutdown'; Start=1933; End=1948},
    @{Name='fetchServerStatusOnce'; Start=1949; End=1964},
    @{Name='startUptimeLoops'; Start=1965; End=1980},
    @{Name='handleBuyMinOrder'; Start=1981; End=2014},
    @{Name='handleSellAll'; Start=2015; End=2096},
    @{Name='initApp'; Start=2097; End=2191},
    @{Name='handleResetCycle'; Start=2192; End=2223},
    @{Name='handleResumeCycle'; Start=2224; End=2298}
)

Write-Host "=== АНАЛИЗ РАЗМЕРОВ ФУНКЦИЙ В app.js ===" -ForegroundColor Cyan
Write-Host ""

$results = @()
foreach ($func in $functions) {
    $size = $func.End - $func.Start + 1
    $results += [PSCustomObject]@{
        Name = $func.Name
        Size = $size
        Line = $func.Start
    }
}

Write-Host "=== ТОП-30 САМЫХ БОЛЬШИХ ФУНКЦИЙ ===" -ForegroundColor Yellow
Write-Host ""
$top30 = $results | Sort-Object -Property Size -Descending | Select-Object -First 30
$top30 | ForEach-Object {
    $color = if ($_.Size -gt 100) { "Red" } elseif ($_.Size -gt 50) { "Yellow" } else { "Green" }
    $bar = "█" * [Math]::Min(40, [Math]::Floor($_.Size / 3))
    Write-Host ("{0,4} строк │ {1,-35} │ строка {2,4} │ {3}" -f $_.Size, $_.Name, $_.Line, $bar) -ForegroundColor $color
}

Write-Host ""
Write-Host "=== СТАТИСТИКА ===" -ForegroundColor Cyan
Write-Host "Всего функций: $($results.Count)" -ForegroundColor White
Write-Host "Средний размер: $([Math]::Round(($results | Measure-Object -Property Size -Average).Average, 1)) строк" -ForegroundColor White
Write-Host "Самая большая: $($top30[0].Name) ($($top30[0].Size) строк)" -ForegroundColor Red
Write-Host "Функций > 100 строк: $(($results | Where-Object { $_.Size -gt 100 }).Count)" -ForegroundColor Red
Write-Host "Функций > 50 строк: $(($results | Where-Object { $_.Size -gt 50 }).Count)" -ForegroundColor Yellow
Write-Host "Функций > 20 строк: $(($results | Where-Object { $_.Size -gt 20 }).Count)" -ForegroundColor Green
