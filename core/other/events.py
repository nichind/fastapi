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
        await user.update(password=user._generate_secret(128), groups=["admin"])
        if len(await user.get_sessions()) == 0:
            await user.create_session()
            app.debug("Created admin session")
    except Exception as exc:
        app.debug("Error while creating admin:", exc)


async def sheduled_backup() -> None:
    pass
