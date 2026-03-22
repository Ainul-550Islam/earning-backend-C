
import os
import re

base = r"C:\Users\Ainul Islam\New folder (8)\earning_backend"

for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in ["__pycache__", "venv", ".git"]]
    for f in files:
        if f != "models.py":
            continue
        path = os.path.join(root, f)
        rel = path.replace(base + "\\", "")
        app = rel.replace("\\models.py","").replace("\\","_").replace("api_","")
        with open(path, "r", encoding="utf-8") as fp:
            lines = fp.readlines()
        if not any("tenants.Tenant" in l for l in lines):
            continue
        current_model = "base"
        new_lines = []
        changed = False
        prev_lines = []
        for line in lines:
            cm = re.match(r"^class\s+(\w+)\s*\(", line)
            if cm:
                current_model = cm.group(1)
            is_tenant_block = any("tenants.Tenant" in p for p in prev_lines[-4:])
            if "related_name=" in line and is_tenant_block:
                unique = f"{app}_{current_model.lower()}_tenant"
                new_line = re.sub(r"related_name='[^']*'", f"related_name='{unique}'", line)
                if new_line != line:
                    changed = True
                new_lines.append(new_line)
            else:
                new_lines.append(line)
            prev_lines.append(line)
        if changed:
            with open(path, "w", encoding="utf-8") as fp:
                fp.writelines(new_lines)
            print(f"Fixed: {rel}")
