"""The CSRF helper shared by the session-authenticated write endpoints.

DRF's `APIView` is csrf-exempt, but these endpoints authenticate with the
Django session cookie, so the browser must send the CSRF token on every unsafe
method. Wrapping the view as a plain Django view re-enables the check.
"""

from __future__ import annotations

from functools import wraps

from django.views.decorators.csrf import csrf_protect


def protect_csrf(view):
    """Apply the CSRF check to a DRF view, whose ``as_view`` is exempt by default."""

    @wraps(view)
    def csrf_checked_view(*args, **kwargs):
        return view(*args, **kwargs)

    csrf_checked_view.csrf_exempt = False
    return csrf_protect(csrf_checked_view)
