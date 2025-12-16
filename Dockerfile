FROM python:3.11-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# نصب بسته‌های پایتون
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    # برای matplotlib و جدیتیتایم
    libpng-dev \
    libfreetype6-dev \
    pkg-config \
    # برای جدیتیتایم (اگرچه python-is-python3 کفایت می‌کند)
    python3-dev \
    # پاکسازی
    && rm -rf /var/lib/apt/lists/*
    
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن کدهای برنامه
COPY . .

# تنظیم پورت و اجرای بدون بافر پایتون
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
