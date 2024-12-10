from ..database import User, create_tables


async def setup_hook(app, *args, **kwargs) -> None:
    app.debug("Creating tables...")
    await create_tables()
    try:
        user = await User.get(username="dev")
        if not user:
            app.debug("Creating admin...")
            user = await User.add(username="dev")
        app.debug("Setting admin...")
        await user.update(
            is_admin=True, token="dev", password=User._generate_secret(128)
        )
    except Exception as exc:
        app.debug("Error while creating admin:", exc)


async def sheduled_backup() -> None:
    pass
