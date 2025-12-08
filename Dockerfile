# =========================================================
# FINAL STAGE (مرحله نهایی): ساخت ایمیج سبک و تمیز
# =========================================================
FROM python:3.10-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# 1. کپی کردن فایل باینری FFmpeg و FFprobe از مرحله builder
# FFmpeg باینری
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
COPY --from=builder /usr/bin/ffprobe /usr/bin/ffprobe # ⬅️ اضافه شدن ffprobe
# کپی کردن کتابخانه‌های وابسته به FFmpeg (مانند libavcodec)
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavcodec* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavformat* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libavutil* /usr/lib/x86_64-linux-gnu/


# 💡 خط جدید: اضافه کردن /usr/bin به PATH برای دسترسی به ffmpeg و ffprobe
ENV PATH="/usr/bin:${PATH}"

# 2. کپی کردن پکیج‌های پایتون نصب شده
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 3. کپی کردن فایل‌های کد اصلی
COPY main.py .

# 4. دستور اجرای ربات
CMD ["python", "main.py"]
