import shutil
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings


class AdminPanelRootTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='pob-admin-root-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'index.html').write_text('panel home', encoding='utf-8')
        login = self.root / 'login'
        login.mkdir()
        (login / 'index.html').write_text('panel login', encoding='utf-8')
        override = override_settings(ADMIN_PANEL_DIST=self.root)
        override.enable()
        self.addCleanup(override.disable)

    def test_host_root_serves_the_panel(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'panel home')

    def test_panel_page_is_served_without_an_admin_prefix(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'panel login')

    def test_old_admin_prefix_redirects_to_the_root_path(self):
        response = self.client.get('/admin/login/?next=/finance/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/login/?next=/finance/')

    def test_bare_admin_prefix_redirects_home(self):
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/')
