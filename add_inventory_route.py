# -*- coding: utf-8 -*-
path = r"C:\Users\Ainul Islam\New folder (8)\earning_backend\frontend\src\router\index.jsx"
content = open(path, encoding='utf-8').read()

OLD_IMPORT = "import PayoutQueue      from '../pages/PayoutQueue';"
NEW_IMPORT = """import PayoutQueue      from '../pages/PayoutQueue';
import Inventory        from '../pages/Inventory';"""

OLD_ROUTE = "          { path: 'payout-queue',         element: <PayoutQueue />      },"
NEW_ROUTE = """          { path: 'payout-queue',         element: <PayoutQueue />      },
          { path: 'inventory',            element: <Inventory />        },"""

if 'Inventory' not in content:
    content = content.replace(OLD_IMPORT, NEW_IMPORT)
    content = content.replace(OLD_ROUTE, NEW_ROUTE)
    open(path, 'w', encoding='utf-8').write(content)
    print("Done! Inventory route added.")
else:
    print("Already added!")
