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
import datetime as dt
import json
import time
from collections import Counter
from pathlib import Path

from imperium_api import ImperiumAPI


ROOT = Path(__file__).resolve().parent


def is_deterministic_error(message: str) -> bool:
    normalized = message.casefold()
    return any(
        marker in normalized
        for marker in (
            "nao esta disponivel para este servico",
            "different order",
            "primary key",
            "foreign key",
            "restricao",
            "restrição",
            "nao foi validada",
            "não foi validada",
            "seriam truncados",
        )
    )


def append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cancela todas as OS EM CAMPO da base selecionada."
    )
    parser.add_argument("--port", type=int, default=212)
    parser.add_argument("--company", default="NATAL / PARNAMIRIM")
    parser.add_argument("--profile", default="natal")
    parser.add_argument("--controller-id", type=int, default=313101)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()

    log_root = ROOT / "logs"
    if args.profile != "natal":
        log_root = log_root / args.profile
    audit = log_root / f"cancelamento-em-massa-{dt.date.today():%Y%m%d}.jsonl"
    api = ImperiumAPI(
        ROOT,
        port=args.port,
        company=args.company,
        profile_key=args.profile,
        controller_id=args.controller_id,
        log_root=log_root,
    )
    started = time.monotonic()
    totals = Counter()
    deterministic_failures: set[int] = set()

    for round_number in range(1, max(1, args.rounds) + 1):
        orders = api.list_orders(dt.date.today())
        eligible = [
            order for order in orders if order.id_os not in deterministic_failures
        ]
        print(
            f"RODADA {round_number}: {len(orders)} OS em campo; "
            f"{len(eligible)} serao processadas",
            flush=True,
        )
        append_event(
            audit,
            {
                "at": dt.datetime.now().isoformat(timespec="seconds"),
                "event": "round_started",
                "round": round_number,
                "open": len(orders),
                "eligible": len(eligible),
            },
        )
        if not eligible:
            break

        for index, order in enumerate(eligible, start=1):
            item_started = time.monotonic()
            try:
                result = api.close_order(order, "0")
            except Exception as exc:
                error = str(exc)
                totals["failed"] += 1
                if is_deterministic_error(error):
                    deterministic_failures.add(order.id_os)
                event = {
                    "at": dt.datetime.now().isoformat(timespec="seconds"),
                    "event": "failed",
                    "round": round_number,
                    "index": index,
                    "total": len(eligible),
                    "id_os": order.id_os,
                    "num_os": order.num_os,
                    "contract": order.contract,
                    "service": order.service,
                    "duration_seconds": round(time.monotonic() - item_started, 3),
                    "error": error,
                }
                append_event(audit, event)
                print(
                    f"[{index}/{len(eligible)}] ERRO OS {order.num_os}: {error}",
                    flush=True,
                )
                continue

            totals["closed"] += 1
            append_event(
                audit,
                {
                    "at": dt.datetime.now().isoformat(timespec="seconds"),
                    "event": "closed",
                    "round": round_number,
                    "index": index,
                    "total": len(eligible),
                    "id_os": order.id_os,
                    "num_os": order.num_os,
                    "contract": order.contract,
                    "service": order.service,
                    "duration_seconds": round(time.monotonic() - item_started, 3),
                    "already_closed": bool(result.get("already_closed")),
                },
            )
            print(
                f"[{index}/{len(eligible)}] OK OS {order.num_os} "
                f"({totals['closed']} baixadas; {totals['failed']} falhas)",
                flush=True,
            )

        if round_number < args.rounds:
            print("Aguardando 5 segundos antes da conferencia...", flush=True)
            time.sleep(5)

    remaining = api.list_orders(dt.date.today())
    summary = {
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "event": "completed",
        "closed": totals["closed"],
        "failed_attempts": totals["failed"],
        "remaining": len(remaining),
        "duration_seconds": round(time.monotonic() - started, 3),
        "remaining_orders": [order.to_dict() for order in remaining],
    }
    append_event(audit, summary)
    print(
        "CONCLUIDO: "
        f"{summary['closed']} baixadas; {summary['failed_attempts']} falhas; "
        f"{summary['remaining']} OS ainda em campo",
        flush=True,
    )


if __name__ == "__main__":
    main()
