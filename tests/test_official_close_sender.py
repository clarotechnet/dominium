import contextlib
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import official_close_sender as sender_module
from official_close_sender import (
    FingerprintMismatchError,
    HttpsOfficialCloseTransport,
    OfficialCloseSenderError,
    OfficialCloseUncertainError,
    OfficialCloseValidationError,
    OperationConflictError,
    RejectedReauthorizationRequired,
    TransportResponse,
    execute_single_official_close,
    official_payload_fingerprint,
)


TOKEN = "test-token-that-must-never-be-persisted"
OS_NUMBER = "2646508672"


def valid_payload() -> dict:
    return {
        "ordemservico": {
            "numero": OS_NUMBER,
            "dataagendamento": "2026-07-22",
            "codigotecnico": "Z637677",
            "codigobaixa": 409,
            "instaladosserializados": [{"serialnumber": "2CD8AE5D436F"}],
            "instaladosmiscelaneas": [
                {"codigoequipamento": "22069613", "qtd": "100.5"}
            ],
            "removidosserializados": [
                {
                    "codigoequipamento": "41001485",
                    "serialnumber": "B4F26757B818",
                }
            ],
        }
    }


class FakeTransport:
    def __init__(
        self,
        response: TransportResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or TransportResponse(200, b"")
        self.error = error
        self.calls: list[dict] = []

    def send(self, *, endpoint: str, body: bytes, token: str) -> TransportResponse:
        self.calls.append({"endpoint": endpoint, "body": body, "token": token})
        if self.error is not None:
            raise self.error
        return self.response


class OfficialCloseSenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state_dir = Path(self.temp.name)
        self.payload = valid_payload()
        self.fingerprint = official_payload_fingerprint(self.payload)
        self.environment = patch.dict(
            os.environ,
            {sender_module.TOKEN_ENVIRONMENT_VARIABLE: TOKEN},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def execute(
        self,
        transport: FakeTransport,
        *,
        operation_id: str = "operation-1",
        payload: object | None = None,
        fingerprint: str | None = None,
        rejected_reauthorization: str | None = None,
    ) -> dict:
        return execute_single_official_close(
            self.payload if payload is None else payload,
            expected_fingerprint=fingerprint or self.fingerprint,
            operation_id=operation_id,
            confirmation=f"ENVIAR-OS-{OS_NUMBER}",
            state_directory=self.state_dir,
            transport=transport,
            rejected_reauthorization=rejected_reauthorization,
        )

    def read_record(self, operation_id: str) -> dict:
        return json.loads(
            (self.state_dir / f"{operation_id}.json").read_text(encoding="utf-8")
        )

    def test_correct_fingerprint_allows_exactly_one_fake_call(self) -> None:
        transport = FakeTransport()

        result = self.execute(transport)

        self.assertEqual(result["state"], "queued")
        self.assertEqual(len(transport.calls), 1)
        sent_payload = json.loads(transport.calls[0]["body"].decode("utf-8"))
        self.assertEqual(sent_payload, self.payload)
        self.assertEqual(
            [entry["state"] for entry in result["history"]],
            ["prepared", "sending", "queued"],
        )

    def test_https_transport_sends_required_official_headers_once(self) -> None:
        class FakeResponse:
            status = 200

            @staticmethod
            def read(_size: int) -> bytes:
                return b""

        class FakeConnection:
            instances: list["FakeConnection"] = []

            def __init__(self, host: str, *, timeout: float) -> None:
                self.host = host
                self.timeout = timeout
                self.requests: list[dict] = []
                self.closed = False
                self.__class__.instances.append(self)

            def request(
                self,
                method: str,
                path: str,
                *,
                body: bytes,
                headers: dict[str, str],
            ) -> None:
                self.requests.append(
                    {
                        "method": method,
                        "path": path,
                        "body": body,
                        "headers": headers,
                    }
                )

            @staticmethod
            def getresponse() -> FakeResponse:
                return FakeResponse()

            def close(self) -> None:
                self.closed = True

        with patch.object(
            sender_module.http.client,
            "HTTPSConnection",
            FakeConnection,
        ):
            response = HttpsOfficialCloseTransport().send(
                endpoint=sender_module.OFFICIAL_CLOSE_ENDPOINT,
                body=b'{"ordemservico":{}}',
                token=TOKEN,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(FakeConnection.instances), 1)
        connection = FakeConnection.instances[0]
        self.assertEqual(len(connection.requests), 1)
        request = connection.requests[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["path"], "/technet/ordemservico")
        self.assertEqual(request["headers"]["Accept"], "application/json")
        self.assertEqual(
            request["headers"]["Content-Type"],
            "application/json; charset=utf-8",
        )
        self.assertEqual(request["headers"]["User-Agent"], "DOMINIUM/1.0")
        self.assertEqual(request["headers"]["Authorization"], f"Bearer {TOKEN}")
        self.assertTrue(connection.closed)

    def test_different_fingerprint_blocks_before_transport(self) -> None:
        transport = FakeTransport()

        with self.assertRaises(FingerprintMismatchError):
            self.execute(transport, fingerprint="0" * 64)

        self.assertEqual(transport.calls, [])
        self.assertEqual(list(self.state_dir.glob("*.json")), [])

    def test_invalid_payload_blocks_before_transport(self) -> None:
        transport = FakeTransport()
        payload = valid_payload()
        del payload["ordemservico"]["dataagendamento"]

        with self.assertRaises(OfficialCloseValidationError):
            self.execute(transport, payload=payload)

        self.assertEqual(transport.calls, [])

    def test_http_200_with_empty_body_is_queued_not_confirmed(self) -> None:
        result = self.execute(FakeTransport(TransportResponse(200, b"")))

        self.assertEqual(result["state"], "queued")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["response_body"], "")
        self.assertNotEqual(result["state"], "confirmed")

    def test_http_202_is_queued(self) -> None:
        result = self.execute(FakeTransport(TransportResponse(202, "accepted")))

        self.assertEqual(result["state"], "queued")
        self.assertEqual(result["http_status"], 202)

    def test_http_400_is_rejected(self) -> None:
        result = self.execute(FakeTransport(TransportResponse(400, "invalid")))

        self.assertEqual(result["state"], "rejected")
        self.assertEqual(result["http_status"], 400)

    def test_timeout_is_uncertain(self) -> None:
        transport = FakeTransport(error=TimeoutError("late"))

        with self.assertRaises(OfficialCloseUncertainError):
            self.execute(transport)

        self.assertEqual(self.read_record("operation-1")["state"], "uncertain")
        self.assertEqual(len(transport.calls), 1)

    def test_exception_after_call_start_is_uncertain(self) -> None:
        transport = FakeTransport(error=ConnectionResetError("closed"))

        with self.assertRaises(OfficialCloseUncertainError):
            self.execute(transport)

        record = self.read_record("operation-1")
        self.assertEqual(record["state"], "uncertain")
        self.assertEqual(record["transport_calls"], 1)

    def test_transport_failure_is_never_repeated(self) -> None:
        transport = FakeTransport(error=OSError("network unavailable"))

        with self.assertRaises(OfficialCloseUncertainError):
            self.execute(transport)

        self.assertEqual(len(transport.calls), 1)

    def test_module_has_no_alternate_transport_fallback(self) -> None:
        source = inspect.getsource(sender_module).lower()

        self.assertNotIn("datasnap", source)
        self.assertNotIn("imperium_http_api", source)

    def test_queued_record_blocks_same_os_and_fingerprint(self) -> None:
        self.execute(FakeTransport())
        second = FakeTransport()

        with self.assertRaises(OperationConflictError):
            self.execute(second, operation_id="operation-2")

        self.assertEqual(second.calls, [])

    def test_queued_record_blocks_same_os_even_if_payload_changes(self) -> None:
        self.execute(FakeTransport())
        changed = valid_payload()
        changed["ordemservico"]["instaladosmiscelaneas"][0]["qtd"] = "101"
        second = FakeTransport()

        with self.assertRaises(OperationConflictError):
            self.execute(
                second,
                operation_id="operation-2",
                payload=changed,
                fingerprint=official_payload_fingerprint(changed),
            )

        self.assertEqual(second.calls, [])

    def test_uncertain_record_blocks_same_os_and_fingerprint(self) -> None:
        with self.assertRaises(OfficialCloseUncertainError):
            self.execute(FakeTransport(error=TimeoutError()))
        second = FakeTransport()

        with self.assertRaises(OperationConflictError):
            self.execute(second, operation_id="operation-2")

        self.assertEqual(second.calls, [])

    def test_rejected_requires_separate_manual_reauthorization(self) -> None:
        rejected = self.execute(FakeTransport(TransportResponse(400, "invalid")))
        self.assertEqual(rejected["state"], "rejected")
        second = FakeTransport(TransportResponse(202, "queued"))

        with self.assertRaises(RejectedReauthorizationRequired):
            self.execute(second, operation_id="operation-2")
        self.assertEqual(second.calls, [])

        accepted = self.execute(
            second,
            operation_id="operation-3",
            rejected_reauthorization=f"REAUTORIZAR-OS-{OS_NUMBER}",
        )
        self.assertEqual(accepted["state"], "queued")
        self.assertEqual(len(second.calls), 1)

    def test_response_body_cannot_persist_the_environment_token(self) -> None:
        response = TransportResponse(
            400,
            f'{{"token":"{TOKEN}","message":"Bearer {TOKEN}"}}',
        )

        result = self.execute(FakeTransport(response))
        persisted = (self.state_dir / "operation-1.json").read_text(
            encoding="utf-8"
        )

        self.assertEqual(result["state"], "rejected")
        self.assertNotIn(TOKEN, result["response_body"])
        self.assertNotIn(TOKEN, persisted)

    def test_token_is_not_printed_persisted_or_exposed_by_exception(self) -> None:
        transport = FakeTransport(error=RuntimeError(f"failure {TOKEN}"))
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(OfficialCloseUncertainError) as raised:
                self.execute(transport)

        record_text = (self.state_dir / "operation-1.json").read_text(
            encoding="utf-8"
        )
        combined = stdout.getvalue() + stderr.getvalue() + str(raised.exception)
        self.assertNotIn(TOKEN, combined)
        self.assertNotIn(TOKEN, record_text)
        self.assertNotIn("Authorization", record_text)

    def test_import_does_not_open_network(self) -> None:
        script = (
            "import http.client\n"
            "class BlockedConnection:\n"
            "    def __init__(self, *args, **kwargs):\n"
            "        raise RuntimeError('network-called-during-import')\n"
            "http.client.HTTPSConnection = BlockedConnection\n"
            "import official_close_sender\n"
            "print('IMPORT_OK')\n"
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "IMPORT_OK")

    def test_list_with_two_orders_is_rejected(self) -> None:
        transport = FakeTransport()
        payload = [valid_payload(), valid_payload()]

        with self.assertRaises(OfficialCloseValidationError):
            self.execute(transport, payload=payload)

        self.assertEqual(transport.calls, [])

    def test_each_invocation_calls_transport_at_most_once(self) -> None:
        for status in (200, 202, 400, 503):
            with self.subTest(status=status):
                directory = Path(self.temp.name) / str(status)
                transport = FakeTransport(TransportResponse(status, "body"))
                execute_single_official_close(
                    deepcopy(self.payload),
                    expected_fingerprint=self.fingerprint,
                    operation_id=f"operation-{status}",
                    confirmation=f"ENVIAR-OS-{OS_NUMBER}",
                    state_directory=directory,
                    transport=transport,
                )
                self.assertEqual(len(transport.calls), 1)

    def test_missing_execute_confirmation_blocks_before_state_creation(self) -> None:
        transport = FakeTransport()

        with self.assertRaises(OfficialCloseSenderError):
            execute_single_official_close(
                self.payload,
                expected_fingerprint=self.fingerprint,
                operation_id="operation-1",
                confirmation="ENVIAR",
                state_directory=self.state_dir,
                transport=transport,
            )

        self.assertEqual(transport.calls, [])
        self.assertEqual(list(self.state_dir.glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
