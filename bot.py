import os
import re
import cv2
import pytesseract
from telegram.ext import Updater, MessageHandler, Filters
from dotenv import load_dotenv

# Загрузка токена из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

def preprocess_image(image_path):
    """Улучшение качества изображения для OCR"""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return thresh

def extract_passport_data(image_path):
    """Извлечение текста из паспорта"""
    try:
        processed_img = preprocess_image(image_path)
        text = pytesseract.image_to_string(
            processed_img,
            lang="eng+rus",
            config="--psm 6 --oem 3"
        )
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines[-2:]  # Последние 2 строки
    except Exception as e:
        print(f"OCR Error: {e}")
        return None

def parse_passport_lines(lines):
    """Парсинг данных паспорта"""
    if not lines or len(lines) < 2:
        return None
        
    # Первая строка (например: "UZB FA0421711 UZB 29NOV86 F")
    line1 = re.split(r"\s+", lines[0])
    country = line1[0] if len(line1) > 0 else "UZB"
    dob = line1[3] if len(line1) > 3 else ""
    gender = line1[4] if len(line1) > 4 else "F"

    # Вторая строка (например: "02JUL29 IBragimova Barno Baktiyarovna")
    line2 = re.split(r"\s+", lines[1], maxsplit=2)
    expiry = line2[0] if len(line2) > 0 else ""
    surname = line2[1] if len(line2) > 1 else ""
    given_name = line2[2] if len(line2) > 2 else ""

    return {
        "country": country,
        "dob": dob,
        "gender": gender,
        "expiry": expiry,
        "surname": surname.upper(),
        "given_name": given_name.upper()
    }

def generate_amadeus_format(data):
    """Генерация строки для Amadeus"""
    return (
        f"SR DOCS YY HK1-P-{data['country']}-FA0421711-"
        f"{data['country']}-{data['dob']}-{data['gender']}-"
        f"{data['expiry']}-{data['surname']}-{data['given_name']}"
    )

async def handle_photo(update, context):
    """Обработчик фотографий"""
    try:
        # Скачивание фото
        photo_file = await update.message.photo[-1].get_file()
        image_path = "temp_passport.jpg"
        await photo_file.download_to_drive(image_path)
        
        # Обработка изображения
        lines = extract_passport_data(image_path)
        if not lines:
            await update.message.reply_text("❌ Не удалось прочитать паспорт")
            return

        # Парсинг данных
        passport_data = parse_passport_lines(lines)
        if not passport_data:
            await update.message.reply_text("❌ Неверный формат паспорта")
            return

        # Форматирование для Amadeus
        amadeus_format = generate_amadeus_format(passport_data)
        
        # Отправка результата
        await update.message.reply_text(
            f"✅ Данные паспорта:\n"
            f"{' '.join(lines)}\n\n"
            f"🔹 Формат Amadeus:\n"
            f"{amadeus_format}"
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

def main():
    """Запуск бота"""
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))
    
    print("Бот запущен...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
