import unittest
from dataclasses import replace
import disconnect_local_runner as runner
from disconnect_contracts import (DisconnectMessageEvent, DisconnectJob,
                                 TOADisconnectSnapshot, TOAEquipment, MovementDirection)
from toa_adm_task_splitter import ADMTaskEvidence


class MultiOwnerTests(unittest.TestCase):
    def test_companion_task_without_items_reaches_safe_aggregation_plan(self):
        event = DisconnectMessageEvent(
            message_id="message-test", chat_id="group", sender_id="sender",
            received_at="2026-10-29T18:00:00Z", raw_text="4000001 430",
            contract="4000001", requested_close_code="430", import_origin="NTL",
            city="NATAL", profile_key="natal",
        )
        snapshot = TOADisconnectSnapshot.create(
            profile_key="natal", city="NATAL", contract="4000001",
            activity_id="203000001", activity_type="Desconexao", activity_status="complete",
            installed_equipments=(),
            removed_equipments=(TOAEquipment(serial="SERIAL01",equipment_type="DECODER",
                                             direction=MovementDirection.OUTGOING),),
            materials=(), source_reference="toa|bucket=NTL-DMV_ADM", job_id="job-test",
            message_id="message-test", group_id="group", processing_id="message-test",
            direction_source="toa_csv_validation_baixa_exact_task",
            task_os_numbers=("2663000001","2663000002"), materials_complete=True,
        )
        job = DisconnectJob.create(event,snapshot,job_id="job-test",ttl_seconds=900)
        tasks=(ADMTaskEvidence(1,"2663000001","430","RETIRAR","",(),("SERIAL01",),"test.csv"),
               ADMTaskEvidence(2,"2663000002","430","RETIRAR","",(),(),"test.csv"))
        children=runner._adm_child_jobs(job,tasks=tasks)
        self.assertEqual(len(children),2)
        self.assertEqual(children[1][1].toa_snapshot.removed_equipments,())
        allocation=runner.single_os_allocation(tasks,"430",toa_removed=["SERIAL01"])
        self.assertEqual(allocation.target_os,"2663000001")
        self.assertEqual(allocation.other_os,("2663000002",))
        single_snapshot = replace(snapshot, task_os_numbers=("2663000001",),
            removed_equipments=snapshot.removed_equipments + (TOAEquipment(
                serial="SERIAL02",equipment_type="DECODER",direction=MovementDirection.OUTGOING),))
        single_job = replace(job,toa_snapshot=single_snapshot)
        single = runner._adm_child_jobs(single_job,tasks=tasks[:1])
        self.assertEqual({e.serial for e in single[0][1].toa_snapshot.removed_equipments},
                         {"SERIAL01","SERIAL02"})
