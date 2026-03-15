import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="Dashboard Casa Durval Paiva", layout="wide")

# Estilo para as métricas
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 40px; color: #E63946; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏥 Sistema de Monitoramento - Casa Durval Paiva")
st.markdown("---")

caminho_banco = r"C:\Users\User\Desktop\PROJETO CDP\MeusContatos.db"

try:
    conn = sqlite3.connect(caminho_banco)
    # Lendo a tabela 'Doacao' que confirmamos que existe
    df = pd.read_sql_query("SELECT * FROM Doacao", conn)
    conn.close()

    # --- BARRA LATERAL (Filtros) ---
    st.sidebar.header("🔍 Filtros de Busca")
    
    # Ajustado para 'tipo_doacao' que é o que aparece na sua tabela
    coluna_filtro = 'tipo_doacao' 
    tipos = ["Todos"] + sorted(df[coluna_filtro].unique().tolist())
    tipo_selecionado = st.sidebar.selectbox("Selecione a Categoria:", tipos)

    # Aplicando o filtro
    if tipo_selecionado != "Todos":
        df_filtrado = df[df[coluna_filtro] == tipo_selecionado]
    else:
        df_filtrado = df

    # --- MÉTRICAS ---
    # Ajustado para 'valor_estimado' conforme sua imagem
    total_arrecadado = df_filtrado['valor_estimado'].sum()
    quantidade = len(df_filtrado)
    
    m1, m2 = st.columns(2)
    m1.metric("Total no Filtro", f"R$ {total_arrecadado:,.2f}")
    m2.metric("Qtd. de Doações", quantidade)

    # --- VISUALIZAÇÃO ---
    st.markdown("### 📊 Detalhamento das Doações")
    
    col1, col2 = st.columns([1, 1])

    with col1:
        st.write("📋 **Tabela de Dados**")
        # Mostrando colunas específicas para ficar mais limpo
        colunas_exibir = ['valor_estimado', 'tipo_doacao', 'data_doacao', 'descricao']
        st.dataframe(df_filtrado[colunas_exibir], use_container_width=True, hide_index=True)

    with col2:
        st.write("📈 **Valores por Descrição**")
        # Gráfico usando a descrição real da doação
        st.bar_chart(data=df_filtrado, x='descricao', y='valor_estimado', color='#457B9D')

except Exception as e:
    st.error(f"Erro ao carregar o dashboard: {e}")
    st.info("Verifique se os nomes das colunas estão corretos.")
    
    st.markdown("---")
st.subheader("📥 Exportar Relatório")

# Transforma a tabela filtrada em um formato que o navegador entende (CSV)
csv = df_filtrado.to_csv(index=False).encode('utf-8')

st.download_button(
    label="Baixar Relatório em Excel (CSV)",
    data=csv,
    file_name='relatorio_doacoes_durval_paiva.csv',
    mime='text/csv',
)