"""Lokal ishga tushirish uchun.

Railway'da bu fayl ishlatilmaydi — Procfile / railway.json orqali
uvicorn to'g'ridan-to'g'ri chaqiriladi (reload'siz).
"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        # Production'da avtomatik qayta yuklash o'chirilgan:
        # u xotirani ko'p yeydi va scheduler/bot'ni ikki marta ishga tushiradi
        reload=not settings.is_production,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
