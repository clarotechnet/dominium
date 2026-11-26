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


def patch_official_atlas_before_return(text: str) -> str:
    """Use exact Atlas groups before RETORNO in the installed official path."""
    methods = {
        node.name: node for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.FunctionDef) and node.name in {
            '_allocate_requested_material_groups_on', 'prepare_official_materials',
        }
    }
    if len(methods) != 2:
        raise ValueError('Unsupported legacy official material methods')
    lines = text.splitlines(keepends=True)
    allocator = methods['_allocate_requested_material_groups_on']
    prepare = methods['prepare_official_materials']
    allocation = ''.join(lines[allocator.lineno - 1:allocator.end_lineno])
    official = ''.join(lines[prepare.lineno - 1:prepare.end_lineno])
    if 'official_atlas_first: bool = False,' in allocation and 'official_atlas_first=True,' in official:
        return text
    keyword = '        lookup_handle: int | None = None,\n'
    previous_start = '            candidate_codes = set(candidate_by_code)\n'
    previous_end = '            ordered_codes = sorted(candidate_codes)\n'
    call = '                    requested,\n                )\n'
    if any(allocation.count(marker) != 1 for marker in (keyword, previous_start, previous_end)) or official.count(call) != 1:
        raise ValueError('Unsupported legacy official material layout')
    start, end = allocation.index(previous_start), allocation.index(previous_end)
    original = allocation[start:end]
    official_branch = '''            if official_atlas_first:
                candidate_codes = {requested_code}
                if technician_remaining.get(requested_code, 0) < required:
                    master_group = (
                        self._master_atlas_group_on(client, requested_code)
                        if re.fullmatch(r"[0-9]{8}", requested_code)
                        else ()
                    )
                    original_material = available.get(requested_code) or candidate_by_code.get(requested_code)

                    def add_stocked_equivalents(inventory, balances):
                        for code in master_group:
                            alternate = inventory.get(code)
                            if code == requested_code or alternate is None or balances.get(code, 0) <= 0:
                                continue
                            if original_material is None:
                                raise ValueError(f"Unidade da miscelanea {requested_code} nao confirmada no Atlas")
                            if alternate.identified == "N" and alternate.unit == original_material.unit:
                                candidate_codes.add(code)

                    add_stocked_equivalents(available, technician_remaining)
                    if sum(technician_remaining.get(code, 0) for code in candidate_codes) < required:
                        ensure_source_catalog()
                        original_material = original_material or source_available.get(requested_code)
                        add_stocked_equivalents(source_available, source_remaining)
                # The shared allocator now consumes the vetted codes in order.
            else:
'''
    # An empty master group is authoritative. Read failures are propagated,
    # so the existing zero-stock audit applies only to completed reads.
    allocation = allocation[:start] + official_branch + ''.join(
        '    ' + line if line.strip() else line for line in original.splitlines(keepends=True)
    ) + allocation[end:]
    allocation = allocation.replace(keyword, keyword + '        official_atlas_first: bool = False,\n', 1)
    official = official.replace(call, '                    requested,\n                    official_atlas_first=True,\n                )\n', 1)
    for node, segment in sorted(((allocator, allocation), (prepare, official)), key=lambda item: item[0].lineno, reverse=True):
        lines[node.lineno - 1:node.end_lineno] = segment.splitlines(keepends=True)
    patched = ''.join(lines)
    ast.parse(patched)
    return patched


