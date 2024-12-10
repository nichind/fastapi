from core.database import *
from asyncio import run


async def main():
    session = await Session.get_user("LJJ.DPM3kbHzAZNTV3l57PXzOsfA.rAs9HX0G4PzDesroklKBZhsl2B8Ff3kqz")
    print(session)
            

run(main())