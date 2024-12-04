import base64
import os
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    JSON,
    DateTime,
    func,
    Identity,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from datetime import datetime
from typing import Self, List
from uuid import uuid4
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from os import getenv, path
from dotenv import load_dotenv
from threading import Thread
from time import sleep
from loguru import logger
from random import choice, shuffle
from string import ascii_letters, digits
from asyncio import get_event_loop, new_event_loop
import core.database.exceptions as exceptions


load_dotenv()
db_backup_folder = getenv("DB_FOLDER_PATH") + "backups/"
engines = {
    n: create_async_engine(
        "sqlite+aiosqlite:///"
        + getenv("DB_FOLDER_PATH")
        + (f"{n}_" if n != "main" else "")
        + "server.sqlite"
    )
    for n in ["main"]
}
sessions = {
    k: sessionmaker(v, expire_on_commit=False, class_=AsyncSession)
    for k, v in engines.items()
}
Base = declarative_base()


class PerfomanceMeter:
    start = datetime.now()
    all = [0]

    def report(self):
        while True:
            sleep(60 * 5)
            if len(self.all) > 10**6:
                self.all = self.all[-(10**6) :]
            logger.info("Database delay report")
            logger.info(f"Average time per action: {sum(self.all) / len(self.all)}s")
            logger.info(
                f"Average time per action (last 1k): {sum(self.all[-1000:]) / len(self.all[-1000:])}s"
            )
            logger.info(
                f"Average time per action (last 100): {sum(self.all[-100:]) / len(self.all[-100:])}s"
            )


perfomance = PerfomanceMeter()


class BaseItem(Base):
    __abstract__ = True

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    @classmethod
    async def add(cls, **kwargs) -> Self:
        start_at = datetime.now()
        async with engines[cls.__table_args__.get("comment", "main")].begin() as conn:
            item = cls(**kwargs)
            conn.add(item)
            await conn.commit()
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return await cls.get(id=item.id)

    @classmethod
    async def get(cls, **kwargs) -> Self | None:
        start_at = datetime.now()
        async with engines[cls.__table_args__.get("comment", "main")].begin() as conn:
            item = (
                (await conn.execute(select(cls).filter_by(**kwargs))).scalars().first()
            )
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return item

    @classmethod
    async def update(cls, **kwargs) -> Self | None:
        start_at = datetime.now()
        async with engines[cls.__table_args__.get("comment", "main")].begin() as conn:
            item = (
                (await conn.execute(select(cls).filter_by(**kwargs))).scalars().first()
            )
            for key, value in kwargs.items():
                setattr(item, key, value)
            await conn.commit()
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return item


class ServerSetting(BaseItem):
    __tablename__ = "server_settings"
    __table_args__ = {"comment": "main"}

    key = Column(String, unique=True)
    value = Column(String)


async def create_tables():
    try:
        for name, engine in engines.items():
            if not os.path.exists("./databases/"):
                os.mkdir("./databases")
            async with engine.begin() as conn:
                for table in Base.metadata.sorted_tables:
                    if table.comment == name:
                        await conn.run_sync(table.create, checkfirst=True)
    except Exception as exc:
        print(exc)


def create_db():
    if get_event_loop() is None:
        new_event_loop().run_until_completed(create_tables())
    else:
        get_event_loop().create_task(create_tables())