def patch_official_atlas_master_unit(text: str) -> str:
    """Read the unit from the exact master record when the original is absent from stock."""
    replacements = (
        (
            '    parse_code_group,\n',
            '    EquipmentAtlasRecord,\n    parse_code_record,\n',
        ),
        (
            '''    ) -> tuple[str, ...]:
        """Official read-only equipment master: Codigo -> DescricaoAtlas list."""
''',
            '''    ) -> tuple[str, ...]:
        return self._master_atlas_record_on(client, code).codes

    def _master_atlas_record_on(
        self,
        client: DataSnapClient,
        code: str,
    ) -> EquipmentAtlasRecord:
        """Official read-only equipment master: exact code, aliases and unit."""
''',
        ),
        (
            '        return parse_code_group(payload, code)\n',
            '        return parse_code_record(payload, code)\n',
        ),
        (
            '''                    master_group = (
                        self._master_atlas_group_on(client, requested_code)
                        if re.fullmatch(r"[0-9]{8}", requested_code)
                        else ()
                    )
''',
            '''                    master_group, master_unit = (
                        self._master_atlas_record_on(client, requested_code)
                        if re.fullmatch(r"[0-9]{8}", requested_code)
                        else ((), "")
                    )
''',
        ),
        (
            '''                            if original_material is None:
                                raise ValueError(f"Unidade da miscelanea {requested_code} nao confirmada no Atlas")
                            if alternate.identified == "N" and alternate.unit == original_material.unit:
                                candidate_codes.add(code)
''',
            '''                            if alternate.identified != "N":
                                continue
                            unit = original_material.unit if original_material is not None else master_unit
                            if not unit or (master_unit and unit != master_unit):
                                raise ValueError(f"Unidade da miscelanea {requested_code} nao confirmada no Atlas")
                            if alternate.unit == unit:
                                candidate_codes.add(code)
''',
        ),
    )
    if all(new in text for _, new in replacements):
        return text
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError('Unsupported legacy Atlas material layout')
        text = text.replace(old, new, 1)
    ast.parse(text)
    return text


def patch_official_return_group_search(text: str) -> str:
    """Use confirmed same-group RETORNO items after the official Atlas codes."""
    changes = (
        ('    parse_code_record,\n', '    parse_code_record,\n    parse_stock_atlas_record,\n    stocked_return_group_codes,\n'),
        (
            '    ) -> EquipmentAtlasRecord:\n        """Official read-only equipment master',
            '        *, allow_empty: bool = False,\n    ) -> EquipmentAtlasRecord:\n        """Official read-only equipment master',
        ),
        (
            '        return parse_code_record(payload, code)\n',
            '        parser = parse_stock_atlas_record if allow_empty else parse_code_record\n'
            '        return parser(payload, code)\n',
        ),
        (
            '                        self._master_atlas_record_on(client, requested_code)\n',
            '                        self._master_atlas_record_on(client, requested_code, allow_empty=self.profile_key == "natal")\n',
        ),
        (
            '            for candidate_code in return_order:\n',
            '''            group_return_codes = ()
            if (official_atlas_first and self.profile_key == "natal" and remaining > 0
                    and sum(source_remaining.get(code, 0) for code in return_order) < remaining):
                reference = source_available.get(requested_code) or available.get(requested_code)
                if reference is not None and (not master_unit or reference.unit == master_unit):
                    group_return_codes = tuple(
                        code for code in stocked_return_group_codes(
                            reference, description, source_available, source_remaining,
                        ) if code not in candidate_codes
                    )
                    return_order.extend(group_return_codes)
            for candidate_code in return_order:
''',
        ),
        (
            '''            for candidate_code, parts in allocations.items():
''',
            '''            if any(code in group_return_codes for code in used_codes):
                match_type = "grupo_retorno_confirmado"

            for candidate_code, parts in allocations.items():
''',
        ),
        (
            '                concrete["match_types"].add(match_type)\n',
            '                concrete_match = match_type\n'
            '                if match_type == "grupo_retorno_confirmado" and candidate_code not in group_return_codes:\n'
            '                    concrete_match = "exact_code" if requested_code == candidate_code else "codigo_atlas"\n'
            '                concrete["match_types"].add(concrete_match)\n',
        ),
    )
    audit_old = '''                        "codigo_atlas"
                        if (
                            "codigo_atlas" in match_types
                            or any(code != material.code for code in requested_codes)
                        )
'''
    audit_new = '''                        "grupo_retorno_confirmado"
                        if "grupo_retorno_confirmado" in match_types
                        else "codigo_atlas"
''' + audit_old.split('\n', 1)[1]
    if all(new in text for _, new in changes) and audit_new in text:
        return text
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError(f'Unsupported legacy RETORNO group search: {old.strip()[:100]}')
        text = text.replace(old, new, 1)
    marker = '    def prepare_official_materials(\n'
    before, official = text.split(marker, 1)
    if official.count(audit_old) != 1:
        raise ValueError('Unsupported legacy official material audit')
    text = before + marker + official.replace(audit_old, audit_new, 1)
    ast.parse(text)
    return text


