"""Operator-only LOCAL CLI for staging the Atlas x Imperium confrontation.

Never serves HTTP. No automatic daemon, no production queue mutation unless
the privileged operator explicitly invokes 'step' for an existing job.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations" / "serial_consult"))

JOB_DB = Path(r"C:\DominiumRuntime\ConfrontJobData\jobs.sqlite3")


def main():
    from atlas_bridge_client import AtlasBridgeClient
    from confront_export import confront_csv
    from confront_job_runner import ConfrontJobStore

    parser = argparse.ArgumentParser(description="DOMINIUM confronto Atlas x Imperium (local staging)")
    sub = parser.add_subparsers(dest="action", required=True)

    create = sub.add_parser("create", help="Criar trabalho sem iniciar consultas")
    create.add_argument("--profile", required=True, choices=("natal", "fortaleza", "mossoro", "recife"))
    create.add_argument("--mode", choices=("analitico", "sintetico"), default="analitico")
    create.add_argument("--input", required=True, type=Path, help="Arquivo de seriais, um por linha")

    status = sub.add_parser("status", help="Mostrar progresso sem exibir dados de clientes")
    status.add_argument("--job", required=True)
    step = sub.add_parser("step", help="Executar UMA etapa de consulta somente leitura")
    step.add_argument("--job", required=True)

    recover = sub.add_parser("recover", help="Marcar POST interrompido para revisao; nao reenvia")
    recover.add_argument("--job", required=True)

    export = sub.add_parser("export", help="Exportar resultado CSV local")
    export.add_argument("--job", required=True)
    export.add_argument("--output", required=True, type=Path)

    args = parser.parse_args()
    store = ConfrontJobStore(JOB_DB)
    if args.action == "create":
        if not args.input.is_file() or args.input.stat().st_size > 50_000:
            parser.error("Arquivo nao encontrado ou acima de 50 KB")
        serials = args.input.read_text(encoding="utf-8-sig")
        job_id = store.create(serials, profile=args.profile, mode=args.mode)
        print(json.dumps({"created": True, "job_id": job_id,
                          "total": store.progress(job_id)["total"]}))
    elif args.action == "status":
        print(json.dumps(store.progress(args.job), ensure_ascii=False))
    elif args.action == "recover":
        repaired = store.recover_uncertain(args.job)
        print(json.dumps({"orphaned_submissions_for_review": repaired,
                          "progress": store.progress(args.job)}))
    elif args.action == "step":
        from serial_service import consult_serials
        action = store.step(args.job, imperium_query=consult_serials, atlas_client=AtlasBridgeClient())
        print(json.dumps({"action": action, "progress": store.progress(args.job)}, ensure_ascii=False))
    elif args.action == "export":
        progress = store.progress(args.job, include_rows=True)
        if progress["done"] != progress["total"]:
            parser.error("Trabalho ainda nao finalizado; nao exportar resultado parcial")
        results = []
        for row in progress["rows"]:
            result = row["resultado"]
            if result is None:
                result = {
                    "serial": row["serial"], "situacao": "inconclusivo",
                    "motivos": [row["error_code"] or "revisao_manual_pendente"],
                    "atlas": None, "imperium": None, "evidencias": [], "alertas": [],
                }
            results.append(result)
        destination = args.output.resolve()
        if destination.exists():
            parser.error("Arquivo de destino ja existe; nao substituir relatorios")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="") as handle:
            handle.write(confront_csv({"resultados": results}))
        print(json.dumps({"exported": True, "rows": len(results),
                          "file": str(destination)}))


if __name__ == "__main__":
    main()
