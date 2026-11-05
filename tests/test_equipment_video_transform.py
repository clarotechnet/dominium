"""Synthetic video-workbook transformation tests; no client data in Git."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations"/"serial_consult"))
from equipment_video_transform import (
    ATLAS_HEADERS, ASSINANTES_HEADERS, EXPECTED_TABS, IMPERIUM_HEADERS,
    NOMES_HEADERS, VideoSourceIncomplete, names_first_match, is_chip,
    imperium_video_sheets, assemble_six_verified_sheets,
)


class VideoWorkbookContractTests(unittest.TestCase):
    def test_vlookup_uses_first_serial_and_preserves_leading_zeros(self):
        source=[["SERIAL","NOME"],["00123","SUPERVISOR A"],
                ["00123","SUPERVISOR B"],["A9","OPERADOR B"]]
        self.assertEqual(names_first_match(source)["00123"],"SUPERVISOR A")

    def test_only_used_serials_in_nomes_go_to_expected_two_tabs(self):
        names=[["SERIAL","NOME"],["00123","TECNICO A"],
               ["chip-1","TECNICO B"],["never-used","TECNICO C"]]
        used=[
            {"SerialNumber":"00123","Grupo":"DECODER CARDLESS 4K",
             "Equipamento":"DECODER UHD","DataBaixa":"2026-10-28",
             "Contrato":"C1"},
            {"SerialNumber":"CHIP-1","Grupo":"SIM CARD MOVEL",
             "Equipamento":"SIM CARD","DataBaixa":"2026-10-28",
             "Contrato":"C2"},
            {"SerialNumber":"not-in-nomes","Grupo":"MODEM WIFI",
             "Equipamento":"MODEM","DataBaixa":"2026-10-28"},
            {"SerialNumber":"00123","Grupo":"DECODER CARDLESS 4K",
             "Equipamento":"DUPLICATE","DataBaixa":"2026-10-28"},
            {"SerialNumber":"","Grupo":"CABO COAXIAL","Equipamento":"CABLE"},
        ]
        imp,chip,names_tab,stats=imperium_video_sheets(used,names)
        self.assertEqual(imp,[list(IMPERIUM_HEADERS),["00123","DECODER UHD","2026-10-28","C1","TECNICO A"]])
        self.assertEqual(chip,[list(IMPERIUM_HEADERS),["CHIP-1","SIM CARD","2026-10-28","C2","TECNICO B"]])
        self.assertEqual(stats["source_used_serials"],3)
        self.assertEqual(stats["matched_used_serials"],2)
        self.assertEqual(stats["unmatched_used_serials"],1)
        self.assertFalse(stats["complete_six_tab_analysis"])
        self.assertEqual(len(names_tab),4)

    def test_smart_cards_not_decoders_are_chips(self):
        self.assertTrue(is_chip("SIM CARD"))
        self.assertTrue(is_chip("SMART CARD MOVEL"))
        self.assertTrue(is_chip("CHIP"))
        self.assertFalse(is_chip("DECODER CARDLESS"))
        self.assertFalse(is_chip("MODEM VOIP"))

    def test_no_names_does_not_claim_empty_success(self):
        with self.assertRaises(VideoSourceIncomplete):
            imperium_video_sheets([{"SerialNumber":"X"}], [])

    def test_no_six_tab_claim_without_independent_sources(self):
        with self.assertRaises(VideoSourceIncomplete):
            assemble_six_verified_sheets(
                atlas_rows=None,chips_atlas_rows=None,
                imperium_rows=[list(IMPERIUM_HEADERS)],
                chip_imperium_rows=[list(IMPERIUM_HEADERS)],
                assinantes_rows=None,nomes_rows=[list(NOMES_HEADERS)],
            )

    def test_six_source_assembly_requires_verified_physical_stock(self):
        args=dict(
            atlas_rows=[list(ATLAS_HEADERS)],
            chips_atlas_rows=[list(ATLAS_HEADERS)],
            imperium_rows=[list(IMPERIUM_HEADERS)],
            chip_imperium_rows=[list(IMPERIUM_HEADERS)],
            assinantes_rows=[list(ASSINANTES_HEADERS),["X","01","MODEL","date","C","P",""]],
            nomes_rows=[list(NOMES_HEADERS)]
        )
        with self.assertRaises(VideoSourceIncomplete):
            assemble_six_verified_sheets(**args)
        args["assinantes_rows"][1][-1]="NÃO"
        result=assemble_six_verified_sheets(**args)
        self.assertEqual(tuple(name for name,_ in result),EXPECTED_TABS)
        self.assertEqual(result[4][1][1][-1],"NÃO")


if __name__=="__main__":
    unittest.main()
