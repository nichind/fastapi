from core.database import *
from asyncio import run


async def main():
    user = await User.get(id=1)
    print(user)
    await user.update(password=user._generate_secret(128))
    print(user)
    if len(await user.get_sessions()) == 0:
        await user.create_session()
    
    
run(main())