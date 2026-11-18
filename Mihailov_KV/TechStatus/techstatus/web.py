from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from .store import EquipmentError, EquipmentStore

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')


def e(value: object) -> str:
    return escape(str(value), quote=True)


def frame(title: str, body: str, notice: str = '', error: bool = False) -> str:
    banner = f'<div class="notice {"bad" if error else ""}">{e(notice)}</div>' if notice else ''
    return f'''<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · ТехСтатус</title><link rel="stylesheet" href="/static/style.css"></head>
<body><header class="top"><div class="wrap header"><a href="/" class="logo"><span class="logo-icon">Т</span>ТехСтатус</a>
<nav><a href="/">Оборудование</a><a href="/history">Журнал операций</a></nav><span class="pill">Локальный режим</span></div></header>
<main class="wrap">{banner}{body}</main>
<footer class="wrap foot">ТехСтатус · Данные хранятся на этом компьютере</footer></body></html>'''


def dashboard(store: EquipmentStore, query: dict) -> str:
    search = query.get('q', [''])[0]
    status = query.get('status', ['all'])[0]
    if status not in ('all', 'available', 'issued'):
        status = 'all'
    items = store.list(search=search, status=status)
    counts = store.counts()
    cards = ''.join(f'<div class="stat"><span>{label}</span><strong>{counts[key]}</strong></div>'
                    for label, key in [('Всего объектов', 'all'), ('Доступно', 'available'), ('Занято', 'issued')])
    rows = ''
    for item in items:
        is_free = item['status'] == 'available'
        state = '<span class="tag ok">● Доступно</span>' if is_free else '<span class="tag busy">● Занято</span>'
        action = (f'<form method="post" action="/issue/{item["id"]}" class="inline">'
                  f'<input name="holder" aria-label="Кому выдать" placeholder="Получатель" required maxlength="100">'
                  '<button class="small primary">Выдать</button></form>') if is_free else (
                  f'<form method="post" action="/return/{item["id"]}" class="inline">'
                  '<button class="small">Вернуть</button></form>')
        remove = (f'<form method="post" action="/delete/{item["id"]}" class="inline">'
                  '<button class="small quiet" title="Удалить">×</button></form>') if is_free else ''
        rows += (f'<tr><td><strong>{e(item["inventory_no"])}</strong><small>{e(item["category"])}</small></td>'
                 f'<td>{e(item["name"])}</td><td>{e(item["room"])}</td><td>{state}</td>'
                 f'<td>{e(item["holder"]) or "—"}</td>'
                 f'<td class="actions">{action}<a class="small" href="/edit/{item["id"]}">Изменить</a>{remove}</td></tr>')
    if not rows:
        rows = '<tr><td colspan="6" class="empty">По заданным фильтрам оборудование не найдено.</td></tr>'
    status_links = ' '.join(f'<a class="filter {"chosen" if status==code else ""}" '
                            f'href="/?status={code}&q={quote(search)}">{label}</a>'
                            for code, label in [('all', 'Все'), ('available', 'Доступно'), ('issued', 'Занято')])
    reset_link = ('<a class="filter reset" href="/">Сбросить фильтры</a>'
                  if search or status != 'all' else '')
    return f'''<section class="hero"><div><div class="eyebrow">УЧЁТ УЧЕБНОГО ОБОРУДОВАНИЯ</div>
<h1>Всё оборудование — под контролем.</h1>
<p>Проверяйте доступность, оформляйте выдачу и возврат. Каждое действие сохраняется в журнале.</p></div>
<a href="/new" class="button primary">+ Добавить оборудование</a></section>
<section class="stats">{cards}</section>
<section class="panel"><div class="panel-head"><div><h2>Реестр оборудования</h2><p>Актуальный статус каждой единицы оборудования</p></div>
<form method="get" action="/" class="search"><input type="search" name="q" value="{e(search)}" placeholder="Поиск по номеру, названию, аудитории…"><button>Найти</button></form></div>
<div class="filters">{status_links} {reset_link}</div><div class="scroll"><table><thead><tr><th>Инв. номер</th><th>Наименование</th><th>Аудитория</th>
<th>Статус</th><th>Получатель</th><th>Действия</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''


def item_form(item: dict | None = None) -> str:
    item = item or {}
    is_edit = bool(item)
    title = 'Редактирование оборудования' if is_edit else 'Добавление оборудования'
    action = f'/update/{item["id"]}' if is_edit else '/add'
    fields = [('inventory_no', 'Инвентарный номер', 'TS-1001'),
              ('name', 'Наименование', 'Ноутбук Lenovo'),
              ('category', 'Категория', 'Компьютерная техника'),
              ('room', 'Аудитория / место хранения', 'Ауд. 305')]
    inputs = ''.join(f'<label>{e(label)}<input name="{key}" maxlength="{32 if key=="inventory_no" else 100}" '
                     f'placeholder="{e(ph)}" required value="{e(item.get(key,""))}"></label>' for key, label, ph in fields)
    return f'''<a class="back" href="/">← Вернуться к реестру</a><section class="form-panel"><h1>{title}</h1>
