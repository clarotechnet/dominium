from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_ROOT = ROOT / ".dominium"
STOP_WORDS = {
    "a", "as", "o", "os", "de", "da", "do", "das", "dos", "e", "em",
    "para", "por", "que", "um", "uma", "the", "and", "of", "to", "in",
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9_/.-]+", " ", text.casefold()).strip()


def tokens(value: str) -> list[str]:
    return [
        token for token in normalize(value).split()
        if len(token) > 1 and token not in STOP_WORDS
    ]
@dataclass(frozen=True)
class Hit:
    score: int
    kind: str
    path: str
    line: str
    label: str
    detail: str

    def render(self) -> str:
        location = self.path + (f":{self.line}" if self.line else "")
        suffix = f" | {self.detail}" if self.detail else ""
        return f"{self.score:03d} {self.kind:<10} {location} | {self.label}{suffix}"


def read_tsv(name: str) -> list[dict[str, str]]:
    path = INDEX_ROOT / name
    if not path.is_file():
        raise SystemExit(
            f"Missing {path.relative_to(ROOT)}; run scripts/generate_agent_context.py"
        )
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def score(query: str, wanted: list[str], *fields: object) -> int:
    values = [normalize(field) for field in fields if field]
    haystack = " ".join(values)
    if not haystack:
        return 0
    total = 0
    normalized_query = normalize(query)
    if normalized_query and normalized_query in haystack:
        total += 80
    words = re.findall(r"[a-z0-9]+", haystack.replace("_", " "))
    matched = 0
    for token in wanted:
        stem = token[:5] if len(token) >= 6 else token
        token_matches = token in haystack or (
            len(stem) >= 4 and any(word.startswith(stem) for word in words)
        )
        if token_matches:
            matched += 1
            total += 12
            if any(value == token for value in values):
                total += 8
    if wanted and matched == len(wanted):
        total += 25
    return total
def symbol_hits(query: str, wanted: list[str]) -> list[Hit]:
    result: list[Hit] = []
    for row in read_tsv("symbol-index.tsv"):
        value = score(
            query, wanted,
            row.get("name"), row.get("parent"), row.get("path"), row.get("kind"),
        )
        if value:
            path = row.get("path", "")
            source_bias = -8 if path.startswith("tests/") else 8
            result.append(Hit(
                value + 12 + source_bias, "symbol", path, row.get("line", ""),
                row.get("name", ""),
                row.get("kind", "") + (
                    f" parent={row.get('parent')}"
                    if row.get("parent") not in {"", "-"} else ""
                ),
            ))
    return result


def file_hits(query: str, wanted: list[str]) -> list[Hit]:
    result: list[Hit] = []
    for row in read_tsv("file-index.tsv"):
        value = score(
            query, wanted,
            row.get("path"), row.get("category"), row.get("summary"),
        )
        if value:
            path = row.get("path", "")
            source_bias = -8 if row.get("category") == "tests" else 8
            result.append(Hit(
                value + source_bias, "file", path, "",
                row.get("summary", "") or row.get("path", ""),
                row.get("category", ""),
            ))
    return result
def api_hits(query: str, wanted: list[str]) -> list[Hit]:
    result: list[Hit] = []
    for row in read_tsv("api-index.tsv"):
        value = score(query, wanted, row.get("endpoint"), row.get("path"))
        if value:
            result.append(Hit(
                value + 8, "api", row.get("path", ""), "",
                row.get("endpoint", ""), "",
            ))
    return result


def dependency_hits(query: str, wanted: list[str]) -> list[Hit]:
    result: list[Hit] = []
    for row in read_tsv("dependency-index.tsv"):
        value = score(query, wanted, row.get("import"), row.get("path"))
        if value:
            result.append(Hit(
                value, "import", row.get("path", ""), "",
                row.get("import", ""), "",
            ))
    return result


def dedupe(hits: list[Hit]) -> list[Hit]:
    best: dict[tuple[str, str, str, str], Hit] = {}
    for hit in hits:
        key = (hit.kind, hit.path, hit.line, hit.label)
        current = best.get(key)
        if current is None or hit.score > current.score:
            best[key] = hit
    return sorted(
        best.values(),
        key=lambda item: (-item.score, item.kind, item.path, item.line, item.label),
    )
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query DOMINIUM generated agent indexes without scanning source files."
    )
    parser.add_argument("query", nargs="+", help="symbol, endpoint, module, or concept")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument(
        "--kind",
        choices=("all", "symbol", "file", "api", "import"),
        default="all",
    )
    args = parser.parse_args()
    query = " ".join(args.query).strip()
    wanted = tokens(query)
    if not wanted:
        raise SystemExit("Query has no searchable terms")

    handlers = {
        "symbol": symbol_hits,
        "file": file_hits,
        "api": api_hits,
        "import": dependency_hits,
    }
    hits: list[Hit] = []
    selected = handlers if args.kind == "all" else {args.kind: handlers[args.kind]}
    for handler in selected.values():
        hits.extend(handler(query, wanted))

    ranked = dedupe(hits)[: max(1, min(args.limit, 50))]
    print(f"DOMINIUM_CONTEXT_QUERY query={query!r} hits={len(ranked)}")
    for hit in ranked:
        print(hit.render())
    if not ranked:
        print("No indexed candidate. Read docs/agent/TASK_ROUTER.md, then use narrow source search.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
