"""
Shared client-IP extraction. Honors x-forwarded-for (we run behind Cloudflare),
falling back to the direct peer when absent.
"""

from fastapi import Request


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
