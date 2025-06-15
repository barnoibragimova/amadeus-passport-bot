import re
import logging
import pytesseract
import cv2
import numpy as np
from io import BytesIO
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from PIL import Image

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        '📄 Отправьте мне ФОТО последних двух строк паспорта. Я распознаю текст и преобразую в формат AMADEUS.\n\n'
        'Пример результата:\n'
        'SR DOCS YY HK1-P-UZB-FA0421711-UZB-29NOV86-F-02JUL29-IBRAGIMOVA-BARNO BAKTIYAROVNA'
    )

def process_photo(update: Update, context: CallbackContext):
    try:
        # Получаем фото
        photo_file = update.message.photo[-1].get_file()
        img_bytes = BytesIO()
        photo_file.download(out=img_bytes)
        img_bytes.seek(0)
        
        # Преобразуем в OpenCV формат
        image = Image.open(img_bytes)
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Улучшаем качество изображения
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        
        # Распознаем текст
        text = pytesseract.image_to_string(gray, lang='eng+rus')
        logger.info(f"Распознанный текст: {text}")
        
        # Ищем паспортные данные
        match = re.search(
            r'([A-Z0-9<]+)\s+([A-Z0-9<]+)\s+([A-Z0-9<]+)\s+([A-Z]{3})\s+(\d{2}[A-Z]{3}\d{2})\s+([FM])\s+(\d{2}[A-Z]{3}\d{2})\s+([A-Z<]+)\s+([A-Z<]+)',
            text
        )
        
        if not match:
            raise ValueError("Не удалось распознать паспортные данные")
            
        # Форматируем в AMADEUS
        country = match.group(2)
        passport_num = match.group(3)
        birth_date = match.group(5)
        gender = match.group(6)
        expiry_date = match.group(7)
        last_name = match.group(8).replace('<', '')
        first_name = match.group(9).replace('<', ' ').strip()
        
        result = f"SR DOCS YY HK1-P-{country}-{passport_num}-{country}-{birth_date}-{gender}-{expiry_date}-{last_name}-{first_name}"
        
        update.message.reply_text(f"✅ Готово! Копируйте:\n\n{result}")
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        update.message.reply_text('❌ Не удалось обработать фото. Убедитесь, что фото четкое и содержит две строки паспорта.')

def main():
    updater = Updater("YOUR_TELEGRAM_TOKEN", use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.photo, process_photo))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
