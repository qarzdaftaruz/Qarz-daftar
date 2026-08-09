from fastapi import APIRouter
from app.api.admin import router as admin_router
from app.api.tma_auth import router as tma_auth_router
from app.api.tma_owner import router as tma_owner_router
from app.api.tma_debtor import router as tma_debtor_router

router = APIRouter()
router.include_router(admin_router)
router.include_router(tma_auth_router)
router.include_router(tma_owner_router)
router.include_router(tma_debtor_router)
