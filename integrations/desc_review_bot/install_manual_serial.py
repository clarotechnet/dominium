"""Install the manual Atlas helper without replacing the live history implementation."""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def patch_server(source: str) -> str:
    if 'createManualSerialReview' in source:
        if all(marker in source for marker in ("'/serial-lookup'", "'/serial-apply'", 'operator_session:d.review_session', 'capabilities:{manual_serial:true}')):
            return source
        raise ValueError('Instalação manual parcial; examine o código antes de aplicar')
    anchor = "const PREFIX='/desc-review';"
    if source.count(anchor) != 1:
        raise ValueError('Servidor DESC diverge do ponto de instalação esperado')
    source = source.replace(anchor, "const {createManualSerialReview}=require('./manualSerial');\n" + anchor, 1)
    store = re.findall(r'^  const store=createReviewStore\(.*\);$', source, re.MULTILINE)
    if len(store) != 1:
        raise ValueError('Store DESC não identificado de forma única')
    source = source.replace(store[0], store[0] + '\n  const manualSerial=createManualSerialReview({store,lookupSerials,now,scan:()=>scan()});', 1)
    anchor = "    if(req.method==='POST'&&url.pathname===PREFIX+'/decision')"
    if source.count(anchor) != 1:
        raise ValueError('Rota de revisão DESC diverge do esperado')
    routes = """    if(req.method==='POST'&&url.pathname===PREFIX+'/serial-lookup'){const d=await body(req);json(res,200,await manualSerial.lookup(d,{actor:d.actor||session.actor,csrf:session.csrf,operator_session:d.review_session||session.csrf}));return true;}
    if(req.method==='POST'&&url.pathname===PREFIX+'/serial-apply'){const d=await body(req);json(res,200,await manualSerial.apply(d,{actor:d.actor||session.actor,csrf:session.csrf,operator_session:d.review_session||session.csrf}));return true;}
"""
    source = source.replace(anchor, routes + anchor, 1)
    anchor = '{...status,csrf:session.csrf,batches:'
    if source.count(anchor) != 1:
        raise ValueError('Estado DESC não identificado; capacidade manual não foi anunciada')
    return source.replace(anchor, '{...status,capabilities:{manual_serial:true},csrf:session.csrf,batches:', 1)


def patch_proxy(source: str) -> str:
    match = re.search(r"'POST':\s*\{([^}]+)\}", source)
    if match is None or not all("'" + route + "'" in match.group(1) for route in ('decision', 'refresh', 'technician', 'manual')):
        raise ValueError('Allowlist privada de revisão não identificada')
    additions = [repr(route) for route in ('serial-lookup', 'serial-apply') if repr(route) not in match.group(1)]
    if not additions:
        return source
    return source[:match.end() - 1] + ', ' + ', '.join(additions) + source[match.end() - 1:]


def preserved_bytes(original: bytes, updated: str) -> bytes:
    if b'\r\n' in original:
        updated = updated.replace('\n', '\r\n')
    return updated.encode('utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bot-root', type=Path, default=Path(r'\\wsl.localhost\Ubuntu\home\technet\BotDMV'))
    parser.add_argument('--relay-root', type=Path, default=Path(r'C:\DominiumRuntime\DescRelay-20261010'))
    parser.add_argument('--node', type=Path, default=Path(r'C:\Program Files\nodejs\node.exe'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    server_path = args.bot_root / 'src' / 'descReview' / 'server.js'
    proxy_path = args.relay_root / 'desc_review_proxy.py'
    helper_path = args.bot_root / 'src' / 'descReview' / 'manualSerial.js'
    original_server = server_path.read_bytes()
    original_proxy = proxy_path.read_bytes()
    server = patch_server(original_server.decode('utf-8').replace('\r\n', '\n'))
    proxy = patch_proxy(original_proxy.decode('utf-8').replace('\r\n', '\n'))
    helper = (Path(__file__).parent / 'src' / 'descReview' / 'manualSerial.js').read_bytes()
    with tempfile.TemporaryDirectory(prefix='dominium-manual-check-') as temp:
        for name, data in [('server.js', server.encode('utf-8')), ('manualSerial.js', helper)]:
            staged = Path(temp) / name
            staged.write_bytes(data)
            check = subprocess.run([str(args.node), '--check', str(staged)], capture_output=True, check=False)
            if check.returncode:
                raise ValueError('Verificação de sintaxe falhou; nenhum arquivo foi instalado')
    compile(proxy, 'desc_review_proxy.py', 'exec')
    if not args.apply:
        print('CHECK_OK: patch cirúrgico validado; use --apply para instalar')
        return
    if server_path.read_bytes() != original_server or proxy_path.read_bytes() != original_proxy:
        raise ValueError('Arquivos mudaram durante a validação; nenhuma instalação aplicada')
    backup = args.relay_root / 'backups' / ('manual-serial-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    for target in (server_path, proxy_path, helper_path):
        if target.exists():
            shutil.copy2(target, backup / target.name)
    changes = [(helper_path, helper), (server_path, preserved_bytes(original_server, server)),
               (proxy_path, preserved_bytes(original_proxy, proxy))]
    completed = []
    try:
        for target, data in changes:
            temporary = target.with_name(target.name + '.manual-serial.tmp')
            temporary.write_bytes(data)
            temporary.replace(target)
            completed.append(target)
    except OSError:
        for target in reversed(completed):
            saved = backup / target.name
            if saved.exists():
                shutil.copy2(saved, target)
            elif target == helper_path:
                target.unlink(missing_ok=True)
        raise
    print('INSTALLED: consulta manual e capacidade adicionadas; histórico, core e dados preservados')
    print('Reinicie o relay Windows e o processo Bot para carregar os módulos. Modo de teste permanece ativo.')


if __name__ == '__main__':
    main()
