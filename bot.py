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

# Шаблоны для узбекских паспортов
UZ_PASSPORT_PATTERNS = [
    re.compile(r'P<([A-Z]{3})([A-Z<]+)<<([A-Z<]+)<([A-Z<]+)<<*'),
    re.compile(r'([A-Z0-9<]{9})([0-9]{1})([A-Z]{3})([0-9]{6})([MF])([0-9]{6})')
]

def find_mrz_zone(image):
    """Автоматическое обнаружение машиносчитываемой зоны"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Ищем контуры текстовых блоков
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        x, y, w, h = cv2.boundingRect(cnt)
        roi = image[y:y+h, x:x+w]
        text = pytesseract.image_to_string(roi, config='--psm 6')
        
        if "P<" in text and len(text.split('\n')) >= 2:
            return roi
    
    # Если не нашли, возвращаем нижнюю часть изображения
    return image[-150:]

def preprocess_for_mrz(image):
    """Специальная обработка для MRZ"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return gray

def parse_uzbek_passport(text):
    """Парсинг specifically для узбекских паспортов"""
    lines = [line for line in text.split('\n') if len(line) > 10]
    
    if len(lines) < 2:
        return None
    
    # Первая строка MRZ
    line1 = lines[0].replace(' ', '')
    # Вторая строка MRZ
    line2 = lines[1].replace(' ', '')
    
    # Парсим первую строку
    m1 = UZ_PASSPORT_PATTERNS[0].search(line1)
    if not m1:
        return None
    
    # Парсим вторую строку
    m2 = UZ_PASSPORT_PATTERNS[1].search(line2)
    if not m2:
        return None
    
    return {
        'country_code': m1.group(1),
        'surname': m1.group(2).replace('<', ' ').strip(),
        'given_names': m1.group(3).replace('<', ' ').strip(),
        'passport_number': m2.group(1),
        'birth_date': f"{m2.group(4)[4:6]}{m2.group(4)[2:4]}{m2.group(4)[0:2]}",
        'sex': 'F' if m2.group(5) == 'F' else 'M',
        'expiry_date': f"{m2.group(6)[4:6]}{m2.group(6)[2:4]}{m2.group(6)[0:2]}"
    }

async def process_photo(update: Update, context: CallbackContext):
    try:
        # Получаем фото
        photo_file = await update.message.photo[-1].get_file()
        img_bytes = BytesIO()
        await photo_file.download(out=img_bytes)
        img_bytes.seek(0)
        
        # Конвертируем в OpenCV формат
        img_array = np.frombuffer(img_bytes.getvalue(), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        # Находим MRZ зону
        mrz_zone = find_mrz_zone(img)
        processed = preprocess_for_mrz(mrz_zone)
        
        # Распознаем текст
        text = pytesseract.image_to_string(
            processed,
            lang='eng',
            config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
        )
        
        logger.info(f"Распознанный MRZ:\n{text}")
        
        # Парсим данные
        data = parse_uzbek_passport(text)
        if not data:
            raise ValueError("Не удалось распознать данные паспорта")
        
        # Форматируем для Amadeus
        result = (
            f"SR DOCS YY HK1-P-{data['country_code']}-{data['passport_number']}-"
            f"{data['country_code']}-{data['birth_date']}-{data['sex']}-"
            f"{data['expiry_date']}-{data['surname']}-{data['given_names']}"
        )
        
        await update.message.reply_text(f"✅ Успешно распознано:\n\n`{result}`", parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await update.message.reply_text(
            "❌ Не удалось обработать паспорт. Пожалуйста:\n"
            "1. Сфотографируйте ТОЛЬКО нижнюю часть страницы с 2 строками\n"
            "2. Убедитесь, что текст четко виден\n"
            "3. Отправьте фото еще раз\n\n"
            "Пример правильного фото:\n"
            "P<UZBANVARJONOV<<BOBURJON<SARVAROVICH<<<<<<<<\n"
            "FB11488013UZB1505122M30052135120515657003468"
        )

async def send_instructions(update: Update, context: CallbackContext):
    instructions = (
        "📘 Инструкция для узбекских паспортов:\n\n"
        "1. Откройте страницу с фото\n"
        "2. Сфотографируйте ТОЛЬКО нижнюю часть с 2 строками\n"
        "3. Убедитесь, что текст четкий и не обрезан\n\n"
        "Пример правильного фото:\n"
        "P<UZBANVARJONOV<<BOBURJON<SARVAROVICH<<<<<<<<\n"
        "FB11488013UZB1505122M30052135120515657003468\n\n"
        "Отправьте фото паспорта сейчас"
    )
    await update.message.reply_text(instructions)

def main():
    application = Updater("7921805686:AAH0AJrCC0Dd6Lvb5mc3CXI9dUda_n89Y0Y")
    
    application.add_handler(CommandHandler("start", send_instructions))
    application.add_handler(CommandHandler("help", send_instructions))
    application.add_handler(MessageHandler(Filters.photo, process_photo))
    
    application.start_polling()
    logger.info("Бот для узбекских паспортов запущен!")
    application.idle()

if __name__ == '__main__':
    main()
