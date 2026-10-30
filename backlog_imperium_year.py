"""Planejamento seguro da sincronizacao anual Imperium/DataSnap.

Modular e sem IO: nenhum acesso de rede, baixa, gravacao ou automacao.
Usado pelo futuro executor para dividir a carga e retomar apos falhas.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping

PROFILES = ("natal", "fortaleza", "mossoro", "recife")
DATE_FMT = "%Y-%m-%d"


@dataclass(frozen=True)
class YearWindow:
    start: dt.date
    end: dt.date

    @property
    def days(self) -> int:
        return max(0, (self.end - self.start).days + 1)


@dataclass(frozen=True)
class DayTask:
    profile: str
    date: dt.date


def _one_year_before(day: dt.date) -> dt.date:
    """Calendario real: 29/02 cai em 28/02 no ano anterior."""
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def year_window(today: dt.date | None = None) -> YearWindow:
    """Ultimos 12 meses completos ate ontem; nao consulta o dia corrente."""
    day = today or dt.date.today()
    return YearWindow(start=_one_year_before(day), end=day - dt.timedelta(days=1))


def plan_days(
    *,
    today: dt.date,
    checkpoints: Mapping[str, dt.date | None] | None = None,
    max_days_per_profile: int = 7,
) -> list[DayTask]:
    """Retoma apenas dias ainda nao confirmados, por perfil.

    Checkpoint so pode ser atualizado depois de gravar e validar integralmente
    todos os registros de um dia. Nenhuma nova consulta durante a execucao.
    """
    if not 1 <= max_days_per_profile <= 31:
        raise ValueError("max_days_per_profile deve ser de 1 a 31")
    w = year_window(today)
    checkpoints = checkpoints or {}
    tasks: list[DayTask] = []
    for profile in PROFILES:
        checkpoint = checkpoints.get(profile)
        if checkpoint is not None and not isinstance(checkpoint, dt.date):
            raise ValueError("checkpoint invalido")
        start = max(w.start, checkpoint + dt.timedelta(days=1)) if checkpoint else w.start
        for i in range(min(max_days_per_profile, max(0, (w.end - start).days + 1))):
            tasks.append(DayTask(profile, start + dt.timedelta(days=i)))
    return tasks


def valid_close_code(value: object) -> str | None:
    """Codigo 3 digitos confirmado pelo detalhe, nunca inferido de status."""
    code = str(value or "").strip()
    return code if re.fullmatch(r"[0-9]{3}", code) and code != "000" else None


def normalize_city(name: object) -> str:
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text.strip().upper())
    if text in {"PARNAMIRIM", "NATAL"}:
        return "NATAL/PARNAMIRIM"
    if text in {"JABOATAO DOS GUARARAPES", "RECIFE"}:
        return "RECIFE"
    return text


def historical_record(
    *,
    profile: str,
    activity_day: dt.date,
    id_os: int,
    os_number: str,
    contract: str,
    code: object,
) -> dict[str, object]:
    """Exige code validado; nunca classifica como 'sem historico' sem ler."""
    if profile not in PROFILES:
        raise ValueError("Perfil desconhecido")
    if not isinstance(activity_day, dt.date):
        raise ValueError("Data invalida")
    if id_os <= 0 or not str(os_number).strip() or not str(contract).strip().isdigit():
        raise ValueError("O.S./contrato invalido")
    close_code = valid_close_code(code)
    if close_code is None:
        raise ValueError("Codigo de baixa sem confirmacao; nao importar como historico concluido")
    return {
        "idempotency_key": f"{profile}:{id_os}:{activity_day.isoformat()}",
        "profile": profile,
        "activity_date": activity_day.isoformat(),
        "id_os": id_os,
        "os_number": str(os_number).strip(),
        "contract": str(contract).strip(),
        "baixa_code": close_code,
        "source": "imperium_datasnap_detail",
    }
