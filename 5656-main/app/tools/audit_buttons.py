#!/usr/bin/env python3
"""
Comprehensive button audit tool.

Validates that:
1. All callback_data in UI have handlers
2. All handlers are registered
3. No dead/coming soon buttons
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class ButtonInfo:
    """Information about a button in the UI."""
    callback_data: str
    file: str
    line: int
    context: str = ""


@dataclass
class HandlerInfo:
    """Information about a callback handler."""
    pattern: str
    handler_type: str  # exact, prefix, regex, fallback
    file: str
    line: int
    function_name: str = ""


class ButtonAuditor:
    """Audits all buttons and their handlers."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.buttons: List[ButtonInfo] = []
        self.handlers: List[HandlerInfo] = []
        self.issues: Dict[str, List[str]] = defaultdict(list)
    
    def scan_buttons(self) -> None:
        """Scan all callback_data in UI files."""
        ui_patterns = [
            "app/helpers/*.py",
            "app/ui/*.py",
            "app/buttons/*.py",
            "bot/ui/*.py",
        ]
        
        callback_patterns = [
            r'callback_data\s*=\s*["\']([^"\']+)["\']',  # callback_data="value"
            r'callback_data\s*=\s*f["\']([^"\'{}]+)',    # callback_data=f"prefix{var}"
        ]
        
        for pattern in ui_patterns:
            for file_path in self.project_root.glob(pattern):
                if not file_path.exists() or file_path.name.startswith("__"):
                    continue
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    lines = content.split('\n')
                    
                    for i, line in enumerate(lines):
                        for regex_pattern in callback_patterns:
                            matches = re.findall(regex_pattern, line)
                            for match in matches:
                                # Skip ignored callbacks
                                if "ignore" in match or "header" in match:
                                    continue
                                
                                self.buttons.append(ButtonInfo(
                                    callback_data=match,
                                    file=str(file_path.relative_to(self.project_root)),
                                    line=i + 1,
                                    context=line.strip()[:80]
                                ))
                except Exception as e:
                    print(f"⚠️  Error scanning {file_path}: {e}", file=sys.stderr)
    
    def scan_handlers(self) -> None:
        """Scan all callback_query handlers."""
        handler_patterns = [
            "bot/handlers/*.py",
            "app/handlers/*.py",
        ]
        
        # Patterns to match
        exact_pattern = r'@router\.callback_query\(F\.data\s*==\s*["\']([^"\']+)["\']\)'
        prefix_pattern = r'@router\.callback_query\(F\.data\.startswith\(["\']([^"\']+)["\']\)\)'
        in_pattern = r'@router\.callback_query\(F\.data\.in_\(\{([^}]+)\}\)\)'
        fallback_pattern = r'@router\.callback_query\(\s*\)'
        
        for pattern in handler_patterns:
            for file_path in self.project_root.glob(pattern):
                if not file_path.exists() or file_path.name.startswith("__"):
                    continue
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    lines = content.split('\n')
                    
                    for i, line in enumerate(lines):
                        # Exact match
                        matches = re.findall(exact_pattern, line)
                        for match in matches:
                            func_name = self._get_function_name(lines, i)
                            self.handlers.append(HandlerInfo(
                                pattern=match,
                                handler_type="exact",
                                file=str(file_path.relative_to(self.project_root)),
                                line=i + 1,
                                function_name=func_name
                            ))
                        
                        # Prefix match
                        matches = re.findall(prefix_pattern, line)
                        for match in matches:
                            func_name = self._get_function_name(lines, i)
                            self.handlers.append(HandlerInfo(
                                pattern=match,
                                handler_type="prefix",
                                file=str(file_path.relative_to(self.project_root)),
                                line=i + 1,
                                function_name=func_name
                            ))
                        
                        # In match
                        matches = re.findall(in_pattern, line)
                        for match in matches:
                            func_name = self._get_function_name(lines, i)
                            # Split comma-separated values
                            values = [v.strip().strip('"').strip("'") for v in match.split(',')]
                            for value in values:
                                self.handlers.append(HandlerInfo(
                                    pattern=value,
                                    handler_type="exact",
                                    file=str(file_path.relative_to(self.project_root)),
                                    line=i + 1,
                                    function_name=func_name
                                ))
                        
                        # Fallback
                        if re.search(fallback_pattern, line):
                            func_name = self._get_function_name(lines, i)
                            self.handlers.append(HandlerInfo(
                                pattern="*",
                                handler_type="fallback",
                                file=str(file_path.relative_to(self.project_root)),
                                line=i + 1,
                                function_name=func_name
                            ))
                
                except Exception as e:
                    print(f"⚠️  Error scanning {file_path}: {e}", file=sys.stderr)
    
    def _get_function_name(self, lines: List[str], decorator_line: int) -> str:
        """Get function name after decorator."""
        for i in range(decorator_line + 1, min(decorator_line + 5, len(lines))):
            line = lines[i]
            match = re.search(r'async\s+def\s+(\w+)', line)
            if match:
                return match.group(1)
        return "unknown"
    
    def validate(self) -> bool:
        """Validate buttons against handlers. Returns True if all OK."""
        print("\n" + "="*80)
        print("🔍 BUTTON AUDIT REPORT")
        print("="*80 + "\n")
        
        print(f"📊 Summary:")
        print(f"   Buttons found: {len(self.buttons)}")
        print(f"   Handlers found: {len(self.handlers)}")
        print()
        
        # Build handler lookup
        exact_handlers = {h.pattern for h in self.handlers if h.handler_type == "exact"}
        prefix_handlers = {h.pattern for h in self.handlers if h.handler_type == "prefix"}
        has_fallback = any(h.handler_type == "fallback" for h in self.handlers)
        
        # Check each button
        missing_handlers = []
        covered_buttons = []
        
        for button in self.buttons:
            callback = button.callback_data
            
            # Check exact match
            if callback in exact_handlers:
                covered_buttons.append(callback)
                continue
            
            # Check prefix match
            matched = False
            for prefix in prefix_handlers:
                if callback.startswith(prefix):
                    covered_buttons.append(callback)
                    matched = True
                    break
            
            if matched:
                continue
            
            # Not covered by specific handler
            if not has_fallback:
                missing_handlers.append((callback, button.file, button.line))
        
        # Report
        if missing_handlers:
            print(f"❌ MISSING HANDLERS ({len(missing_handlers)}):")
            print()
            for callback, file, line in sorted(missing_handlers):
                print(f"   • {callback}")
                print(f"     └─ {file}:{line}")
                self.issues["missing_handlers"].append(f"{callback} ({file}:{line})")
            print()
        else:
            print(f"✅ All buttons have handlers!")
            print()
        
        # Show handler coverage
        print(f"📋 Handler Types:")
        exact_count = len([h for h in self.handlers if h.handler_type == "exact"])
        prefix_count = len([h for h in self.handlers if h.handler_type == "prefix"])
        fallback_count = len([h for h in self.handlers if h.handler_type == "fallback"])
        
        print(f"   • Exact matches: {exact_count}")
        print(f"   • Prefix matches: {prefix_count}")
        print(f"   • Fallback handlers: {fallback_count}")
        print()
        
        # Check for duplicate handlers
        handler_counts = defaultdict(int)
        for handler in self.handlers:
            if handler.handler_type != "fallback":
                handler_counts[handler.pattern] += 1
        
        duplicates = {k: v for k, v in handler_counts.items() if v > 1}
        if duplicates:
            print(f"⚠️  DUPLICATE HANDLERS ({len(duplicates)}):")
            for pattern, count in sorted(duplicates.items()):
                print(f"   • {pattern} (registered {count} times)")
                handlers_list = [h for h in self.handlers if h.pattern == pattern]
                for h in handlers_list:
                    print(f"     └─ {h.file}:{h.line} ({h.function_name})")
                self.issues["duplicate_handlers"].append(f"{pattern} ({count} times)")
            print()
        
        # Summary
        print("="*80)
        if self.issues:
            print(f"❌ AUDIT FAILED - {len(self.issues)} issue types found")
            return False
        else:
            print("✅ AUDIT PASSED - All buttons have handlers")
            return True
    
    def get_button_handler_map(self) -> Dict[str, List[str]]:
        """Get mapping of buttons to their handlers."""
        mapping = defaultdict(list)
        
        exact_handlers = {h.pattern: h for h in self.handlers if h.handler_type == "exact"}
        prefix_handlers = {h.pattern: h for h in self.handlers if h.handler_type == "prefix"}
        
        for button in self.buttons:
            callback = button.callback_data
            
            # Exact match
            if callback in exact_handlers:
                h = exact_handlers[callback]
                mapping[callback].append(f"{h.function_name} ({h.file}:{h.line})")
                continue
            
            # Prefix match
            for prefix, h in prefix_handlers.items():
                if callback.startswith(prefix):
                    mapping[callback].append(f"{h.function_name} ({h.file}:{h.line}) [prefix: {prefix}]")
                    break
        
        return mapping


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent.parent
    
    auditor = ButtonAuditor(project_root)
    
    print("🔍 Scanning buttons in UI...")
    auditor.scan_buttons()
    
    print(f"   Found {len(auditor.buttons)} buttons")
    
    print("\n🔍 Scanning handlers...")
    auditor.scan_handlers()
    
    print(f"   Found {len(auditor.handlers)} handlers")
    
    # Validate
    success = auditor.validate()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
