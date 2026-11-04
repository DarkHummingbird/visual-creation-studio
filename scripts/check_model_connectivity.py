"""Read-only transport checks. Does not read API keys or submit generation jobs."""
import json
import socket
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.work' / 'api-smoke'
OUT.mkdir(parents=True, exist_ok=True)
results = []
for host in ('cn-beijing.maas.qianwenaiapi.com', 'maas.qianwenaiapi.com'):
    row = {'host': host}
    try:
        row['dns_addresses'] = sorted({x[4][0] for x in socket.getaddrinfo(host, 443)})
    except Exception as e:
        row['dns_error'] = type(e).__name__
    try:
        with urllib.request.urlopen('https://' + host + '/', timeout=12) as r:
            row['http_status'] = r.status
    except urllib.error.HTTPError as e:
        row['http_status'] = e.code
    except Exception as e:
        row['transport_error'] = type(e).__name__
    results.append(row)
report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
          'paid_requests': 0, 'checks': results,
          'note': 'HTTP 404 only establishes a responding HTTPS host, not API authentication or model access.'}
(OUT / 'transport-diagnostic.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
