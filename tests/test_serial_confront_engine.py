"""Synthetic contract tests for the read-only reconciliation engine."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "serial_consult"))
from confront_engine import classify_pair, normalize_serials, run_confront
from confront_export import confront_csv


def imperium(serial, *, owner=None, contract=None):
    response = {
        "serial": serial,
        "datasnap": {"verified": True, "count": 2, "movements": []},
        "last_destination": {"stock_name": "Tecnico antigo"},
        "live": {"found": True, "verified": True, "owner": {"technician_name": "Operador Atual"}},
    }
    if owner:
        response.update(current_owner_verified=True, current_owner_id=owner)
    if contract:
        response.update(current_contract_verified=True, current_contract=contract)
    return response


def atlas(serial, *, owner=None, contract=None):
    response = {
        "ok": True, "serial_consultado": serial, "serial_encontrado": True,
        "estado": "INICIALIZADO", "localizacao": "Empreiteira",
        "numero_contrato": "1111111", "partial": False,
    }
    if owner:
        response.update(current_owner_verified=True, current_owner_id=owner)
    if contract:
        response.update(current_contract_verified=True, current_contract=contract)
    return response


class ConfrontEngineTests(unittest.TestCase):
    def test_normalize_and_deduplicate(self):
        self.assertEqual(normalize_serials("ab1234567890,AB1234567890\nCD1234567890"),
                         ["AB1234567890", "CD1234567890"])
        with self.assertRaises(ValueError):
            normalize_serials("")
        with self.assertRaises(ValueError):
            normalize_serials("abc ; valid1234")

    def test_limit_checked_before_any_query(self):
        called = []
        with self.assertRaises(ValueError):
            run_confront([f"SERIAL{i:06d}" for i in range(501)], profile="natal",
                         mode="analitico", imperium_query=lambda payload: called.append(payload))
        self.assertEqual(called, [])

    def test_unverified_historical_mismatch_is_not_a_divergence(self):
        pair = classify_pair("AABBCCDDEEFF", imperium("AABBCCDDEEFF"), atlas("AABBCCDDEEFF"))
        self.assertEqual(pair["situacao"], "inconclusivo")
        self.assertIn("sem_campos_atuais_equivalentes_confirmados", pair["motivos"])

    def test_realistic_history_and_atlas_labels_do_not_invent_current_owner(self):
        source = imperium("AABBCCDDEEFF")
        source["live"] = {"verified": False, "found": False}
        source["last_destination"] = {
            "stock_name": None, "movement": "SAÍDA", "date": "2026-10-22",
            "source": "last_imperium_movement_unverified"}
        asset = atlas("AABBCCDDEEFF")
        asset.update({"tipo_localizacao": "ASSINANTE", "operacao": "NATAL"})
        pair = classify_pair("AABBCCDDEEFF", source, asset)
        self.assertEqual(pair["situacao"], "inconclusivo")
        self.assertEqual(pair["imperium"]["ultima_movimentacao_historica"], "SAÍDA")
        self.assertEqual(pair["atlas"]["tipo_localizacao"], "ASSINANTE")
        self.assertFalse(pair["imperium"]["posse_atual_confirmada"])
        csv_text = confront_csv({"resultados": [pair]})
        self.assertIn("Ultima movimentacao Imperium", csv_text)
        self.assertIn("SAÍDA", csv_text)
        self.assertIn("ASSINANTE", csv_text)

    def test_verified_current_contract_difference_is_divergence(self):
        pair = classify_pair("AABBCCDDEEFF", imperium("AABBCCDDEEFF", contract="123456"),
                             atlas("AABBCCDDEEFF", contract="654321"))
        self.assertEqual(pair["situacao"], "divergente")
        self.assertEqual(pair["evidencias"], [{"campo": "contrato_atual_confirmado", "coincide": False}])

    def test_verified_current_owner_match_is_convergence(self):
        pair = classify_pair("AABBCCDDEEFF", imperium("AABBCCDDEEFF", owner="STOCK-22"),
                             atlas("AABBCCDDEEFF", owner="stock-22"))
        self.assertEqual(pair["situacao"], "convergente")

    def test_partial_atlas_result_never_declares_convergence(self):
        broken = atlas("AABBCCDDEEFF", owner="TECH-42")
        broken["partial"] = True
        pair = classify_pair("AABBCCDDEEFF", imperium("AABBCCDDEEFF", owner="TECH-42"), broken)
        self.assertEqual(pair["situacao"], "inconclusivo")
        self.assertIn("atlas_historico_parcial", pair["motivos"])

    def test_no_atlas_connector_is_explicitly_inconclusive(self):
        calls = []
        def imp(request):
            calls.append(request)
            serials, mode, profile = request
            return {"ok": True, "results": [imperium(s) for s in serials]}
        result = run_confront(["AABBCCDDEEFF", "FFEEDDCCBBAA"], profile="natal",
                              mode="sintetico", imperium_query=imp)
        self.assertEqual(result["resumo"]["inconclusivo"], 2)
        self.assertFalse(result["atlas_integrado"])
        self.assertEqual(len(calls), 1)

    def test_bounded_batches_and_exact_single_atlas_query_per_serial(self):
        calls = []
        consulted = []
        serials = [f"SN{i:010d}" for i in range(45)]
        def imp(payload):
            values, mode, profile = payload
            calls.append(list(values))
            return {"ok": True, "results": [imperium(s, owner="X") for s in values]}
        def at(serial):
            consulted.append(serial)
            return atlas(serial, owner="X")
        result = run_confront(serials, profile="recife", mode="analitico",
                              imperium_query=imp, atlas_query=at)
        self.assertEqual([len(x) for x in calls], [20, 20, 5])
        self.assertEqual(consulted, serials)
        self.assertEqual(result["resumo"]["convergente"], 45)

    def test_one_atlas_timeout_does_not_abort_batch(self):
        def imp(payload):
            return {"ok": True, "results": [imperium(s) for s in payload[0]]}
        def at(serial):
            if serial == "AABBCCDDEEFF":
                raise TimeoutError("Timeout")
            return atlas(serial)
        result = run_confront(["AABBCCDDEEFF", "FFEEDDCCBBAA"], profile="mossoro",
                              mode="analitico", imperium_query=imp, atlas_query=at)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["resultados"][0]["situacao"], "inconclusivo")
        self.assertTrue(result["resultados"][1]["atlas"])

    def test_unauthorized_profile_rejected_before_queries(self):
        with self.assertRaises(ValueError):
            run_confront("AABBCCDDEEFF", profile="outra", mode="analitico",
                         imperium_query=lambda _: self.fail("query should not run"))

    def test_atlas_explicit_fail_inconclusive(self):
        pair = classify_pair("AABBCCDDEEFF", imperium("AABBCCDDEEFF"),
                             {"ok": False, "error": "sessao_expirada"})
        self.assertEqual(pair["situacao"], "inconclusivo")
        self.assertIn("atlas_consulta_falhou", pair["motivos"])

    def test_atlas_suspeito_is_review_not_fraud_or_proven_divergence(self):
        record = atlas("AABBCCDDEEFF")
        record["estado"] = "SUSPEITO"
        pair = classify_pair("AABBCCDDEEFF", imperium("AABBCCDDEEFF"), record)
        self.assertEqual(pair["situacao"], "revisao")
        self.assertIn("atlas_sinaliza_suspeito_exige_analise_humana", pair["alertas"])

    def test_historical_contract_conflict_requires_review_not_conviction(self):
        stock = imperium("AABBCCDDEEFF")
        stock["datasnap"]["movements"] = [
            {"Id": 2, "Contrato": "987654"},
            {"Id": 1, "Contrato": "1111111"},
        ]
        pair = classify_pair("AABBCCDDEEFF", stock, atlas("AABBCCDDEEFF"))
        self.assertEqual(pair["situacao"], "revisao")
        self.assertIn("contratos_historicos_diferentes_revisar_datas", pair["alertas"])

    def test_csv_export_blocks_formula_injection(self):
        pair = classify_pair("AABBCCDDEEFF", imperium("AABBCCDDEEFF"), atlas("AABBCCDDEEFF"))
        pair["atlas"]["localizacao"] = "=HYPERLINK(1)"
        text = confront_csv({"resultados": [pair]})
        self.assertTrue(text.startswith("\ufeffSerial;"))
        self.assertIn("'=HYPERLINK(1)", text)
        self.assertIn("AABBCCDDEEFF", text)

    def test_csv_rejects_invalid_records(self):
        with self.assertRaises(ValueError):
            confront_csv({"resultados": [None]})


if __name__ == "__main__":
    unittest.main()
