#!/usr/bin/env python3
"""
Загружает список всех опубликованных баттлов Standoff365 через API
и сохраняет HTML и Markdown с глобальной таблицей в папку battles/.
"""

import json
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

BASE_URL = "https://api.standoff365.com/api/game-portal/battles/published"
OUT_DIR = Path(__file__).parent / "battles"
OUT_HTML = OUT_DIR / "battles_list.html"
OUT_MD = OUT_DIR / "battles_list.md"


BATTLE_IDS_UP_TO = 100  # парсим баттлы с ID от 1 до этого числа
BATCH_SIZE = 25  # сколько battle_ids в одном запросе


def _request(params: dict) -> dict:
    """Выполняет GET-запрос к API."""
    if requests:
        r = requests.get(BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    from urllib.request import urlopen
    from urllib.parse import urlencode
    url = f"{BASE_URL}?{urlencode(params, doseq=True)}"
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_battles() -> list[dict]:
    """Загружает баттлы с ID от 1 до BATTLE_IDS_UP_TO (по API battle_ids), затем сортирует по ID."""
    all_items = []
    ids = list(range(1, BATTLE_IDS_UP_TO + 1))
    for i in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[i : i + BATCH_SIZE]
        params = {"paginated": "false"}
        for bid in batch_ids:
            params.setdefault("battle_ids", []).append(bid)
        # requests с list: battle_ids=1&battle_ids=2&...
        data = _request(params)
        items = data if isinstance(data, list) else data.get("items", [])
        all_items.extend(items)
    # убираем дубликаты, сортируем по battleId
    by_id = {b["battleId"]: b for b in all_items}
    return [by_id[k] for k in sorted(by_id.keys())]


def format_date(iso_str: str | None) -> str:
    """Форматирует ISO дату в читаемый вид."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_str or "—"


def battle_url(battle: dict) -> str:
    """Собирает URL страницы баттла из domains."""
    domains = battle.get("domains") or []
    bid = battle.get("battleId", "")
    if domains and bid:
        base = domains[0].get("url", "hackbase.standoff365.com")
        return f"https://{base}/battle/{bid}"
    return f"https://hackbase.standoff365.com/battle/{bid}" if bid else ""


def escape_html(s: str) -> str:
    """Экранирует HTML-символы."""
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_html(battles: list[dict]) -> str:
    """Строит один HTML с таблицей всех баттлов."""
    rows_html = []
    for b in battles:
        bid = b.get("battleId", "")
        name = escape_html(b.get("name") or "")
        desc = escape_html((b.get("description") or "")[:200])
        if (b.get("description") or "").strip() and len((b.get("description") or "")) > 200:
            desc += "…"
        status = b.get("status") or "—"
        started = format_date((b.get("timings") or {}).get("startedAt"))
        finished = format_date((b.get("timings") or {}).get("finishedAt"))
        url = battle_url(b)
        landing = escape_html((b.get("landingAddress") or "").strip() or "—")

        name_cell = f'<a href="{escape_html(url)}" target="_blank" rel="noopener">{name}</a>' if url else name
        link_cell = f'<a href="{escape_html(url)}" target="_blank" rel="noopener">Открыть</a>' if url else "—"

        rows_html.append(
            f"            <tr>\n"
            f"                <td>{bid}</td>\n"
            f"                <td>{name_cell}</td>\n"
            f"                <td>{desc}</td>\n"
            f"                <td>{escape_html(status)}</td>\n"
            f"                <td>{started}</td>\n"
            f"                <td>{finished}</td>\n"
            f"                <td>{link_cell}</td>\n"
            f"                <td>{landing}</td>\n"
            f"            </tr>"
        )

    table_body = "\n".join(rows_html)

    count = len(battles)
    return (
        """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Список баттлов Standoff365</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th {
            background-color: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }
        td {
            padding: 10px;
            border: 1px solid #ddd;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        a {
            color: #1976d2;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>Список баттлов Standoff365</h1>
    <p>Всего: """
        + str(count)
        + """ баттлов. Данные с API game-portal.</p>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Описание</th>
                <th>Статус</th>
                <th>Начало</th>
                <th>Окончание</th>
                <th>Ссылка</th>
                <th>Landing</th>
            </tr>
        </thead>
        <tbody>
"""
        + table_body
        + """
        </tbody>
    </table>
</body>
</html>
"""
    )


def _md_cell(s: str, max_len: int = 120) -> str:
    """Очищает строку для ячейки markdown-таблицы (без | и переносов)."""
    if not s:
        return "—"
    t = str(s).replace("|", " / ").replace("\n", " ").strip()
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return t


def build_md(battles: list[dict]) -> str:
    """Строит один Markdown-файл с таблицей всех баттлов."""
    lines = [
        "# Список баттлов Standoff365",
        "",
        f"Всего: {len(battles)} баттлов. Данные с API game-portal.",
        "",
        "| ID | Название | Описание | Статус | Начало | Окончание | Ссылка | Landing |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for b in battles:
        bid = b.get("battleId", "")
        name = _md_cell(b.get("name") or "", 80)
        desc = _md_cell((b.get("description") or "")[:200], 150)
        status = _md_cell(b.get("status") or "—")
        started = format_date((b.get("timings") or {}).get("startedAt"))
        finished = format_date((b.get("timings") or {}).get("finishedAt"))
        url = battle_url(b)
        link = f"[Открыть]({url})" if url else "—"
        landing = _md_cell((b.get("landingAddress") or "").strip() or "—")
        lines.append(f"| {bid} | {name} | {desc} | {status} | {started} | {finished} | {link} | {landing} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    print("Загрузка списка баттлов...")
    battles = fetch_all_battles()
    print(f"Загружено баттлов: {len(battles)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = build_html(battles)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Сохранено: {OUT_HTML}")
    md = build_md(battles)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"Сохранено: {OUT_MD}")


if __name__ == "__main__":
    main()
