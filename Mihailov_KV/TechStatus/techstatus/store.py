"""Доменная логика и постоянное хранение данных проекта «ТехСтатус»."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class EquipmentError(ValueError):
    """Некорректная операция с карточкой оборудования."""


def _text(value: str, field: str, limit: int = 100) -> str:
    result = (value or "").strip()
    if not result:
        raise EquipmentError(f"Заполните поле «{field}».")
    if len(result) > limit:
        raise EquipmentError(f"Поле «{field}» слишком длинное (до {limit} символов).")
    return result


class EquipmentStore:
    """Локальный SQLite-реестр. Одна запись — один инвентарный объект."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inventory_no TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    room TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'available'
                        CHECK (status IN ('available', 'issued')),
                    holder TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id INTEGER NOT NULL,
                    inventory_no TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _event(db, obj, action: str, details: str):
        db.execute(
            "INSERT INTO events(equipment_id, inventory_no, action, details, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (obj['id'], obj['inventory_no'], action, details,
             datetime.now().strftime('%d.%m.%Y %H:%M:%S')),
        )

    def add(self, inventory_no: str, name: str, category: str, room: str) -> int:
        inventory_no = _text(inventory_no, 'Инвентарный номер', 32)
        name = _text(name, 'Наименование')
        category = _text(category, 'Категория', 60)
        room = _text(room, 'Аудитория', 60)
        with self._connect() as db:
            try:
                cur = db.execute(
                    "INSERT INTO equipment(inventory_no,name,category,room) VALUES (?,?,?,?)",
                    (inventory_no, name, category, room),
                )
            except sqlite3.IntegrityError as error:
                raise EquipmentError('Такой инвентарный номер уже существует.') from error
            self._event(db, {'id': cur.lastrowid, 'inventory_no': inventory_no},
                        'Добавление', name)
            return int(cur.lastrowid)

    def get(self, equipment_id: int) -> dict:
        with self._connect() as db:
            row = db.execute('SELECT * FROM equipment WHERE id=?', (equipment_id,)).fetchone()
        if row is None:
            raise EquipmentError('Оборудование не найдено.')
        return dict(row)

    def list(self, search: str = '', status: str = 'all') -> list[dict]:
        if status not in ('all', 'available', 'issued'):
            raise EquipmentError('Неизвестный статус фильтра.')
        search = search.strip()[:100].casefold()
        sql = 'SELECT * FROM equipment'
        params: list[str] = []
        if status != 'all':
            sql += ' WHERE status=?'
            params.append(status)
        sql += ' ORDER BY inventory_no COLLATE NOCASE'
        with self._connect() as db:
            items = [dict(row) for row in db.execute(sql, params).fetchall()]
        # SQLite LIKE регистронезависим только для ASCII; casefold корректно ищет кириллицу.
        if search:
            items = [x for x in items if any(search in str(x[key]).casefold()
                     for key in ('inventory_no', 'name', 'category', 'room', 'holder'))]
        return items

    def counts(self) -> dict[str, int]:
        with self._connect() as db:
            rows = db.execute('SELECT status, count(*) n FROM equipment GROUP BY status').fetchall()
        data = {row['status']: row['n'] for row in rows}
        return {'all': sum(data.values()), 'available': data.get('available', 0),
                'issued': data.get('issued', 0)}

    def update(self, equipment_id: int, inventory_no: str, name: str,
               category: str, room: str) -> None:
        obj = self.get(equipment_id)
        inventory_no = _text(inventory_no, 'Инвентарный номер', 32)
        name = _text(name, 'Наименование')
        category = _text(category, 'Категория', 60)
        room = _text(room, 'Аудитория', 60)
        with self._connect() as db:
            try:
                db.execute('UPDATE equipment SET inventory_no=?, name=?, category=?, room=? WHERE id=?',
                           (inventory_no, name, category, room, equipment_id))
            except sqlite3.IntegrityError as error:
                raise EquipmentError('Такой инвентарный номер уже существует.') from error
            self._event(db, obj, 'Изменение', f'{name}; номер: {inventory_no}')

    def issue(self, equipment_id: int, holder: str) -> None:
        holder = _text(holder, 'Получатель', 100)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            obj = db.execute('SELECT * FROM equipment WHERE id=?', (equipment_id,)).fetchone()
            if obj is None:
                raise EquipmentError('Оборудование не найдено.')
            if obj['status'] != 'available':
                raise EquipmentError('Оборудование уже выдано. Повторная выдача запрещена.')
            db.execute("UPDATE equipment SET status='issued', holder=? WHERE id=?",
                       (holder, equipment_id))
            self._event(db, obj, 'Выдача', f'Получатель: {holder}')

    def return_item(self, equipment_id: int) -> None:
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            obj = db.execute('SELECT * FROM equipment WHERE id=?', (equipment_id,)).fetchone()
            if obj is None:
                raise EquipmentError('Оборудование не найдено.')
            if obj['status'] != 'issued':
                raise EquipmentError('Оборудование уже доступно. Повторный возврат невозможен.')
            db.execute("UPDATE equipment SET status='available', holder='' WHERE id=?",
                       (equipment_id,))
            self._event(db, obj, 'Возврат', f'Предыдущий получатель: {obj["holder"]}')

    def delete(self, equipment_id: int) -> None:
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            obj = db.execute('SELECT * FROM equipment WHERE id=?', (equipment_id,)).fetchone()
            if obj is None:
                raise EquipmentError('Оборудование не найдено.')
            if obj['status'] == 'issued':
                raise EquipmentError('Нельзя удалить выданное оборудование. Сначала оформите возврат.')
            db.execute('DELETE FROM equipment WHERE id=?', (equipment_id,))
            self._event(db, obj, 'Удаление', obj['name'])

    def history(self, limit: int = 50) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM events ORDER BY id DESC LIMIT ?', (min(max(limit, 1), 500),))]
