import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import streamlit as st

def format_br(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# 1. Defina sua senha (ou busque de um banco de dados/secrets)
SENHA_MESTRA = "CDP2026" # Altere para uma senha forte

def verificar_login():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown("<h1 style='text-align: center;'> Sistema interno - Desenvolvimento Institucional</h1>", unsafe_allow_html=True)
        
        # Centraliza a caixa de login
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            senha = st.text_input("Insira a senha de acesso:", type="password")
            if st.button("Entrar", use_container_width=True):
                if senha == "CDP2026": # Substitua pela sua senha
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Senha incorreta!")
        
        # O PULO DO GATO: Para a execução aqui se não estiver logado
        st.stop() 

# Chama a função logo no início do código
verificar_login()



# --- EXECUÇÃO ---
if verificar_login():
    # AQUI VAI TODO O SEU CÓDIGO ATUAL (Menu, Dashboard, etc.)
    # Se o usuário não estiver logado, ele nunca chegará aqui.
    st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"autenticado": False}))
    
    # ... resto do seu código ...
# 1. Configuração de Página e Identidade Visual
st.set_page_config(page_title="GESTÃO DI", layout="wide", page_icon="🏠")

st.markdown("""
    <style>
    /* 1. Transforma a área da seta em um botão retangular com a palavra MENU */
    [data-testid="stSidebarCollapsedControl"] {
        background-color: #E31D24 !important;
        border-radius: 0 20px 20px 0 !important;
        width: 80px !important; /* Mais largo para caber o texto */
        height: 45px !important;
        top: 15px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 4px 4px 10px rgba(0,0,0,0.2) !important;
    }

    /* 2. Esconde a seta original do Streamlit */
    [data-testid="stSidebarCollapsedControl"] svg {
        display: none !important;
    }

    /* 3. Injeta a palavra "MENU" no lugar da seta */
    [data-testid="stSidebarCollapsedControl"]::before {
        content: "☰ MENU" !important;
        color: white !important;
        font-weight: bold !important;
        font-size: 14px !important;
        font-family: sans-serif !important;
    }
    
    /* 4. Ajuste para o conteúdo não subir demais */
    .main .block-container {
        padding-top: 5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INSERÇÃO DA LOGO ---
# Opção A: Se você tiver o link da imagem na internet
logo_url = "https://casadurvalpaiva.org.br/wp-content/themes/durvalpaiva/dist/img/header/logo.png" # Verifique se este link está ativo ou use o seu
st.sidebar.image(logo_url, width=150) # Ajuste o número 150 até ficar do tamanho que você gosta
st.sidebar.markdown("---")

# Caminho do banco
pasta_atual = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(pasta_atual, 'MeusContatos.db')

# Teste de leitura direta do banco
with sqlite3.connect(db_path) as test_conn:
    res = test_conn.execute("SELECT COUNT(*) FROM Contato_Direto").fetchone()
   

def run_query(query, params=()):
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            return pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        st.error(f"Erro na consulta: {e}")
        return pd.DataFrame()

def run_insert(query, params=()):
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            # Esta linha abaixo registra a ação no Log automaticamente
            cursor.execute("CREATE TABLE IF NOT EXISTS Logs (id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT, data_hora DATETIME)")
            cursor.execute("INSERT INTO Logs (acao, data_hora) VALUES (?,?)", (query[:50], datetime.now().strftime('%d/%m/%Y %H:%M:%S')))
            conn.commit()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        
# --- AJUSTE DEFINITIVO DO BANCO ---
try:
    with sqlite3.connect(db_path) as conn:
        # Tenta adicionar a coluna email se ela não existir
        try:
            conn.execute("ALTER TABLE Contato_Direto ADD COLUMN email TEXT")
        except:
            pass # Se já existir, ele pula
except Exception as e:
    st.error(f"Erro ao atualizar banco: {e}")

# --- NAVEGAÇÃO ---
st.sidebar.title("**MENU GESTÃO**")
menu = st.sidebar.radio("Ir para:", [
    "**PAINEL GERAL**",
    "**RELACIONAMENTO**", 
    "**PARCEIROS/PROJETOS**", 
    "**REGISTRAR DOAÇÃO**", 
    "**CONTATOS**"
    ])

# --- 1. DASHBOARD GERAL ---
if menu == "**PAINEL GERAL**":
    st.title("DASHBOARD DI")
    
    df_doacoes = run_query("SELECT * FROM Doacao")
    
    if not df_doacoes.empty:
        # 1. Tratamento Inicial
        df_doacoes['data_doacao'] = pd.to_datetime(df_doacoes['data_doacao'])
        anos = sorted(df_doacoes['data_doacao'].dt.year.unique(), reverse=True)
        ano_sel = st.selectbox("**Selecione o ano para análise:**", anos)
        
        # 2. Cálculos dos Dados (Ano Atual vs Ano Anterior)
        df_atual = df_doacoes[df_doacoes['data_doacao'].dt.year == ano_sel]
        df_passado = df_doacoes[df_doacoes['data_doacao'].dt.year == (ano_sel - 1)]
        
        # Valores Totais
        total_atual = df_atual['valor_estimado'].sum()
        total_passado = df_passado['valor_estimado'].sum()
        
        # Quantidades
        qtd_atual = len(df_atual)
        qtd_passada = len(df_passado)
        
        # Médias
        media_atual = total_atual / qtd_atual if qtd_atual > 0 else 0
        media_passada = total_passado / qtd_passada if qtd_passada > 0 else 0

       # --- EXIBIÇÃO DAS MÉTRICAS (COLE AQUI) ---
        
        # 1. Primeiro definimos a função de formatar moeda
        def fmt(v): 
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
        c1, c2, c3 = st.columns(3)
        
        # 2. Depois calculamos as variações
        diff_valor = total_atual - total_passado
        diff_qtd = qtd_atual - qtd_passada

        # 3. Lógica para a cor do Delta de Arrecadação
        # Se o valor for negativo, colocamos o sinal de menos ANTES do R$
        texto_delta_v = fmt(diff_valor)
        if diff_valor < 0:
            texto_delta_v = f"- {fmt(abs(diff_valor))}" 

        # 4. Exibimos os cartões (Metrics)
        # O delta de arrecadação agora ficará VERMELHO se cair
        c1.metric("**Arrecadação no ano**", fmt(total_atual), 
                  delta=texto_delta_v if ano_sel-1 in anos else None)
        
        # O delta de doações mostrará a quantidade
        c2.metric("**Doações no ano**", f"{qtd_atual} un", 
                  delta=f"{diff_qtd} vs ano ant." if ano_sel-1 in anos else None)
        
        c3.metric("**Ticket Médio**", fmt(media_atual))

        # --- GRÁFICOS ---
        col_esq, col_dir = st.columns(2)
        
        with col_esq:
            st.subheader("Por categoria")
            dados_cat = df_atual.groupby('tipo_doacao')['valor_estimado'].sum()
            st.bar_chart(dados_cat, color="#E31D24") 

        with col_dir:
            st.subheader("Evolução mensal")
            df_atual['Mes'] = df_atual['data_doacao'].dt.strftime('%m - %b')
            dados_mes = df_atual.groupby('Mes')['valor_estimado'].sum()
            st.line_chart(dados_mes, color="#FFF200")

        st.markdown("---")

        # --- RANKING TOP 5 (Nova Melhoria) ---
        st.subheader("**Maiores doadores do ano** 🏆😎")
        # Busca o nome das instituições fazendo um Join
        query_top = f"""
            SELECT p.nome_instituicao as Parceiro, SUM(d.valor_estimado) as Total
            FROM Doacao d
            JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
            WHERE strftime('%Y', d.data_doacao) = '{ano_sel}'
            GROUP BY Parceiro ORDER BY Total DESC LIMIT 5
        """
        df_top = run_query(query_top)
        if not df_top.empty:
            df_top['Total'] = df_top['Total'].apply(fmt)
            st.table(df_top)

    else:
        st.info("Nenhum dado encontrado no banco de dados.")

# --- 2. PARCEIROS E PROJETOS ---
elif menu == "**PARCEIROS/PROJETOS**":
    st.title("**GESTÃO DE PARCEIROS E PROJETOS**")
    tab1, tab2 = st.tabs(["🏢 **Parceiros**", "📃 **Projetos**"])
    
    with tab1:

        # 1. BUSCA DE DADOS SIMPLIFICADA
        # Se o erro 'subcategory' persistir, o try/except abaixo vai ignorar e rodar o resto
        try:
            query = """
                SELECT p.*, c.nome_categoria 
                FROM Parceiro p 
                LEFT JOIN Categoria_Parceiro c ON p.id_categoria = c.id_categoria
            """
            df_p = run_query(query)
        except:
            df_p = run_query("SELECT * FROM Parceiro")

        # Filtro de Busca
        busca = st.text_input("🔍 Pesquisar parceiro:")
        if busca and not df_p.empty:
            df_p = df_p[df_p['nome_instituicao'].str.contains(busca, case=False)]

        # Exibição da Tabela
        st.dataframe(df_p, use_container_width=True, hide_index=True)

        st.markdown("---")

        # 2. SEÇÃO DE CADASTRO
        with st.expander("**CADASTRAR NOVO PARCEIRO**"):
            # Busca categorias para o menu
            df_cat_list = run_query("SELECT id_categoria, nome_categoria FROM Categoria_Parceiro")
            opcoes_cat = dict(zip(df_cat_list['nome_categoria'], df_cat_list['id_categoria']))
            
            with st.form("form_novo_p", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    nome = st.text_input("Nome da instituição")
                    # Calendário aparece sempre por padrão
                    data_input = st.date_input("Data de adesão")
                    # Checkbox para ignorar a data
                    sem_data = st.checkbox("Não possuo a data de adesão")
                    
                with col2:
                    status = st.selectbox("Status", ["Ativo", "Inativo", "Prospecção"])
                    cat_nome = st.selectbox("Categoria principal", options=list(opcoes_cat.keys()))
                    sub_txt = st.text_input("Subcategoria / Detalhe")

                if st.form_submit_button("Salvar", type="primary"):
                    if nome:
                        id_cat = opcoes_cat[cat_nome]
                        # Se o checkbox estiver marcado, data_final será None (vazio no SQL)
                        data_final = None if sem_data else data_input.strftime('%Y-%m-%d')
                        
                        try:
                            # 1. SQL com as 5 colunas EXATAS do seu banco (image_9f9400.png)
                            sql = """
                                INSERT INTO Parceiro (nome_instituicao, status, id_categoria, data_adesao, subcategoria) 
                                VALUES (?, ?, ?, ?, ?)
                            """
                            
                            # 2. Enviando as 5 variáveis na ordem correta
                            # Note que usamos 'sub_txt' que é o nome da sua variável na linha 231
                            run_insert(sql, (nome, status, id_cat, data_final, sub_txt))
                            
                            st.success(f"✅ {nome} cadastrado com sucesso!")
                            st.rerun() 
                        except Exception as e:
                            st.error(f"Erro técnico ao salvar: {e}")

# --- ABA DE PROJETOS ---
    with tab2:
        st.subheader("HISTÓRICO FINANCEIRO")
        
        # Query que agrupa por Nome do Projeto e Ano da Doação
        query_projetos = """
            SELECT 
                UPPER(nome_projeto) as Projeto,
                strftime('%Y', data_doacao) as Ano,
                COUNT(*) as 'Qtd Repasses',
                SUM(valor_estimado) as Total
            FROM Doacao
            WHERE nome_projeto IS NOT NULL AND nome_projeto != ''
            GROUP BY Projeto, Ano
            ORDER BY Ano DESC, Total DESC
        """
        df_proj = run_query(query_projetos)
        
        if not df_proj.empty:
            # Filtro de Ano para facilitar a busca
            anos_lista = ["Todos"] + sorted(df_proj['Ano'].unique().tolist(), reverse=True)
            ano_escolhido = st.selectbox("Filtrar por ano de recebimento:", anos_lista)
            
            if ano_escolhido != "Todos":
                df_exibir = df_proj[df_proj['Ano'] == ano_escolhido].copy()
            else:
                df_exibir = df_proj.copy()

            # Formatação para o padrão brasileiro R$ 1.234,56
            df_exibir['Total'] = df_exibir['Total'].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            # Exibição da tabela organizada
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
            
            # Resumo rápido para o usuário
            total_geral = df_proj['Total'].sum()
            total_formatado = f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            st.info(f"**Captação total acumulada (Todos os anos):** {total_formatado}")
            
        else:
            st.info("Ainda não existem doações vinculadas a projetos específicos.")

# --- 3. REGISTRAR DOAÇÃO ---
# --- 3. REGISTRAR DOAÇÃO ---
elif menu == "**REGISTRAR DOAÇÃO**":
    st.title("ENTRADA DE RECURSOS")
    
    # 1. Buscamos os nomes para o usuário escolher
    df_p = run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro")
    
    if not df_p.empty:
        with st.form("nova_doacao", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            
            with col_a:
                # --- AQUI ESTÁ A MUDANÇA: ADICIONANDO A OPÇÃO NEUTRA ---
                opcoes_p = ["Selecione o parceiro..."] + df_p['nome_instituicao'].tolist()
                nome_sel = st.selectbox("Selecione o parceiro/fonte", opcoes_p)
                
                valor = st.number_input("Valor do repasse (R$)", min_value=0.0)
                data = st.date_input("Data do recebimento", datetime.now())

            with col_b:
                # Campo de projeto que você já usava
                projeto = st.text_input("Nome do Projeto / Emenda / Finalidade", placeholder="Ex: Projeto Vida")
                tipo = st.selectbox("Tipo de recurso", ["Financeira", "Vestuário", "Alimentos", "Serviços", "Midiática", "Projetos"])
            
            desc = st.text_area("Observações")
            
            # --- BOTÃO COM VALIDAÇÃO ---
            if st.form_submit_button("Confirmar doação", type="primary"):
                # TRAVA: Se o usuário não escolheu um parceiro, dá erro e não salva
                if nome_sel == "Selecione o parceiro...":
                    st.error("ERRO: Você esqueceu de selecionar o Parceiro!")
                
                elif not projeto: # Aproveitamos para validar o projeto também
                    st.warning("Por favor, informe o nome do Projeto ou Emenda.")
                
                else:
                    # Se passou nas travas, salva no banco
                    id_p = df_p[df_p['nome_instituicao'] == nome_sel]['id_parceiro'].values[0]
                    
                    sql = """
                        INSERT INTO Doacao (id_parceiro, valor_estimado, tipo_doacao, data_doacao, descricao, nome_projeto) 
                        VALUES (?,?,?,?,?,?)
                    """
                    run_insert(sql, (int(id_p), valor, tipo, data.strftime('%Y-%m-%d'), desc, projeto.upper()))
                    
                    st.success(f"✅ Recurso de '{nome_sel}' registrado com sucesso!")
                    st.balloons()
    else:
        st.error("Cadastre um parceiro na aba 'PARCEIROS' antes de registrar uma doação.")

        # --- NOVO: GERENCIAR LANÇAMENTOS RECENTES ---
    st.write("---")
    st.subheader("**LANÇAMENTOS RECENTES**")
    
    # Busca as últimas 5 doações para conferência
    df_recentes = run_query("""
        SELECT d.id_doacao, p.nome_instituicao, d.valor_estimado, d.data_doacao, d.nome_projeto
        FROM Doacao d
        JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
        ORDER BY d.id_doacao DESC LIMIT 5
    """)

    if not df_recentes.empty:
        for _, row in df_recentes.iterrows():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"📌 {row['nome_instituicao']} - {row['nome_projeto']} (R$ {row['valor_estimado']:.2f})")
            with col2:
                st.write(f"📅 {row['data_doacao']}")
            with col3:
                # Botão para excluir o registro específico
                if st.button(f"Excluir #{row['id_doacao']}", key=f"del_{row['id_doacao']}"):
                    run_insert("DELETE FROM Doacao WHERE id_doacao = ?", (int(row['id_doacao']),))
                    st.warning(f"Lançamento #{row['id_doacao']} removido!")
                    st.rerun()
    else:
        st.info("Nenhum lançamento recente encontrado.")

    # --- SEÇÃO DE VISUALIZAÇÃO DE PARCEIROS (MANTIDA IGUAL À SUA) ---
    st.write("---")
    st.subheader("📋 Parceiros Cadastrados")

    # 1. Filtro de Status
    status_filtro = st.selectbox("Filtrar por Status", ["Todos", "Ativo", "Inativo", "Prospecção"])

    # 2. Query com LEFT JOIN
    query_base = """
        SELECT 
            p.id_parceiro as ID,
            p.nome_instituicao as Nome,
            p.data_adesao as 'Data Adesão',
            p.status as Status,
            c.nome_categoria as Categoria
        FROM Parceiro p
        LEFT JOIN Categoria_Parceiro c ON p.id_categoria = c.id_categoria
    """

    # 3. Aplica o filtro
    if status_filtro != "Todos":
        df_viz = run_query(query_base + f" WHERE p.status = '{status_filtro}'")
    else:
        df_viz = run_query(query_base)

    # 4. Exibição da tabela
    if not df_viz.empty:
        st.dataframe(df_viz, use_container_width=True)
    else:
        st.info(f"Nenhum parceiro encontrado com o status: {status_filtro}")

# --- 4. CONTATOS DIRETO ---
elif menu == "**CONTATOS**":
    st.title("**AGENDA**")

    # 1. BUSCA DE DADOS (Usando o nome correto: nome_pessoa)
    query_view = """
        SELECT p.nome_instituicao as Empresa, 
               c.nome_pessoa as Nome, 
               c.cargo as Cargo, 
               c.telefone as WhatsApp, 
               c.email as [E-mail]
        FROM Contato_Direto c
        LEFT JOIN Parceiro p ON c.id_parceiro = p.id_parceiro
    """
    try:
        df_contatos = run_query(query_view)
        if not df_contatos.empty:
            st.dataframe(df_contatos, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum contato cadastrado ainda.")
    except Exception as e:
        st.error(f"Erro ao carregar tabela: {e}")

    st.markdown("---")

    # 2. FORMULÁRIO DE CADASTRO
    with st.expander("NOVO CONTATO"):
        df_p_contatos = run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro")
        

        if not df_p_contatos.empty:
            with st.form("form_contato_final", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    nome_f = st.text_input("Nome da Pessoa")
                    email_f = st.text_input("E-mail")
                with c2:
                    cargo_f = st.text_input("Cargo")
                    tel_f = st.text_input("Telefone")
                
                parceiro_nome = st.selectbox("Vincular à instituição", 
                                           options=df_p_contatos['nome_instituicao'].tolist())

                if st.form_submit_button("Salvar contato"):
                    if nome_f:
                        try:
                            # Pega o ID do parceiro selecionado
                            id_p = df_p_contatos[df_p_contatos['nome_instituicao'] == parceiro_nome]['id_parceiro'].values[0]
                            
                            # SQL usando 'nome_pessoa' (confirmado no seu DB Browser)
                            sql = "INSERT INTO Contato_Direto (id_parceiro, nome_pessoa, cargo, telefone, email) VALUES (?, ?, ?, ?, ?)"
                            run_insert(sql, (int(id_p), nome_f, cargo_f, tel_f, email_f))
                            
                            st.success(f"✅ {nome_f} cadastrado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                    else:
                        st.warning("Por favor, digite o nome da pessoa.")
        else:
            st.warning("⚠️ Você precisa cadastrar um Parceiro antes de adicionar contatos.")

            # --- TUDO O QUE JÁ EXISTE NA SIDEBAR FICA ACIMA ---

st.sidebar.subheader("Extrair dados")

# 1. Download do Banco de Dados Completo (para abrir no DB Browser)
with open(db_path, "rb") as f:
    st.sidebar.download_button(
        label="Baixar arquivo .db",
        data=f,
        file_name="MeusContatos_Nuvem.db",
        mime="application/octet-stream"
    )

# 2. Download em Excel (mais fácil para relatórios)
import pandas as pd
from io import BytesIO

if st.sidebar.button("Gerar planilha Excel"):
    df_excel = run_query("SELECT * FROM Contato_Direto")
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Contatos')
    
    st.sidebar.download_button(
        label="Clique para baixar Excel",
        data=output.getvalue(),
        file_name="contatos_extraidos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# 3. O botão de sair
if st.sidebar.button("Sair", use_container_width=True):
    st.session_state.clear()
    st.rerun()

    st.sidebar.markdown("---")

# --- COLOGUE ISSO NO FINAL DO ARQUIVO, NA MARGEM ESQUERDA ---
elif menu == "**RELACIONAMENTO**":
    st.title("RELACIONAMENTO")
    
    # 1. BUSCA OS DADOS DA VIEW
    df_rel = run_query("SELECT * FROM View_Relacionamento_Critico")

    if not df_rel.empty:
        # --- FILTRO DE URGÊNCIA (O que evita a repetição) ---
        st.subheader("**STATUS**")
        status_filtro = st.radio("Filtrar por urgência:", 
                                ["Todos", "🔴 CRÍTICO", "🟡 ATENÇÃO", "🟢 EM DIA"], 
                                horizontal=True)
        
        # Lógica para filtrar o DataFrame baseado na bolinha selecionada
        if status_filtro != "Todos":
            # Extraímos apenas a palavra (ex: CRÍTICO) para filtrar
            termo = status_filtro.split(" ")[1] 
            df_display = df_rel[df_rel['Status_Relacionamento'].str.contains(termo)]
        else:
            df_display = df_rel
        
        # EXIBE APENAS UMA TABELA
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.success("✅ Todos os contatos estão em dia!")

    st.divider()


    # 2. Formulário para registrar nova conversa
    st.subheader("**Registrar nova interação**")
    df_p = run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro ORDER BY nome_instituicao")
    
    with st.form("form_crm", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            # Aqui usamos o nome em maiúsculo como você pediu
            p_sel = st.selectbox("Parceiro", ["Selecione..."] + df_p['nome_instituicao'].tolist())
            data_c = st.date_input("Data de contato", datetime.now())
        with col2:
            prox_c = st.date_input("Agendar retorno")
            
        txt = st.text_area("Descrição da conversa").upper() # Força maiúsculo aqui também
        
        if st.form_submit_button("Salvar histórico"):
            if p_sel != "Selecione...":
                id_parc = df_p[df_p['nome_instituicao'] == p_sel]['id_parceiro'].values[0]
                sql = """
                    INSERT INTO Registro_Relacionamento 
                    (id_parceiro, data_interacao, descricao_do_que_foi_feito, proxima_acao_data)
                    VALUES (?, ?, ?, ?)
                """
                run_insert(sql, (int(id_parc), data_c.strftime('%Y-%m-%d'), txt, prox_c.strftime('%Y-%m-%d')))
                st.success("Histórico salvo!")
                st.rerun()
            else:
                st.error("Por favor, selecione um parceiro.")

# --- NOVO: GRÁFICO DE SAÚDE DA BASE (CRM) ---
        st.markdown("---")
        st.subheader("**Saúde da base de doadores**")
        
        # 1. Buscamos os dados da sua View de Relacionamento
        df_saude = run_query("SELECT Status_Relacionamento, COUNT(*) as qtd FROM View_Relacionamento_Critico GROUP BY Status_Relacionamento")
        
        if not df_saude.empty:
            import plotly.express as px
            
            # 2. Criamos o gráfico de rosca
            # Definimos as cores para bater com o que você já usa: Vermelho para Crítico, etc.
            cores_map = {
    "🔴 CRÍTICO (+3 meses)": "#FF4B4B", 
    "🟡 ATENÇÃO (+45 dias)": "#FFA500", 
    "🟢 EM DIA": "#00CC96"
}
            
            fig = px.pie(
                df_saude, 
                values='qtd', 
                names='Status_Relacionamento',
                hole=0.5,
                color='Status_Relacionamento',
                color_discrete_map=cores_map
            )
            
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(showlegend=False, height=350, margin=dict(t=0, b=0, l=0, r=0))
            
            # 3. Exibimos o gráfico e um pequeno insight
            col_graph, col_txt = st.columns([2, 1])
            with col_graph:
                st.plotly_chart(fig, use_container_width=True)
            
            with col_txt:
                total_parceiros = df_saude['qtd'].sum()
                criticos = df_saude[df_saude['Status_Relacionamento'].str.contains("CRÍTICO")]['qtd'].sum() if any("CRÍTICO" in s for s in df_saude['Status_Relacionamento']) else 0
                percent_critico = (criticos / total_parceiros) * 100
                
                st.metric("Parceiros com registro", total_parceiros)
                st.warning(f"⚠️ {percent_critico:.1f}% da sua base está em estado **CRÍTICO**.")
                st.write("Isso significa que esses parceiros não recebem contato há mais de 1 ano.")
        else:
            st.info("Ainda não há dados de relacionamento para gerar o gráfico.")
            c1.metric(
    "**Arrecadação no ano**", 
    fmt(total_atual), 
    delta=fmt(diff_valor), 
    delta_color="normal" # Isso garante que negativo = vermelho/baixo
)