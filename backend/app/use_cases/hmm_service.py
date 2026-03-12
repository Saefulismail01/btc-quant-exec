"""
hmm_service.py — BACKWARD COMPATIBILITY SHIM

This module has been renamed to bcd_service.py (2026-03-04).
All symbols are re-exported from bcd_service for zero-breakage migration.

Old imports still work:
    from app.services.hmm_service import get_hmm_service   # OK
    from app.services.hmm_service import Layer1EngineService  # OK

New preferred imports:
    from app.services.bcd_service import get_bcd_service
    from app.services.bcd_service import Layer1EngineService
"""
from app.services.bcd_service import (  # noqa: F401
    Layer1EngineService,
    get_bcd_service,
    get_bcd_service as get_hmm_service,  # alias: identical singleton
)

__all__ = ["Layer1EngineService", "get_bcd_service", "get_hmm_service"]
