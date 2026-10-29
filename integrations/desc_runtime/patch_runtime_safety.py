"""Small source transformations for the legacy server; no network or writes.

The deployment script must verify the expected whole-file hash, create a
backup, compile the result and test it before replacing a running source.
"""
import ast


def patch_persisted_removed_movements(text: str) -> str:
    """Teach only the legacy reader the exact saved withdrawal row layout.

    Builders continue to emit delta rows. Saved rows returned by GetRecords
    have different flags/trailers but retain the same identity fields.
    """
    methods = {
        node.name: node
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.FunctionDef)
        and node.name in {'_parse_removed_detail_row', 'read_detail_equipment_movements'}
    }
    if len(methods) != 2:
        raise ValueError('Unsupported legacy movement reader identity')
    replacements = {
        '_parse_removed_detail_row': [
            (
                '        marker = bytes.fromhex("040000200000")\n'
                '        if record[position : position + len(marker)] != marker:',
                '        delta_marker = bytes.fromhex("040000200000")\n'
                '        saved_marker = bytes.fromhex("000000100000")\n'
                '        marker = record[position : position + len(delta_marker)]\n'
                '        if marker not in (delta_marker, saved_marker):',
            ),
            (
                '        trailer = bytes.fromhex("01000100014e1002")',
                '        trailer = bytes.fromhex(\n'
                '            "0000014e1002" if marker == saved_marker else "01000100014e1002"\n'
                '        )',
            ),
        ],
        'read_detail_equipment_movements': [
            (
                '        removed_marker = bytes.fromhex("040000200000") + id_marker',
                '        removed_markers = tuple(\n'
                '            bytes.fromhex(marker) + id_marker\n'
                '            for marker in ("040000200000", "000000100000")\n'
                '        )',
            ),
            (
                '            row_position = record.find(removed_marker, position)',
                '            row_positions = (record.find(marker, position) for marker in removed_markers)\n'
                '            row_position = min((offset for offset in row_positions if offset >= 0), default=-1)',
            ),
        ],
    }
    lines = text.splitlines(keepends=True)
    for method in sorted(methods.values(), key=lambda node: node.lineno, reverse=True):
        segment = ''.join(lines[method.lineno - 1:method.end_lineno])
        pairs = replacements[method.name]
        if all(new in segment for _, new in pairs):
            continue
        if any(segment.count(old) != 1 for old, _ in pairs):
            raise ValueError('Unsupported legacy movement reader layout')
        for old, new in pairs:
            segment = segment.replace(old, new, 1)
        lines[method.lineno - 1:method.end_lineno] = segment.splitlines(keepends=True)
    return ''.join(lines)


