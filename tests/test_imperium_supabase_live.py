"""No Excel intermediary: DataSnap -> normalized records -> private Supabase batches."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"))
from imperium_supabase_live import (
    ALLOWED_PROFILES,BATCHES,CHUNK_ROWS,RUNS,LiveSyncError,
    ImperiumLiveSyncService,SupabasePeriodStore,route_for,prepare_snapshot,
)

DATA={
    "consolidado":[{"Grupo":"SIM CARD","CodigoEquipamento":"410002","Equipamento":"SIM","Qtd":"1","Identificado":"S"}],
    "por_os":[
        {"Cidade":"MOSSORO","SerialNumber":"000111","Grupo":"SIM CARD MOVEL","Equipamento":"SIM CARD",
         "NumeroWO":"00123","NumOs":"11","DataBaixa":"2026-11-03T10:00:00","Qtd":"1"},
        {"Cidade":"MOSSORO","SerialNumber":"000222","Grupo":"GPON 6","Equipamento":"TERMINAL GPON",
         "NumeroWO":"00124","NumOs":"12","DataBaixa":"2026-11-03T11:00:00","Qtd":"1"},
        {"Cidade":"MOSSORO","SerialNumber":"","Grupo":"CABO COAXIAL","Equipamento":"CABLE",
         "NumeroWO":"00125","NumOs":"13","Qtd":"3"},
    ]
}
URL="/api/stock/analyses/imperium/live"
BODY={"city":"mossoro","start":"2026-11-03","end":"2026-11-03"}
ACTOR="user-9"


class FakeRest:
    def __init__(self):
        self.runs={}
        self.batches={}
        self.fail_batch=False
        self.actions=[]
        self.schema_ready=True
    @staticmethod
    def compare(row,query):
        for name,test in (query or {}).items():
            if not test.startswith("eq."):continue
            actual=str(row.get(name))
            if actual!=test[3:]:return False
        return True
    def __call__(self,table,method,query,body):
        self.actions.append((table,method))
        if not self.schema_ready:raise LiveSyncError(503,"supabase_migration_missing","Tabelas ausentes")
        if table==RUNS:
            if method=="POST":
                row=dict(body)
                row.setdefault("criado_em","2026-11-05T20:00:00+00:00")
                self.runs[row["id"]]=row
                return [dict(row)]
            if method=="PATCH":
                matches=[r for r in self.runs.values() if self.compare(r,query)]
                for row in matches:row.update(body)
                return [dict(r) for r in matches]
            rows=[dict(r) for r in self.runs.values() if self.compare(r,query)]
        elif table==BATCHES:
            if method=="POST":
                if self.fail_batch:raise LiveSyncError(502,"test_error","Failed writing batch")
                row=dict(body)
                key=(row["consulta_id"],row["categoria"],row["indice_lote"])
                self.batches[key]=row
                return [row]
            rows=[dict(r) for r in self.batches.values() if self.compare(r,query)]
        else:raise AssertionError(table)
        if query and query.get("order"):
            rows.sort(key=lambda r:r.get(query["order"].split(".")[0],""),reverse=".desc" in query["order"])
        if query and "limit" in query:
            rows=rows[:int(query["limit"])]
        return rows


class SupabaseLiveTests(unittest.TestCase):
    def setUp(self):
        self.api=FakeRest()
        self.store=lambda:SupabasePeriodStore(requester=self.api)
        self.called=[]
        def fetch(start,end,*,profile,partner_id,credential_path):
            self.called.append((profile,partner_id,start,end))
            return copy.deepcopy(DATA)
        self.service=ImperiumLiveSyncService(fetcher=fetch,repository_factory=self.store)
    def sync(self,body=None):
        return self.service.handle("POST",URL,ACTOR,body or BODY)
    def test_protected_routes(self):
        self.assertEqual(route_for("POST",URL)[0],"sync")
        self.assertEqual(route_for("GET",URL+"?city=mossoro&start=2026-11-03&end=2026-11-03")[0],"history")
        self.assertEqual(route_for("GET",URL+"/550e8400-e29b-41d4-a716-446655440000/data?city=mossoro&category=seriais_tratados&page=1")[0],"preview")
        for url in (URL+"/bad/data?city=mossoro&category=por_os&page=1",
                    URL+"/550e8400-e29b-41d4-a716-446655440000/data?city=mossoro&category=forbidden&page=1",
                    URL+"?city=all&start=2026-11-03&end=2026-11-03"):
            self.assertIsNone(route_for("GET",url))
    def test_full_snapshots_are_saved_to_supabase_without_excel(self):
        status,result,_=self.sync()
        self.assertEqual(status,201,result)
        self.assertEqual(self.called,[("mossoro",1,"2026-11-03","2026-11-03")])
        self.assertEqual(result["selected"]["city"],"mossoro")
        self.assertFalse(result["selected"]["complete_six_tab_analysis"])
        counts=result["selected"]["counts"]
        self.assertEqual(counts["por_os"],3)
        self.assertEqual(counts["seriais_tratados"],2)
        self.assertEqual(counts["chips"],1)
        self.assertEqual(counts["equipamentos"],1)
        self.assertEqual(len(self.api.runs),1)
        self.assertEqual({row["estado"] for row in self.api.runs.values()},{"concluido"})
        self.assertEqual({key[1] for key in self.api.batches},
                         {"consolidado","por_os","seriais_tratados"})
        self.assertEqual(len(self.api.batches),3)
        code,hist,_=self.service.handle("GET",URL+"?city=mossoro&start=2026-11-03&end=2026-11-03",ACTOR)
        self.assertEqual(code,200,hist)
        self.assertEqual(len(hist["history"]),1)
        run=result["selected"]["id"]
        code,preview,_=self.service.handle("GET",
            URL+"/"+run+"/data?city=mossoro&category=seriais_tratados&page=1",ACTOR)
        self.assertEqual(code,200,preview)
        self.assertEqual(preview["total"],2)
        self.assertEqual({x["classificacao"] for x in preview["rows"]},{"chip","equipamento"})
        self.assertTrue(all(x["data_modelo_video_verificada"] is False for x in preview["rows"]))
    def test_idempotency_reuses_same_source_hash(self):
        first=self.sync()
        second=self.sync()
        self.assertEqual(first[0],201)
        self.assertEqual(second[0],200)
        self.assertTrue(second[1]["reused"])
        self.assertEqual(first[1]["selected"]["id"],second[1]["selected"]["id"])
        self.assertEqual(len(self.api.runs),1)
    def test_missing_schema_fails_before_datasnap_call(self):
        self.api.schema_ready=False
        code,res,_=self.sync()
        self.assertEqual(code,503)
        self.assertEqual(res["code"],"supabase_migration_missing")
        self.assertFalse(self.called)
    def test_failed_batch_never_returns_completed_snapshot(self):
        self.api.fail_batch=True
        code,res,_=self.sync()
        self.assertEqual(code,502)
        self.assertEqual(res["code"],"test_error")
        self.assertEqual(list(self.api.runs.values())[0]["estado"],"falhou")
        history=self.service.handle("GET",URL+"?city=mossoro&start=2026-11-03&end=2026-11-03",ACTOR)[1]
        self.assertEqual(history["history"],[])
    def test_wrong_city_does_not_persist(self):
        wrong=copy.deepcopy(DATA)
        wrong["por_os"][0]["Cidade"]="NATAL"
        with self.assertRaises(LiveSyncError) as raised:
            prepare_snapshot(wrong,"mossoro")
        self.assertEqual(raised.exception.code,"city_mismatch")
        self.assertFalse(self.api.runs)
    def test_does_not_use_fortaleza_or_all(self):
        for city in ("fortaleza","all"):
            code,payload,_=self.sync({**BODY,"city":city})
            self.assertEqual(code,409)
            self.assertEqual(payload["code"],"city_not_homologated")
        self.assertFalse(self.called)
    def test_independent_snapshot_batch_sizes(self):
        many=copy.deepcopy(DATA)
        many["por_os"]=many["por_os"]*110
        structured,count,digest=prepare_snapshot(many,"mossoro")
        res=self.store().store("mossoro","2026-11-03","2026-11-03",ACTOR,structured,count,digest)
        self.assertTrue(res["ok"])
        groups={k[1] for k in self.api.batches}
        self.assertEqual(groups,{"consolidado","por_os","seriais_tratados"})
        self.assertEqual(sum(r["quantidade"] for r in self.api.batches.values() if r["categoria"]=="por_os"),330)
        self.assertTrue(all(r["quantidade"]<=CHUNK_ROWS for r in self.api.batches.values()))
    def test_actor_rejected_and_period_not_reversed(self):
        self.assertEqual(self.service.handle("POST",URL,"bad",BODY)[0],403)
        code,payload,_=self.sync({**BODY,"start":"2026-11-04","end":"2026-11-03"})
        self.assertEqual(code,400)
        self.assertFalse(self.called)


if __name__=="__main__":
    unittest.main()
