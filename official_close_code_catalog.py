# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - SIM - protocolo, baixa, estoque ou operacao do Imperium.
#
# TOA
# - NAO - este arquivo nao consulta nem automatiza o TOA.
#
# DOMINIUM COMPARTILHADO
# - Apoio local apenas quando necessario ao fluxo Imperium.
#
# Categoria deste arquivo: IMPERIUM.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
import argparse
import hashlib
import json
import re
from pathlib import Path


CATALOG_SCHEMA = "dominium_official_close_code_catalog_v1"

# Data pages and their visible table boundaries in Tabela_codigo_baixa0711.pdf.
# Category title pages immediately precede these table pages.
PAGE_LAYOUTS = {
    **{
        page: ("IMPRODUTIVOS", (39.1, 129.4, 334.4))
        for page in range(4, 9)
    },
    **{
        page: ("IMPRODUTIVOS", (42.1, 178.5, 359.3))
        for page in range(9, 12)
    },
    13: ("SINAL", (63.6, 297.0, None)),
    15: ("PASSIVO", (65.6, 289.3, None)),
    17: ("EQUIPAMENTO (T.T)", (57.1, 264.6, None)),
    18: ("EQUIPAMENTO (T.T)", (56.6, 267.0, None)),
    20: ("RECONFIGURACAO", (57.1, 266.3, None)),
    22: ("CONEXOES", (57.1, 266.3, None)),
    24: ("CLIENTE", (57.1, 266.3, None)),
    25: ("CLIENTE", (57.1, 266.3, None)),
    27: ("CABEAMENTO", (57.1, 266.3, None)),
    29: ("INFRA-ESTRUTURA", (57.1, 266.3, None)),
    31: ("TELEFONIA", (57.1, 266.3, None)),
    33: ("MANUTENCAO MDU", (57.1, 266.3, None)),
    35: ("SMARTHOME/CYBER-REDE/EXTENSAO WIFI", (57.1, 266.3, None)),
    37: ("GPON/MDU GPON (EXCLUSIVO)", (57.1, 266.3, None)),
    38: ("GPON/MDU GPON (EXCLUSIVO)", (57.1, 266.3, None)),
    40: ("MESH", (57.1, 266.3, None)),
    42: ("RETIRADA", (85.4, 329.1, None)),
    44: ("VISTORIA", (85.4, 329.1, None)),
}


class CloseCodeCatalogError(ValueError):
    pass


