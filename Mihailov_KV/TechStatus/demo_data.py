"""Добавить демонстрационные записи в пустую локальную базу данных."""
from pathlib import Path
from techstatus.store import EquipmentStore

store = EquipmentStore(Path(__file__).resolve().parent / 'data' / 'techstatus.sqlite3')
if store.counts()['all']:
    print('В базе уже есть оборудование, повторное заполнение пропущено.')
else:
    examples = [
        ('TS-001', 'Ноутбук Lenovo ThinkBook', 'Ноутбуки', 'Ауд. 305'),
        ('TS-002', 'Проектор Epson EB-X06', 'Проекторы', 'Ауд. 206'),
        ('TS-003', 'Ноутбук Acer Aspire', 'Ноутбуки', 'Ауд. 305'),
        ('TS-004', 'Веб-камера Logitech', 'Периферия', 'Ауд. 312'),
        ('TS-005', 'Мультимедийный проектор BenQ', 'Проекторы', 'Ауд. 208'),
        ('TS-006', 'Микрофон USB', 'Аудиооборудование', 'Ауд. 312'),
    ]
    ids = [store.add(*obj) for obj in examples]
    store.issue(ids[1], 'Кафедра, занятие № 12')
    store.issue(ids[4], 'Преподаватель аудитории 208')
    print('Добавлены 6 демонстрационных единиц оборудования (4 доступны, 2 заняты).')
