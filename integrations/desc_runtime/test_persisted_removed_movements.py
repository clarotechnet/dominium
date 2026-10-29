"""Legacy server tests; run against its staged imperium_api, without network I/O."""
import struct
import unittest
from pathlib import Path

from datasnap_client import DataSnapError
from imperium_api import DetailContext, ImperiumAPI


if not hasattr(ImperiumAPI, 'read_detail_equipment_movements'):
    # The web API and the installed legacy API have different readers.
    # CI executes the same transformer against the frozen legacy methods.
    from integrations.desc_runtime.patch_runtime_safety import (
        patch_persisted_removed_movements, patch_persisted_installed_movements,
    )
    fixture = Path(__file__).resolve().parents[2] / 'tests/fixtures/legacy_movement_reader.py'
    source = fixture.read_text(encoding='utf-8')
    patched = patch_persisted_installed_movements(patch_persisted_removed_movements(source))
    assert patch_persisted_removed_movements(patched) == patched
    assert patch_persisted_installed_movements(patched) == patched
    namespace = {'__name__': '_legacy_reader_fixture'}
    exec(compile(patched, str(fixture), 'exec'), namespace)
    ImperiumAPI = namespace['ImperiumAPI']


CONTEXT = DetailContext(7001, '4000001', 9001, 'TECNICO TESTE DESC')


class PacketAPI(ImperiumAPI):
    # Only the outer dataset loader is replaced. Row decoding is production code.
    @staticmethod
    def _detail_record(detail):
        return detail

    @staticmethod
    def _detail_context(detail):
        return CONTEXT


def text(value):
    encoded = value.encode('ascii')
    return bytes([len(encoded)]) + encoded


def row(*, saved=True, serial='SERIAL000001', repeated_serial=None, id_os=7001):
    # Independent synthetic fixture: same field layout observed on the wire,
    # with fictional identifiers and descriptions. No production builder used.
    return b''.join([
        bytes.fromhex('000000100000' if saved else '040000200000'),
        struct.pack('<II', id_os, 260),
        text('41000001'), text('EMTA TESTE'), text('S'),
        struct.pack('<I', 2), text('MARCA TESTE'),
        struct.pack('<I', 2), text('UN'), text(serial),
        struct.pack('<I', 260), text(repeated_serial or serial),
        bytes.fromhex('0000014e1002' if saved else '01000100014e1002'),
        bytes.fromhex('000001000000000000000000'),
    ])


def installed_row(*, saved=True, linked_id=None, installer_id=9001, repeated_serial=None):
    row_id = 1001 if saved else -1
    return b''.join([
        bytes.fromhex('00000000000000' if saved else '040000800a0000'),
        struct.pack('<IIIi', 7001, 5001, 57, row_id),
        text('DECODER TESTE'), struct.pack('<I', 6), text('MARCA TESTE'),
        struct.pack('<I', 2), text('UN'), text('S'), text('TECNICO TESTE DESC'),
        (struct.pack('<I', installer_id) + text('LOGIN TESTE') + text('TECNICO TESTE DESC')) if saved else b'',
        bytes.fromhex('100200000000000001'),
        b'\x00', text('41000002'), struct.pack('<I', 1), text('N'), text('INSTALL00001'),
        b'\x00' if saved else b'\x01\x00',
        struct.pack('<II', 10005, 1), b'\x00\x00' if saved else b'\x04\x00',
        struct.pack('<i', row_id if linked_id is None else linked_id),
        text(repeated_serial or 'INSTALL00001'), b'\x00\x01' if saved else b'\x01\x00',
    ])


class PersistedRemovedMovementTests(unittest.TestCase):
    def test_saved_withdrawal_is_reconciled_from_detail(self):
        result = PacketAPI.read_detail_equipment_movements(row())
        self.assertEqual([e.serial for e in result.removed], ['SERIAL000001'])
        self.assertEqual(result.removed[0].code, '41000001')
        self.assertEqual(result.installed, ())
        self.assertFalse(result.materials_present)

    def test_existing_delta_withdrawal_is_preserved(self):
        result = PacketAPI.read_detail_equipment_movements(row(saved=False))
        self.assertEqual([e.serial for e in result.removed], ['SERIAL000001'])

    def test_saved_and_delta_rows_are_both_checked(self):
        packet = row() + row(saved=False, serial='SERIAL000002')
        result = PacketAPI.read_detail_equipment_movements(packet)
        self.assertEqual([e.serial for e in result.removed],
                         ['SERIAL000001', 'SERIAL000002'])

    def test_saved_row_cannot_reconcile_another_os(self):
        self.assertEqual(PacketAPI.read_detail_equipment_movements(row(id_os=7002)).removed, ())
        with self.assertRaises(DataSnapError):
            PacketAPI._parse_removed_detail_row(row(id_os=7002), 0, CONTEXT)

    def test_saved_row_with_conflicting_serial_is_rejected(self):
        with self.assertRaises(DataSnapError):
            PacketAPI.read_detail_equipment_movements(row(repeated_serial='SERIAL000099'))

    def test_unknown_saved_trailer_is_rejected(self):
        packet = row().replace(bytes.fromhex('0000014e1002'), bytes.fromhex('000001581002'))
        with self.assertRaises(DataSnapError):
            PacketAPI.read_detail_equipment_movements(packet)

    def test_duplicate_saved_movements_are_rejected(self):
        with self.assertRaises(DataSnapError):
            PacketAPI.read_detail_equipment_movements(row() + row())

    def test_serial_mentions_do_not_prove_a_movement(self):
        self.assertEqual(PacketAPI.read_detail_equipment_movements(text('SERIAL000001')).removed, ())

    def test_saved_installation_is_reconciled_with_its_serial_link(self):
        result = PacketAPI.read_detail_equipment_movements(installed_row())
        self.assertEqual([(e.serial, e.code, e.id_stock, e.id_group) for e in result.installed],
                         [('INSTALL00001', '41000002', 57, 10005)])

    def test_delta_installation_is_preserved(self):
        result = PacketAPI.read_detail_equipment_movements(installed_row(saved=False))
        self.assertEqual([e.serial for e in result.installed], ['INSTALL00001'])

    def test_saved_swap_reports_one_incoming_and_one_outgoing(self):
        result = PacketAPI.read_detail_equipment_movements(installed_row() + row())
        self.assertEqual([e.serial for e in result.installed], ['INSTALL00001'])
        self.assertEqual([e.serial for e in result.removed], ['SERIAL000001'])

    def test_saved_installation_rejects_a_different_serial_row_link(self):
        with self.assertRaises(DataSnapError):
            PacketAPI.read_detail_equipment_movements(installed_row(linked_id=1002))

    def test_saved_installation_rejects_a_different_installer(self):
        with self.assertRaises(DataSnapError):
            PacketAPI.read_detail_equipment_movements(installed_row(installer_id=9002))

    def test_duplicate_saved_installations_are_rejected(self):
        with self.assertRaises(DataSnapError):
            PacketAPI.read_detail_equipment_movements(installed_row() + installed_row())

    def test_saved_installation_rejects_conflicting_repeated_serial(self):
        with self.assertRaises(DataSnapError):
            PacketAPI.read_detail_equipment_movements(installed_row(repeated_serial='INSTALL00099'))
