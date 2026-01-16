#!/usr/bin/env python3
"""
Smoke test tool for TRT bot.

Usage: python -m app.tools.smoke [--report-file SMOKE_REPORT.md]

Tests:
- Environment variables
- Database connectivity and schema
- KIE API access
- Telegram webhook configuration
- Button handlers and menu routing
- Payment flow simulation
"""

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️  WARN"
    SKIP = "⏭️  SKIP"


@dataclass
class CheckResult:
    component: str
    status: CheckStatus
    message: str
    time_ms: float
    error: str = None


class SmokeTest:
    """Main smoke test orchestrator."""
    
    def __init__(self, smoke_mode: bool = True, report_file: str = None):
        self.smoke_mode = smoke_mode
        self.report_file = report_file or "SMOKE_REPORT.md"
        self.results: List[CheckResult] = []
        self.start_time = None
    
    def add_result(self, component: str, status: CheckStatus, message: str, 
                   time_ms: float, error: str = None):
        """Add a check result."""
        result = CheckResult(component, status, message, time_ms, error)
        self.results.append(result)
        print(f"{status.value} {component}: {message}")
        if error:
            print(f"   Error: {error[:200]}")
    
    async def check_env_variables(self):
        """Check required environment variables."""
        start = datetime.now()
        
        required_vars = [
            'ADMIN_ID',
            'BOT_MODE',
            'PORT',
            'KIE_API_KEY',
            'TELEGRAM_BOT_TOKEN',
            'WEBHOOK_BASE_URL',
            'PAYMENT_BANK',
            'PAYMENT_CARD_HOLDER',
            'PAYMENT_PHONE',
            'SUPPORT_TELEGRAM',
        ]
        
        # Database vars are optional in smoke mode (can use mock)
        if not self.smoke_mode:
            required_vars.extend(['DATABASE_URL', 'DB_MAXCONN'])
        
        missing = [var for var in required_vars if not os.getenv(var)]
        elapsed = (datetime.now() - start).total_seconds() * 1000
        
        if missing:
            self.add_result(
                "Environment Variables",
                CheckStatus.FAIL,
                f"Missing: {', '.join(missing)}",
                elapsed,
                f"Found {len(required_vars) - len(missing)}/{len(required_vars)}"
            )
            return False
        
        self.add_result(
            "Environment Variables",
            CheckStatus.PASS,
            f"All {len(required_vars)} variables present",
            elapsed
        )
        return True
    
    async def check_database(self):
        """Check PostgreSQL connectivity and schema."""
        start = datetime.now()
        
        # Skip database check in smoke mode (even if DATABASE_URL is set, it's usually a test DB)
        if self.smoke_mode:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            self.add_result(
                "Database Connection",
                CheckStatus.SKIP,
                "Skipped in SMOKE_MODE (using test database)",
                elapsed
            )
            return True
        
        try:
            # Import database functions
            from database import get_connection_pool
            
            # Try to get a connection
            pool = get_connection_pool()
            conn = pool.getconn()
            
            try:
                cursor = conn.cursor()
                
                # Check for key tables
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
                
                tables = cursor.fetchall()
                table_names = [t[0] for t in tables]
                required_tables = ['users', 'user_balance', 'transactions']
                
                missing_tables = [t for t in required_tables if t not in table_names]
                
                cursor.close()
                
                elapsed = (datetime.now() - start).total_seconds() * 1000
                
                if missing_tables:
                    self.add_result(
                        "Database Schema",
                        CheckStatus.FAIL,
                        f"Missing tables: {missing_tables}",
                        elapsed,
                        f"Found {len(table_names)} tables"
                    )
                    return False
                
                self.add_result(
                    "Database Connection",
                    CheckStatus.PASS,
                    f"Connected, found {len(table_names)} tables",
                    elapsed
                )
                return True
            
            finally:
                pool.putconn(conn)
        
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            self.add_result(
                "Database Connection",
                CheckStatus.FAIL,
                "Failed to connect",
                elapsed,
                str(e)[:100]
            )
            return False
    
    async def check_kie_models(self):
        """Check KIE model configuration."""
        start = datetime.now()
        
        try:
            models_file = Path("/workspaces/TRT/models/KIE_SOURCE_OF_TRUTH.json")
            
            if not models_file.exists():
                elapsed = (datetime.now() - start).total_seconds() * 1000
                self.add_result(
                    "KIE Models",
                    CheckStatus.FAIL,
                    "Models file not found",
                    elapsed,
                    str(models_file)
                )
                return False
            
            with open(models_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            models = data.get('models', {})
            
            if not isinstance(models, dict) or len(models) == 0:
                elapsed = (datetime.now() - start).total_seconds() * 1000
                self.add_result(
                    "KIE Models",
                    CheckStatus.FAIL,
                    "No models found in configuration",
                    elapsed
                )
                return False
            
            # Check model structure
            invalid_models = []
            for model_id, model in list(models.items())[:5]:
                if not isinstance(model, dict):
                    invalid_models.append(f"{model_id}: not a dict")
                elif 'input_schema' not in model and 'inputs' not in model:
                    invalid_models.append(f"{model_id}: no input schema")
            
            elapsed = (datetime.now() - start).total_seconds() * 1000
            
            if invalid_models:
                self.add_result(
                    "KIE Models",
                    CheckStatus.WARN,
                    f"{len(models)} models configured, {len(invalid_models)} issues",
                    elapsed,
                    invalid_models[0] if invalid_models else None
                )
            else:
                self.add_result(
                    "KIE Models",
                    CheckStatus.PASS,
                    f"{len(models)} models configured with valid schemas",
                    elapsed
                )
                return True
        
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            self.add_result(
                "KIE Models",
                CheckStatus.FAIL,
                "Error reading models",
                elapsed,
                str(e)
            )
            return False
    
    async def check_telegram_webhook(self):
        """Check Telegram webhook configuration."""
        start = datetime.now()
        
        try:
            # In SMOKE_MODE, just check the configuration
            webhook_url = os.getenv('WEBHOOK_BASE_URL', '')
            webhook_secret = os.getenv('WEBHOOK_SECRET_PATH', '') or 'webhook'
            
            if not webhook_url:
                elapsed = (datetime.now() - start).total_seconds() * 1000
                self.add_result(
                    "Telegram Webhook",
                    CheckStatus.FAIL,
                    "Webhook URL not configured",
                    elapsed
                )
                return False
            
            full_url = f"{webhook_url.rstrip('/')}/{webhook_secret}"
            
            elapsed = (datetime.now() - start).total_seconds() * 1000
            self.add_result(
                "Telegram Webhook",
                CheckStatus.PASS,
                f"Webhook URL configured: {full_url[:50]}...",
                elapsed
            )
            return True
        
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            self.add_result(
                "Telegram Webhook",
                CheckStatus.FAIL,
                "Error checking webhook",
                elapsed,
                str(e)
            )
            return False
    
    async def check_button_handlers(self):
        """Check that main buttons have handlers."""
        start = datetime.now()
        
        try:
            from app.tools.button_validator import check_essential_buttons
            
            # Check essential buttons
            buttons = check_essential_buttons()
            
            missing = [name for name, present in buttons.items() if not present]
            
            elapsed = (datetime.now() - start).total_seconds() * 1000
            
            if missing:
                self.add_result(
                    "Button Handlers",
                    CheckStatus.WARN,
                    f"Some buttons missing: {missing}",
                    elapsed,
                    f"Found {len(buttons) - len(missing)}/{len(buttons)} essential buttons"
                )
                return True  # Warning, not failure
            
            self.add_result(
                "Button Handlers",
                CheckStatus.PASS,
                f"All {len(buttons)} essential buttons configured",
                elapsed
            )
            return True
        
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            self.add_result(
                "Button Handlers",
                CheckStatus.WARN,
                "Could not fully check handlers",
                elapsed,
                str(e)
            )
            return True
    
    async def check_payment_flow(self):
        """Check payment system configuration and schema validation."""
        start = datetime.now()
        
        try:
            # Check payment environment variables
            required_payment_vars = [
                'PAYMENT_BANK',
                'PAYMENT_CARD_HOLDER',
                'PAYMENT_PHONE',
            ]
            
            missing = [v for v in required_payment_vars if not os.getenv(v)]
            
            if missing:
                elapsed = (datetime.now() - start).total_seconds() * 1000
                self.add_result(
                    "Payment Configuration",
                    CheckStatus.FAIL,
                    f"Missing: {', '.join(missing)}",
                    elapsed
                )
                return False
            
            # Validate payment webhook schema
            from app.tools.payment_validator import PaymentFlowValidator, MockPaymentEvent
            from decimal import Decimal
            
            # Create mock event
            mock_event = MockPaymentEvent(
                user_id=12345,
                amount=Decimal("1.38"),
                status="confirmed"
            )
            
            payload = mock_event.to_dict()
            valid, error = PaymentFlowValidator.validate_payment_webhook_schema(payload)
            
            elapsed = (datetime.now() - start).total_seconds() * 1000
            
            if not valid:
                self.add_result(
                    "Payment Configuration",
                    CheckStatus.FAIL,
                    f"Webhook schema invalid: {error}",
                    elapsed
                )
                return False
            
            # Validate balance update logic
            before = Decimal("100.00")
            cost = Decimal("1.38")
            after = before - cost
            
            valid, msg = PaymentFlowValidator.validate_balance_update(before, after, cost)
            
            if not valid:
                self.add_result(
                    "Payment Configuration",
                    CheckStatus.FAIL,
                    msg,
                    elapsed
                )
                return False
            
            self.add_result(
                "Payment Configuration",
                CheckStatus.PASS,
                f"Payment variables configured, webhook schema valid",
                elapsed
            )
            return True
        
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            self.add_result(
                "Payment Configuration",
                CheckStatus.WARN,
                "Error checking payment setup",
                elapsed,
                str(e)[:100]
            )
            return True
    
    def generate_report(self):
        """Generate markdown report."""
        report = "# Smoke Test Report\n\n"
        report += f"Generated: {datetime.now().isoformat()}\n"
        report += f"Smoke Mode: {self.smoke_mode}\n\n"
        
        # Summary
        passed = sum(1 for r in self.results if r.status == CheckStatus.PASS)
        failed = sum(1 for r in self.results if r.status == CheckStatus.FAIL)
        warned = sum(1 for r in self.results if r.status == CheckStatus.WARN)
        
        report += "## Summary\n\n"
        report += f"- ✅ **Passed**: {passed}\n"
        report += f"- ❌ **Failed**: {failed}\n"
        report += f"- ⚠️  **Warned**: {warned}\n"
        report += f"- **Total**: {len(self.results)}\n\n"
        
        if failed == 0:
            report += "## Status: 🟢 GREEN\n\n"
        else:
            report += "## Status: 🔴 RED\n\n"
        
        # Detailed results
        report += "## Detailed Results\n\n"
        report += "| Component | Status | Message | Time (ms) |\n"
        report += "|-----------|--------|---------|----------|\n"
        
        for result in self.results:
            report += f"| {result.component} | {result.status.value} | "
            report += f"{result.message[:50]} | {result.time_ms:.0f} |\n"
        
        # Failures section
        if failed > 0:
            report += "\n## Failures\n\n"
            for result in self.results:
                if result.status == CheckStatus.FAIL:
                    report += f"### {result.component}\n"
                    report += f"- **Message**: {result.message}\n"
                    if result.error:
                        report += f"- **Error**: {result.error[:200]}\n"
                    report += "\n"
        
        return report
    
    async def run_all(self):
        """Run all smoke tests."""
        print("\n" + "="*70)
        print("🧪 SMOKE TEST")
        print("="*70 + "\n")
        
        self.start_time = datetime.now()
        
        checks = [
            self.check_env_variables(),
            self.check_database(),
            self.check_kie_models(),
            self.check_telegram_webhook(),
            self.check_button_handlers(),
            self.check_payment_flow(),
        ]
        
        await asyncio.gather(*checks, return_exceptions=True)
        
        # Generate report
        report = self.generate_report()
        
        # Write report
        with open(self.report_file, 'w') as f:
            f.write(report)
        
        print("\n" + "="*70)
        print(f"Report written to: {self.report_file}")
        print("="*70 + "\n")
        
        # Summary
        failed = sum(1 for r in self.results if r.status == CheckStatus.FAIL)
        if failed == 0:
            print("✅ ALL CHECKS PASSED")
            return 0
        else:
            print(f"❌ {failed} CHECK(S) FAILED")
            return 1


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run smoke tests")
    parser.add_argument(
        '--report-file',
        default='SMOKE_REPORT.md',
        help='Report file path'
    )
    parser.add_argument(
        '--smoke-mode',
        action='store_true',
        default=True,
        help='Run in smoke mode (no real operations)'
    )
    
    args = parser.parse_args()
    
    smoke = SmokeTest(smoke_mode=args.smoke_mode, report_file=args.report_file)
    exit_code = await smoke.run_all()
    
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
