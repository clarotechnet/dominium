"""Small source transformations for the legacy server; no network or writes.

The deployment script must verify the expected whole-file hash, create a
backup, compile the result and test it before replacing a running source.
"""
import ast


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
