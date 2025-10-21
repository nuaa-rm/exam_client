def session_to_cookie_string(session) -> str:
    """Convert various session/cookie representations into a single cookie string suitable for document.cookie.

    Supports:
    - dict of {name: value}
    - requests.cookies.RequestsCookieJar
    - list/tuple of (name, value) pairs
    - raw string (returned as-is)
    - None -> empty string
    """
    if not session:
        return ""
    # raw string
    if isinstance(session, str):
        return session
    # dict
    if isinstance(session, dict):
        parts = []
        for k, v in session.items():
            parts.append(f"{k}={v}")
        return "; ".join(parts)
    # requests cookiejar
    try:
        from requests.cookies import RequestsCookieJar
        if isinstance(session, RequestsCookieJar):
            parts = []
            for c in session:
                parts.append(f"{c.name}={c.value}")
            return "; ".join(parts)
    except Exception:
        pass
    # list/tuple of pairs
    if isinstance(session, (list, tuple)):
        parts = []
        for item in session:
            try:
                k, v = item
            except Exception:
                continue
            parts.append(f"{k}={v}")
        return "; ".join(parts)
    # fallback: try JSON-serializable mapping
    try:
        as_dict = dict(session)
        parts = [f"{k}={v}" for k, v in as_dict.items()]
        return "; ".join(parts)
    except Exception:
        return ""
