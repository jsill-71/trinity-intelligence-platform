"""
Workflow Engine - URL Validation to prevent SSRF
"""

from urllib.parse import urlparse

# Whitelist of allowed service domains
ALLOWED_SERVICES = {
    "user-management",
    "rca-api",
    "investigation-api",
    "vector-search",
    "audit-service",
    "notification-service",
    "ml-training",
    "agent-orchestrator",
    "query-optimizer",
    "data-aggregator",
    "alert-manager",
    "cache-service"
}

# Allowed ports
ALLOWED_PORTS = range(8000, 8016)  # 8000-8015

def validate_service_url(url: str) -> bool:
    """
    Validate that URL is safe to call (prevent SSRF)

    Returns True if URL is whitelisted, False otherwise
    """
    try:
        parsed = urlparse(url)

        # Must be HTTP
        if parsed.scheme not in ["http", "https"]:
            return False

        # Extract hostname (may include port)
        hostname = parsed.hostname
        port = parsed.port or 8000

        # Check if hostname is in allowed services
        if hostname not in ALLOWED_SERVICES:
            return False

        # Check if port is allowed
        if port not in ALLOWED_PORTS:
            return False

        return True

    except Exception:
        return False
