# Railway uchun: repo ildizidan quriladi, ilova esa `backend/` ichida.
# Shu sabab Root Directory ni o'zgartirish shart emas.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*

# Kesh uchun: avval faqat requirements, keyin kod
COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install -r requirements.txt

COPY backend/ ./

# Root'siz ishlatamiz
RUN useradd --create-home --uid 10001 appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Railway `PORT` beradi; lokal docker run uchun 8000 zaxira qiymat
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*' --no-server-header --timeout-keep-alive 65"]
