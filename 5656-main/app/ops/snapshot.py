"""
Ops snapshot generator (for admin command).

Generates ops snapshot and formats summary for admin delivery.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from app.ops.critical5 import detect_critical5, CriticalIssue


def generate_snapshot_summary(
    render_logs_file: Optional[Path] = None,
    db_diag_file: Optional[Path] = None,
) -> str:
    """
    Generate human-readable snapshot summary.
    
    Args:
        render_logs_file: Path to render_logs_latest.txt
        db_diag_file: Path to db_diag_latest.json
    
    Returns:
        Formatted summary text (safe for Telegram, no secrets)
    """
    # Detect critical issues
    issues = detect_critical5(render_logs_file, db_diag_file)
    
    summary_lines = [
        "📊 <b>Ops Snapshot</b>",
        f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]
    
    if not issues:
        summary_lines.append("✅ <b>No critical issues detected</b>")
    else:
        summary_lines.append(f"🚨 <b>Top {len(issues)} Critical Issues:</b>")
        summary_lines.append("")
        
        for i, issue in enumerate(issues[:5], 1):
            risk_emoji = {
                "CRITICAL": "🔴",
                "HIGH": "🟠",
                "MEDIUM": "🟡",
                "LOW": "🟢",
            }.get(issue.risk_level, "⚪")
            
            summary_lines.append(
                f"{i}. {risk_emoji} <b>{issue.title}</b>"
            )
            summary_lines.append(f"   Impact: {issue.impact}")
            summary_lines.append(f"   Risk: {issue.risk_level}")
            summary_lines.append("")
    
    # Add DB status if available
    if db_diag_file and db_diag_file.exists():
        try:
            with open(db_diag_file, "r") as f:
                db_data = json.load(f)
            
            if db_data.get("connection_ok"):
                activity = db_data.get("pg_stat_activity", {})
                if isinstance(activity, dict):
                    total = activity.get("total_connections", 0)
                    active = activity.get("active_connections", 0)
                    summary_lines.append(f"💾 <b>DB Status:</b> OK ({active}/{total} active)")
                
                recent_errors = db_data.get("recent_errors_1h")
                if recent_errors:
                    summary_lines.append(f"⚠️ Errors (1h): {recent_errors}")
            else:
                summary_lines.append("❌ <b>DB Status:</b> Connection failed")
        except Exception:
            pass
    
    return "\n".join(summary_lines)


def get_snapshot_files() -> tuple[Optional[Path], Optional[Path]]:
    """Get paths to latest snapshot files."""
    render_logs = Path("artifacts/render_logs_latest.txt")
    db_diag = Path("artifacts/db_diag_latest.json")
    
    return (
        render_logs if render_logs.exists() else None,
        db_diag if db_diag.exists() else None,
    )

