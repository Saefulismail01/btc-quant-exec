"""
Root conftest for proposed_code pytest suite.

Adds proposed_code/ to sys.path so that `from reconciliation.models import ...`
and `from signal_snapshot.models import ...` work without installing packages.

pytest-asyncio mode set to auto so async tests don't need @pytest.mark.asyncio
per-test (they still work with it, but it's not required).
"""

import sys
import os

# Make proposed_code/ the import root for reconciliation.* and signal_snapshot.*
_HERE = os.path.dirname(__file__)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
