"""Read-only allocation for DESC multi-OS activities.

An activity may contain many OS identifiers but all stock movements belong
to ONE exact selected OS per close code. This module never posts to Imperium.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from toa_adm_task_splitter import ADMTaskEvidence

class AllocationBlocked(ValueError):
    pass

@dataclass(frozen=True)
class SingleOSAllocation:
    target_os: str
    close_code: str
    installed_serials: tuple[str, ...]
    removed_serials: tuple[str, ...]
    other_os: tuple[str, ...]

def single_os_allocation(
    tasks: Sequence[ADMTaskEvidence], close_code: str,
    *, toa_installed: Sequence[str]=(), toa_removed: Sequence[str]=(),
) -> SingleOSAllocation:
    selected=sorted((task for task in tasks if task.close_code==close_code),
                    key=lambda task:(task.index, task.os_number))
    if not selected:
        raise AllocationBlocked("toa_close_code_not_in_tasks")
    if len({task.os_number for task in selected})!=len(selected):
        raise AllocationBlocked("duplicate_os_task")
    if not all(task.os_number and task.os_number.isdigit() for task in selected):
        raise AllocationBlocked("non_numeric_os_identity")
    def unique(values):
        return tuple(dict.fromkeys(str(v).strip().upper() for v in values if str(v).strip()))
    installed=unique(serial for task in selected for serial in task.installed_serials)
    removed=unique(serial for task in selected for serial in task.removed_serials)
    ownership = {}
    for task in tasks:
        for direction, serials in (("installed", task.installed_serials),
                                   ("removed", task.removed_serials)):
            for serial in unique(serials):
                previous = ownership.setdefault(serial, (task.close_code, direction))
                if previous[0] != task.close_code:
                    raise AllocationBlocked("equipment_code_conflict")
                if previous[1] != direction:
                    raise AllocationBlocked("equipment_direction_conflict")
    all_installed=unique(toa_installed)
    all_removed=unique(toa_removed)
    # Without per-task mapping the aggregate snapshot cannot be assigned safely
    # to only the requested code when there are mixed codes in a single activity.
    all_same_code=len(selected)==len(tasks)
    if all_same_code:
        installed=unique([*installed,*all_installed])
        removed=unique([*removed,*all_removed])
    else:
        mapped_installed = set(unique(s for t in tasks for s in t.installed_serials))
        mapped_removed = set(unique(s for t in tasks for s in t.removed_serials))
        if set(all_installed)-mapped_installed or set(all_removed)-mapped_removed:
            raise AllocationBlocked("mixed_code_equipment_mapping_incomplete")
    if set(installed)&set(removed):
        raise AllocationBlocked("equipment_direction_conflict")
    if close_code=="409" and not installed and not removed:
        raise AllocationBlocked("close_409_without_equipment")
    if close_code=="430" and not removed and not installed:
        raise AllocationBlocked("close_430_without_equipment")
    # First explicitly numbered task is the deterministic one-time equipment owner.
    return SingleOSAllocation(
       target_os=selected[0].os_number,
       close_code=close_code,
       installed_serials=installed,
       removed_serials=removed,
       other_os=tuple(task.os_number for task in selected[1:]),
    )
