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
from cryptography.fernet import Fernet
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

    class Audit: ...

    audit = Audit()
    id = Column(Integer, Identity(start=1, increment=1), primary_key=True, unique=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    is_deleted = Column(Boolean)

    @classmethod
    async def add(
        cls, ignore_crypt: bool = False, ignore_blacklist: bool = True, **kwargs
    ) -> Self:
        """
        Adds a new item to the database.

        Args:
            **kwargs: the keyword arguments to pass to the item's constructor

        Returns:
            The newly created item
        """
        start_at = datetime.now()
        async with sessions[
            cls.__table_args__.get("comment", "main")
        ].begin() as session:
            item = cls(**kwargs)
            for key, value in kwargs.items():
                if not ignore_blacklist and cls._is_value_blacklisted(key, value):
                    raise database_exc.Blacklisted(key, value)
                if key in getenv("CRYPT_VALUES", "").split(",") and not ignore_crypt:
                    value = cls._crypt(value)
                setattr(item, key, value)
            session.add(item)
            await session.commit()
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return item

    @classmethod
    async def get(cls, **filters) -> Self | None:
        """
        Gets an item from the database.

        Args:
            **filters: the keyword arguments to filter by

        Returns:
            The item if found, None otherwise
        """
        start_at = datetime.now()
        async with sessions[
            cls.__table_args__.get("comment", "main")
        ].begin() as session:
            item = (
                (await session.execute(select(User).filter_by(**filters)))
                .scalars()
                .first()
            )
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return item

    @classmethod
    async def get_chunk(
        cls, limit: int = 100, offset: int = 0, **filters
    ) -> List[Self]:
        """
        Gets a chunk of items from the database.

        Args:
            limit (int, optional): the maximum number of items to return. Defaults to 100.
            offset (int, optional): the offset to start from. Defaults to 0.
            **filters: the keyword arguments to filter by

        Returns:
            A list of items
        """
        start_at = datetime.now()
        async with sessions[
            cls.__table_args__.get("comment", "main")
        ].begin() as session:
            items = (
                (
                    await session.execute(
                        select(cls).filter_by(**filters).limit(limit).offset(offset)
                    )
                )
                .scalars()
                .all()
            )
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return items

    @classmethod
    async def get_all(cls, **filters) -> List[Self]:
        """
        Gets all items from the database.

        Args:
            **filters: the keyword arguments to filter by

        Returns:
            A list of all items
        """
        return await cls.get_chunk(limit=-1, **filters)

    @classmethod
    async def update(
        cls,
        id: int = None,
        ignore_crypt: bool = False,
        ignore_blacklist: bool = False,
        **kwargs,
    ) -> Self | None:
        """
        Updates an item in the database.

        Args:
            id (int, optional): The id of the item to update. Defaults to None.
            ignore_crypt (bool, optional): Whether to ignore encryption. Defaults to False.
            ignore_blacklist (bool, optional): Whether to ignore blacklisting. Defaults to False.
            **kwargs: The keyword arguments to update with

        Returns:
            The updated item if found, None otherwise
        """
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
                if getattr(cls, key) == value:
                    continue
                if not ignore_blacklist and cls._is_value_blacklisted(key, value):
                    raise database_exc.Blacklisted(key, value)
                if key in getenv("CRYPT_VALUES", "").split(",") and not ignore_crypt:
                    value = cls._crypt(value)
                await AuditLog.add(
                    old_value=getattr(cls, key),
                    new_value=value,
                    key=key,
                    origin_id=cls.id,
                    origin_table=cls.__tablename__,
                )
                setattr(cls, key, value)
            await session.commit()
        perfomance.all += [(datetime.now() - start_at).total_seconds()]
        return cls

    @classmethod
    def _crypt(cls, value: str, crypt_key: str = None) -> str:
        if not crypt_key:
            crypt_key = getenv("CRYPT_KEY", None)
        if not crypt_key:
            raise database_exc.NoCryptKey
        crypt = Fernet(crypt_key.encode("utf-8"))
        return crypt.encrypt(value.encode()).decode()

    @classmethod
    def _decrypt(cls, value: str, crypt_key: str = None) -> str:
        if not crypt_key:
            crypt_key = getenv("CRYPT_KEY", None)
        if not crypt_key:
            raise database_exc.NoCryptKey
        crypt = Fernet(crypt_key.encode("utf-8"))
        return crypt.decrypt(value.encode()).decode()

    @classmethod
    def _compare(
        cls, decrypted_value: str, encrypted_value: str, crypt_key: str = None
    ) -> bool:
        if not crypt_key:
            crypt_key = getenv("CRYPT_KEY", None)
        if not crypt_key:
            raise database_exc.NoCryptKey
        crypt = Fernet(crypt_key.encode("utf-8"))
        return crypt.decrypt(encrypted_value.encode()).decode() == decrypted_value

    @classmethod
    def _generate_secret(cls, length: int = 32) -> str:
        secret = "".join(choice(ascii_letters + digits) for _ in range(length))
        secret = secret[0:3] + "." + secret[5:]
        if len(secret) >= 32:
            secret = secret[0:28] + "." + secret[30:]
        return secret

    @classmethod
    def _is_value_blacklisted(cls, key: str, value: str) -> bool:
        blacklist_file = f"./core/database/blacklists/{key}.txt"
        if os.path.exists(blacklist_file):
            with open(blacklist_file) as f:
                for line in f:
                    if line.strip() == str(value):
                        return True

        return False

    def decrypted(self) -> Self:
        """
        Returns a new instance of the item with all values decrypted.

        This method takes all values that are in the CRYPT_VALUES environment variable
        and decrypts them, returning a new instance of the item with the decrypted values.

        Returns:
            Self: A new instance of the item with decrypted values.
        """
        for key, value in self.__dict__.items():
            if key in getenv("CRYPT_VALUES", "").split(","):
                self.__dict__[key] = self._decrypt(value)
        return self

    async def get_audit(self) -> dict[str, List["AuditLog"]]:
        """
        Gets all audit logs for the current item.

        This method returns a dictionary with all keys being the column names of the item
        and the values being lists of AuditLog objects.

        Returns:
            dict[str, List["AuditLog"]]: A dictionary with all audit logs for the item.
        """
        for key in self.__dict__.keys():
            if key.startswith("_"):
                continue
            setattr(
                self.audit,
                key,
                await AuditLog.get_all(
                    origin_table=self.__tablename__, origin_id=self.id, key=key
                ),
            )
        return self.audit

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.id}>"

    def __int__(self) -> int:
        return self.id


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


class AuditLog(BaseItem):
    __tablename__ = "audit_logs"
    __table_args__ = {"comment": "main"}

    updated_at = None
    is_deleted = None
    origin_table = Column(String(48), nullable=False)
    origin_id = Column(Integer, nullable=False)
    key = Column(String(64))
    old_value = Column(String(256))
    new_value = Column(String(256))


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
