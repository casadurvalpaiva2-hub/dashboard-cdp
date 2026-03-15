import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import streamlit as st

# 1. Defina sua senha (ou busque de um banco de dados/secrets)
SENHA_MESTRA = "CDP2026" # Altere para uma senha forte

def verificar_login():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown("<h1 style='text-align: center;'> Sistema interno - CDP (DI)</h1>", unsafe_allow_html=True)
        
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
    "**PARCEIROS/PROJETOS**", 
    "**REGISTRAR DOAÇÃO**", 
    "**CONTATOS**"
])

# --- 1. DASHBOARD GERAL ---
if menu == "**PAINEL GERAL**":
    st.title("DASHBBOARD DI")
    
    df_doacoes = run_query("SELECT * FROM Doacao")
    
    if not df_doacoes.empty:
        # Tratamento de dados
        df_doacoes['data_doacao'] = pd.to_datetime(df_doacoes['data_doacao'])
        
        # Filtro de Ano
        anos = sorted(df_doacoes['data_doacao'].dt.year.unique(), reverse=True)
        ano_sel = st.selectbox("**Selecione o ano para análise:**", anos)
        
        # --- A MÁGICA ACONTECE AQUI ---
        # Criamos um NOVO dataframe que contém APENAS os dados do ano escolhido
        df_final = df_doacoes[df_doacoes['data_doacao'].dt.year == ano_sel]
        
        

        # 1. MÉTRICAS (Usando df_final)
        c1, c2, c3 = st.columns(3)
        total = df_final['valor_estimado'].sum()
        qtd = len(df_final)
        media = total / qtd if qtd > 0 else 0
        
        c1.metric("**Arrecadação no ano**", f"R$ {total:,.2f}")
        c2.metric("**Doações no ano**", f"{qtd}")
        c3.metric("**Média do período**", f"R$ {media:,.2f}")

        st.markdown("---")

        # 2. GRÁFICOS (Também usando df_final)
        col_esq, col_dir = st.columns(2)
        
        with col_esq:
            st.subheader("📊 Por categoria")
            dados_cat = df_final.groupby('tipo_doacao')['valor_estimado'].sum()
            st.bar_chart(dados_cat, color="#E31D24") # Vermelho Institucional

        with col_dir:
            st.subheader("📈 Evolução mensal")
            # Agrupa por mês dentro do ano selecionado
            df_final['Mes'] = df_final['data_doacao'].dt.strftime('%m - %b')
            dados_mes = df_final.groupby('Mes')['valor_estimado'].sum()
            st.line_chart(dados_mes, color="#FFF200") # Amarelo Institucional

        st.markdown("---")

        # 3. TABELA (Apenas o que foi filtrado)
        with st.expander(f"**VER TODOS OS LANÇAMENTOS DE {ano_sel} 🔍**"):
            st.dataframe(df_final.sort_values(by='data_doacao', ascending=False), 
                         use_container_width=True, hide_index=True)

    else:
        st.info("Nenhum dado encontrado no banco de dados.")

# --- 2. PARCEIROS E PROJETOS ---
elif menu == "**PARCEIROS/PROJETOS**":
    st.title("**Gestão de parceiros e projetos**")
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
                    nome = st.text_input("Nome da Instituição")
                    data = st.date_input("Data de Adesão")
                with col2:
                    status = st.selectbox("Status", ["Ativo", "Inativo"])
                    cat_nome = st.selectbox("Categoria Principal", options=list(opcoes_cat.keys()))
                    sub_txt = st.text_input("Subcategoria / Detalhe")

                if st.form_submit_button("Salvar"):
                    if nome:
                        id_cat = opcoes_cat[cat_nome]
                        # SQL seguro: se a coluna 'subcategory' não existir, ele salva apenas o básico
                        try:
                            ins = "INSERT INTO Parceiro (nome_instituicao, data_adesao, status, id_categoria, subcategory) VALUES (?,?,?,?,?)"
                            run_insert(ins, (nome, data.strftime('%Y-%m-%d'), status, id_cat, sub_txt))
                        except:
                            ins = "INSERT INTO Parceiro (nome_instituicao, data_adesao, status, id_categoria) VALUES (?,?,?,?)"
                            run_insert(ins, (nome, data.strftime('%Y-%m-%d'), status, id_cat))
                        
                        st.success("Cadastrado!")
                        st.rerun()

# --- 3. REGISTRAR DOAÇÃO ---
elif menu == "**REGISTRAR DOAÇÃO**":
    st.title("Entrada de Recursos")
    
    # Buscamos os nomes para o usuário escolher, mas guardamos o ID
    df_p = run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro")
    
    if not df_p.empty:
        with st.form("nova_doacao"):
            # O usuário vê o nome
            nome_sel = st.selectbox("Selecione o Parceiro", df_p['nome_instituicao'].tolist())
            valor = st.number_input("Valor Estimado", min_value=0.0)
            tipo = st.selectbox("Tipo", ["Financeira", "Vestuário", "Alimentos", "Serviços"])
            data = st.date_input("Data", datetime.now())
            desc = st.text_area("Descrição")
            
            # O sistema recupera o ID correto para o SQL
            id_p = df_p[df_p['nome_instituicao'] == nome_sel]['id_parceiro'].values[0]
            
            if st.form_submit_button("Confirmar Doação"):
                run_insert("""
                    INSERT INTO Doacao (id_parceiro, valor_estimado, tipo_doacao, data_doacao, descricao) 
                    VALUES (?,?,?,?,?)""", 
                    (int(id_p), valor, tipo, data.strftime('%Y-%m-%d'), desc))
                st.success(f"Doação de {nome_sel} registrada!")
                st.balloons()
    else:
        st.error("Cadastre um parceiro na tabela 'Parceiro' antes de continuar.")

# --- 4. CONTATOS DIRETO ---
elif menu == "**CONTATOS**":
    st.title("👤 Agenda de Contatos Diretos")

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
    with st.expander("➕ Adicionar Novo Contato"):
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
                
                parceiro_nome = st.selectbox("Vincular à Instituição", 
                                           options=df_p_contatos['nome_instituicao'].tolist())

                if st.form_submit_button("Salvar Contato"):
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

# 3. O botão de sair
if st.sidebar.button("Sair", use_container_width=True):
    st.session_state.clear()
    st.rerun()