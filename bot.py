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
    """Улучшение качества изображения для лучшего распознавания"""
    # Конвертация в grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Увеличение контраста
    gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=40)
    
    # Бинаризация
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # Удаление шума
    gray = cv2.medianBlur(gray, 3)
    
    return gray

def extract_passport_data(text):
    """Извлечение данных паспорта из текста"""
    patterns = [
        # Основной шаблон для машиносчитываемой зоны
        r'([A-Z0-9<]+)\s+([A-Z0-9<]+)\s+([A-Z0-9<]+).*?([A-Z]{3})\s+(\d{2}[A-Z]{3}\d{2})\s+([FM])\s+(\d{2}[A-Z]{3}\d{2})\s+([A-Z<]+)\s+([A-Z<]+)',
        
        # Альтернативный шаблон для случаев с меньшим количеством пробелов
        r'([A-Z0-9<]+)([A-Z0-9<]+)([A-Z0-9<]+).*?([A-Z]{3})(\d{2}[A-Z]{3}\d{2})([FM])(\d{2}[A-Z]{3}\d{2})([A-Z<]+)([A-Z<]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match
    return None

def start(update: Update, context: CallbackContext):
    help_text = (
        "📄 Отправьте мне ФОТО последних двух строк паспорта. Я преобразую их в формат AMADEUS.\n\n"
        "Требования к фото:\n"
        "- Хорошее освещение\n"
        "- Четкий текст\n"
        "- Только машиносчитываемая зона (2 строки)\n\n"
        "Пример:\n"
        "P<UZBFA0421711<1111111M1111111<<<<<<<<<<<<<<<0\n"
        "IBRAGIMOVA<<BARNO<BAKTIYAROVNA<<<<<<<<<<<<<<"
    )
    update.message.reply_text(help_text)

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
        processed_img = enhance_image(img_cv)
        
        # Распознаем текст
        text = pytesseract.image_to_string(
            processed_img,
            lang='eng+rus',
            config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789< '
        )
        
        logger.info(f"Распознанный текст:\n{text}")
        
        if not text:
            raise ValueError("Не удалось распознать текст на фото")

        # Ищем данные паспорта
        passport_data = extract_passport_data(text.replace('\n', ' '))
        
        if not passport_data:
            raise ValueError("Не удалось найти паспортные данные в распознанном тексте")
            
        # Форматируем для Amadeus
        country = passport_data.group(2)
        passport_num = passport_data.group(3)
        birth_date = passport_data.group(5)
        gender = passport_data.group(6)
        expiry_date = passport_data.group(7)
        last_name = passport_data.group(8).replace('<', '')
        first_name = passport_data.group(9).replace('<', ' ').strip()

        result = (
            f"SR DOCS YY HK1-P-{country}-{passport_num}-"
            f"{country}-{birth_date}-{gender}-"
            f"{expiry_date}-{last_name}-{first_name}"
        )
        
        update.message.reply_text(f"✅ Готово! Скопируйте:\n\n`{result}`", parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Ошибка обработки фото: {str(e)}")
        
        error_help = (
            "❌ Не удалось обработать фото. Пожалуйста:\n"
            "1. Убедитесь, что фото четкое и хорошо освещено\n"
            "2. На фото должны быть видны только 2 строки паспорта\n"
            "3. Попробуйте сделать фото под прямым углом\n\n"
            "Пример правильного фото:\n"
            "P<UZBFA0421711<1111111M1111111<<<<<<<<<<<<<<<0\n"
            "IBRAGIMOVA<<BARNO<BAKTIYAROVNA<<<<<<<<<<<<<<"
        )
        
        update.message.reply_text(error_help)

def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Ошибка в обработчике: {context.error}")
    if update.message:
        update.message.reply_text("⚠️ Произошла внутренняя ошибка. Пожалуйста, попробуйте позже.")

def main():
    updater = Updater("YOUR_TELEGRAM_TOKEN", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.photo, process_photo))
    dp.add_error_handler(error_handler)

    updater.start_polling()
    logger.info("Бот успешно запущен!")
    updater.idle()

if __name__ == '__main__':
    main()
