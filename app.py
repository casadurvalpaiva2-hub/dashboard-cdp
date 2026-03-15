import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# Configuração de Página
st.set_page_config(page_title="Sistema Integrado CDP", layout="wide")

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

# --- 1. PAINEL GERAL ---
if menu == "📊 Painel Geral":
    st.title("Dashboard DI 💻")
    df_doacoes = run_query("SELECT * FROM Doacao")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Arrecadação Total", f"R$ {df_doacoes['valor_estimado'].sum():,.2f}")
    m2.metric("Total de Doações", len(df_doacoes))
    m3.metric("Média por Doação", f"R$ {df_doacoes['valor_estimado'].mean():,.2f}" if len(df_doacoes)>0 else "0")

    st.markdown("---")
    st.subheader("Visualização por Categoria")
    st.bar_chart(df_doacoes, x='tipo_doacao', y='valor_estimado')

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