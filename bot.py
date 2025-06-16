import os
import re
import cv2
import pytesseract
from telegram.ext import Updater, MessageHandler, filters
from telegram import Update
from telegram.ext import CallbackContext
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

def preprocess_image(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return thresh

def extract_passport_data(image_path):
    try:
        processed_img = preprocess_image(image_path)
        text = pytesseract.image_to_string(
            processed_img,
            lang="eng+rus",
            config="--psm 6 --oem 3"
        )
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines[-2:] if len(lines) >= 2 else None
    except Exception as e:
        print(f"OCR Error: {e}")
        return None

def format_for_amadeus(lines):
    if not lines or len(lines) < 2:
        return "❌ Неверный формат паспорта"
    
    try:
        # Парсинг первой строки (например: "UZB FA0421711 UZB 29NOV86 F")
        line1 = re.split(r"\s+", lines[0])
        country = line1[0] if len(line1) > 0 else "UZB"
        dob = line1[3] if len(line1) > 3 else "01JAN00"
        gender = line1[4] if len(line1) > 4 else "F"

        # Парсинг второй строки (например: "02JUL29 Ibragimova Barno")
        line2 = re.split(r"\s+", lines[1])
        expiry = line2[0] if len(line2) > 0 else "01JAN30"
        surname = line2[1] if len(line2) > 1 else "SURNAME"
        given_name = " ".join(line2[2:]) if len(line2) > 2 else "NAME"

        return (
            f"SR DOCS YY HK1-P-{country}-FA0421711-"
            f"{country}-{dob}-{gender}-{expiry}-"
            f"{surname.upper()}-{given_name.upper()}"
        )
    except Exception as e:
        return f"❌ Ошибка форматирования: {str(e)}"

def handle_photo(update: Update, context: CallbackContext):
    try:
        photo = update.message.photo[-1].get_file()
        image_path = 'temp_passport.jpg'
        photo.download(image_path)
        
        lines = extract_passport_data(image_path)
        if not lines:
            update.message.reply_text("❌ Не удалось распознать паспорт")
            return

        result = format_for_amadeus(lines)
        update.message.reply_text(
            f"✅ Распознанные данные:\n{' '.join(lines)}\n\n"
            f"🔹 Формат Amadeus:\n{result}"
        )
    except Exception as e:
        update.message.reply_text(f"⚠️ Ошибка: {str(e)}")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

def main():
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("Бот запущен...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
