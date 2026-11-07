"""collectstatic that also rebuilds the admin panel on the server.

The panel is served from admin_panel/out, which git does not track, so a pull
alone leaves the old panel live. The server's shared deploy script runs
collectstatic on every deploy, which makes this the one step this repo controls.

That script is sourced with ``set -e`` and restarts Gunicorn after this step, so
a failed panel build must never fail the command. The previous panel stays live.
"""
import glob
import os
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.management.commands.collectstatic import (
    Command as CollectStaticCommand,
)

API_URL = '/api/v1'
AAPANEL_NODE_GLOB = '/www/server/nodejs/v*/bin/node'
STEP_TIMEOUT_SECONDS = 900


def find_node():
    """aaPanel installs Node outside PATH, so fall back to its newest version."""
    found = shutil.which('node')
    if found:
        return found
    versions = glob.glob(AAPANEL_NODE_GLOB)
    if not versions:
        return None
    return max(versions, key=lambda path: [int(part) for part in re.findall(r'\d+', path)])


def dependencies_stale(panel):
    installed = panel / 'node_modules' / '.package-lock.json'
    if not installed.exists():
        return True
    return (panel / 'package-lock.json').stat().st_mtime > installed.stat().st_mtime


class Command(CollectStaticCommand):
    def handle(self, **options):
        summary = super().handle(**options)
        if not settings.DEBUG and not options['dry_run']:
            self.build_admin_panel()
        return summary

    def build_admin_panel(self):
        out = Path(settings.ADMIN_PANEL_DIST)
        panel = out.parent
        backup = panel / 'out.previous'
        node = find_node()
        if node is None:
            self.stderr.write('Admin panel not rebuilt: Node was not found. The previous panel stays live.')
            return

        node_dir = Path(node).parent
        env = {
            **os.environ,
            'PATH': f'{node_dir}{os.pathsep}{os.environ.get("PATH", "")}',
            'NEXT_PUBLIC_API_URL': API_URL,
            'NEXT_TELEMETRY_DISABLED': '1',
        }
        shutil.rmtree(backup, ignore_errors=True)
        if out.is_dir():
            shutil.copytree(out, backup)
        try:
            self.stdout.write('Building admin panel...')
            if dependencies_stale(panel):
                self._run([str(node_dir / 'npm'), 'ci'], panel, env)
            # Through node, because deploy makes every project file non-executable.
            self._run([node, 'node_modules/next/dist/bin/next', 'build'], panel, env)
        except (OSError, subprocess.SubprocessError) as exc:
            if backup.is_dir():
                shutil.rmtree(out, ignore_errors=True)
                shutil.move(str(backup), str(out))
            self.stderr.write(f'Admin panel not rebuilt: {str(exc).rstrip(".")}. The previous panel stays live.')
        else:
            self.stdout.write(self.style.SUCCESS('Admin panel rebuilt.'))
        finally:
            shutil.rmtree(backup, ignore_errors=True)

    def _run(self, command, cwd, env):
        subprocess.run(command, cwd=cwd, env=env, check=True, timeout=STEP_TIMEOUT_SECONDS)
