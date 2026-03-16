# -*- coding: utf-8 -*-
path = r"C:\Users\Ainul Islam\New folder (8)\earning_backend\frontend\src\router\index.jsx"
content = open(path, encoding='utf-8').read()

OLD_IMPORT = "import Inventory        from '../pages/Inventory';"
NEW_IMPORT = """import Inventory        from '../pages/Inventory';
import AutoMod          from '../pages/AutoMod';"""

OLD_ROUTE = "          { path: 'inventory',            element: <Inventory />        },"
NEW_ROUTE = """          { path: 'inventory',            element: <Inventory />        },
          { path: 'auto-mod',             element: <AutoMod />          },"""

if 'AutoMod' not in content:
    content = content.replace(OLD_IMPORT, NEW_IMPORT)
    content = content.replace(OLD_ROUTE, NEW_ROUTE)
    open(path, 'w', encoding='utf-8').write(content)
    print("Done! AutoMod route added.")
else:
    print("Already added!")
