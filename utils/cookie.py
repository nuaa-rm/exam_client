def session_to_cookie_string(session) -> str:
    """Convert various session/cookie representations into a single cookie string suitable for document.cookie.

    Supports:
    - dict of {name: value}
    - requests.cookies.RequestsCookieJar
    - list/tuple of (name, value) pairs
    - raw string (returned as-is)
    - None -> empty string
    """
    from datetime import datetime, timedelta

    # If falsy, return empty
    if not session:
        return ""

    # raw string -> returned as-is (caller may have prepared attributes already)
    if isinstance(session, str):
        return session

    # helper to build a persistent cookie string for a single (k,v)
    def _build_cookie(k, v, days=1):
        # ensure basic str and strip newlines
        kv = f"{k}={v}" if v is not None else f"{k}="
        kv = kv.replace('\n', '').replace('\r', '')
        expires = (datetime.utcnow() + timedelta(days=days)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        max_age = int(days * 24 * 3600)
        # Use Path and Max-Age/Expires so cookie persists when set from document.cookie.
        # Avoid Secure flag to keep it usable on http (webview local pages). Use SameSite=Lax as a safe default.
        return f"{kv}; Path=/; Expires={expires}; Max-Age={max_age}; SameSite=Lax"

    # dict
    if isinstance(session, dict):
        items = list(session.items())
        # if only one cookie, return single persistent cookie string (suitable for document.cookie assignment)
        if len(items) == 1:
            k, v = items[0]
            return _build_cookie(k, v)
        # multiple: return joined cookie attribute strings (best-effort; callers using document.cookie should set cookies one-by-one,
        # but this keeps backward compatibility with previous output while appending persistence attributes)
        parts = [_build_cookie(k, v) for k, v in items]
        return "; ".join(parts)

    # requests cookiejar
    try:
        from requests.cookies import RequestsCookieJar
        if isinstance(session, RequestsCookieJar):
            cookies = [(c.name, c.value) for c in session]
            if len(cookies) == 1:
                return _build_cookie(*cookies[0])
            parts = [_build_cookie(k, v) for k, v in cookies]
            return "; ".join(parts)
    except Exception:
        pass

    # list/tuple of pairs
    if isinstance(session, (list, tuple)):
        pairs = []
        for item in session:
            try:
                k, v = item
            except Exception:
                continue
            pairs.append((k, v))
        if not pairs:
            return ""
        if len(pairs) == 1:
            return _build_cookie(*pairs[0])
        parts = [_build_cookie(k, v) for k, v in pairs]
        return "; ".join(parts)

    # fallback: try JSON-serializable mapping
    try:
        as_dict = dict(session)
        items = list(as_dict.items())
        if not items:
            return ""
        if len(items) == 1:
            return _build_cookie(*items[0])
        parts = [_build_cookie(k, v) for k, v in items]
        return "; ".join(parts)
    except Exception:
        return ""
