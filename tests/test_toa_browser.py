import unittest

from selenium.common.exceptions import NoSuchElementException

from toa_browser import authenticated


class _Element:
    def __init__(self, *, text="", displayed=True):
        self.text = text
        self._displayed = displayed

    def is_displayed(self):
        return self._displayed


class _Driver:
    def __init__(self, url, body, *, login=False):
        self.current_url = url
        self.body = body
        self.login = login

    def find_element(self, by, value):
        if value == "sign-in" or value == "username":
            if self.login:
                return _Element()
            raise NoSuchElementException()
        if value == "body":
            return _Element(text=self.body)
        raise NoSuchElementException()


class TOABrowserAuthenticationTests(unittest.TestCase):
    def test_activity_details_page_is_authenticated(self):
        driver = _Driver(
            "https://clarobrasil.etadirect.com/?m=activity",
            "Detalhes da atividade\nEquipamento\nHistorico",
        )
        self.assertTrue(authenticated(driver))

    def test_allocation_console_is_authenticated(self):
        driver = _Driver(
            "https://clarobrasil.etadirect.com/toa/",
            "Console de Alocacao\nRecursos",
        )
        self.assertTrue(authenticated(driver))

    def test_login_page_is_not_authenticated(self):
        driver = _Driver(
            "https://cap.claro.com.br/loginapp2fa/",
            "Login de usuario",
            login=True,
        )
        self.assertFalse(authenticated(driver))

    def test_untrusted_host_is_not_authenticated(self):
        driver = _Driver("https://example.com/", "Detalhes da atividade")
        self.assertFalse(authenticated(driver))


if __name__ == "__main__":
    unittest.main()
