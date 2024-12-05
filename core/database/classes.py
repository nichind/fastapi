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
    insert,
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
from os import getenv
from dotenv import load_dotenv
from time import sleep
from loguru import logger
from string import ascii_letters, digits
from random import choice
from asyncio import get_event_loop, new_event_loop
import core.database.exceptions as database_exc


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

    async def report(self):
        while True:
            await sleep(60 * 5)
            if len(self.all) > 10**6:
                self.all = self.all[-(10**6) :]
            logger.info("Database delay report")
            logger.info(
                f"Average time per action: {sum(self.all) / len(self.all) / 1000:.2f}ms"
            )
            logger.info(
                f"Average time per action (last 1k): {sum(self.all[-1000:]) / len(self.all[-1000:]) / 1000:.2f}ms"
            )
            logger.info(
                f"Average time per action (last 100): {sum(self.all[-100:]) / len(self.all[-100:]) / 1000:.2f}ms"
            )


perfomance = PerfomanceMeter()


class BaseItem(Base):
    __abstract__ = True

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True, unique=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    is_deleted = Column(Boolean)

    @classmethod
    async def add(cls, **kwargs) -> Self:
        start_at = datetime.now()
        async with sessions[
            cls.__table_args__.get("comment", "main")
        ].begin() as session:
            item = cls(**kwargs)
            session.add(item)
            await session.commit()
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return item

    @classmethod
    async def get(cls, **kwargs) -> Self | None:
        start_at = datetime.now()
        async with sessions[
            cls.__table_args__.get("comment", "main")
        ].begin() as session:
            item = (
                (await session.execute(select(User).filter_by(**kwargs)))
                .scalars()
                .first()
            )
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return item

    @classmethod
    async def get_chunk(cls, limit: int = 100, offset: int = 0) -> List[Self]:
        start_at = datetime.now()
        async with sessions[
            cls.__table_args__.get("comment", "main")
        ].begin() as session:
            items = (
                (await session.execute(select(cls).limit(limit).offset(offset)))
                .scalars()
                .all()
            )
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return items

    @classmethod
    async def update(
        cls,
        id: int = None,
        ignore_crypt: bool = False,
        ignore_blacklist: bool = False,
        **kwargs,
    ) -> Self | None:
        start_at = datetime.now()
        if not id:
            id = cls.id if cls.id else None
        if not id:
            raise database_exc.NoID
        async with sessions[
            cls.__table_args__.get("comment", "main")
        ].begin() as session:
            cls = (
                (await session.execute(select(cls).filter_by(id=id))).scalars().first()
            )
            for key, value in kwargs.items():
                if not ignore_blacklist and await cls.is_value_blacklisted(key, value):
                    raise database_exc.Blacklisted
                if key in getenv("CRYPT_VALUES", "").split(",") and not ignore_crypt:
                    value = await cls._crypt(value)
                setattr(cls, key, value)
            await session.commit()
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return cls

    @classmethod
    async def _crypt(cls, value: str, crypt_key: str = None) -> str:
        if not crypt_key:
            crypt_key = getenv("CRYPT_KEY", None)
        if not crypt_key:
            raise database_exc.NoCryptKey
        crypt = Fernet(crypt_key.encode("utf-8"))
        return crypt.encrypt(value.encode()).decode()

    @classmethod
    async def _decrypt(cls, value: str, crypt_key: str = None) -> str:
        if not crypt_key:
            crypt_key = getenv("CRYPT_KEY", None)
        if not crypt_key:
            raise database_exc.NoCryptKey
        crypt = Fernet(crypt_key.encode("utf-8"))
        return crypt.decrypt(value.encode()).decode()

    @classmethod
    async def _compare(
        cls, decrypted_value: str, encrypted_value: str, crypt_key: str = None
    ) -> bool:
        if not crypt_key:
            crypt_key = getenv("CRYPT_KEY", None)
        if not crypt_key:
            raise database_exc.NoCryptKey
        crypt = Fernet(crypt_key.encode("utf-8"))
        return crypt.decrypt(encrypted_value.encode()).decode() == decrypted_value

    @classmethod
    async def _generate_secret(cls, length: int = 32) -> str:
        secret = "".join(choice(ascii_letters + digits) for _ in range(length))
        secret = secret[0:3] + "." + secret[5:]
        if len(secret) >= 32:
            secret = secret[0:28] + "." + secret[30:]
        return secret

    @classmethod
    async def is_value_blacklisted(cls, key: str, value: str) -> bool:
        blacklist_file = f"./core/database/blacklists/{key}.txt"
        if not os.path.exists(blacklist_file):
            return False

        with open(blacklist_file) as f:
            for line in f:
                if line.strip() == str(value):
                    return True

        return False

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.id}>"


class ServerSetting(BaseItem):
    __tablename__ = "server_settings"
    __table_args__ = {"comment": "main"}

    key = Column(String, unique=True)
    value = Column(String)


class User(BaseItem):
    __tablename__ = "users"
    __table_args__ = {"comment": "main"}

    username = Column(String(48), unique=True)
    email = Column(String(128), unique=True)
    password = Column(String(256))
    token = Column(String(256), unique=True)
    is_admin = Column(Boolean)


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
        print("Error while creating tables:", exc)


def create_db():
    if get_event_loop() is None:
        new_event_loop().run_until_completed(create_tables())
    else:
        get_event_loop().create_task(create_tables())
