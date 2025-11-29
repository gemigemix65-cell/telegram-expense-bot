# استفاده از ایمیج پایه رسمی پایتون 3.11 (یا هر نسخه دیگری که نیاز دارید)
FROM python:3.11-slim

# تنظیم متغیرهای محیطی برای عملکرد بهتر (اختیاری)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# ایجاد دایرکتوری کار برای اپلیکیشن
WORKDIR /app

# کپی کردن فایل نیازمندی‌ها (requirements.txt) به دایرکتوری کار
# این کار کمک می‌کند تا در صورت تغییر نکردن سورس کد، نصب پکیج‌ها کش (cache) شود
COPY requirements.txt /app/

# نصب پکیج‌های پایتون با پرهیز از کش موقت برای کاهش حجم ایمیج
# برای رفع خطای ResolutionImpossible، نسخه‌ها باید در requirements.txt اصلاح شده باشند
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن تمام فایل‌های سورس کد پروژه به دایرکتوری کار
COPY . /app/

# دستور اجرای اپلیکیشن شما
# فرض بر این است که فایل اصلی شما main.py است
CMD ["python", "main.py"]
