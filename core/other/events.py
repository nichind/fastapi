from ..database import User, create_tables, AuditLog


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
        # print((await User.search("dev"))[0].decrypted().__dict__)
        # print(await AuditLog.search("1"))
        dev = await User.get(username="dev")
        print((await dev.get_audit()))
    except Exception as exc:
        app.debug("Error while creating admin:", exc)
    app.debug("Setup hook finished")


async def sheduled_backup() -> None:
    pass
