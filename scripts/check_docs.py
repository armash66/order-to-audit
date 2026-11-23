"""Check local Markdown links in the README and current documentation guides."""
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "README.md", *[ROOT / "docs" / name for name in (
    "README.md", "operations.md", "development.md", "localization.md",
    "security.md", "reference.md", "react-demo.md", "design.md", "compliance.md", "submission.md",
)]]
missing = []
for file in FILES:
    for target in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
        if target.startswith(("http:", "https:", "mailto:", "#")):
            continue
        target = unquote(target.split("#", 1)[0].strip("<>"))
        if not (file.parent / target).exists():
            missing.append(f"{file.relative_to(ROOT)}: {target}")
if missing:
    raise SystemExit("Broken links:\n" + "\n".join(missing))
print(f"Documentation links passed: {len(FILES)} files")
