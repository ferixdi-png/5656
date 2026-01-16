#!/usr/bin/env python3
"""
БЕЗОПАСНАЯ очистка репозитория - удаляет ТОЛЬКО явно указанные файлы.
НЕ удаляет ничего из app/, bot/, models/, migrations/, tests/
"""
import os
from pathlib import Path

# ТОЛЬКО файлы, которые точно не нужны и не используются
SAFE_TO_DELETE = [
    # Старые entry points (если есть)
    "bot_kie.py",
    "run_bot.py",
    
    # Старые клиенты в корне (если есть)
    "kie_client.py",
    "kie_gateway.py", 
    "kie_universal_handler.py",
    "kie_input_adapter.py",
    "kie_models.py",
    "kie_schema.py",
    
    # Временные файлы
    "5656-main-ideal-self.zip",
    "all_models_test_results.json",
    "cheap_models_test_results.json",
    "model_generation_test_results_*.json",
    "audit_output.txt",
    "validation_output.txt",
    "e2e_test_output.txt",
    "prod_check_output.txt",
    "test_schema_output.txt",
    "verify_report.txt",
    
    # Старые отчеты (кроме TRT_REPORT.md)
    "TRT_REPORT_OLD.md",
    "TRT_REPORT_v2.md", 
    "TRT_REPORT.md.old",
    "AUDIT_FIXES_TOP50.md",
    "AUDIT_RESULT.json",
    "409_CONFLICT_FIX_REPORT.md",
    "AUTOPILOT_FINAL_REPORT.md",
    "AUTOPILOT_REPORT.md",
    "AUTOPILOT_UX_IMPROVEMENTS_REPORT.md",
    "BATCH_48_9_SUMMARY.md",
    "CIRCULAR_IMPORTS_FIX_REPORT.md",
    "COMPREHENSIVE_AUDIT_REPORT.md",
    "CRITICAL_FIXES_BATCH_48_10.md",
    "CRITICAL_FIXES_BATCH_48_11.md",
    "CRITICAL_FIXES_BATCH_48_12.md",
    "CYCLE_6_REPORT.md",
    "CYCLE_8_EMERGENCY_HOTFIX.md",
    "CYCLE_8_EXTENDED_SUMMARY.md",
    "CYCLE_9_PHASE_2_TASKS.md",
    "CYCLE_9_TELEMETRY_INTEGRATION.md",
    "DEPLOY_CHECKLIST.md",  # Если есть новый
    "E2E_DELIVERY_SUCCESS.txt",
    "FINAL_409_FIX_SUMMARY.md",
    "FINAL_AUTOPILOT_REPORT.md",
    "FINAL_FIXES_REPORT.md",
    "FINAL_GITHUB_ACTIONS_SUMMARY.md",
    "FINAL_INSTRUCTION.txt",
    "FINAL_PRODUCTION_STATUS.txt",
    "FINAL_RENDER_DEPLOYMENT_REPORT.md",
    "FINAL_STATUS_REPORT.md",
    "FINAL_SUMMARY_BALANCE_DEDUCTION.md",
    "FINAL_SUMMARY_INPUT_BUILDER.md",
    "FINAL_SUMMARY_MODELS_MENU.md",
    "FINAL_SUMMARY_RU.txt",
    "FINAL_UX_IMPROVEMENTS_SUMMARY.md",
    "FINAL_VERIFICATION_REPORT.md",
    "GENERATION_STABILIZATION_REPORT.md",
    "GITHUB_ACTIONS_FINAL_REPORT.md",
    "IMAGE_UPLOAD_FIX_SUMMARY.txt",
    "KIE_INTEGRATION_SUMMARY.md",
    "MODELS_NEED_MANUAL_MAPPING.txt",
    "MODELS_READINESS_REPORT.txt",
    "PR_OPS_OBSERVABILITY.md",
    "RENDER_HARDENING_REPORT.md",
    "SMOKE_QUICK_START.sh",
    "STABILIZATION_REPORT.md",
    "STORAGE_UNIFICATION_REPORT.md",
    "SYSTEM_EXPLANATION.txt",
    "SYSTEM_TEST_REPORT.md",
    "TOP_10_CRITICAL_FIXES_BATCH_48_15.md",
    "TOP_10_CRITICAL_FIXES_BATCH_48_16.md",
    "TOP_10_CRITICAL_FIXES_BATCH_48_17.md",
    "TOP_10_CRITICAL_FIXES_BATCH_48_18.md",
    "TOP_10_CRITICAL_ISSUES.md",
    "TOP_10_IMPROVEMENTS_BATCH_48_14.md",
    "VERIFICATION_REPORT.md",
    "VISIBLE_IMPROVEMENTS_SUMMARY.md",
]

# Папки для удаления (только если точно не нужны)
SAFE_DIRS_TO_DELETE = [
    "quarantine",
    "archive", 
    "legacy",
    "betboom_scanner",
    "bb_tt_scanner",
    "scanner_app",
    "scanner_min",
    "kie_sync",
    "5656",
]

def main():
    """Безопасная очистка - только явно указанные файлы."""
    root = Path(".")
    deleted = []
    errors = []
    
    print("Safe cleanup - deleting only explicitly listed files...\n")
    
    # Удаление файлов
    for filename in SAFE_TO_DELETE:
        # Обработка wildcards
        if "*" in filename:
            import glob
            matches = list(root.glob(filename))
            for match in matches:
                if match.is_file() and match.exists():
                    try:
                        match.unlink()
                        deleted.append(str(match))
                        print(f"  [OK] {match.name}")
                    except Exception as e:
                        errors.append(f"{match}: {e}")
        else:
            filepath = root / filename
            if filepath.exists() and filepath.is_file():
                try:
                    filepath.unlink()
                    deleted.append(filename)
                    print(f"  [OK] {filename}")
                except Exception as e:
                    errors.append(f"{filename}: {e}")
    
    # Удаление папок
    print("\nDeleting directories...")
    for dirname in SAFE_DIRS_TO_DELETE:
        dirpath = root / dirname
        if dirpath.exists() and dirpath.is_dir():
            try:
                import shutil
                shutil.rmtree(dirpath)
                deleted.append(f"DIR: {dirname}")
                print(f"  [OK] {dirname}/")
            except Exception as e:
                errors.append(f"{dirname}: {e}")
    
    print(f"\nDeleted: {len(deleted)} items")
    if errors:
        print(f"Errors: {len(errors)}")
    
    print("\nNext: git add -A && git commit -m 'Cleanup: remove unused files'")

if __name__ == "__main__":
    main()

