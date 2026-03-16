# -*- coding: utf-8 -*-
path = r"C:\Users\Ainul Islam\New folder (8)\earning_backend\frontend\src\router\index.jsx"
content = open(path, encoding='utf-8').read()

OLD_IMPORT = "import Messaging        from '../pages/Messaging';"
NEW_IMPORT = """import Messaging        from '../pages/Messaging';
import VersionControl   from '../pages/VersionControl';"""

OLD_ROUTE = "          { path: 'messaging',            element: <Messaging />        },"
NEW_ROUTE = """          { path: 'messaging',            element: <Messaging />        },
          { path: 'version-control',      element: <VersionControl />   },"""

changed = False
if 'VersionControl' not in content:
    content = content.replace(OLD_IMPORT, NEW_IMPORT)
    content = content.replace(OLD_ROUTE, NEW_ROUTE)
    open(path, 'w', encoding='utf-8').write(content)
    print("Done! Route added.")
    changed = True

if not changed:
    print("Already added!")
