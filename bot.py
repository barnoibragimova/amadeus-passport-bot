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
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def enhance_image(image):
    """Улучшение качества изображения"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    gray = cv2.medianBlur(gray, 3)
    return gray

def extract_passport_data(text):
    """Извлечение данных паспорта с несколькими шаблонами"""
    patterns = [
        r'([A-Z0-9<]+)\s+([A-Z0-9<]+)\s+([A-Z0-9<]+).*?([A-Z]{3})\s+(\d{2}[A-Z]{3}\d{2})\s+([FM])\s+(\d{2}[A-Z]{3}\d{2})\s+([A-Z<]+)\s+([A-Z<]+)',
        r'([A-Z0-9<]+)([A-Z0-9<]+)([A-Z0-9<]+).*?([A-Z]{3})(\d{2}[A-Z]{3}\d{2})([FM])(\d{2}[A-Z]{3}\d{2})([A-Z<]+)([A-Z<]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.replace('\n', ' '))
        if match:
            return match
    return None

def start(update: Update, context: CallbackContext):
    help_text = (
        "🛂 Отправьте фото двух строк машиносчитываемой зоны паспорта.\n\n"
        "Пример правильного фото:\n"
        "P<UZBFA0421711<1111111M1111111<<<<<<<<<<<<<<<0\n"
        "IBRAGIMOVA<<BARNO<BAKTIYAROVNA<<<<<<<<<<<<<<\n\n"
        "Требования:\n"
        "- Хорошее освещение\n"
        -"Четкий текст\n"
        -"Только 2 строки паспорта"
    )
    update.message.reply_text(help_text)

def process_photo(update: Update, context: CallbackContext):
    try:
        # Получаем фото
        photo_file = update.message.photo[-1].get_file()
        img_bytes = BytesIO()
        photo_file.download(out=img_bytes)
        img_bytes.seek(0)
        
        # Обработка изображения
        image = Image.open(img_bytes)
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        processed_img = enhance_image(img_cv)
        
        # Распознавание текста
        text = pytesseract.image_to_string(
            processed_img, 
            lang='eng+rus',
            config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
        )
        
        logger.info(f"Распознанный текст: {text}")
        
        if not text:
            raise ValueError("Текст не распознан")
            
        # Извлечение данных
        data = extract_passport_data(text)
        if not data:
            raise ValueError("Не найдены паспортные данные")
            
        # Форматирование результата
        result = (
            f"SR DOCS YY HK1-P-{data.group(2)}-{data.group(3)}-"
            f"{data.group(4)}-{data.group(5)}-{data.group(6)}-"
            f"{data.group(7)}-{data.group(8).replace('<', '')}-"
            f"{data.group(9).replace('<', ' ').strip()}"
        )
        
        update.message.reply_text(f"✅ Результат:\n\n`{result}`", parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        update.message.reply_text(
            "❌ Ошибка обработки. Пожалуйста:\n"
            "1. Убедитесь, что фото четкое\n"
            "2. Видны только 2 строки паспорта\n"
            "3. Нет бликов и теней\n\n"
            "Попробуйте еще раз или отправьте /start для инструкций"
        )

def main():
    updater = Updater("7921805686:AAH0AJrCC0Dd6Lvb5mc3CXI9dUda_n89Y0Y", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.photo, process_photo))

    updater.start_polling()
    logger.info("Бот запущен и готов к работе!")
    updater.idle()

if __name__ == '__main__':
    main()
