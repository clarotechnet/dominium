import unittest
from unittest.mock import patch

from scripts.configure_imperium_credentials import (
    DATASNAP_PATH,
    HTTP_PATH,
    configure,
)


class ConfigureImperiumCredentialsTests(unittest.TestCase):
    @patch("scripts.configure_imperium_credentials.save_credentials")
    def test_default_writes_both_channels(self, save) -> None:
        written = configure(" dalton ", "segredo")
        self.assertEqual(written, [DATASNAP_PATH, HTTP_PATH])
        self.assertEqual(save.call_count, 2)
        save.assert_any_call(DATASNAP_PATH, "dalton", "segredo")
        save.assert_any_call(HTTP_PATH, "dalton", "segredo")

    @patch("scripts.configure_imperium_credentials.save_credentials")
    def test_can_write_only_datasnap(self, save) -> None:
        written = configure("user", "pw", datasnap=True, http=False)
        self.assertEqual(written, [DATASNAP_PATH])
        save.assert_called_once_with(DATASNAP_PATH, "user", "pw")

    @patch("scripts.configure_imperium_credentials.save_credentials")
    def test_rejects_empty_credentials(self, save) -> None:
        with self.assertRaises(ValueError):
            configure("", "pw")
        with self.assertRaises(ValueError):
            configure("user", "")
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
