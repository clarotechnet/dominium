# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO - este arquivo nao envia operacoes ao Imperium.
#
# TOA
# - SIM - sessao, coleta, importacao, inventario ou monitor do TOA.
#
# DOMINIUM COMPARTILHADO
# - A saida pode alimentar o restante do DOMINIUM em modo leitura.
#
# Categoria deste arquivo: TOA.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
import json
import threading
import unicodedata
from collections import Counter
from dataclasses import replace
from pathlib import Path


def normalize(value: object) -> str:
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(character)
    ).upper()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in text)
        .split()
    )


class TechnicianDirectory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._mtime_ns = -1
        self._source: dict = {}
        self._technicians: list[dict] = []
        self._by_login: dict[str, dict] = {}
        self._by_name: dict[str, dict] = {}

    def _reload_if_needed(self) -> None:
        try:
            mtime_ns = self.path.stat().st_mtime_ns
        except OSError:
            mtime_ns = 0
        if mtime_ns == self._mtime_ns:
            return

        with self._lock:
            if mtime_ns == self._mtime_ns:
                return
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}

            technicians = []
            for raw in payload.get("technicians", []):
                if not isinstance(raw, dict):
                    continue
                login = str(raw.get("login", "")).strip().upper()
                name = " ".join(str(raw.get("name", "")).strip().split()).upper()
                if not login or not name:
                    continue
                raw_toa = raw.get("toa", {})
                if not isinstance(raw_toa, dict):
                    raw_toa = {}
                toa = {
                    key: str(raw_toa.get(key, "")).strip()
                    for key in (
                        "resource_id",
                        "user_id",
                        "city",
                        "bucket",
                        "city_status",
                        "route_status",
                        "total_os",
                        "pending_os",
                        "skills",
                        "calendar",
                        "groups",
                        "work_areas",
                        "captured_at",
                        "record_origin",
                    )
                }
                technicians.append(
                    {
                        "login": login,
                        "name": name,
                        "plate": str(raw.get("plate", "")).strip().upper(),
                        "teams": sorted(
                            {
                                " ".join(str(value).strip().split())
                                for value in raw.get("teams", [])
                                if str(value).strip()
                            }
                        ),
                        "profiles": sorted(
                            {
                                str(value).strip().lower()
                                for value in raw.get("profiles", [])
                                if str(value).strip()
                            }
                        ),
                        "city": toa["city"].upper(),
                        "bucket": toa["bucket"].upper(),
                        "city_status": toa["city_status"].lower(),
                        "toa": toa,
                    }
                )
            technicians.sort(key=lambda item: (normalize(item["name"]), item["login"]))
            self._source = payload.get("source", {}) if isinstance(payload, dict) else {}
            self._technicians = technicians
            self._by_login = {normalize(item["login"]): item for item in technicians}
            self._by_name = {normalize(item["name"]): item for item in technicians}
            self._mtime_ns = mtime_ns

    def resolve(self, value: object) -> dict | None:
        self._reload_if_needed()
        key = normalize(value)
        if not key:
            return None
        return self._by_login.get(key) or self._by_name.get(key)

    def enrich_preview(self, preview):
        orders = []
        for order in preview.orders:
            technician = self.resolve(order.technician)
            orders.append(
                replace(
                    order,
                    technician_login=(
                        technician["login"] if technician else order.technician.strip().upper()
                    ),
                    technician_name=technician["name"] if technician else "",
                )
            )
        return replace(preview, orders=tuple(orders))

    def public_dict(self) -> dict:
        self._reload_if_needed()
        teams = Counter(
            team for technician in self._technicians for team in technician["teams"]
        )
        return {
            "ok": True,
            "count": len(self._technicians),
            "with_plate": sum(bool(item["plate"]) for item in self._technicians),
            "teams": dict(sorted(teams.items())),
            "source": dict(self._source),
            "technicians": [dict(item) for item in self._technicians],
        }
