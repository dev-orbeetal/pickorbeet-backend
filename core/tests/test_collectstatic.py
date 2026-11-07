import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from core.management.commands import collectstatic as command


class AdminPanelBuildTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='pob-panel-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.panel = self.root / 'admin_panel'
        self.out = self.panel / 'out'
        self.out.mkdir(parents=True)
        (self.out / 'index.html').write_text('old panel')
        (self.panel / 'package-lock.json').write_text('{}')
        installed = self.panel / 'node_modules' / '.package-lock.json'
        installed.parent.mkdir()
        installed.write_text('{}')

        settings_override = override_settings(
            ADMIN_PANEL_DIST=self.out,
            STATIC_ROOT=self.root / 'static',
            STATICFILES_DIRS=[],
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        node = mock.patch.object(command, 'find_node', return_value='/opt/node/bin/node')
        node.start()
        self.addCleanup(node.stop)
        run = mock.patch.object(command.subprocess, 'run', side_effect=self._build)
        self.run_mock = run.start()
        self.addCleanup(run.stop)
        self.build_fails = False

    def _build(self, args, **_kwargs):
        if args[1:2] != ['ci']:
            self.env = _kwargs['env']
            shutil.rmtree(self.out)
            self.out.mkdir()
            (self.out / 'partial.html').write_text('half written')
            if self.build_fails:
                raise subprocess.CalledProcessError(1, args)
            (self.out / 'index.html').write_text('new panel')

    def _collect(self, **options):
        stdout, stderr = StringIO(), StringIO()
        call_command('collectstatic', interactive=False, verbosity=0, stdout=stdout, stderr=stderr, **options)
        return stdout.getvalue(), stderr.getvalue()

    def _commands(self):
        return [call.args[0] for call in self.run_mock.call_args_list]

    @override_settings(DEBUG=False)
    def test_deploy_rebuilds_the_panel_through_node(self):
        self._collect()

        self.assertEqual(
            self._commands(),
            [['/opt/node/bin/node', 'node_modules/next/dist/bin/next', 'build']],
        )
        self.assertEqual(self.env['NEXT_PUBLIC_API_URL'], '/api/v1')
        self.assertTrue(self.env['PATH'].startswith('/opt/node/bin'))
        self.assertEqual((self.out / 'index.html').read_text(), 'new panel')
        self.assertFalse((self.panel / 'out.previous').exists())

    @override_settings(DEBUG=False)
    def test_failed_build_keeps_the_previous_panel_and_does_not_fail_the_deploy(self):
        self.build_fails = True
        _stdout, stderr = self._collect()

        self.assertIn('previous panel stays live', stderr)
        self.assertEqual((self.out / 'index.html').read_text(), 'old panel')
        self.assertFalse((self.out / 'partial.html').exists())
        self.assertFalse((self.panel / 'out.previous').exists())

    @override_settings(DEBUG=False)
    def test_timed_out_build_keeps_the_previous_panel(self):
        self.run_mock.side_effect = subprocess.TimeoutExpired('next', 1)
        _stdout, stderr = self._collect()

        self.assertIn('previous panel stays live', stderr)
        self.assertEqual((self.out / 'index.html').read_text(), 'old panel')

    @override_settings(DEBUG=False)
    def test_missing_node_does_not_fail_the_deploy(self):
        with mock.patch.object(command, 'find_node', return_value=None):
            _stdout, stderr = self._collect()

        self.assertIn('Node was not found', stderr)
        self.assertEqual(self._commands(), [])

    @override_settings(DEBUG=False)
    def test_changed_lockfile_installs_dependencies_first(self):
        (self.panel / 'node_modules' / '.package-lock.json').unlink()
        self._collect()

        self.assertEqual(self._commands()[0], ['/opt/node/bin/npm', 'ci'])
        self.assertEqual(self._commands()[1][2], 'build')

    @override_settings(DEBUG=True)
    def test_local_collectstatic_does_not_build(self):
        self._collect()
        self.assertEqual(self._commands(), [])

    @override_settings(DEBUG=False)
    def test_dry_run_does_not_build(self):
        self._collect(dry_run=True)
        self.assertEqual(self._commands(), [])


class FindNodeTests(SimpleTestCase):
    def test_path_wins(self):
        with mock.patch.object(command.shutil, 'which', return_value='/usr/bin/node'):
            self.assertEqual(command.find_node(), '/usr/bin/node')

    def test_newest_aapanel_version_is_numeric_not_alphabetical(self):
        paths = ['/www/server/nodejs/v9.1.0/bin/node', '/www/server/nodejs/v22.23.1/bin/node']
        with mock.patch.object(command.shutil, 'which', return_value=None):
            with mock.patch.object(command.glob, 'glob', return_value=paths):
                self.assertEqual(command.find_node(), paths[1])

    def test_no_node_anywhere(self):
        with mock.patch.object(command.shutil, 'which', return_value=None):
            with mock.patch.object(command.glob, 'glob', return_value=[]):
                self.assertIsNone(command.find_node())
