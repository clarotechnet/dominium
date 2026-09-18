import json
import unittest

from toa_inventory import parse_toa_clipboard, parse_toa_inventory


class TOAInventoryTests(unittest.TestCase):
    @staticmethod
    def response() -> str:
        inventory = {
            "equipment": {
                "invid": 10,
                "invtype": 6,
                "invsn": "ABC123456789",
                "quantity": 1,
                "invpool": "install",
                "inv_pid": 66627,
                "inv_aid": 194314352,
                "335": "38233746",
                "307": "1",
                "419": "1",
                "_identifier_structure": {
                    "invtype": {"text": "3 - EMTA"},
                    "419": {"text": "Nova Instalacao"},
                    "307": {"text": "Sala"},
                },
            },
            "material": {
                "invid": 11,
                "invtype": 106,
                "192": "22026223",
                "quantity": 38,
                "invpool": "install",
                "inv_pid": 66627,
                "inv_aid": 194314352,
                "335": "38233746",
                "419": "1",
                "_identifier_structure": {
                    "invtype": {"text": "HFC"},
                    "192": {"text": "22026223_CABO COAXIAL RG6 TRI C/M PT"},
                    "419": {"text": "Nova Instalacao"},
                },
            },
        }
        # The invalid escape outside Inventory reproduces the Postman response.
        return '{"Inventory":' + json.dumps(inventory) + ',"broken":"\\x"}'

    def test_parses_inventory_even_when_the_outer_json_is_invalid(self) -> None:
        result = parse_toa_inventory(self.response())

        self.assertEqual(len(result.equipment), 1)
        self.assertEqual(result.equipment[0].equipment_type, "emta")
        self.assertEqual(result.equipment[0].serial, "ABC123456789")
        self.assertEqual(result.equipment[0].point, "38233746")
        self.assertEqual(len(result.materials), 1)
        self.assertEqual(result.materials[0].code, "22026223")
        self.assertEqual(
            result.materials[0].description,
            "CABO COAXIAL RG6 TRI C/M PT",
        )
        self.assertEqual(result.materials[0].quantity, "38")
        self.assertEqual(result.materials[0].technician_id, 66627)
        self.assertEqual(result.materials[0].activity_id, 194314352)

    def test_rejects_missing_inventory(self) -> None:
        with self.assertRaisesRegex(ValueError, "Inventory"):
            parse_toa_inventory('{"Activity": {}}')

    def test_parses_copied_toa_table_and_keeps_points(self) -> None:
        source = """
496202570
1 - DECODER DIGITAL
241786846063
1
38220812
Sala
instalado
1
496192014
3 - EMTA
3453D2A98CFC
1
38220813
Sala
instalado
1
496192015
HFC
22026219_CABO COAXIAL RG6 TRI S/M BR
1
38220813
instalado
16
496199893
HFC
22056338_FITA PLASTICA DIELETRICA ROLO 15MTS
1
38220812
instalado
2
"""

        result = parse_toa_clipboard(source)

        self.assertEqual(len(result.equipment), 2)
        self.assertEqual(result.equipment[0].equipment_type, "decoder")
        self.assertEqual(result.equipment[0].point, "38220812")
        self.assertEqual(result.equipment[1].equipment_type, "emta")
        self.assertEqual(result.equipment[1].serial, "3453D2A98CFC")
        self.assertEqual(len(result.materials), 2)
        self.assertEqual(result.materials[0].code, "22026219")
        self.assertEqual(result.materials[0].quantity, "16")
        self.assertEqual(result.materials[0].point, "38220813")


if __name__ == "__main__":
    unittest.main()
