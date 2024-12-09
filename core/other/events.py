from ..database import User, create_db


async def setup_hook(*args, **kwargs) -> None:
    create_db()
    try:
        user = await User.get(username="dev")
        if not user:
            user = await User.add(username="dev")
        await user.update(is_admin=True, token="dev", password=User._generate_secret(64))
    except Exception as exc:
        print("Error while creating admin:", exc)


async def sheduled_backup() -> None:
    pass
