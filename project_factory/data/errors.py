"""Shared error taxonomy for real DataAdapters.

Every real adapter (Bybit, NYISO, and any future one) should raise one
of these rather than letting an underlying httpx/parsing exception
propagate raw — the whole point is that a user running `qpf run --stage
data` outside this sandbox can immediately tell *which kind* of problem
they hit without reading a stack trace:

- DataSourceNetworkError: couldn't reach the host at all (DNS, refused,
  proxy block, timeout). Fix: check internet access / the URL's host.
- DataSourceHTTPError: reached the host, got a non-2xx response (404 =
  wrong URL/date/symbol, 403 = blocked or needs auth, etc). Fix: check
  the request against a browser/manual download of the same resource.
- DataSourceSchemaError: got a response, but its structure didn't match
  what the adapter expects (missing columns, unexpected format). Fix:
  the source likely changed format, or the adapter's documented-but-
  unverified assumption was wrong — compare against a real downloaded
  file.
- DataSourceQualityError: parsed fine structurally but failed a quality
  check (empty, all-NaN, huge gaps). Fix: likely a bad date range or a
  genuinely bad day of source data, not an adapter bug.
"""

from __future__ import annotations


class DataSourceError(RuntimeError):
    """Base class for all real-adapter data-acquisition failures."""


class DataSourceNetworkError(DataSourceError):
    """Could not reach the source at all."""


class DataSourceHTTPError(DataSourceError):
    """Reached the source; it returned a non-success HTTP status."""


class DataSourceSchemaError(DataSourceError):
    """Response received but didn't match the expected structure."""


class DataSourceQualityError(DataSourceError):
    """Parsed successfully but failed a data-quality check."""
