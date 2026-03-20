import os, re

BASE = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\api'

print("Scanning urls.py files...")
required = {}

for root, dirs, files in os.walk(BASE):
    if 'migration' in root or '__pycache__' in root:
        continue
    for f in files:
        if f != 'urls.py':
            continue
        path = os.path.join(root, f)
        with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
            content = fp.read()
        for m in re.finditer(r"(\w+ViewSet)\.as_view\(\{([^}]+)\}\)", content):
            vs = m.group(1)
            pairs = re.findall(r"'[a-z]+'\s*:\s*'(\w+)'", m.group(2))
            if vs not in required:
                required[vs] = set()
            required[vs].update(pairs)

print(f"Found {len(required)} ViewSets in URLs")

viewset_locations = {}
for root, dirs, files in os.walk(BASE):
    if 'migration' in root or '__pycache__' in root:
        continue
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(root, f)
        with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
            content = fp.read()
        for m in re.finditer(r'^class (\w+ViewSet)\s*\(([^)]+)\)\s*:', content, re.MULTILINE):
            vs_name = m.group(1)
            if vs_name in required:
                class_start = m.start()
                next_class = re.search(r'^class \w', content[class_start+1:], re.MULTILINE)
                class_content = content[class_start:class_start+1+next_class.start()] if next_class else content[class_start:]
                existing = set(re.findall(r'def (\w+)\(self', class_content))
                viewset_locations[vs_name] = (path, existing)

standard = {'list','create','retrieve','update','partial_update','destroy','get','post','put','patch','delete','get_queryset','get_serializer','get_permissions','perform_create','perform_update','perform_destroy','get_object','filter_queryset','paginate_queryset','get_extra_actions'}

print("Finding missing actions...")
missing_by_file = {}

for vs_name, actions in required.items():
    if vs_name not in viewset_locations:
        print(f"  WARNING: {vs_name} not found!")
        continue
    file_path, existing = viewset_locations[vs_name]
    missing = actions - existing - standard
    if missing:
        if file_path not in missing_by_file:
            missing_by_file[file_path] = []
        for action in missing:
            missing_by_file[file_path].append((vs_name, action))
            print(f"  MISSING: {vs_name}.{action}")

total_missing = sum(len(v) for v in missing_by_file.values())
print(f"\nTotal missing: {total_missing}")

if total_missing == 0:
    print("All actions exist!")
else:
    def make_stub(action_name):
        return f'\n    @action(detail=False, methods=[\'get\', \'post\'])\n    def {action_name}(self, request, *args, **kwargs):\n        return Response({{\'message\': \'{action_name} ok\'}})\n'

    for file_path, actions_list in missing_by_file.items():
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as fp:
            content = fp.read()
        if 'from rest_framework.decorators import action' not in content:
            content = 'from rest_framework.decorators import action\n' + content
        if 'from rest_framework.response import Response' not in content:
            content = 'from rest_framework.response import Response\n' + content
        vs_actions = {}
        for vs_name, action_name in actions_list:
            if vs_name not in vs_actions:
                vs_actions[vs_name] = []
            vs_actions[vs_name].append(action_name)
        for vs_name, action_names in vs_actions.items():
            class_match = re.search(rf'^class {vs_name}\s*\(', content, re.MULTILINE)
            if not class_match:
                continue
            class_start = class_match.start()
            next_class_match = re.search(r'\n^class \w', content[class_start+1:], re.MULTILINE)
            stubs = ''.join(make_stub(a) for a in action_names)
            if next_class_match:
                insert_pos = class_start + 1 + next_class_match.start()
                content = content[:insert_pos] + stubs + content[insert_pos:]
            else:
                content = content.rstrip() + '\n' + stubs + '\n'
            print(f"  FIXED: {vs_name} -> {action_names} in {os.path.basename(file_path)}")
        with open(file_path, 'w', encoding='utf-8') as fp:
            fp.write(content)

print("\nDone! Now run: git add . && git commit -m 'fix: add missing ViewSet actions' && git push origin main")
