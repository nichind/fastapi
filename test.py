from asyncio import run
from core.database import *


async def main():
    print(await Session.get_user("hMY.8RGPgOPB3YswhCIuSG2EpRuV.f96WTzwQafJsgHAPGsf96XLRqp3LycZS817fRga8Q"))


run(main())
