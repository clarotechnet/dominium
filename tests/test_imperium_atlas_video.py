"""Synthetic tests for resumable Atlas x Imperium video workflow."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"))
from tests.test_imperium_serial_treatment import Repo, SOURCE, ID
from imperium_atlas_video import AtlasVideoService, ROOT, route_for


class AtlasStub:
    def __init__(self):
        self.queued=[]
        self.polled=[]
        self.online=True
        self.polls=0
        self.raise_submit=False
        self.raise_poll=False
    @staticmethod
    def valid_serial(serial):
        return len(serial)==12 and serial.isalnum()
    def status(self):
        return {"ok":True,"online":self.online}
    def enqueue(self,serial):
        self.queued.append(serial)
        if self.raise_submit:raise OSError("submission may have succeeded")
        return "queue_123456"
    def poll_result(self,request_id,serial):
        self.polled.append((request_id,serial))
        if self.raise_poll:raise TimeoutError("unconfirmed")
        self.polls+=1
        if self.polls==1:return None
        return {"ok":True,"resultado":{
            "serial_consultado":serial,"serial_encontrado":True,
            "estado":"INICIALIZADO","operacao":"NATAL",
            "tipo_localizacao":"ASSINANTE","localizacao":"ASSINANTE",
            "data_alteracao":"2026-11-05T14:30:00",
            "numero_contrato":"1234","partial":False,
        }}


class AtlasVideoTests(unittest.TestCase):
    def setUp(self):
        self.db=Repo()
        self.bridge=AtlasStub()
        for row in SOURCE:
            self.db.records[row["serial"]]={
                "consulta_id":ID,"serial":row["serial"],"situacao":"historico_verificado",
                "evidencia":{"history_verified":True,"movement_count":2},
                "tentativas":1,"tratado_em":"2026-11-06T12:00:00Z","tratado_por":"user-101",
            }
        self.s=AtlasVideoService(
            repository_factory=lambda:self.db,
            bridge_factory=lambda:self.bridge,
        )
    def call(self,method,path,body=None,actor="user-101"):
        return self.s.handle(method,path,actor,body)
    def status(self):
        return self.call("GET",ROOT+"/status?city=natal&run="+ID)
    def next(self,city="natal"):
        return self.call("POST",ROOT+"/next",{"city":city,"run":ID})

    def test_routes_reject_injection_and_other_methods(self):
        self.assertEqual(route_for("POST",ROOT+"/next")[0],"next")
        self.assertEqual(route_for("GET",ROOT+"/status?city=natal&run="+ID)[0],"status")
        self.assertIsNone(route_for("POST",ROOT+"/next?run="+ID))
        self.assertIsNone(route_for("GET",ROOT+"/status?city=all&run="+ID))
        self.assertIsNone(route_for("GET",ROOT+"/status?city=natal&run="+ID+"&debug=1"))
        self.assertIsNone(route_for("DELETE",ROOT+"/next"))

    def test_real_atlas_identification_is_a_separate_third_stage(self):
        code,initial,_=self.status()
        self.assertEqual(code,200,initial)
        self.assertEqual(initial["counts"]["total"],4)
        self.assertEqual(initial["counts"]["tratados_imperium"],4)
        self.assertEqual(initial["counts"]["atlas_aguardando"],4)
        self.assertFalse(initial["analise_video_seis_abas_completa"])
        self.assertEqual(self.bridge.queued,[])
        code,queued,_=self.next()
        self.assertEqual(code,200,queued)
        self.assertEqual(queued["counts"]["atlas_fila"],1)
        self.assertEqual(len(self.bridge.queued),1)
        self.assertEqual(self.db.records[SOURCE[0]["serial"]]["evidencia"]["atlas_video"]["status"],"queued")
        code,pending,_=self.next()
        self.assertEqual(code,200,pending)
        self.assertEqual(pending["updated"]["situacao"],"aguardando_atlas")
        self.assertEqual(len(self.bridge.queued),1,"pending queue must never be submitted twice")
        code,ready,_=self.next()
        self.assertEqual(code,200,ready)
        self.assertEqual(ready["counts"]["atlas_verificados"],1)
        self.assertEqual(ready["rows"][0]["estado_atlas"],"INICIALIZADO")
        self.assertFalse(ready["rows"][0]["localizacao_atual_comprovada"])
        self.assertEqual(len(self.bridge.queued),1)

    def test_bridge_must_return_the_exact_requested_serial(self):
        self.next()
        def wrong_reply(request_id,serial):
            return {"ok":True,"serial":serial,"resultado":{
                "serial_consultado":"DIFFERENT001",
                "serial_encontrado":True,"estado":"INICIALIZADO",
            }}
        self.bridge.poll_result=wrong_reply
        code,payload,_=self.next()
        self.assertEqual(code,502,payload)
        self.assertEqual(payload["code"],"atlas_serial_mismatch")
        self.assertEqual(self.db.records[SOURCE[0]["serial"]]
                         ["evidencia"]["atlas_video"]["status"],"queued")

    def test_unsupported_serial_is_flagged_never_faked_as_not_found(self):
        # Complete first two 12-char records and leave the 20-digit ICCID next.
        for row in SOURCE[:2]:
            self.db.records[row["serial"]]["evidencia"]["atlas_video"]={"status":"verificado"}
        self.db.records[SOURCE[3]["serial"]]["evidencia"]["atlas_video"]={"status":"verificado"}
        code,result,_=self.next()
        self.assertEqual(code,200,result)
        self.assertEqual(result["counts"]["atlas_formatos_pendentes"],1)
        self.assertEqual(result["updated"]["situacao"],"formato_nao_suportado")
        self.assertFalse(self.bridge.queued)

    def test_offline_bridge_never_enqueues_or_saves_uncertain(self):
        self.bridge.online=False
        code,result,_=self.next()
        self.assertEqual(code,503)
        self.assertEqual(result["code"],"atlas_offline")
        self.assertEqual(self.bridge.queued,[])
        self.assertNotIn("atlas_video",self.db.records[SOURCE[0]["serial"]]["evidencia"])

    def test_unknown_submit_cannot_auto_retry(self):
        self.bridge.raise_submit=True
        code,result,_=self.next()
        self.assertEqual(code,503)
        self.assertEqual(result["code"],"atlas_submission_uncertain")
        self.assertEqual(len(self.bridge.queued),1)
        self.assertEqual(self.db.records[SOURCE[0]["serial"]]["evidencia"]["atlas_video"]["status"],"submitting")
        self.bridge.raise_submit=False
        code,result,_=self.next()
        self.assertEqual(code,200)
        self.assertEqual(len(self.bridge.queued),2)
        self.assertNotEqual(self.bridge.queued[0],self.bridge.queued[1],
          "uncertain serial must not be resubmitted")

    def test_poll_error_retains_id_for_resume(self):
        code,result,_=self.next()
        self.assertEqual(code,200)
        self.bridge.raise_poll=True
        code,result,_=self.next()
        self.assertEqual(code,503)
        self.assertEqual(result["code"],"atlas_queue_pending")
        self.assertEqual(self.db.records[SOURCE[0]["serial"]]["evidencia"]["atlas_video"]["status"],"queued")
        self.assertEqual(len(self.bridge.queued),1)

    def test_other_city_blocks_before_queueing(self):
        code,data,_=self.next("mossoro")
        self.assertEqual(code,409)
        self.assertEqual(data["code"],"atlas_city_unverified")
        self.assertFalse(self.bridge.queued)

    def test_login_required(self):
        code,_,_=self.call("GET",ROOT+"/status?city=natal&run="+ID,actor="")
        self.assertEqual(code,403)

    def test_only_treated_serials_are_submitted(self):
        self.db.records.pop(SOURCE[0]["serial"])
        code,result,_=self.next()
        self.assertEqual(code,200)
        self.assertEqual(self.bridge.queued,[SOURCE[1]["serial"]])
        self.assertEqual(result["counts"]["aguardando_tratativa_imperium"],1)


if __name__=="__main__":unittest.main()
