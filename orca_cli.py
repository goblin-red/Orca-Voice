"""Работа с Orca через его CLI: какая вкладка в фокусе, переключение вкладок, отправка клавиш, статусы агентов."""

import json
import shutil
import subprocess

from i18n import t

# команда orca: из PATH, а если её там нет — прямо из приложения Orca
ORCA = shutil.which("orca") or "/Applications/Orca.app/Contents/Resources/bin/orca"


def _run(args, timeout=10):
    """Запускает `orca ... --json` и возвращает поле result."""
    proc = subprocess.run(
        [ORCA, *args, "--json"],
        capture_output=True, text=True, timeout=timeout,
    )
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        raise RuntimeError(f"orca {' '.join(args)}: {t('err.orca_not_json')}: {proc.stdout[:200]} {proc.stderr[:200]}")
    if not data.get("ok"):
        raise RuntimeError(f"orca {' '.join(args)}: {data.get('error') or proc.stderr[:300]}")
    return data["result"]


def worktrees():
    """Все рабочие области Orca вместе с агентами (состояние, последний ответ)."""
    return _run(["worktree", "ps"]).get("worktrees", [])


# ---------- вкладка в фокусе

def _terminal_leaves(node, active_leaf=None):
    """Обходит дерево раскладки и отдаёт терминалы только из активных вкладок."""
    if isinstance(node, list):
        for item in node:
            yield from _terminal_leaves(item, active_leaf)
        return
    if not isinstance(node, dict):
        return

    if node.get("type") == "terminal":
        yield node, active_leaf
        return

    # группа вкладок: берём только активную вкладку
    if "tabs" in node:
        tab = next((t for t in node["tabs"] if t.get("tabId") == node.get("activeTabId")), None)
        if tab:
            yield from _terminal_leaves(tab.get("panes"), tab.get("activeLeafId"))
        return

    # сплит или другой контейнер: идём во все вложенные узлы
    for value in node.values():
        if isinstance(value, (dict, list)):
            yield from _terminal_leaves(value, active_leaf)


def _tabs(node):
    """Все вкладки раскладки по порядку (и активные, и нет)."""
    if isinstance(node, list):
        for item in node:
            yield from _tabs(item)
        return
    if not isinstance(node, dict):
        return

    if "tabs" in node:
        yield from node["tabs"]
        return

    for value in node.values():
        if isinstance(value, (dict, list)):
            yield from _tabs(value)


def _active_layout():
    """Активная рабочая область, её терминалы и раскладка: (active, listing, layout) или None."""
    active = next((w for w in worktrees() if w.get("isActive")), None)
    if not active:
        return None

    wt_id = active["worktreeId"]
    listing = _run(["terminal", "list", "--worktree", f"id:{wt_id}", "--include-visual-layouts"])
    layout = next((l for l in listing.get("visualLayouts", []) if l.get("worktreeId") == wt_id), None)
    if not layout:
        return None
    return active, listing, layout


def _focused_leaf(layout):
    """Панель терминала в фокусе или None."""
    leaves = list(_terminal_leaves(layout.get("root")))
    # активная панель вкладки важнее остальных панелей той же вкладки
    best = next((leaf for leaf, act in leaves if leaf.get("leafId") == act), None)
    if best is None and leaves:
        best = leaves[0][0]
    return best


def _describe(leaf, active, listing):
    """Панель -> {handle, paneKey, title, worktree, agent, cwd}."""
    info = next((t for t in listing.get("terminals", []) if t.get("handle") == leaf["handle"]), {})
    return {
        "handle": leaf["handle"],
        "paneKey": f"{leaf['tabId']}:{leaf['leafId']}",
        "title": leaf.get("title", ""),
        "worktree": active.get("displayName", ""),
        "agent": info.get("agentIdentity"),                     # claude / codex / opencode
        "cwd": info.get("worktreePath") or active.get("path"),  # папка проекта
    }


def focused_terminal():
    """Терминал в фокусе окна Orca: {handle, paneKey, title, worktree} или None."""
    found = _active_layout()
    if not found:
        return None
    active, listing, layout = found

    best = _focused_leaf(layout)
    if best is None:
        return None
    return _describe(best, active, listing)


# ---------- переключение вкладок

def next_agent_terminal():
    """Следующая по кругу вкладка с агентом в активном проекте или None, если другой такой нет."""
    found = _active_layout()
    if not found:
        return None
    active, listing, layout = found

    agents = {t.get("handle") for t in listing.get("terminals", []) if t.get("agentIdentity")}
    current = _focused_leaf(layout)
    current_tab = current.get("tabId") if current else None

    tabs = list(_tabs(layout.get("root")))
    start = next((i for i, tab in enumerate(tabs) if tab.get("tabId") == current_tab), -1)

    # идём по кругу от текущей вкладки, обычные терминалы пропускаем
    for step in range(1, len(tabs) + 1):
        tab = tabs[(start + step) % len(tabs)]
        if tab.get("tabId") == current_tab:
            continue
        leaves = [leaf for leaf, _ in _terminal_leaves(tab.get("panes")) if leaf.get("handle") in agents]
        if not leaves:
            continue
        # активная панель вкладки важнее остальных
        leaf = next((l for l in leaves if l.get("leafId") == tab.get("activeLeafId")), leaves[0])
        return _describe(leaf, active, listing)
    return None


def switch_terminal(handle):
    """Выводит вкладку терминала на передний план."""
    return _run(["terminal", "switch", "--terminal", handle])


# ---------- клавиши

def send_space(handle):
    return _run(["terminal", "send", "--terminal", handle, "--text", " "])


def send_enter(handle):
    return _run(["terminal", "send", "--terminal", handle, "--enter"])


def send_text(handle, text):
    """Печатает текст во ввод терминала без Enter."""
    tail = " " if text[-1:].isspace() else ""   # пробел в конце нужен, чтобы фразы не слипались
    text = " ".join(text.split()) + tail        # без переводов строк — иначе агент отправит раньше времени
    return _run(["terminal", "send", "--terminal", handle, "--text", text])
