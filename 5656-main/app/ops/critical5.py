"""
Critical 5 detector.

Analyzes Render logs + DB diagnostics to identify top-5 critical issues.
"""

import sys
import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime

from app.ops.observer_config import load_config


class CriticalIssue:
    """Represents a critical issue."""
    
    def __init__(
        self,
        title: str,
        impact: str,
        evidence: List[str],
        root_cause: str,
        proposed_fix: str,
        risk_level: str,  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
        score: int,
    ):
        self.title = title
        self.impact = impact
        self.evidence = evidence
        self.root_cause = root_cause
        self.proposed_fix = proposed_fix
        self.risk_level = risk_level
        self.score = score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON output."""
        return {
            "title": self.title,
            "impact": self.impact,
            "evidence": self.evidence,
            "root_cause": self.root_cause,
            "proposed_fix": self.proposed_fix,
            "risk_level": self.risk_level,
            "score": self.score,
        }
    
    def to_markdown(self) -> str:
        """Convert to markdown."""
        return f"""### {self.title}

**Impact**: {self.impact}  
**Risk Level**: {self.risk_level}  
**Score**: {self.score}

**Evidence**:
{chr(10).join(f"- {e}" for e in self.evidence[:5])}

**Root Cause**: {self.root_cause}

**Proposed Fix**: {self.proposed_fix}
"""


def analyze_render_logs(log_file: Path) -> List[CriticalIssue]:
    """Analyze Render logs for critical issues."""
    issues = []
    
    if not log_file.exists():
        return issues
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            logs = f.read()
    except Exception:
        return issues
    
    lines = logs.split("\n")
    
    # Pattern detection
    error_count = len([l for l in lines if "ERROR" in l.upper() or "Exception" in l])
    passive_reject_count = len([l for l in lines if "PASSIVE_REJECT" in l])
    dispatch_fail_count = len([l for l in lines if "DISPATCH_FAIL" in l])
    unknown_callback_count = len([l for l in lines if "UNKNOWN_CALLBACK" in l])
    lock_wait_count = len([l for l in lines if "LOCK" in l.upper() and ("WAIT" in l.upper() or "NOT ACQUIRED" in l.upper())])
    timeout_count = len([l for l in lines if "TIMEOUT" in l.upper() or "timeout" in l])
    queue_full_count = len([l for l in lines if "queue full" in l.lower() or "QUEUE_FULL" in l])
    
    # Issue 1: High error rate
    if error_count > 10:
        issues.append(CriticalIssue(
            title="High Error Rate in Logs",
            impact="Reliability: User requests may fail silently or with errors",
            evidence=[
                f"Found {error_count} ERROR/Exception lines in recent logs",
                "Check logs for stack traces and error patterns",
            ],
            root_cause="Unhandled exceptions or external service failures",
            proposed_fix="Review error patterns, add error handling, check external service health",
            risk_level="HIGH" if error_count > 50 else "MEDIUM",
            score=error_count * 2,
        ))
    
    # Issue 2: PASSIVE_REJECT events
    if passive_reject_count > 5:
        issues.append(CriticalIssue(
            title="PASSIVE Mode Rejecting Requests",
            impact="UX: Users see loading spinners but requests are rejected",
            evidence=[
                f"Found {passive_reject_count} PASSIVE_REJECT events",
                "Instance may be stuck in PASSIVE mode or lock contention",
            ],
            root_cause="Singleton lock not acquired, or deploy overlap causing PASSIVE state",
            proposed_fix="Check lock status, verify only one instance is ACTIVE, review deploy process",
            risk_level="HIGH" if passive_reject_count > 20 else "MEDIUM",
            score=passive_reject_count * 3,
        ))
    
    # Issue 3: DISPATCH_FAIL events
    if dispatch_fail_count > 5:
        issues.append(CriticalIssue(
            title="Handler Dispatch Failures",
            impact="UX: User actions not processed, no response",
            evidence=[
                f"Found {dispatch_fail_count} DISPATCH_FAIL events",
                "Handlers are crashing or timing out",
            ],
            root_cause="Unhandled exceptions in handlers, timeout issues, or resource exhaustion",
            proposed_fix="Review handler code, add error handling, check resource limits",
            risk_level="HIGH" if dispatch_fail_count > 20 else "MEDIUM",
            score=dispatch_fail_count * 4,
        ))
    
    # Issue 4: Unknown callbacks
    if unknown_callback_count > 3:
        issues.append(CriticalIssue(
            title="Unknown Callback Queries",
            impact="UX: Buttons not responding, users see no feedback",
            evidence=[
                f"Found {unknown_callback_count} UNKNOWN_CALLBACK events",
                "Callback data not matching any registered handler",
            ],
            root_cause="Callback data mismatch, missing handlers, or stale UI state",
            proposed_fix="Review callback routing, ensure all buttons have handlers, check FSM state",
            risk_level="MEDIUM",
            score=unknown_callback_count * 2,
        ))
    
    # Issue 5: Queue full
    if queue_full_count > 0:
        issues.append(CriticalIssue(
            title="Update Queue Full",
            impact="Reliability: Updates dropped, users see no response",
            evidence=[
                f"Found {queue_full_count} 'queue full' messages",
                "System overloaded, cannot process updates fast enough",
            ],
            root_cause="High traffic, slow processing, or insufficient workers",
            proposed_fix="Increase worker count, optimize handler performance, add backpressure handling",
            risk_level="CRITICAL" if queue_full_count > 10 else "HIGH",
            score=queue_full_count * 10,
        ))
    
    # Issue 6: Lock contention
    if lock_wait_count > 5:
        issues.append(CriticalIssue(
            title="Lock Contention",
            impact="Reliability: Instances competing for lock, potential race conditions",
            evidence=[
                f"Found {lock_wait_count} lock wait/not acquired messages",
                "Multiple instances trying to acquire singleton lock",
            ],
            root_cause="Deploy overlap, stale lock, or lock cleanup not working",
            proposed_fix="Review lock mechanism, ensure proper cleanup, check deploy process",
            risk_level="HIGH",
            score=lock_wait_count * 3,
        ))
    
    # Issue 7: Timeouts
    if timeout_count > 5:
        issues.append(CriticalIssue(
            title="Request Timeouts",
            impact="Reliability: Operations timing out, incomplete processing",
            evidence=[
                f"Found {timeout_count} timeout messages",
                "Operations taking too long to complete",
            ],
            root_cause="Slow external APIs, database queries, or resource exhaustion",
            proposed_fix="Review timeout settings, optimize slow operations, add retries",
            risk_level="MEDIUM",
            score=timeout_count * 2,
        ))
    
    return issues


def analyze_db_diagnostics(db_file: Path) -> List[CriticalIssue]:
    """Analyze DB diagnostics for critical issues."""
    issues = []
    
    if not db_file.exists():
        return issues
    
    try:
        with open(db_file, "r", encoding="utf-8") as f:
            db_data = json.load(f)
    except Exception:
        return issues
    
    # Check connection
    if not db_data.get("connection_ok"):
        issues.append(CriticalIssue(
            title="Database Connection Failed",
            impact="CRITICAL: Cannot connect to database",
            evidence=[f"Connection error: {db_data.get('error', 'Unknown')}"],
            root_cause="Database down, network issue, or credentials invalid",
            proposed_fix="Check database status, network connectivity, credentials",
            risk_level="CRITICAL",
            score=1000,
        ))
        return issues  # Can't analyze further if DB is down
    
    # Check connection pool
    activity = db_data.get("pg_stat_activity", {})
    if isinstance(activity, dict) and "total_connections" in activity:
        total = activity.get("total_connections", 0)
        max_conn = db_data.get("max_connections")
        if max_conn and total > max_conn * 0.8:
            issues.append(CriticalIssue(
                title="High Database Connection Usage",
                impact="Reliability: Approaching connection limit, may reject new connections",
                evidence=[
                    f"Using {total}/{max_conn} connections ({100*total/max_conn:.1f}%)",
                    "May cause connection pool exhaustion",
                ],
                root_cause="Connection leaks, insufficient pool size, or long-running queries",
                proposed_fix="Review connection pool settings, check for leaks, optimize queries",
                risk_level="HIGH" if total > max_conn * 0.9 else "MEDIUM",
                score=int((total / max_conn) * 100),
            ))
    
    # Check recent errors
    recent_errors = db_data.get("recent_errors_1h")
    if recent_errors and recent_errors > 10:
        issues.append(CriticalIssue(
            title="High Error Rate in Database Events",
            impact="Reliability: Many errors recorded in app_events table",
            evidence=[
                f"Found {recent_errors} ERROR/CRITICAL events in last hour",
                "Check app_events table for error patterns",
            ],
            root_cause="Application errors, external service failures, or data issues",
            proposed_fix="Review app_events table, check error patterns, fix root causes",
            risk_level="HIGH" if recent_errors > 50 else "MEDIUM",
            score=recent_errors * 2,
        ))
    
    # Check slow queries
    slow_queries = db_data.get("slow_queries")
    if slow_queries and len(slow_queries) > 0:
        avg_time = sum(q.get("mean_exec_time", 0) for q in slow_queries) / len(slow_queries)
        if avg_time > 1000:  # > 1 second
            issues.append(CriticalIssue(
                title="Slow Database Queries",
                impact="Performance: Queries taking >1s, may cause timeouts",
                evidence=[
                    f"Found {len(slow_queries)} slow queries (avg {avg_time:.0f}ms)",
                    "Check pg_stat_statements for query patterns",
                ],
                root_cause="Missing indexes, inefficient queries, or database load",
                proposed_fix="Add indexes, optimize queries, review database load",
                risk_level="MEDIUM",
                score=int(avg_time / 10),
            ))
    
    return issues


def detect_critical5(
    render_logs_file: Optional[Path] = None,
    db_diag_file: Optional[Path] = None,
) -> List[CriticalIssue]:
    """
    Detect top-5 critical issues from logs and DB diagnostics.
    
    Args:
        render_logs_file: Path to render_logs_latest.txt
        db_diag_file: Path to db_diag_latest.json
    
    Returns:
        List of CriticalIssue objects, sorted by score (descending)
    """
    all_issues = []
    
    # Analyze Render logs
    if render_logs_file:
        all_issues.extend(analyze_render_logs(render_logs_file))
    
    # Analyze DB diagnostics
    if db_diag_file:
        all_issues.extend(analyze_db_diagnostics(db_diag_file))
    
    # Sort by score (descending) and return top 5
    all_issues.sort(key=lambda x: x.score, reverse=True)
    return all_issues[:5]


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Detect top-5 critical issues")
    parser.add_argument(
        "--render-logs",
        type=str,
        default="artifacts/render_logs_latest.txt",
        help="Path to render logs file"
    )
    parser.add_argument(
        "--db-diag",
        type=str,
        default="artifacts/db_diag_latest.json",
        help="Path to DB diagnostics file"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="artifacts/critical5.md",
        help="Output file path (default: artifacts/critical5.md)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of Markdown"
    )
    
    args = parser.parse_args()
    
    render_logs_path = Path(args.render_logs) if args.render_logs else None
    db_diag_path = Path(args.db_diag) if args.db_diag else None
    
    # Detect issues
    issues = detect_critical5(render_logs_path, db_diag_path)
    
    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    if args.json:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([issue.to_dict() for issue in issues], f, indent=2)
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# Critical 5 Issues\n\n")
            f.write(f"Generated: {datetime.utcnow().isoformat()}Z\n\n")
            f.write(f"Top {len(issues)} critical issues detected:\n\n")
            for i, issue in enumerate(issues, 1):
                f.write(f"## {i}. {issue.title}\n\n")
                f.write(issue.to_markdown())
                f.write("\n")
    
    print(f"✅ Detected {len(issues)} critical issues, saved to {out_path}", file=sys.stderr)
    sys.exit(0 if len(issues) == 0 else 1)  # Exit 1 if issues found


if __name__ == "__main__":
    main()

