FROM python:3.9-slim

# Установка Tesseract с русской и английской поддержкой
RUN apt-get update && \
    apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Настройка рабочей директории
WORKDIR /app

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Запуск бота
CMD ["python", "bot.py"]
