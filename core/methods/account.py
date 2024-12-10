from fastapi import Request, Depends, Header, HTTPException
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    PlainTextResponse,
    FileResponse,
    Response,
)
from pydantic import BaseModel
from datetime import datetime
from ..database import User, perfomance, choice, ascii_letters, getenv
from ..other import track_usage
from typing import Literal, Annotated
from re import match


class Methods:
    def __init__(self, app):
        self.path = app.root + "account/"

        class Account(BaseModel):
            email: str | None = None
            username: str
            password: str

        @app.post(self.path + "auth/register", tags=["auth"])
        @app.limit("30/hour")
        @track_usage
        async def register(
            request: Request,
            account: Account,
            type: Literal["default", "google", "github", "discord"] = "default",
        ) -> JSONResponse:
            errors = []

            if type != "default":
                return JSONResponse(
                    {
                        "url": f"https://accounts.google.com/o/oauth2/auth?response_type=code&client_id={getenv('GOOGLE_CLIENT_ID', '')}&redirect_uri={app.api_url}/account/auth/google&scope=openid%20profile%20email&access_type=offline"
                    },
                    status_code=200,
                    headers=app.no_cache_headers,
                )

            if account.username and len(account.username) < 3:
                errors.append("Username must be at least 3 characters long")
            if account.username and await User.get(username=account.username):
                errors.append("Username already exists")
            if account.username is None and account.email is None:
                errors.append("Either username or email must be provided")
            if account.email and await User.get(email=account.email):
                errors.append("Email already used")
            if account.email and not match(r"[^@]+@[^@]+\.[^@]+", account.email):
                errors.append("Invalid email address")
            if len(account.password) < 8:
                errors.append("Password must be at least 8 characters long")
            if (
                account.password == account.password.lower()
                or account.password == account.password.upper()
            ):
                errors.append(
                    "Password must contain at least one uppercase letter and one lowercase letter"
                )
            if not any(char.isdigit() for char in account.password):
                errors.append("Password must contain at least one number")

            for user in await User.get_all(reg_ip=request.state.ip):
                if user.created_at.timestamp() + 60 * 60 > datetime.timestamp():
                    errors.append("You have already registered recently, please wait")

            if len(errors) == 0:
                try:
                    email_confirm_code = (
                        User._generate_secret(64) if account.email else None
                    )
                    email_confirm_url = f"{app.api_url}/account/auth/confirmEmail?key={email_confirm_code}"
                    user = await User.add(
                        username=account.username,
                        email=account.email,
                        password=account.password,
                        reg_ip=request.state.ip,
                        reg_type=type if type != "default" else None,
                        email_confirm_code=email_confirm_code,
                        last_ip=request.state.ip,
                        token=User._generate_secret(64),
                    )
                    app.logger.info(f"User {user.id} created | ip: {request.state.ip}")
                    if account.email:
                        app.email.send(
                            to=account.email,
                            subject=request.state.tl("CONFIRM_REGISTRATION_SUBJECT"),
                            message_content="confirm-email",
                            user=user.username,
                            key_url=email_confirm_url,
                            ip=request.state.ip,
                        )
                    return JSONResponse(
                        {
                            "details": request.state.tl("ACCOUNT_CREATED"),
                            "user_id": user.id,
                            "token": user.token,
                        },
                        status_code=201,
                        headers=app.no_cache_headers,
                    )
                except Exception as e:
                    app.logger.error(e)
                    errors.append("An error occurred...")
            return JSONResponse(
                {"details": errors}, status_code=400, headers=app.no_cache_headers
            )
