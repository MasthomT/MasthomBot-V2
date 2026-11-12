"""Les requêtes partent telles quelles à PostgreSQL (plus de traduction SQLite) :
un marqueur « ? » dans une requête la ferait échouer à l'exécution."""

import ast
import pathlib
import re

SQL = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH)\b", re.I)
APP = pathlib.Path(__file__).resolve().parent.parent / "app"


def _sql_literals():
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                text = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            else:
                continue
            if SQL.match(text):
                yield path.relative_to(APP.parent), node.lineno, text


def test_no_sqlite_placeholders():
    offenders = [f"{p}:{ln}" for p, ln, text in _sql_literals()
                 if re.search(r"(=|,|\(|>|<|\bIN|\bLIKE)\s*\?", text)]
    assert not offenders, "Marqueurs SQLite « ? » à remplacer par $1, $2… : " + ", ".join(offenders)
