import io
import json
import socket
import unittest
import urllib.error
from unittest.mock import Mock

from imperium_http_api import (
    CLOSE_PATH,
    LOGIN_PATH,
    ImperiumHTTPClient,
    ImperiumHTTPError,
    ImperiumHTTPUncertainError,
    ImperiumHTTPValidationError,
    build_close_payload,
    validate_close_payload,
)


class FakeResponse:
    def __init__(self, status: int, payload, headers=None) -> None:
        self.status = status
        self.headers = headers or {}
        self._raw = json.dumps(payload).encode("utf-8") if payload is not None else b""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._raw if size < 0 else self._raw[:size]


def sample_payload() -> dict:
    return build_close_payload(
        number="2646000001",
        scheduled_date="2026-07-20",
        technician_code="z123456",
        close_code="409",
        installed_serials=[{"serialnumber": "ABC123"}],
        installed_materials=[
            {"codigoequipamento": "22026189", "qtd": "2"},
            {"codigoequipamento": "22026189", "qtd": "3"},
            {"codigoequipamento": "22026219", "qtd": "1.5"},
        ],
        removed_serials=[
            {"codigoequipamento": "41001234", "serialnumber": "987654"}
        ],
    )


class PayloadTests(unittest.TestCase):
    def test_builds_and_aggregates_materials(self) -> None:
        order = sample_payload()["ordemservico"]
        self.assertEqual(order["codigotecnico"], "Z123456")
        self.assertEqual(order["codigobaixa"], 409)
        self.assertEqual(
            order["instaladosmiscelaneas"],
            [
                {"codigoequipamento": "22026189", "qtd": "5"},
                {"codigoequipamento": "22026219", "qtd": "1.5"},
            ],
        )

    def test_rejects_invalid_date(self) -> None:
        payload = sample_payload()
        payload["ordemservico"]["dataagendamento"] = "20/07/2026"
        with self.assertRaisesRegex(ImperiumHTTPValidationError, "YYYY-MM-DD"):
            validate_close_payload(payload)

    def test_rejects_duplicate_serial(self) -> None:
        payload = sample_payload()
        payload["ordemservico"]["instaladosserializados"].append(
            {"serialnumber": "ABC123"}
        )
        with self.assertRaisesRegex(ImperiumHTTPValidationError, "duplicado"):
            validate_close_payload(payload)

    def test_rejects_same_installed_and_removed_serial(self) -> None:
        payload = sample_payload()
        payload["ordemservico"]["removidosserializados"][0]["serialnumber"] = "ABC123"
        with self.assertRaisesRegex(ImperiumHTTPValidationError, "instalado e removido"):
            validate_close_payload(payload)

    def test_rejects_non_positive_quantity(self) -> None:
        payload = sample_payload()
        payload["ordemservico"]["instaladosmiscelaneas"][0]["qtd"] = "0"
        with self.assertRaisesRegex(ImperiumHTTPValidationError, "positiva"):
            validate_close_payload(payload)


