from ..database import User


async def setup_hook(*args, **kwargs) -> None:
    try:
        user = await User.get(username="waomoe")
        if not user:
            user = await User.add(username="waomoe", password=User._generate_secret(64))
        await user.update(is_admin=True, token="dev")
        print(user.decrypted().password)
    except Exception as exc:
        print("Error while creating admin:", exc)


async def sheduled_backup() -> None:
    pass
