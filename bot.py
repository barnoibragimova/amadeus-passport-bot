import os
import re
import cv2
import pytesseract
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.error import Conflict

# Конфигурация
BOT_TOKEN = "7921805686:AAH0AJrCC0Dd6Lvb5mc3CXI9dUda_n89Y0Y"
TESSERACT_CONFIG = r'--oem 3 --psm 6 -l eng+rus'

async def enhance_image(image_path):
    """Улучшение качества изображения"""
    try:
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    except Exception as e:
        print(f"Image enhancement failed: {e}")
        return None

async def extract_text(image_path):
    """Извлечение текста из изображения"""
    try:
        processed_img = await enhance_image(image_path)
        if processed_img is None:
            return None
        return pytesseract.image_to_string(processed_img, config=TESSERACT_CONFIG)
    except Exception as e:
        print(f"Text extraction failed: {e}")
        return None

def parse_passport_data(text):
    """Парсинг данных паспорта"""
    if not text:
        return None
        
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) < 2:
        return None
        
    return {
        'line1': lines[-2],
        'line2': lines[-1]
    }

def generate_amadeus_format(data):
    """Генерация строки Amadeus"""
    try:
        # Парсинг первой строки (пример: "UZB FA0421711 UZB 29NOV86 F")
        parts1 = re.split(r'\s+', data['line1'])
        country = parts1[0] if len(parts1) > 0 else "UZB"
        dob = parts1[3] if len(parts1) > 3 else "01JAN00"
        gender = parts1[4] if len(parts1) > 4 else "F"

        # Парсинг второй строки (пример: "02JUL29 IBragimova Barno")
        parts2 = re.split(r'\s+', data['line2'], maxsplit=2)
        expiry = parts2[0] if len(parts2) > 0 else "01JAN30"
        surname = parts2[1] if len(parts2) > 1 else "SURNAME"
        given_name = parts2[2] if len(parts2) > 2 else "NAME"

        return (
            f"SR DOCS YY HK1-P-{country}-FA0421711-"
            f"{country}-{dob}-{gender}-{expiry}-"
            f"{surname.upper()}-{given_name.upper()}"
        )
    except Exception as e:
        print(f"Amadeus formatting failed: {e}")
        return None

async def handle_passport_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото паспорта"""
    try:
        # Скачивание фото
        photo_file = await update.message.photo[-1].get_file()
        temp_image = "temp_passport.jpg"
        await photo_file.download_to_drive(temp_image)
        
        # Извлечение текста
        text = await extract_text(temp_image)
        if not text:
            await update.message.reply_text("❌ Не удалось прочитать паспорт. Попробуйте другое фото.")
            return
            
        # Парсинг данных
        passport_data = parse_passport_data(text)
        if not passport_data:
            await update.message.reply_text("❌ Неверный формат паспорта. Убедитесь, что видны последние 2 строки.")
            return
            
        # Генерация формата Amadeus
        amadeus_format = generate_amadeus_format(passport_data)
        if not amadeus_format:
            await update.message.reply_text("❌ Ошибка обработки данных. Попробуйте еще раз.")
            return
            
        # Отправка результата
        await update.message.reply_text(
            f"✅ Успешно распознано:\n\n"
            f"Исходные данные:\n{passport_data['line1']}\n{passport_data['line2']}\n\n"
            f"🔹 Формат Amadeus:\n{amadeus_format}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Произошла ошибка: {str(e)}")
        
    finally:
        # Удаление временного файла
        if os.path.exists(temp_image):
            os.remove(temp_image)

async def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_passport_photo))
    
    print("Бот @Amadeus2bot запущен и готов к работе!")
    
    try:
        await app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            close_loop=False  # Важно для Render
        )
    except Conflict as e:
        print(f"⚠️ Ошибка: {e}. Остановка...")
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
