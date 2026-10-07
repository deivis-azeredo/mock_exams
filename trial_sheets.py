"""
Cadastro, login e controle de período de teste, usando uma Google Planilha
como "banco de dados" de usuários.

- A senha NUNCA é salva em texto puro — só o hash gerado com bcrypt
  (biblioteca padrão de mercado para isso). Mesmo quem tiver acesso direto
  à planilha não consegue ler a senha original.
- O período de teste começa na data de CRIAÇÃO da conta (cadastro), não em
  cada login — assim a pessoa não "ganha dias extras" só por logar de novo.
"""

import datetime

import bcrypt
import gspread
from google.oauth2.service_account import Credentials

ESCOPOS = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CABECALHO_ESPERADO = ["email", "nome", "senha_hash", "primeiro_acesso", "questoes_geradas"]


def conectar_planilha(credenciais_dict, id_planilha):
    creds = Credentials.from_service_account_info(credenciais_dict, scopes=ESCOPOS)
    cliente = gspread.authorize(creds)
    planilha = cliente.open_by_key(id_planilha)
    aba = planilha.sheet1

    primeira_linha = aba.row_values(1)
    if primeira_linha != CABECALHO_ESPERADO:
        aba.update('A1', [CABECALHO_ESPERADO])

    return aba


def _normalizar_email(email):
    return (email or "").strip().lower()


def _hash_senha(senha):
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _conferir_senha(senha, hash_salvo):
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), hash_salvo.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def _buscar_linha_por_email(aba, email):
    """Retorna (indice_linha, dict_linha) ou (None, None) se não existir."""
    email = _normalizar_email(email)
    registros = aba.get_all_records()
    for indice, linha in enumerate(registros, start=2):  # linha 1 é cabeçalho
        if _normalizar_email(linha.get("email", "")) == email:
            return indice, linha
    return None, None


def _montar_status_trial(linha, indice, dias_permitidos):
    primeiro_acesso = datetime.datetime.fromisoformat(linha["primeiro_acesso"])
    dias_passados = (datetime.datetime.now() - primeiro_acesso).days
    return {
        "dias_passados": dias_passados,
        "dias_restantes": max(0, dias_permitidos - dias_passados),
        "expirado": dias_passados > dias_permitidos,
        "primeiro_acesso": primeiro_acesso,
        "linha": indice,
        "questoes_geradas": int(linha.get("questoes_geradas") or 0),
    }


def criar_usuario(aba, email, nome, senha, dias_permitidos):
    """
    Cria uma conta nova. Retorna (sucesso: bool, resultado):
      - sucesso=False, resultado="email_ja_existe"  -> já tem conta com esse e-mail
      - sucesso=True,  resultado=<status_trial dict> -> conta criada e logada
    """
    email = _normalizar_email(email)
    indice_existente, _ = _buscar_linha_por_email(aba, email)
    if indice_existente is not None:
        return False, "email_ja_existe"

    agora = datetime.datetime.now()
    senha_hash = _hash_senha(senha)
    aba.append_row([email, nome.strip(), senha_hash, agora.isoformat(), 0])

    # Recalcula a linha de verdade (mais seguro que "adivinhar" o índice)
    indice, linha = _buscar_linha_por_email(aba, email)
    return True, _montar_status_trial(linha, indice, dias_permitidos)


def autenticar_usuario(aba, email, senha, dias_permitidos):
    """
    Confere e-mail + senha. Retorna (sucesso: bool, resultado):
      - sucesso=False, resultado="credenciais_invalidas" -> e-mail não existe OU senha errada
      - sucesso=True,  resultado=<status_trial dict>
    Propositalmente não diferenciamos "e-mail não existe" de "senha errada" na
    mensagem de erro — evita dar pista pra quem está tentando adivinhar contas.
    """
    indice, linha = _buscar_linha_por_email(aba, email)
    if linha is None:
        return False, "credenciais_invalidas"

    if not _conferir_senha(senha, linha.get("senha_hash", "")):
        return False, "credenciais_invalidas"

    return True, _montar_status_trial(linha, indice, dias_permitidos)


def registrar_questoes_geradas(aba, email, quantidade_questoes):
    """Soma ao total histórico de questões geradas por aquele e-mail."""
    indice, linha = _buscar_linha_por_email(aba, email)
    if indice is None:
        return
    total_anterior = int(linha.get("questoes_geradas") or 0)
    aba.update_cell(indice, 5, total_anterior + quantidade_questoes)
