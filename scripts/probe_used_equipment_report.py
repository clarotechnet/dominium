"""Read-only DataSnap discovery. Does not download any report or execute SQL.

Examples:
    python scripts/probe_used_equipment_report.py --contract
    python scripts/probe_used_equipment_report.py --exe "C:\\Imperium\\ClientVCL.exe"
    python scripts/probe_used_equipment_report.py --profile natal --probe --confirm-tcp
"""
from __future__ import annotations
import argparse
import getpass
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"integrations"/"serial_consult"))

from used_equipment_report import (
    PROVIDERS, check_executable,load_contract,probe_prepare_only
)

def main(argv=None):
    parser=argparse.ArgumentParser(description="Sonda de leitura, sem consulta de negócio")
    parser.add_argument("--contract",action="store_true",help="Mostra contrato confirmado offline")
    parser.add_argument("--exe",type=Path,help="Compara versão instalada ClientVCL.exe, sem iniciá-la")
    parser.add_argument("--probe",action="store_true",help="Testa autenticação e prepare, NÃO extrai dados")
    parser.add_argument("--profile",choices=("natal","fortaleza","mossoro","recife"))
    parser.add_argument("--confirm-tcp",action="store_true",help="Confirma rede corporativa/VPN e protocolo legado")
    parser.add_argument("--local-credentials",action="store_true",
                        help="Usa credenciais DPAPI já configuradas no Dominium, sem exibi-las")
    args=parser.parse_args(argv)
    contract=load_contract()
    output={}
    if args.contract:
        output["contract"]={"form":contract["form"],"server_class":contract["server_class"],
                            "providers":PROVIDERS,"state":"offline_only"}
    if args.exe:
        output["executable"]=check_executable(args.exe,contract)
    if args.probe:
        if not args.profile or not args.confirm_tcp:
            parser.error("--probe exige --profile e --confirm-tcp")
        if args.local_credentials:
            from datasnap_client import load_credentials
            creds=load_credentials(ROOT/"config"/"credentials.dat")
            username,password=creds["username"],creds["password"]
        else:
            if not sys.stdin.isatty():
                parser.error("Credenciais manuais requerem terminal interativo")
            username=input("Usuário DataSnap: ").strip()
            password=getpass.getpass("Senha DataSnap: ")
        output["probe"]=probe_prepare_only(args.profile,username,password)
    if not output:
        parser.print_help()
        return 0
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except (OSError,RuntimeError,ValueError) as exc:
        print("Falha segura: "+type(exc).__name__+" (sem consulta ou alteração de estoque)",file=sys.stderr)
        raise SystemExit(2)
