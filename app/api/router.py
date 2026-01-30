from fastapi import APIRouter

from app.api.routes import auth, measurements, weather

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(measurements.router, tags=["measurements"])
api_router.include_router(weather.router, tags=["weather"])
