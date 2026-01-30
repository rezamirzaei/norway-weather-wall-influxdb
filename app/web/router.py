from fastapi import APIRouter

from app.web.routes.pages import router as pages_router

ui_router = APIRouter(prefix="/ui", include_in_schema=False)
ui_router.include_router(pages_router)

