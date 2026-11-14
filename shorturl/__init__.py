"""shorturl - URL shortener with a stdlib HTTP API and SQLite storage."""

from .store import Shortener, resolve_path

__all__ = ["Shortener", "resolve_path"]
