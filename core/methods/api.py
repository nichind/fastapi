from fastapi import Request, Depends, Header, HTTPException
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    PlainTextResponse,
    FileResponse,
    Response,
)
from datetime import datetime
from ..database import User, perfomance, choice, ascii_letters, digits, getenv
from ..other import track_usage
from typing import Literal, Annotated
import time


class Methods:
    def __init__(self, app):
        self.path = app.root

        @app.middleware("http")
        async def main_middleware(request: Request, call_next):
            start_time = time.perf_counter()
            languages = request.headers.get("accept-language", "en").split(",")
            language = "en"
            for lang in languages:
                lang = lang.strip()
                if lang in app.tlbook:
                    language = lang
                    break
            setattr(request.state, "tl", lambda text: app.tl(text, language))
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Process-Time-MS"] = str(process_time * 1000)
            response.headers["X-Server-Time"] = str(datetime.now())
            if request.client.host not in app.ipratelimit:
                app.ipratelimit[request.client.host] = []
            if len(app.ipratelimit[request.client.host]) <= int(
                getenv("IP_RATE_LIMIT_PER_MINUTE", 60)
            ):
                app.ipratelimit[request.client.host] += [time.time()]
            for i in app.ipratelimit[request.client.host]:
                if time.time() - i > 60:
                    app.ipratelimit[request.client.host].remove(i)
            if len(app.ipratelimit[request.client.host]) > int(
                getenv("IP_RATE_LIMIT_PER_MINUTE", 60)
            ):
                return JSONResponse(
                    status_code=429,
                    content={"detail": request.state.tl("IP_RATE_LIMIT_EXCEEDED")},
                )
            try:
                user = await User.get(
                    token=request.headers.get("X-Authorization", "1337")
                )
                response.headers["X-Auth-As"] = f"{user.username}"
            except Exception:
                pass
            return response

        @app.get(self.path, include_in_schema=False)
        @track_usage
        async def root(request: Request, *args, **kwargs):
            app.logger.info(request.url)
            return RedirectResponse("/docs")

        @app.get(
            self.path + "status",
            tags=["default"],
            dependencies=[Depends(app.checks.anti_ddos)],
        )
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
        @app.limit("60/minute")
        @track_usage
        async def database(
            request: Request, x_authorization: Annotated[str, Header()] = None
        ) -> JSONResponse:
            await User.get_chunk(limit=500)
            delays = {
                "all_time": {
                    "ms": round(sum(perfomance.all) / len(perfomance.all) * 1000, 5),
                    "s": round(sum(perfomance.all) / len(perfomance.all), 5),
                },
                "last_1": {
                    "ms": round(
                        sum(perfomance.all[-1:]) / len(perfomance.all[-1:]) * 1000, 5
                    ),
                    "s": round(sum(perfomance.all[-1:]) / len(perfomance.all[-1:]), 5),
                },
                "last_10": {
                    "ms": round(
                        sum(perfomance.all[-10:]) / len(perfomance.all[-10:]) * 1000, 5
                    ),
                    "s": round(
                        sum(perfomance.all[-10:]) / len(perfomance.all[-10:]), 5
                    ),
                },
                "last_100": {
                    "ms": round(
                        sum(perfomance.all[-100:]) / len(perfomance.all[-100:]) * 1000,
                        5,
                    ),
                    "s": round(
                        sum(perfomance.all[-100:]) / len(perfomance.all[-100:]), 5
                    ),
                },
                "last_1000": {
                    "ms": round(
                        sum(perfomance.all[-1000:])
                        / len(perfomance.all[-1000:])
                        * 1000,
                        5,
                    ),
                    "s": round(
                        sum(perfomance.all[-1000:]) / len(perfomance.all[-1000:]), 5
                    ),
                },
                "last_10000": {
                    "ms": round(
                        sum(perfomance.all[-10000:])
                        / len(perfomance.all[-10000:])
                        * 1000,
                        5,
                    ),
                    "s": round(
                        sum(perfomance.all[-10000:]) / len(perfomance.all[-10000:]), 5
                    ),
                },
            }

            return JSONResponse(
                {
                    "status": "ok" if delays["last_100"]["ms"] < 90 else "slow",
                    "total_actions": len(perfomance.all),
                    "delays": delays,
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
        async def stress(
            request: Request, count: int = 5000, data: Literal["users"] = "users"
        ) -> JSONResponse:
            if data == "users":
                for x in range(count):
                    await User.add(
                        username=f"stress_{x}"
                        + "".join(choice(ascii_letters) for _ in range(6)),
                        email=f"stress_{x}"
                        + "".join(choice(ascii_letters) for _ in range(6))
                        + "@example.com",
                        password="".join(choice(ascii_letters) for _ in range(12)),
                    )
            return JSONResponse({"status": "ok"}, headers=app.no_cache_headers)
