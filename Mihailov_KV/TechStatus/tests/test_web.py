"""Checks HTML of the registry for reset link in active filters."""
import tempfile
import unittest
from pathlib import Path
from techstatus.store import EquipmentStore
from techstatus.web import dashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = EquipmentStore(Path(self.directory.name) / 'data.sqlite3')
        self.store.add('TS-101', 'Проектор', 'Проекторы', 'Ауд. 101')

    def tearDown(self):
        self.directory.cleanup()

    def test_reset_control_is_visible_for_search(self):
        page = dashboard(self.store, {'q': ['Проектор'], 'status': ['all']})
        self.assertIn('Сбросить фильтры', page)
        self.assertIn('href="/"', page)

    def test_reset_control_hidden_without_filter(self):
        page = dashboard(self.store, {'q': [''], 'status': ['all']})
        self.assertNotIn('Сбросить фильтры', page)


if __name__ == '__main__':
    unittest.main()
