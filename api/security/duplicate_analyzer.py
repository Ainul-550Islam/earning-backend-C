#!/usr/bin/env python3
"""
Duplicate Analyzer for Security Module
Finds duplicate classes and functions across all files
"""

import os
import ast
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple
from pathlib import Path

class DuplicateAnalyzer:
    def __init__(self, security_module_path: str):
        self.security_module_path = Path(security_module_path)
        self.class_definitions = defaultdict(list)
        self.function_definitions = defaultdict(list)
        self.import_statements = defaultdict(list)
        self.duplicate_classes = {}
        self.duplicate_functions = {}
        self.duplicate_imports = {}
        self.all_files = []
        
    def analyze_all_files(self):
        """Analyze all Python files in the security module"""
        print("🔍 Scanning security module for duplicates...")
        
        # Find all Python files
        for root, dirs, files in os.walk(self.security_module_path):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    self.all_files.append(file_path)
                    self.analyze_file(file_path)
        
        print(f"📁 Analyzed {len(self.all_files)} files")
        
        # Find duplicates
        self.find_duplicates()
        
        # Generate report
        self.generate_report()
    
    def analyze_file(self, file_path: str):
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content)
            
            # Extract definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self.class_definitions[node.name].append({
                        'file': file_path,
                        'line': node.lineno,
                        'end_line': getattr(node, 'end_lineno', node.lineno),
                        'bases': [self._get_base_name(base) for base in node.bases]
                    })
                
                elif isinstance(node, ast.FunctionDef):
                    # Skip dunder methods and private methods
                    if not node.name.startswith('_') or node.name.startswith('__'):
                        self.function_definitions[node.name].append({
                            'file': file_path,
                            'line': node.lineno,
                            'end_line': getattr(node, 'end_lineno', node.lineno),
                            'args': [arg.arg for arg in node.args.args]
                        })
                
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    self._extract_imports(node, file_path)
        
        except Exception as e:
            print(f"⚠️  Error analyzing {file_path}: {e}")
    
    def _get_base_name(self, base):
        """Extract base class name"""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return base.attr
        return str(base)
    
    def _extract_imports(self, node, file_path: str):
        """Extract import statements"""
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                self.import_statements[name].append({
                    'file': file_path,
                    'line': node.lineno,
                    'module': alias.name,
                    'alias': alias.asname
                })
        
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                full_name = f"{module}.{name}" if module else name
                self.import_statements[full_name].append({
                    'file': file_path,
                    'line': node.lineno,
                    'module': module,
                    'name': name,
                    'alias': alias.asname
                })
    
    def find_duplicates(self):
        """Find duplicate definitions"""
        print("🔍 Finding duplicates...")
        
        # Find duplicate classes
        for class_name, definitions in self.class_definitions.items():
            if len(definitions) > 1:
                self.duplicate_classes[class_name] = definitions
        
        # Find duplicate functions
        for func_name, definitions in self.function_definitions.items():
            if len(definitions) > 1:
                self.duplicate_functions[func_name] = definitions
        
        # Find duplicate imports
        for import_name, definitions in self.import_statements.items():
            if len(definitions) > 1:
                self.duplicate_imports[import_name] = definitions
        
        print(f"📊 Found {len(self.duplicate_classes)} duplicate classes")
        print(f"📊 Found {len(self.duplicate_functions)} duplicate functions")
        print(f"📊 Found {len(self.duplicate_imports)} duplicate imports")
    
    def generate_report(self):
        """Generate comprehensive duplicate report"""
        report_file = self.security_module_path / "DUPLICATE_ANALYSIS_REPORT.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Security Module Duplicate Analysis Report\n\n")
            f.write(f"**Generated on:** {self._get_current_time()}\n")
            f.write(f"**Total Files Analyzed:** {len(self.all_files)}\n\n")
            
            # Summary
            f.write("## 📊 Summary\n\n")
            f.write(f"- **Duplicate Classes:** {len(self.duplicate_classes)}\n")
            f.write(f"- **Duplicate Functions:** {len(self.duplicate_functions)}\n")
            f.write(f"- **Duplicate Imports:** {len(self.duplicate_imports)}\n\n")
            
            # Duplicate Classes (A-Z)
            if self.duplicate_classes:
                f.write("## 🏷️ Duplicate Classes (A-Z)\n\n")
                for class_name in sorted(self.duplicate_classes.keys()):
                    f.write(f"### {class_name}\n\n")
                    for i, definition in enumerate(self.duplicate_classes[class_name], 1):
                        rel_path = os.path.relpath(definition['file'], self.security_module_path)
                        f.write(f"{i}. **{rel_path}** (Line {definition['line']})\n")
                        if definition['bases']:
                            f.write(f"   - Inherits from: {', '.join(definition['bases'])}\n")
                    f.write("\n")
            
            # Duplicate Functions (A-Z)
            if self.duplicate_functions:
                f.write("## 🔧 Duplicate Functions (A-Z)\n\n")
                for func_name in sorted(self.duplicate_functions.keys()):
                    f.write(f"### {func_name}\n\n")
                    for i, definition in enumerate(self.duplicate_functions[func_name], 1):
                        rel_path = os.path.relpath(definition['file'], self.security_module_path)
                        f.write(f"{i}. **{rel_path}** (Line {definition['line']})\n")
                        if definition['args']:
                            f.write(f"   - Arguments: ({', '.join(definition['args'])})\n")
                    f.write("\n")
            
            # Duplicate Imports (A-Z)
            if self.duplicate_imports:
                f.write("## 📦 Duplicate Imports (A-Z)\n\n")
                for import_name in sorted(self.duplicate_imports.keys()):
                    f.write(f"### {import_name}\n\n")
                    for i, definition in enumerate(self.duplicate_imports[import_name], 1):
                        rel_path = os.path.relpath(definition['file'], self.security_module_path)
                        f.write(f"{i}. **{rel_path}** (Line {definition['line']})\n")
                        if definition['module']:
                            f.write(f"   - From module: {definition['module']}\n")
                    f.write("\n")
            
            # Detailed Analysis
            f.write("## 🔍 Detailed Analysis\n\n")
            
            # Most problematic duplicates
            f.write("### 🚨 Most Problematic Duplicates\n\n")
            
            # Classes with most duplicates
            if self.duplicate_classes:
                most_dup_classes = max(self.duplicate_classes.values(), key=len)
                class_name = [name for name, defs in self.duplicate_classes.items() if defs == most_dup_classes][0]
                f.write(f"- **Class:** {class_name} ({len(most_dup_classes)} occurrences)\n")
            
            # Functions with most duplicates
            if self.duplicate_functions:
                most_dup_funcs = max(self.duplicate_functions.values(), key=len)
                func_name = [name for name, defs in self.duplicate_functions.items() if defs == most_dup_funcs][0]
                f.write(f"- **Function:** {func_name} ({len(most_dup_funcs)} occurrences)\n")
            
            f.write("\n")
            
            # Recommendations
            f.write("## 💡 Recommendations\n\n")
            f.write("### 🏷️ For Duplicate Classes:\n")
            f.write("1. **Merge similar classes** - If classes have similar functionality, consider merging\n")
            f.write("2. **Use inheritance** - Create a base class and inherit from it\n")
            f.write("3. **Rename classes** - Use more specific names to avoid conflicts\n")
            f.write("4. **Move to modules** - Separate classes into different modules\n\n")
            
            f.write("### 🔧 For Duplicate Functions:\n")
            f.write("1. **Create utility modules** - Move common functions to utility modules\n")
            f.write("2. **Use mixins** - Create mixin classes for shared functionality\n")
            f.write("3. **Rename functions** - Use more descriptive names\n")
            f.write("4. **Consolidate logic** - Merge functions with similar logic\n\n")
            
            f.write("### 📦 For Duplicate Imports:\n")
            f.write("1. **Create import modules** - Consolidate imports in __init__.py files\n")
            f.write("2. **Remove unused imports** - Clean up unnecessary imports\n")
            f.write("3. **Use absolute imports** - Standardize import style\n\n")
        
        print(f"📄 Report generated: {report_file}")
    
    def _get_current_time(self):
        """Get current time string"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_duplicate_summary(self) -> Dict:
        """Get summary of duplicates"""
        return {
            'duplicate_classes': dict(sorted(self.duplicate_classes.items())),
            'duplicate_functions': dict(sorted(self.duplicate_functions.items())),
            'duplicate_imports': dict(sorted(self.duplicate_imports.items())),
            'total_files': len(self.all_files),
            'total_duplicates': len(self.duplicate_classes) + len(self.duplicate_functions) + len(self.duplicate_imports)
        }
    
    def print_console_summary(self):
        """Print summary to console"""
        print("\n" + "="*80)
        print("🔍 DUPLICATE ANALYSIS SUMMARY")
        print("="*80)
        
        print(f"\n📁 Total Files Analyzed: {len(self.all_files)}")
        print(f"🏷️  Duplicate Classes: {len(self.duplicate_classes)}")
        print(f"🔧 Duplicate Functions: {len(self.duplicate_functions)}")
        print(f"📦 Duplicate Imports: {len(self.duplicate_imports)}")
        print(f"📊 Total Duplicates: {len(self.duplicate_classes) + len(self.duplicate_functions) + len(self.duplicate_imports)}")
        
        if self.duplicate_classes:
            print(f"\n🏷️  Classes with duplicates (A-Z):")
            for class_name in sorted(self.duplicate_classes.keys())[:10]:  # Show first 10
                print(f"   - {class_name} ({len(self.duplicate_classes[class_name])} occurrences)")
            if len(self.duplicate_classes) > 10:
                print(f"   ... and {len(self.duplicate_classes) - 10} more")
        
        if self.duplicate_functions:
            print(f"\n🔧 Functions with duplicates (A-Z):")
            for func_name in sorted(self.duplicate_functions.keys())[:10]:  # Show first 10
                print(f"   - {func_name} ({len(self.duplicate_functions[func_name])} occurrences)")
            if len(self.duplicate_functions) > 10:
                print(f"   ... and {len(self.duplicate_functions) - 10} more")
        
        print("\n" + "="*80)


def main():
    """Main function to run duplicate analysis"""
    security_path = "api/security"
    
    if not os.path.exists(security_path):
        print(f"❌ Security module path not found: {security_path}")
        return
    
    analyzer = DuplicateAnalyzer(security_path)
    analyzer.analyze_all_files()
    analyzer.print_console_summary()
    
    # Get detailed summary
    summary = analyzer.get_duplicate_summary()
    
    return summary


if __name__ == "__main__":
    main()