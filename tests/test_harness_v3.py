import json
import os
import sys
import unittest

import test_harness as fixtures
from test_harness import base_tasks, base_config


class HarnessV3Test(unittest.TestCase):
    setUp = fixtures.HarnessCliTest.setUp
    tearDown = fixtures.HarnessCliTest.tearDown
    write_json = fixtures.HarnessCliTest.write_json
    read_tasks = fixtures.HarnessCliTest.read_tasks
    run_cli = fixtures.HarnessCliTest.run_cli
    initialize_git_repository = fixtures.HarnessCliTest.initialize_git_repository

    def ready(self):
        self.assertEqual(0, self.run_cli('next').returncode)
        result = self.run_cli('verify')
        self.assertEqual(0, result.returncode, result.stderr)

    def test_content_change_invalidates_pass_and_report_is_read_only(self):
        source = self.workspace / 'src.txt'
        source.write_text('first')
        self.ready()
        source.write_text('other')
        before = (self.harness_dir / 'tasks.json').read_bytes()
        handoff = (self.harness_dir / 'HANDOFF.md').read_bytes()
        report = self.run_cli('report', 'task-1', '--format', 'json')
        self.assertEqual(1, report.returncode, report.stderr)
        self.assertFalse(json.loads(report.stdout)['ready'])
        self.assertIn('source', report.stdout)
        self.assertEqual(before, (self.harness_dir / 'tasks.json').read_bytes())
        self.assertEqual(handoff, (self.harness_dir / 'HANDOFF.md').read_bytes())
        self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)

    def test_touch_does_not_invalidate_content_snapshot(self):
        source = self.workspace / 'src.txt'
        source.write_text('first')
        self.ready()
        os.utime(source, (100, 100))
        self.assertEqual(0, self.run_cli('complete', 'task-1').returncode)

    def test_removed_check_and_changed_command_require_explicit_revision(self):
        tasks = base_tasks()
        extra = dict(tasks['tasks'][0]['acceptance'][0], id='extra')
        tasks['tasks'][0]['acceptance'].append(extra)
        self.write_json('tasks.json', tasks)
        self.ready()
        tasks = self.read_tasks()
        tasks['tasks'][0]['acceptance'].pop()
        self.write_json('tasks.json', tasks)
        self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)
        self.assertEqual(1, self.run_cli('verify').returncode)

    def test_mid_run_source_drift_cannot_pass(self):
        tasks = base_tasks(command=[sys.executable, '-c', "from pathlib import Path; Path('src.txt').write_text('changed')"])
        self.write_json('tasks.json', tasks)
        self.run_cli('next')
        result = self.run_cli('verify')
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertNotEqual('passed', self.read_tasks()['tasks'][0]['acceptance'][0]['status'])
        self.assertTrue(list((self.harness_dir / 'attempts').rglob('*.json')))

    def test_revision_detaches_evidence_and_preserves_baselines(self):
        self.ready()
        old = self.read_tasks()['tasks'][0]
        definition = {'id': 'task-1', 'title': 'Revised', 'acceptance': [{'id': 'new', 'type': 'manual', 'instruction': 'Inspect', 'steps': ['Inspect']}]}
        path = self.workspace / 'definition.json'
        path.write_text(json.dumps(definition))
        result = self.run_cli('task', 'revise', 'task-1', '--from', str(path), '--note', 'new requirement')
        self.assertEqual(0, result.returncode, result.stderr)
        task = self.read_tasks()['tasks'][0]
        self.assertEqual(old['git_baseline'], task['git_baseline'])
        self.assertEqual(old['policy_baseline'], task['policy_baseline'])
        self.assertEqual('unverified', task['acceptance'][0]['status'])
        self.assertTrue(task['revision_history'])

    def test_add_rejects_runtime_fields(self):
        path = self.workspace / 'definition.json'
        path.write_text(json.dumps(base_tasks()['tasks'][0]))
        self.assertEqual(2, self.run_cli('task', 'add', '--from', str(path)).returncode)

    def test_git_ignored_files_do_not_invalidate_but_tracked_config_does(self):
        (self.workspace / '.gitignore').write_text('cache/\n')
        self.initialize_git_repository()
        self.ready()
        (self.workspace / 'cache').mkdir()
        (self.workspace / 'cache' / 'new').write_text('ignored')
        self.assertEqual(0, self.run_cli('report', 'task-1', '--format', 'json').returncode)
        config = base_config()
        config['project_name'] = 'changed'
        self.write_json('config.json', config)
        self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)

    def test_v2_migration_preserves_baselines_and_blockers(self):
        tasks = base_tasks(command=[sys.executable, '-c', 'raise SystemExit(1)'])
        self.write_json('tasks.json', tasks)
        self.run_cli('next')
        for _ in range(3):
            self.run_cli('verify')
        old = self.read_tasks()
        old['schema_version'] = 2
        old['tasks'][0]['git_baseline']['version'] = 2
        old['tasks'][0]['policy_baseline']['schema_version'] = 2
        old['tasks'][0].pop('contract_baseline', None)
        config = base_config()
        config['schema_version'] = config['policy']['schema_version'] = 2
        self.write_json('config.json', config)
        self.write_json('tasks.json', old)
        result = self.run_cli('migrate', '--note', 'retain baseline')
        self.assertEqual(0, result.returncode, result.stderr)
        task = self.read_tasks()['tasks'][0]
        self.assertEqual(old['tasks'][0]['git_baseline'], task['git_baseline'])
        self.assertEqual(old['tasks'][0]['policy_baseline'], task['policy_baseline'])
        self.assertEqual('blocked', task['status'])
        self.assertEqual(3, task['acceptance'][0]['consecutive_failures'])

    def test_failed_rerun_revokes_all_previous_command_passes(self):
        tasks = base_tasks(command=[sys.executable, '-c', "from pathlib import Path; raise SystemExit(7 if Path('.harness/artifacts/fail').exists() else 0)"])
        tasks['tasks'][0]['acceptance'].append(dict(tasks['tasks'][0]['acceptance'][0], id='later'))
        self.write_json('tasks.json', tasks)
        self.ready()
        artifacts = self.harness_dir / 'artifacts'
        artifacts.mkdir()
        (artifacts / 'fail').touch()
        self.assertEqual(1, self.run_cli('verify').returncode)
        checks = self.read_tasks()['tasks'][0]['acceptance']
        self.assertEqual(['failed', 'unverified'], [check['status'] for check in checks])
        self.assertIsNone(checks[1]['latest_evidence'])

    def test_browser_and_command_must_share_current_snapshot(self):
        tasks = base_tasks()
        tasks['tasks'][0]['acceptance'].append({'id': 'browser', 'type': 'browser', 'instruction': 'Observe', 'steps': ['Observe'], 'status': 'not_run', 'consecutive_failures': 0})
        self.write_json('tasks.json', tasks)
        artifact_dir = self.harness_dir / 'artifacts'
        artifact_dir.mkdir()
        image = artifact_dir / 'screenshot.png'
        image.write_bytes(b'fixture')
        self.ready()
        (self.workspace / 'source.txt').write_text('updated')
        result = self.run_cli('record', 'task-1', 'browser', '--result', 'passed', '--summary', 'Observed', '--tool', 'Playwright', '--artifact', str(image))
        self.assertEqual(0, result.returncode, result.stderr)
        task = self.read_tasks()['tasks'][0]
        evidence = json.loads((self.workspace / task['acceptance'][1]['latest_evidence']).read_text())
        self.assertEqual('browser-attestation', evidence['provenance'])
        self.assertIn('attestation', evidence)
        self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)
        self.assertEqual(0, self.run_cli('verify').returncode)
        self.assertEqual(0, self.run_cli('complete', 'task-1').returncode)
        report = self.run_cli('report', 'task-1', '--format', 'json')
        self.assertEqual(1, report.returncode)
        self.assertTrue(json.loads(report.stdout)['historical'])

    def test_timeout_retains_attempt_and_partial_log(self):
        tasks = base_tasks(command=[sys.executable, '-c', "import time; print('partial', flush=True); time.sleep(20)"])
        tasks['tasks'][0]['acceptance'][0]['timeout_seconds'] = 0.15
        self.write_json('tasks.json', tasks)
        self.run_cli('next')
        result = self.run_cli('verify')
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn('partial', result.stdout)
        check = self.read_tasks()['tasks'][0]['acceptance'][0]
        attempt = json.loads((self.workspace / check['latest_attempt']).read_text())
        self.assertEqual('timeout', attempt['reason'])
        self.assertEqual('failed', check['status'])

    def test_midrun_contract_drift_is_preserved_but_never_passes(self):
        script = "import json; from pathlib import Path; p=Path('.harness/tasks.json'); s=json.loads(p.read_text()); s['tasks'][0]['acceptance'][0]['instruction']='weaker'; p.write_text(json.dumps(s))"
        self.write_json('tasks.json', base_tasks(command=[sys.executable, '-c', script]))
        self.run_cli('next')
        self.assertEqual(1, self.run_cli('verify').returncode)
        check = self.read_tasks()['tasks'][0]['acceptance'][0]
        self.assertEqual('weaker', check['instruction'])
        self.assertEqual('unverified', check['status'])
        self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)

    def test_older_state_cannot_hide_newer_unfinished_attempt(self):
        self.ready()
        old = self.read_tasks()
        attempt_dir = self.harness_dir / 'attempts' / 'task-1'
        attempt_path = self.workspace / old['tasks'][0]['acceptance'][0]['latest_attempt']
        attempt = json.loads(attempt_path.read_text())
        attempt.update(attempt_id='newer', started_at='2099-01-01T00:00:00Z', status='running')
        (attempt_dir / 'newer.json').write_text(json.dumps(attempt))
        self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)

    def test_failed_spawn_retains_unverified_attempt(self):
        executable = self.harness_dir / 'artifacts' / 'never-installed-command.exe'
        self.assertFalse(executable.exists())
        self.write_json('tasks.json', base_tasks(command=[str(executable)]))
        selected = self.run_cli('next')
        self.assertEqual(0, selected.returncode, selected.stderr)
        result = self.run_cli('verify')
        self.assertEqual(2, result.returncode, result.stderr)
        check = self.read_tasks()['tasks'][0]['acceptance'][0]
        self.assertEqual('unverified', check['status'])
        attempt = json.loads((self.workspace / check['latest_attempt']).read_text())
        self.assertEqual('execution_error', attempt['status'])

    @unittest.skipUnless(os.name == 'posix', 'SIGINT uses POSIX')
    def test_interrupted_rerun_revokes_success(self):
        import signal
        import subprocess
        import time
        script = "from pathlib import Path; import time; print('started', flush=True); time.sleep(30 if Path('.harness/artifacts/wait').exists() else 0)"
        self.write_json('tasks.json', base_tasks(command=[sys.executable, '-c', script]))
        self.ready()
        (self.harness_dir / 'artifacts').mkdir()
        (self.harness_dir / 'artifacts' / 'wait').touch()
        process = subprocess.Popen([sys.executable, str(fixtures.SCRIPT), '--workspace', str(self.workspace), 'verify'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                check = self.read_tasks()['tasks'][0]['acceptance'][0]
                if check['status'] == 'unverified' and check.get('latest_attempt'):
                    attempt = json.loads((self.workspace / check['latest_attempt']).read_text())
                    if attempt['status'] == 'running':
                        break
                time.sleep(.02)
            else:
                self.fail('no running attempt observed')
            time.sleep(.15)
            process.send_signal(signal.SIGINT)
            _, stderr = process.communicate(timeout=5)
            self.assertEqual(130, process.returncode, stderr)
            self.assertEqual('unverified', self.read_tasks()['tasks'][0]['acceptance'][0]['status'])
            self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_add_definition_and_reject_duplicate_without_changing_state(self):
        path = self.workspace / 'definition.json'
        definition = {'id': 'added', 'title': 'Added', 'acceptance': [{'id': 'review', 'type': 'manual', 'instruction': 'Review', 'steps': ['Review']}]}
        path.write_text(json.dumps(definition))
        added = self.run_cli('task', 'add', '--from', str(path))
        self.assertEqual(0, added.returncode, added.stderr)
        state = (self.harness_dir / 'tasks.json').read_bytes()
        self.assertEqual(2, self.run_cli('task', 'add', '--from', str(path)).returncode)
        self.assertEqual(state, (self.harness_dir / 'tasks.json').read_bytes())

    def test_v2_pass_migration_detaches_evidence_without_resetting_git_baseline(self):
        self.initialize_git_repository()
        self.ready()
        old = self.read_tasks()
        config = base_config()
        config['schema_version'] = config['policy']['schema_version'] = 2
        old['schema_version'] = 2
        task = old['tasks'][0]
        task['git_baseline']['version'] = 2
        task['policy_baseline']['schema_version'] = 2
        baseline = dict(task['git_baseline'])
        legacy_path = task['acceptance'][0]['latest_evidence']
        task.pop('contract_baseline')
        self.write_json('config.json', config)
        self.write_json('tasks.json', old)
        result = self.run_cli('migrate', '--note', 'acknowledge current contract')
        self.assertEqual(0, result.returncode, result.stderr)
        task = self.read_tasks()['tasks'][0]
        self.assertEqual(baseline, task['git_baseline'])
        self.assertEqual('unverified', task['acceptance'][0]['status'])
        self.assertIsNone(task['acceptance'][0]['latest_evidence'])
        self.assertEqual(legacy_path, task['acceptance'][0]['legacy_evidence']['path'])
        self.assertTrue((self.workspace / legacy_path).exists())
        self.assertTrue(list((self.harness_dir / 'migrations').glob('v2-to-v3-*/tasks.v2.json')))

    def test_tracked_ignored_file_is_still_a_source_input(self):
        (self.workspace / '.gitignore').write_text('tracked.txt\n')
        source = self.workspace / 'tracked.txt'
        source.write_text('first')
        self.initialize_git_repository()
        import subprocess
        subprocess.run(['git', 'add', '-f', 'tracked.txt'], cwd=self.workspace, check=True, capture_output=True)
        self.ready()
        source.write_text('changed')
        self.assertEqual(1, self.run_cli('report', 'task-1', '--format', 'json').returncode)

    def test_positive_timeout_override_can_exceed_default(self):
        tasks = base_tasks()
        tasks['tasks'][0]['acceptance'][0]['timeout_seconds'] = 301
        self.write_json('tasks.json', tasks)
        result = self.run_cli('doctor')
        self.assertEqual(0, result.returncode, result.stderr)

    def test_report_describes_validated_acceptance_and_evidence(self):
        self.ready()
        report = self.run_cli('report', 'task-1', '--format', 'json')
        self.assertEqual(0, report.returncode, report.stderr)
        check = json.loads(report.stdout)['checks'][0]
        self.assertEqual('Prove the behavior', check['instruction'])
        self.assertEqual('command-exit', check['provenance'])
        self.assertTrue(check['evidence_valid'])
        self.assertTrue(check['summary'])
        self.assertTrue(check['evidence_path'])
        self.assertEqual([], check['artifacts'])
        text = self.run_cli('report', 'task-1', '--format', 'markdown').stdout
        self.assertIn(check['summary'], text)
        self.assertIn(check['evidence_path'], text)
        (self.workspace / 'source.txt').write_text('updated')
        stale = json.loads(self.run_cli('report', 'task-1', '--format', 'json').stdout)['checks'][0]
        self.assertFalse(stale['evidence_valid'])
        self.assertIsNone(stale['summary'])

    def test_handoff_recommends_reverification_after_source_drift(self):
        self.ready()
        (self.workspace / 'source.txt').write_text('updated')
        result = self.run_cli('handoff')
        self.assertEqual(0, result.returncode, result.stderr)
        handoff = (self.harness_dir / 'HANDOFF.md').read_text()
        self.assertIn('source snapshot is stale', handoff)
        self.assertIn('verify task-1', handoff)
        self.assertNotIn('Run `python3 .harness/harness.py complete task-1`', handoff)
        self.assertNotIn('check-1 [passed]', handoff)

    def test_init_cli_accepts_generic_and_rejects_unrequested_adapters(self):
        self.workspace = self.workspace / "fresh"
        self.workspace.mkdir()
        result = self.run_cli('init', '--agent', 'generic', '--dry-run')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, self.run_cli('init', '--agent', 'cursor', '--dry-run').returncode)

    def test_midrun_malformed_state_is_not_overwritten_with_stale_copy(self):
        script = "from pathlib import Path; Path('.harness/tasks.json').write_text('{broken')"
        self.write_json('tasks.json', base_tasks(command=[sys.executable, '-c', script]))
        self.run_cli('next')
        result = self.run_cli('verify')
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual('{broken', (self.harness_dir / 'tasks.json').read_text())
        attempt = json.loads(next((self.harness_dir / 'attempts' / 'task-1').glob('*.json')).read_text())
        self.assertEqual('unverified', attempt['status'])

    def test_ignored_harness_runtime_and_config_always_bind_evidence(self):
        (self.workspace / '.gitignore').write_text('.harness/\n')
        for name in ('harness.py', 'harness_runner.py', 'harness_init.py'):
            (self.harness_dir / name).write_text('# fixture runtime\n')
        adapters = self.harness_dir / 'adapters'
        adapters.mkdir()
        (adapters / 'generic.md').write_text('Runtime guidance\n')
        self.initialize_git_repository()
        self.ready()
        for relative in ('config.json', 'harness.py', 'harness_runner.py', 'harness_init.py', 'adapters/generic.md'):
            with self.subTest(path=relative):
                target = self.harness_dir / relative
                original = target.read_bytes()
                target.write_bytes(original + b'\n')
                result = self.run_cli('report', 'task-1', '--format', 'json')
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertFalse(json.loads(result.stdout)['ready'])
                self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)
                target.write_bytes(original)
        self.assertEqual(0, self.run_cli('report', 'task-1', '--format', 'json').returncode)
        generated = self.harness_dir / 'reports'
        generated.mkdir()
        (generated / 'new.md').write_text('Generated report')
        self.assertEqual(0, self.run_cli('complete', 'task-1').returncode)

    def add_clean_submodule(self):
        import tempfile
        import subprocess
        source_dir = tempfile.TemporaryDirectory()
        self.addCleanup(source_dir.cleanup)
        source = fixtures.Path(source_dir.name)
        for arguments in (['init'], ['config', 'user.email', 'test@example.test'], ['config', 'user.name', 'Test']):
            subprocess.run(['git', *arguments], cwd=source, check=True, capture_output=True)
        (source / 'library.txt').write_text('Library code\n')
        subprocess.run(['git', 'add', '.'], cwd=source, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'library'], cwd=source, check=True, capture_output=True)
        self.initialize_git_repository()
        subprocess.run(['git', '-c', 'protocol.file.allow=always', 'submodule', 'add', str(source), 'vendor/library'], cwd=self.workspace, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-am', 'add library'], cwd=self.workspace, check=True, capture_output=True)
        return self.workspace / 'vendor' / 'library'

    def test_clean_initialized_submodule_can_verify_and_complete(self):
        self.add_clean_submodule()
        self.ready()
        check = self.read_tasks()['tasks'][0]['acceptance'][0]
        evidence = json.loads((self.workspace / check['latest_evidence']).read_text())
        fingerprint = evidence['source_snapshot']['files']['vendor/library']
        self.assertIn('gitlink:', fingerprint)
        self.assertIn(':head:', fingerprint)
        self.assertEqual(0, self.run_cli('complete', 'task-1').returncode)

    def test_submodule_drift_rejects_prior_evidence_even_if_git_hides_dirty_files(self):
        import subprocess
        library = self.add_clean_submodule()
        self.ready()
        subprocess.run(['git', 'update-index', '--assume-unchanged', 'library.txt'], cwd=library, check=True, capture_output=True)
        (library / 'library.txt').write_text('Changed after verification\n')
        result = self.run_cli('report', 'task-1', '--format', 'json')
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual(1, self.run_cli('complete', 'task-1').returncode)

    def test_uninitialized_submodule_fails_closed_with_clear_diagnostic(self):
        import subprocess
        self.add_clean_submodule()
        subprocess.run(['git', 'submodule', 'deinit', '-f', 'vendor/library'], cwd=self.workspace, check=True, capture_output=True)
        self.assertEqual(0, self.run_cli('next').returncode)
        result = self.run_cli('verify')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('uninitialized submodule', result.stderr)

    def test_harness_bytecode_cache_is_generated_not_a_source_input(self):
        import subprocess
        module = self.harness_dir / 'cache_fixture.py'
        module.write_text('value = 1\n')
        self.ready()
        argv = [sys.executable, '-c', "import sys; sys.pycache_prefix = None; sys.path.insert(0, '.harness'); import cache_fixture"]
        env = {key: value for key, value in os.environ.items() if key != 'PYTHONDONTWRITEBYTECODE'}
        subprocess.run(argv, cwd=self.workspace, env=env, check=True, capture_output=True)
        cache_file = next((self.harness_dir / '__pycache__').glob('*.pyc'))
        first_cache = cache_file.read_bytes()
        result = self.run_cli('report', 'task-1', '--format', 'json')
        self.assertEqual(0, result.returncode, result.stderr)
        os.utime(module, (100, 100))
        subprocess.run(argv, cwd=self.workspace, env=env, check=True, capture_output=True)
        self.assertNotEqual(first_cache, cache_file.read_bytes())
        self.assertEqual(0, self.run_cli('complete', 'task-1').returncode)

    def test_fresh_evidence_with_scope_violation_recommends_git_inspection(self):
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli('next').returncode)
        (self.workspace / 'outside.txt').write_text('Task change outside allowed paths')
        verified = self.run_cli('verify')
        self.assertEqual(0, verified.returncode, verified.stderr)
        result = self.run_cli('report', 'task-1', '--format', 'json')
        self.assertEqual(1, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(all(check['ready'] for check in report['checks']))
        self.assertIn('outside allowed_paths', ' '.join(report['issues']))
        self.assertEqual('git status --short', report['next_command'])