def _clean_text(value: object) -> str:
    cleaned = " ".join(str(value or "").split())
    return re.sub(
        (
            r"\s*Bot[aã]o de menu de tr[eê]s linhas horizontais"
            r"\s*\|\s*[ÍI]cone Gratis(?:\s+\d+)?\s*$"
        ),
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CloseCodeCatalogError(
            f"Nao foi possivel ler o PDF: {exc}"
        ) from exc
    return digest.hexdigest()


def _crop_text(page, bbox: tuple[float, float, float, float]) -> str:
    x0, top, x1, bottom = bbox
    safe_bbox = (
        max(0.0, x0),
        max(0.0, top),
        min(float(page.width), x1),
        min(float(page.height), bottom),
    )
    value = page.crop(safe_bbox).extract_text(
        x_tolerance=2,
        y_tolerance=3,
    )
    return _clean_text(value)


def extract_pdf_rows(path: str | Path) -> tuple[list[dict], int]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise CloseCodeCatalogError(
            "pdfplumber e necessario para extrair o catalogo"
        ) from exc

    source = Path(path)
    try:
        pdf = pdfplumber.open(source)
    except Exception as exc:
        raise CloseCodeCatalogError(
            f"Nao foi possivel abrir o PDF: {exc}"
        ) from exc

    rows = []
    try:
        page_count = len(pdf.pages)
        if page_count < max(PAGE_LAYOUTS):
            raise CloseCodeCatalogError(
                f"PDF incompleto: {page_count} paginas"
            )
        for page_number in sorted(PAGE_LAYOUTS):
            category, boundaries = PAGE_LAYOUTS[page_number]
            page = pdf.pages[page_number - 1]
            tables = page.find_tables()
            if not tables:
                raise CloseCodeCatalogError(
                    f"Tabela nao encontrada na pagina {page_number}"
                )
            table = max(
                tables,
                key=lambda value: value.bbox[2] - value.bbox[0],
            )
            description_start, usage_start, communication_start = boundaries
            for row in table.rows[1:]:
                if row.bbox[2] - row.bbox[0] < float(page.width) * 0.85:
                    continue
                top, bottom = row.bbox[1], row.bbox[3]
                code_text = _crop_text(
                    page,
                    (table.bbox[0], top, description_start, bottom),
                )
                code = re.sub(r"\D", "", code_text)
                if not re.fullmatch(r"\d{3}", code):
                    continue
                description = _crop_text(
                    page,
                    (description_start, top, usage_start, bottom),
                )
                usage_end = communication_start or table.bbox[2]
                usage_rule = _crop_text(
                    page,
                    (usage_start, top, usage_end, bottom),
                )
                customer_communication = ""
                if communication_start is not None:
                    customer_communication = _crop_text(
                        page,
                        (
                            communication_start,
                            top,
                            table.bbox[2],
                            bottom,
                        ),
                    )
                rows.append(
                    {
                        "code": code,
                        "category": category,
                        "description": description,
                        "usage_rule": usage_rule,
                        "customer_communication": (
                            customer_communication or None
                        ),
                        "page": page_number,
                    }
                )
    finally:
        pdf.close()
    return rows, page_count


def build_close_code_catalog(
    rows: list[dict],
    *,
    source_file_name: str,
    source_sha256: str,
    page_count: int,
) -> dict:
    if not rows:
        raise CloseCodeCatalogError("Nenhum codigo foi extraido do PDF")
    by_code: dict[str, list[dict]] = {}
    for index, raw_row in enumerate(rows, 1):
        if not isinstance(raw_row, dict):
            raise CloseCodeCatalogError(
                f"Linha extraida invalida na posicao {index}"
            )
        code = _clean_text(raw_row.get("code"))
        category = _clean_text(raw_row.get("category"))
        description = _clean_text(raw_row.get("description"))
        usage_rule = _clean_text(raw_row.get("usage_rule"))
        communication = _clean_text(
            raw_row.get("customer_communication")
        )
        try:
            page = int(raw_row.get("page"))
        except (TypeError, ValueError) as exc:
            raise CloseCodeCatalogError(
                f"Pagina invalida para o codigo {code or '?'}"
            ) from exc
        if not re.fullmatch(r"\d{3}", code):
            raise CloseCodeCatalogError(f"Codigo invalido: {code}")
        if not category or not description or not usage_rule:
            raise CloseCodeCatalogError(
                f"Campos obrigatorios ausentes para o codigo {code}"
            )
        if page <= 0 or page > page_count:
            raise CloseCodeCatalogError(
                f"Pagina fora do documento para o codigo {code}"
            )
        by_code.setdefault(code, []).append(
            {
                "category": category,
                "description": description,
                "usage_rule": usage_rule,
                "customer_communication": communication or None,
                "page": page,
            }
        )

    entries = []
    warnings = []
    for code in sorted(by_code, key=int):
        occurrences = by_code[code]
        content_variants: dict[tuple, dict] = {}
        for occurrence in occurrences:
            key = (
                occurrence["category"],
                occurrence["description"],
                occurrence["usage_rule"],
                occurrence["customer_communication"],
            )
            variant = content_variants.setdefault(
                key,
                {
                    "category": occurrence["category"],
                    "description": occurrence["description"],
                    "usage_rule": occurrence["usage_rule"],
                    "customer_communication": occurrence[
                        "customer_communication"
                    ],
                    "source_pages": [],
                    "occurrences": 0,
                },
            )
            variant["source_pages"].append(occurrence["page"])
            variant["occurrences"] += 1
        variants = sorted(
            content_variants.values(),
            key=lambda value: (
                value["category"],
                value["description"],
                value["usage_rule"],
                value["customer_communication"] or "",
            ),
        )
        for variant in variants:
            variant["source_pages"] = sorted(set(variant["source_pages"]))

        if len(variants) == 1:
            variant = variants[0]
            entry = {
                "code": code,
                "status": "valid",
                "category": variant["category"],
                "description": variant["description"],
                "usage_rule": variant["usage_rule"],
                "customer_communication": variant[
                    "customer_communication"
                ],
                "source_pages": variant["source_pages"],
                "occurrences": len(occurrences),
            }
            if len(occurrences) > 1:
                warnings.append(
                    {
                        "type": "duplicate_code_identical",
                        "code": code,
                        "occurrences": len(occurrences),
                        "source_pages": variant["source_pages"],
                        "automatic_correction": False,
                    }
                )
        else:
            entry = {
                "code": code,
                "status": "inconsistent",
                "category": None,
                "description": None,
                "usage_rule": None,
                "customer_communication": None,
                "source_pages": sorted(
                    {
                        page
                        for variant in variants
                        for page in variant["source_pages"]
                    }
                ),
                "occurrences": len(occurrences),
                "variants": variants,
            }
            warnings.append(
                {
                    "type": "duplicate_code_inconsistent",
                    "code": code,
                    "occurrences": len(occurrences),
                    "source_pages": entry["source_pages"],
                    "automatic_correction": False,
                }
            )
        entries.append(entry)

    return {
        "schema": CATALOG_SCHEMA,
        "mode": "offline_pdf_extraction",
        "source": {
            "file_name": Path(source_file_name).name,
            "sha256": source_sha256.lower(),
            "page_count": page_count,
        },
        "occurrence_count": len(rows),
        "unique_code_count": len(entries),
        "entries": entries,
        "warnings": warnings,
        "aliases_created": [],
        "equivalences_authorized": [],
        "payload_generated": False,
        "safety": {
            "network_used": False,
            "post_executed": False,
            "datasnap_read_executed": False,
            "datasnap_write_executed": False,
            "stock_movement_executed": False,
            "close_executed": False,
            "payload_generated": False,
        },
    }


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extrai catalogo offline de codigos de baixa do PDF.",
    )
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    rows, page_count = extract_pdf_rows(args.pdf)
    catalog = build_close_code_catalog(
        rows,
        source_file_name=Path(args.pdf).name,
        source_sha256=_sha256(args.pdf),
        page_count=page_count,
    )
    _write_json_atomic(Path(args.output), catalog)
    print(
        json.dumps(
            {
                "catalog": args.output,
                "occurrences": catalog["occurrence_count"],
                "unique_codes": catalog["unique_code_count"],
                "warnings": len(catalog["warnings"]),
                "payload_generated": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
