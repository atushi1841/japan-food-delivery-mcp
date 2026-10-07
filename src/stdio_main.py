"""stdio entry point — MCPB bundle (local execution)."""
from __future__ import annotations

import logging
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import server  # noqa: E402

def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    server.server.run()

if __name__ == "__main__":
    main()
