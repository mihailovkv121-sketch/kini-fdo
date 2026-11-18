"""Запуск локальной веб-программы «ТехСтатус»."""
from pathlib import Path
from techstatus.store import EquipmentStore
from techstatus.web import serve

if __name__ == '__main__':
    db = Path(__file__).resolve().parent / 'data' / 'techstatus.sqlite3'
    serve(EquipmentStore(db))
