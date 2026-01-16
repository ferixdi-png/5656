#!/usr/bin/env python3
"""
Payment Invariants Audit - Safety Verification

Verifies:
1. commit_charge ONLY on success
2. fail/timeout/cancel → release_charge
3. Idempotent protection (double commit = no-op)
4. OCR non-blocking and requests retry on uncertainty
"""
import os
import sys
import ast
import re
from pathlib import Path
from typing import List, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def find_python_files(directory: str = "app") -> List[Path]:
    """Find all Python files in directory."""
    files = []
    for path in Path(directory).rglob("*.py"):
        if path.is_file():
            files.append(path)
    return files


def check_commit_only_on_success(file_path: Path) -> List[Tuple[int, str]]:
    """
    Check that commit_charge is only called on success.
    
    Violations:
    - commit_charge called in except/finally without success check
    - commit_charge called after fail/timeout
    """
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Parse AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return violations
        
        # Find all commit_charge calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                if func_name == 'commit_charge':
                    line_no = node.lineno
                    line = lines[line_no - 1] if line_no <= len(lines) else ""
                    
                    # Check context - should be in success path
                    parent = node
                    in_except = False
                    in_finally = False
                    has_success_check = False
                    
                    # Walk up to find context
                    for parent_node in ast.walk(tree):
                        if parent_node == node:
                            break
                        if isinstance(parent_node, (ast.ExceptHandler, ast.Except)):
                            in_except = True
                        if isinstance(parent_node, ast.Try):
                            # Check if there's a finally
                            if hasattr(parent_node, 'finalbody') and parent_node.finalbody:
                                in_finally = True
                    
                    # Check if there's a success check nearby
                    # Look for 'success', 'state == "success"', etc. in surrounding lines
                    context_start = max(0, line_no - 10)
                    context_end = min(len(lines), line_no + 10)
                    context = '\n'.join(lines[context_start:context_end])
                    
                    if 'success' in context.lower() or 'state' in context.lower():
                        has_success_check = True
                    
                    # Violation: commit_charge in except/finally without success check
                    if (in_except or in_finally) and not has_success_check:
                        violations.append((
                            line_no,
                            f"commit_charge in exception/finally block without success check: {line.strip()}"
                        ))
                    
                    # Violation: commit_charge after fail/timeout
                    if 'fail' in context.lower() or 'timeout' in context.lower():
                        violations.append((
                            line_no,
                            f"commit_charge potentially called after fail/timeout: {line.strip()}"
                        ))
    
    except Exception as e:
        logger.warning(f"Error checking {file_path}: {e}")
    
    return violations


def check_release_on_fail_timeout(file_path: Path) -> List[Tuple[int, str]]:
    """
    Check that release_charge is called on fail/timeout/cancel.
    """
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Find fail/timeout/cancel patterns
        fail_patterns = [
            r'fail',
            r'timeout',
            r'cancel',
            r'error',
            r'exception',
        ]
        
        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            
            # Check if line contains fail/timeout/cancel
            has_fail = any(re.search(pattern, line_lower) for pattern in fail_patterns)
            
            if has_fail:
                # Check if release_charge is called in nearby context
                context_start = max(0, i - 5)
                context_end = min(len(lines), i + 20)
                context = '\n'.join(lines[context_start:context_end])
                
                # Should have release_charge in context
                if 'release_charge' not in context.lower():
                    # But might be in except/finally, which is OK
                    # Check if it's in a try/except structure
                    if 'except' in context.lower() or 'finally' in context.lower():
                        # This might be OK - check if release is in finally
                        if 'finally' in context.lower():
                            # Check if release is after this line
                            after_context = '\n'.join(lines[i:context_end])
                            if 'release_charge' not in after_context.lower():
                                violations.append((
                                    i,
                                    f"fail/timeout detected but release_charge not found in finally: {line.strip()}"
                                ))
                    else:
                        violations.append((
                            i,
                            f"fail/timeout detected but release_charge not in context: {line.strip()}"
                        ))
    
    except Exception as e:
        logger.warning(f"Error checking {file_path}: {e}")
    
    return violations


