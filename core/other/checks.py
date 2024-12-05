from fastapi import HTTPException, Header, Request
from typing import Annotated
from ..database import User


class Checks:
    def __init__(self, app):
        self.app = app

    async def auth_check(self, request: Request, x_authorization: Annotated[str, Header()] = None):
        """
        Check user authentication based on the authorization token.

        Args:
            x_authorization (Annotated[str, Header()], optional): The authorization token
            provided in the request header.

        Raises:
            HTTPException: If the authorization header is missing or the token is invalid.

        Returns:
            User: The authenticated user object if the token is valid.
        """
        if x_authorization is None:
            raise HTTPException(status_code=401, detail=request.state.tl("NO_AUTH_HEADER"))
        user = await User.get(token=x_authorization)
        if not user:
            raise HTTPException(status_code=401, detail=request.state.tl("INVALID_TOKEN"))
        return x_authorization

    async def admin_check(self, request: Request, x_authorization: Annotated[str, Header()] = None):
        """
        Check if the user is an administrator.

        Args:
            user (User): The user object.

        Raises:
            HTTPException: If the user is not an administrator.

        Returns:
            User: The user object if the user is an administrator.
        """
        user = await User.get(token=x_authorization)
        if not user:
            raise HTTPException(status_code=401, detail=request.state.tl("INVALID_TOKEN"))
        if not user.is_admin:
            raise HTTPException(
                status_code=403, detail=request.state.tl("NOT_AN_ADMINISTRATOR")
            )
        return x_authorization

    async def anti_ddos(self, request: Request):
        self.app.chache = {}
