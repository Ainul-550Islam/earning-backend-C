import os, re

base = r'C:\Users\Ainul Islam\New folder (8)\earning_backend'

for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in ['__pycache__', 'venv', '.git']]
    for fname in files:
        if fname != 'models.py':
            continue
        path = os.path.join(root, fname)
        rel = path.replace(base + '\\', '')
        app = rel.replace('\\models.py','').replace('\\','_').replace('api_','')
        with open(path, 'r', encoding='utf-8') as fp:
            lines = fp.readlines()
        if not any('tenants.Tenant' in l for l in lines):
            continue
        current_model = 'base'
        new_lines = []
        changed = False
        in_tenant_fk = False
        for line in lines:
            cm = re.match(r'^class\s+(\w+)\s*\(', line)
            if cm:
                current_model = cm.group(1)
                in_tenant_fk = False
            if 'tenants.Tenant' in line:
                in_tenant_fk = True
            if in_tenant_fk and 'related_name=' in line:
                unique = app + '_' + current_model.lower() + '_tenant'
                new_line = re.sub(r"related_name='[^']*'", "related_name='" + unique + "'", line)
                if new_line != line:
                    changed = True
                    in_tenant_fk = False
                new_lines.append(new_line)
                continue
            if in_tenant_fk and ')' in line and 'models.ForeignKey' not in line:
                in_tenant_fk = False
            new_lines.append(line)
        if changed:
            with open(path, 'w', encoding='utf-8') as fp:
                fp.writelines(new_lines)
            print('Fixed: ' + rel)
print('All done!')
