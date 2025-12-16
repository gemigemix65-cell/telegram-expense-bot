# ------------------------------------
# Stage 1: Build stage (نصب بسته‌های پایتون)
# ------------------------------------
# استفاده از یک ایمیج پایه که از قبل شامل کروم و درایور آن است.
# این ایمیج بر پایه Debian است و کروم و ChromeDriver را به صورت پیش‌فرض نصب شده دارد.
FROM selenium/standalone-chrome:latest as build-stage

# نصب Python 3.11 و pip
RUN apt-get update && apt-get install -y python3.11 python3-pip --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن و نصب نیازمندی‌های پایتون
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt

# ------------------------------------
# Stage 2: Final stage (اجرای ربات)
# ------------------------------------
# استفاده از ایمیج پایه Selenium برای مرحله اجرا
FROM selenium/standalone-chrome:latest

# نصب Python 3.11 و وابستگی‌های مورد نیاز
RUN apt-get update && apt-get install -y python3.11 python3-pip --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن بسته‌های پایتون نصب شده از مرحله قبل
COPY --from=build-stage /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build-stage /usr/lib/python3/dist-packages /usr/lib/python3/dist-packages

# کپی کردن کدهای برنامه
COPY . /app
WORKDIR /app

# تنظیم متغیر محیطی برای دسترسی مستقیم به ChromeDriver (برای اجرای Headless)
# مسیر پیش‌فرض ChromeDriver در این ایمیج‌ها /usr/bin/ است
ENV PATH="/usr/bin/:${PATH}"

# تنظیم پورت و اجرای بدون بافر پایتون
ENV PORT=3000
ENV PYTHONUNBUFFERED=1

# تعیین دستوری که پس از راه‌اندازی کانتینر اجرا می‌شود
CMD ["python3", "main.py"]
