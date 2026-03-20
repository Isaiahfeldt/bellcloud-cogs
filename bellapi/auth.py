import jwt


class AuthError(Exception):
    def __init__(self, message: str, status: int = 403):
        super().__init__(message)
        self.status = status
        self.message = message


def verify_jwt(token: str, secret: str, required_guild_id: str | None) -> dict:
    """
    Validate a JWT and return its payload.

    - required_guild_id=None  → skip guild_id scope check (used for /guilds list endpoint)
    - required_guild_id=<id>  → validate that token's guild_id matches the path param

    Raises AuthError on any failure.
    """
    if not token:
        raise AuthError("Missing token", status=403)

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired", status=403)
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token", status=403)

    if required_guild_id is not None:
        if str(payload.get("guild_id")) != str(required_guild_id):
            raise AuthError("Token guild_id does not match request", status=403)

    return payload
