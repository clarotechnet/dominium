"""No personal records; deterministic two-stage Imperium treatment tests."""
import io,sys,unittest
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"))
from imperium_supabase_live import RUNS,BATCHES,LiveSyncError
from imperium_serial_treatment import TREATMENTS,ROOT,SerialTreatmentService,route_for

ID="550e8400-e29b-41d4-a716-446655440000"
SERIALS=["000000000001","000000000002","89899912345678901234","000000000003"]
SOURCE=[{"serial":s,"equipamento":"SIM CARD" if len(s)==20 else "GPON",
        "grupo":"SIM CARD MOVEL" if len(s)==20 else "GPON 6",
        "numero_wo":"0001|123","contrato":"1234"} for s in SERIALS]

class Repo:
    def __init__(self):
        self.schema=True
        self.source={"id":ID,"cidade":"natal","estado":"concluido","total_seriais":len(SOURCE),
            "data_inicio":"2026-11-05","data_fim":"2026-11-05","criado_em":"2026-11-06T10:00:00Z"}
        self.batches=[{"consulta_id":ID,"categoria":"seriais_tratados",
                       "indice_lote":0,"quantidade":len(SOURCE),"registros":deepcopy(SOURCE)}]
        self.records={}
        self.fail_write=False
    def ensure_ready(self):
        if not self.schema:raise LiveSyncError(503,"missing_schema","Missing database schema")
    def call(self,table,method="GET",*,query=None,body=None,upsert=False):
        self.ensure_ready()
        if table==RUNS:
            return [deepcopy(self.source)] if self.matches(self.source,query) else []
        if table==BATCHES:
            return [deepcopy(x) for x in self.batches if self.matches(x,query)]
        if table==TREATMENTS:
            if method=="POST":
                if self.fail_write:raise LiveSyncError(502,"test_write_error","Not saved")
                self.records[body["serial"]]=deepcopy(body)
                return [deepcopy(body)]
            if method=="PATCH":
                if self.fail_write:raise LiveSyncError(502,"test_write_error","Not saved")
                selected=[v for v in self.records.values() if self.matches(v,query)]
                for item in selected:item.update(deepcopy(body))
                return [deepcopy(v) for v in selected]
            return [deepcopy(v) for v in self.records.values() if self.matches(v,query)]
        raise AssertionError(table)
    @staticmethod
    def matches(data,query):
        return all(str(data.get(k))==v[3:] for k,v in (query or {}).items()
                   if isinstance(v,str) and v.startswith("eq."))

def verified(group):
    items,mode,city=group
    assert city=="natal" and mode=="analitico"
    return {"ok":True,"results":[{"serial":items[0],
        "datasnap":{"verified":True,"movements":[{"Id":3,"Movimento":"BAIXA","Contrato":"1234"}]},
        "last_destination":{"movement":"BAIXA","date":"2026-11-05","stock_name":"HISTORICO"},
        "live":{"verified":False,"found":False}}]}

