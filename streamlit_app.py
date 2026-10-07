import datetime

import streamlit as st
from groq import Groq

import core_prova
import trial_sheets

# ---------------------------------------------------------------------------
# Configuração da versão de teste
# ---------------------------------------------------------------------------
DIAS_TESTE = 7
MAX_QUESTOES_TESTE = 5
SENHA_MINIMA = 6

st.set_page_config(page_title="Gerador de Provas IA", page_icon="📝", layout="centered")


# ---------------------------------------------------------------------------
# Conexão com a planilha de controle (cacheada — não reconecta a cada clique)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def obter_aba_planilha():
    credenciais = dict(st.secrets["gcp_service_account"])
    id_planilha = st.secrets["ID_PLANILHA_TRIAL"]
    return trial_sheets.conectar_planilha(credenciais, id_planilha)


@st.cache_resource(show_spinner=False)
def obter_cliente_groq():
    return Groq(api_key=st.secrets["GROQ_API_KEY"])


def _logar(email, nome, registro):
    st.session_state["usuario"] = {"nome": nome, "email": email}
    st.session_state["registro_trial"] = registro


# ---------------------------------------------------------------------------
# Tela de autenticação (cadastro + login)
# ---------------------------------------------------------------------------
def tela_autenticacao():
    st.title("📝 Gerador de Provas com IA")
    st.caption(f"Versão de teste — {DIAS_TESTE} dias, até {MAX_QUESTOES_TESTE} questões por prova.")

    aba_entrar, aba_criar_conta = st.tabs(["Entrar", "Criar conta"])

    with aba_entrar:
        with st.form("form_login"):
            email = st.text_input("E-mail", key="login_email")
            senha = st.text_input("Senha", type="password", key="login_senha")
            enviado = st.form_submit_button("Entrar")

        if enviado:
            if not email.strip() or not senha:
                st.error("Preencha e-mail e senha.")
            else:
                with st.spinner("Verificando..."):
                    aba = obter_aba_planilha()
                    ok, resultado = trial_sheets.autenticar_usuario(aba, email, senha, DIAS_TESTE)

                if not ok:
                    st.error("E-mail ou senha incorretos.")
                elif resultado["expirado"]:
                    st.error(
                        f"O período de teste de {DIAS_TESTE} dias para **{email}** já terminou "
                        f"(conta criada em {resultado['primeiro_acesso'].strftime('%d/%m/%Y')}).\n\n"
                        f"Entre em contato para liberar a versão completa."
                    )
                else:
                    _logar(email.strip().lower(), email.split("@")[0], resultado)
                    st.rerun()

    with aba_criar_conta:
        with st.form("form_cadastro"):
            nome = st.text_input("Seu nome", key="cad_nome")
            email_cad = st.text_input("Seu e-mail", key="cad_email")
            senha_cad = st.text_input("Crie uma senha", type="password", key="cad_senha")
            senha_cad2 = st.text_input("Confirme a senha", type="password", key="cad_senha2")
            enviado_cad = st.form_submit_button("Criar conta e começar o teste")

        if enviado_cad:
            if not nome.strip() or "@" not in email_cad:
                st.error("Preencha nome e um e-mail válido.")
            elif len(senha_cad) < SENHA_MINIMA:
                st.error(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.")
            elif senha_cad != senha_cad2:
                st.error("As senhas não coincidem.")
            else:
                with st.spinner("Criando sua conta..."):
                    aba = obter_aba_planilha()
                    ok, resultado = trial_sheets.criar_usuario(aba, email_cad, nome, senha_cad, DIAS_TESTE)

                if not ok:
                    st.error("Já existe uma conta com esse e-mail. Use a aba \"Entrar\".")
                else:
                    _logar(email_cad.strip().lower(), nome.strip(), resultado)
                    st.rerun()


# ---------------------------------------------------------------------------
# Tela principal (depois do login)
# ---------------------------------------------------------------------------
def tela_gerador():
    usuario = st.session_state["usuario"]
    registro = st.session_state["registro_trial"]

    st.title("📝 Gerador de Provas com IA")
    st.caption(
        f"Olá, {usuario['nome']}! Dia {registro['dias_passados'] + 1} de {DIAS_TESTE} "
        f"({registro['dias_restantes']} dia(s) restante(s) de teste)."
    )

    arquivos = st.file_uploader(
        "Envie um ou mais PDFs (apostila, capítulo, texto-base)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    quantidade_questoes = st.number_input(
        f"Quantidade de questões de múltipla escolha (máximo {MAX_QUESTOES_TESTE} na versão de teste)",
        min_value=1,
        max_value=MAX_QUESTOES_TESTE,
        value=MAX_QUESTOES_TESTE,
    )

    gerar = st.button("🚀 Gerar prova(s)", type="primary", disabled=not arquivos)

    if gerar and arquivos:
        client = obter_cliente_groq()
        aba = obter_aba_planilha()
        total_geradas_nesta_sessao = 0

        for arquivo in arquivos:
            nome_sem_ext = arquivo.name.rsplit(".", 1)[0]
            with st.status(f"Processando: {arquivo.name}", expanded=True) as status:
                try:
                    texto = core_prova.extrair_texto(arquivo)
                    if not texto:
                        status.update(label=f"{arquivo.name}: PDF sem texto legível", state="error")
                        continue

                    texto_para_ia, foi_reduzido = core_prova.preparar_texto_para_ia(texto)
                    if foi_reduzido:
                        st.write(f"ℹ️ Documento extenso ({len(texto):,} caracteres) — usando amostra representativa.")

                    st.write("🤖 Gerando prova com a IA...")
                    resposta_ia = core_prova.gerar_prova_ia(client, texto_para_ia, nome_sem_ext, quantidade_questoes)

                    st.write("🧩 Interpretando resposta...")
                    dados = core_prova.extrair_json(resposta_ia)

                    st.write("📝 Montando o documento Word...")
                    aviso = (
                        f"VERSÃO DE TESTE — máximo {MAX_QUESTOES_TESTE} questões — "
                        f"gerado em {datetime.datetime.now().strftime('%d/%m/%Y')}"
                    )
                    docx_bytes = core_prova.construir_docx_bytes(dados, nome_sem_ext, aviso_teste=aviso)

                    status.update(label=f"✅ {arquivo.name} pronto!", state="complete")

                    st.download_button(
                        label=f"⬇️ Baixar prova — {nome_sem_ext}.docx",
                        data=docx_bytes,
                        file_name=f"Prova - {nome_sem_ext}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"download_{arquivo.name}",
                    )
                    total_geradas_nesta_sessao += quantidade_questoes

                except Exception as erro:
                    mensagem_erro = str(erro)
                    if "reduce the length" in mensagem_erro or "context" in mensagem_erro.lower():
                        status.update(
                            label=f"❌ {arquivo.name}: texto grande demais para essa quantidade de questões",
                            state="error",
                        )
                    else:
                        status.update(label=f"❌ Erro em {arquivo.name}: {erro}", state="error")

        if total_geradas_nesta_sessao:
            trial_sheets.registrar_questoes_geradas(aba, usuario["email"], total_geradas_nesta_sessao)

    st.divider()
    if st.button("Sair"):
        del st.session_state["usuario"]
        del st.session_state["registro_trial"]
        st.rerun()


# ---------------------------------------------------------------------------
# Roteamento simples
# ---------------------------------------------------------------------------
if "usuario" not in st.session_state:
    tela_autenticacao()
else:
    tela_gerador()
