import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import streamlit as st
import re
from streamlit_option_menu import option_menu

def format_br(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- SISTEMA DE LOGIN ---
# Podes alterar as senhas aqui
contas = {
    "comunicação": {"nome": "Alice/Daniel", "setor": "MARKETING DIGITAL", "senha": "cdp1", "perfil": "operacional"},
    "imprensa": {"nome": "Michelle Phiffer", "setor": "IMPRENSA", "senha": "cdp2", "perfil": "operacional"},
    "projetos": {"nome": "Viviane Moura", "setor": "PROJETOS", "senha": "cdp3", "perfil": "operacional"},
    "gerencia": {"nome": "Helder Coutinho", "setor": "GERÊNCIA", "senha": "Hc!24601", "perfil": "gerencia"}
}

if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.user_data = None

if not st.session_state.autenticado:
    st.title("Desenvolvimento Institucional CDP")
    with st.form("login"):
        user_login = st.text_input("Utilizador (ex: helder.mkt)").lower()
        pass_login = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if user_login in contas and contas[user_login]["senha"] == pass_login:
                st.session_state.autenticado = True
                st.session_state.user_data = contas[user_login]
                st.rerun()
            else:
                st.error("Utilizador ou senha incorretos.")
    st.stop() # Bloqueia o resto do app se não estiver logado

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

# ==========================================
# COLE O CÓDIGO AQUI VVVVVVV
# ==========================================
# --- CRIAÇÃO DA TABELA DE EVENTOS ---
try:
    run_insert("""
        CREATE TABLE IF NOT EXISTS Convidados_Almoco (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes_referencia TEXT,
            segmento TEXT,
            nome TEXT,
            empresa TEXT,
            cargo TEXT,
            telefone TEXT,
            contato_1 BOOLEAN DEFAULT 0,
            contato_2 BOOLEAN DEFAULT 0,
            contato_3 BOOLEAN DEFAULT 0,
            contato_4 BOOLEAN DEFAULT 0,
            confirmado BOOLEAN DEFAULT 0,
            compareceu BOOLEAN DEFAULT 0,
            observacoes TEXT
        )
    """)
except Exception as e:
    st.error(f"Erro ao criar tabela de almoço: {e}")

# --- NAVEGAÇÃO PREMIUM (Substitua o radio por isso) ---
with st.sidebar:
    # O menu retorna o texto selecionado para a variável 'menu'
    menu = option_menu(
        menu_title="MENU", # Título do menu
        options=["PAINEL GERAL", "PARCERIAS", "CONTATOS", "EVENTOS", "DEMANDAS", "REGISTRAR DOAÇÃO","RELACIONAMENTO"],
        icons=["bar-chart-fill", "building", "person-lines-fill", "calendar-event", "stoplights", "cash-coin", "heart-fill",],
        menu_icon="cast", 
        default_index=0,
        styles={
            "container": {
                "padding": "5!important", 
                "background-color": "transparent" # Remove o fundo branco fixo
            },
            "icon": {
                "color": "#E31D24", 
                "font-size": "18px"
            }, 
            "nav-link": {
                "font-size": "14px", 
                "text-align": "left", 
                "margin":"0px", 
                # Removemos cores fixas de texto para o Streamlit decidir conforme o tema
            },
            "nav-link-selected": {
                "background-color": "#E31D24", # Mantém o destaque vermelho da Casa Durval Paiva
                "color": "white" # Garante que o texto no botão selecionado seja branco
            },
        }
    )

# --- 1. DASHBOARD GERAL ---
if menu == "PAINEL GERAL":
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

# ... final do código do PAINEL GERAL ...
        if not df_top.empty:
            df_top['Total'] = df_top['Total'].apply(fmt)
            st.table(df_top)


# --- 2. DEMANDAS (ESTE BLOCO DEVE FICAR COLADO NA ESQUERDA) ---
# --- COLAR ESTE BLOCO DENTRO DO elif menu == "DEMANDAS": ---
elif menu == "DEMANDAS":
    # Captura dados do usuário logado
    user = st.session_state.user_data
    eh_gerente = user['perfil'] == 'gerencia'
    meu_setor = user['setor']

    # 1. DEFINIÇÃO DOS DADOS (PITs)
    dados_equipe = {
        "MARKETING DIGITAL": {"Produção de Peças Avulsas": 2, "Edição de Vídeo/Reels": 3, "Gestão de Redes Sociais": 1, "Campanha Google Ads": 5, "Atualização de Site": 2},
        "IMPRENSA": {"Redação de Release": 3, "Clipping de Projetos": 7, "Agendamento de Pauta": 2, "Artigos Institucionais": 5, "Boletim Informativo": 2},
        "PROJETOS": {"Escrita de Novo Edital": 15, "Relatório de Prestação de Contas": 10, "Pesquisa de Editais": 5, "Inscrição em Prêmios": 7},
        "GERÊNCIA": {"Manutenção de Parcerias": 7, "Análise de Relatórios": 2, "Planejamento Anual": 30, "Gestão de Equipe": 2}
    }

    # 2. ESTILIZAÇÃO CSS
    st.markdown("""
        <style>
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
        .card-demanda { background: white; padding: 20px; border-radius: 12px; margin-bottom: 15px; border-left: 8px solid; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .setor-tag { font-size: 11px; font-weight: bold; color: #555; background: #f0f2f6; padding: 3px 10px; border-radius: 15px; }
        .sla-box { background: #e3f2fd; color: #0d47a1; padding: 10px; border-radius: 8px; font-size: 13px; margin-bottom: 10px; }
        </style>
    """, unsafe_allow_html=True)

    st.title(f"Planejamento: {user['nome']}")
    

    # 3. DASHBOARD FILTRADO
    # Se for gerente, conta tudo. Se for operacional, conta só o seu setor.
    def contar_status_filtrado(status_nome):
        try:
            sql = f"SELECT COUNT(*) as total FROM Demandas_Estrategicas WHERE status = '{status_nome}'"
            if not eh_gerente:
                sql += f" AND setor = '{meu_setor}'"
            res = run_query(sql)
            return res.iloc[0]['total'] if not res.empty else 0
        except: return 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Pendentes", contar_status_filtrado('PENDENTE'))
    c2.metric("Com barreira", contar_status_filtrado('BLOQUEADO'), delta_color="inverse")
    c3.metric("Concluídas", contar_status_filtrado('REALIZADO'))

    st.divider()

    # 4. FORMULÁRIO DE CADASTRO
    with st.expander("NOVA SOLICITAÇÃO", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            # Gerente escolhe qualquer um. Operacional só pode cadastrar para si mesmo ou o sistema trava no setor dele.
            setor_opcoes = list(dados_equipe.keys())
            setor_sel = st.selectbox("Responsável:", setor_opcoes, index=setor_opcoes.index(meu_setor) if meu_setor in setor_opcoes else 0, disabled=not eh_gerente)
            solicitante = st.text_input("SOLICITANTE", value=user['nome'])
        with col_b:
            tarefa_sel = st.selectbox("O que precisa ser feito?", list(dados_equipe[setor_sel].keys()))
            sla_dias = dados_equipe[setor_sel][tarefa_sel]
            st.markdown(f"<div class='sla-box'>⏱️ <b>SLA:</b> {sla_dias} dias úteis</div>", unsafe_allow_html=True)

        detalhes = st.text_area("Descrição:")
        
        st.write("**Prioridade (GUT):**")
        g1, u1, t1 = st.columns(3)
        g = g1.select_slider("Gravidade", [1,2,3,4,5], 3, key="g_d")
        u = u1.select_slider("Urgência", [1,2,3,4,5], 3, key="u_d")
        t = t1.select_slider("Tendência", [1,2,3,4,5], 3, key="t_d")

        if st.button("Lançar demanda", use_container_width=True):
            score = g * u * t
            run_insert("INSERT INTO Demandas_Estrategicas (tarefa, setor, gravidade, urgencia, tendencia, score_gut, status) VALUES (?,?,?,?,?,?,'PENDENTE')",
                       (f"[{tarefa_sel}] {detalhes} | POR: {solicitante}".upper(), setor_sel, g, u, t, score))
            st.success("Registrado!"); st.rerun()

    # 5. FILA DE TRABALHO FILTRADA
    st.subheader("Fila")
    
    # Lógica de Filtro SQL: Gerência vê tudo, Operacional vê só o seu
    query_sql = "SELECT id, tarefa, setor, score_gut, status FROM Demandas_Estrategicas WHERE status IN ('PENDENTE', 'BLOQUEADO')"
    params = []
    
    if not eh_gerente:
        query_sql += " AND setor = ?"
        params.append(meu_setor)
    
    demandas = run_query(query_sql + " ORDER BY status DESC, score_gut DESC", tuple(params))

    if not demandas.empty:
        for _, row in demandas.iterrows():
            is_b = row['status'] == 'BLOQUEADO'
            cor = "#7030a0" if is_b else ("#FF4B4B" if row['score_gut'] >= 80 else "#FFA500" if row['score_gut'] >= 40 else "#28A745")
            
            st.markdown(f"""
                <div class="card-demanda" style="border-left-color: {cor};">
                    <span class="setor-tag">{row['setor']}</span>
                    <h5 style="margin: 10px 0;">{'🚨 BLOQUEADO: ' if is_b else ''}{row['tarefa']}</h5>
                    <p style="font-size: 12px; color: #666; margin:0;">Prioridade: <b>{row['score_gut']} pts</b></p>
                </div>
            """, unsafe_allow_html=True)
            
            b1, b2 = st.columns(2)
            if b1.button("**Concluir**", key=f"c_{row['id']}"):
                run_insert("UPDATE Demandas_Estrategicas SET status = 'REALIZADO' WHERE id = ?", (row['id'],))
                st.rerun()
            if b2.button("**Barreira / Liberar**", key=f"b_{row['id']}"):
                novo_st = 'PENDENTE' if is_b else 'BLOQUEADO'
                run_insert("UPDATE Demandas_Estrategicas SET status = ? WHERE id = ?", (novo_st, row['id']))
                st.rerun()
    else:
        st.info("Nenhuma demanda pendente para o seu setor.")

    # 6. HISTÓRICO (Também filtrado)
    with st.expander("MEU HISTÓRICO"):
        sql_hist = "SELECT tarefa, status FROM Demandas_Estrategicas WHERE status = 'REALIZADO'"
        if not eh_gerente: sql_hist += f" AND setor = '{meu_setor}'"
        hist = run_query(sql_hist + " ORDER BY id DESC LIMIT 5")
        st.table(hist)
        

elif menu == "EVENTOS":
    st.markdown("<h1 style='text-align: center;'>ALMOÇO CDP</h1>", unsafe_allow_html=True)
    
    # 1. Definição do Mês de Referência
    mes_atual = datetime.now().strftime("%m/%Y")
    mes_ref = st.selectbox("📅 Mês do evento", [mes_atual, "04/2026", "05/2026"], help="Selecione o mês para cadastrar ou consultar convidados")
    
    # BUSCA OS DADOS (Certifique-se de que a tabela já tem a coluna 'telefone')
    df_almoco = run_query("SELECT * FROM Convidados_Almoco WHERE mes_referencia = ?", (mes_ref,))
    
    metas = {
        "Influencers": 3, "Imprensa": 3, "Doadores alto valor": 6, 
        "Cofrinhos": 2, "Parlamentar": 3, "Parceiros CDP": 12
    }

    tab_recepcao, tab_planejamento = st.tabs(["CHECK-IN E RECEPÇÃO", "PLANEJAMENTO MENSAL"])

    # ==========================================
    # ABA 1: RECEPÇÃO (Modo Inteligente)
    # ==========================================
    with tab_recepcao:
        df_conf = df_almoco[df_almoco['confirmado'] == 1].copy() if not df_almoco.empty else pd.DataFrame()
        pres = len(df_conf[df_conf['compareceu'] == 1]) if not df_conf.empty else 0
        tot = len(df_conf)
        
        c1, c2, c3 = st.columns([1, 2, 1])
        c1.metric("Confirmados", tot)
        c2.write(f"**Ocupação Real: {pres} de {tot}**")
        c2.progress(pres/tot if tot > 0 else 0)
        c3.metric("Presentes", pres)

        st.divider()
        col_fila, col_brief = st.columns([1.5, 1])

        with col_fila:
            busca = st.text_input("🔍 Buscar por nome...", label_visibility="collapsed", placeholder="Buscar na lista...")
            
            if not df_conf.empty:
                df_v = df_conf[df_conf['nome'].str.contains(busca, case=False)] if busca else df_conf
                for _, row in df_v.iterrows():
                    with st.container(border=True):
                        ca, cb = st.columns([3, 1])
                        ca.markdown(f"**{row['nome']}**")
                        # Exibe cargo e telefone no card de recepção
                        ca.markdown(f"<small>{row['cargo']} | {row['empresa']} | 📞 {row['telefone']}</small>", unsafe_allow_html=True)
                        
                        label_btn = "Check-in" if not row['compareceu'] else "Anular"
                        if cb.button(label_btn, key=f"btn_{row['id']}", type="primary" if not row['compareceu'] else "secondary", use_container_width=True):
                            novo_status = 1 if not row['compareceu'] else 0
                            run_insert("UPDATE Convidados_Almoco SET compareceu = ? WHERE id = ?", (novo_status, row['id']))
                            st.rerun()

        with col_brief:
            st.subheader("Dôssie executivo")
            df_p = df_conf[df_conf['compareceu'] == 1] if not df_conf.empty else pd.DataFrame()
            if not df_p.empty:
                msg = f"*ALMOÇO CDP - {mes_ref}*\n\n"
                for seg, gp in df_p.groupby('segmento'):
                    msg += f"✅ *{seg.upper()}*\n"
                    for _, p in gp.iterrows():
                        msg += f"• {p['nome']} ({p['cargo']})\n"
                    msg += "\n"
                st.code(msg, language="markdown")
            else:
                st.info("Aguardando chegadas...")

    # ==========================================
    # ABA 2: PLANEJAMENTO (AQUI O TELEFONE É EDITÁVEL)
    # ==========================================
    with tab_planejamento:
        st.subheader("Cadastro e Edição")
        with st.expander("NOVO CONVIDADO"):
            with st.form("form_planejamento", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n_c = c1.text_input("Nome *")
                f_c = c2.text_input("Cargo/Função *")
                e_c = c1.text_input("Empresa")
                t_c = c2.text_input("WhatsApp")
                s_c = st.selectbox("Segmento", list(metas.keys()))
                if st.form_submit_button("Salvar na lista"):
                    if n_c:
                        run_insert("INSERT INTO Convidados_Almoco (mes_referencia, segmento, nome, cargo, empresa, telefone) VALUES (?,?,?,?,?,?)",
                                   (mes_ref, s_c, n_c, f_c, e_c, t_c))
                        st.rerun()

        st.divider()
        if not df_almoco.empty:
            df_ed = df_almoco.copy()
            for col in ['contato_1', 'contato_2', 'confirmado']:
                df_ed[col] = df_ed[col].astype(bool)

            # TABELA COM TELEFONE APARECENDO E SENDO EDITÁVEL
            edited = st.data_editor(
                df_ed[['id', 'nome', 'cargo', 'empresa', 'telefone', 'segmento', 'contato_1', 'contato_2', 'confirmado']],
                column_config={
                    "id": None, 
                    "confirmado": st.column_config.CheckboxColumn("✅ CONFIRMOU"),
                    "telefone": st.column_config.TextColumn("WhatsApp")
                },
                hide_index=True, 
                use_container_width=True
            )
            
            if st.button("Guardar"):
                for _, r in edited.iterrows():
                    # UPDATE INCLUINDO O TELEFONE
                    run_insert("""
                        UPDATE Convidados_Almoco 
                        SET contato_1=?, contato_2=?, confirmado=?, telefone=?, cargo=?, empresa=?, nome=?
                        WHERE id=?
                    """, (int(r['contato_1']), int(r['contato_2']), int(r['confirmado']), r['telefone'], r['cargo'], r['empresa'], r['nome'], r['id']))
                st.success("Dados e Telefones atualizados!")
                st.rerun()

# --- 2. PARCEIROS E PROJETOS ---
elif menu == "PARCERIAS":
    st.title("**GESTÃO DE PARCEIROS E PROJETOS**")
    tab1, tab2 = st.tabs(["**PARCEIROS**", "**PROJETOS**"])
    
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
        busca = st.text_input("Pesquisar parceiro:")
        if busca and not df_p.empty:
            df_p = df_p[df_p['nome_instituicao'].str.contains(busca, case=False)]

        # Exibição da Tabela
        st.dataframe(df_p, use_container_width=True, hide_index=True)

        st.markdown("---")

        st.markdown("---")
        st.subheader("Fichas")
        
        # Cria uma lista de nomes para o selectbox
        lista_nomes = df_p['nome_instituicao'].tolist()
        parceiro_selecionado = st.selectbox("Selecione um parceiro para ver os contatos:", ["Selecione..."] + lista_nomes)

        if parceiro_selecionado != "Selecione...":
            # Descobre o ID do parceiro escolhido
            id_selecionado = df_p[df_p['nome_instituicao'] == parceiro_selecionado]['id_parceiro'].values[0]
            
            # Busca os contatos específicos desse ID
            query_contatos = f"""
                SELECT nome_pessoa as Nome, cargo as Cargo, telefone as WhatsApp, email as Email 
                FROM Contato_Direto 
                WHERE id_parceiro = {id_selecionado}
            """
            df_contatos_parceiro = run_query(query_contatos)
            
            # Exibe a tabela de contatos
            if not df_contatos_parceiro.empty:
                st.write(f"**Pessoas de contato em {parceiro_selecionado}:**")
                st.dataframe(df_contatos_parceiro, hide_index=True, use_container_width=True)
            else:
                st.info(f"Ainda não há contatos cadastrados para {parceiro_selecionado}.")
        
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
    # --- ABA DE PROJETOS ---
    with tab2:
        
        
        # 1. Query para a TABELA (Filtra 'GERAL' e vazios)
        query_projetos = """
            SELECT 
                UPPER(nome_projeto) as Projeto,
                strftime('%Y', data_doacao) as Ano,
                COUNT(*) as 'Qtd Repasses',
                SUM(valor_estimado) as Total
            FROM Doacao
            WHERE nome_projeto IS NOT NULL 
              AND nome_projeto != '' 
              AND UPPER(nome_projeto) != 'GERAL'
            GROUP BY Projeto, Ano
            ORDER BY Ano DESC, Total DESC
        """
        df_proj = run_query(query_projetos)
        
        # 2. Cálculos de Totais para os Cartões
        total_projetos = df_proj['Total'].sum() if not df_proj.empty else 0
        
        # Criamos duas métricas no topo
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Total em projetos", format_br(total_projetos))
        with m2:
            qtd_projetos = df_proj['Projeto'].nunique() if not df_proj.empty else 0
            st.metric("Total de projetos feitos", f"{qtd_projetos}")

        st.divider()
        
        if not df_proj.empty:
            # Filtro de Ano
            anos_lista = ["Todos"] + sorted(df_proj['Ano'].unique().tolist(), reverse=True)
            ano_escolhido = st.selectbox("Filtrar por ano de recebimento:", anos_lista, key="filtro_proj_ano")
            
            df_exibir = df_proj.copy()
            if ano_escolhido != "Todos":
                df_exibir = df_exibir[df_exibir['Ano'] == ano_escolhido]

            # Formatação para exibição na tabela
            df_exibir_copy = df_exibir.copy()
            df_exibir_copy['Total'] = df_exibir_copy['Total'].apply(format_br)
            
            st.dataframe(df_exibir_copy, use_container_width=True, hide_index=True)
        else:
            st.info("Ainda não existem doações vinculadas a projetos específicos.")

# --- 3. REGISTRAR DOAÇÃO ---
# --- 3. REGISTRAR DOAÇÃO ---
elif menu == "REGISTRAR DOAÇÃO":
    st.title("ENTRADA DE RECURSOS")
    
    # 1. Buscamos os nomes para o usuário escolher
    df_p = run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro")
    
    if not df_p.empty:
        with st.form("nova_doacao", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            
            with col_a:
                opcoes_p = ["Selecione o parceiro..."] + df_p['nome_instituicao'].tolist()
                nome_sel = st.selectbox("Selecione o parceiro/fonte", opcoes_p)
                
                valor = st.number_input("Valor do repasse (R$)", min_value=0.0)
                data = st.date_input("Data do recebimento", datetime.now())

            with col_b:
                projeto = st.text_input("Nome do Projeto / Emenda / Finalidade", placeholder="Ex: Projeto Vida")
                tipo = st.selectbox("Tipo de recurso", ["Financeira", "Vestuário", "Alimentos", "Serviços", "Midiática", "Projetos"])
                
                # --- NOVIDADE AQUI: Seleção da Estratégia do Plano de Captação ---
                origens_plano = ["Selecione...", "Bazar do Caquito", "Campanha Troco", "Parcerias", "Nota Potiguar", "Doações Online", "Projetos", "Troco"]
                origem_sel = st.selectbox("Origem da Captação (Estratégia)", origens_plano)
            
            desc = st.text_area("Observações")
            
            # --- BOTÃO COM VALIDAÇÃO AJUSTADA ---
            if st.form_submit_button("Confirmar doação", type="primary"):
                if nome_sel == "Selecione o parceiro...":
                    st.error("ERRO: Você esqueceu de selecionar o Parceiro!")
                
                
                else:
                    projeto_final = projeto.upper() if projeto else "GERAL"
                    id_p = df_p[df_p['nome_instituicao'] == nome_sel]['id_parceiro'].values[0]
                    
                    # --- SQL ATUALIZADO: Agora enviamos 7 campos (incluindo origem_captacao) ---
                    sql = """
                        INSERT INTO Doacao (
                            id_parceiro, valor_estimado, tipo_doacao, 
                            data_doacao, descricao, nome_projeto, origem_captacao
                        ) 
                        VALUES (?,?,?,?,?,?,?)
                    """
                    
                    # Enviamos os 7 valores na ordem correta
                    run_insert(sql, (
                        int(id_p), 
                        valor, 
                        tipo, 
                        data.strftime('%Y-%m-%d'), 
                        desc.upper(), 
                        projeto_final,
                        origem_sel  # <--- A nova informação sendo salva!
                    ))
                    
                    st.success(f"✅ Recurso de '{nome_sel}' registrado com sucesso!")
                    st.balloons()
                    st.rerun()

    # --- CENTRAL DE GESTÃO DE LANÇAMENTOS (EXTRATO POR PARCEIRO) ---
    st.divider()
    st.subheader("HISTÓRICO E LANÇAMENTOS")

    # 1. Seleção do Parceiro para busca
    lista_busca = ["Todos"] + df_p['nome_instituicao'].tolist()
    parceiro_busca = st.selectbox("Filtrar histórico por parceiro:", lista_busca)

    # 2. Query Dinâmica para buscar doações
    if parceiro_busca == "Todos":
        query_h = """
            SELECT d.id_doacao, p.nome_instituicao, d.valor_estimado, d.data_doacao, 
                   d.nome_projeto, d.descricao, d.tipo_doacao, d.origem_captacao
            FROM Doacao d
            JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
            ORDER BY d.data_doacao DESC LIMIT 20
        """
        params_h = ()
    else:
        query_h = """
            SELECT d.id_doacao, p.nome_instituicao, d.valor_estimado, d.data_doacao, 
                   d.nome_projeto, d.descricao, d.tipo_doacao, d.origem_captacao
            FROM Doacao d
            JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
            WHERE p.nome_instituicao = ?
            ORDER BY d.data_doacao DESC
        """
        params_h = (parceiro_busca,)

    df_h = run_query(query_h, params_h)

    if not df_h.empty:
        st.write(f"Exibindo **{len(df_h)}** lançamentos encontrados:")
        
        for _, row in df_h.iterrows():
            # Card principal usando Expander para não poluir a tela
            with st.expander(f"{row['data_doacao']} | {row['nome_instituicao']} | {format_br(row['valor_estimado'])}"):
                
                # Criamos um mini-formulário de edição dentro do expander
                with st.form(key=f"edit_form_{row['id_doacao']}"):
                    st.markdown(f"**Editando Lançamento #{row['id_doacao']}**")
                    c1, c2, c3 = st.columns(3)
                    
                    novo_valor = c1.number_input("Valor (R$)", value=float(row['valor_estimado']), key=f"v_{row['id_doacao']}")
                    nova_data = c2.date_input("Data", value=datetime.strptime(row['data_doacao'], '%Y-%m-%d'), key=f"d_{row['id_doacao']}")
                    novo_projeto = c3.text_input("Projeto", value=row['nome_projeto'], key=f"p_{row['id_doacao']}")
                    
                    nova_desc = st.text_area("Descrição", value=row['descricao'] or "", key=f"desc_{row['id_doacao']}")
                    
                    col_btn1, col_btn2 = st.columns([1, 1])
                    
                    if col_btn1.form_submit_button("💾 Salvar alterações", use_container_width=True):
                        sql_upd = """
                            UPDATE Doacao SET valor_estimado=?, data_doacao=?, nome_projeto=?, descricao=?
                            WHERE id_doacao=?
                        """
                        run_insert(sql_upd, (novo_valor, str(nova_data), novo_projeto, nova_desc, row['id_doacao']))
                        st.success("Alterado com sucesso!")
                        st.rerun()

                    if col_btn2.form_submit_button("🗑️ Excluir registro", type="secondary", use_container_width=True):
                        run_insert("DELETE FROM Doacao WHERE id_doacao = ?", (row['id_doacao'],))
                        st.warning("Registro excluído.")
                        st.rerun()
    else:
        st.info("Nenhum lançamento encontrado para os critérios selecionados.")

elif menu == "CONTATOS":
    st.title("AGENDA")
    st.markdown("Gerencie sua rede de contatos, parceiros e tomadores de decisão.")

    # Busca os dados no banco
    query_view = """
        SELECT c.id_contato, p.nome_instituicao as Empresa, c.nome_pessoa as Nome, 
               c.cargo as Cargo, c.telefone as WhatsApp, c.email as Email
        FROM Contato_Direto c
        LEFT JOIN Parceiro p ON c.id_parceiro = p.id_parceiro
        ORDER BY c.nome_pessoa ASC
    """
    df_contatos = run_query(query_view)

    # --- NAVEGAÇÃO POR ABAS (Design Limpo) ---
    tab_lista, tab_novo, tab_gerir = st.tabs(["CONTATOS", "ADICIONAR NOVO", "GERENCIAR"])

    # ==========================================
    # ABA 1: VISUALIZAÇÃO ELEGANTE
    # ==========================================
    with tab_lista:
        if not df_contatos.empty:
            # 1. Métricas de Resumo
            c1, c2, c3 = st.columns(3)
            c1.metric("**Total de contatos**", len(df_contatos))
            c2.metric("**Empresas vinculadas**", df_contatos['Empresa'].nunique())
            
            st.divider()

            # 2. Barra de Busca
            busca = st.text_input("Buscar contato por nome, empresa ou cargo...", placeholder="Digite para filtrar a tabela abaixo...")
            
            # Filtra o dataframe se houver busca
            if busca:
                df_filtrado = df_contatos[
                    df_contatos['Nome'].str.contains(busca, case=False, na=False) | 
                    df_contatos['Empresa'].str.contains(busca, case=False, na=False) |
                    df_contatos['Cargo'].str.contains(busca, case=False, na=False)
                ].copy()
            else:
                df_filtrado = df_contatos.copy()

            # 3. Tratamento de Dados para a Tabela Interativa
            # Cria links clicáveis para WhatsApp e Email direto na tabela
            if not df_filtrado.empty:
                df_filtrado['Ação_WA'] = df_filtrado['WhatsApp'].apply(
                    lambda x: f"https://wa.me/55{re.sub(r'[^0-9]', '', str(x))}" if pd.notnull(x) and x != "" else None
                )
                df_filtrado['Ação_Email'] = df_filtrado['Email'].apply(
                    lambda x: f"mailto:{x}" if pd.notnull(x) and x != "" else None
                )

                # 4. Exibição da Tabela com Column Config (O visual fica incrível)
                st.dataframe(
                    df_filtrado,
                    column_config={
                        "id_contato": None, # Esconde o ID para ficar limpo
                        "Empresa": st.column_config.TextColumn("🏢 Empresa", width="medium"),
                        "Nome": st.column_config.TextColumn("👤 Nome", width="medium"),
                        "Cargo": st.column_config.TextColumn("💼 Cargo/Função"),
                        "WhatsApp": st.column_config.TextColumn("📱 Telefone"),
                        "Ação_WA": st.column_config.LinkColumn("💬 WhatsApp", display_text="Abrir Conversa"),
                        "Email": None, # Esconde o texto puro do email
                        "Ação_Email": st.column_config.LinkColumn("📧 E-mail", display_text="Enviar E-mail")
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.warning("Nenhum contato encontrado na busca.")
        else:
            st.info("Sua agenda está vazia. Vá na aba 'Adicionar novo' para começar.")

    # ==========================================
    # ABA 2: FORMULÁRIO LIMPO
    # ==========================================
    with tab_novo:
        st.subheader("Cadastrar contato")
        df_p_contatos = run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro ORDER BY nome_instituicao")
        
        if not df_p_contatos.empty:
            with st.form("form_novo_contato", clear_on_submit=True, border=False):
                col1, col2 = st.columns(2)
                nome_f = col1.text_input("Nome*")
                cargo_f = col2.text_input("Cargo/Função")
                email_f = col1.text_input("Endereço de E-mail")
                tel_f = col2.text_input("WhatsApp (com DDD) *")
                
                parceiro_nome = st.selectbox("Instituição Vinculada *", options=df_p_contatos['nome_instituicao'].tolist())
                
                submit_btn = st.form_submit_button("Salvar contato", type="primary")
                
                if submit_btn:
                    if nome_f and tel_f:
                        id_p = df_p_contatos[df_p_contatos['nome_instituicao'] == parceiro_nome]['id_parceiro'].values[0]
                        sql = "INSERT INTO Contato_Direto (id_parceiro, nome_pessoa, cargo, telefone, email) VALUES (?, ?, ?, ?, ?)"
                        run_insert(sql, (int(id_p), nome_f, cargo_f, tel_f, email_f))
                        st.success(f"Contato **{nome_f}** adicionado à agenda!")
                        st.rerun()
                    else:
                        st.error("Por favor, preencha o Nome e o WhatsApp.")
        else:
            st.warning("É necessário cadastrar um Parceiro na aba 'Parceiros/Projetos' primeiro.")

    # ==========================================
    # ABA 3: GERENCIAMENTO DE DADOS (Exclusão)
    # ==========================================
    with tab_gerir:
        st.subheader("Gerenciar Cadastros")
        if not df_contatos.empty:
            st.write("Selecione um contato abaixo para remover do sistema.")
            
            # Cria uma lista formatada para o selectbox
            opcoes_exclusao = df_contatos.apply(lambda row: f"{row['Nome']} ({row['Empresa']}) - ID: {row['id_contato']}", axis=1).tolist()
            contato_selecionado = st.selectbox("Selecionar contato para exclusão:", [""] + opcoes_exclusao)
            
            if contato_selecionado != "":
                # Extrai o ID do texto do selectbox
                id_para_excluir = int(contato_selecionado.split("ID: ")[-1])
                
                st.error("⚠️ Atenção: Esta ação não pode ser desfeita.")
                if st.button("🗑️ Confirmar Exclusão", use_container_width=True):
                    run_insert("DELETE FROM Contato_Direto WHERE id_contato = ?", (id_para_excluir,))
                    st.success("Contato excluído com sucesso!")
                    st.rerun()
        else:
            st.info("Não há contatos para gerenciar.")

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

# --- COLOQUE ISSO NO FINAL DO ARQUIVO ---
elif menu == "RELACIONAMENTO":
    st.title("SAÚDE BD")
    
    # 1. BUSCA OS DADOS DA VIEW
    df_rel = run_query("SELECT * FROM View_Relacionamento_Critico")
    
    # Criamos o resumo para o gráfico
    df_status = df_rel.groupby('Status_Relacionamento').size().reset_index(name='qtd')

    # --- LAYOUT EM COLUNAS ---
    col_grafico, col_tabela = st.columns([1, 1.2])

    with col_grafico:
        if not df_status.empty:
            import plotly.graph_objects as go
            
            # Cores modernas sincronizadas
            cores_map = {
                "🔴 CRÍTICO (+3 meses)": "#FF4B4B", 
                "🟡 ATENÇÃO (+45 dias)": "#FFA500", 
                "🟢 EM DIA": "#00CC96"
            }
            cores_lista = [cores_map.get(s, "#808080") for s in df_status['Status_Relacionamento']]

            fig = go.Figure(data=[go.Pie(
                labels=df_status['Status_Relacionamento'], 
                values=df_status['qtd'], 
                hole=.6, 
                marker_colors=cores_lista,
                textinfo='percent'
            )])

            total_p = df_status['qtd'].sum()
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                margin=dict(t=0, b=0, l=0, r=0),
                height=300,
                annotations=[dict(text=f'<b>{total_p}</b><br>Parceiros', x=0.5, y=0.5, font_size=18, showarrow=False)]
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_tabela:
        st.subheader("**STATUS ATUAL**")
        if not df_rel.empty:
            status_filtro = st.radio("Filtrar urgência:", 
                                    ["Todos", "🔴 CRÍTICO", "🟡 ATENÇÃO", "🟢 EM DIA"], 
                                    horizontal=True)
            
            if status_filtro != "Todos":
                termo = status_filtro.split(" ")[1] 
                df_display = df_rel[df_rel['Status_Relacionamento'].str.contains(termo)]
            else:
                df_display = df_rel
            
            # AJUSTE AQUI: Mudamos 'nome_instituicao' para 'Empresa' que é o nome real na View
            st.dataframe(df_display[['Empresa', 'Status_Relacionamento']], height=250, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Todos em dia!")

    st.divider()

    # 2. Formulário para registrar nova conversa
    st.subheader("**Registrar nova interação**")
    # No banco a tabela principal de parceiros usa 'nome_instituicao', então aqui mantemos
    df_p = run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro ORDER BY nome_instituicao")
    
    with st.form("form_crm", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            p_sel = st.selectbox("Parceiro", ["Selecione..."] + df_p['nome_instituicao'].tolist())
            data_c = st.date_input("Data de contato", datetime.now())
        with c2:
            prox_c = st.date_input("Agendar retorno")
            
        txt = st.text_area("Descrição da conversa").upper()
        
        if st.form_submit_button("Salvar histórico", type="primary"):
            if p_sel != "Selecione...":
                id_parc = df_p[df_p['nome_instituicao'] == p_sel]['id_parceiro'].values[0]
                sql = """
                    INSERT INTO Registro_Relacionamento 
                    (id_parceiro, data_interacao, descricao_do_que_foi_feito, proxima_acao_data)
                    VALUES (?, ?, ?, ?)
                """
                run_insert(sql, (int(id_parc), data_c.strftime('%Y-%m-%d'), txt, prox_c.strftime('%Y-%m-%d')))
                st.success("✅ Histórico salvo com sucesso!")
                st.rerun()
            else:
                st.error("Por favor, selecione um parceiro.")