from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from datetime import datetime
from core import Translator, Checks, setup_hook, create_db
from loguru import logger
from pprint import pformat
from loguru._defaults import LOGURU_FORMAT
from glob import glob
from os.path import dirname, basename, isfile, join
from asyncio import create_task, run
from subprocess import check_output
from threading import Thread
from asyncio import sleep
from sys import stdout
from dotenv import load_dotenv
from os import getenv
import logging


async def rechache_translations():
    while True:
        app.logger.info("Chaching translations...")
        app.translator.chache_translations()
        app.logger.info("Re-cached translations")
        await sleep(60 * 30)


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = app.logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        app.logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def format_record(record: dict) -> str:
    format_string = LOGURU_FORMAT

    if record["extra"].get("payload") is not None:
        record["extra"]["payload"] = pformat(
            record["extra"]["payload"], indent=4, compact=True, width=88
        )
        format_string += "\n<level>{extra[payload]}</level>"

    format_string += "{exception}\n"
    return format_string


load_dotenv()
version = "2024.12.1"
tags_metadata = [
    {
        "name": "default",
        "description": "Default endpoints.",
    },
]
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    version=version,
    openapi_url="/pubapi.json",
    openapi_tags=tags_metadata,
)

try:
    app.commit = (
        check_output(["git", "rev-parse", "--short", "HEAD"]).decode("ascii").strip()
    )
except Exception:
    app.commit = "unknown"

app.root_dir = dirname(__file__)
app.current_version = version
app.start_at = datetime.now()
app.url = getenv("FRONTEND_URL", "")
app.api_url = getenv("BACKEND_URL", "")
app.root = "/"
app.translator = Translator()
app.logger = logger
app.tl = app.translator.tl
app.title = app.tl("title")
app.description = app.tl("description")

Thread(target=run, args=(rechache_translations(),)).start()

app.state.limiter = limiter
app.limit = app.state.limiter.limit
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[app.url, app.api_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

logging.getLogger().handlers = [InterceptHandler()]

app.logger.configure(
    handlers=[
        {"sink": stdout, "level": logging.DEBUG, "format": format_record},
        {
            "sink": "./logs/{time:YYYY}-{time:MM}-{time:DD}.log",
            "level": logging.DEBUG,
            "format": format_record,
        },
    ]
)

logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]

app.no_cache_headers = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}
app.logger.info("Loading modules from core.methods...")
app.checks = Checks(app)

modules = glob(join(dirname(__file__) + "/core/methods/", "*.py"))
__all__ = [
    basename(f)[:-3] for f in modules if isfile(f) and not f.endswith("__init__.py")
]
for module in __all__:
    module = __import__(f"core.methods.{module}", globals(), locals(), ["Methods"], 0)
    if "dev" not in app.current_version and module.__name__.split(".")[-1] == "dev":
        continue
    module.Methods(app)
    app.logger.info(f"Loaded {module.__name__} methods")

create_db()

app.setup_hook = create_task(setup_hook())
app.logger.success(
    f"Started backend v{app.current_version} in {int((datetime.now() - app.start_at).total_seconds() * 1000)} ms"
)
app.setup_hook.add_done_callback(
    lambda x: app.logger.info(
        f"\n\n\t{app.title} Backend v{app.current_version}\n\tCommit #{app.commit}\n\tAPI URL: {app.api_url}\n\tFrontend URL: {app.url}\n\tModules loaded: {len(__all__)}\n"
    )
)
