# ------------------------------------
# Stage 1: Build stage (نصب وابستگی‌ها)
# ------------------------------------
FROM python:3.11-slim as build-stage

# تنظیمات و نصب وابستگی‌های سیستمی مورد نیاز برای Matplotlib
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpng-dev \
        pkg-config \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

# تنظیم دایرکتوری کاری
WORKDIR /app

# کپی کردن فایل نیازمندی‌ها و نصب بسته‌های پایتون
COPY requirements.txt .
RUN pip install --upgrade pip
# نصب بسته‌ها
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------
# Stage 2: Final stage (اجرای ربات)
# ------------------------------------
FROM python:3.11-slim

# نصب وابستگی‌های سیستمی مورد نیاز در زمان اجرا (مانند فونت‌ها برای نمودار)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fontconfig \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# تنظیم دایرکتوری کاری
WORKDIR /app

# کپی کردن بسته‌های نصب‌شده از مرحله build
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
# کپی کردن کدهای برنامه
COPY . .

# تنظیم پورت بر اساس استاندارد شما و لیارا
# لیارا به طور پیش فرض از متغیر PORT استفاده می کند، اما ما آن را روی 3000 تنظیم می کنیم
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

# تعیین دستوری که پس از راه‌اندازی کانتینر اجرا می‌شود
# این دستور فایل main.py را اجرا می کند
CMD ["python", "main.py"]
