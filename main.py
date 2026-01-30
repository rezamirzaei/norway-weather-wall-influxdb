import os

import uvicorn


def main() -> None:
    reload_enabled = os.getenv("APP_ENV", "development").lower() != "production"
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=reload_enabled,
    )


if __name__ == "__main__":
    main()

