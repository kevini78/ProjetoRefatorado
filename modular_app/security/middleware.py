from flask import request, abort

def register_security(app):
    csp = app.config.get("CONTENT_SECURITY_POLICY", "default-src 'self'")
    allowed_ips = set(ip.strip() for ip in app.config.get("ALLOWED_IPS", []) if ip and ip.strip())

    @app.before_request
    def _ip_filter():
        if allowed_ips:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            if ip not in allowed_ips:
                abort(403)

    @app.after_request
    def _set_headers(resp):
        resp.headers.setdefault("Content-Security-Policy", csp)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp
