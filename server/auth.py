import typing
import ipaddress
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

from config import jwt_public_key
from utils.logger import getLogger


logger = getLogger("server.auth")


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that checks for a valid JWT in the 'teacher_jwt' cookie.

    Behavior change: requests coming from loopback addresses (e.g. 127.0.0.1 or ::1)
    will bypass JWT verification. For such local requests `request.state.teacher_payload`
    will be set to {'local': True} so downstream handlers can detect the bypass.
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

        # try to detect if request comes from a loopback (localhost) IP and skip auth
        # Note: depending on deployment (reverse proxy), the client IP may be in headers
        client_ip = None
        # prefer X-Forwarded-For if present (first value), fall back to client.host
        xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if xff:
            # X-Forwarded-For may contain comma-separated list; take first
            client_ip = xff.split(",")[0].strip()
            logger.debug("Found X-Forwarded-For: %s", client_ip)
        else:
            # starlette Request.client may be None in some cases; guard it
            if request.client and request.client.host:
                client_ip = request.client.host

        if client_ip:
            try:
                ip = ipaddress.ip_address(client_ip)
                if ip.is_loopback:
                    # mark as local and bypass JWT verification
                    request.state.teacher_payload = {"local": True}
                    logger.info("Bypassing JWT for local request from %s to %s", client_ip, path)
                    return await call_next(request)
            except ValueError:
                # not a valid IP address; proceed with normal auth
                logger.debug("Could not parse client IP: %s", client_ip)

        token = None
        token_source = None

        cookie_token = request.cookies.get("teacher_jwt")
        if cookie_token:
            token = cookie_token
            token_source = "cookie"

        if not token:
            header_token = request.headers.get("x-teacher-jwt") or request.headers.get("X-Teacher-JWT")
            if header_token:
                token = header_token
                token_source = "header:x-teacher-jwt"

        if not token:
            qp = request.query_params
            q_token = qp.get("teacher_jwt") or qp.get("token")
            if q_token:
                token = q_token
                token_source = "query"

        if not token:
            logger.warning(
                "Missing token for path: %s (client_ip=%s). Supported locations: cookie 'teacher_jwt', header 'X-Teacher-JWT', or query 'teacher_jwt'/'token'",
                path,
                client_ip,
            )
            raise HTTPException(status_code=401, detail="Missing token (check cookie, header, or query param)")

        try:
            # verify RS256 JWT using provided public key
            payload = jwt.decode(token, jwt_public_key, algorithms=["RS256"], options={"verify_aud": False})
            # attach payload and token metadata to request.state for downstream handlers
            request.state.teacher_payload = payload
            request.state.teacher_token_source = token_source
            logger.info("JWT validated for path %s, sub=%s (source=%s)", path, payload.get("sub"), token_source)
        except jwt.ExpiredSignatureError:
            logger.warning("Expired token for path: %s (source=%s)", path, token_source)
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            logger.error("Invalid token for path %s (source=%s): %s", path, token_source, e)
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

        return await call_next(request)
