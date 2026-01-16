"""
Render logs fetcher (read-only, safe).

Fetches logs from Render API and stores sanitized snapshot.
"""

import sys
import re
import argparse
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("ERROR: requests library required. Install: pip install requests", file=sys.stderr)
    sys.exit(1)

from app.ops.observer_config import load_config, validate_config


def redact_secrets(text: str) -> str:
    """Redact secrets from log text."""
    # Redact API keys (rnd_...)
    text = re.sub(r'rnd_[a-zA-Z0-9]{20,}', 'rnd_***REDACTED***', text)
    
    # Redact tokens (Bearer ...)
    text = re.sub(r'Bearer\s+[a-zA-Z0-9_-]{20,}', 'Bearer ***REDACTED***', text)
    
    # Redact URLs with tokens
    text = re.sub(r'https?://[^\s]+token=[^\s]+', 'https://***REDACTED***', text)
    text = re.sub(r'https?://[^\s]+key=[^\s]+', 'https://***REDACTED***', text)
    
    # Redact DATABASE_URL (show only host)
    text = re.sub(
        r'postgresql://[^:]+:[^@]+@([^/]+)/',
        r'postgresql://***:***@\1/',
        text
    )
    
    return text


def fetch_render_logs(
    api_key: str,
    service_id: str,
    minutes: Optional[int] = None,
    lines: Optional[int] = None,
) -> List[str]:
    """
    Fetch logs from Render API.
    
    Args:
        api_key: Render API key
        service_id: Render service ID
        minutes: Fetch logs from last N minutes (if None, uses lines)
        lines: Fetch last N lines (if None and minutes is None, defaults to 100)
    
    Returns:
        List of log lines (sanitized)
    """
    url = f"https://api.render.com/v1/services/{service_id}/logs"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    params = {}
    
    if minutes:
        since_time = datetime.utcnow() - timedelta(minutes=minutes)
        params["since"] = int(since_time.timestamp())
    elif lines:
        params["limit"] = lines
    else:
        params["limit"] = 100  # Default
    
    all_logs = []
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse response (Render API format may vary)
        if isinstance(data, dict):
            if "logs" in data:
                for log_entry in data["logs"]:
                    if isinstance(log_entry, dict):
                        message = log_entry.get("message", "")
                        timestamp = log_entry.get("timestamp", "")
                        if message:
                            all_logs.append(f"[{timestamp}] {message}")
                    elif isinstance(log_entry, str):
                        all_logs.append(log_entry)
            elif "data" in data:
                log_text = data["data"]
                if isinstance(log_text, str):
                    all_logs = log_text.split("\n")
        elif isinstance(data, list):
            for log_entry in data:
                if isinstance(log_entry, dict):
                    message = log_entry.get("message", "")
                    timestamp = log_entry.get("timestamp", "")
                    if message:
                        all_logs.append(f"[{timestamp}] {message}")
                elif isinstance(log_entry, str):
                    all_logs.append(log_entry)
        elif isinstance(data, str):
            all_logs = data.split("\n")
        
        # Sanitize logs
        all_logs = [redact_secrets(line) for line in all_logs]
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("ERROR: Invalid RENDER_API_KEY (401 Unauthorized)", file=sys.stderr)
        elif e.response.status_code == 403:
            print("ERROR: Access forbidden (403) - check API key permissions", file=sys.stderr)
        elif e.response.status_code == 404:
            print(f"ERROR: Service {service_id} not found (404)", file=sys.stderr)
        else:
            print(f"ERROR: HTTP {e.response.status_code}: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch logs: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    
    return all_logs


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Fetch Render logs (read-only)")
    parser.add_argument("--minutes", type=int, help="Fetch logs from last N minutes")
    parser.add_argument("--lines", type=int, help="Fetch last N lines")
    parser.add_argument(
        "--out",
        type=str,
        default="artifacts/render_logs_latest.txt",
        help="Output file path (default: artifacts/render_logs_latest.txt)"
    )
    
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    
    if not validate_config(config, require_render=True):
        print(
            "ERROR: RENDER_API_KEY and RENDER_SERVICE_ID required.\n"
            "Set via env vars or Desktop TRT_RENDER.env file.",
            file=sys.stderr
        )
        sys.exit(1)
    
    # Fetch logs
    print(f"Fetching logs for service {config.render_service_id}...", file=sys.stderr)
    logs = fetch_render_logs(
        config.render_api_key,
        config.render_service_id,
        minutes=args.minutes,
        lines=args.lines,
    )
    
    print(f"Fetched {len(logs)} log lines", file=sys.stderr)
    
    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Render Logs Snapshot\n")
        f.write(f"# Service: {config.render_service_id}\n")
        f.write(f"# Fetched: {datetime.utcnow().isoformat()}Z\n")
        f.write(f"# Lines: {len(logs)}\n")
        f.write(f"#\n")
        f.write("\n".join(logs))
    
    print(f"✅ Saved to {out_path}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()

