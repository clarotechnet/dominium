import io
import struct
import unittest
import zipfile

from flow_reader import CaptureFormatError, analyze_capture


def _block(block_type: int, body: bytes) -> bytes:
    padding = b"\x00" * ((-len(body)) % 4)
    length = 12 + len(body) + len(padding)
    return (
        struct.pack("<II", block_type, length)
        + body
        + padding
        + struct.pack("<I", length)
    )


def _tcp_frame(
    source_port: int,
    destination_port: int,
    sequence: int,
    payload: bytes,
    *,
    push: bool = True,
) -> bytes:
    ethernet = (
        bytes.fromhex("00112233445566778899aabb")
        + struct.pack("!H", 0x0800)
    )
    source_ip = bytes((192, 168, 1, 10))
    destination_ip = bytes((45, 176, 169, 251))
    if source_port == 212:
        source_ip, destination_ip = destination_ip, source_ip
    total_length = 20 + 20 + len(payload)
    ipv4 = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        1,
        0x4000,
        64,
        6,
        0,
        source_ip,
        destination_ip,
    )
    flags = 0x18 if push else 0x10
    tcp = struct.pack(
        "!HHIIBBHHH",
        source_port,
        destination_port,
        sequence,
        1,
        0x50,
        flags,
        65535,
        0,
        0,
    )
    return ethernet + ipv4 + tcp + payload


def _epb(frame: bytes, timestamp_us: int) -> bytes:
    body = struct.pack(
        "<IIIII",
        0,
        timestamp_us >> 32,
        timestamp_us & 0xFFFFFFFF,
        len(frame),
        len(frame),
    ) + frame
    return _block(6, body)


def _capture() -> bytes:
    section = _block(
        0x0A0D0D0A,
        struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1),
    )
    interface = _block(1, struct.pack("<HHI", 1, 0, 65535))
    target = "TDtmOrdemServico.AS_ApplyUpdates"
    prepare = (
        b'{"method":"prepare","params":[-1,false,'
        b'"DataSnap.ServerMethod","'
        + target.encode("ascii")
        + b'"]}'
    )
    prepare_response = b'{"result":[{"handle":[12]},{"fields":[]}]}'
    status = "Status".encode("utf-16le") + struct.pack("<II", 8, 1) + b"1"
    service = (
        "IdTipoServico".encode("utf-16le")
        + struct.pack("<II", 8, 1)
        + b"3"
    )
    close = b"\x03" + b"312" + b"\x15NAO SOLICITOU SERVICO"
    execute = (
        b'{"method":"execute","params":[{"handle":[12]},{"data":[120,'
        + status
        + service
        + close
        + b"]}]}"
    )
    execute_response = b'{"result":[{"rows":[1]}]}'
    client_sequence = 1000
    server_sequence = 9000
    pieces = [execute[:55], execute[55:]]
    return b"".join(
        [
            section,
            interface,
            _epb(_tcp_frame(50000, 212, client_sequence, prepare), 1_000_000),
            _epb(_tcp_frame(212, 50000, server_sequence, prepare_response), 1_010_000),
            # The final half arrives first in the file to exercise sequence reordering.
            _epb(
                _tcp_frame(
                    50000,
                    212,
                    client_sequence + len(prepare) + len(pieces[0]),
                    pieces[1],
                ),
                1_020_000,
            ),
            _epb(
                _tcp_frame(
                    50000,
                    212,
                    client_sequence + len(prepare),
                    pieces[0],
                    push=False,
                ),
                1_021_000,
            ),
            # Duplicate shorter segment must not replace the complete one.
            _epb(
                _tcp_frame(
                    50000,
                    212,
                    client_sequence + len(prepare),
                    pieces[0][:20],
                    push=False,
                ),
                1_022_000,
            ),
            _epb(
                _tcp_frame(
                    212,
                    50000,
                    server_sequence + len(prepare_response),
                    execute_response,
                ),
                1_030_000,
            ),
        ]
    )


class FlowReaderTests(unittest.TestCase):
    def test_reconstructs_datasnap_write_and_evidence(self) -> None:
        result = analyze_capture(_capture(), "teste.pcapng")

        writes = [flow for flow in result["flows"] if flow["category"] == "write"]
        self.assertEqual(len(writes), 1)
        write = writes[0]
        self.assertEqual(write["server_method"], "TDtmOrdemServico.AS_ApplyUpdates")
        self.assertEqual(write["filters"]["Status"], "1")
        self.assertEqual(write["filters"]["IdTipoServico"], "3")
        self.assertEqual(write["close_codes"][0]["code"], "312")
        self.assertEqual(write["status"], "ok")
        self.assertEqual(result["summary"]["write_count"], 1)
        self.assertEqual(result["summary"]["prepared_write_count"], 1)
        prepared = next(flow for flow in result["flows"] if flow["category"] == "prepare")
        self.assertEqual(prepared["risk"], "prepara alteracao; nao executada")

    def test_reads_zip_and_information_file_without_extracting(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("sessao/captura.pcapng", _capture())
            archive.writestr("sessao/INFORMACOES.txt", "Resumo: baixa 312")

        result = analyze_capture(buffer.getvalue(), "sessao.zip")

        self.assertEqual(result["source"]["filename"], "sessao.zip")
        self.assertEqual(result["source"]["notes"], "Resumo: baixa 312")
        self.assertEqual(len(result["source"]["sha256"]), 64)

    def test_rejects_non_capture_input(self) -> None:
        with self.assertRaisesRegex(CaptureFormatError, "ZIP ou PCAPNG"):
            analyze_capture(b"not a capture", "arquivo.txt")


if __name__ == "__main__":
    unittest.main()
