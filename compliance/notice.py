import json
import sys
from pathlib import Path

compliance_dir = Path(__file__).parent
sbom = json.load(sys.stdin)

lines = []
for comp in sbom.get("components", []):
    name = comp.get("name")
    version = comp.get("version")
    licenses = [
        lic.get("expression")
        or lic.get("license", {}).get("id")
        or lic.get("license", {}).get("name")
        for lic in comp.get("licenses", [])
    ]
    lic_str = ", ".join(filter(None, licenses)) or "Unknown License"
    lines.append(f"{name} ({version}) - {lic_str}")

if lines:
    lines.insert(0, "THIRD-PARTY SOFTWARE NOTICES")
    lines.insert(1, "============================")

print("\n".join(lines)) # noqa: T201
