FROM python:3.11-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# نصب ابزارهای لازم برای کامپایل برخی پکیج‌ها
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل نیازمندی‌ها
COPY requirements.txt .

# نصب پکیج‌ها با اطمینان از عدم استفاده از کش قدیمی
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن بقیه کدها
COPY . .

# تنظیم پورت لیارا
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
