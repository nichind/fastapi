from fastapi import Request
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    PlainTextResponse,
    FileResponse,
)
from datetime import datetime
from ..database import perfomance
from ..other import track_usage


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
            return JSONResponse(
                {
                    "status": (
                        "ok"
                        if sum(perfomance.all[-100:]) / len(perfomance.all[-100:])
                        < 0.09
                        else "slow"
                    ),
                    "total_actions": len(perfomance.all),
                    "delays": {
                        "all_time": sum(perfomance.all) / len(perfomance.all),
                        "last_1": sum(perfomance.all[-1:]) / len(perfomance.all[-1:]),
                        "last_10": sum(perfomance.all[-10:])
                        / len(perfomance.all[-10:]),
                        "last_100": sum(perfomance.all[-100:])
                        / len(perfomance.all[-100:]),
                        "last_1000": sum(perfomance.all[-1000:])
                        / len(perfomance.all[-1000:]),
                        "last_10000": sum(perfomance.all[-10000:])
                        / len(perfomance.all[-10000:]),
                    },
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
            return RedirectResponse("https://github.com/waomoe")

        @app.get(self.path + "favicon.ico", include_in_schema=False)
        @app.limit("10/minute")
        async def favicon(request: Request):
            return FileResponse(app.root_dir + "/logo.png")
