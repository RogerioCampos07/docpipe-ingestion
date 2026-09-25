"""Container healthcheck with a finite deadline."""

import sys
from urllib.error import URLError
from urllib.request import urlopen

port = 9002 if sys.argv[1] == 'worker2' else 9001
if sys.argv[1] == 'api':
    port = 8000
try:
    with urlopen(f'http://127.0.0.1:{port}/health/ready', timeout=3) as r:
        sys.exit(0 if r.status == 200 else 1)  # noqa: PLR2004
except OSError, URLError:
    sys.exit(1)