class ClientTests(unittest.TestCase):
    def test_login_and_write_use_exact_contract(self) -> None:
        calls = []

        def opener(request, timeout):
            calls.append((request, timeout))
            if request.full_url.endswith(LOGIN_PATH):
                return FakeResponse(200, {"token": "header.payload.signature"})
            return FakeResponse(200, {"mensagem": "recebido"})

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        result = client.close_order(sample_payload())

        self.assertTrue(result.accepted)
        self.assertTrue(result.requires_confirmation)
        self.assertEqual(len(calls), 2)
        login_request = calls[0][0]
        close_request = calls[1][0]
        self.assertTrue(login_request.full_url.endswith(LOGIN_PATH))
        self.assertEqual(
            json.loads(login_request.data),
            {"jwtusername": "USER", "jwtpassword": "PASSWORD"},
        )
        self.assertEqual(login_request.get_header("Cache-control"), "no-store")
        self.assertEqual(len(login_request.get_header("X-request-id")), 32)
        self.assertTrue(close_request.full_url.endswith(CLOSE_PATH))
        self.assertEqual(close_request.get_header("Authorization"), "Bearer header.payload.signature")
        self.assertEqual(json.loads(close_request.data), sample_payload())

    def test_login_captures_jader_identity_headers(self) -> None:
        def opener(request, timeout):
            return FakeResponse(
                200,
                {"token": "header.payload.signature"},
                {
                    "Id-Usuario": "10",
                    "Id-Estoque": "77",
                    "Grupo-Usuario": "INSTALADOR",
                    "Usuario": "ALAN",
                },
            )

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        self.assertEqual(
            client.login_metadata(),
            {
                "user_id": 10,
                "stock_id": 77,
                "group": "INSTALADOR",
                "username": "ALAN",
            },
        )

    def test_official_stock_reads_use_bearer_and_expected_routes(self) -> None:
        calls = []

        def opener(request, timeout):
            calls.append(request)
            if request.full_url.endswith(LOGIN_PATH):
                return FakeResponse(200, {"token": "header.payload.signature"})
            if request.full_url.endswith("/technet/estoques/10"):
                return FakeResponse(200, [{"idestoque": 77}])
            return FakeResponse(200, [{"codigo": "22026189", "saldo": 5}])

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        stocks = client.installer_stocks(10)
        balance = client.stock_balance(77)

        self.assertEqual(stocks, [{"idestoque": 77}])
        self.assertEqual(balance, [{"codigo": "22026189", "saldo": 5}])
        self.assertEqual(calls[1].method, "GET")
        self.assertTrue(calls[1].full_url.endswith("/technet/estoques/10"))
        self.assertTrue(calls[2].full_url.endswith("/technet/equipamentosestocagem/saldo/77"))
        self.assertEqual(calls[2].get_header("Authorization"), "Bearer header.payload.signature")

    def test_official_stock_read_renews_expired_token_once(self) -> None:
        login_count = 0
        get_count = 0

        def opener(request, timeout):
            nonlocal login_count, get_count
            if request.full_url.endswith(LOGIN_PATH):
                login_count += 1
                return FakeResponse(200, {"token": f"token-{login_count}"})
            get_count += 1
            if get_count == 1:
                raise urllib.error.HTTPError(
                    request.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{}')
                )
            return FakeResponse(200, [{"idestoque": 77}])

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        self.assertEqual(client.list_stocks(), [{"idestoque": 77}])
        self.assertEqual(login_count, 2)
        self.assertEqual(get_count, 2)

    def test_official_stock_rejects_invalid_identifier_without_network(self) -> None:
        opener = Mock()
        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        with self.assertRaisesRegex(ImperiumHTTPValidationError, "ID do estoque"):
            client.stock_balance(0)
        opener.assert_not_called()

    def test_validation_failure_sends_nothing(self) -> None:
        opener = Mock()
        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        payload = sample_payload()
        payload["ordemservico"]["numero"] = ""
        with self.assertRaises(ImperiumHTTPValidationError):
            client.close_order(payload)
        opener.assert_not_called()

    def test_write_timeout_is_uncertain_and_not_retried(self) -> None:
        calls = []

        def opener(request, timeout):
            calls.append(request)
            if request.full_url.endswith(LOGIN_PATH):
                return FakeResponse(200, {"token": "header.payload.signature"})
            raise socket.timeout("late response")

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        with self.assertRaisesRegex(ImperiumHTTPUncertainError, "Nao repita"):
            client.close_order(sample_payload())
        self.assertEqual(len(calls), 2)

    def test_unauthorized_write_renews_token_and_retries_once(self) -> None:
        calls = []
        login_count = 0
        write_count = 0

        def opener(request, timeout):
            nonlocal login_count, write_count
            calls.append(request)
            if request.full_url.endswith(LOGIN_PATH):
                login_count += 1
                return FakeResponse(200, {"token": f"token-{login_count}"})
            write_count += 1
            if write_count == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    401,
                    "Unauthorized",
                    {},
                    io.BytesIO(b'{"erro":"token expirado"}'),
                )
            return FakeResponse(200, {"mensagem": "recebido"})

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        result = client.close_order(sample_payload())

        self.assertTrue(result.accepted)
        self.assertEqual(login_count, 2)
        self.assertEqual(write_count, 2)
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[-1].get_header("Authorization"), "Bearer token-2")

    def test_second_unauthorized_write_is_not_retried_again(self) -> None:
        calls = []

        def opener(request, timeout):
            calls.append(request)
            if request.full_url.endswith(LOGIN_PATH):
                return FakeResponse(200, {"token": f"token-{len(calls)}"})
            raise urllib.error.HTTPError(
                request.full_url,
                403,
                "Forbidden",
                {},
                io.BytesIO(b'{"erro":"sem permissao"}'),
            )

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        with self.assertRaises(ImperiumHTTPError) as caught:
            client.close_order(sample_payload())

        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(len(calls), 4)

    def test_http_error_keeps_structured_response(self) -> None:
        calls = []

        def opener(request, timeout):
            calls.append(request)
            if request.full_url.endswith(LOGIN_PATH):
                return FakeResponse(200, {"token": "header.payload.signature"})
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(b'{"erro":"material invalido"}'),
            )

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        with self.assertRaises(ImperiumHTTPError) as caught:
            client.close_order(sample_payload())
        self.assertEqual(caught.exception.status, 400)
        self.assertEqual(caught.exception.response, {"erro": "material invalido"})
        self.assertEqual(len(calls), 2)

    def test_secrets_are_redacted_from_login_error(self) -> None:
        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                io.BytesIO(b'{"erro":"USER PASSWORD"}'),
            )

        client = ImperiumHTTPClient("USER", "PASSWORD", opener=opener)
        with self.assertRaises(ImperiumHTTPError) as caught:
            client.login()
        rendered = json.dumps(caught.exception.response)
        self.assertNotIn("USER", rendered)
        self.assertNotIn("PASSWORD", rendered)
        self.assertIn("[redacted]", rendered)

    def test_rejects_unencrypted_or_unknown_api_destination(self) -> None:
        with self.assertRaisesRegex(ImperiumHTTPValidationError, "nao autorizado"):
            ImperiumHTTPClient("USER", "PASSWORD", base_url="http://www.sistemaimperium.com.br")
        with self.assertRaisesRegex(ImperiumHTTPValidationError, "nao autorizado"):
            ImperiumHTTPClient("USER", "PASSWORD", base_url="https://evil.example")


if __name__ == "__main__":
    unittest.main()
