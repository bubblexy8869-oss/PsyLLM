import os
import re

NODES_DIR = "src/graph/nodes"

pattern = re.compile(r"from\s+\.common\s+import\s+(.*)")

results = {}

for root, _, files in os.walk(NODES_DIR):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            matches = pattern.findall(content)
            if matches:
                results[path] = matches

print("=== Imports from .common ===")
for path, imports in results.items():
    print(f"{path}: {imports}")