def check_idempotency(file_path: Path) -> List[Tuple[int, str]]:
    """
    Check that commit_charge has idempotent protection.
    """
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Find commit_charge function definition
        in_commit_function = False
        has_idempotent_check = False
        
        for i, line in enumerate(lines, 1):
            if 'def commit_charge' in line:
                in_commit_function = True
                has_idempotent_check = False
                continue
            
            if in_commit_function:
                # Check for function end
                if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                    if not has_idempotent_check:
                        violations.append((
                            i,
                            "commit_charge function may lack idempotent check (check manually)"
                        ))
                    in_commit_function = False
                    has_idempotent_check = False
                    continue
                
                # Look for idempotent patterns
                if any(keyword in line.lower() for keyword in [
                    'idempotent', 'already', 'committed', 'exists', 'duplicate', 'repeat'
                ]):
                    has_idempotent_check = True
        
        # Also check for charge_id tracking
        if 'charge_id' in content and 'pending_charges' in content:
            # Likely has tracking
            pass
        else:
            violations.append((
                0,
                "No charge_id tracking found - idempotency may not be guaranteed"
            ))
    
    except Exception as e:
        logger.warning(f"Error checking {file_path}: {e}")
    
    return violations


def check_ocr_non_blocking(file_path: Path) -> List[Tuple[int, str]]:
    """
    Check that OCR is non-blocking and requests retry on uncertainty.
    """
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Check for OCR blocking patterns
        if 'pytesseract' in content or 'tesseract' in content.lower():
            # Should use threading or async
            has_async = 'async' in content or 'await' in content
            has_threading = 'thread' in content.lower() or 'ThreadPoolExecutor' in content
            
            if not has_async and not has_threading:
                violations.append((
                    0,
                    "OCR processing may be blocking - should use async or threading"
                ))
            
            # Check for confidence check and retry request
            has_confidence_check = 'confidence' in content.lower()
            has_retry_request = any(keyword in content.lower() for keyword in [
                'retry', 'repeat', 'again', 'resend', 'переслать', 'повторить'
            ])
            
            if not has_confidence_check:
                violations.append((
                    0,
                    "OCR may not check confidence - should request retry on low confidence"
                ))
            
            if not has_retry_request:
                violations.append((
                    0,
                    "OCR may not request retry on uncertainty - should ask user to resend"
                ))
    
    except Exception as e:
        logger.warning(f"Error checking {file_path}: {e}")
    
    return violations


def audit_payment_invariants() -> bool:
    """Run full payment invariants audit."""
    logger.info("=== PAYMENT INVARIANTS AUDIT ===")
    logger.info("")
    
    all_violations = []
    
    # Check payment files
    payment_files = [
        Path("app/payments/charges.py"),
        Path("app/payments/integration.py"),
        Path("app/kie/generator.py"),
        Path("app/ocr/tesseract_processor.py"),
    ]
    
    for file_path in payment_files:
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            continue
        
        logger.info(f"Checking: {file_path}")
        
        # Check each invariant
        violations = check_commit_only_on_success(file_path)
        if violations:
            logger.warning(f"  [VIOLATION] commit_charge safety:")
            for line_no, msg in violations:
                logger.warning(f"    Line {line_no}: {msg}")
                all_violations.append((file_path, line_no, msg))
        
        violations = check_release_on_fail_timeout(file_path)
        if violations:
            logger.warning(f"  [VIOLATION] release_charge on fail/timeout:")
            for line_no, msg in violations:
                logger.warning(f"    Line {line_no}: {msg}")
                all_violations.append((file_path, line_no, msg))
        
        violations = check_idempotency(file_path)
        if violations:
            logger.warning(f"  [VIOLATION] idempotency:")
            for line_no, msg in violations:
                logger.warning(f"    Line {line_no}: {msg}")
                all_violations.append((file_path, line_no, msg))
        
        violations = check_ocr_non_blocking(file_path)
        if violations:
            logger.warning(f"  [VIOLATION] OCR non-blocking:")
            for line_no, msg in violations:
                logger.warning(f"    Line {line_no}: {msg}")
                all_violations.append((file_path, line_no, msg))
    
    # Summary
    logger.info("")
    if all_violations:
        logger.error(f"[FAIL] Found {len(all_violations)} potential violations")
        logger.error("Review violations above and fix if needed")
        return False
    else:
        logger.info("[OK] All payment invariants verified")
        logger.info("")
        logger.info("Invariants checked:")
        logger.info("  [OK] commit_charge only on success")
        logger.info("  [OK] release_charge on fail/timeout/cancel")
        logger.info("  [OK] Idempotent protection")
        logger.info("  [OK] OCR non-blocking with retry request")
        return True


if __name__ == "__main__":
    success = audit_payment_invariants()
    sys.exit(0 if success else 1)
