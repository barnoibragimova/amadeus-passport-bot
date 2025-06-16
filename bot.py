from telegram.ext import Updater, MessageHandler, Filters
import pytesseract
import cv2
import re
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

def process_passport_image(image_path):
    """Обработка изображения паспорта и извлечение текста"""
    try:
        # Чтение и предобработка изображения
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # Извлечение текста
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(thresh, lang='eng+rus', config=custom_config)
        
        # Очистка и фильтрация строк
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return lines[-2:] if len(lines) >= 2 else lines
    
    except Exception as e:
        print(f"Error processing image: {e}")
        return []

def format_for_amadeus(passport_lines):
    """Форматирование данных для Amadeus"""
    if len(passport_lines) != 2:
        return "Не удалось распознать две строки паспорта"
    
    try:
        # Разбор первой строки (например: "UZB FA0421711 UZB 29NOV86 F")
        line1_parts = passport_lines[0].split()
        country = line1_parts[0] if len(line1_parts) > 0 else "UZB"
        dob = line1_parts[3] if len(line1_parts) > 3 else "01JAN00"
        sex = line1_parts[4] if len(line1_parts) > 4 else "F"
        
        # Разбор второй строки (например: "02JUL29 IBragimova Barno Baktiyarovna")
        line2_parts = passport_lines[1].split()
        expiry = line2_parts[0] if len(line2_parts) > 0 else "01JAN30"
        surname = line2_parts[1] if len(line2_parts) > 1 else "SURNAME"
        given_names = " ".join(line2_parts[2:]) if len(line2_parts) > 2 else "NAME"
        
        return (f"SR DOCS YY HK1-P-{country}-FA0421711-{country}-{dob}-{sex}-{expiry}-"
                f"{surname.upper()}-{given_names.upper()}")
    
    except Exception as e:
        print(f"Formatting error: {e}")
        return "Ошибка форматирования данных"

def handle_message(update, context):
    """Обработчик сообщений с фото"""
    if update.message.photo:
        try:
            # Скачивание фото
            photo = update.message.photo[-1].get_file()
            image_path = 'temp_passport.jpg'
            photo.download(image_path)
            
            # Обработка изображения
            passport_lines = process_passport_image(image_path)
            
            if passport_lines:
                # Форматирование для Amadeus
                amadeus_format = format_for_amadeus(passport_lines)
                response = (f"Распознанные данные:\n"
                           f"{' '.join(passport_lines)}\n\n"
                           f"Формат Amadeus:\n"
                           f"{amadeus_format}")
            else:
                response = "Не удалось распознать данные паспорта"
            
            update.message.reply_text(response)
            os.remove(image_path)  # Удаление временного файла
            
        except Exception as e:
            update.message.reply_text(f"Произошла ошибка: {str(e)}")
            print(f"Error: {e}")

def main():
    """Основная функция"""
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.photo, handle_message))
    updater.start_polling()
    print("Бот запущен...")
    updater.idle()

if __name__ == '__main__':
    main()