def patch_close_report_download(text: str, *, web_app: str) -> str:
    """Reuse the web export route in the legacy panel, beside its JSON report."""
    marker = '            if parsed.path in ("/api/close-report/export.xlsx", "/api/close-report.xlsx"):\n'
    if text.count(marker) == 1:
        return text
    start = '            if parsed.path == "/api/close-report":\n'
    end = '            installer_detail_match = re.fullmatch(\n'
    if any(source.count(token) != 1 for source in (text, web_app) for token in (start, end)):
        raise ValueError('Unsupported close report layout')
    if web_app.count(marker) != 1:
        raise ValueError('Web export route not found')
    index = text.index(end, text.index(start))
    route = web_app[web_app.index(marker):web_app.index(end, web_app.index(marker))]
    export_call = '                xlsx_bytes = build_close_report_xlsx('
    if route.count(export_call) != 1:
        raise ValueError('Web export builder not found')
    route = route.replace(export_call, '                from close_report_excel import build_close_report_xlsx\n\n' + export_call)
    patched = text[:index] + route + text[index:]
    ast.parse(patched)
    return patched


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


def patch_adhesion_live_technician(text: str) -> str:
    """Keep the legacy identity checks and accept corroborated current TOA evidence."""
    replacements = (
        (
            'TECHNICIANS = TechnicianDirectory(ROOT / "config" / "technicians.json")\n',
            'from adhesion_technician_evidence import AdhesionTechnicianEvidence\n\n'
            'TECHNICIANS = TechnicianDirectory(ROOT / "config" / "technicians.json")\n'
            'ADHESION_TECHNICIAN_EVIDENCE = AdhesionTechnicianEvidence()\n',
        ),
        (
            '''                self._json(
                    HTTPStatus.OK,
                    _match_live_capture_to_orders(profile, result),
                )
''',
            '''                prepared = _match_live_capture_to_orders(profile, result)
                ADHESION_TECHNICIAN_EVIDENCE.record(profile.key, prepared)
                self._json(HTTPStatus.OK, prepared)
''',
        ),
        (
            '''            capture_login_matches = False
            if not supplied_identity_matches:
''',
            '''            if not supplied_identity_matches and ADHESION_TECHNICIAN_EVIDENCE.matches(
                profile.key, order, scheduled_date, toa_technician,
                installer_id, profile.api.list_stock_technicians,
            ):
                return supplied_login, current_name, installer_id
            capture_login_matches = False
            if not supplied_identity_matches:
''',
        ),
    )
    if all(new in text for _, new in replacements):
        return text
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError('Unsupported legacy technician evidence layout')
        text = text.replace(old, new, 1)
    ast.parse(text)
    return text


