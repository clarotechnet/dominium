# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - SIM - protocolo, baixa, estoque ou operacao do Imperium.
#
# TOA
# - NAO - este arquivo nao consulta nem automatiza o TOA.
#
# DOMINIUM COMPARTILHADO
# - Apoio local apenas quando necessario ao fluxo Imperium.
#
# Categoria deste arquivo: IMPERIUM.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
import ctypes
import json
import re
import socket
from ctypes import wintypes
from pathlib import Path
from typing import Any


class DataSnapError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob_from_bytes(data: bytes) -> tuple[_DataBlob, Any]:
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _configure_dpapi(crypt32: Any, kernel32: Any) -> None:
    blob_pointer = ctypes.POINTER(_DataBlob)
    crypt32.CryptProtectData.argtypes = [
        blob_pointer,
        wintypes.LPCWSTR,
        blob_pointer,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        blob_pointer,
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        blob_pointer,
        ctypes.c_void_p,
        blob_pointer,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        blob_pointer,
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p


def protect_secret(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    _configure_dpapi(crypt32, kernel32)
    source, source_buffer = _blob_from_bytes(data)
    output = _DataBlob()
    entropy, entropy_buffer = _blob_from_bytes(b"ImperiumDireto:v1")

    ok = crypt32.CryptProtectData(
        ctypes.byref(source),
        "Imperium DataSnap",
        ctypes.byref(entropy),
        None,
        None,
        0x1,
        ctypes.byref(output),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer, entropy_buffer


def unprotect_secret(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    _configure_dpapi(crypt32, kernel32)
    source, source_buffer = _blob_from_bytes(data)
    output = _DataBlob()
    entropy, entropy_buffer = _blob_from_bytes(b"ImperiumDireto:v1")

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        ctypes.byref(entropy),
        None,
        None,
        0x1,
        ctypes.byref(output),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer, entropy_buffer


def save_credentials(path: Path, username: str, password: str) -> None:
    payload = json.dumps(
        {"username": username, "password": password},
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(protect_secret(payload))


def load_credentials(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(unprotect_secret(path.read_bytes()).decode("utf-8"))
    except FileNotFoundError as exc:
        raise DataSnapError(f"Credencial local nao encontrada: {path}") from exc
    if not payload.get("username") or not payload.get("password"):
        raise DataSnapError("A credencial DataSnap local esta incompleta")
    return payload


class DataSnapClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: float = 20.0,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._pending = bytearray()

    def __enter__(self) -> "DataSnapClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def connect(self) -> None:
        if self._socket is not None:
            return

        connection = socket.create_connection((self.host, self.port), self.timeout)
        connection.settimeout(self.timeout)
        self._socket = connection
        connection.sendall(b"\x05" * 5)
        greeting = self._receive_exact(5)
        if greeting != b"\x06\x00\x00\x00\x00":
            self.close()
            raise DataSnapError(f"Resposta inicial DataSnap inesperada: {greeting.hex()}")

        response = self.request(
            "connect",
            [
                {
                    "DriverName": "DataSnap",
                    "DriverUnit": "Data.DBXDataSnap",
                    "Port": str(self.port),
                    "CommunicationProtocol": "tcp/ip",
                    "DatasnapContext": "datasnap/",
                    "DriverAssemblyLoader": (
                        "Borland.Data.TDBXClientDriverLoader,"
                        "Borland.Data.DbxClientDriver,Version=24.0.0.0,"
                        "Culture=neutral,PublicKeyToken=91d62ebb5b0d1b1b"
                    ),
                    "HostName": self.host,
                    "DSAuthenticationUser": self.username,
                    "DSAuthenticationPassword": self.password,
                    "UNLICENSED_DRIVERS": "0",
                }
            ],
        )
        if response.get("result", [None])[0] != 0:
            self.close()
            raise DataSnapError(f"Conexao DataSnap recusada: {response}")

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._pending.clear()

    def set_timeout(self, timeout: float) -> None:
        self.timeout = timeout
        if self._socket is not None:
            self._socket.settimeout(timeout)

    def prepare(self, method_name: str) -> dict[str, Any]:
        return self.request(
            "prepare",
            [-1, False, "DataSnap.ServerMethod", method_name],
        )

    def request(self, method: str, params: list[Any]) -> dict[str, Any]:
        if self._socket is None:
            raise DataSnapError("Cliente DataSnap nao conectado")
        payload = _encode_wire_value({"method": method, "params": params})
        self._socket.sendall(payload)
        response = self._receive_json()
        if "error" in response:
            raise DataSnapError(str(response["error"]))
        return response

    def continue_blob(self, data: bytes, *, final: bool = True) -> dict[str, Any]:
        if self._socket is None:
            raise DataSnapError("Cliente DataSnap nao conectado")
        length = -len(data) if final else len(data)
        payload = b'{"data":[' + str(length).encode("ascii") + b"," + data + b"]}"
        self._socket.sendall(payload)
        response = self._receive_json()
        if "error" in response:
            raise DataSnapError(str(response["error"]))
        return response

    def _receive_exact(self, length: int) -> bytes:
        if self._socket is None:
            raise DataSnapError("Cliente DataSnap nao conectado")
        output = bytearray()
        while len(output) < length:
            chunk = self._socket.recv(length - len(output))
            if not chunk:
                raise DataSnapError("Servidor encerrou a conexao durante a leitura")
            output.extend(chunk)
        return bytes(output)

    def _receive_json(self) -> dict[str, Any]:
        if self._socket is None:
            raise DataSnapError("Cliente DataSnap nao conectado")

        while True:
            decoded = _decode_wire_message(self._pending)
            if decoded is not None:
                end, response = decoded
                del self._pending[:end]
                if not isinstance(response, dict):
                    raise DataSnapError("Resposta DataSnap nao e um objeto JSON")
                return response

            chunk = self._socket.recv(64 * 1024)
            if not chunk:
                raise DataSnapError("Servidor encerrou a conexao sem responder")
            self._pending.extend(chunk)


def _encode_wire_value(value: Any) -> bytes:
    if isinstance(value, bytes):
        return b'{"data":[' + str(len(value)).encode("ascii") + b"," + value + b"]}"
    if isinstance(value, list):
        return b"[" + b",".join(_encode_wire_value(item) for item in value) + b"]"
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            encoded_key = json.dumps(str(key), ensure_ascii=True).encode("ascii")
            parts.append(encoded_key + b":" + _encode_wire_value(item))
        return b"{" + b",".join(parts) + b"}"
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


_DATA_HEADER = re.compile(br'"data"\s*:\s*\[\s*(-?\d+)\s*,')


def _replace_blob_markers(value: Any, blobs: dict[str, bytes]) -> Any:
    if isinstance(value, str) and value in blobs:
        return blobs[value]
    if isinstance(value, list):
        return [_replace_blob_markers(item, blobs) for item in value]
    if isinstance(value, dict):
        return {key: _replace_blob_markers(item, blobs) for key, item in value.items()}
    return value


def _decode_wire_message(data: bytearray) -> tuple[int, Any] | None:
    normalized = bytearray()
    blobs: dict[str, bytes] = {}
    started = False
    depth = 0
    in_string = False
    escaped = False
    index = 0

    while index < len(data):
        byte = data[index]
        if not started:
            if byte in b" \t\r\n":
                normalized.append(byte)
                index += 1
                continue
            if byte != ord("{"):
                raise DataSnapError(f"Resposta DataSnap invalida no byte {index}")
            started = True

        if in_string:
            normalized.append(byte)
            if escaped:
                escaped = False
            elif byte == ord("\\"):
                escaped = True
            elif byte == ord('"'):
                in_string = False
            index += 1
            continue

        header = _DATA_HEADER.match(data, index)
        if header is not None:
            blob_length = abs(int(header.group(1)))
            blob_start = header.end()
            blob_end = blob_start + blob_length
            if blob_end > len(data):
                return None
            marker = f"__datasnap_blob_{len(blobs)}__"
            blobs[marker] = bytes(data[blob_start:blob_end])
            normalized.extend(data[index:blob_start])
            normalized.extend(json.dumps(marker).encode("ascii"))
            depth += 1
            index = blob_end
            continue

        normalized.append(byte)
        if byte == ord('"'):
            in_string = True
        elif byte in (ord("{"), ord("[")):
            depth += 1
        elif byte in (ord("}"), ord("]")):
            depth -= 1
            if started and depth == 0:
                try:
                    decoded = json.loads(bytes(normalized).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise DataSnapError("Resposta DataSnap invalida") from exc
                return index + 1, _replace_blob_markers(decoded, blobs)
        index += 1
    return None
