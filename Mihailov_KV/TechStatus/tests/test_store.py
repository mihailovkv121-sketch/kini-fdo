import tempfile
import unittest
from pathlib import Path
from techstatus.store import EquipmentStore, EquipmentError


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = EquipmentStore(Path(self.temp.name) / 'test.sqlite3')
        self.first = self.store.add('TS-1', 'Проектор', 'Проекторы', 'Ауд. 101')

    def tearDown(self):
        self.temp.cleanup()

    def test_add_and_statistics(self):
        self.assertEqual(self.store.counts(), {'all': 1, 'available': 1, 'issued': 0})

    def test_issue_changes_status(self):
        self.store.issue(self.first, 'Преподаватель')
        self.assertEqual(self.store.get(self.first)['status'], 'issued')
        self.assertEqual(self.store.get(self.first)['holder'], 'Преподаватель')

    def test_return_restores_availability(self):
        self.store.issue(self.first, 'Кабинет 101')
        self.store.return_item(self.first)
        self.assertEqual(self.store.get(self.first)['status'], 'available')
        self.assertEqual(self.store.get(self.first)['holder'], '')

    def test_duplicate_inventory_number_rejected(self):
        with self.assertRaises(EquipmentError):
            self.store.add('TS-1', 'Второй проектор', 'Проекторы', 'Ауд. 102')

    def test_double_issue_rejected(self):
        self.store.issue(self.first, 'Преподаватель')
        with self.assertRaises(EquipmentError):
            self.store.issue(self.first, 'Другой получатель')

    def test_return_available_rejected(self):
        with self.assertRaises(EquipmentError):
            self.store.return_item(self.first)

    def test_delete_issued_rejected(self):
        self.store.issue(self.first, 'Преподаватель')
        with self.assertRaises(EquipmentError):
            self.store.delete(self.first)

    def test_search_and_filter(self):
        self.store.issue(self.first, 'Преподаватель')
        self.store.add('TS-2', 'Микрофон', 'Аудио', 'Ауд. 102')
        self.assertEqual(len(self.store.list(status='issued')), 1)
        self.assertEqual(len(self.store.list(search='микрофон')), 1)

    def test_search_by_current_recipient(self):
        self.store.issue(self.first, 'Учебная лаборатория 205')
        self.assertEqual(len(self.store.list(search='лаборатория 205')), 1)
        self.assertEqual(len(self.store.list(search='несуществующий получатель')), 0)

    def test_update_fields(self):
        self.store.update(self.first, 'TS-100', 'Проектор Epson', 'Проекторы', 'Ауд. 203')
        self.assertEqual(self.store.get(self.first)['inventory_no'], 'TS-100')

    def test_delete_available(self):
        self.store.delete(self.first)
        self.assertEqual(self.store.counts()['all'], 0)

    def test_empty_field_rejected(self):
        with self.assertRaises(EquipmentError):
            self.store.add('', 'Проектор', 'Проекторы', 'Ауд. 101')

    def test_history_registers_actions(self):
        self.store.issue(self.first, 'Преподаватель')
        self.store.return_item(self.first)
        actions = [x['action'] for x in self.store.history()]
        self.assertEqual(actions[:3], ['Возврат', 'Выдача', 'Добавление'])


if __name__ == '__main__':
    unittest.main()
