"""Assessment B: execute the bundled detector exactly once; retain raw output."""
import hashlib
import json
import pathlib
import subprocess

root = pathlib.Path(__file__).resolve().parents[4]
out = root / 'docs/design/space-kit/passes'
cmd = ['/Users/ifedayoakinduro/.hermes/skills/creative/impeccable/scripts/impeccable', 'detect', '--json', 'src/living-spaces/skills/build-space/references', 'src/living-spaces/runtime/kit/spaces-kit.css']
files = [p for p in (root / 'src/living-spaces/skills/build-space/references').rglob('*') if p.is_file()]
files.append(root / 'src/living-spaces/runtime/kit/spaces-kit.css')
meta = {'command': cmd, 'cwd': str(root), 'source_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, 'git_status_before': subprocess.check_output(['git', 'status', '--short'], cwd=root, text=True)}
p = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
(out / 'assessment-b-detector.raw.json').write_text(p.stdout)
(out / 'assessment-b-detector.stderr.txt').write_text(p.stderr)
meta['exit_code'] = p.returncode
(out / 'assessment-b-execution.json').write_text(json.dumps(meta, indent=2))
print('Detector executed; outputs saved.')
