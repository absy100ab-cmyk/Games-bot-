FROM python:3.11-slim

# تثبيت ffmpeg ومكتبات الصور
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libjpeg-dev \
    zlib1g-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# تثبيت مكتبات بايثون
RUN pip install --no-cache-dir \
    python-telegram-bot==20.7 \
    Pillow==10.2.0 \
    moviepy==1.0.3

# نسخ الكود
COPY bot.py .

# تشغيل البوت
CMD ["python", "bot.py"]