def patch_stock_retry_runtime(app: str, ledger: str, api: str, *, web_app: str, web_ledger: str) -> tuple[str, str, str]:
    """Port the verified stock-recheck path without replacing legacy services."""
    def replace_once(text, old, new):
        if text.count(old) != 1:
            raise ValueError(f'Unsupported stock retry anchor: {old.strip()[:80]}')
        return text.replace(old, new, 1)

    def before(text, first, last):
        start = text.index(first)
        return text[start:text.index(last, start)]

    if 'def _prepare_stock_close_retry(' in app:
        raise ValueError('Stock retry already installed')
    prepare = before(web_app, 'def _prepare_stock_close_retry(', 'def _report_base(')
    proof = before(web_ledger, 'def stock_prepare_failure(', 'class CloseReportStore:')
    app = replace_once(app, 'from close_report import CloseReportStore\n', 'from close_report import CloseReportStore, stock_prepare_failure\n')
    app = replace_once(app, 'def _report_base(', prepare + 'def _report_base(')
    retry_var = '            retry_of_request_id = str(body.get("retry_of_request_id", "")).strip()[:80]\n'
    app = replace_once(app, retry_var, retry_var + '            stock_retry_request_id = str(body.get("stock_retry_request_id", "")).strip()[:80]\n            prepared_stock_retry = None\n')
    controlled = '            if retry_of_request_id:\n'
    stock_check = before(web_app, '            if stock_retry_request_id:\n                try:', controlled)
    app = replace_once(app, controlled, stock_check + controlled)
    app = replace_once(app, '                    retry_of_request_id=retry_of_request_id,\n', '                    retry_of_request_id=stock_retry_request_id or retry_of_request_id,\n')
    app = replace_once(app, '                block_active_duplicate=True,\n', '                block_active_duplicate=True,\n                **({"stock_retry_request_id": stock_retry_request_id} if stock_retry_request_id else {}),\n')
    app = replace_once(app, '                material_preparation = profile.api.prepare_official_materials(\n', '                material_preparation = prepared_stock_retry or profile.api.prepare_official_materials(\n')

    ledger = replace_once(ledger, 'class CloseReportStore:', proof + 'class CloseReportStore:')
    begin_arg = '        block_active_duplicate: bool = False,\n'
    ledger = replace_once(ledger, begin_arg, begin_arg + '        stock_retry_request_id: str = "",\n')
    start = '            fingerprint = _text(record.get("fingerprint"), 128)\n'
    end = '            value = {\n'
    ledger = replace_once(ledger, before(ledger, start, end), before(web_ledger, start, end))
    insert = '            records.insert(0, value)\n'
    ledger = replace_once(ledger, insert, before(web_ledger, '            if stock_previous is not None:\n', insert) + insert)
    update = '                if record.get("request_id") != identifier:\n                    continue\n                value = dict(record)'
    ledger = replace_once(ledger, update, update.replace('                value = dict(record)', '                if record.get("category") == "STOCK_RECHECKED":\n                    return dict(record)\n                value = dict(record)'))

    method = '    def prepare_official_materials(\n'
    end = '    @classmethod\n    def _installed_parts('
    prepare_api = before(api, method, end)
    signature = '        expected_installer_id: int,\n'
    edited = replace_once(prepare_api, signature, signature + '        allow_transfer: bool = True,\n')
    transfer = '                if transfer_materials:\n                    self._transfer_material_shortfalls('
    edited = replace_once(edited, transfer, '''                if transfer_materials:
                    if not allow_transfer:
                        codes = ", ".join(dict.fromkeys(row.code for row in transfer_materials))
                        raise ValueError(f"RETORNO tem saldo para {codes}; o complemento anterior precisa ser conciliado")
                    self._transfer_material_shortfalls(''')
    api = replace_once(api, prepare_api, edited)
    for result in (app, ledger, api):
        ast.parse(result)
    return app, ledger, api

def patch_adhesion_fresh_export_runtime(text: str) -> str:
    """Refresh stale adhesion evidence without importing orders or touching DESC."""
    old = ('            from toa_export_task_recovery import reconcile_export_tasks\n'
           '            capture["tasks"] = reconcile_export_tasks(capture, ROOT / "logs" / "toa-exports")')
    new = ('            from toa_export_task_recovery import recover_tasks_with_refresh, download_adhesion_export\n'
           '            def refresh_adhesion_export(route, day):\n'
           '                if TOA_AUTOMATION.running or TOA_BUCKET_COLLECTOR.running:\n'
           '                    raise RuntimeError("TOA busy; retry consultation later")\n'
           '                download_adhesion_export(ROOT, route, day)\n'
           '            capture["tasks"] = recover_tasks_with_refresh(\n'
           '                capture, ROOT / "logs" / "toa-exports", all_status_rows or cached_rows,\n'
           '                refresh_adhesion_export)')
    if new in text:
        return text
    if text.count(old) != 1 or 'all_status_rows = result.get("imperium_all_orders")' not in text:
        raise ValueError("Unsupported legacy adhesion task recovery layout")
    result = text.replace(old, new, 1)
    ast.parse(result)
    return result


