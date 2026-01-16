"""Entry point for smoke test module."""

import asyncio
import sys
from app.tools.smoke import main

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
