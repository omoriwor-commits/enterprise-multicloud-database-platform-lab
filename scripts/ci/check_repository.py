"""Validate tracked text structure without contacting a database or cloud."""
from pathlib import Path
import re
import subprocess
import sys
import yaml

errors = []
for name in subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], text=True).splitlines():
    path = Path(name)
    if not path.is_file() or '.git' in path.parts or '__pycache__' in path.parts:
        continue
    if path.suffix in ('.yaml', '.yml'):
        try:
            list(yaml.safe_load_all(path.read_text()))
        except yaml.YAMLError as exc:
            errors.append(str(path) + ': invalid YAML: ' + str(exc))
    if path.suffix != '.md':
        continue
    text = re.sub(r'```.*?```|~~~.*?~~~', '', path.read_text(), flags=re.S)
    for match in re.finditer(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', text):
        url = match.group(1).split()[0].strip('<>')
        if not url or re.match(r'^[a-zA-Z]+:', url) or url.startswith('#'):
            continue
        relative = url.split('#')[0]
        target = Path(relative.lstrip('/')) if relative.startswith('/') else path.parent / relative
        if not target.exists():
            errors.append(str(path) + ': missing local link ' + url)
if errors:
    print('\n'.join(errors), file=sys.stderr)
    sys.exit(1)
print('YAML parsing and local Markdown file links passed; external URLs and anchors are not checked.')