<p>Заполните карточку одного физического объекта с уникальным инвентарным номером.</p>
<form method="post" action="{action}" class="editform">{inputs}
<div class="form-actions"><button class="primary">Сохранить</button><a href="/">Отмена</a></div></form></section>'''


def history_page(store: EquipmentStore) -> str:
    rows = ''.join(f'<tr><td>{e(ev["created_at"])}</td><td>{e(ev["inventory_no"])}</td><td><b>{e(ev["action"])}</b></td>'
                   f'<td>{e(ev["details"])}</td></tr>' for ev in store.history())
    if not rows:
        rows = '<tr><td colspan="4" class="empty">Журнал пока пуст.</td></tr>'
    return f'''<a class="back" href="/">← Вернуться к реестру</a><section class="panel"><div class="panel-head">
<div><h1>Журнал операций</h1><p>Последние 50 записей об изменениях, выдаче и возврате.</p></div></div>
<div class="scroll"><table><thead><tr><th>Дата и время</th><th>Инв. номер</th><th>Операция</th><th>Детали</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>'''


def make_handler(store: EquipmentStore):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, data: str | bytes, code: int = 200, kind: str = 'text/html; charset=utf-8'):
            data = data.encode('utf-8') if isinstance(data, str) else data
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, message: str, error: bool = False):
            self.send_response(303)
            self.send_header('Location', '/?msg=' + quote(message) + ('&error=1' if error else ''))
            self.end_headers()

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == '/static/style.css':
                return self._send(CSS, kind='text/css; charset=utf-8')
            try:
                if parsed.path == '/':
                    content = dashboard(store, query)
                elif parsed.path == '/new':
                    content = item_form()
                elif parsed.path == '/history':
                    content = history_page(store)
                elif parsed.path.startswith('/edit/'):
                    equipment_id = int(parsed.path.rsplit('/', 1)[-1])
                    content = item_form(store.get(equipment_id))
                else:
                    return self._send(frame('Не найдено', '<h1>Страница не найдена</h1>'), 404)
            except (ValueError, EquipmentError) as error:
                return self._send(frame('Ошибка', '<h1>Ошибка запроса</h1><p>' + e(error) + '</p>'), 400)
            notice = query.get('msg', [''])[0]
            return self._send(frame('Оборудование', content, notice, 'error' in query))

        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size > 8192:
                    raise EquipmentError('Слишком большой запрос.')
                form = parse_qs(self.rfile.read(size).decode('utf-8'))
                get = lambda key: form.get(key, [''])[0]
                segments = self.path.strip('/').split('/')
                command = segments[0]
                if command == 'add' and len(segments) == 1:
                    store.add(get('inventory_no'), get('name'), get('category'), get('room'))
                    message = 'Оборудование добавлено.'
                elif command in ('issue', 'return', 'delete', 'update') and len(segments) == 2:
                    equipment_id = int(segments[1])
                    if command == 'issue':
                        store.issue(equipment_id, get('holder'))
                        message = 'Выдача оформлена.'
                    elif command == 'return':
                        store.return_item(equipment_id)
                        message = 'Возврат оформлен.'
                    elif command == 'delete':
                        store.delete(equipment_id)
                        message = 'Оборудование удалено.'
                    else:
                        store.update(equipment_id, get('inventory_no'), get('name'),
                                     get('category'), get('room'))
                        message = 'Карточка изменена.'
                else:
                    return self._send(frame('Не найдено', '<h1>Страница не найдена</h1>'), 404)
                self._redirect(message)
            except (EquipmentError, ValueError, UnicodeDecodeError) as error:
                self._redirect(str(error), error=True)

    return Handler


def serve(store: EquipmentStore, host: str = '127.0.0.1', port: int = 8000):
    server = ThreadingHTTPServer((host, port), make_handler(store))
    print(f'ТехСтатус запущен: http://{host}:{port}')
    print('Остановить: Ctrl+C')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
