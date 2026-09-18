# =============================================================================
# DOMINIUM | MAPA DE RESPONSABILIDADE
#
# IMPERIUM
# - NAO - este arquivo nao envia operacoes ao Imperium.
#
# TOA
# - SIM - sessao, coleta, importacao, inventario ou monitor do TOA.
#
# DOMINIUM COMPARTILHADO
# - A saida pode alimentar o restante do DOMINIUM em modo leitura.
#
# Categoria deste arquivo: TOA.
# Mapa completo: MAPA_DOMINIUM_IMPERIUM_TOA.md
# A ordem executavel abaixo foi preservada para evitar regressao.
# =============================================================================
from getpass import getpass
from pathlib import Path

from datasnap_client import save_credentials


ROOT = Path(__file__).resolve().parent
CREDENTIALS_PATH = ROOT / "config" / "toa_credentials.dat"


def main() -> None:
    print("Configuracao segura do acesso ao Oracle Field Service (TOA)")
    username = input("Login TOA: ").strip()
    password = getpass("Senha TOA: ")
    if not username or not password:
        raise SystemExit("Login e senha sao obrigatorios.")
    save_credentials(CREDENTIALS_PATH, username, password)
    print(f"Credencial protegida pelo Windows salva em {CREDENTIALS_PATH}")


if __name__ == "__main__":
    main()
