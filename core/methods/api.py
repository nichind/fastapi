from fastapi import Request, Depends
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    PlainTextResponse,
    FileResponse,
)
from datetime import datetime
from ..database import *
from ..other import track_usage
from typing import Literal


class Methods:
    def __init__(self, app):
        self.path = app.root

        @app.get(self.path, include_in_schema=False)
        @track_usage
        async def root(request: Request, *args, **kwargs):
            app.logger.info(request.url)
            return RedirectResponse("/docs")

        @app.get(self.path + "status", tags=["default"])
        @track_usage
        async def status(request: Request) -> JSONResponse:
            return JSONResponse(
                {
                    "status": "ok",
                    "current_version": app.current_version,
                    "uptime": str(datetime.now() - app.start_at),
                    "server_time": str(datetime.now()),
                },
                headers=app.no_cache_headers,
            )

        @app.get(self.path + "database", tags=["default"])
        @app.limit("12/minute")
        @track_usage
        async def database(request: Request) -> JSONResponse:
            delays = {
                "all_time": round(sum(perfomance.all) / len(perfomance.all) * 1000, 5),
                "last_1": round(sum(perfomance.all[-1:]) / len(perfomance.all[-1:]) * 1000, 5),
                "last_10": round(sum(perfomance.all[-10:]) / len(perfomance.all[-10:]) * 1000, 5),
                "last_100": round(sum(perfomance.all[-100:]) / len(perfomance.all[-100:]) * 1000, 5),
                "last_1000": round(sum(perfomance.all[-1000:]) / len(perfomance.all[-1000:]) * 1000, 5),
                "last_10000": round(sum(perfomance.all[-10000:]) / len(perfomance.all[-10000:]) * 1000, 5),
            }

            return JSONResponse(
                {
                    "status": "ok" if delays["last_100"] < 90 else "slow",
                    "total_actions": len(perfomance.all),
                    "delays_ms": delays,
                },
                headers=app.no_cache_headers,
            )

        @app.get(self.path + "version", tags=["default"])
        @track_usage
        async def version(request: Request) -> PlainTextResponse:
            return app.current_version

        @app.get(self.path + "github", include_in_schema=False, tags=["default"])
        @track_usage
        async def github(request: Request) -> RedirectResponse:
            return RedirectResponse("https://github.com/nichind/fastapi")

        @app.get(self.path + "favicon.ico", include_in_schema=False)
        @app.limit("10/minute")
        async def favicon(request: Request):
            return FileResponse(app.root_dir + "/logo.png")

        @app.get(self.path + "stress", dependencies=[Depends(app.checks.admin_check)])
        @track_usage
        async def stress(request: Request, count: int = 5000, data: Literal["users"] = "users") -> JSONResponse:
            if data == "users":
                for x in range(count):
                    await User.add(username=f"user_{x}", email=f"user_{x}@example.com", password=f"user_{x}")
            return JSONResponse({"status": "ok"}, headers=app.no_cache_headers)
            