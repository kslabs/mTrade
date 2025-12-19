// === Скрипт диагностики WS для проблемных валют ===
// Вставьте в консоль браузера (F12) и выполните

console.log('=== ДИАГНОСТИКА WS ===');

const problemCurrencies = ['XRP', 'ADA', 'LINK', 'TAO', 'ANIME', 'ICP'];

console.log('\n1. Проверка глобальных переменных с ценами:');
problemCurrencies.forEach(code => {
  console.log(`${code}:`, {
    currentPrice: window.currentPrices?.[code],
    sellPrice: window.sellPrices?.[code],
    buyPrice: window.buyPrices?.[code],
    activeStep: window.activeSteps?.[code]
  });
});

console.log('\n2. Проверка вкладок:');
problemCurrencies.forEach(code => {
  const tab = document.querySelector(`.tab-item[data-code="${code}"]`);
  if (tab) {
    console.log(`${code}:`, {
      hasTab: true,
      classes: tab.className,
      isDisconnected: tab.classList.contains('ws-disconnected')
    });
  } else {
    console.log(`${code}: вкладка не найдена`);
  }
});

console.log('\n3. Проверка списка валют:');
console.log('currenciesList:', window.currenciesList);

console.log('\n=== КОНЕЦ ДИАГНОСТИКИ ===');