class SerialTreatmentTests(unittest.TestCase):
    def setUp(self):
        self.repo=Repo()
        self.calls=[]
        def consult(group):
            self.calls.append(group)
            return verified(group)
        self.s=SerialTreatmentService(repository_factory=lambda:self.repo,consult=consult)
    def call(self,method,route,body=None):
        return self.s.handle(method,route,"user-101",body)
    def step(self,**extra):
        return self.call("POST",ROOT+"/next",{"city":"natal","run":ID,**extra})

    def test_route_guards(self):
        self.assertEqual(route_for("POST",ROOT+"/next")[0],"next")
        self.assertEqual(route_for("GET",ROOT+"/status?city=natal&run="+ID)[0],"status")
        self.assertIsNone(route_for("GET",ROOT+"/status?city=all&run="+ID))
        self.assertIsNone(route_for("POST",ROOT+"/next?bad=1"))

    def test_stage_one_has_only_pending_serials(self):
        status,out,_=self.call("GET",ROOT+"/status?city=natal&run="+ID)
        self.assertEqual(status,200,out)
        self.assertEqual(out["counts"]["total"],4)
        self.assertEqual(out["counts"]["processados"],0)
        self.assertFalse(out["download_enabled"])
        self.assertTrue(all(r["situacao"]=="aguardando" for r in out["rows"]))
        self.assertEqual(self.calls,[])

    def test_stage_two_progress_and_resume(self):
        for index in range(4):
            code,res,_=self.step()
            self.assertEqual(code,200,res)
            self.assertEqual(res["counts"]["processados"],index+1)
        self.assertEqual(len(self.calls),3)
        self.assertEqual(self.repo.records[SERIALS[2]]["situacao"],"formato_nao_suportado")
        self.assertEqual(res["status"],"concluido_com_pendencias")
        self.assertTrue(res["download_enabled"])
        self.assertFalse(res["six_tab_analysis_complete"])
        self.assertEqual(self.step()[1].get("updated"),None)
        self.assertEqual(len(self.calls),3)
        s=SerialTreatmentService(repository_factory=lambda:self.repo,consult=verified)
        self.assertEqual(s.handle("GET",ROOT+"/status?city=natal&run="+ID,"user-101")[1]["counts"]["processados"],4)

    def test_retry_error_and_preserve_evidence(self):
        self.s.consult=lambda _: (_ for _ in ()).throw(TimeoutError("network"))
        code,res,_=self.step()
        self.assertEqual(code,200)
        self.assertEqual(res["rows"][0]["situacao"],"erro_consulta")
        self.assertNotIn("not found",str(res["rows"][0]).lower())
        self.s.consult=verified
        for _ in range(3):self.step()
        code,res,_=self.step(retry_errors=True)
        self.assertEqual(code,200,res)
        self.assertEqual(self.repo.records[SERIALS[0]]["tentativas"],2)
        self.assertEqual(self.repo.records[SERIALS[0]]["situacao"],"historico_verificado")

    def test_no_mossoro_without_individual_protocol_validation(self):
        code,res,_=self.call("POST",ROOT+"/next",{"city":"mossoro","run":ID})
        self.assertEqual(code,409,res)
        self.assertFalse(self.calls)

    def test_incomplete_source_cannot_be_treated(self):
        self.repo.source["estado"]="processando"
        code,res,_=self.step()
        self.assertEqual(code,404,res)
        self.assertFalse(self.calls)

    def test_broken_record_count_never_processed(self):
        self.repo.source["total_seriais"]=len(SERIALS)+1
        code,res,_=self.step()
        self.assertEqual(code,502,res)
        self.assertFalse(self.calls)

    def test_database_failure_is_not_reported_as_progress(self):
        self.repo.fail_write=True
        code,res,_=self.step()
        self.assertEqual(code,502,res)
        self.assertEqual(self.repo.records,{})

    def test_download_only_after_all_processed(self):
        code,reply,_=self.call("GET",ROOT+"/export?city=natal&run="+ID)
        self.assertEqual(code,409,reply)
        for _ in SERIALS:self.step()
        self.repo.records[SERIALS[0]]["evidencia"]["atlas_video"]={
            "status":"verificado",
            "estado":"INICIALIZADO",
            "tipo_localizacao":"ASSINANTE",
            "localizacao":"LOCAL CONFIRMADO",
            "data_alteracao":"2026-11-05T10:30:00",
            "numero_contrato":"1234",
            "observacao":"Consulta verificada; posse física não confirmada",
        }
        code,payload,mime=self.call("GET",ROOT+"/export?city=natal&run="+ID)
        self.assertEqual(code,200)
        self.assertTrue(payload.startswith(b"PK\x03\x04"))
        self.assertIn("spreadsheetml.sheet",mime)
        with ZipFile(io.BytesIO(payload)) as z:
            book=z.read("xl/workbook.xml")
            self.assertIn(b"Seriais Tratados",book)
            self.assertIn(b"Pendencias",book)
            self.assertIn(b"Conferencia Atlas",book)
            self.assertIn(b"Pendencias Atlas",book)
            text="".join(z.read(name).decode("utf-8",errors="replace")
                         for name in z.namelist() if name.startswith("xl/worksheets/"))
            self.assertIn("INICIALIZADO",text)
            self.assertIn("NÃO VERIFICADO",text)
            self.assertIn("aguardando",text)

if __name__=="__main__":unittest.main()
