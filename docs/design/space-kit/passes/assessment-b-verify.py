"""Aggregate Assessment B artifacts and stop only its Impeccable server."""
import collections
import hashlib
import json
import pathlib
import subprocess
import urllib.error
import urllib.request

out = pathlib.Path(__file__).resolve().parent
root = out.parents[3]
raw = json.loads((out / 'assessment-b-detector.raw.json').read_text())
execution = json.loads((out / 'assessment-b-execution.json').read_text())
summary = {
    'detector_exit_code': execution['exit_code'],
    'findings_total': len(raw),
    'rules': dict(collections.Counter(x['antipattern'] for x in raw)),
    'files': dict(collections.Counter(x['file'] for x in raw)),
    'severity': dict(collections.Counter(x['severity'] for x in raw)),
    'snippets': dict(collections.Counter(x['snippet'] for x in raw)),
    'source_inventory': list(execution['source_sha256']),
    'source_changed_since_scan': [name for name, sha in execution['source_sha256'].items() if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha],
}
cmd = ['/Users/ifedayoakinduro/.hermes/skills/creative/impeccable/scripts/impeccable', 'live-server', 'stop', '--keep-inject']
p = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
summary['live_server_stop'] = {'command': cmd, 'cwd': str(out), 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
try:
    with urllib.request.urlopen('http://localhost:8401/health', timeout=3) as response:
        summary['live_server_health_after_stop'] = {'responded': True, 'status': response.status}
except Exception as e:
    summary['live_server_health_after_stop'] = {'responded': False, 'error': str(e)}
summary['artifacts'] = sorted(p.name for p in out.glob('assessment-b-*') if p.is_file())
(out / 'assessment-b-verification.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
