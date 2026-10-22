"""Minimal, backup-first insertion of the confront read-only API into live DESC relay.

Keeps REPORTs, DESC, stock, OS-check, token and existing watchdog unchanged.
No restart or HTTP requests are performed by this installer.
Run without --apply to verify anchors. Run --apply only after quality gate.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import shutil
from pathlib import Path

STAGE = Path(r"C:\DominiumRuntime\SerialMultiCityPatch-20261022\integrations\serial_consult")
LIVE = Path(r"C:\DominiumRuntime\DescRelay-20261010")
FILES = ("atlas_bridge_client.py", "confront_engine.py", "confront_export.py",
         "confront_job_runner.py", "confront_http.py")
MARKER = "# DOMINIUM CONFRONT PRIVATE ENDPOINT"


def one_replace(text: str, before: str, after: str) -> str:
    if text.count(before) != 1:
        raise RuntimeError("Live DESC relay changed: expected anchor not unique")
    return text.replace(before, after, 1)


def make_patch(original: str) -> str:
    if MARKER in original:
        return original
    changed = one_replace(original,
        "from operator_reports import OperatorReports, ReportError\n",
        "from operator_reports import OperatorReports, ReportError\n"
        + "from confront_http import ConfrontService, parse_confront_route\n")
    changed = one_replace(changed,
        "    def _dispatch(self):\n",
        """    def _csv(self, content):
        data = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="dominium-confronto.csv"')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self):
""")
    changed = one_replace(changed,
        "        if self.path == '/api/disconnection/reports' and self.command in ('GET', 'POST'):\n",
        """        # DOMINIUM CONFRONT PRIVATE ENDPOINT
        confrontation = parse_confront_route(self.command, self.path)
        if confrontation is not None:
            if self.headers.get('X-Dominium-Role') not in {'admin', 'controller'}:
                self._json(403, {'ok': False, 'error': 'Perfil operacional necessario'})
                return
            try:
                body = self._read_json() if self.command == 'POST' else None
                status, result, content_type = self.server.confront_service.handle(
                    self.command, self.path, actor, body)
                if content_type == 'text/csv; charset=utf-8' and status == 200:
                    self._csv(result)
                else:
                    self._json(status, result)
            except ValueError:
                self._json(400, {'ok': False, 'error': 'Corpo invalido'})
            return
        if self.path == '/api/disconnection/reports' and self.command in ('GET', 'POST'):
""")
    changed = one_replace(changed,
        "    server.serve_forever()\n",
        """    server.confront_service = ConfrontService()
    try:
        server.serve_forever()
    finally:
        server.confront_service.close()
""")
    ast.parse(changed)
    if not all(x in changed for x in ("operator_reports", "DescReviewProxy", "OfficialStockBridge", "serial_service")):
        raise RuntimeError("Live DESC integrations unexpectedly missing")
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    target = LIVE / "desc_review_relay.py"
    if not target.is_file():
        raise SystemExit("Live relay missing")
    original = target.read_text(encoding="utf-8")
    patched = make_patch(original)
    for filename in FILES:
        data = (STAGE / filename).read_text(encoding="utf-8")
        ast.parse(data)
    print("patch_ready", patched != original)
    print("staging_files_verified", len(FILES))
    print("reports_preserved", "operator_reports" in patched)
    if not args.apply:
        print("dry_run_only", True)
        return
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = LIVE / "backups" / ("pre-confront-" + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(target, backup / target.name)
    try:
        for filename in FILES:
            existing = LIVE / filename
            if existing.is_file():
                shutil.copy2(existing, backup / filename)
            shutil.copy2(STAGE / filename, existing)
        target.write_text(patched, encoding="utf-8", newline="")
    except Exception:
        shutil.copy2(backup / target.name, target)
        for filename in FILES:
            saved = backup / filename
            installed = LIVE / filename
            if saved.is_file():
                shutil.copy2(saved, installed)
            elif installed.is_file():
                installed.unlink()
        raise
    print("installed", True)
    print("backup_folder", str(backup))
    print("restart_performed", False)


if __name__ == "__main__":
    main()
