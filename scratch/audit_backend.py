import os
import sys
import pkgutil
import importlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src

print("=== AUDIT BACKEND MODULES & DEPENDENCIES ===")
modules_checked = []
errors = []

for _, module_name, _ in pkgutil.walk_packages(src.__path__, src.__name__ + '.'):
    try:
        importlib.import_module(module_name)
        modules_checked.append(module_name)
    except Exception as e:
        errors.append((module_name, str(e)))

print(f"Total modules loaded: {len(modules_checked)}")
if errors:
    print(f"FAILED MODULES ({len(errors)}):")
    for mod, err in errors:
        print(f"  [X] {mod}: {err}")
else:
    print("[OK] All modules imported successfully with 0 errors!")
