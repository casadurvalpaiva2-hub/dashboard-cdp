import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# 1. Configuração de Página e Identidade Visual
st.set_page_config(page_title="Gestão Casa Durval Paiva", layout="wide", page_icon="🏥")

st.markdown("""
    <style>
    /* Transforma a área da seta lateral em um botão flutuante visível */
    [data-testid="stSidebarCollapsedControl"] {
        background-color: #E31D24 !important; /* Vermelho institucional */
        border-radius: 0 10px 10px 0 !important; /* Arredonda as bordas direitas */
        width: 50px !important;
        height: 50px !important;
        top: 10px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.2) !important;
    }

    /* Muda a cor da setinha (>>) para branco para contrastar com o vermelho */
    [data-testid="stSidebarCollapsedControl"] svg {
        fill: white !important;
        color: white !important;
        width: 30px !important;
        height: 30px !important;
    }
    
    /* Ajuste para o conteúdo não ficar colado no topo no celular */
    @media (max-width: 640px) {
        .block-container {
            padding-top: 4rem !important;
        }
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

# --- NAVEGAÇÃO ---
st.sidebar.title("MENU GESTÃO")
menu = st.sidebar.radio("Ir para:", [
    "📊 Painel Geral", 
    "🏢 Parceiros e Projetos", 
    "💰 Registrar Doação", 
    "📞 Contatos Diretos"
])

# --- 1. DASHBOARD GERAL ---
if menu == "📊 Painel Geral" or menu == "📊 Dashboard Geral":
    st.title("Dashboard DI 💻")
    st.markdown("---")
    
    # Carrega os dados
    df_doacoes = run_query("SELECT * FROM Doacao")
    
    if not df_doacoes.empty:
        # BLINDAGEM: Garante que os valores são números e datas são datas, evitando tela branca!
        df_doacoes['valor_estimado'] = pd.to_numeric(df_doacoes['valor_estimado'], errors='coerce').fillna(0)
        df_doacoes['data_doacao'] = pd.to_datetime(df_doacoes['data_doacao'], errors='coerce')
        
        # --- LINHA 1: MÉTRICAS (Cards no topo) ---
        col1, col2, col3 = st.columns(3)
        
        total = df_doacoes['valor_estimado'].sum()
        qtd = len(df_doacoes)
        media = total / qtd if qtd > 0 else 0
        
        with col1:
            st.metric("💰 Arrecadação Total", f"R$ {total:,.2f}")
        with col2:
            st.metric("📦 Total de Doações", f"{qtd}")
        with col3:
            st.metric("📈 Média por Doação", f"R$ {media:,.2f}")

        st.markdown("---")

        # --- LINHA 2: GRÁFICOS LADO A LADO ---
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("#### 📊 Distribuição por Categoria")
            # Agrupa os dados e colore de Vermelho Institucional
            dados_cat = df_doacoes.groupby('tipo_doacao')['valor_estimado'].sum().reset_index()
            dados_cat = dados_cat.set_index('tipo_doacao')
            st.bar_chart(dados_cat, color="#E31D24") 

        with c2:
            st.markdown("#### 📅 Evolução Mensal")
            # Remove datas vazias para não quebrar o gráfico e colore de Amarelo
            df_temporal = df_doacoes.dropna(subset=['data_doacao']).copy()
            if not df_temporal.empty:
                df_temporal['Mes'] = df_temporal['data_doacao'].dt.strftime('%m/%Y')
                dados_tempo = df_temporal.groupby('Mes')['valor_estimado'].sum().reset_index()
                dados_tempo = dados_tempo.set_index('Mes')
                st.line_chart(dados_tempo, color="#FFF200")
            else:
                st.info("Datas não cadastradas para exibir evolução.")

        st.markdown("---")

        # --- LINHA 3: TABELA OCULTA ---
        with st.expander("🔍 Ver Lista Detalhada de Lançamentos"):
            st.dataframe(df_doacoes.sort_values(by='data_doacao', ascending=False), use_container_width=True, hide_index=True)

    else:
        st.info("Nenhum dado cadastrado ainda.")

# --- 2. PARCEIROS E PROJETOS ---
elif menu == "🏢 Parceiros e Projetos":
    st.title("Gestão de Parceiros e Projetos")
    tab1, tab2 = st.tabs(["🏢 Parceiros", "🚀 Projetos"])
    
    with tab1:
        st.subheader("🏢 Gestão de Parceiros")
        
        # 1. Exibição da Tabela Atual
        df_p = run_query("SELECT * FROM Parceiro")
        st.dataframe(df_p, use_container_width=True, hide_index=True)
        
        # 2. Formulário de Cadastro de Novo Parceiro
        with st.expander("➕ Cadastrar Novo Parceiro / Instituição"):
            with st.form("form_novo_parceiro", clear_on_submit=True):
                # Pegamos as colunas reais para evitar erro de nome
                colunas_p = df_p.columns.tolist()
                
                # Mapeando campos (ajuste conforme os nomes que aparecem na sua tabela)
                # Geralmente: [0] id, [1] nome/empresa, [2] tipo/contato...
                label_nome = colunas_p[1] if len(colunas_p) > 1 else "Nome"
                
                novo_nome = st.text_input(f"Nome da Instituição ({label_nome})")
                
                # Se houver mais colunas, criamos campos extras dinamicamente
                extra_campos = {}
                for col in colunas_p[2:]: # Pula o ID e o Nome
                    extra_campos[col] = st.text_input(f"Informação: {col}")
                
                if st.form_submit_button("Salvar Parceiro"):
                    if novo_nome:
                        # Montando a Query Dinâmica
                        cols_sql = [label_nome] + list(extra_campos.keys())
                        placeholders = ", ".join(["?"] * len(cols_sql))
                        nomes_cols = ", ".join(cols_sql)
                        valores = [novo_nome] + list(extra_campos.values())
                        
                        query_insert = f"INSERT INTO Parceiro ({nomes_cols}) VALUES ({placeholders})"
                        
                        if run_insert(query_insert, valores, f"Cadastrou Parceiro: {novo_nome}"):
                            st.success(f"Parceiro '{novo_nome}' adicionado com sucesso!")
                            st.rerun()
                    else:
                        st.warning("O nome da instituição é obrigatório.")

# --- 3. REGISTRAR DOAÇÃO ---
elif menu == "💰 Registrar Doação":
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

# --- 4. CONTATOS DIRETOS ---
elif menu == "📞 Contatos Diretos":
    st.title("Agenda de Contatos Diretos")
    
    # 1. Exibição da Tabela
    df_contatos = run_query("SELECT * FROM Contato_Direto")
    st.dataframe(df_contatos, use_container_width=True, hide_index=True)
    
    # 2. Formulário com Vínculo
    with st.expander("➕ Adicionar Novo Contato"):
        # Buscamos os parceiros para o usuário selecionar pelo nome
        df_p_contatos = run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro")
        
        if not df_p_contatos.empty:
            with st.form("form_contato_direto", clear_on_submit=True):
                nome_c = st.text_input("Nome do Contato")
                cargo = st.text_input("Cargo")
                telefone = st.text_input("Telefone/WhatsApp")
                
                # Seleção do Parceiro (O pulo do gato!)
                parceiro_nome = st.selectbox("Vincular ao Parceiro/Instituição", df_p_contatos['nome_instituicao'].tolist())
                
                if st.form_submit_button("Salvar Contato"):
                    if nome_c:
                        # Recupera o ID do parceiro selecionado
                        id_venculado = df_p_contatos[df_p_contatos['nome_instituicao'] == parceiro_nome]['id_parceiro'].values[0]
                        
                        # Ajuste os nomes das colunas abaixo conforme seu banco (ex: id_parceiro, nome_contato, etc)
                        query_c = "INSERT INTO Contato_Direto (id_parceiro, nome_contato, cargo, telefone) VALUES (?,?,?,?)"
                        params_c = (int(id_venculado), nome_c, cargo, telefone)
                        
                        if run_insert(query_c, params_c, f"Cadastrou contato: {nome_c} para {parceiro_nome}"):
                            st.success(f"Contato {nome_c} vinculado a {parceiro_nome} com sucesso!")
                            st.rerun()
                    else:
                        st.error("O nome do contato é obrigatório.")
        else:
            st.warning("Cadastre um Parceiro antes de adicionar contatos.")