def patch_persisted_installed_movements(text: str) -> str:
    """Read saved installations with their permanent row and installer links."""
    replacements = {
        '_parse_installed_detail_row': [
            (
                '        marker = bytes.fromhex("040000800a0000")\n'
                '        if record[position : position + len(marker)] != marker:',
                '        delta_marker = bytes.fromhex("040000800a0000")\n'
                '        saved_marker = bytes.fromhex("00000000000000")\n'
                '        marker = record[position : position + len(delta_marker)]\n'
                '        if marker not in (delta_marker, saved_marker):',
            ),
            (
                '        trailer = bytes.fromhex("100200000000000001")',
                '        if marker == saved_marker:\n'
                '            saved_installer_id, position = cls._detail_u32(record, position)\n'
                '            _, position = cls._read_short_text(record, position)\n'
                '            saved_installer_name, position = cls._read_short_text(record, position)\n'
                '            if (saved_installer_id != context.installer_id\n'
                '                    or saved_installer_name != context.installer_name\n'
                '                    or installer_name != context.installer_name):\n'
                '                raise DataSnapError("The saved equipment installer identity is invalid")\n'
                '        trailer = bytes.fromhex("100200000000000001")',
            ),
            (
                '            or temporary_id >= 0',
                '            or (temporary_id <= 0 if marker == saved_marker else temporary_id >= 0)',
            ),
        ],
        '_find_installed_detail_serial': [
            (
                '        for candidate in range(max(0, start), len(record)):',
                '        serial_flags = b"\\x00" if temporary_id > 0 else b"\\x01\\x00"\n'
                '        row_flags = b"\\x00\\x00" if temporary_id > 0 else b"\\x04\\x00"\n'
                '        tail_flags = b"\\x00\\x01" if temporary_id > 0 else b"\\x01\\x00"\n'
                '        for candidate in range(max(0, start), len(record)):',
            ),
            (
                '                if record[position : position + 2] != b"\\x01\\x00":\n'
                '                    continue\n'
                '                position += 2\n'
                '                id_group, position = cls._detail_u32(record, position)',
                '                if record[position : position + len(serial_flags)] != serial_flags:\n'
                '                    continue\n'
                '                position += len(serial_flags)\n'
                '                id_group, position = cls._detail_u32(record, position)',
            ),
            (
                '                if record[position : position + 2] != b"\\x04\\x00":',
                '                if record[position : position + 2] != row_flags:',
            ),
            (
                '                if record[position : position + 2] != b"\\x01\\x00":\n'
                '                    continue\n'
                '            except',
                '                if record[position : position + 2] != tail_flags:\n'
                '                    continue\n'
                '            except',
            ),
        ],
        'read_detail_equipment_movements': [
            (
                '        installed_marker = bytes.fromhex("040000800a0000") + id_marker',
                '        installed_markers = tuple(\n'
                '            bytes.fromhex(marker) + id_marker\n'
                '            for marker in ("040000800a0000", "00000000000000")\n'
                '        )',
            ),
            (
                '            row_position = record.find(installed_marker, position)',
                '            row_positions = (record.find(marker, position) for marker in installed_markers)\n'
                '            row_position = min((offset for offset in row_positions if offset >= 0), default=-1)',
            ),
        ],
    }
    nodes = [node for node in ast.walk(ast.parse(text))
             if isinstance(node, ast.FunctionDef) and node.name in replacements]
    if len(nodes) != len(replacements):
        raise ValueError('Unsupported legacy installed reader identity')
    lines = text.splitlines(keepends=True)
    for method in sorted(nodes, key=lambda node: node.lineno, reverse=True):
        segment = ''.join(lines[method.lineno - 1:method.end_lineno])
        pairs = replacements[method.name]
        # The saved-row prelude retains the old trailer line; that line alone
        # cannot indicate that a partially modified method is supported.
        if all(new in segment for _, new in pairs):
            continue
        if any(segment.count(old) != 1 for old, _ in pairs):
            raise ValueError('Unsupported legacy installed reader layout')
        for old, new in pairs:
            segment = segment.replace(old, new, 1)
        lines[method.lineno - 1:method.end_lineno] = segment.splitlines(keepends=True)
    return ''.join(lines)


def patch_material_completeness(text: str) -> str:
    lines = text.splitlines(keepends=True)
    candidates = [node for node in ast.walk(ast.parse(text))
                  if isinstance(node, ast.FunctionDef) and node.name == 'prepare_official_materials']
    if len(candidates) != 1:
        raise ValueError('Unsupported legacy material preparation identity')
    method = candidates[0]
    segment = ''.join(lines[method.lineno - 1:method.end_lineno])
    marker = '                transfer_materials = list(allocation["transfers"])'
    guard = '''                # All TOA materials are required; never transfer or close a partial plan.
                if (allocation["partial_shortfalls"] or allocation["discarded_shortfalls"]
                        or int(allocation["missing_distinct_count"])):
                    raise ValueError(
                        "Estoque do tecnico + RETORNO insuficiente; baixa bloqueada "
                        "antes de qualquer transferencia. Todos os itens do TOA sao obrigatorios"
                    )
'''
    if guard in segment:
        return text
    if segment.count(marker) != 1:
        raise ValueError('Unsupported legacy material preparation layout')
    patched = segment.replace(marker, guard + marker, 1)
    return ''.join(lines[:method.lineno - 1]) + patched + ''.join(lines[method.end_lineno:])


def patch_official_code_only(text: str, *, helper_source: str) -> str:
    marker = '    if not productive and (installed_source or removed_source or material_source):'
    guard = '''    if is_code_only_adhesion_service(_value(order, "service")) and (
        installed_source or removed_source or material_source
    ):
        raise ValueError("Este servico de adesao aceita somente codigo de baixa, sem itens")

'''
    if guard in text:
        return text
    if text.count(marker) != 1 or 'def is_code_only_adhesion_service' in text:
        raise ValueError('Unsupported legacy official close layout')
    if not helper_source.startswith('def is_code_only_adhesion_service('):
        raise ValueError('Missing tested official service classifier')
    text = text.replace('import json\n', 'import json\nimport re\nimport unicodedata\n', 1)
    return text.replace('def _items(', helper_source + '\n\ndef _items(', 1).replace(marker, guard + marker, 1)
