/**
 * ui-helpers.js - UI вспомогательные функции
 * Функции для работы с модальными окнами и UI-элементами
 */

/**
 * Показать модальное окно с сообщением
 * @param {string} title - Заголовок
 * @param {string} content - Содержимое
 */
export function showMessageModal(title, content) {
  const modal = document.getElementById('messageModal');
  const modalTitle = document.getElementById('messageModalTitle');
  const modalContent = document.getElementById('messageModalContent');
  
  if (!modal || !modalTitle || !modalContent) {
    // Fallback to alert if modal not found
    alert(title + '\n\n' + content);
    return;
  }
  
  modalTitle.textContent = title;
  modalContent.textContent = content;
  modal.style.display = 'flex';
}

/**
 * Закрыть модальное окно с сообщением
 */
export function closeMessageModal() {
  const modal = document.getElementById('messageModal');
  if (modal) {
    modal.style.display = 'none';
  }
}

/**
 * Скопировать содержимое модального окна в буфер обмена
 */
export function copyMessageModalContent() {
  const modalContent = document.getElementById('messageModalContent');
  if (!modalContent) return;
  
  const text = modalContent.textContent;
  
  // Try modern clipboard API first
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      const btn = event.target;
      const originalText = btn.textContent;
      btn.textContent = '✓ Скопировано!';
      setTimeout(() => { btn.textContent = originalText; }, 1500);
    }).catch(err => {
      console.error('Clipboard API failed:', err);
      fallbackCopyText(text);
    });
  } else {
    fallbackCopyText(text);
  }
}

/**
 * Fallback для копирования текста (для старых браузеров)
 * @param {string} text - Текст для копирования
 */
function fallbackCopyText(text) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand('copy');
    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = '✓ Скопировано!';
    setTimeout(() => { btn.textContent = originalText; }, 1500);
  } catch (err) {
    console.error('Fallback copy failed:', err);
    alert('Не удалось скопировать текст');
  }
  document.body.removeChild(textarea);
}
