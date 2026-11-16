"""P13 completion: feed Refresh admission beside an agent schedule.

Actual core, parser, SQLite, generated worker text and genuine guest sessions. Cron outcomes and
feed bytes are synthetic public-API replies. This is not native-host, model or Desktop proof.
Agent work is established only through public Upkeep Run calls, never by inserting a claim.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.python import review_customization_support as support
from tests.python.test_agent_refresh_dispatch import PausedRefusingContext, RunOutcome
from tests.python.test_f3_feed_admission_separation import FeedScenario, PATHS, RELEASED
from tests.python.test_f3_feed_later_tick import SHIM_BOOTSTRAP, ScheduledExecution


SCOPE = ('Actual core/SQLite/parser, real generated worker text and real guest sessions. Synthetic public cron '
         'outcomes and feed bytes. Not native-host, model or Desktop UI proof.')
PRE_P13 = Path(os.environ.get(
    'LIVING_SPACES_PRE_P13_ROOT',
    '/Volumes/Expansion/Development/Build/living-spaces-bugfix-evidence/review09-finding-f1/before-p13'))
RELEASED_LABEL, PRE_P13_LABEL, CANDIDATE_LABEL = 'released-0.1.1', 'pre-p13', 'candidate'
LABELS = (RELEASED_LABEL, PRE_P13_LABEL, CANDIDATE_LABEL)
IDLE, ACTIVE, UNKNOWN = 'idle', 'active', 'unknown'
STATES = (IDLE, ACTIVE, UNKNOWN)
HAZARDS = {ACTIVE: (RunOutcome.BACKGROUND, 'background'), UNKNOWN: (RunOutcome.UNSPECIFIED, 'unresolved')}
ROUTE_NAMES = ('desktop-refresh', 'chat-refresh', 'valid-guest-refresh', 'upkeep-run',
               'scheduled-generated-tick', 'scheduled-public-object', 'scheduled-without-cron-identity',
               'worker-retry')
ROUTES = {path.name: path for path in PATHS}
REFUSAL_REASON = 'refresh_outcome_unknown'
STALE_LABEL = ('SYNTHETIC stale-worker input: bytes of the REAL generated feed shim retained before the '
               'schedule switch. An agent schedule does not install a feed worker.')
STRICTER = ('Retained safety exception: active/unknown agent work blocks feed Refresh. Released 0.1.1 '
            'lacked this guard.')
DUPLICATE_AI = ('Retained safety exception: Upkeep Run on an active/unknown AGENT link joins instead of '
                'starting a second model run. Released 0.1.1 lacked duplicate-AI protection.')
FEED_EXCEPTION_KEYS = {'attempts', 'new_fetches', 'records_total', 'source_title', 'records_unchanged',
                       'new_run_statuses'}
RUN_EXCEPTION_KEYS = {'attempts', 'native_run_delta', 'native_runs_target_linked_job', 'executions_delta'}


def describe(exc):
    return {'type': type(exc).__name__, 'message': str(exc)[:4000],
            'detail': exc.to_dict() if hasattr(exc, 'to_dict') else None}


def attempt_class(path, attempt):
    if path.kind == 'run':
        if 'error' in attempt:
            return 'error:' + str(attempt['error'])
        if attempt['joined']:
            return 'joined'
        return 'fresh-dispatch' if attempt['dispatches'] == 1 else 'dispatches:' + str(attempt['dispatches'])
    if path.kind == 'worker':
        runs = attempt['new_runs']
        if attempt['exit_code'] == 0 and runs == ['succeeded']:
            return 'succeeded'
        if attempt['exit_code'] != 0 and runs == [] and 'Living Spaces refresh:' in attempt['stdout']:
            return 'refused'
        return 'other:exit=%s:runs=%s' % (attempt['exit_code'], runs)
    if attempt.get('status') == 'succeeded':
        return 'succeeded'
    if 'status' in attempt:
        return 'status:' + str(attempt['status'])
    return 'refused' if attempt.get('error') == 'blocked' else 'error:' + str(attempt.get('error'))


def project(path, observation, jid):
    before, after = observation['before'], observation['after']
    delta = after['native_runs'][len(before['native_runs']):]
    new_ids = [run_id for run_id in after['run_statuses'] if run_id not in before['run_statuses']]
    return {
        'attempts': [attempt_class(path, attempt) for attempt in observation['attempts']],
        'new_fetches': after['fetches'] - before['fetches'],
        'records_total': after['records']['total'],
        'source_title': after['saved']['source']['title'],
        'user_data_preserved': after['saved']['data'] == observation['user_data'],
        'records_unchanged': after['records'] == before['records'] and after['saved'] == before['saved'],
        'new_run_statuses': sorted(after['run_statuses'][run_id] for run_id in new_ids),
        'native_run_delta': len(delta),
        'native_runs_target_linked_job': sorted(run.get('job_id') == jid for run in delta),
        'agent_job_uses_model': bool(after['job']) and after['job'].get('no_agent') is False,
        'executions_delta': len(after['executions']) - len(before['executions']),
        'effect_calls_unchanged': after['effects'] == before['effects'],
        'schedule_job_unchanged': after['job'] == before['job'],
        'schedule_enabled': after['job']['enabled'] if after['job'] else None,
        'link_kind': after['link']['kind'] if after['link'] else None,
        'link_job_unchanged': (after['link'] or {}).get('cron_job_id') == (before['link'] or {}).get('cron_job_id'),
    }


def control_problems(control):
    problems = []
    if control['class'] != 'succeeded':
        problems.append('healthy feed control was not admitted: %r' % (control['result'],))
    if control['new_fetches'] != 1:
        problems.append('healthy feed control did not fetch exactly once: %r' % control['new_fetches'])
    if control['records_total'] != 1:
        problems.append('healthy feed control did not create exactly one record: %r' % control['records_total'])
    return problems


def state_problems(evidence, state, jid, ownership_required):
    problems = []
    link, job = evidence['link'], evidence['job']
    if not link or link.get('kind') != 'agent' or link.get('cron_job_id') != jid:
        problems.append('upkeep link is not the agent schedule: %r' % (link,))
    if not job or job.get('enabled') is not True or job.get('no_agent') is not False:
        problems.append('linked job is not an enabled model job: %r' % (job,))
    runs = evidence['native_runs']
    if len(runs) != (0 if state == IDLE else 1) or any(run.get('job_id') != jid for run in runs):
        problems.append('native Run evidence does not match %s: %r' % (state, runs))
    executions = evidence['executions']
    if state == ACTIVE:
        if len(executions) != 1 or executions[0]['status'] != 'running' or executions[0]['job_id'] != jid:
            problems.append('active state has no running synthetic execution: %r' % (executions,))
    elif executions:
        problems.append('%s state has an execution: %r' % (state, executions))
    if state != IDLE and (evidence['hazard_result'] or {}).get('joined'):
        problems.append('hazard Run joined existing work instead of dispatching fresh work')
    claims, operations = evidence['claims'], evidence['operations']
    if not ownership_required:
        return problems
    live = [operation for operation in operations if operation.get('phase') != 'retired']
    if state == IDLE:
        if claims or live:
            problems.append('idle state already has ownership evidence: %r' % ({'claims': claims, 'live': live},))
        return problems
    phase = HAZARDS[state][1]
    if len(claims) != 1:
        return problems + ['expected exactly one held claim: %r' % (claims,)]
    claim = claims[0]
    native_job = (json.loads(claim['native']) if claim.get('native') else {}).get('job') or {}
    if (claim.get('cron_job_id') != jid or claim.get('created_one_shot') or claim.get('command') != 'run'
            or claim.get('phase') != phase):
        problems.append('held claim does not describe %s agent Run work: %r' % (state, claim))
    if state == ACTIVE and not (native_job.get('executed') is True and native_job.get('execution_mode') == 'background'):
        problems.append('active claim lacks the accepted background reply: %r' % (native_job,))
    if state == UNKNOWN and (native_job.get('executed') is not None or native_job.get('execution_mode') is not None
                             or native_job.get('execution_success') is not None):
        problems.append('unknown claim carries completion evidence: %r' % (native_job,))
    if not any(op.get('token') == claim.get('token') and op.get('phase') == phase for op in operations):
        problems.append('operation receipt does not match the held claim: %r' % (operations,))
    return problems


class MixedScenario(FeedScenario):
    def __init__(self, package, *, ownership_required=True):
        super().__init__(package)
        self.ownership_required = ownership_required
        self.feed_jid = self.agent_jid = self.stale_worker = None
        self.record_id = self.user_data = self.hazard_result = None

    def __enter__(self):
        super().__enter__()
        try:
            self.feed_jid = self.jid
            shim = self.case.shim
            self.stale_worker = self.fx.home / 'p13-stale-worker' / shim.name
            self.stale_worker.parent.mkdir(parents=True, exist_ok=True)
            self.stale_worker.write_text(shim.read_text())
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def table(self, sql, params=()):
        with self.fx.db.read() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def has_table(self, name):
        return bool(self.table("SELECT 1 AS present FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def claims(self):
        if not self.has_table('refresh_claims'):
            return []
        return self.table('SELECT * FROM refresh_claims WHERE space=? ORDER BY token', (self.sid,))

    def operations(self):
        if not self.has_table('maintenance_operations'):
            return []
        return self.table('SELECT * FROM maintenance_operations WHERE space=? ORDER BY created_at, token', (self.sid,))

    def native_runs(self):
        return [copy.deepcopy(args) for _, args in self.fx.ctx.calls if args.get('action') == 'run']

    def snapshot(self):
        fx = self.fx
        return {'fetches': self.fetch_count(),
                'records': fx.records.query(self.sid, 'items'),
                'saved': fx.records.get(self.sid, 'items', self.record_id),
                'run_statuses': {run['id']: run['status'] for run in fx.runs.list_runs(self.sid)},
                'job': fx.cron.get_job(self.agent_jid) if self.agent_jid else None,
                'link': fx.upkeep.get_upkeep(self.sid).get('link'),
                'executions': copy.deepcopy(fx.cron.executions),
                'effects': [entry for entry in fx.cron.calls if entry[0] != 'list'],
                'native_runs': self.native_runs(),
                'claims': self.claims(),
                'operations': self.operations()}

    def run_stale_worker(self):
        before = {run['id'] for run in self.fx.runs.list_runs(self.sid)}
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LOGNAME', 'SHELL', 'USER')}
        env.update(HOME=str(self.fx.home), HERMES_HOME=str(self.fx.home),
                   LIVING_SPACES_DB=str(self.fx.home / 'spaces.db'), TMPDIR=str(self.fx.home),
                   PYTHONDONTWRITEBYTECODE='1', HERMES_DISABLE_LAZY_INSTALLS='1')
        completed = subprocess.run([sys.executable, '-B', '-c', SHIM_BOOTSTRAP, str(self.package),
                                    str(self.stale_worker)], env=env, capture_output=True, text=True, timeout=25)
        runs = self.fx.runs.list_runs(self.sid)
        return {'exit_code': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr,
                'new_runs': [run['status'] for run in runs if run['id'] not in before], 'input': STALE_LABEL}

    def agent_run(self, state):
        ctx = self.fx.ctx
        if state == IDLE:
            ctx.outcome = RunOutcome.BACKGROUND
        before = len(self.native_runs())
        try:
            result = self.fx.upkeep.upkeep_action(self.sid, 'run', actor='user')
        except self.fx.core.SpacesError as exc:
            error = exc.to_dict()
            return {'error': error['code'], 'reason': error.get('reason'), 'detail': error,
                    'dispatches': len(self.native_runs()) - before}
        return {'joined': bool(result.get('joined')), 'dispatches': len(self.native_runs()) - before,
                'refresh_state': result.get('refresh_state'), 'recovery': result.get('recovery'), 'result': result}

    def healthy_control(self, path):
        control_path = ROUTES['desktop-refresh'] if path.kind == 'run' else path
        before = self.fetch_count()
        if control_path.kind == 'worker':
            raw = self.run_stale_worker()
        elif control_path.kind == 'scheduled':
            self.fx.ctx.execution = ScheduledExecution(self.feed_jid)
            try:
                raw = self.refresh(control_path)
            finally:
                self.fx.ctx.execution = None
        else:
            raw = self.refresh(control_path)
        return {'schedule': 'feed', 'route': control_path.name, 'result': raw,
                'class': attempt_class(control_path, raw), 'new_fetches': self.fetch_count() - before,
                'records_total': self.fx.records.query(self.sid, 'items')['total']}

    def edit_user_fields(self):
        record = self.fx.records.query(self.sid, 'items')['records'][0]
        self.record_id = record['id']
        self.user_data = {'title': 'My title', 'note': 'Keep this note', 'pinned': True}
        self.fx.records.put(self.sid, 'items', record['id'], self.user_data, actor='user', base_rev=record['rev'])
        self.write_feed(True)

    def switch_to_agent(self, state):
        fx = self.fx
        ctx = PausedRefusingContext(fx)
        fx.ctx = ctx
        fx.upkeep.configure_context(ctx)
        self.agent_jid = fx.schedule(self.sid, kind='agent')['link']['cron_job_id']
        self.session = fx.sessions.open_session(self.sid)['session']
        if state != IDLE:
            ctx.outcome = HAZARDS[state][0]
            self.hazard_result = fx.upkeep.upkeep_action(self.sid, 'run', actor='user')
        evidence = self.snapshot()
        evidence.update(state=state, shim_installed=self.case.shim.exists(), stale_input=STALE_LABEL,
                        hazard_result=self.hazard_result)
        return evidence

    def invoke_route(self, path, state):
        attempts = []
        for _ in range(path.repeats):
            if path.kind == 'run':
                attempts.append(self.agent_run(state))
            elif path.kind == 'worker':
                attempts.append(self.run_stale_worker())
            elif path.kind == 'scheduled':
                self.fx.ctx.execution = ScheduledExecution(self.agent_jid)
                try:
                    attempts.append(self.refresh(path))
                finally:
                    self.fx.ctx.execution = None
            else:
                attempts.append(self.refresh(path))
        return attempts

    def drive(self, path, state, out, capture=False):
        out.update(route=path.name, state=state, package=str(self.package))
        phase = 'control'
        try:
            out['control'] = self.healthy_control(path)
            problems = control_problems(out['control'])
            if problems:
                raise AssertionError(problems)
            phase = 'setup'
            self.edit_user_fields()
            out['setup'] = self.switch_to_agent(state)
            out['setup_problems'] = state_problems(out['setup'], state, self.agent_jid, self.ownership_required)
            if out['setup_problems']:
                raise AssertionError(out['setup_problems'])
            phase = 'route'
            out['before'] = self.snapshot()
            out['attempts'] = self.invoke_route(path, state)
            out['after'] = self.snapshot()
            out['user_data'] = self.user_data
            out['projection'] = project(path, out, self.agent_jid)
        except Exception as exc:
            if not capture:
                raise
            out['error'] = dict({'phase': phase}, **describe(exc))
        return out


def collect_matrix(package, ownership_required):
    rows = []
    for state in STATES:
        for path in PATHS:
            row = {'state': state, 'route': path.name}
            try:
                with MixedScenario(package, ownership_required=ownership_required) as case:
                    case.drive(path, state, row, capture=True)
            except Exception as exc:
                row['error'] = dict({'phase': 'fixture'}, **describe(exc))
            rows.append(row)
    return rows


def diff(left, right):
    return sorted(key for key in left if left[key] != right.get(key))


def refused_clean(proj):
    return (bool(proj['attempts']) and all(item == 'refused' for item in proj['attempts'])
            and proj['new_fetches'] == 0 and proj['records_unchanged'] and proj['user_data_preserved']
            and proj['native_run_delta'] == 0 and proj['executions_delta'] == 0
            and proj['effect_calls_unchanged'] and proj['schedule_job_unchanged'] and proj['schedule_enabled'] is True
            and proj['link_job_unchanged'] and proj['new_run_statuses'] == [])


def admitted(proj):
    return (bool(proj['attempts']) and all(item == 'succeeded' for item in proj['attempts'])
            and proj['new_fetches'] == len(proj['attempts']) and proj['native_run_delta'] == 0
            and proj['user_data_preserved'] and proj['schedule_job_unchanged'])


def named_exception(path, state, candidate, released, keys):
    if state == IDLE:
        return None
    if path.kind == 'run':
        if (released['attempts'] == ['fresh-dispatch'] and candidate['attempts'] == ['joined']
                and set(keys) <= RUN_EXCEPTION_KEYS):
            return DUPLICATE_AI
        return None
    if admitted(released) and refused_clean(candidate) and set(keys) <= FEED_EXCEPTION_KEYS:
        return STRICTER
    return None


def contract_problems(path, state, proj):
    unchanged = {'effect_calls_unchanged': True, 'schedule_enabled': True, 'link_kind': 'agent',
                 'link_job_unchanged': True, 'user_data_preserved': True}
    if path.kind == 'run':
        if state == IDLE:
            want = {'attempts': ['fresh-dispatch'], 'native_run_delta': 1, 'native_runs_target_linked_job': [True],
                    'agent_job_uses_model': True}
        else:
            want = {'attempts': ['joined'], 'native_run_delta': 0, 'native_runs_target_linked_job': [],
                    'executions_delta': 0}
        want.update(unchanged, new_fetches=0, records_unchanged=True, new_run_statuses=[])
    elif state == IDLE:
        want = dict(unchanged, attempts=['succeeded'] * path.repeats, new_fetches=path.repeats, records_total=2,
                    source_title='Revised', new_run_statuses=['succeeded'] * path.repeats, native_run_delta=0,
                    executions_delta=0, schedule_job_unchanged=True)
    else:
        want = dict(unchanged, attempts=['refused'] * path.repeats, new_fetches=0, records_unchanged=True,
                    new_run_statuses=[], native_run_delta=0, executions_delta=0, schedule_job_unchanged=True)
    return {key: {'expected': value, 'observed': proj.get(key)} for key, value in want.items()
            if proj.get(key) != value}


def judge(observed):
    expected_keys = [(state, path.name) for state in STATES for path in PATHS]
    failures, differences, exceptions = {}, [], []

    def fail(group, item):
        failures.setdefault(group, []).append(item)

    index = {}
    for label in LABELS:
        rows = observed[label]
        keys = [(row['state'], row['route']) for row in rows]
        if keys != expected_keys:
            fail('incomplete_matrix', {'pin': label, 'keys': keys})
        index[label] = {(row['state'], row['route']): row for row in rows}
        for row in rows:
            if 'error' in row:
                fail('scenario_errors', {'pin': label, 'state': row['state'], 'route': row['route'],
                                         'error': row['error']})
    for key in expected_keys:
        state, route = key
        path = ROUTES[route]
        rows = {label: index[label].get(key) for label in LABELS}
        if any(row is None or 'error' in row for row in rows.values()):
            continue
        proj = {label: row['projection'] for label, row in rows.items()}
        released, pre, candidate = proj[RELEASED_LABEL], proj[PRE_P13_LABEL], proj[CANDIDATE_LABEL]
        problems = contract_problems(path, state, candidate)
        if problems:
            fail('candidate_contract', {'state': state, 'route': route, 'problems': problems})
        if state == IDLE and path.kind != 'run' and not (
                admitted(released) and released['records_total'] == 2 and released['user_data_preserved']):
            fail('released_idle_premise', {'route': route, 'released': released})
        pre_keys = diff(candidate, pre)
        if pre_keys:
            fail('candidate_vs_pre_p13', {'state': state, 'route': route, 'keys': pre_keys,
                                          'pre_p13': pre, 'candidate': candidate})
        keys_vs_released = diff(candidate, released)
        if keys_vs_released:
            if not diff(pre, released):
                attribution = 'pre-P13 matches released, so this difference arrived after pre-P13'
            elif not diff(pre, candidate):
                attribution = 'pre-P13 matches candidate, so this difference predates P13'
            else:
                attribution = 'pre-P13 differs from both released and candidate'
            entry = {'state': state, 'route': route, 'keys': keys_vs_released, 'attribution': attribution,
                     'released': released, 'pre_p13': pre, 'candidate': candidate}
            named = named_exception(path, state, candidate, released, keys_vs_released)
            if named:
                exceptions.append(dict(entry, exception=named))
            else:
                differences.append(entry)
                fail('unexplained_difference_from_released', entry)
        for label in (PRE_P13_LABEL, CANDIDATE_LABEL):
            before, after = rows[label]['before'], rows[label]['after']
            if before['claims'] and (after['claims'] != before['claims']
                                     or after['operations'] != before['operations']):
                fail('held_ownership_changed', {'pin': label, 'state': state, 'route': route,
                                                'before': before['claims'], 'after': after['claims']})
    return {'failures': failures, 'unexplained_differences': differences, 'retained_safety_exceptions': exceptions}


class FeedMixedAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.observations = {}
        self.addCleanup(self.report)

    def report(self):
        print(json.dumps({'case': self.id(), 'observations': self.observations, 'scope': SCOPE},
                         default=str, sort_keys=True), flush=True)

    def check_idle_core_route(self, name, trigger, actor):
        path = ROUTES[name]
        self.assertEqual((path.kind, path.trigger, path.actor), ('core', trigger, actor))
        out = self.observations.setdefault(name, {})
        with MixedScenario(support.PACKAGE) as case:
            case.drive(path, IDLE, out)
            if actor == 'guest':
                self.assertIsNotNone(case.session)
            before, after, proj = out['before'], out['after'], out['projection']
            self.assertEqual(out['control']['class'], 'succeeded')
            self.assertEqual(out['attempts'], [{'status': 'succeeded'}],
                             'Idle agent schedule must not block ordinary feed Refresh')
            self.assertEqual(proj['new_fetches'], 1, 'Refresh must fetch fresh input')
            self.assertEqual(after['records']['total'], 2, 'Revised source item must merge and the new one add')
            self.assertEqual(sorted(row['source'].get('title') for row in after['records']['records']),
                             ['New', 'Revised'])
            self.assertEqual(after['saved']['source']['title'], 'Revised')
            self.assertEqual(after['saved']['data'], case.user_data)
            self.assertEqual(proj['new_run_statuses'], ['succeeded'])
            self.assertEqual(after['job'], before['job'])
            self.assertIs(after['job']['enabled'], True)
            self.assertEqual(after['link'], before['link'])
            self.assertEqual(after['native_runs'], [])
            self.assertEqual(after['executions'], [])
            self.assertEqual(after['effects'], before['effects'])
            self.assertEqual(after['claims'], [])
            self.assertEqual([op for op in after['operations'] if op.get('phase') != 'retired'], [])

    def test_idle_agent_schedule_admits_desktop_core_manual_user_refresh(self):
        self.check_idle_core_route('desktop-refresh', 'manual', 'user')

    def test_idle_agent_schedule_admits_chat_core_chat_refresh(self):
        self.check_idle_core_route('chat-refresh', 'chat', 'chat')

    def test_idle_agent_schedule_admits_manual_guest_refresh_with_real_session(self):
        self.check_idle_core_route('valid-guest-refresh', 'manual', 'guest')

    def test_all_eight_routes_by_agent_state_match_released_except_named_safety_exceptions(self):
        self.assertEqual(tuple(path.name for path in PATHS), ROUTE_NAMES)
        self.assertEqual(len(PATHS), 8)
        pins = ((RELEASED_LABEL, RELEASED / 'src/living-spaces'), (PRE_P13_LABEL, PRE_P13 / 'src/living-spaces'),
                (CANDIDATE_LABEL, Path(support.PACKAGE)))
        for label, package in pins:
            self.assertTrue((package / '_core.py').is_file(), (label, str(package)))
        self.observations['pins'] = {label: str(package) for label, package in pins}
        self.observations['stale_worker_input'] = STALE_LABEL
        observed = self.observations['matrix'] = {}
        for label, package in pins:
            observed[label] = collect_matrix(package, ownership_required=label != RELEASED_LABEL)
        verdict = self.observations['verdict'] = judge(observed)
        self.assertEqual(verdict['failures'], {},
                         'Every route/state must match released admission or a named retained safety exception, '
                         'agree with pre-P13 and preserve held agent ownership')

    def check_hazard_blocks(self, state):
        for name in ('desktop-refresh', 'chat-refresh', 'valid-guest-refresh'):
            path = ROUTES[name]
            with self.subTest(route=name, state=state):
                out = self.observations.setdefault(state, {}).setdefault(name, {})
                with MixedScenario(support.PACKAGE) as case:
                    case.drive(path, state, out)
                    before, after, proj = out['before'], out['after'], out['projection']
                    self.assertEqual(out['control']['class'], 'succeeded')
                    self.assertEqual(out['attempts'], [{'error': 'blocked', 'reason': REFUSAL_REASON}])
                    self.assertEqual(proj['new_fetches'], 0)
                    self.assertEqual(after['records'], before['records'])
                    self.assertEqual(after['saved'], before['saved'])
                    self.assertEqual(after['saved']['data'], case.user_data)
                    self.assertEqual(after['job'], before['job'])
                    self.assertIs(after['job']['enabled'], True)
                    self.assertEqual(after['link'], before['link'])
                    self.assertEqual(len(after['native_runs']), 1)
                    self.assertEqual(after['native_runs'], before['native_runs'])
                    self.assertEqual(after['executions'], before['executions'])
                    self.assertEqual(after['effects'], before['effects'])
                    self.assertEqual(len(after['claims']), 1)
                    self.assertEqual(after['claims'], before['claims'])
                    self.assertEqual(after['operations'], before['operations'])
                    self.assertEqual([op.get('phase') for op in after['operations']
                                      if op.get('token') == after['claims'][0]['token']], [HAZARDS[state][1]])
                    self.assertEqual(after['claims'][0]['phase'], HAZARDS[state][1])

    def test_active_agent_work_still_blocks_all_three_refresh_routes(self):
        self.check_hazard_blocks(ACTIVE)

    def test_unknown_agent_work_still_blocks_all_three_refresh_routes(self):
        self.check_hazard_blocks(UNKNOWN)


if __name__ == '__main__':
    unittest.main(verbosity=2)
