import re
import logging
import pytesseract
import cv2
import numpy as np
from io import BytesIO
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Предкомпилированные шаблоны для разных форматов паспортов
PASSPORT_PATTERNS = [
    re.compile(r'([A-Z0-9<]+)\s*([A-Z0-9<]+)\s*([A-Z0-9<]+).*?([A-Z]{2,3})\s*(\d{2}[A-Z]{3}\d{2})\s*([FM])\s*(\d{2}[A-Z]{3}\d{2})\s*([A-Z<]+)\s*([A-Z<]+)'),
    re.compile(r'([A-Z0-9<]+)([A-Z0-9<]+)([A-Z0-9<]+).*?([A-Z]{2,3})(\d{2}[A-Z]{3}\d{2})([FM])(\d{2}[A-Z]{3}\d{2})([A-Z<]+)([A-Z<]+)'),
    re.compile(r'([A-Z]{1}[A-Z0-9<]{1,9})\s*([A-Z0-9<]{1,9})\s*([A-Z0-9<]{1,14}).*?([A-Z]{2,3})\s*(\d{2}[A-Z]{3}\d{2})\s*([FM])\s*(\d{2}[A-Z]{3}\d{2})\s*([A-Z<]{1,28})\s*([A-Z<]+)')
]

def preprocess_image(image_bytes):
    """Улучшенная предобработка изображения"""
    try:
        img_array = np.frombuffer(image_bytes.getvalue(), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        # Конвертация в grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Увеличение контраста
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=40)
        
        # Бинаризация
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # Удаление шума
        gray = cv2.medianBlur(gray, 3)
        
        return gray
    except Exception as e:
        logger.error(f"Ошибка обработки изображения: {str(e)}")
        raise ValueError("Ошибка обработки изображения")

def extract_passport_data(text):
    """Улучшенное извлечение данных с проверкой форматов"""
    clean_text = text.replace('\n', ' ').replace('  ', ' ')
    
    for pattern in PASSPORT_PATTERNS:
        match = pattern.search(clean_text)
        if match:
            # Дополнительная проверка валидности данных
            if (len(match.group(5)) == 7 and len(match.group(7)) == 7:
                return match
    
    logger.warning(f"Не распознан текст: {clean_text}")
    return None

def format_amadeus(data):
    """Форматирование результата для Amadeus"""
    try:
        return (
            f"SR DOCS YY HK1-P-{data.group(2)}-{data.group(3)}-"
            f"{data.group(4)}-{data.group(5)}-{data.group(6)}-"
            f"{data.group(7)}-{data.group(8).replace('<', '')}-"
            f"{data.group(9).replace('<', ' ').strip()}"
        )
    except Exception as e:
        logger.error(f"Ошибка форматирования: {str(e)}")
        raise ValueError("Ошибка формирования результата")

async def process_photo(update: Update, context: CallbackContext):
    try:
        # Получаем фото
        photo_file = await update.message.photo[-1].get_file()
        img_bytes = BytesIO()
        await photo_file.download(out=img_bytes)
        img_bytes.seek(0)
        
        # Обработка изображения
        processed_img = preprocess_image(img_bytes)
        
        # Распознавание текста с разными параметрами
        text = ""
        for config in ['--psm 6', '--psm 11']:
            text = pytesseract.image_to_string(
                processed_img,
                lang='eng+rus',
                config=f'{config} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
            )
            if any(c.isalpha() for c in text):
                break
        
        logger.info(f"Распознанный текст: {text}")
        
        if not any(c.isalpha() for c in text):
            raise ValueError("Не удалось распознать текст")
            
        # Извлечение данных
        data = extract_passport_data(text)
        if not data:
            raise ValueError("Не найдены паспортные данные")
            
        # Форматирование результата
        result = format_amadeus(data)
        
        await update.message.reply_text(f"✅ Результат:\n\n`{result}`", parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Ошибка обработки: {str(e)}")
        
        # Сохраняем проблемное фото для анализа
        try:
            with open("last_error_photo.jpg", "wb") as f:
                f.write(img_bytes.getvalue())
        except:
            pass
        
        await update.message.reply_text(
            "❌ Не удалось обработать фото. Пожалуйста:\n"
            "1. Убедитесь, что фото содержит ТОЛЬКО 2 строки паспорта\n"
            "2. Текст должен быть четким и горизонтальным\n"
            "3. Попробуйте сделать фото при лучшем освещении\n\n"
            "Пример правильного фото:\n"
            "P<UZBFA0421711<1111111M1111111<<<<<<<<<<<<<<<0\n"
            "IBRAGIMOVA<<BARNO<BAKTIYAROVNA<<<<<<<<<<<<<<\n\n"
            "Отправьте /help для подробной инструкции"
        )

async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "📘 Инструкция по использованию:\n\n"
        "1. Сфотографируйте ТОЛЬКО 2 строки машиносчитываемой зоны паспорта\n"
        "2. Убедитесь, что:\n"
        "   - Весь текст четко виден\n"
        "   - Нет бликов и теней\n"
        "   - Фото сделано прямо, без наклона\n"
        "3. Отправьте фото боту\n\n"
        "Пример правильного фото:\n"
        "P<UZBFA0421711<1111111M1111111<<<<<<<<<<<<<<<0\n"
        "IBRAGIMOVA<<BARNO<BAKTIYAROVNA<<<<<<<<<<<<<<\n\n"
        "Если бот не распознает данные, попробуйте:\n"
        "- Перефотографировать при другом освещении\n"
        -"Обрезать лишние части фото\n"
        -"Отправить фото еще раз"
    )
    await update.message.reply_text(help_text)

def main():
    # Инициализация бота с вашим токеном
    application = Updater("7921805686:AAH0AJrCC0Dd6Lvb5mc3CXI9dUda_n89Y0Y")
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", help_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(Filters.PHOTO, process_photo))
    
    # Запуск бота
    application.start_polling()
    logger.info("Бот запущен в улучшенном режиме!")
    application.idle()

if __name__ == '__main__':
    main()
