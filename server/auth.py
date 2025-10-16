import typing
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

from config import jwt_public_key
from utils.logger import getLogger


logger = getLogger("server.auth")


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that checks for a valid JWT in the 'teacher_jwt' cookie.

    It expects RS256-signed JWTs and verifies them against the public key
    provided in `config.jwt_public_key`.
    """

    def __init__(self, app, exempt_paths: typing.Optional[typing.List[str]] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or []
        logger.info("JWTAuthMiddleware initialized; exempt_paths=%s", self.exempt_paths)

    async def dispatch(self, request: Request, call_next):
        # allow exempted paths through
        path = request.url.path
        if any(path.startswith(p) for p in self.exempt_paths):
            logger.debug("Path exempted from auth: %s", path)
            return await call_next(request)

        token = request.cookies.get("teacher_jwt")
        if not token:
            logger.warning("Missing teacher_jwt cookie for path: %s", path)
            raise HTTPException(status_code=401, detail="Missing teacher_jwt cookie")

        try:
            # verify RS256 JWT using provided public key
            payload = jwt.decode(token, jwt_public_key, algorithms=["RS256"], options={"verify_aud": False})
            # attach payload to request.state for downstream handlers
            request.state.teacher_payload = payload
            logger.info("JWT validated for path %s, sub=%s", path, payload.get("sub"))
        except jwt.ExpiredSignatureError:
            logger.warning("Expired token for path: %s", path)
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            logger.error("Invalid token for path %s: %s", path, e)
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

        return await call_next(request)
