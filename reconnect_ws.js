// === Скрипт переподключения WS для проблемных валют ===
// Вставьте в консоль браузера (F12) и выполните

async function reconnectProblemCurrencies() {
  const problemCurrencies = ['XRP', 'ADA', 'LINK', 'TAO', 'ANIME', 'ICP'];
  
  console.log('🔄 Начинаем переподключение проблемных валют...');
  
  for (const code of problemCurrencies) {
    try {
      console.log(`🔄 Переподключаем ${code}...`);
      
      // Используем глобальную функцию subscribeToPairData
      if (typeof subscribeToPairData === 'function') {
        await subscribeToPairData(code, 'USDT');
        console.log(`✅ ${code} переподключен`);
      } else {
        console.error(`❌ Функция subscribeToPairData не найдена`);
        break;
      }
      
      // Пауза между подключениями
      await new Promise(resolve => setTimeout(resolve, 500));
      
    } catch (e) {
      console.error(`❌ Ошибка при переподключении ${code}:`, e);
    }
  }
  
  console.log('✅ Переподключение завершено. Подождите 2-3 секунды и проверьте вкладки.');
}

// Запускаем переподключение
reconnectProblemCurrencies();
