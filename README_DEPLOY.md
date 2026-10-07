# Como colocar o Gerador de Provas no ar (passo a passo)

Este projeto vira um site de verdade, gratuito, que atualiza sozinho toda vez
que você der push no GitHub. Vai levar uns 20-30 minutos na primeira vez
(só a configuração inicial — depois é só editar código e dar push).

---

## Parte 1 — Subir o código no GitHub

1. Crie uma conta no [github.com](https://github.com) se ainda não tiver.
2. Crie um repositório novo (pode ser privado).
3. Suba todos os arquivos desta pasta para o repositório **exceto**:
   - `.streamlit/secrets.toml.example` pode subir (é só um modelo, sem segredo real)
   - Nunca suba um arquivo `secrets.toml` de verdade com credenciais reais.

---

## Parte 2 — Criar a Google Planilha de controle do trial

1. Crie uma planilha nova no [Google Sheets](https://sheets.google.com).
2. Dê um nome qualquer, ex: "Controle Trial - Gerador de Provas".
3. Pegue o **ID da planilha**: é o trecho da URL entre `/d/` e `/edit`:
   ```
   https://docs.google.com/spreadsheets/d/ESTE_PEDAÇO_AQUI_É_O_ID/edit
   ```
   Guarde esse ID — vai usar no passo 4.
4. Deixe a primeira aba em branco (o próprio app cria o cabeçalho sozinho
   na primeira vez que alguém logar).

---

## Parte 3 — Criar a credencial do Google (conta de serviço)

Isso é necessário para o site conseguir ler/escrever na planilha sozinho,
sem pedir login do Google para o cliente.

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um projeto novo (qualquer nome).
3. No menu, vá em **APIs e Serviços > Biblioteca** e ative estas duas APIs:
   - **Google Sheets API**
   - **Google Drive API**
4. Vá em **APIs e Serviços > Credenciais > Criar Credenciais > Conta de
   serviço**. Dê um nome qualquer (ex: "provagen-bot") e conclua.
5. Clique na conta de serviço criada > aba **Chaves** > **Adicionar chave >
   Criar nova chave > tipo JSON**. Isso baixa um arquivo `.json` — é a sua
   credencial. **Guarde esse arquivo, você vai precisar do conteúdo dele.**
6. Copie o e-mail da conta de serviço (algo como
   `provagen-bot@seu-projeto.iam.gserviceaccount.com` — está dentro do
   JSON, no campo `client_email`).
7. Volte na sua Google Planilha (Parte 2) e clique em **Compartilhar**.
   Cole o e-mail da conta de serviço e dê permissão de **Editor**.
   (Sem esse passo, o app não consegue escrever na planilha.)

---

## Parte 4 — Pegar sua chave da Groq

Se ainda não tiver, crie em [console.groq.com](https://console.groq.com) e
copie a `GROQ_API_KEY`.

**Atenção:** essa chave vai ficar escondida no site (ninguém vê), mas todo
uso feito por qualquer cliente no site consome da sua cota/custo da Groq.

---

## Parte 5 — Publicar no Streamlit Community Cloud (gratuito)

1. Acesse [share.streamlit.io](https://share.streamlit.io) e entre com sua
   conta do GitHub.
2. Clique em **New app**, escolha o repositório que você criou na Parte 1,
   e aponte o arquivo principal como `streamlit_app.py`.
3. **Antes de clicar em Deploy**, vá em **Advanced settings > Secrets** e
   cole algo assim (preenchendo com seus dados reais das Partes 2, 3 e 4):

   ```toml
   GROQ_API_KEY = "sua_chave_groq_aqui"
   ID_PLANILHA_TRIAL = "id_da_planilha_aqui"

   [gcp_service_account]
   type = "service_account"
   project_id = "seu-projeto-id"
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "provagen-bot@seu-projeto.iam.gserviceaccount.com"
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."
   ```

   Todos esses valores (exceto as duas primeiras linhas) vêm direto do
   arquivo `.json` que você baixou na Parte 3 — é só copiar campo por campo.
   **Atenção ao `private_key`**: copie com as quebras de linha como `\n`
   mesmo (o próprio JSON baixado já vem assim).

4. Clique em **Deploy**. Em 1-2 minutos o site está no ar, com uma URL tipo
   `https://seu-app.streamlit.app`.

---

## Como funciona depois de publicado

- Na primeira visita, a pessoa cria uma conta (nome, e-mail e senha, aba
  "Criar conta"). A senha é salva na sua planilha **já criptografada**
  (hash bcrypt) — nem você, olhando a planilha, consegue ver a senha
  original.
- Nas próximas vezes, ela usa a aba "Entrar" com e-mail + senha.
- O período de 7 dias começa a contar a partir da data de **criação da
  conta**, não de cada login.
- Depois de 7 dias daquela data, a conta para de conseguir gerar provas
  (mensagem de "período expirado"), mas ainda consegue logar (só não gera
  prova nova).
- Isso dificulta bastante a burla de "ficar recriando conta" só trocando
  o e-mail — mas não impede 100%: alguém disposto pode sempre criar um
  e-mail novo. Para controle realmente rígido, seria necessário verificar
  o e-mail de verdade (confirmação por link) antes de liberar o uso —
  avise se quiser essa camada extra também.
- Você pode abrir a planilha a qualquer momento para ver quem testou,
  quando começou, e quantas questões cada um gerou no total.
- Para resetar o teste de alguém: abra a planilha e apague a linha da
  pessoa (ou edite a data manualmente).
- Para dar acesso à versão completa: hoje o jeito mais simples é você
  manter **dois apps separados no Streamlit Cloud** (um deployado a partir
  do `streamlit_app.py` de teste, outro de um `streamlit_app.py` sem os
  limites de dias/questões) e mandar o link do segundo quando o cliente
  fechar negócio.

---

## Atualizando o site depois

Qualquer alteração que você fizer no código: só dar `git push` para o
GitHub. O Streamlit Cloud detecta sozinho e redeploya em menos de um
minuto — não precisa fazer nada manual na hospedagem.
