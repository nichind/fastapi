from random import choice
from string import ascii_letters, digits
from asyncio import sleep
from ..database import User


async def setup_hook(*args, **kwargs) -> None:
    try:
        user = await User.get(username="admin")
        if not user:
            user = await User.add(
                username="admin"
            )
        await user.update(password="admin", token=await user._generate_secret(128))
        print(await user._compare("admin", user.password))
    except Exception as exc:
        print("Error while creating admin:", exc)
    ...

async def sheduled_backup() -> None:
    pass
