"""SSL context helpers."""

from __future__ import annotations

import ssl


def get_ssl_context() -> ssl.SSLContext:
    """Get SSL context that doesn't verify certificates.

    This is useful for self-signed Forgejo instances.

    Returns:
        SSL context configured to skip certificate verification.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context
