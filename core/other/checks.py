from fastapi import HTTPException, Header
from typing import Annotated


class Checks:
    def __init__(self, app):
        self.app = app

    async def auth_check(self, x_authorization: Annotated[str, Header()] = None):
        if x_authorization is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