def patch_adhesion_lookup_runtime(app, secondary, bridge, gateway, extension, source_extension):
    """Port the opt-in adhesion lookup to the active Windows runtime layout."""
    def replace(text, old, new):
        if text.count(new) == 1:
            return text
        if text.count(old) != 1:
            raise ValueError(f"Unsupported legacy adhesion lookup: {old[:100]}")
        return text.replace(old, new, 1)

    app = replace(app,
        '                else:\n                    result = TOA_LIVE.lookup_contract(lookup_value)\n',
        '''                else:
                    if body.get("adhesion_batch") is True:
                        if profile.key != "natal":
                            raise ValueError("Consulta de adesao exclusiva de NTL/PWM")
                        adhesion_date = dt.date.fromisoformat(str(body.get("expected_date") or "")).isoformat()
                        result = TOA_LIVE.lookup_contract(lookup_value, adhesion_date=adhesion_date)
                    else:
                        result = TOA_LIVE.lookup_contract(lookup_value)
''')
    secondary = replace(secondary,
        'def _direct_lookup(self, contract: str)',
        'def _direct_lookup(self, contract: str, *, adhesion_date: str = "")')
    secondary = replace(secondary,
        '        with self._lookup_lock:\n            last_detail = ""',
        '        arguments = ["node", str(self.lookup_script), contract]\n'
        '        if adhesion_date:\n            arguments.append(adhesion_date)\n'
        '        with self._lookup_lock:\n            last_detail = ""')
    secondary = replace(secondary, '["node", str(self.lookup_script), contract],', 'arguments,')
    secondary = replace(secondary,
        'def lookup_contract(self, contract: object)',
        'def lookup_contract(self, contract: object, *, adhesion_date: str = "")')
    secondary = replace(secondary,
        'direct = self._direct_lookup(wanted)',
        'direct = self._direct_lookup(wanted, adhesion_date=adhesion_date)')

    bridge = replace(bridge,
        "const response = await fetch('http://127.0.0.1:9341/toa/lookup?contract=' + encodeURIComponent(contract),",
        "const query = new URLSearchParams({contract});\n"
        "const adhesionDate = String(process.argv[3] || '');\n"
        "if (adhesionDate) query.set('adhesion_date', adhesionDate);\n"
        "const response = await fetch('http://127.0.0.1:9341/toa/lookup?' + query,")
    old_expression = ('        return "globalThis.__TN_TOA_DIRECT_LOOKUP__(" + json.dumps(contract)'
                      ' + ", {requireSingleActivity: true})"')
    gateway = replace(gateway, old_expression,
        '        adhesion_date = (query.get("adhesion_date") or [""])[0]\n'
        '        if adhesion_date:\n'
        '            if dt.date.fromisoformat(adhesion_date).isoformat() != adhesion_date:\n'
        '                raise ValueError("invalid_adhesion_date")\n'
        '            options = {"requireSingleActivity": True, "adhesionDate": adhesion_date}\n'
        '            return "globalThis.__TN_TOA_DIRECT_LOOKUP__(" + json.dumps(contract) + ", " + json.dumps(options) + ")"\n'
        + old_expression)

    lookup = '  async function lookupContractDirect(contract, options = {}) {'
    helpers = source_extension.split('  function selectMirroredAdhesionActivity(', 1)[1].split(lookup, 1)[0]
    extension = replace(extension, lookup, '  function selectMirroredAdhesionActivity(' + helpers + lookup)
    start = '      if (options.requireSingleActivity === true && options.adhesionDate) {'
    end = '      } else if (options.requireSingleActivity === true) {'
    branch = start + source_extension.split(start, 1)[1].split(end, 1)[0] + end
    extension = replace(extension, '      if (options.requireSingleActivity === true) {', branch)
    for source in (app, secondary, gateway):
        ast.parse(source)
    return app, secondary, bridge, gateway, extension
