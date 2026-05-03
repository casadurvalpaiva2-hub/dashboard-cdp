# ============================================================
#  SISTEMA INTERNO DI CDP
#  Versão refatorada — dívida técnica limpa
#  (login unificado, CSS centralizado, imports consolidados)
# ============================================================

import os
import re
from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from psycopg2 import pool as pg_pool
import streamlit as st

# set_page_config DEVE ser o primeiro comando Streamlit do script
st.set_page_config(
    page_title="Casa Durval Paiva · DI",
    layout="wide",
    page_icon="https://casadurvalpaiva.org.br/wp-content/themes/durvalpaiva/dist/img/header/logo.png",
)


# ------------------------------------------------------------
#  HELPERS GLOBAIS
# ------------------------------------------------------------
def _chart_layout(height=240, margin=None):
    """Layout padrão para gráficos Plotly — tema escuro integrado ao app."""
    return dict(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="'Inter', -apple-system, sans-serif",
            color="rgba(255,255,255,0.50)",
            size=11,
        ),
        margin=margin or dict(l=0, r=8, t=12, b=0),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(size=10, color="rgba(255,255,255,0.40)"),
            linecolor="rgba(255,255,255,0.08)",
            tickcolor="rgba(255,255,255,0)",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            gridwidth=1,
            zeroline=False,
            tickfont=dict(size=10, color="rgba(255,255,255,0.40)"),
            linecolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor="rgba(18,20,28,0.97)",
            bordercolor="rgba(55,138,221,0.40)",
            font=dict(
                family="'Inter', sans-serif",
                color="white",
                size=12,
            ),
            namelength=0,
        ),
        showlegend=False,
        bargap=0.30,
    )

# ── Paleta de dados — Opção A ───────────────────────────────────────────────
# Vermelho CDP reservado para marca, alertas críticos e UI (nav, botões).
# Dados usam a paleta abaixo para criar hierarquia visual clara.
_CLR_FINANCIAL = "#378ADD"   # azul — captação financeira (principal)
_CLR_POSITIVE  = "#1D9E75"   # teal — metas atingidas, resultados positivos
_CLR_WARNING   = "#D97706"   # amber — atenção, pendências, prazos
_CLR_NEUTRAL   = "#888780"   # cinza — estimados, mídia, dados secundários
_CLR_PROJECT   = "#378ADD"   # azul (mesmo financeiro) — projetos/plano DI

# Aliases de compatibilidade para os gráficos já criados
_CDP_BAR   = _CLR_FINANCIAL
_CDP_LINE  = _CLR_FINANCIAL
_CDP_BLUE  = _CLR_NEUTRAL


def format_br(valor):
    """Formata número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------
#  LOGIN — sistema único (multiusuário com perfis)
# ------------------------------------------------------------
CONTAS = {
    "alice":    {"nome": "Alice Karine",    "setor": "MARKETING DIGITAL", "senha": "123456", "perfil": "operacional"},
    "daniel":   {"nome": "Daniel",          "setor": "MARKETING DIGITAL", "senha": "123456", "perfil": "operacional"},
    "imprensa": {"nome": "Michelle Phiffer","setor": "IMPRENSA",          "senha": "cdp2",   "perfil": "operacional"},
    "projetos": {"nome": "Viviane Moura",   "setor": "PROJETOS",          "senha": "cdp3",   "perfil": "operacional"},
    "gerencia": {"nome": "Helder Coutinho", "setor": "GERÊNCIA",          "senha": "Hc!24601","perfil": "gerencia"},
}

def _perfil():
    try:
        return (st.session_state.get("user_data") or {}).get("perfil", "operacional")
    except Exception:
        return "operacional"
def _is_gerente(): return _perfil() == "gerencia"

def _verificar_senha(login: str, senha_digitada: str) -> bool:
    """Verifica senha: CONTAS dict (lookup instantâneo, sem DB no login)."""
    if login not in CONTAS:
        return False
    return CONTAS[login]["senha"] == senha_digitada


if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.user_data = None

if not st.session_state.autenticado:
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(135deg, #0f0f0f 0%, #1a0a0a 50%, #0f0f0f 100%);
        }
        [data-testid="stHeader"] { background: transparent; }
        /* Centraliza verticalmente removendo padding padrão */
        [data-testid="stMainBlockContainer"],
        .block-container {
            padding-top: 8vh !important;
            padding-bottom: 0 !important;
            max-width: 100% !important;
        }
        [data-testid="stHeader"] { display: none; }
        .login-wrapper {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .login-logo {
            font-size: 13px;
            letter-spacing: 4px;
            text-transform: uppercase;
            color: #C0392B;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .login-title {
            font-size: 38px;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 4px;
            letter-spacing: -1px;
        }
        .login-sub {
            font-size: 14px;
            color: #666;
            margin-bottom: 40px;
            letter-spacing: 1px;
        }
        .login-divider {
            width: 40px;
            height: 3px;
            background: #C0392B;
            margin: 0 auto 36px auto;
            border-radius: 2px;
        }
        div[data-testid="stForm"] {
            background: rgba(255,255,255,0.03) !important;
            border: 1px solid rgba(255,255,255,0.07) !important;
            border-radius: 16px !important;
            padding: 36px 40px !important;
            backdrop-filter: blur(10px);
            width: 100%;
            max-width: 420px;
        }
        div[data-testid="stForm"] input {
            background: rgba(255,255,255,0.05) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 8px !important;
            color: #fff !important;
        }
        div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
            background: #C0392B !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            letter-spacing: 1px !important;
            height: 48px !important;
            font-size: 15px !important;
            width: 100% !important;
            margin-top: 8px !important;
        }
        div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover {
            background: #922b21 !important;
        }
        .login-footer {
            font-size: 11px;
            color: #444;
            margin-top: 32px;
            letter-spacing: 1px;
        }
        /* Esconde decorações desnecessárias */
        #MainMenu, footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    _, col_mid, _ = st.columns([1, 1.2, 1])
    with col_mid:
        st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
        st.markdown('<div class="login-logo">Casa Durval Paiva</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Sistema DI</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Desenvolvimento Institucional · 2026</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-divider"></div>', unsafe_allow_html=True)

        with st.form("login"):
            user_login = st.text_input("Usuário", placeholder="seu usuário", label_visibility="collapsed").lower()
            pass_login = st.text_input("Senha",   placeholder="sua senha",   label_visibility="collapsed", type="password")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("ENTRAR", use_container_width=True, type="primary"):
                if user_login in CONTAS and _verificar_senha(user_login, pass_login):
                    st.session_state.autenticado = True
                    st.session_state.user_data = CONTAS[user_login]
                    # Tela de transição enquanto o app carrega
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

        st.markdown('<div class="login-footer">© 2026 · Acesso restrito à equipe autorizada</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

# (set_page_config movido para o topo)


# ============================================================
#  DESIGN SYSTEM — tokens + CSS base + componentes Python
#  Paleta neutra corporativa com vermelho CDP como acento.
#  Adaptável a tema claro/escuro do Streamlit via CSS vars.
# ============================================================

# ------------------------------------------------------------
#  DESIGN TOKENS (referência — também expostos como CSS vars)
# ------------------------------------------------------------
CDP_RED        = "#E31D24"       # vermelho institucional — acento
CDP_RED_DARK   = "#B51319"       # vermelho pressed/hover
CDP_RED_SOFT   = "rgba(227,29,36,0.10)"  # vermelho sutil (fundos)

# Tons funcionais (usados pelos badges de situação / status)
COLOR_DANGER   = "#DC2626"       # crítico / erro
COLOR_WARNING  = "#D97706"       # atenção / amber
COLOR_SUCCESS  = "#1D9E75"       # positivo / teal
COLOR_INFO     = "#378ADD"       # dados / azul
COLOR_NEUTRAL  = "#888780"       # estimado / neutro

CSS_GLOBAL = """
<style>
/* ============================================================
   TIPOGRAFIA — Inter + Material Symbols preservados
   ============================================================ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Aplica Inter em todos os elementos de texto — MAS não em spans nus
   usados pelo Streamlit para renderizar ícones Material Symbols */
html, body,
h1, h2, h3, h4, h5, h6,
p, div, label, a, td, th, li, dt, dd,
input, textarea, select, option, button,
[data-testid],
[data-testid] p,
.stMarkdown, .stText, .stMetric,
[data-testid="stMarkdownContainer"],
[data-testid="stWidgetLabel"],
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}

/* Preserva Material Symbols para ícones do Streamlit */
span.material-symbols-rounded,
[data-testid="stIconMaterial"],
[data-testid="stBaseButton-secondary"] > div > div > span:first-child,
[data-testid="stBaseButton-primary"] > div > div > span:first-child,
[data-testid="stSidebarCollapsedControl"] > div > span {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

/* ============================================================
   TOKENS — variáveis adaptativas ao tema (claro/escuro)
   ============================================================ */
:root {
    --cdp-red: #E31D24;
    --cdp-red-dark: #B51319;
    --cdp-red-soft: rgba(227,29,36,0.10);

    /* Superfícies e texto — tema claro (padrão) */
    --ds-bg-page:      transparent;
    --ds-bg-surface:   rgba(15, 23, 42, 0.03);
    --ds-bg-elevated:  rgba(15, 23, 42, 0.06);
    --ds-border:       rgba(15, 23, 42, 0.12);
    --ds-border-soft:  rgba(15, 23, 42, 0.06);
    --ds-text:         inherit;
    --ds-text-muted:   rgba(15, 23, 42, 0.65);
    --ds-text-subtle:  rgba(15, 23, 42, 0.45);

    /* Cores semânticas */
    --ds-danger:  #DC2626;
    --ds-warning: #D97706;
    --ds-success: #1D9E75;
    --ds-info:    #378ADD;
    --ds-neutral: #888780;

    /* Espaçamento e raio */
    --ds-radius-sm: 6px;
    --ds-radius-md: 10px;
    --ds-radius-lg: 14px;
    --ds-gap-xs: 4px;
    --ds-gap-sm: 8px;
    --ds-gap-md: 12px;
    --ds-gap-lg: 20px;
}

/* Tema escuro — forçado para manter identidade com a tela de login */
:root {
    --ds-bg-surface:   rgba(255, 255, 255, 0.04);
    --ds-bg-elevated:  rgba(255, 255, 255, 0.07);
    --ds-border:       rgba(255, 255, 255, 0.10);
    --ds-border-soft:  rgba(255, 255, 255, 0.05);
    --ds-text-muted:   rgba(255, 255, 255, 0.65);
    --ds-text-subtle:  rgba(255, 255, 255, 0.40);
}

/* ============================================================
   IDENTIDADE VISUAL — fundo escuro CDP (espelha o login)
   ============================================================ */

/* Fundo principal — cinza carvão neutro, sem tint vermelho */
[data-testid="stAppViewContainer"] {
    background: #111318 !important;
}

/* Header transparente */
[data-testid="stHeader"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
}

/* Sidebar — superfície escura com borda sutil */
[data-testid="stSidebar"] {
    background: rgba(15, 17, 22, 0.92) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    backdrop-filter: blur(12px);
}
[data-testid="stSidebar"] > div:first-child {
    background: transparent !important;
}

/* Linha sutil no topo da sidebar */
[data-testid="stSidebar"]::before {
    content: "";
    display: block;
    height: 2px;
    background: linear-gradient(90deg, rgba(55,138,221,0.6), transparent);
    position: absolute;
    top: 0; left: 0; right: 0;
}

/* Área de conteúdo principal */
[data-testid="stMain"] {
    background: transparent !important;
}

/* Remove só a decoração "Made with Streamlit" — toolbar mantida para o toggle da sidebar */
[data-testid="stDecoration"] {
    display: none !important;
}
/* Esconde o menu ⋮ da toolbar mas mantém o botão de sidebar */
[data-testid="stToolbarActions"] {
    display: none !important;
}
/* Garante que o botão de reabrir sidebar sempre aparece */
[data-testid="stSidebarCollapsedControl"] {
    display: flex !important;
}

/* Dataframes e tabelas — fundo escuro consistente */
[data-testid="stDataFrame"] > div,
.stDataFrame {
    background: rgba(255,255,255,0.03) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
}

/* Expanders — visual coeso */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 8px !important;
}

/* Inputs e selects dentro do app */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] select,
div[data-baseweb="select"] {
    background: rgba(255,255,255,0.05) !important;
    border-color: rgba(255,255,255,0.10) !important;
}

/* ============================================================
   SIDEBAR — navegação via st.radio (CSS puro)
   Lição: [data-baseweb="radio"] = CADA OPÇÃO — não esconder!
   ============================================================ */

/* Remove gap do radiogroup e padding extra */
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
    gap: 1px !important;
    padding: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] {
    padding: 0 !important;
    margin: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
    gap: 0 !important;
}

/* Cada opção do radio — estilo de nav item */
section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 8px 14px 8px 16px !important;
    margin: 0 !important;
    border-radius: 8px !important;
    border-left: 3px solid transparent !important;
    cursor: pointer !important;
    color: rgba(255,255,255,0.48) !important;
    font-size: 13.5px !important;
    font-weight: 400 !important;
    letter-spacing: 0.1px !important;
    line-height: 1.2 !important;
    transition: background 0.12s, color 0.12s, border-color 0.12s !important;
    background: transparent !important;
    box-sizing: border-box !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:hover {
    background: rgba(255,255,255,0.06) !important;
    color: rgba(255,255,255,0.82) !important;
    border-left-color: rgba(255,255,255,0.14) !important;
}
/* Item selecionado */
section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
    background: rgba(55,138,221,0.13) !important;
    border-left-color: #378ADD !important;
    color: rgba(255,255,255,0.95) !important;
    font-weight: 600 !important;
}
/* Esconde APENAS o círculo indicador (primeiro filho do label) */
section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
    display: none !important;
}
/* Esconde input nativo */
section[data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"] {
    display: none !important;
}
/* O div com o texto da opção — ocupa o espaço todo */
section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] > div:last-child {
    width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Scrollbar discreta */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.15);
    border-radius: 2px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.30); }

/* ============================================================
   SIDEBAR — botão MENU (mantém identidade CDP vermelho)
   ============================================================ */
[data-testid="stSidebarCollapsedControl"] {
    background-color: var(--cdp-red) !important;
    border-radius: 0 var(--ds-radius-lg) var(--ds-radius-lg) 0 !important;
    width: 80px !important;
    height: 45px !important;
    top: 15px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 4px 4px 10px rgba(0,0,0,0.2) !important;
}
/* Esconde o ícone Material Icons (pode ser SVG ou span de texto) */
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] span {
    display: none !important;
    font-size: 0 !important;
}
[data-testid="stSidebarCollapsedControl"]::before {
    content: "☰ MENU" !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    letter-spacing: 0.5px;
}
.main .block-container { padding-top: 4rem !important; }

/* ============================================================
   BOTÕES PRIMÁRIOS — cor CDP
   ============================================================ */
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background-color: var(--cdp-red) !important;
    border-color: var(--cdp-red) !important;
    color: white !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
    background-color: var(--cdp-red-dark) !important;
    border-color: var(--cdp-red-dark) !important;
}

/* ============================================================
   st.metric — visual unificado (tom neutro, acento vermelho no delta)
   ============================================================ */
div[data-testid="stMetric"] {
    background-color: var(--ds-bg-surface);
    padding: 14px 16px;
    border-radius: var(--ds-radius-md);
    border: 1px solid var(--ds-border-soft);
}
div[data-testid="stMetricLabel"] p {
    font-size: 11px !important;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    opacity: 0.75;
    font-weight: 600;
}

/* ============================================================
   DESIGN SYSTEM — COMPONENTES
   ============================================================ */

/* Page Header */
.ds-page-header {
    margin-bottom: var(--ds-gap-lg);
    padding-bottom: 12px;
    border-bottom: 1px solid var(--ds-border-soft);
}
.ds-page-header h1 {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.3px;
    margin: 0 0 4px 0 !important;
    color: var(--ds-text);
}
.ds-page-header .ds-page-subtitle {
    font-size: 0.9rem;
    color: var(--ds-text-muted);
    margin: 0;
}

/* Section divider (para subdividir módulos) */
.ds-section {
    margin: 24px 0 12px 0;
    display: flex;
    align-items: center;
    gap: 10px;
}
.ds-section-title {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--ds-text-subtle);
    white-space: nowrap;
}
.ds-section-line {
    flex: 1;
    height: 1px;
    background: var(--ds-border-soft);
}

/* Card de KPI (alternativa enxuta ao st.metric) */
.ds-kpi {
    background: var(--ds-bg-surface);
    border: 1px solid var(--ds-border-soft);
    border-radius: var(--ds-radius-md);
    padding: 14px 16px;
    min-width: 0;
}
.ds-kpi-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--ds-text-muted);
    font-weight: 600;
    margin-bottom: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.ds-kpi-value {
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1.15;
    color: rgba(255,255,255,0.92);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    letter-spacing: -0.5px;
}
/* accent = destaque neutro (branco brilhante), não cor de dado */
.ds-kpi-value.accent { color: rgba(255,255,255,0.95); }
.ds-kpi-hint {
    font-size: 11px;
    color: var(--ds-text-subtle);
    margin-top: 4px;
}

/* Action card — padrão único para listas de itens */
.ds-card {
    background: var(--ds-bg-surface);
    border: 1px solid var(--ds-border-soft);
    border-left: 3px solid var(--ds-neutral);
    border-radius: var(--ds-radius-md);
    padding: 12px 14px;
    margin-bottom: 8px;
    transition: background-color 0.15s ease;
}
.ds-card:hover { background: var(--ds-bg-elevated); }
.ds-card.danger  { border-left-color: var(--ds-danger); }
.ds-card.warning { border-left-color: var(--ds-warning); }
.ds-card.success { border-left-color: var(--ds-success); }
.ds-card.info    { border-left-color: var(--ds-info); }
.ds-card.accent  { border-left-color: var(--cdp-red); }

.ds-card-title {
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0 0 4px 0;
    color: var(--ds-text);
}
.ds-card-meta {
    font-size: 0.8rem;
    color: var(--ds-text-muted);
    margin: 0;
}
.ds-card-meta strong { color: var(--ds-text); font-weight: 600; }

/* Badge / tag */
.ds-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    line-height: 1.6;
    background: var(--ds-bg-elevated);
    color: var(--ds-text-muted);
    border: 1px solid var(--ds-border-soft);
    white-space: nowrap;
}
.ds-badge.danger  { background: rgba(220, 38, 38, 0.12);  color: var(--ds-danger);  border-color: rgba(220, 38, 38, 0.25); }
.ds-badge.warning { background: rgba(217, 119, 6, 0.12);  color: var(--ds-warning); border-color: rgba(217, 119, 6, 0.25); }
.ds-badge.success { background: rgba(5, 150, 105, 0.12);  color: var(--ds-success); border-color: rgba(5, 150, 105, 0.25); }
.ds-badge.info    { background: rgba(2, 132, 199, 0.12);  color: var(--ds-info);    border-color: rgba(2, 132, 199, 0.25); }
.ds-badge.accent  { background: var(--cdp-red-soft);      color: var(--cdp-red);    border-color: rgba(227, 29, 36, 0.30); }

/* Empty state */
.ds-empty {
    text-align: center;
    padding: 40px 20px;
    border: 1px dashed var(--ds-border);
    border-radius: var(--ds-radius-md);
    background: var(--ds-bg-surface);
}
.ds-empty-icon  { font-size: 2.2rem; margin-bottom: 8px; opacity: 0.6; }
.ds-empty-title { font-size: 1rem; font-weight: 600; margin-bottom: 4px; color: var(--ds-text); }
.ds-empty-msg   { font-size: 0.85rem; color: var(--ds-text-muted); }

/* Classes legadas mantidas para compatibilidade com módulos ainda não migrados.
   TODO: remover assim que todos os módulos usarem os componentes DS. */
.glass-card {
    background: var(--ds-bg-surface);
    border: 1px solid var(--ds-border-soft);
    border-radius: var(--ds-radius-lg);
    padding: 20px;
    margin-bottom: 16px;
}
.guest-item {
    background: var(--ds-bg-surface);
    border-radius: var(--ds-radius-md);
    padding: 10px 12px;
    margin-bottom: 8px;
    border: 1px solid var(--ds-border-soft);
}
.suggestion-box {
    background: var(--ds-bg-surface);
    border-left: 3px solid var(--ds-success);
    border-radius: var(--ds-radius-sm);
    padding: 12px 14px;
    margin: 8px 0;
}
.urgent-border { border-left-color: var(--ds-danger); }
.date-badge {
    background: var(--cdp-red-soft);
    color: var(--cdp-red);
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    border: 1px solid rgba(227, 29, 36, 0.25);
    font-weight: 600;
}
.stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--ds-info);
    margin: 4px 0;
}
.task-card {
    background: var(--ds-bg-surface);
    padding: 10px 14px;
    border-radius: var(--ds-radius-sm);
    border-left: 4px solid var(--ds-neutral);
    margin-bottom: 0;
    border-top: 1px solid var(--ds-border-soft);
    border-right: 1px solid var(--ds-border-soft);
    border-bottom: 1px solid var(--ds-border-soft);
}
.task-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; color: var(--ds-text); }
.task-meta  { font-size: 11px; color: var(--ds-text-muted); }
.tag-diaria { background: var(--cdp-red-soft); color: var(--cdp-red); font-size: 9px; padding: 2px 6px; border-radius: 4px; margin-left: 8px; vertical-align: middle; font-weight: 600; }
.sla-box {
    background: var(--ds-bg-surface);
    color: var(--ds-text-muted);
    padding: 10px;
    border-radius: var(--ds-radius-sm);
    font-size: 13px;
    margin-bottom: 10px;
    border: 1px solid var(--ds-border-soft);
}
</style>
"""
st.markdown(CSS_GLOBAL, unsafe_allow_html=True)

# (overlay JS removido)

# ── Sincroniza senhas alteradas pelo usuário (DB → CONTAS em memória) ─────────
# Roda apenas uma vez por sessão para evitar queries repetidas
if not st.session_state.get("_senhas_sincronizadas"):
    try:
        _url_sync = os.environ.get("DATABASE_URL", "")
        if not _url_sync:
            try:
                _url_sync = st.secrets["DATABASE_URL"]
            except Exception:
                _url_sync = ""
        if _url_sync.startswith("postgres://"):
            _url_sync = _url_sync.replace("postgres://", "postgresql://", 1)
        if _url_sync:
            _conn_sync = psycopg2.connect(_url_sync, connect_timeout=3)
            with _conn_sync.cursor() as _cur_sync:
                _cur_sync.execute(
                    "SELECT login, senha FROM Usuario_Senhas"
                )
                for _row_s in _cur_sync.fetchall():
                    if _row_s[0] in CONTAS:
                        CONTAS[_row_s[0]]["senha"] = _row_s[1]
            _conn_sync.close()
    except Exception:
        pass
    st.session_state["_senhas_sincronizadas"] = True


# ============================================================
#  DESIGN SYSTEM — COMPONENTES PYTHON REUTILIZÁVEIS
# ============================================================

def page_header(titulo: str, subtitulo: str | None = None):
    """Cabeçalho padrão de cada módulo/página."""
    sub_html = f'<p class="ds-page-subtitle">{subtitulo}</p>' if subtitulo else ""
    st.markdown(
        f'<div class="ds-page-header"><h1>{titulo}</h1>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def section(titulo: str):
    """Divisor de seção dentro de uma página. Use em vez de st.subheader/st.divider."""
    st.markdown(
        f'<div class="ds-section">'
        f'<span class="ds-section-title">{titulo}</span>'
        f'<span class="ds-section-line"></span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def kpi_row(items: list[dict]):
    """Renderiza uma linha de KPIs em colunas iguais.
    Cada item: {'label': str, 'value': str|int, 'hint': str|None, 'accent': bool}
    """
    if not items:
        return
    cols = st.columns(len(items))
    for col, it in zip(cols, items):
        accent_cls = " accent" if it.get("accent") else ""
        hint_html = f'<div class="ds-kpi-hint">{it["hint"]}</div>' if it.get("hint") else ""
        col.markdown(
            f'<div class="ds-kpi">'
            f'<div class="ds-kpi-label">{it["label"]}</div>'
            f'<div class="ds-kpi-value{accent_cls}">{it["value"]}</div>'
            f'{hint_html}'
            f'</div>',
            unsafe_allow_html=True,
        )


def badge(texto: str, tom: str = "neutral") -> str:
    """Retorna HTML de um badge. Tons: neutral, danger, warning, success, info, accent."""
    tom_cls = tom if tom in {"neutral", "danger", "warning", "success", "info", "accent"} else "neutral"
    cls = "" if tom_cls == "neutral" else f" {tom_cls}"
    return f'<span class="ds-badge{cls}">{texto}</span>'


def situacao_to_tom(situacao: str) -> str:
    """Mapeia os emojis de situação para o tom do DS."""
    if not situacao:
        return "neutral"
    if any(k in situacao for k in ("ATRASAD", "CRITICO")):                      return "danger"
    if any(k in situacao for k in ("URGENTE", "ATENCAO", "EM PROGRESSO", "ABAIXO")): return "warning"
    if any(k in situacao for k in ("ESTA SEMANA", "EM DIA", "ATINGIDO")):       return "success"
    return "neutral"


def action_card(titulo: str, meta_parts: list[str], tom: str = "neutral",
                situacao_badge: str | None = None, extra_badges: list[tuple[str, str]] | None = None):
    """Card padrão para listas de ações/convidados/parceiros.
    - titulo: texto principal
    - meta_parts: lista de strings com metadata (serão juntadas por · )
    - tom: cor da barra lateral (neutral|danger|warning|success|info|accent)
    - situacao_badge: texto para virar badge no cabeçalho
    - extra_badges: lista de (texto, tom) para badges adicionais
    """
    tom_cls = tom if tom in {"neutral", "danger", "warning", "success", "info", "accent"} else "neutral"
    tom_class = "" if tom_cls == "neutral" else f" {tom_cls}"

    badges_html = ""
    if situacao_badge:
        badges_html += badge(situacao_badge, situacao_to_tom(situacao_badge)) + " "
    if extra_badges:
        badges_html += " ".join(badge(t, tom) for t, tom in extra_badges)

    meta = " · ".join(meta_parts) if meta_parts else ""

    st.markdown(
        f'<div class="ds-card{tom_class}">'
        f'<div style="margin-bottom:4px;">{badges_html}</div>'
        f'<p class="ds-card-title">{titulo}</p>'
        f'<p class="ds-card-meta">{meta}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def empty_state(icone: str, titulo: str, mensagem: str = ""):
    """Estado vazio padronizado."""
    st.markdown(
        f'<div class="ds-empty">'
        f'<div class="ds-empty-icon">{icone}</div>'
        f'<div class="ds-empty-title">{titulo}</div>'
        f'<div class="ds-empty-msg">{mensagem}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------
#  LOGO NO SIDEBAR
# ------------------------------------------------------------
LOGO_URL = "https://casadurvalpaiva.org.br/wp-content/themes/durvalpaiva/dist/img/header/logo.png"
st.sidebar.image(LOGO_URL, width=150)

# ── Identidade do usuário logado ──────────────────────────────────────────────
_ud = st.session_state.user_data or {}
_badge_cor = "#C0392B" if _ud.get("perfil") == "gerencia" else "#378ADD"
_badge_txt = "GERÊNCIA" if _ud.get("perfil") == "gerencia" else "OPERACIONAL"
st.sidebar.markdown(
    f'<div style="padding:8px 10px;margin:6px 0 2px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);">' +
    f'<div style="font-size:12px;font-weight:600;color:#E5E7EB;">{_ud.get("nome","")}</div>' +
    f'<div style="font-size:10px;color:#94A3B8;">{_ud.get("setor","")}</div>' +
    f'<div style="margin-top:4px;display:inline-block;font-size:9px;font-weight:700;letter-spacing:1px;' +
    f'padding:2px 7px;border-radius:20px;background:{_badge_cor}22;color:{_badge_cor};border:1px solid {_badge_cor}55;">{_badge_txt}</div>' +
    f'</div>',
    unsafe_allow_html=True,
)

if st.sidebar.button("↩ Sair", key="logout_btn", use_container_width=False,
                     help="Encerrar sessão", type="secondary"):
    st.session_state.autenticado = False
    st.session_state.user_data = None
    st.rerun()

st.sidebar.markdown("---")

# ── Navegação — inicialização antecipada para o menu renderizar imediatamente ──
if "current_page" not in st.session_state:
    st.session_state.current_page = "Painel Geral"
if "open_form" not in st.session_state:
    st.session_state.open_form = None
if "_qa_nonce" not in st.session_state:
    st.session_state._qa_nonce = 0

_menus_gerencia = ["Painel Geral", "Calendário", "Plano DI 2026", "Parcerias", "Contatos", "Almoço CDP", "Ações", "Entrada de Recursos", "Relacionamento"]
_menus_operacional = ["Painel Geral", "Calendário", "Plano DI 2026", "Parcerias", "Contatos", "Almoço CDP", "Ações", "Entrada de Recursos", "Relacionamento"]
_opcoes_menu = _menus_gerencia if _is_gerente() else _menus_operacional

def _trigger_quick_add(tipo: str):
    """Navega para a página certa e sinaliza abertura de formulário."""
    mapa_menu = {
        "parceiro": "Parcerias",
        "contato":  "Contatos",
        "doacao":   "Entrada de Recursos",
    }
    st.session_state.current_page = mapa_menu[tipo]
    st.session_state.open_form = tipo

with st.sidebar:
    # ── Atalho rápido ──────────────────────────────────────────
    st.markdown("""<p style="font-size:10px;letter-spacing:1.8px;text-transform:uppercase;
    color:rgba(255,255,255,0.25);font-weight:600;margin:8px 0 6px 4px;">Acesso rápido</p>""",
    unsafe_allow_html=True)
    _opcoes_add = {"Criar novo...": None, "Parceiro": "parceiro", "Contato": "contato", "Doação": "doacao"}
    _qa_key = f"sel_quick_add_{st.session_state._qa_nonce}"
    _escolha = st.selectbox("Atalho", options=list(_opcoes_add.keys()), index=0, key=_qa_key, label_visibility="collapsed")
    if _opcoes_add[_escolha] is not None:
        _trigger_quick_add(_opcoes_add[_escolha])
        st.session_state._qa_nonce += 1
        st.rerun()

    # ── Navegação principal ─────────────────────────────────────
    st.markdown("""<p style="font-size:10px;letter-spacing:1.8px;text-transform:uppercase;
    color:rgba(255,255,255,0.25);font-weight:600;margin:20px 0 2px 4px;">Navegação</p>""",
    unsafe_allow_html=True)

    _opcoes_nav = ["Painel Geral", "Calendário", "Plano DI 2026", "Parcerias", "Contatos",
                   "Almoço CDP", "Ações", "Entrada de Recursos", "Relacionamento"]
    _nav_items = [(p, p) for p in _opcoes_nav]

    _nav_idx = _opcoes_nav.index(st.session_state.current_page) \
               if st.session_state.current_page in _opcoes_nav else 0
    _nav_choice = st.radio(
        "nav",
        options=_opcoes_nav,
        index=_nav_idx,
        label_visibility="collapsed",
        key="sidebar_nav_radio",
    )
    if _nav_choice != st.session_state.current_page:
        st.session_state.current_page = _nav_choice

    _active_page = st.session_state.current_page

menu = st.session_state.current_page


# ------------------------------------------------------------
#  BANCO DE DADOS — Supabase / PostgreSQL
# ------------------------------------------------------------
def _db_url() -> str:
    """Lê a URL do banco de variável de ambiente ou st.secrets."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            url = st.secrets["DATABASE_URL"]
        except Exception:
            url = ""
    # Supabase às vezes retorna postgres:// — psycopg2 precisa de postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

@st.cache_resource
def _pool() -> pg_pool.ThreadedConnectionPool:
    """Pool de conexões (reutilizado entre reruns do Streamlit)."""
    url = _db_url()
    return pg_pool.ThreadedConnectionPool(2, 10, url)


# ------------------------------------------------------------
#  ACESSO AO BANCO — funções centrais
# ------------------------------------------------------------
def run_query(query, params=()):
    """Executa SELECT e retorna DataFrame. Compatível com PostgreSQL."""
    pool = _pool()
    conn = pool.getconn()
    try:
        q = query.replace('?', '%s')
        return pd.read_sql_query(q, conn, params=params if params else None)
    except Exception as e:
        st.error(f"Erro na consulta: {e}")
        return pd.DataFrame()
    finally:
        pool.putconn(conn)


@st.cache_data(ttl=60, show_spinner=False)
def run_query_cached(query, params=()):
    """Versão cacheada de run_query — TTL 60s. Para listas e views que mudam com frequência."""
    return run_query(query, params)


@st.cache_data(ttl=300, show_spinner=False)
def run_query_slow(query, params=()):
    """Versão cacheada com TTL 5min. Para dados de referência e qualidade que mudam raramente."""
    return run_query(query, params)


@st.cache_data(ttl=120, show_spinner=False)
def _parceiros_lista():
    """Lista de parceiros para dropdowns — cache 2min, reutilizada em vários pontos do app."""
    return run_query("SELECT id_parceiro, nome_instituicao FROM Parceiro ORDER BY nome_instituicao")


def run_exec(query, params=()):
    """Executa INSERT/UPDATE/DELETE/DDL.
    Registra no Logs mantendo só os últimos 1000 registros (rotação)."""
    pool = _pool()
    conn = pool.getconn()
    try:
        q = query.replace('?', '%s')
        with conn.cursor() as cur:
            cur.execute(q, params if params else None)
            # Log apenas de mutações reais (ignora CREATE/DROP idempotente de setup)
            q_upper = query.lstrip().upper()
            if q_upper.startswith(("INSERT", "UPDATE", "DELETE")):
                cur.execute(
                    "INSERT INTO Logs (acao, data_hora) VALUES (%s, %s)",
                    (query[:50], datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
                # Rotação: mantém só os últimos 1000 logs
                cur.execute(
                    "DELETE FROM Logs WHERE id NOT IN "
                    "(SELECT id FROM Logs ORDER BY id DESC LIMIT 1000)"
                )
        conn.commit()
        # Invalida caches de leitura para refletir alterações imediatamente
        try:
            run_query_cached.clear()
            run_query_slow.clear()
        except Exception:
            pass
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao salvar: {e}")
    finally:
        pool.putconn(conn)


# Alias para não quebrar as ~20 chamadas existentes no código
run_insert = run_exec


# ------------------------------------------------------------
#  MIGRATIONS IDEMPOTENTES — rodam 1x ao carregar o app
#  (adicionar colunas ou criar tabelas ausentes sem explodir)
# ------------------------------------------------------------
def setup_schema():
    """Garante views atualizadas no PostgreSQL a cada deploy."""
    pool = _pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:

            # Adicionar colunas se não existirem (idempotente no PostgreSQL)
            for ddl in [
                "ALTER TABLE Contato_Direto ADD COLUMN IF NOT EXISTS email TEXT",
                "ALTER TABLE Demandas_Estrategicas ADD COLUMN IF NOT EXISTS responsavel TEXT",
                "ALTER TABLE Demandas_Estrategicas ADD COLUMN IF NOT EXISTS data_prevista DATE",
                "ALTER TABLE Demandas_Estrategicas ADD COLUMN IF NOT EXISTS is_diaria INTEGER DEFAULT 0",
                "ALTER TABLE Demandas_Estrategicas ADD COLUMN IF NOT EXISTS data_ultima_conclusao TIMESTAMPTZ",
                "ALTER TABLE Convidados_Almoco ADD COLUMN IF NOT EXISTS id_parceiro INTEGER REFERENCES Parceiro(id_parceiro)",
            ]:
                try:
                    cur.execute(ddl)
                    conn.commit()
                except Exception:
                    conn.rollback()

            # Tabelas que podem não existir ainda
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Convidados_Almoco (
                    id             SERIAL PRIMARY KEY,
                    mes_referencia TEXT,
                    segmento       TEXT,
                    nome           TEXT,
                    empresa        TEXT,
                    cargo          TEXT,
                    telefone       TEXT,
                    contato_1      BOOLEAN DEFAULT FALSE,
                    contato_2      BOOLEAN DEFAULT FALSE,
                    contato_3      BOOLEAN DEFAULT FALSE,
                    contato_4      BOOLEAN DEFAULT FALSE,
                    confirmado     BOOLEAN DEFAULT FALSE,
                    compareceu     BOOLEAN DEFAULT FALSE,
                    observacoes    TEXT,
                    id_parceiro    INTEGER REFERENCES Parceiro(id_parceiro)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Meta_Fonte_2026 (
                    id_fonte      SERIAL PRIMARY KEY,
                    codigo_fonte  TEXT UNIQUE NOT NULL,
                    nome_fonte    TEXT NOT NULL,
                    valor_2025    REAL DEFAULT 0,
                    meta_2026     REAL NOT NULL,
                    tipo          TEXT DEFAULT 'outros',
                    ativa         INTEGER DEFAULT 1
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS Registro_Captacao_DI (
                    id              SERIAL PRIMARY KEY,
                    id_fonte        INTEGER NOT NULL REFERENCES Meta_Fonte_2026(id_fonte),
                    mes_referencia  TEXT NOT NULL,
                    valor_realizado REAL NOT NULL,
                    observacao      TEXT,
                    data_registro   TIMESTAMPTZ DEFAULT NOW(),
                    registrado_por  TEXT
                )
            """)

            # Seed das fontes de captação (idempotente)
            _fontes_plano = [
                ('BAZAR_CDP',            'Bazar CDP',                             216639.18,  238000.00, 'evento'),
                ('BAZAR_RFB',            'Bazar RFB (Mercadorias)',               135138.87,  500000.00, 'evento'),
                ('BAZAR_RFB_BRINQUEDOS', 'Bazar RFB (Brinquedos)',               213151.81,   40000.00, 'evento'),
                ('DOACAO_ONLINE',        'Doação On-line',                         17881.24,   30000.00, 'campanha'),
                ('EMENDAS',              'Emendas Parlamentares',                 100000.00,  200000.00, 'projeto'),
                ('NOTA_POTIGUAR',        'Nota Potiguar',                          73350.70,   77018.24, 'campanha'),
                ('OUTROS',               'Outros',                                 37621.99,   39503.09, 'outros'),
                ('PARCERIAS_INST',       'Parcerias Institucionais',              166915.90,  166000.00, 'parceria'),
                ('PROJETOS',             'Projetos (Recup. Crédito / Emendas)',   175000.00,  350000.00, 'projeto'),
                ('TROCO',                'Troco',                                  70142.25,   70000.00, 'campanha'),
            ]
            for _f in _fontes_plano:
                cur.execute(
                    "INSERT INTO Meta_Fonte_2026 (codigo_fonte,nome_fonte,valor_2025,meta_2026,tipo) "
                    "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (codigo_fonte) DO NOTHING",
                    _f
                )

            # ── VIEWS (PostgreSQL: CREATE OR REPLACE VIEW) ─────────────────
            cur.execute("""
                CREATE OR REPLACE VIEW View_Acoes_Unificadas AS
                SELECT
                    'D' || d.id                                        AS id_uniforme,
                    'DEMANDA'                                          AS fonte,
                    d.tarefa                                           AS titulo,
                    d.setor                                            AS setor,
                    d.responsavel                                      AS responsavel,
                    NULL::TEXT                                         AS parceiro,
                    NULL::TEXT                                         AS contato,
                    d.data_prevista                                    AS data_prazo,
                    d.score_gut                                        AS score,
                    d.status                                           AS status,
                    d.is_diaria                                        AS is_diaria,
                    d.data_criacao                                     AS data_criacao,
                    CASE
                        WHEN d.data_prevista IS NULL                        THEN 'SEM PRAZO'
                        WHEN d.data_prevista < CURRENT_DATE                 THEN 'ATRASADA'
                        WHEN (d.data_prevista - CURRENT_DATE) <= 2          THEN 'URGENTE'
                        WHEN (d.data_prevista - CURRENT_DATE) <= 7          THEN 'ESTA SEMANA'
                        ELSE 'FUTURA'
                    END                                                AS situacao
                FROM Demandas_Estrategicas d
                WHERE d.status IN ('PENDENTE', 'BLOQUEADO')

                UNION ALL

                SELECT
                    'T' || t.id_tarefa                                 AS id_uniforme,
                    'TAREFA'                                           AS fonte,
                    t.tipo_tarefa || ' — ' || t.descricao              AS titulo,
                    NULL::TEXT                                         AS setor,
                    t.responsavel                                      AS responsavel,
                    p.nome_instituicao                                 AS parceiro,
                    c.nome_pessoa                                      AS contato,
                    t.data_prazo                                       AS data_prazo,
                    CASE t.prioridade
                        WHEN 'ALTA'  THEN 100
                        WHEN 'MEDIA' THEN 50
                        WHEN 'BAIXA' THEN 20
                        ELSE 0
                    END                                                AS score,
                    t.status                                           AS status,
                    0                                                  AS is_diaria,
                    t.data_criacao::TIMESTAMPTZ                        AS data_criacao,
                    CASE
                        WHEN t.data_prazo < CURRENT_DATE               THEN 'ATRASADA'
                        WHEN (t.data_prazo - CURRENT_DATE) <= 2        THEN 'URGENTE'
                        WHEN (t.data_prazo - CURRENT_DATE) <= 7        THEN 'ESTA SEMANA'
                        ELSE 'FUTURA'
                    END                                                AS situacao
                FROM Tarefas_Pendentes t
                LEFT JOIN Parceiro       p ON t.id_parceiro = p.id_parceiro
                LEFT JOIN Contato_Direto c ON t.id_contato  = c.id_contato
                WHERE t.status = 'PENDENTE'
            """)

            cur.execute("""
                CREATE OR REPLACE VIEW View_Tarefas_Abertas AS
                SELECT
                    t.id_tarefa,
                    t.tipo_tarefa,
                    t.descricao,
                    t.data_criacao,
                    t.data_prazo,
                    t.prioridade,
                    t.status,
                    t.observacoes,
                    p.nome_instituicao                           AS "Parceiro",
                    c.nome_pessoa                                AS "Contato",
                    (t.data_prazo - CURRENT_DATE)::INTEGER       AS "Dias_Ate_Prazo",
                    CASE
                        WHEN t.data_prazo < CURRENT_DATE               THEN 'ATRASADA'
                        WHEN (t.data_prazo - CURRENT_DATE) <= 2        THEN 'URGENTE'
                        WHEN (t.data_prazo - CURRENT_DATE) <= 7        THEN 'ESTA SEMANA'
                        ELSE 'FUTURA'
                    END                                          AS "Situacao"
                FROM Tarefas_Pendentes t
                LEFT JOIN Parceiro       p ON t.id_parceiro = p.id_parceiro
                LEFT JOIN Contato_Direto c ON t.id_contato  = c.id_contato
                WHERE t.status = 'PENDENTE'
            """)

            cur.execute("""
                CREATE OR REPLACE VIEW View_Relacionamento_Critico AS
                SELECT
                    p.nome_instituicao                                              AS "Empresa",
                    p.status                                                        AS "Situacao",
                    MAX(r.data_interacao)                                           AS "Ultima_Interacao",
                    (CURRENT_DATE - MAX(r.data_interacao)::date)::INTEGER           AS "Dias_Sem_Contato",
                    CASE
                        WHEN MAX(r.data_interacao) IS NULL                          THEN 'SEM HISTORICO'
                        WHEN (CURRENT_DATE - MAX(r.data_interacao)::date) > 90      THEN 'CRITICO (+3 meses)'
                        WHEN (CURRENT_DATE - MAX(r.data_interacao)::date) > 45      THEN 'ATENCAO (+45 dias)'
                        ELSE 'EM DIA'
                    END                                                             AS "Status_Relacionamento",
                    (
                        SELECT proxima_acao_data
                        FROM Registro_Relacionamento rr
                        WHERE rr.id_parceiro = p.id_parceiro
                        ORDER BY rr.data_interacao DESC
                        LIMIT 1
                    )                                                               AS "Proxima_Acao_Planejada"
                FROM Parceiro p
                LEFT JOIN Registro_Relacionamento r ON p.id_parceiro = r.id_parceiro
                GROUP BY p.id_parceiro, p.nome_instituicao, p.status
                ORDER BY "Dias_Sem_Contato" DESC NULLS LAST
            """)

            cur.execute("""
                CREATE OR REPLACE VIEW View_Progresso_PlanoAnual AS
                SELECT
                    m.id_fonte, m.codigo_fonte, m.nome_fonte, m.tipo,
                    m.valor_2025, m.meta_2026,
                    COALESCE(SUM(c.valor_realizado), 0)                                              AS captado_2026,
                    ROUND((COALESCE(SUM(c.valor_realizado),0)/m.meta_2026*100)::NUMERIC, 1)          AS pct_meta,
                    m.meta_2026 - COALESCE(SUM(c.valor_realizado), 0)                                AS saldo_pendente,
                    CASE
                        WHEN COALESCE(SUM(c.valor_realizado),0) >= m.meta_2026          THEN 'ATINGIDO'
                        WHEN COALESCE(SUM(c.valor_realizado),0) / m.meta_2026 >= 0.7    THEN 'EM PROGRESSO'
                        WHEN COALESCE(SUM(c.valor_realizado),0) > 0                     THEN 'ABAIXO DO ESPERADO'
                        ELSE 'SEM REGISTRO'
                    END AS status_meta
                FROM Meta_Fonte_2026 m
                LEFT JOIN (
                    SELECT id_fonte, valor_realizado
                    FROM Registro_Captacao_DI
                    WHERE LEFT(mes_referencia, 7) BETWEEN '2026-01' AND '2026-12'
                    UNION ALL
                    SELECT m2.id_fonte, d.valor_estimado AS valor_realizado
                    FROM Doacao d
                    JOIN Meta_Fonte_2026 m2
                        ON m2.codigo_fonte = CASE d.origem_captacao
                            WHEN 'Nota Potiguar'    THEN 'NOTA_POTIGUAR'
                            WHEN 'Parcerias'        THEN 'PARCERIAS_INST'
                            WHEN 'Doações Online'   THEN 'DOACAO_ONLINE'
                            WHEN 'Projetos'         THEN 'PROJETOS'
                            WHEN 'Bazar do Caquito' THEN 'BAZAR_CDP'
                            WHEN 'Campanha Troco'   THEN 'TROCO'
                            WHEN 'Outros'           THEN 'OUTROS'
                            ELSE NULL
                        END
                    WHERE d.tipo_doacao IN ('Financeira', 'Projetos')
                      AND d.data_doacao >= '2026-01-01'
                ) c ON m.id_fonte = c.id_fonte
                WHERE m.ativa = 1
                GROUP BY m.id_fonte, m.codigo_fonte, m.nome_fonte, m.tipo, m.valor_2025, m.meta_2026
                ORDER BY m.meta_2026 DESC
            """)

            conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao preparar banco: {e}")
    finally:
        pool.putconn(conn)


# setup_schema roda apenas 1x por sessão (evita round-trips desnecessários ao Supabase)
if "schema_ok" not in st.session_state:
    setup_schema()
    st.session_state.schema_ok = True

# ── Seed da Regua_Matriz — roda 1x por sessão ────────────────────────────────
# Garante que todo tipo definido em REGUA_CONFIG exista no banco.



# ── Régua de relacionamento: config mestra ──────────────────────────────
REGUA_CONFIG = {
    "Parceiros importantes": [
        {"acao": "Cartao de aniversario digital",   "periodo_dias": 365,  "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Agradecimento personalizado",      "periodo_dias": 90,   "canal": "E-mail/Presencial", "responsavel": "DI"},
        {"acao": "Destaque em redes + Selo Amigo",   "periodo_dias": 180,  "canal": "Redes Sociais",     "responsavel": "DI"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "DI"},
        {"acao": "Mensagem de campanha",             "periodo_dias": 45,   "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Brindes e datas comemorativas",    "periodo_dias": 365,  "canal": "Presencial",        "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "DI"},
        {"acao": "Balanço Social",                   "periodo_dias": 365,  "canal": "E-mail/Fisico",     "responsavel": "DI"},
    ],
    "Financiador": [
        {"acao": "Cartao de aniversario digital",   "periodo_dias": 365,  "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Agradecimento personalizado",      "periodo_dias": 90,   "canal": "E-mail/Presencial", "responsavel": "DI"},
        {"acao": "Destaque em redes + Selo Amigo",   "periodo_dias": 180,  "canal": "Redes Sociais",     "responsavel": "DI"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "DI"},
        {"acao": "Mensagem de campanha",             "periodo_dias": 45,   "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Brindes e datas comemorativas",    "periodo_dias": 365,  "canal": "Presencial",        "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "DI"},
        {"acao": "Balanço Social",                   "periodo_dias": 365,  "canal": "E-mail/Fisico",     "responsavel": "DI"},
    ],
    "Imprensa": [
        {"acao": "Agradecimento padrao",             "periodo_dias": 90,   "canal": "E-mail",            "responsavel": "DI"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "DI"},
        {"acao": "Mensagem de campanha",             "periodo_dias": 45,   "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "DI"},
        {"acao": "Balanço Social",                   "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "DI"},
    ],
    "Doadores especiais: não mon.": [
        {"acao": "Cartao de aniversario digital",   "periodo_dias": 365,  "canal": "WhatsApp/E-mail",   "responsavel": "Eq. Tecnica"},
        {"acao": "Boas-vindas",                      "periodo_dias": None, "canal": "E-mail",            "responsavel": "Eq. Tecnica"},
        {"acao": "Agradecimento personalizado",      "periodo_dias": 90,   "canal": "E-mail",            "responsavel": "Eq. Tecnica"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "DI"},
        {"acao": "Mensagem de campanha",             "periodo_dias": 45,   "canal": "WhatsApp/E-mail",   "responsavel": "Eq. Tecnica"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Brindes e datas comemorativas",    "periodo_dias": 365,  "canal": "Presencial",        "responsavel": "Eq. Tecnica"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "Eq. Tecnica"},
    ],
    "Doador pontual": [
        {"acao": "Boas-vindas",                      "periodo_dias": None, "canal": "E-mail",            "responsavel": "Telemarketing"},
        {"acao": "Agradecimento personalizado",      "periodo_dias": 90,   "canal": "E-mail/Presencial", "responsavel": "Telemarketing"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "Telemarketing"},
    ],
    "Voluntário": [
        {"acao": "Cartao de aniversario digital",   "periodo_dias": 365,  "canal": "WhatsApp/E-mail",   "responsavel": "RH"},
        {"acao": "Boas-vindas",                      "periodo_dias": None, "canal": "E-mail",            "responsavel": "RH"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "DI"},
        {"acao": "Mensagem de campanha",             "periodo_dias": 45,   "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "RH"},
    ],
    "Apoiadores de eventos": [
        {"acao": "Boas-vindas",                      "periodo_dias": None, "canal": "E-mail",            "responsavel": "Eq. Tecnica"},
        {"acao": "Agradecimento personalizado",      "periodo_dias": 90,   "canal": "E-mail",            "responsavel": "Eq. Tecnica"},
        {"acao": "Destaque em redes + Selo Amigo",   "periodo_dias": 180,  "canal": "Redes Sociais",     "responsavel": "DI"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "DI"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "DI"},
    ],
    "Conselho e diretoria": [
        {"acao": "Cartao de aniversario digital",   "periodo_dias": 365,  "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "DI"},
        {"acao": "Mensagem de campanha",             "periodo_dias": 45,   "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "DI"},
        {"acao": "Balanço Social",                   "periodo_dias": 365,  "canal": "E-mail/Fisico",     "responsavel": "DI"},
    ],
    "Acolhidos": [
        {"acao": "Cartao de aniversario digital",   "periodo_dias": 365,  "canal": "WhatsApp/E-mail",   "responsavel": "Responsavel"},
        {"acao": "Boas-vindas",                      "periodo_dias": None, "canal": "E-mail",            "responsavel": "Responsavel"},
        {"acao": "Mensagem de campanha",             "periodo_dias": 45,   "canal": "WhatsApp/E-mail",   "responsavel": "Responsavel"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "Responsavel"},
    ],
    "Doador via site": [
        {"acao": "Agradecimento automatico",         "periodo_dias": None, "canal": "E-mail",            "responsavel": "Plataforma"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "DI"},
    ],
    "Doadores em geral": [
        {"acao": "Boas-vindas",                      "periodo_dias": None, "canal": "E-mail",            "responsavel": "Telemarketing"},
        {"acao": "Agradecimento padrao",             "periodo_dias": 90,   "canal": "E-mail",            "responsavel": "Telemarketing"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "DI"},
        {"acao": "Mensagem de campanha",             "periodo_dias": 45,   "canal": "WhatsApp/E-mail",   "responsavel": "Telemarketing"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "Telemarketing"},
    ],
    "Visitantes": [
        {"acao": "Agradecimento padrao",             "periodo_dias": 90,   "canal": "E-mail",            "responsavel": "Telemarketing"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "Telemarketing"},
    ],
    "Funcionário": [
        {"acao": "Cartao de aniversario digital",   "periodo_dias": 365,  "canal": "WhatsApp",          "responsavel": "RH"},
        {"acao": "Boas-vindas",                      "periodo_dias": None, "canal": "E-mail",            "responsavel": "RH"},
        {"acao": "Mensagem mensal",                  "periodo_dias": 30,   "canal": "E-mail/WhatsApp",   "responsavel": "RH"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "RH"},
    ],
    "Fornecedores": [
        {"acao": "Agradecimento padrao",             "periodo_dias": 90,   "canal": "E-mail",            "responsavel": "Responsavel"},
        {"acao": "Boletim semanal",                  "periodo_dias": 7,    "canal": "WhatsApp/E-mail",   "responsavel": "DI"},
        {"acao": "Cartao de boas festas digital",    "periodo_dias": 365,  "canal": "E-mail",            "responsavel": "Responsavel"},
    ],
}


# ON CONFLICT DO NOTHING preserva edições manuais feitas pela UI.
# Sem gate de COUNT: novos tipos adicionados ao REGUA_CONFIG propagam
# automaticamente na próxima sessão sem precisar de deploy ou reset.
if "regua_tipo_norm_ok" not in st.session_state:
    _tp_renames = [
        ("Parceiros importantes",             "Parceiros importantes"),
        ("Doadores Especiais (nao monetario)","Doadores especiais: não mon."),
        ("Doador Pontual",                    "Doador pontual"),
        ("Voluntário",                        "Voluntário"),
        ("Apoiadores de Eventos",             "Apoiadores de eventos"),
        ("Conselho e diretoria",              "Conselho e diretoria"),
        ("Doador via Site",                   "Doador via site"),
        ("Doadores em Geral",                 "Doadores em geral"),
        ("Funcionario",                       "Funcionário"),
    ]
    for _old, _new in _tp_renames:
        run_exec("UPDATE Regua_Matriz SET tipo_publico = %s WHERE tipo_publico = %s", (_new, _old))
        run_exec("UPDATE Parceiro SET tipo_publico_regua = %s WHERE tipo_publico_regua = %s", (_new, _old))
    st.session_state.regua_tipo_norm_ok = True

if "regua_seed_v2_ok" not in st.session_state:
    for _rsc_tp, _rsc_acoes in REGUA_CONFIG.items():
        for _rsc_item in _rsc_acoes:
            run_exec(
                "INSERT INTO Regua_Matriz (tipo_publico, acao, periodo_dias, canal, responsavel) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (tipo_publico, acao) "
                "DO UPDATE SET responsavel = EXCLUDED.responsavel",
                (_rsc_tp, _rsc_item["acao"], _rsc_item["periodo_dias"],
                 _rsc_item["canal"], _rsc_item.get("responsavel", "DI"))
            )
    st.session_state.regua_seed_ok = True



def _get_regua_config_db() -> dict:
    """Lê a config da régua do banco (fonte de verdade em runtime).
    Fallback para REGUA_CONFIG apenas como segurança — em condições normais
    a tabela já foi semeada pelo bloco de seed na inicialização da sessão."""
    df_rm = run_query_cached(
        "SELECT tipo_publico, acao, periodo_dias, canal "
        "FROM Regua_Matriz WHERE ativo = TRUE ORDER BY tipo_publico, id"
    )
    if df_rm.empty:
        return REGUA_CONFIG
    config = {}
    for _, row in df_rm.iterrows():
        tp = row["tipo_publico"]
        if tp not in config:
            config[tp] = []
        config[tp].append({
            "acao": row["acao"],
            "periodo_dias": int(row["periodo_dias"]) if pd.notna(row["periodo_dias"]) else None,
            "canal": row["canal"] or "",
        })
    return config


def _gerar_regua_pendencias(id_parceiro: int, tipo_publico: str):
    """Gera tarefas da régua para um parceiro, evitando duplicatas e respeitando periodicidade."""
    config_ativa = _get_regua_config_db()
    if not tipo_publico or tipo_publico not in config_ativa:
        return
    hoje_dt = datetime.now().date()
    for item in config_ativa[tipo_publico]:
        # Verificar se já existe pendente
        ex_pend = run_query(
            "SELECT id FROM Regua_Pendencias WHERE id_parceiro=%s AND tipo_acao=%s AND status=\'PENDENTE\'",
            (id_parceiro, item["acao"])
        )
        if not ex_pend.empty:
            continue
        # Verificar última vez que foi feito
        if item["periodo_dias"]:
            ex_feito = run_query(
                "SELECT feito_em FROM Regua_Pendencias WHERE id_parceiro=%s AND tipo_acao=%s "
                "AND status=\'FEITO\' ORDER BY feito_em DESC LIMIT 1",
                (id_parceiro, item["acao"])
            )
            if not ex_feito.empty:
                ultima = pd.to_datetime(ex_feito["feito_em"].values[0])
                if (datetime.now() - ultima).days < item["periodo_dias"]:
                    continue
        # Gerar pendência
        data_sug = (datetime.now() + timedelta(days=7)).date()
        run_exec(
            "INSERT INTO Regua_Pendencias (id_parceiro, tipo_acao, canal_sugerido, data_sugerida) "
            "VALUES (%s, %s, %s, %s)",
            (id_parceiro, item["acao"], item["canal"], data_sug)
        )


# ── Aba Relacionamento — funções por sub-aba ────────────────────────────
def _rel_tab_registrar(df_parceiros, df_interacoes):
    _rc1, _rc2 = st.columns([3, 2], gap="large")

    with _rc1:
        section("Nova interação")
        _TIPOS_INTERACAO = [
            "Almoço CDP", "Reunião presencial", "Ligação telefônica",
            "WhatsApp", "E-mail", "Visita ao parceiro",
            "Evento externo", "Envio de material", "Agradecimento", "Follow-up", "Outro",
        ]
        _CANAIS = ["Presencial", "WhatsApp", "E-mail", "Telefone", "Redes Sociais", "Plataforma"]

        with st.form("form_nova_interacao", clear_on_submit=True):
            _nomes_parc = sorted(df_parceiros["nome_instituicao"].dropna().tolist())
            _fi1, _fi2  = st.columns(2)
            _parc_sel   = _fi1.selectbox("Parceiro *", ["-- selecione --"] + _nomes_parc, key="ni_parc")
            _tipo_sel   = _fi2.selectbox("Tipo de interação *", _TIPOS_INTERACAO, key="ni_tipo")

            _fi3, _fi4  = st.columns(2)
            _canal_sel  = _fi3.selectbox("Canal", _CANAIS, key="ni_canal")
            _data_int   = _fi4.date_input("Data *", datetime.now().date(), key="ni_data")

            # Tipo público da régua (define quais automações gerar)
            _tipo_pub_atual = None
            _id_p_form_val  = None
            if _parc_sel != "-- selecione --":
                _row_p = df_parceiros[df_parceiros["nome_instituicao"] == _parc_sel]
                if not _row_p.empty:
                    _id_p_form_val  = int(_row_p["id_parceiro"].values[0])
                    _tipo_pub_atual = _row_p["tipo_publico_regua"].values[0]

            _opts_pub = ["(não definir)"] + list(REGUA_CONFIG.keys())
            _idx_pub  = 0
            if _tipo_pub_atual and _tipo_pub_atual in _opts_pub:
                _idx_pub = _opts_pub.index(_tipo_pub_atual)
            _tipo_pub_sel = st.selectbox(
                "Tipo de público (régua) — define automações",
                options=_opts_pub, index=_idx_pub, key="ni_pub"
            )

            # Contato envolvido
            _contatos_disp = [("Nenhum", None)]
            if _id_p_form_val:
                _ct = run_query(
                    "SELECT id_contato, nome_pessoa FROM Contato_Direto "
                    "WHERE id_parceiro = %s ORDER BY nome_pessoa",
                    (_id_p_form_val,)
                )
                if not _ct.empty:
                    _contatos_disp += [(r["nome_pessoa"], r["id_contato"]) for _, r in _ct.iterrows()]
            _contato_sel    = st.selectbox("Contato envolvido (opcional)",
                                           [c[0] for c in _contatos_disp], key="ni_contato")
            _id_contato_form = dict(_contatos_disp).get(_contato_sel)

            _descricao = st.text_area(
                "O que foi feito / conversado *",
                placeholder="Descreva o que aconteceu, decisoes, encaminhamentos...",
                height=100, key="ni_desc"
            )
            _fi5, _fi6  = st.columns(2)
            _prox_acao  = _fi5.text_input("Próxima ação", placeholder="ex: Enviar proposta", key="ni_prox")
            _prox_data  = _fi6.date_input("Data da próxima ação", value=None, key="ni_prox_data")
            _resp       = st.text_input("Responsável", placeholder="Quem fez o contato?", key="ni_resp")

            _submitted = st.form_submit_button("Registrar", type="primary", use_container_width=True)
            if _submitted:
                if _parc_sel == "-- selecione --":
                    st.warning("Selecione o parceiro.")
                elif not _descricao.strip():
                    st.warning("Descreva o que foi feito.")
                else:
                    _id_p_reg   = int(df_parceiros[df_parceiros["nome_instituicao"] == _parc_sel]["id_parceiro"].values[0])
                    _desc_final = f"[{_tipo_sel}] {_descricao.strip()}"
                    if _prox_acao.strip():
                        _desc_final += f" | Próxima ação: {_prox_acao.strip()}"
                    run_exec(
                        "INSERT INTO Registro_Relacionamento "
                        "(id_parceiro, id_contato, data_interacao, descricao_do_que_foi_feito, "
                        " proxima_acao_data, tipo_interacao, canal, responsavel) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            _id_p_reg, _id_contato_form, _data_int, _desc_final,
                            _prox_data if _prox_data else None,
                            _tipo_sel, _canal_sel,
                            _resp.strip() if _resp.strip() else None,
                        )
                    )
                    # Atualizar tipo_publico_regua do parceiro se selecionado
                    if _tipo_pub_sel != "(não definir)":
                        run_exec(
                            "UPDATE Parceiro SET tipo_publico_regua = %s WHERE id_parceiro = %s",
                            (_tipo_pub_sel, _id_p_reg)
                        )
                        # Gerar pendências da régua
                        _gerar_regua_pendências(_id_p_reg, _tipo_pub_sel)

                    run_exec("INSERT INTO Logs (acao) VALUES (%s)",
                             (f"Interação: {_parc_sel} — {_tipo_sel}",))
                    st.success(f"Interação com {_parc_sel} registrada.")
                    st.rerun()

    # ── Painel direito: alertas da régua para o parceiro selecionado ──────
    with _rc2:
        section("Régua de relacionamento")
        if "ni_parc" in st.session_state and st.session_state["ni_parc"] != "-- selecione --":
            _pn = st.session_state["ni_parc"]
            _row_sel = df_parceiros[df_parceiros["nome_instituicao"] == _pn]
            if not _row_sel.empty:
                _id_sel_reg = int(_row_sel["id_parceiro"].values[0])
                _pub_sel    = _row_sel["tipo_publico_regua"].values[0]
                if _pub_sel and _pub_sel in REGUA_CONFIG:
                    st.markdown(
                        f"<div style=\'font-size:0.8rem;color:#94A3B8;margin-bottom:8px;\'>"
                        f"Público: <b style='color:#E5E7EB;'>{_pub_sel}</b></div>",
                        unsafe_allow_html=True
                    )
                    _pend_parc = run_query(
                        "SELECT tipo_acao, canal_sugerido, data_sugerida FROM Regua_Pendencias "
                        "WHERE id_parceiro=%s AND status=\'PENDENTE\' ORDER BY data_sugerida",
                        (_id_sel_reg,)
                    )
                    if not _pend_parc.empty:
                        st.markdown("<div style=\'font-size:0.82rem;color:#FBBF24;font-weight:600;margin-bottom:4px;\'>Pendente para este parceiro:</div>", unsafe_allow_html=True)
                        for _, _rp in _pend_parc.iterrows():
                            _ds = str(_rp["data_sugerida"])[:10] if pd.notna(_rp["data_sugerida"]) else "—"
                            st.markdown(
                                f"<div style=\'padding:5px 10px;margin-bottom:4px;background:rgba(251,191,36,0.08);"
                                f"border-left:2px solid #FBBF24;border-radius:4px;font-size:0.82rem;\'>"
                                f"<b>{_rp['tipo_acao']}</b><br>"
                                f"<span style='color:#94A3B8;'>{_rp['canal_sugerido']} · ate {_ds}</span></div>",
                                unsafe_allow_html=True
                            )
                    else:
                        st.markdown("<div style=\'font-size:0.82rem;color:#059669;\'>Sem pendências na régua para este parceiro.</div>", unsafe_allow_html=True)
                else:
                    st.info("Defina o tipo de público (campo acima) para ativar as automações da régua.")
        else:
            # Mostrar referência geral da régua
            st.markdown("<div style=\'font-size:0.82rem;color:#94A3B8;margin-bottom:8px;\'>Ações por tipo de público:</div>", unsafe_allow_html=True)
            _REGUA_REF = [
                ("Parceiros importantes", ["Agradec. personalizado", "Destaque em redes", "Mensagem mensal", "Boletim semanal", "Brindes", "Boas festas", "Balanço Social"]),
                ("Financiador",           ["Agradec. personalizado", "Destaque em redes", "Mensagem mensal", "Mensagem campanha", "Boletim semanal", "Brindes", "Balanço Social"]),
                ("Imprensa",              ["Agradec. padrao", "Mensagem mensal", "Mensagem campanha", "Boletim semanal"]),
                ("Doadores Especiais",    ["Agradec. personalizado", "Mensagem mensal", "Boletim semanal", "Brindes"]),
                ("Doador Pontual",        ["Boas-vindas", "Agradec. padrao", "Boletim semanal"]),
                ("Voluntário",            ["Aniversário", "Mensagem mensal", "Boletim semanal"]),
                ("Apoiadores de Eventos", ["Agradec. padrao", "Mensagem mensal"]),
                ("Conselho e diretoria",  ["Aniversário", "Mensagem mensal", "Boletim semanal", "Balanço Social"]),
            ]
            for _pub, _acoes in _REGUA_REF:
                with st.expander(_pub, expanded=False):
                    for _a in _acoes:
                        st.markdown(f"- {_a}")

    # ── Últimas interações ────────────────────────────────────────────────
    st.divider()
    section("Últimas interações registradas")
    _df_ult     = df_interacoes.head(8) if not df_interacoes.empty else pd.DataFrame()
    _nomes_map  = df_parceiros.set_index("id_parceiro")["nome_instituicao"].to_dict()
    if _df_ult.empty:
        st.info("Nenhuma interação registrada ainda.")
    else:
        for _, _r in _df_ult.iterrows():
            _nome_p  = _nomes_map.get(_r["id_parceiro"], "—")
            _data_r  = str(_r["data_interacao"])[:10] if pd.notna(_r["data_interacao"]) else "—"
            _tipo_r  = str(_r.get("tipo_interacao", "")) if pd.notna(_r.get("tipo_interacao")) else ""
            _tipo_tag = (f"<span style=\'background:rgba(59,130,246,0.18);color:#93C5FD;"
                         f"padding:1px 8px;border-radius:10px;font-size:0.78rem;margin-right:6px;\'>"
                         f"{_tipo_r}</span>") if _tipo_r else ""
            _desc_r  = str(_r["descricao_do_que_foi_feito"])[:130] if pd.notna(_r["descricao_do_que_foi_feito"]) else "—"
            _resp_r  = str(_r.get("responsavel", "")) if pd.notna(_r.get("responsavel")) else ""
            _resp_tag = (f" <span style='font-size:0.75rem;color:#64748B;'>por {_resp_r}</span>") if _resp_r else ""
            st.markdown(
                f"<div style=\'padding:8px 14px;margin-bottom:6px;background:rgba(255,255,255,0.04);"
                f"border-radius:8px;border-left:3px solid #3B82F6;\'>"
                f"<div style=\'display:flex;justify-content:space-between;\'>"
                f"<span style='font-weight:600;color:#E5E7EB;'>{_nome_p}</span>"
                f"<span style='font-size:0.78rem;color:#94A3B8;'>{_data_r}</span></div>"
                f"<div style='margin-top:3px;'>{_tipo_tag}"
                f"<span style='font-size:0.87rem;color:#CBD5E1;'>{_desc_r}</span>"
                f"{_resp_tag}</div></div>",
                unsafe_allow_html=True
            )

# ══════════════════════════════════════════════════════════════════════════
# ABA 2 — PARCEIROS
# ══════════════════════════════════════════════════════════════════════════


def _rel_tab_parceiros(df_parceiros, hoje):

    # ── Parceiros sem toque ───────────────────────────────────────────────
    section("Parceiros sem toque")

    _st_col1, _st_col2 = st.columns([3, 1])
    _limiar_dias = _st_col2.selectbox(
        "Sem contato ha mais de:", [30, 60, 90, 180],
        index=1, key="st_limiar", format_func=lambda x: f"{x} dias"
    )

    df_sem_toque = run_query_slow(
        "SELECT p.id_parceiro, p.nome_instituicao, p.status, "
        "MAX(r.data_interacao) AS ultimo_contato "
        "FROM Parceiro p "
        "LEFT JOIN Registro_Relacionamento r ON p.id_parceiro = r.id_parceiro "
        "WHERE UPPER(TRIM(p.status)) IN ('ATIVO', 'PROSPECCAO', 'PROSPECÇÃO') "
        "GROUP BY p.id_parceiro, p.nome_instituicao, p.status "
        "ORDER BY ultimo_contato ASC NULLS FIRST"
    )

    if not df_sem_toque.empty:
        df_sem_toque["_ultimo"] = pd.to_datetime(df_sem_toque["ultimo_contato"], errors="coerce").dt.date
        df_sem_toque["_dias_sem"] = df_sem_toque["_ultimo"].apply(
            lambda d: (hoje - d).days if pd.notna(d) else 9999
        )
        df_st_show = df_sem_toque[df_sem_toque["_dias_sem"] >= _limiar_dias].copy()

        with _st_col1:
            _st_busca = st.text_input("Filtrar por nome:", key="st_busca")
        if _st_busca:
            df_st_show = df_st_show[df_st_show["nome_instituicao"].str.contains(_st_busca, case=False, na=False)]

        _total_st = len(df_st_show)
        if _total_st == 0:
            st.success(f"Todos os parceiros ativos foram contatados nos últimos {_limiar_dias} dias.")
        else:
            st.markdown(
                f"<div style='font-size:0.85rem;color:#F59E0B;margin-bottom:12px;'>"
                f"<b>{_total_st}</b> parceiro(s) sem contato ha mais de <b>{_limiar_dias} dias</b>"
                f"</div>",
                unsafe_allow_html=True
            )
            for _, _sr in df_st_show.iterrows():
                _dias_label = "Nunca contatado" if _sr["_dias_sem"] >= 9999 else f"Último contato há {_sr['_dias_sem']}d"
                if _sr["_dias_sem"] >= 9999 or _sr["_dias_sem"] >= 180:
                    _tom_st = "danger"
                else:
                    _tom_st = "warning"
                _data_label = (
                    f"Ultimo: {_sr['_ultimo'].strftime('%d/%m/%Y')}"
                    if pd.notna(_sr["_ultimo"]) else "Sem histórico"
                )
                action_card(
                    titulo=str(_sr["nome_instituicao"]),
                    meta_parts=[str(_sr.get("status", "")), _data_label, _dias_label],
                    tom=_tom_st,
                )
    else:
        st.info("Nenhum parceiro ativo encontrado.")

    st.divider()

    # ── Histórico por parceiro ────────────────────────────────────────────
    section("Histórico por parceiro")

    _tl1, _tl2 = st.columns([2, 1])
    p_lista = ["-- selecione --"] + sorted(df_parceiros["nome_instituicao"].dropna().tolist())
    sel_p   = _tl1.selectbox("Parceiro:", p_lista, key="tl_parceiro")

    if sel_p != "-- selecione --":
        _row_tl  = df_parceiros[df_parceiros["nome_instituicao"] == sel_p]
        id_p     = int(_row_tl["id_parceiro"].values[0])
        _pub_tl  = _row_tl["tipo_publico_regua"].values[0] if not _row_tl.empty else None

        # KPIs do parceiro no topo direito
        with _tl2:
            if _pub_tl:
                st.markdown(
                    f"<div style=\'font-size:0.82rem;color:#94A3B8;margin-top:28px;\'>Tipo público: "
                    f"<b style='color:#E5E7EB;'>{_pub_tl}</b></div>", unsafe_allow_html=True
                )
            _pend_tl = run_query(
                "SELECT COUNT(*) AS n FROM Regua_Pendencias WHERE id_parceiro=%s AND status=\'PENDENTE\'",
                (id_p,)
            )
            if not _pend_tl.empty:
                _n_pend = int(_pend_tl["n"].values[0])
                if _n_pend > 0:
                    st.warning(f"{_n_pend} pendência(s) da régua para este parceiro.")

        hist_int = run_query(
            "SELECT data_interacao AS data, descricao_do_que_foi_feito AS descricao, "
            "proxima_acao_data, tipo_interacao, canal, responsavel "
            "FROM Registro_Relacionamento WHERE id_parceiro = %s "
            "ORDER BY data_interacao DESC", (id_p,)
        )
        hist_doa = run_query(
            "SELECT data_doacao AS data, tipo_doacao AS tipo, "
            "descricao AS descricao, valor_estimado "
            "FROM Doacao WHERE id_parceiro = %s ORDER BY data_doacao DESC", (id_p,)
        )

        if hist_int.empty and hist_doa.empty:
            empty_state("—", "Sem histórico", "Nenhuma interação ou doação registrada para este parceiro.")
        else:
            # Totais
            total_int     = len(hist_int)
            total_doa_val = hist_doa["valor_estimado"].fillna(0).sum() if not hist_doa.empty else 0
            total_doa_fmt = f"R$ {total_doa_val:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            kpi_row([
                {"label": "Interações",       "value": total_int},
                {"label": "Total doado",       "value": total_doa_fmt},
            ])

            # Unifica e ordena
            eventos = []
            for _, r in hist_int.iterrows():
                tipo_r = str(r["tipo_interacao"]) if pd.notna(r.get("tipo_interacao")) else "Interacao"
                resp_r = str(r["responsavel"])    if pd.notna(r.get("responsavel"))    else ""
                eventos.append({
                    "data":    pd.to_datetime(r["data"], errors="coerce"),
                    "label":   tipo_r,
                    "desc":    str(r["descricao"]) if pd.notna(r["descricao"]) else "—",
                    "extra":   (f"Proxima acao: {r['proxima_acao_data']}" if pd.notna(r.get("proxima_acao_data")) else None),
                    "extra2":  f"por {resp_r}" if resp_r else None,
                    "cor":     "#3B82F6",
                })
            for _, r in hist_doa.iterrows():
                val     = r["valor_estimado"] if pd.notna(r["valor_estimado"]) else 0
                val_fmt = f"R$ {val:,.2f}".replace(",","X").replace(".",",").replace("X",".")
                eventos.append({
                    "data":   pd.to_datetime(r["data"], errors="coerce"),
                    "label":  str(r["tipo"]) if pd.notna(r["tipo"]) else "Doação",
                    "desc":   str(r["descricao"]) if pd.notna(r["descricao"]) else "—",
                    "extra":  f"Valor: {val_fmt}" if val > 0 else None,
                    "extra2": None,
                    "cor":    "#059669",
                })

            eventos.sort(key=lambda e: e["data"] or pd.Timestamp("1900-01-01"), reverse=True)

            for ev in eventos:
                data_str  = ev["data"].strftime("%d/%m/%Y") if ev["data"] is not pd.NaT else "—"
                cor       = ev["cor"]
                extra_h   = f"<div style='margin-top:4px;font-size:0.8rem;color:#94A3B8;'>{ev['extra']}</div>" if ev["extra"] else ""
                extra2_h  = f"<div style='font-size:0.75rem;color:#64748B;'>{ev['extra2']}</div>" if ev["extra2"] else ""
                st.markdown(
                    f"<div style=\'display:flex;gap:10px;margin-bottom:12px;\'>"
                    f"<div style=\'flex-shrink:0;width:32px;height:32px;border-radius:50%;"
                    f"background:{cor}22;border:2px solid {cor};display:flex;align-items:center;"
                    f"justify-content:center;font-size:11px;font-weight:700;color:{cor};'>"
                    f"{'I' if cor == '#3B82F6' else 'R$'}</div>"
                    f"<div style=\'flex:1;background:rgba(255,255,255,0.04);border-radius:8px;"
                    f"padding:8px 12px;border-left:3px solid {cor};'>"
                    f"<div style=\'display:flex;justify-content:space-between;\'>"
                    f"<span style='font-weight:600;font-size:0.88rem;color:#E5E7EB;'>{ev['label']}</span>"
                    f"<span style=\'font-size:0.78rem;color:#94A3B8;background:rgba(255,255,255,0.08);"
                    f"padding:1px 7px;border-radius:10px;'>{data_str}</span></div>"
                    f"<div style='margin-top:4px;font-size:0.9rem;color:#CBD5E1;'>{ev['desc']}</div>"
                    f"{extra_h}{extra2_h}</div></div>",
                    unsafe_allow_html=True
                )

# ══════════════════════════════════════════════════════════════════════════
# ABA 3 — FOLLOW-UPS
# ══════════════════════════════════════════════════════════════════════════


def _rel_tab_followups(df_regua_pend, hoje):
    _fu_sub1, _fu_sub2 = st.tabs(["Follow-ups manuais", "Pendências da régua"])

    # ── Sub-aba: Follow-ups manuais ───────────────────────────────────────
    with _fu_sub1:
        section("Agenda de follow-ups")
        df_fu = run_query_cached(
            "SELECT * FROM ("
            "  SELECT DISTINCT ON (r.id_parceiro) "
            "    r.id_registro, r.proxima_acao_data, p.nome_instituicao, "
            "    r.id_parceiro, r.data_interacao, r.tipo_interacao "
            "  FROM Registro_Relacionamento r "
            "  JOIN Parceiro p ON r.id_parceiro = p.id_parceiro "
            "  WHERE r.proxima_acao_data IS NOT NULL "
            "  ORDER BY r.id_parceiro, r.proxima_acao_data DESC"
            ") sub ORDER BY proxima_acao_data ASC"
        )

        if df_fu.empty:
            empty_state("—", "Nenhum follow-up agendado",
                        "Ao registrar uma interação, preencha \'Próxima ação\' para aparecer aqui.")
        else:
            df_fu["_data"] = pd.to_datetime(df_fu["proxima_acao_data"], errors="coerce").dt.date
            df_fu["_dias"] = df_fu["_data"].apply(lambda d: (d - hoje).days if d else 999)

            _ff1, _ff2 = st.columns(2)
            _filtro_per = _ff1.selectbox("Período:", ["Todos", "Vencidos", "Esta semana", "Este mês", "Futuros"], key="fu_periodo")
            _filtro_par = _ff2.text_input("Filtrar por parceiro:", key="fu_parc")

            df_fshow = df_fu.copy()
            if _filtro_per == "Vencidos":      df_fshow = df_fshow[df_fshow["_dias"] < 0]
            elif _filtro_per == "Esta semana":  df_fshow = df_fshow[(df_fshow["_dias"] >= 0) & (df_fshow["_dias"] <= 7)]
            elif _filtro_per == "Este mês":     df_fshow = df_fshow[(df_fshow["_dias"] >= 0) & (df_fshow["_dias"] <= 30)]
            elif _filtro_per == "Futuros":      df_fshow = df_fshow[df_fshow["_dias"] > 30]
            if _filtro_par:
                df_fshow = df_fshow[df_fshow["nome_instituicao"].str.contains(_filtro_par, case=False, na=False)]

            if df_fshow.empty:
                st.info("Nenhum follow-up encontrado para o filtro selecionado.")
            else:
                for _, row in df_fshow.iterrows():
                    dias = int(row["_dias"])
                    if   dias < 0:  tom = "danger";  badge = f"Vencido ha {abs(dias)}d"
                    elif dias == 0: tom = "warning"; badge = "Hoje"
                    elif dias <= 7: tom = "warning"; badge = f"Em {dias}d"
                    else:           tom = "info";    badge = f"Em {dias}d"
                    data_fmt = row["_data"].strftime("%d/%m/%Y") if row["_data"] else "—"
                    _fuc1, _fuc2 = st.columns([5, 1])
                    with _fuc1:
                        action_card(
                            titulo=str(row["nome_instituicao"]),
                            meta_parts=[
                                str(row.get("tipo_interacao","")) or "Follow-up",
                                f"Prazo: {data_fmt} ({badge})"
                            ],
                            tom=tom,
                        )
                    with _fuc2:
                        _fk = f"fu_done_{row.get('id_registro','')}"
                        if st.button("Feito", key=_fk, use_container_width=True):
                            _id_p_fu = int(row["id_parceiro"]) if pd.notna(row.get("id_parceiro")) else None
                            if _id_p_fu:
                                run_exec(
                                    "INSERT INTO Registro_Relacionamento "
                                    "(id_parceiro, data_interacao, descricao_do_que_foi_feito, tipo_interacao) "
                                    "VALUES (%s, %s, %s, %s)",
                                    (_id_p_fu, hoje, f"Follow-up concluído (prazo: {data_fmt})", "Follow-up")
                                )
                                run_exec(
                                    "UPDATE Registro_Relacionamento "
                                    "SET proxima_acao_data = NULL "
                                    "WHERE id_parceiro = %s "
                                    "AND proxima_acao_data IS NOT NULL "
                                    "AND proxima_acao_data::date < CURRENT_DATE",
                                    (_id_p_fu,)
                                )
                                st.success(f"Follow-up de {row['nome_instituicao']} concluído.")
                                st.rerun()

    # ── Sub-aba: Pendências da Régua ──────────────────────────────────────
    with _fu_sub2:
        section("Pendências geradas pela régua")

        if df_regua_pend.empty:
            st.success("Nenhuma pendência da régua no momento.")
        else:
            # Filtro por parceiro
            _rp_parc = st.text_input("Filtrar por parceiro:", key="rp_parc_filtro")
            _df_rp = df_regua_pend.copy()
            if _rp_parc:
                _df_rp = _df_rp[_df_rp["nome_instituicao"].str.contains(_rp_parc, case=False, na=False)]

            # Agrupar por parceiro
            _parceiros_pend = _df_rp["nome_instituicao"].unique() if not _df_rp.empty else []
            for _np in _parceiros_pend:
                _df_p_rp = _df_rp[_df_rp["nome_instituicao"] == _np]
                with st.expander(f"{_np}  ({len(_df_p_rp)} pendência(s))", expanded=True):
                    for _, _rp in _df_p_rp.iterrows():
                        _ds    = str(_rp["data_sugerida"])[:10] if pd.notna(_rp["data_sugerida"]) else "—"
                        _dias_rp = (pd.to_datetime(_rp["data_sugerida"]).date() - hoje).days if pd.notna(_rp["data_sugerida"]) else 0
                        _cor_rp  = "#DC2626" if _dias_rp < 0 else "#D97706" if _dias_rp <= 7 else "#3B82F6"
                        _rp_c1, _rp_c2, _rp_c3 = st.columns([4, 2, 1])
                        _rp_c1.markdown(
                            f"<div style='font-size:0.9rem;color:#E5E7EB;font-weight:600;'>{_rp['tipo_acao']}</div>"
                            f"<div style='font-size:0.78rem;color:#94A3B8;'>{_rp['canal_sugerido']}</div>",
                            unsafe_allow_html=True
                        )
                        _rp_c2.markdown(
                            f"<div style='font-size:0.82rem;color:{_cor_rp};margin-top:4px;'>ate {_ds}</div>",
                            unsafe_allow_html=True
                        )
                        _rp_btn_key = f"rp_feito_{_rp['id']}"
                        _rp_ign_key = f"rp_ign_{_rp['id']}"
                        if _rp_c3.button("Feito", key=_rp_btn_key, use_container_width=True):
                            run_exec(
                                "UPDATE Regua_Pendencias SET status=\'FEITO\', feito_em=NOW() WHERE id=%s",
                                (int(_rp["id"]),)
                            )
                            # Registrar como interacao
                            run_exec(
                                "INSERT INTO Registro_Relacionamento "
                                "(id_parceiro, data_interacao, descricao_do_que_foi_feito, tipo_interacao) "
                                "VALUES (%s, %s, %s, %s)",
                                (int(_rp["id_parceiro"]), hoje,
                                 f"[Régua] {_rp['tipo_acao']} — concluído", _rp["tipo_acao"])
                            )
                            st.success(f"{_rp['tipo_acao']} marcado como feito.")
                            st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# ABA 4 — RÉGUA DE RELACIONAMENTO
# ══════════════════════════════════════════════════════════════════════════


def _rel_tab_regua():
    section("Matriz da régua de relacionamento")

    # ── Matriz visual fiel à planilha ─────────────────────────────────────
    _CORES_EQUIPE = {
        "DI":           "#DC2626",
        "Telemarketing":"#3B82F6",
        "Eq. Tecnica":  "#EA580C",
        "Plataforma":   "#16A34A",
        "RH":           "#BE185D",
        "Responsavel":  "#CA8A04",
    }
    _LABEL_EQUIPE = {
        "DI":           "DI",
        "Telemarketing":"Telemarketing",
        "Eq. Tecnica":  "Eq. Técnica",
        "Plataforma":   "Plataforma",
        "RH":           "RH",
        "Responsavel":  "Responsável pela ação",
    }
    _ABREV_EQUIPE = {
        "DI":           "DI",
        "Telemarketing":"TM",
        "Eq. Tecnica":  "ET",
        "Plataforma":   "PL",
        "RH":           "RH",
        "Responsavel":  "RP",
    }
    # ── Colunas fixas da matriz (12 ações canônicas) ──────────────────────
    _ACOES_HEADER = [
        "Aniversário", "Boas-vindas", "Agradec. padrão", "Agradec. person.",
        "Agradec. auto", "Destaque redes", "Msg. mensais", "Msg. esporádicas",
        "Boletim", "Brindes", "Boas Festas", "Balanço Social",
    ]
    _ACOES_FULL = [
        "Cartão de aniversário digital", "Boas-vindas", "Agradecimento padrão",
        "Agradecimento personalizado", "Agradecimento automático",
        "Destaque de reconhecimento nas redes sociais",
        "Mensagens mensais: Notícias, datas comemorativas",
        "Mensagens esporádicas de campanhas via WhatsApp ou e-mail",
        "Boletim Semanal via e-mail e WhatsApp",
        "Brindes em datas comemorativas (Mídia Kit)",
        "Cartão de Boas Festas Digital", "Balanço Social físico ou digital",
    ]
    # Mapa: nome longo da coluna → nome da ação no banco (REGUA_CONFIG usa nomes curtos)
    _ACOES_DB = [
        "Cartao de aniversario digital", "Boas-vindas", "Agradecimento padrao",
        "Agradecimento personalizado",   "Agradecimento automatico",
        "Destaque em redes + Selo Amigo", "Mensagem mensal", "Mensagem de campanha",
        "Boletim semanal", "Brindes e datas comemorativas",
        "Cartao de boas festas digital", "Balanço Social",
    ]
    # Ordem canônica das linhas
    _TIPOS_ORDER = [
        "Acolhidos", "Doador via site", "Doador pontual", "Doadores em geral",
        "Doadores especiais: não mon.", "Parceiros importantes", "Financiador",
        "Imprensa", "Voluntário", "Visitantes", "Apoiadores de eventos",
        "Conselho e diretoria", "Funcionário", "Fornecedores",
    ]

    # ── Buscar atribuições de equipe do banco ──────────────────────────────
    _df_rm = run_query_cached(
        "SELECT tipo_publico, acao, responsavel FROM Regua_Matriz WHERE ativo = TRUE"
    )
    # pivot: {(tipo_publico, col_idx): equipe}
    _rm_pivot: dict = {}
    if not _df_rm.empty:
        _acao_to_col = {acao: i for i, acao in enumerate(_ACOES_DB)}
        for _, _rm_row in _df_rm.iterrows():
            _col = _acao_to_col.get(_rm_row["acao"])
            if _col is not None and _rm_row["responsavel"]:
                _rm_pivot[(_rm_row["tipo_publico"], _col)] = _rm_row["responsavel"]

    # Linhas = tipos com pelo menos 1 ação no banco; respeitar _TIPOS_ORDER
    _tipos_db = set(_df_rm["tipo_publico"].unique()) if not _df_rm.empty else set()
    _tipos_matrix = [t for t in _TIPOS_ORDER if t in _tipos_db] or _TIPOS_ORDER

    _th_style = "background:#1e293b;color:#94a3b8;font-size:10px;font-weight:700;text-align:center;padding:6px 4px;border:1px solid #334155;white-space:nowrap;"
    _td_pub_style = "background:#1e293b;color:#e2e8f0;font-size:11px;font-weight:600;padding:6px 10px;border:1px solid #334155;white-space:nowrap;"

    _html_rows = ""
    for pub in _tipos_matrix:
        _cells = f"<td style='{_td_pub_style}'>{pub}</td>"
        for _col_idx in range(len(_ACOES_HEADER)):
            equipe = _rm_pivot.get((pub, _col_idx))
            if equipe:
                _cor = _CORES_EQUIPE.get(equipe, "#64748b")
                _abrev = _ABREV_EQUIPE.get(equipe, equipe[:2].upper())
                _label = _LABEL_EQUIPE.get(equipe, equipe)
                _cells += (
                    f"<td style='background:{_cor}22;border:1px solid #334155;"
                    f"text-align:center;padding:4px 2px;' title='{_label}'>"
                    f"<span style='display:inline-block;width:22px;height:22px;border-radius:50%;"
                    f"background:{_cor};color:#fff;font-size:9px;font-weight:700;"
                    f"line-height:22px;text-align:center;'>{_abrev}</span></td>"
                )
            else:
                _cells += "<td style='background:#0f172a;border:1px solid #1e293b;'></td>"
        _html_rows += f"<tr>{_cells}</tr>"

    _header_cells = f"<th style='{_th_style}'>Público</th>"
    for h in _ACOES_HEADER:
        _header_cells += f"<th style='{_th_style}' title='{_ACOES_FULL[_ACOES_HEADER.index(h)]}'>{h}</th>"

    _legend_html = "".join([
        f"<span style='display:inline-flex;align-items:center;gap:5px;margin-right:14px;font-size:11px;color:#94a3b8;'>"
        f"<span style='width:14px;height:14px;border-radius:50%;background:{cor};display:inline-block;'></span>"
        f"{_LABEL_EQUIPE.get(eq, eq)}</span>"
        for eq, cor in _CORES_EQUIPE.items()
    ])

    st.markdown(
        f"<div style='overflow-x:auto;'>"
        f"<table style='border-collapse:collapse;width:100%;'>"
        f"<thead><tr>{_header_cells}</tr></thead>"
        f"<tbody>{_html_rows}</tbody>"
        f"</table></div>"
        f"<div style='margin-top:10px;display:flex;flex-wrap:wrap;'>{_legend_html}</div>",
        unsafe_allow_html=True
    )

    st.divider()

    section("Compliance da régua de relacionamento")

    # ── Botão de sincronização em massa ──────────────────────────────
    _sc1, _sc2 = st.columns([3, 1])
    with _sc2:
        if st.button("Sincronizar pendências", use_container_width=True, type="primary"):
            _parceiros_para_sync = run_query(
                "SELECT id_parceiro, tipo_publico_regua FROM Parceiro "
                "WHERE tipo_publico_regua IS NOT NULL AND tipo_publico_regua != '' "
                "AND UPPER(TRIM(status)) IN ('ATIVO', 'PROSPECCAO', 'PROSPECÇÃO')"
            )
            _gerados = 0
            for _, _pr in _parceiros_para_sync.iterrows():
                before = run_query(
                    "SELECT COUNT(*) AS n FROM Regua_Pendencias WHERE id_parceiro=%s AND status='PENDENTE'",
                    (int(_pr["id_parceiro"]),)
                )["n"].values[0]
                _gerar_regua_pendências(int(_pr["id_parceiro"]), _pr["tipo_publico_regua"])
                after = run_query(
                    "SELECT COUNT(*) AS n FROM Regua_Pendencias WHERE id_parceiro=%s AND status='PENDENTE'",
                    (int(_pr["id_parceiro"]),)
                )["n"].values[0]
                _gerados += max(0, int(after) - int(before))
            st.success(f"{_gerados} nova(s) pendência(s) gerada(s) para {len(_parceiros_para_sync)} parceiro(s).")
            st.rerun()

    with _sc1:
        st.markdown(
            "<div style='font-size:0.82rem;color:#94A3B8;padding-top:10px;'>"
            "Gera automaticamente as pendências previstas pela régua para todos os parceiros ativos "
            "que ainda não as possuem, respeitando a periodicidade de cada ação."
            "</div>",
            unsafe_allow_html=True
        )

    st.divider()

    # ── Painel de cobertura por tipo de público ───────────────────────
    df_compliance = run_query_slow(
        "SELECT p.tipo_publico_regua, "
        "COUNT(DISTINCT p.id_parceiro) AS total_parceiros, "
        "COUNT(DISTINCT CASE WHEN rp.status IS NOT NULL THEN p.id_parceiro END) AS com_pendências, "
        "COUNT(DISTINCT CASE WHEN rp.status='PENDENTE' THEN rp.id END) AS pendentes, "
        "COUNT(DISTINCT CASE WHEN rp.status='FEITO' THEN rp.id END) AS concluídas "
        "FROM Parceiro p "
        "LEFT JOIN Regua_Pendencias rp ON p.id_parceiro = rp.id_parceiro "
        "WHERE p.tipo_publico_regua IS NOT NULL AND p.tipo_publico_regua != '' "
        "GROUP BY p.tipo_publico_regua "
        "ORDER BY total_parceiros DESC"
    )

    if df_compliance.empty:
        st.info("Nenhum parceiro com tipo de público da régua cadastrado.")
    else:
        # KPIs gerais
        _ck1, _ck2, _ck3 = st.columns(3)
        _total_parc_regua = int(df_compliance["total_parceiros"].sum())
        _total_com_pend   = int(df_compliance["com_pendências"].sum())
        _total_pendentes  = int(df_compliance["pendentes"].sum())
        _total_concluídas = int(df_compliance["concluídas"].sum())
        _cobertura_pct    = round(_total_com_pend / _total_parc_regua * 100) if _total_parc_regua else 0

        _ck1.metric("Parceiros na régua", _total_parc_regua)
        _ck2.metric("Com pendências ativas", f"{_total_com_pend} ({_cobertura_pct}%)")
        _ck3.metric("Acoes concluídas (total)", _total_concluídas)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # Detalhe por tipo de público
        for _, _cr in df_compliance.iterrows():
            _tipo     = _cr["tipo_publico_regua"]
            _total    = int(_cr["total_parceiros"])
            _com_p    = int(_cr["com_pendências"])
            _pend     = int(_cr["pendentes"])
            _conc     = int(_cr["concluídas"])
            _acoes_previstas = len(_get_regua_config_db().get(_tipo, []))
            _cobert   = round(_com_p / _total * 100) if _total else 0

            if _cobert >= 80:   _cor_cob = "#34d399"
            elif _cobert >= 50: _cor_cob = "#fbbf24"
            else:               _cor_cob = "#f87171"

            st.markdown(
                f"<div style='background:#1e293b;border:1px solid #334155;border-radius:8px;"
                f"padding:12px 16px;margin-bottom:8px;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                f"<div>"
                f"<span style='font-size:0.9rem;font-weight:700;color:#e2e8f0;'>{_tipo}</span>"
                f"<span style='font-size:0.78rem;color:#94a3b8;margin-left:10px;'>"
                f"{_total} parceiro(s) · {_acoes_previstas} ação(ões) prevista(s) na régua</span>"
                f"</div>"
                f"<div style='text-align:right;'>"
                f"<span style='font-size:0.85rem;color:{_cor_cob};font-weight:700;'>{_cobert}% cobertura</span>"
                f"<span style='font-size:0.75rem;color:#64748b;margin-left:12px;'>"
                f"{_pend} pendentes · {_conc} concluídas</span>"
                f"</div>"
                f"</div>"
                f"<div style='margin-top:8px;height:4px;background:#0f172a;border-radius:2px;'>"
                f"<div style='height:4px;width:{_cobert}%;background:{_cor_cob};border-radius:2px;'></div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.divider()

    # ── Editor da Régua Matriz ────────────────────────────────────────
    with st.expander("Editar régua de relacionamento", expanded=False):
        df_matriz = run_query(
            "SELECT id, tipo_publico, acao, periodo_dias, canal, responsavel, ativo "
            "FROM Regua_Matriz ORDER BY tipo_publico, id"
        )

        if not df_matriz.empty:
            _tipos_disponiveis = sorted(df_matriz["tipo_publico"].unique().tolist())
            _ed_tipo = st.selectbox(
                "Tipo de público:", _tipos_disponiveis, key="rm_tipo_sel"
            )
            df_orig = df_matriz[df_matriz["tipo_publico"] == _ed_tipo].copy()

            _equipes = ["DI","Telemarketing","Eq. Tecnica","Plataforma","RH","Responsavel"]

            df_edited = st.data_editor(
                df_orig[["id","acao","periodo_dias","canal","responsavel","ativo"]],
                column_config={
                    "id":           st.column_config.NumberColumn("ID",            disabled=True, width="small"),
                    "acao":         st.column_config.TextColumn("Ação",            width="large"),
                    "periodo_dias": st.column_config.NumberColumn("Período (dias)", min_value=0, step=1),
                    "canal":        st.column_config.TextColumn("Canal"),
                    "responsavel":  st.column_config.SelectboxColumn("Equipe",     options=_equipes),
                    "ativo":        st.column_config.CheckboxColumn("Ativo",       width="small"),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="dynamic",
                key="rm_data_editor",
            )

            _sv_col, _del_col = st.columns([1, 3])
            if _sv_col.button("Salvar alterações", key="rm_save_btn", type="primary", use_container_width=True):
                _orig_ids = set(df_orig["id"].tolist())
                _edit_ids = set(df_edited["id"].dropna().astype(int).tolist())

                # Linhas removidas → DELETE
                for _del_id in _orig_ids - _edit_ids:
                    run_exec("DELETE FROM Regua_Matriz WHERE id = %s", (int(_del_id),))

                for _, _erow in df_edited.iterrows():
                    _row_id = _erow.get("id")
                    _acao   = (_erow["acao"] or "").strip()
                    if not _acao:
                        continue
                    _periodo = int(_erow["periodo_dias"]) if pd.notna(_erow.get("periodo_dias")) and _erow["periodo_dias"] else None
                    _canal   = (_erow.get("canal") or "").strip() or None
                    _resp    = _erow.get("responsavel") or "DI"
                    _ativo   = bool(_erow.get("ativo", True))

                    if pd.notna(_row_id):  # linha existente → UPDATE
                        run_exec(
                            "UPDATE Regua_Matriz "
                            "SET acao=%s, periodo_dias=%s, canal=%s, responsavel=%s, ativo=%s "
                            "WHERE id=%s",
                            (_acao, _periodo, _canal, _resp, _ativo, int(_row_id))
                        )
                    else:  # linha nova → INSERT
                        run_exec(
                            "INSERT INTO Regua_Matriz (tipo_publico, acao, periodo_dias, canal, responsavel, ativo) "
                            "VALUES (%s, %s, %s, %s, %s, %s) "
                            "ON CONFLICT (tipo_publico, acao) DO NOTHING",
                            (_ed_tipo, _acao, _periodo, _canal, _resp, _ativo)
                        )

                st.success("Alterações salvas.")
                st.rerun()

# ABA 5 — RELATÓRIO PARA A DIRETORIA
# ══════════════════════════════════════════════════════════════════════════


def _rel_tab_relatorio(df_rel):
    st.markdown("### Extrair atualizações de parcerias")
    st.write("Gerar um resumo estratégico (ações manuais e doações recebidas) para reportar à direção.")

    c_inicio, c_fim = st.columns(2)
    data_inicio = c_inicio.date_input("Data inicial", datetime.now() - timedelta(days=7), key="dt_ini_rel")
    data_fim    = c_fim.date_input("Data final",    datetime.now(),                       key="dt_fim_rel")

    if st.button("Gerar relatório de atividades", type="primary", use_container_width=True):
        d_ini = data_inicio.strftime('%Y-%m-%d')
        d_fim = data_fim.strftime('%Y-%m-%d')

        df_rel_int = run_query("""
            SELECT p.nome_instituicao,
                   r.data_interacao AS data_registro,
                   'RELACIONAMENTO' AS tipo,
                   r.descricao_do_que_foi_feito AS descricao,
                   0 AS valor_estimado
            FROM Registro_Relacionamento r
            JOIN Parceiro p ON r.id_parceiro = p.id_parceiro
            WHERE r.data_interacao BETWEEN %s AND %s
              AND r.descricao_do_que_foi_feito NOT LIKE 'Sistema:%%'
        """, (d_ini, d_fim))

        df_rel_doa = run_query("""
            SELECT p.nome_instituicao,
                   d.data_doacao AS data_registro,
                   CONCAT('DOAÇÃO (', d.tipo_doacao, ')') AS tipo,
                   d.descricao AS descricao,
                   COALESCE(d.valor_estimado, 0) AS valor_estimado
            FROM Doacao d
            JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
            WHERE d.data_doacao BETWEEN %s AND %s
        """, (d_ini, d_fim))

        df_relatorio = pd.concat([df_rel_int, df_rel_doa], ignore_index=True)
        if not df_relatorio.empty:
            df_relatorio = df_relatorio.sort_values('data_registro', ascending=False)

        if df_relatorio.empty:
            st.info("Nenhuma atividade registrada no período selecionado.")
        else:
            dt_ini_fmt = data_inicio.strftime('%d/%m/%Y')
            dt_fim_fmt = data_fim.strftime('%d/%m/%Y')
            texto_diretoria = f"*RESUMO ESTRATÉGICO DI - {dt_ini_fmt} a {dt_fim_fmt}*\n\n"
            html_relatorio  = (
                f'<div class="glass-card"><h4 style="color:#00CC96;margin-top:0;text-align:center;">'
                f'RESUMO: {dt_ini_fmt} a {dt_fim_fmt}</h4>'
                f'<hr style="border-color:rgba(255,255,255,0.05);margin-bottom:15px;">'
                f'<ul style="list-style-type:none;padding-left:5px;">'
            )

            for _, row in df_relatorio.iterrows():
                _dr = row['data_registro']
                data_reg_fmt = (_dr if hasattr(_dr, 'strftime') else datetime.strptime(str(_dr), '%Y-%m-%d')).strftime('%d/%m')
                nome_parceiro = str(row['nome_instituicao']).upper()
                descricao     = str(row['descricao']).capitalize() if pd.notna(row['descricao']) and str(row['descricao']).strip() else "Sem observações."
                tipo = row['tipo']
                val  = float(row['valor_estimado']) if pd.notna(row['valor_estimado']) else 0
                if "DOA" in tipo and val > 0:
                    val_fmt    = f"R$ {val:,.2f}".replace(',','X').replace('.',',').replace('X','.')
                    texto_extra = f" | Valor: {val_fmt}"
                    html_extra  = f" <span style='color:#00FFC2;font-weight:bold;'>| {val_fmt}</span>"
                else:
                    texto_extra = ""
                    html_extra  = ""

                texto_diretoria += f"🔹 *{nome_parceiro}* ({data_reg_fmt})\n{tipo}{texto_extra}\nDetalhe: {descricao}\n\n"
                html_relatorio  += (
                    f"<li style='margin-bottom:18px;'>"
                    f"🏢 <b style='font-size:1.05em;'>{nome_parceiro}</b>"
                    f" <span class='date-badge' style='margin-left:10px;'>{data_reg_fmt}</span><br>"
                    f"<span style='font-size:0.85em;color:#FFB74D;font-weight:600;margin-left:25px;'>{tipo}{html_extra}</span><br>"
                    f"<span style='opacity:0.85;font-size:0.95em;margin-left:25px;'>↳ {descricao}</span></li>"
                )

            html_relatorio += "</ul></div>"
            st.markdown(html_relatorio, unsafe_allow_html=True)

            with st.expander("Copiar texto para WhatsApp / E-mail"):
                st.code(texto_diretoria, language="markdown")

            # ── PDF ─────────────────────────────────────────────────────
            def _gerar_pdf_diretoria(df_rel, d_ini_fmt, d_fim_fmt):
                from io import BytesIO
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib import colors
                from reportlab.lib.units import cm
                from reportlab.platypus import (
                    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
                )
                buf = BytesIO()
                doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
                estilos        = getSampleStyleSheet()
                cor_principal  = colors.HexColor("#C0392B")
                cor_cinza      = colors.HexColor("#555555")
                cor_fundo      = colors.HexColor("#F7F7F7")
                st_titulo      = ParagraphStyle("titulo",    parent=estilos["Title"],   fontSize=20, textColor=cor_principal, spaceAfter=4)
                st_subtitulo   = ParagraphStyle("sub",       parent=estilos["Normal"],  fontSize=11, textColor=cor_cinza, spaceAfter=12)
                st_secao       = ParagraphStyle("secao",     parent=estilos["Heading2"],fontSize=13, textColor=cor_principal, spaceBefore=14, spaceAfter=6)
                st_item        = ParagraphStyle("item",      parent=estilos["Normal"],  fontSize=10, textColor=colors.HexColor("#222222"), spaceAfter=2, leading=14)
                st_detalhe     = ParagraphStyle("detalhe",   parent=estilos["Normal"],  fontSize=9,  textColor=cor_cinza, leftIndent=12, spaceAfter=8, leading=13)
                story = []
                story.append(Paragraph("Casa Durval Paiva", st_titulo))
                story.append(Paragraph(f"Relatório Estratégico de Parcerias — {d_ini_fmt} a {d_fim_fmt}", st_subtitulo))
                story.append(HRFlowable(width="100%", thickness=1.5, color=cor_principal, spaceAfter=10))

                doacoes_period = df_rel[df_rel['tipo'].str.contains("DOA", na=False, case=False)]
                relac_period   = df_rel[df_rel['tipo'] == 'RELACIONAMENTO']
                total_fin      = doacoes_period['valor_estimado'].sum()
                n_parcerias    = df_rel['nome_instituicao'].nunique()

                dados_kpi = [
                    ["Parceiros movimentados", "Interações registradas", "Doações no período"],
                    [str(n_parcerias), str(len(relac_period)), f"R$ {total_fin:,.2f}".replace(',','X').replace('.',',').replace('X','.')]
                ]
                t_kpi = Table(dados_kpi, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
                t_kpi.setStyle(TableStyle([
                    ("BACKGROUND",    (0,0),(-1,0), cor_fundo),
                    ("TEXTCOLOR",     (0,0),(-1,0), cor_cinza),
                    ("FONTSIZE",      (0,0),(-1,0), 9),
                    ("FONTSIZE",      (0,1),(-1,1), 14),
                    ("FONTNAME",      (0,1),(-1,1), "Helvetica-Bold"),
                    ("TEXTCOLOR",     (0,1),(-1,1), cor_principal),
                    ("ALIGN",         (0,0),(-1,-1), "CENTER"),
                    ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
                    ("BOX",           (0,0),(-1,-1), 0.5, cor_cinza),
                    ("INNERGRID",     (0,0),(-1,-1), 0.3, colors.HexColor("#DDDDDD")),
                    ("TOPPADDING",    (0,0),(-1,-1), 8),
                    ("BOTTOMPADDING", (0,0),(-1,-1), 8),
                ]))
                story.append(t_kpi)
                story.append(Spacer(1, 0.4*cm))

                if not relac_period.empty:
                    story.append(Paragraph("Interações com parceiros", st_secao))
                    for _, row in relac_period.iterrows():
                        _dr  = row['data_registro']
                        drf  = (_dr if hasattr(_dr,'strftime') else datetime.strptime(str(_dr),'%Y-%m-%d')).strftime('%d/%m/%Y')
                        desc = str(row['descricao']).capitalize() if pd.notna(row['descricao']) else "—"
                        story.append(Paragraph(f"<b>{str(row['nome_instituicao']).upper()}</b> &nbsp;&nbsp; <font color='#888888' size='9'>{drf}</font>", st_item))
                        story.append(Paragraph(f"↳ {desc}", st_detalhe))

                if not doacoes_period.empty:
                    story.append(Paragraph("Doações recebidas no período", st_secao))
                    for _, row in doacoes_period.iterrows():
                        _dr  = row['data_registro']
                        drf  = (_dr if hasattr(_dr,'strftime') else datetime.strptime(str(_dr),'%Y-%m-%d')).strftime('%d/%m/%Y')
                        val  = float(row['valor_estimado']) if pd.notna(row['valor_estimado']) else 0
                        vf   = f"R$ {val:,.2f}".replace(',','X').replace('.',',').replace('X','.') if val > 0 else "—"
                        desc = str(row['descricao']).capitalize() if pd.notna(row['descricao']) else "—"
                        story.append(Paragraph(f"<b>{str(row['nome_instituicao']).upper()}</b> &nbsp;&nbsp; <font color='#888888' size='9'>{drf}</font> &nbsp; <b>{vf}</b>", st_item))
                        story.append(Paragraph(f"↳ {desc}", st_detalhe))

                doc.build(story)
                return buf.getvalue()

            try:
                pdf_bytes = _gerar_pdf_diretoria(df_relatorio, dt_ini_fmt, dt_fim_fmt)
                st.download_button(
                    "Baixar PDF para diretoria",
                    data=pdf_bytes,
                    file_name=f"RelatorioParcerias_{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"PDF não gerado: {e}")






# --- 1. DASHBOARD GERAL ---
if menu == "Painel Geral":
    page_header("Painel geral", "Visão consolidada do Desenvolvimento Institucional.")

    # ── Dados transversais ────────────────────────────────────────────────────
    df_doacoes      = run_query_cached("SELECT data_doacao, valor_estimado, tipo_doacao, origem_captacao FROM Doacao")
    df_parceiros_pg = run_query_cached("SELECT id_parceiro, nome_instituicao, status, data_adesao FROM Parceiro")
    df_acoes_pg     = run_query_cached("SELECT fonte, situacao FROM View_Acoes_Unificadas")
    df_rel_pg       = run_query_cached("SELECT * FROM View_Relacionamento_Critico")
    df_prog_plano   = run_query_cached("SELECT nome_fonte, meta_2026, captado_2026, pct_meta FROM View_Progresso_PlanoAnual")

    _tipos_fin = ['Financeira', 'Projetos']

    if df_doacoes.empty and df_prog_plano.empty:
        empty_state("—", "Nenhum dado cadastrado", "Comece registrando doações, parceiros e eventos.")
    else:
        df_doacoes['data_doacao'] = pd.to_datetime(df_doacoes['data_doacao'], errors='coerce')

        # ── ANO DE REFERÊNCIA ─────────────────────────────────────────────────
        anos = sorted(df_doacoes['data_doacao'].dt.year.dropna().unique().astype(int), reverse=True) if not df_doacoes.empty else [datetime.now().year]
        ano_sel = int(st.selectbox("Ano de referência", anos, key="pg_ano"))

        df_atual   = df_doacoes[df_doacoes['data_doacao'].dt.year == ano_sel]
        df_passado = df_doacoes[df_doacoes['data_doacao'].dt.year == (ano_sel - 1)]
        df_fin     = df_atual[df_atual['tipo_doacao'].isin(_tipos_fin)]
        df_fin_pa  = df_passado[df_passado['tipo_doacao'].isin(_tipos_fin)]

        total_fin    = float(df_fin['valor_estimado'].sum())
        total_fin_pa = float(df_fin_pa['valor_estimado'].sum())
        def _fmt(v): return format_br(v)

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 0 — VELOCÍMETRO DO PLANO DI 2026
        # ════════════════════════════════════════════════════════════════════════
        if not df_prog_plano.empty and ano_sel == 2026:
            section("Plano DI 2026 — progresso geral")
            meta_total    = float(df_prog_plano['meta_2026'].sum())
            captado_total = float(df_prog_plano['captado_2026'].sum())
            pct_total     = (captado_total / meta_total * 100) if meta_total > 0 else 0
            saldo         = meta_total - captado_total

            # Meta proporcional ao dia do ano (quanto deveria ter captado até hoje)
            dia_do_ano   = datetime.now().timetuple().tm_yday
            pct_esperado = min(dia_do_ano / 365 * 100, 100)
            meta_esperada = meta_total * pct_esperado / 100

            cv_gauge, cv_kpis = st.columns([1, 1.4])
            with cv_gauge:
                cor_gauge = "#059669" if pct_total >= pct_esperado else "#D97706" if pct_total >= pct_esperado * 0.7 else "#DC2626"
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=pct_total,
                    delta={"reference": pct_esperado, "valueformat": ".1f",
                           "suffix": "%", "increasing": {"color": "#059669"}, "decreasing": {"color": "#DC2626"}},
                    number={"suffix": "%", "valueformat": ".1f", "font": {"size": 36, "color": "#fff"}},
                    gauge={
                        "axis": {"range": [0, 100], "ticksuffix": "%", "tickcolor": "#555", "tickfont": {"color": "#888", "size": 11}},
                        "bar":  {"color": cor_gauge, "thickness": 0.25},
                        "bgcolor": "rgba(0,0,0,0)",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0, pct_esperado * 0.7],  "color": "rgba(220,38,38,0.12)"},
                            {"range": [pct_esperado * 0.7, pct_esperado], "color": "rgba(217,119,6,0.12)"},
                            {"range": [pct_esperado, 100], "color": "rgba(5,150,105,0.12)"},
                        ],
                        "threshold": {"line": {"color": "#94A3B8", "width": 2}, "thickness": 0.8, "value": pct_esperado},
                    },
                    title={"text": "Meta 2026", "font": {"size": 13, "color": "#94A3B8"}},
                ))
                fig_gauge.update_layout(
                    height=240, margin=dict(t=30, b=10, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)", font_color="#fff",
                )
                st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})
                st.caption(f"Traço cinza = meta proporcional ao dia ({pct_esperado:.0f}%)")

            with cv_kpis:
                kpi_row([
                    {"label": "Meta anual",   "value": _fmt(meta_total)},
                    {"label": "Captado 2026", "value": _fmt(captado_total), "accent": True},
                ])
                kpi_row([
                    {"label": "Saldo restante", "value": _fmt(saldo)},
                    {"label": "% da meta",      "value": f"{pct_total:.1f}%"},
                ])
                # Mini-barras por fonte (top 5)
                st.markdown("<div style='margin-top:8px;'>", unsafe_allow_html=True)
                df_top5 = df_prog_plano.sort_values('meta_2026', ascending=False).head(5)
                for _, r in df_top5.iterrows():
                    pf = min(float(r['pct_meta'] or 0), 100)
                    cor_b = "#059669" if pf >= 80 else "#D97706" if pf >= 40 else "#DC2626"
                    nome_curto = str(r['nome_fonte'])[:28]
                    st.markdown(
                        f"<div style='margin-bottom:6px;'>"
                        f"<div style='display:flex;justify-content:space-between;font-size:11px;color:#94A3B8;margin-bottom:2px;'>"
                        f"<span>{nome_curto}</span><span style='color:{cor_b};font-weight:600;'>{pf:.0f}%</span></div>"
                        f"<div style='height:5px;background:rgba(255,255,255,0.08);border-radius:3px;'>"
                        f"<div style='width:{pf}%;height:100%;background:{cor_b};border-radius:3px;'></div></div></div>",
                        unsafe_allow_html=True
                    )
                st.markdown("</div>", unsafe_allow_html=True)

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 1 — EVOLUÇÃO MENSAL (combo: barra captado + linha meta proporcional + linha 2025)
        # ════════════════════════════════════════════════════════════════════════
        section("Evolução mensal da captação")

        if not df_fin.empty:
            # Agrupa por mês
            df_fin_m   = df_fin.copy()
            df_fin_m['mes'] = df_fin_m['data_doacao'].dt.to_period('M')
            cap_mes    = df_fin_m.groupby('mes')['valor_estimado'].sum().reset_index()
            cap_mes['mes_str'] = cap_mes['mes'].dt.strftime('%b/%y')
            cap_mes    = cap_mes.sort_values('mes')

            # 2025 no mesmo período
            df_fin_pa_m = df_fin_pa.copy()
            df_fin_pa_m['mes'] = df_fin_pa_m['data_doacao'].dt.to_period('M')
            cap_pa_mes  = df_fin_pa_m.groupby('mes')['valor_estimado'].sum().reset_index()

            # Meta mensal proporcional (meta_total / 12)
            meta_mensal = (float(df_prog_plano['meta_2026'].sum()) / 12) if (not df_prog_plano.empty and ano_sel == 2026) else None

            fig_evo = go.Figure()

            # Barras — captado 2026
            fig_evo.add_trace(go.Bar(
                x=cap_mes['mes_str'], y=cap_mes['valor_estimado'],
                name=f"Captado {ano_sel}",
                marker_color="rgba(55,138,221,0.75)",
                hovertemplate="<b>%{x}</b><br>Captado: R$ %{y:,.2f}<extra></extra>",
            ))

            # Linha — 2025 comparativo
            if not cap_pa_mes.empty:
                cap_pa_mes['mes_str'] = cap_pa_mes['mes'].dt.strftime('%b/%y').str.replace(
                    str(ano_sel - 1)[-2:], str(ano_sel - 1)[-2:]
                )
                # Alinha meses: usa número do mês para mapear no eixo de 2026
                mapa_mes  = {m: i for i, m in enumerate(cap_mes['mes_str'].tolist())}
                cap_pa_mes['mes_2026'] = cap_pa_mes['mes'].dt.month.apply(
                    lambda m: cap_mes[cap_mes['mes'].dt.month == m]['mes_str'].values[0]
                    if len(cap_mes[cap_mes['mes'].dt.month == m]) > 0 else None
                )
                cap_pa_mes = cap_pa_mes.dropna(subset=['mes_2026'])
                if not cap_pa_mes.empty:
                    fig_evo.add_trace(go.Scatter(
                        x=cap_pa_mes['mes_2026'], y=cap_pa_mes['valor_estimado'],
                        name=f"{ano_sel - 1}",
                        mode="lines+markers",
                        line=dict(color="rgba(148,163,184,0.6)", width=1.5, dash="dot"),
                        marker=dict(size=5, color="rgba(148,163,184,0.6)"),
                        hovertemplate=f"<b>%{{x}}</b><br>{ano_sel-1}: R$ %{{y:,.2f}}<extra></extra>",
                    ))

            # Linha — meta mensal proporcional
            if meta_mensal and ano_sel == 2026:
                fig_evo.add_trace(go.Scatter(
                    x=cap_mes['mes_str'],
                    y=[meta_mensal] * len(cap_mes),
                    name="Meta/mês",
                    mode="lines",
                    line=dict(color="rgba(234,179,8,0.8)", width=1.5, dash="dash"),
                    hovertemplate="Meta mensal: R$ %{y:,.2f}<extra></extra>",
                ))

            _ly_evo = _chart_layout(300)
            _ly_evo["yaxis"]["tickformat"] = "~s"
            _ly_evo["yaxis"]["tickprefix"] = "R$ "
            _ly_evo["barmode"] = "group"
            _ly_evo["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                                     font=dict(size=11, color="#94A3B8"))
            fig_evo.update_layout(**_ly_evo)
            st.plotly_chart(fig_evo, use_container_width=True, config={"displayModeBar": False})

            # KPIs rápidos do ano
            diff_fin = total_fin - total_fin_pa
            kpi_row([
                {"label": f"Captado {ano_sel}",        "value": _fmt(total_fin), "accent": True},
                {"label": f"Captado {ano_sel - 1}",    "value": _fmt(total_fin_pa)},
                {"label": "Variação ano",               "value": f"{'+' if diff_fin >= 0 else ''}{_fmt(diff_fin)}"},
                {"label": "Ticket médio",               "value": _fmt(total_fin / len(df_fin)) if len(df_fin) > 0 else "—"},
            ])
        else:
            st.info(f"Sem captação financeira registrada para {ano_sel}.")

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 2 — TOP 3 ALERTAS PRIORIZADOS
        # ════════════════════════════════════════════════════════════════════════
        section("Ações prioritárias agora")

        _alertas_priorizados = []

        # 1. Follow-ups vencidos
        try:
            df_fu_venc = run_query_cached(
                "SELECT p.nome_instituicao, r.proxima_acao_data, "
                "(CURRENT_DATE - r.proxima_acao_data::date) AS dias_atraso "
                "FROM Registro_Relacionamento r JOIN Parceiro p ON r.id_parceiro=p.id_parceiro "
                "WHERE r.proxima_acao_data IS NOT NULL AND r.proxima_acao_data::date < CURRENT_DATE "
                "ORDER BY dias_atraso DESC LIMIT 3"
            )
            if not df_fu_venc.empty:
                nomes = ", ".join(df_fu_venc['nome_instituicao'].tolist()[:2])
                mais  = f" e mais {len(df_fu_venc)-2}" if len(df_fu_venc) > 2 else ""
                _alertas_priorizados.append({
                    "prioridade": 1,
                    "icone": "(!)",
                    "titulo": f"{len(df_fu_venc)} follow-up(s) vencido(s)",
                    "contexto": f"{nomes}{mais} estão aguardando contato.",
                    "acao": "Acesse Relacionamento → Follow-ups para ver a lista completa.",
                    "tom": "danger",
                })
        except Exception:
            pass

        # 2. Parceiros críticos sem contato há 90+ dias
        if not df_rel_pg.empty:
            df_rel_pg['Dias_Sem_Contato'] = pd.to_numeric(df_rel_pg['Dias_Sem_Contato'], errors='coerce')
            criticos = df_rel_pg[df_rel_pg['Status_Relacionamento'].str.contains("CRIT", na=False)]
            if not criticos.empty:
                nomes_c = ", ".join(criticos['Empresa'].tolist()[:2])
                mais_c  = f" e mais {len(criticos)-2}" if len(criticos) > 2 else ""
                _alertas_priorizados.append({
                    "prioridade": 2,
                    "icone": "(!)",
                    "titulo": f"{len(criticos)} parceiro(s) sem contato há mais de 90 dias",
                    "contexto": f"{nomes_c}{mais_c} estão em risco de abandono.",
                    "acao": "Registre uma interação ou agende uma ligação esta semana.",
                    "tom": "warning",
                })

        # 3. Fontes do Plano DI abaixo de 30% da meta
        if not df_prog_plano.empty and ano_sel == 2026:
            df_baixo = df_prog_plano[df_prog_plano['pct_meta'].fillna(0) < 30]
            if not df_baixo.empty:
                nomes_b = ", ".join(df_baixo['nome_fonte'].tolist()[:2])
                mais_b  = f" e mais {len(df_baixo)-2}" if len(df_baixo) > 2 else ""
                _alertas_priorizados.append({
                    "prioridade": 3,
                    "icone": "(!)",
                    "titulo": f"{len(df_baixo)} fonte(s) abaixo de 30% da meta",
                    "contexto": f"{nomes_b}{mais_b} precisam de atenção imediata.",
                    "acao": "Acesse Plano DI 2026 para ver o detalhamento por fonte.",
                    "tom": "warning",
                })

        # 4. Doações sem tipo definido
        try:
            df_sem_tipo = run_query_slow(
                "SELECT COUNT(*) as n FROM Doacao "
                "WHERE (tipo_doacao IS NULL OR tipo_doacao='' OR tipo_doacao='Selecione...') "
                "AND EXTRACT(YEAR FROM data_doacao)=%s", (int(ano_sel),)
            )
            n_sem_tipo = int(df_sem_tipo['n'].iloc[0]) if not df_sem_tipo.empty else 0
            if n_sem_tipo > 0:
                _alertas_priorizados.append({
                    "prioridade": 4,
                    "icone": "(!)",
                    "titulo": f"{n_sem_tipo} doação(ões) sem tipo definido",
                    "contexto": "Registros sem tipo distorcem o cálculo das metas financeiras.",
                    "acao": "Acesse Entrada de Recursos → Histórico e corrija os registros.",
                    "tom": "info",
                })
        except Exception:
            pass

        _alertas_priorizados = sorted(_alertas_priorizados, key=lambda x: x['prioridade'])[:3]

        if not _alertas_priorizados:
            st.markdown(
                '<div style="padding:14px 18px;background:rgba(5,150,105,0.1);border-left:3px solid #059669;'
                'border-radius:0 8px 8px 0;font-size:14px;">'
                '<strong>Nenhuma ação crítica pendente.</strong> Sistema em dia.</div>',
                unsafe_allow_html=True
            )
        else:
            for al in _alertas_priorizados:
                action_card(
                    titulo=f"{al['icone']} {al['titulo']}",
                    meta_parts=[al['contexto'], f"{al['acao']}"],
                    tom=al['tom'],
                )

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 3 — PARCEIROS + RELACIONAMENTO (compacto)
        # ════════════════════════════════════════════════════════════════════════
        section("Parceiros")
        if not df_parceiros_pg.empty:
            s_lp = df_parceiros_pg['status'].fillna("").str.upper()
            ativos_p   = int(s_lp.str.contains("ATIVO",   na=False).sum())
            prospec_p  = int(s_lp.str.contains("PROSPEC", na=False).sum())
            inativos_p = int(s_lp.str.contains("INATIVO", na=False).sum())
            df_parceiros_pg['_ad'] = pd.to_datetime(df_parceiros_pg['data_adesao'], errors='coerce')
            novos_p = int((df_parceiros_pg['_ad'].dt.year == ano_sel).sum())
            kpi_row([
                {"label": "Total",             "value": len(df_parceiros_pg)},
                {"label": "Ativos",            "value": ativos_p, "accent": True},
                {"label": "Prospecção",        "value": prospec_p},
                {"label": "Inativos",          "value": inativos_p},
                {"label": f"Novos {ano_sel}",  "value": novos_p},
            ])

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 4 — MAIORES DOADORES
        # ════════════════════════════════════════════════════════════════════════
        section("Maiores doadores do ano")
        df_top = run_query_slow(
            "SELECT p.nome_instituicao AS \"Parceiro\", SUM(d.valor_estimado) AS \"Total\", COUNT(*) AS \"Repasses\" "
            "FROM Doacao d JOIN Parceiro p ON d.id_parceiro=p.id_parceiro "
            "WHERE EXTRACT(YEAR FROM d.data_doacao)=%s AND d.tipo_doacao IN ('Financeira','Projetos') "
            "GROUP BY p.nome_instituicao ORDER BY \"Total\" DESC LIMIT 5",
            (int(ano_sel),)
        )
        if not df_top.empty:
            df_top['Total'] = df_top['Total'].apply(_fmt)
            st.dataframe(df_top, use_container_width=True, hide_index=True,
                column_config={"Total": "Valor total", "Repasses": st.column_config.NumberColumn("Repasses", format="%d")})
        else:
            st.caption("Sem doações financeiras registradas para este ano.")

        # ════════════════════════════════════════════════════════════════════════
        # BLOCO 5 — QUALIDADE DOS DADOS (compacto)
        # ════════════════════════════════════════════════════════════════════════
        section("Qualidade dos dados")
        df_qd_sem_contato   = run_query_slow("SELECT COUNT(*) as n FROM Parceiro p WHERE UPPER(p.status) LIKE '%ATIVO%' AND NOT EXISTS (SELECT 1 FROM Contato_Direto c WHERE c.id_parceiro=p.id_parceiro)")
        df_qd_sem_interacao = run_query_slow("SELECT COUNT(*) as n FROM Parceiro p WHERE UPPER(p.status) LIKE '%ATIVO%' AND NOT EXISTS (SELECT 1 FROM Registro_Relacionamento r WHERE r.id_parceiro=p.id_parceiro)")
        df_qd_sem_doacao    = run_query_slow(f"SELECT COUNT(*) as n FROM Parceiro p WHERE UPPER(p.status) LIKE '%ATIVO%' AND NOT EXISTS (SELECT 1 FROM Doacao d WHERE d.id_parceiro=p.id_parceiro AND EXTRACT(YEAR FROM d.data_doacao)={ano_sel})")
        df_qd_sem_tipo_c    = run_query_slow(f"SELECT COUNT(*) as n FROM Doacao WHERE (tipo_doacao IS NULL OR tipo_doacao='' OR tipo_doacao='Selecione...') AND EXTRACT(YEAR FROM data_doacao)={ano_sel}")

        n_sc = int(df_qd_sem_contato['n'].iloc[0])   if not df_qd_sem_contato.empty   else 0
        n_si = int(df_qd_sem_interacao['n'].iloc[0]) if not df_qd_sem_interacao.empty else 0
        n_sd = int(df_qd_sem_doacao['n'].iloc[0])    if not df_qd_sem_doacao.empty    else 0
        n_st = int(df_qd_sem_tipo_c['n'].iloc[0])    if not df_qd_sem_tipo_c.empty    else 0

        pendencias = [n_sc > 0, n_si > 0, n_sd > 0, n_st > 0]
        n_pend = sum(pendencias)
        score_q = round((4 - n_pend) / 4 * 100)
        cor_score = "#059669" if score_q == 100 else "#D97706" if score_q >= 50 else "#DC2626"

        st.markdown(
            f'<div style="padding:10px 14px;background:rgba(255,255,255,0.03);border-radius:8px;'
            f'border:1px solid rgba(255,255,255,0.07);margin-bottom:10px;">'
            f'<div style="display:flex;align-items:center;gap:12px;">'
            f'<div style="flex:1;height:6px;background:rgba(255,255,255,0.1);border-radius:3px;">'
            f'<div style="width:{score_q}%;height:100%;background:{cor_score};border-radius:3px;"></div></div>'
            f'<span style="font-size:15px;font-weight:700;color:{cor_score};">{score_q}%</span>'
            f'<span style="font-size:12px;color:#666;">completude</span></div></div>',
            unsafe_allow_html=True
        )
        itens_qd = [
            (n_sd, f"Parceiros ativos sem doação em {ano_sel}"),
            (n_st, "Doações sem tipo definido"),
            (n_sc, "Parceiros sem contato cadastrado"),
            (n_si, "Parceiros sem interação registrada"),
        ]
        for n_v, label_v in itens_qd:
            if n_v > 0:
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:5px 10px;'
                    f'border-left:2px solid #D97706;margin-bottom:4px;border-radius:0 4px 4px 0;'
                    f'background:rgba(217,119,6,0.06);font-size:13px;">'
                    f'<span>{label_v}</span><span style="color:#D97706;font-weight:600;">{n_v}</span></div>',
                    unsafe_allow_html=True
                )
        if n_pend == 0:
            st.markdown('<div style="font-size:13px;color:#059669;">Banco de dados completo.</div>', unsafe_allow_html=True)



elif menu == "Calendário":
    page_header("Calendário DI", "Prazos, follow-ups e eventos num só lugar.")

    # ── Garante tabela de eventos personalizados e carrega dados ────────────
    run_exec("""
        CREATE TABLE IF NOT EXISTS Eventos_Calendario (
            id          SERIAL PRIMARY KEY,
            titulo      TEXT NOT NULL,
            data_inicio DATE NOT NULL,
            data_fim    DATE,
            cor         TEXT DEFAULT '#8B5CF6',
            criado_por  TEXT,
            criado_em   TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Botão para abrir formulário de novo evento
    _col_btn_ev, _col_sp = st.columns([2, 6])
    with _col_btn_ev:
        if st.button("Adicionar evento", key="btn_add_evento", use_container_width=True, type="primary"):
            st.session_state["_cal_add_open"] = not st.session_state.get("_cal_add_open", False)

    if st.session_state.get("_cal_add_open", False):
        with st.form("form_novo_evento_cal", clear_on_submit=True):
            _ev_c1, _ev_c2 = st.columns(2)
            _ev_titulo   = _ev_c1.text_input("Título do evento *")
            _ev_cor_sel  = _ev_c2.selectbox("Cor", [
                ("Roxo",    "#8B5CF6"),
                ("Azul",    "#378ADD"),
                ("Verde",   "#1D9E75"),
                ("Amarelo", "#D97706"),
                ("Vermelho","#DC2626"),
                ("Rosa",    "#E91E8C"),
            ], format_func=lambda x: x[0])
            _ev_data_ini = _ev_c1.date_input("Data início *")
            _ev_data_fim = _ev_c2.date_input("Data fim (opcional)", value=None)
            _ev_submit   = st.form_submit_button("Salvar evento", use_container_width=True, type="primary")
            if _ev_submit:
                if not _ev_titulo:
                    st.error("Informe o título do evento.")
                else:
                    _cor_hex = _ev_cor_sel[1]
                    _nome_user = (st.session_state.user_data or {}).get("nome","")
                    run_exec(
                        """INSERT INTO Eventos_Calendario (titulo, data_inicio, data_fim, cor, criado_por)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (_ev_titulo, _ev_data_ini,
                         _ev_data_fim if _ev_data_fim else None,
                         _cor_hex, _nome_user)
                    )
                    st.success("Evento adicionado.")
                    st.session_state["_cal_add_open"] = False
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Busca dados das três fontes ──────────────────────────────────────────
    df_acoes_cal = run_query_cached("""
        SELECT tarefa, data_prevista, status, responsavel
        FROM Demandas_Estrategicas
        WHERE data_prevista IS NOT NULL
          AND status NOT IN ('REALIZADO')
    """)

    df_followup_cal = run_query_slow("""
        SELECT rr.proxima_acao_data, p.nome_instituicao,
               rr.descricao_do_que_foi_feito
        FROM Registro_Relacionamento rr
        JOIN Parceiro p ON rr.id_parceiro = p.id_parceiro
        WHERE rr.proxima_acao_data IS NOT NULL
          AND rr.proxima_acao_data >= CURRENT_DATE - INTERVAL '30 days'
    """)

    df_almoco_cal = run_query_slow("""
        SELECT DISTINCT mes_referencia
        FROM Convidados_Almoco
        ORDER BY mes_referencia
    """)

    # ── Carrega eventos personalizados do banco ──────────────────────────────
    df_eventos_db = run_query_cached("SELECT titulo, data_inicio, data_fim, cor FROM Eventos_Calendario ORDER BY data_inicio")

    # ── Monta lista de eventos ──────────────────────────────────────────────
    eventos_cal = []

    # 🟣 Eventos personalizados (adicionados pelos usuários)
    for _, row in df_eventos_db.iterrows():
        try:
            dt_s = str(row["data_inicio"])[:10]
            dt_e = str(row["data_fim"])[:10] if row.get("data_fim") and str(row["data_fim"]) != "None" else None
            ev = {
                "title": str(row["titulo"]),
                "start": dt_s,
                "color": str(row.get("cor","#8B5CF6")),
                "textColor": "#fff",
                "extendedProps": {"tipo": "evento"},
            }
            if dt_e and dt_e != dt_s:
                ev["end"] = dt_e
            eventos_cal.append(ev)
        except Exception:
            pass

    # 🔴 / 🟡 Ações com prazo
    for _, row in df_acoes_cal.iterrows():
        try:
            dt = str(row["data_prevista"])[:10]
            from datetime import date
            vencido = dt < date.today().isoformat()
            cor = "#DC2626" if vencido else "#D97706"
            titulo = str(row["tarefa"] or "Tarefa")[:45]
            resp = f" ({row['responsavel']})" if row.get("responsavel") else ""
            eventos_cal.append({
                "title": f"{titulo}{resp}",
                "start": dt,
                "color": cor,
                "textColor": "#fff",
                "extendedProps": {"tipo": "ação", "status": row.get("status","")},
            })
        except Exception:
            pass

    # 🔵 Follow-ups de relacionamento
    for _, row in df_followup_cal.iterrows():
        try:
            dt = str(row["proxima_acao_data"])[:10]
            empresa = str(row.get("nome_instituicao","Parceiro"))[:30]
            eventos_cal.append({
                "title": f"{empresa}",
                "start": dt,
                "color": "#378ADD",
                "textColor": "#fff",
                "extendedProps": {"tipo": "follow-up"},
            })
        except Exception:
            pass

    # 🟢 Almoço CDP (primeiro sábado do mês — marcado como dia inteiro)
    for _, row in df_almoco_cal.iterrows():
        try:
            from datetime import date, timedelta
            mes_ano = row["mes_referencia"]          # "04/2026"
            mm, yy = mes_ano.split("/")
            primeiro = date(int(yy), int(mm), 1)
            # primeiro sábado
            delta = (5 - primeiro.weekday()) % 7
            sabado = primeiro + timedelta(days=delta)
            eventos_cal.append({
                "title": "️ Almoço CDP",
                "start": sabado.isoformat(),
                "color": "#1D9E75",
                "textColor": "#fff",
                "allDay": True,
                "extendedProps": {"tipo": "evento"},
            })
        except Exception:
            pass

    # ── Legenda compacta ─────────────────────────────────────────────────────
    col_leg = st.columns(4)
    legendas = [
        ("#DC2626", "Ação vencida"),
        ("#D97706", "Ação pendente"),
        ("#378ADD", "Follow-up"),
        ("#1D9E75", "Almoço CDP"),
    ]
    for col, (cor, txt) in zip(col_leg, legendas):
        col.markdown(
            f'<div style="display:flex;align-items:center;gap:6px;font-size:12px;">'
            f'<div style="width:12px;height:12px;border-radius:3px;background:{cor};flex-shrink:0;"></div>'
            f'<span style="color:#94A3B8;">{txt}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Filtros rápidos ──────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns([3, 1])
    with col_f2:
        tipos_sel = st.multiselect(
            "Filtrar por tipo",
            ["ação", "follow-up", "evento"],
            default=["ação", "follow-up", "evento"],
            label_visibility="collapsed",
        )

    # ── Eventos institucionais fixos 2026 (Calendário Temático CDP) ──────────
    # Cores conforme legenda oficial:
    # #E91E8C = AÇÕES  |  #2196F3 = INSTITUCIONAL  |  #4CAF50 = CAPTAÇÃO
    # #FF9800 = CAMPANHA DIAGNÓSTICO PRECOCE        |  #DC2626 = PROJETOS ATIVOS
    _EVENTOS_CDP_2026 = [
        # ── JANEIRO ──
        {"title":"Campanha: Sinais da Leucemia","start":"2026-01-01","end":"2026-01-31","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Dia do Hemofílico","start":"2026-01-04","color":"#2196F3","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-01-28","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-01-30","color":"#E91E8C","textColor":"#fff"},
        # ── FEVEREIRO ──
        {"title":"Campanha: Tumor SNC","start":"2026-02-01","end":"2026-02-28","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Dia Mundial Combate ao Câncer","start":"2026-02-04","color":"#2196F3","textColor":"#fff"},
        {"title":"CarnaCACC","start":"2026-02-11","color":"#E91E8C","textColor":"#fff"},
        {"title":"Dia Int. Câncer Infantil","start":"2026-02-15","color":"#2196F3","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-02-25","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-02-27","color":"#E91E8C","textColor":"#fff"},
        # ── MARÇO ──
        {"title":"Campanha: Osteossarcoma","start":"2026-03-01","end":"2026-03-31","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Dia Internacional da Mulher","start":"2026-03-08","color":"#2196F3","textColor":"#fff"},
        {"title":"Dia Síndrome de Down","start":"2026-03-21","color":"#2196F3","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-03-25","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-03-31","color":"#E91E8C","textColor":"#fff"},
        {"title":"Campanha IRPF - PF","start":"2026-03-01","end":"2026-05-31","color":"#4CAF50","textColor":"#fff","display":"background"},
        # ── ABRIL ──
        {"title":"Campanha: Linfoma","start":"2026-04-01","end":"2026-04-30","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Páscoa CDP","start":"2026-04-01","color":"#E91E8C","textColor":"#fff"},
        {"title":"Dia Mundial Conscientização Autismo","start":"2026-04-02","color":"#2196F3","textColor":"#fff"},
        {"title":"Dia do Jornalista","start":"2026-04-07","color":"#2196F3","textColor":"#fff"},
        {"title":"Dia Mundial Luta Contra o Câncer","start":"2026-04-08","color":"#2196F3","textColor":"#fff"},
        {"title":"Dia da Hemofilia","start":"2026-04-17","color":"#2196F3","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-04-29","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-04-30","color":"#E91E8C","textColor":"#fff"},
        # ── MAIO ──
        {"title":"Campanha: Neuroblastoma","start":"2026-05-01","end":"2026-05-31","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Dia das Mães CDP","start":"2026-05-06","color":"#E91E8C","textColor":"#fff"},
        {"title":"Dia das Mães","start":"2026-05-12","color":"#2196F3","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-05-27","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-05-29","color":"#E91E8C","textColor":"#fff"},
        # ── JUNHO ──
        {"title":"Campanha: Câncer de Tecidos Moles","start":"2026-06-01","end":"2026-06-30","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"São João CDP","start":"2026-06-17","color":"#E91E8C","textColor":"#fff"},
        {"title":"Dia Conscientização Doença Falciforme","start":"2026-06-19","color":"#2196F3","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-06-24","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-06-30","color":"#E91E8C","textColor":"#fff"},
        {"title":"Multirão McDia Feliz","start":"2026-06-01","color":"#4CAF50","textColor":"#fff"},
        # ── JULHO ──
        {"title":"Campanha: Retinoblastoma","start":"2026-07-01","end":"2026-07-31","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Aniversário CDP 31 anos","start":"2026-07-11","color":"#E91E8C","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-07-29","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-07-31","color":"#E91E8C","textColor":"#fff"},
        {"title":"Multirão McDia Feliz","start":"2026-07-31","color":"#4CAF50","textColor":"#fff"},
        # ── AGOSTO ──
        {"title":"Campanha: Tumor de Wilms","start":"2026-08-01","end":"2026-08-31","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Dia dos Pais CDP","start":"2026-08-05","color":"#E91E8C","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-08-26","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-08-31","color":"#E91E8C","textColor":"#fff"},
        {"title":"McDia Feliz","start":"2026-08-21","color":"#4CAF50","textColor":"#fff"},
        # ── SETEMBRO ──
        {"title":"️ Campanha Setembro Dourado","start":"2026-09-01","end":"2026-09-30","color":"#FF9800","textColor":"#fff","display":"background"},
        {"title":"Dia Mundial Conscientização Linfomas","start":"2026-09-15","color":"#FF9800","textColor":"#fff"},
        {"title":"Dia Diagnóstico Precoce Retinoblastoma","start":"2026-09-18","color":"#FF9800","textColor":"#fff"},
        {"title":"Dia Mundial Doador Medula Óssea","start":"2026-09-19","color":"#2196F3","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-09-30","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-09-30","color":"#E91E8C","textColor":"#fff"},
        {"title":"Campanha de Natal - Central de Doações","start":"2026-09-01","end":"2026-12-31","color":"#4CAF50","textColor":"#fff","display":"background"},
        # ── OUTUBRO ──
        {"title":"Campanha: Leucemia","start":"2026-10-01","end":"2026-10-31","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Semana da Criança CDP","start":"2026-10-06","end":"2026-10-09","color":"#E91E8C","textColor":"#fff"},
        {"title":"Campanha IRPF - PJ","start":"2026-10-01","end":"2026-11-30","color":"#4CAF50","textColor":"#fff","display":"background"},
        {"title":"Almoço dos Parceiros","start":"2026-10-28","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-10-30","color":"#E91E8C","textColor":"#fff"},
        # ── NOVEMBRO ──
        {"title":"Feira Empreendedor e Bazar Natalino","start":"2026-11-17","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia Nacional Combate Câncer Inf.","start":"2026-11-23","color":"#2196F3","textColor":"#fff"},
        {"title":"Almoço dos Parceiros","start":"2026-11-25","color":"#4CAF50","textColor":"#fff"},
        {"title":"Dia Nacional Combate ao Câncer","start":"2026-11-27","color":"#2196F3","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-11-30","color":"#E91E8C","textColor":"#fff"},
        # ── DEZEMBRO ──
        {"title":"Campanha: Tumor SNC","start":"2026-12-01","end":"2026-12-31","color":"#E91E8C","textColor":"#fff","display":"background"},
        {"title":"Dia de Doar","start":"2026-12-02","color":"#4CAF50","textColor":"#fff"},
        {"title":"Natal CDP","start":"2026-12-09","color":"#E91E8C","textColor":"#fff"},
        {"title":"Confraternização Colaboradores","start":"2026-12-12","color":"#2196F3","textColor":"#fff"},
        {"title":"Dia do Desapego","start":"2026-12-31","color":"#E91E8C","textColor":"#fff"},
    ]
    eventos_filtrados = [
        e for e in eventos_cal + _EVENTOS_CDP_2026
        if e.get("extendedProps", {}).get("tipo", "evento") in tipos_sel
        or "extendedProps" not in e  # eventos fixos passam sempre
    ]


    # ── Renderiza calendário em grade mensal ─────────────────────────────────
    import calendar as _cal_mod
    _cal_mod.setfirstweekday(0)  # segunda-feira primeiro

    # Navegação de mês
    _hoje = datetime.today()
    if "cal_ano" not in st.session_state:
        st.session_state.cal_ano = _hoje.year
    if "cal_mes" not in st.session_state:
        st.session_state.cal_mes = _hoje.month

    _MESES_PT = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                 "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

    # ── Barra de navegação centrada ───────────────────────────────────────────
    _nav_col_l, _nav_col_c, _nav_col_r = st.columns([1, 3, 1])
    with _nav_col_c:
        _nc1, _nc2, _nc3, _nc4, _nc5 = st.columns([1, 1, 4, 1, 1])
        with _nc1:
            if st.button("◀", key="cal_prev", use_container_width=True):
                if st.session_state.cal_mes == 1:
                    st.session_state.cal_mes = 12; st.session_state.cal_ano -= 1
                else:
                    st.session_state.cal_mes -= 1
        with _nc3:
            st.markdown(
                f'<div style="text-align:center;font-size:20px;font-weight:800;'
                f'letter-spacing:-0.5px;padding:4px 0;">' +
                f'{_MESES_PT[st.session_state.cal_mes]} {st.session_state.cal_ano}</div>',
                unsafe_allow_html=True
            )
        with _nc5:
            if st.button("▶", key="cal_next", use_container_width=True):
                if st.session_state.cal_mes == 12:
                    st.session_state.cal_mes = 1; st.session_state.cal_ano += 1
                else:
                    st.session_state.cal_mes += 1
    with _nav_col_r:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("Hoje", key="cal_hoje", use_container_width=True):
            st.session_state.cal_ano = _hoje.year; st.session_state.cal_mes = _hoje.month

    _ano_v, _mes_v = st.session_state.cal_ano, st.session_state.cal_mes

    # Indexa eventos filtrados por data (só os com "start" de dia único / primeiro dia)
    from collections import defaultdict
    _evs_por_dia = defaultdict(list)
    for _ev in eventos_filtrados:
        _start = _ev.get("start","")[:10]
        if not _start: continue
        try:
            from datetime import date as _date
            _d = _date.fromisoformat(_start)
            if _d.year == _ano_v and _d.month == _mes_v:
                if not _ev.get("display") == "background":
                    _evs_por_dia[_d.day].append(_ev)
        except Exception:
            pass

    # Eventos de fundo (campanhas mensais) para o mês
    _bg_evs = []
    for _ev in eventos_filtrados:
        if _ev.get("display") == "background":
            _s = _ev.get("start","")[:10]
            _e = _ev.get("end","")[:10] if _ev.get("end") else _s
            try:
                from datetime import date as _date
                _ds = _date.fromisoformat(_s)
                _de = _date.fromisoformat(_e)
                _ref = _date(_ano_v, _mes_v, 1)
                import calendar as _cm2
                _last = _date(_ano_v, _mes_v, _cm2.monthrange(_ano_v, _mes_v)[1])
                if _ds <= _last and _de >= _ref:
                    _bg_evs.append(_ev)
            except Exception:
                pass

    # Grade do calendário
    _DIAS_SEMANA = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
    _cols_header = st.columns(7)
    for _i, _dn in enumerate(_DIAS_SEMANA):
        _cols_header[_i].markdown(
            f'<div style="text-align:center;font-size:11px;font-weight:700;'
            f'letter-spacing:1px;color:rgba(255,255,255,0.4);padding:4px 0;">{_dn}</div>',
            unsafe_allow_html=True
        )

    _semanas = _cal_mod.monthcalendar(_ano_v, _mes_v)
    for _semana in _semanas:
        _cols_dias = st.columns(7)
        for _col_i, _dia in enumerate(_semana):
            with _cols_dias[_col_i]:
                if _dia == 0:
                    st.markdown('<div style="min-height:80px;"></div>', unsafe_allow_html=True)
                    continue
                _eh_hoje = (_dia == _hoje.day and _mes_v == _hoje.month and _ano_v == _hoje.year)
                _num_style = (
                    'background:#E31D24;color:#fff;border-radius:50%;'
                    'width:22px;height:22px;display:inline-flex;align-items:center;'
                    'justify-content:center;font-weight:700;font-size:12px;'
                ) if _eh_hoje else (
                    'color:rgba(255,255,255,0.7);font-size:12px;font-weight:600;'
                )
                _evs_dia = _evs_por_dia.get(_dia, [])
                _evs_html = ""
                for _e in _evs_dia[:3]:
                    _cor = _e.get("color","#888")
                    _tit = _e.get("title","")
                    _tit_short = _tit[:22] + "…" if len(_tit) > 22 else _tit
                    _evs_html += (
                        f'<div style="background:{_cor};color:#fff;border-radius:3px;'
                        f'font-size:9px;padding:1px 4px;margin-top:2px;'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" '
                        f'title="{_tit}">{_tit_short}</div>'
                    )
                if len(_evs_dia) > 3:
                    _evs_html += f'<div style="font-size:9px;color:rgba(255,255,255,0.4);margin-top:1px;">+{len(_evs_dia)-3} mais</div>'
                st.markdown(
                    f'<div style="border:1px solid rgba(255,255,255,0.07);border-radius:6px;'
                    f'padding:4px 5px;min-height:80px;background:rgba(255,255,255,0.02);">'
                    f'<div style="{_num_style}">{_dia}</div>'
                    f'{_evs_html}</div>',
                    unsafe_allow_html=True
                )

    # Campanhas do mês (fundo)
    if _bg_evs:
        st.markdown("---")
        st.markdown('<p style="font-size:10px;letter-spacing:1.5px;color:rgba(255,255,255,0.3);font-weight:600;">CAMPANHAS DO MÊS</p>', unsafe_allow_html=True)
        for _ev in _bg_evs:
            _cor = _ev.get("color","#888")
            _tit = _ev.get("title","")
            st.markdown(
                f'<div style="display:inline-flex;align-items:center;gap:6px;'
                f'background:{_cor}22;border:1px solid {_cor}55;border-radius:6px;'
                f'padding:4px 10px;margin:2px 4px 2px 0;font-size:12px;">'
                f'<div style="width:8px;height:8px;border-radius:50%;background:{_cor};"></div>'
                f'{_tit}</div>',
                unsafe_allow_html=True
            )

    # Lista de eventos do mês
    st.markdown("---")
    st.markdown('<p style="font-size:10px;letter-spacing:1.5px;color:rgba(255,255,255,0.3);font-weight:600;">TODOS OS EVENTOS DO MÊS</p>', unsafe_allow_html=True)
    _todos_mes = sorted(
        [(_date.fromisoformat(e["start"][:10]), e) for e in eventos_filtrados
         if not e.get("display") == "background"
         and len(e.get("start","")) >= 10
         and _date.fromisoformat(e["start"][:10]).year == _ano_v
         and _date.fromisoformat(e["start"][:10]).month == _mes_v],
        key=lambda x: x[0]
    )
    if _todos_mes:
        for _dt, _ev in _todos_mes:
            _cor = _ev.get("color","#888")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;'
                f'padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<div style="min-width:32px;font-size:11px;font-weight:700;color:{_cor};">{_dt.day:02d}</div>'
                f'<div style="width:6px;height:6px;border-radius:50%;background:{_cor};flex-shrink:0;"></div>'
                f'<div style="font-size:12px;color:rgba(255,255,255,0.8);">{_ev.get("title","")}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.markdown('<p style="color:rgba(255,255,255,0.3);font-size:12px;">Nenhum evento pontual este mês.</p>', unsafe_allow_html=True)


elif menu == "Plano DI 2026":
    page_header("Plano de Ação DI 2026", "Monitoramento de metas financeiras e indicadores de comunicação.")

    eh_gerente_plano = st.session_state.user_data["perfil"] == "gerencia"

    tab_cap, tab_imp, tab_dig = st.tabs(["Captação financeira", "Imprensa", "Mídias Digitais"])

    # ══════════════════════════════════════════════════════════════════════════
    # ABA 1 — CAPTAÇÃO FINANCEIRA
    # ══════════════════════════════════════════════════════════════════════════
    with tab_cap:
        df_prog = run_query_slow("SELECT * FROM View_Progresso_PlanoAnual ORDER BY meta_2026 DESC")
        df_hist = run_query("""
            SELECT
                CASE
                    WHEN LENGTH(rc.mes_referencia) = 10
                    THEN TO_CHAR(rc.mes_referencia::date, 'DD/MM/YYYY')
                    ELSE rc.mes_referencia
                END AS mes_referencia,
                mf.nome_fonte, rc.valor_realizado,
                rc.observacao, rc.registrado_por, rc.data_registro
            FROM Registro_Captacao_DI rc
            JOIN Meta_Fonte_2026 mf ON rc.id_fonte = mf.id_fonte
            ORDER BY rc.mes_referencia DESC, mf.nome_fonte
        """)

        if not df_prog.empty:
            meta_total    = df_prog['meta_2026'].sum()
            captado_total = df_prog['captado_2026'].sum()
            saldo_total   = meta_total - captado_total
            pct_geral     = round(captado_total / meta_total * 100, 1) if meta_total > 0 else 0
            fontes_ok     = int((df_prog['status_meta'].str.contains("ATINGIDO", na=False)).sum())
            fontes_risco  = int((df_prog['status_meta'].str.contains("SEM REGISTRO", na=False)).sum())

            kpi_row([
                {"label": "Meta total anual DI",    "value": format_br(meta_total)},
                {"label": "Captado em 2026",         "value": format_br(captado_total), "accent": captado_total > 0},
                {"label": "% da meta",               "value": f"{pct_geral}%"},
                {"label": "Saldo a captar",          "value": format_br(saldo_total)},
                {"label": "Fontes sem registro",     "value": fontes_risco, "hint": "Precisam de lançamento"},
            ])

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:13px;color:#555;margin-bottom:4px;">Progresso geral: <b>{pct_geral}%</b> da meta anual</div>',
                unsafe_allow_html=True
            )
            st.progress(min(pct_geral / 100, 1.0))

            section("Progresso por fonte de captação")

            mes_atual = datetime.now().month
            for _, row in df_prog.iterrows():
                nome        = row['nome_fonte']
                meta        = float(row['meta_2026'])
                captado     = float(row['captado_2026'])
                pct         = float(row['pct_meta']) if row['pct_meta'] else 0.0
                saldo       = float(row['saldo_pendente'])
                status      = str(row['status_meta'])
                prorate     = round(meta / 12 * mes_atual, 2)
                pct_prorate = round(captado / prorate * 100, 1) if prorate > 0 else 0

                if "ATINGIDO" in status:       cor_bar = "#059669"
                elif "EM PROGRESSO" in status: cor_bar = "#D97706"
                elif "ABAIXO" in status:       cor_bar = "#EA580C"
                else:                cor_bar = "#94A3B8"

                if captado == 0:
                    badge_txt, badge_cor = "Sem registro", "#94A3B8"
                elif pct_prorate >= 100:
                    badge_txt, badge_cor = "No prazo", "#059669"
                elif pct_prorate >= 70:
                    badge_txt, badge_cor = "Em risco", "#D97706"
                else:
                    badge_txt, badge_cor = "Atrasado", "#DC2626"

                barra_val   = min(pct / 100, 1.0)
                prorata_pct = min(prorate / meta, 1.0) if meta > 0 else 0

                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2px;">'
                    f'  <span style="font-size:14px;font-weight:600;">{nome}</span>'
                    f'  <span style="font-size:12px;font-weight:700;color:{badge_cor};">{badge_txt}</span>'
                    f'</div>'
                    f'<div style="position:relative;background:#2D3748;border-radius:8px;height:14px;margin-bottom:4px;">'
                    f'  <div style="background:{cor_bar};width:{barra_val*100:.1f}%;height:14px;border-radius:8px;transition:width .4s;"></div>'
                    f'  <div style="position:absolute;top:0;left:{prorata_pct*100:.1f}%;width:2px;height:14px;background:#F59E0B;opacity:.8;" title="Pró-rata"></div>'
                    f'  <span style="position:absolute;right:6px;top:0;font-size:10px;line-height:14px;color:#fff;font-weight:700;">{pct:.0f}%</span>'
                    f'</div>'
                    f'<div style="display:flex;gap:16px;font-size:12px;color:#888;margin-bottom:8px;">'
                    f'  <span>Meta: <b style="color:#ccc;">{format_br(meta)}</b></span>'
                    f'  <span>Captado: <b style="color:{cor_bar};">{format_br(captado)}</b></span>'
                    f'  <span>Pró-rata ({mes_atual}m): <b style="color:#F59E0B;">{format_br(prorate)}</b></span>'
                    f'  <span>Saldo: <b style="color:#ccc;">{format_br(saldo)}</b></span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                st.markdown("<hr style='margin:4px 0;border-color:rgba(255,255,255,0.06);'>", unsafe_allow_html=True)
        else:
            st.info("Nenhuma fonte de captação cadastrada.")

        st.info("Para registrar novos valores realizados, acesse **Entrada de Recursos** no menu lateral.")

        if not df_hist.empty:
            section("Histórico de lançamentos")
            df_resumo = df_hist.groupby('nome_fonte')['valor_realizado'].sum().reset_index()
            df_resumo.columns = ['Fonte', 'Total Registrado']
            df_resumo['Total Registrado'] = df_resumo['Total Registrado'].apply(format_br)
            st.dataframe(df_resumo, use_container_width=True, hide_index=True)

            with st.expander("Ver todos os lançamentos"):
                df_hist_exib = df_hist.copy()
                df_hist_exib['valor_realizado'] = df_hist_exib['valor_realizado'].apply(format_br)
                df_hist_exib.columns = ['Mês', 'Fonte', 'Valor', 'Observação', 'Registrado por', 'Data registro']
                st.dataframe(df_hist_exib, use_container_width=True, hide_index=True)

            if eh_gerente_plano:
                df_hist_del = run_query("""
                    SELECT rc.id, mf.nome_fonte, rc.mes_referencia, rc.valor_realizado
                    FROM Registro_Captacao_DI rc
                    JOIN Meta_Fonte_2026 mf ON rc.id_fonte = mf.id_fonte
                    ORDER BY rc.id DESC LIMIT 20
                """)
                if not df_hist_del.empty:
                    with st.expander("Excluir lançamento incorreto (gerência)"):
                        opcoes_del = {
                            f"#{r['id']} — {r['nome_fonte']} / {r['mes_referencia']} — {format_br(r['valor_realizado'])}": r['id']
                            for _, r in df_hist_del.iterrows()
                        }
                        sel_del = st.selectbox("Selecione o lançamento:", list(opcoes_del.keys()))
                        if st.button("Confirmar exclusão", type="secondary"):
                            run_exec("DELETE FROM Registro_Captacao_DI WHERE id = %s", (opcoes_del[sel_del],))
                            st.success("Lançamento excluído.")
                            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # ABA 2 — COMUNICAÇÃO E IMPRENSA
    # ══════════════════════════════════════════════════════════════════════════
    # ── Setup compartilhado ───────────────────────────────────────────────────
    run_exec(
        "CREATE TABLE IF NOT EXISTS Indicadores_Comunicacao_2026 ("
        "id SERIAL PRIMARY KEY, indicador TEXT NOT NULL, "
        "mes_referencia TEXT NOT NULL, valor FLOAT NOT NULL DEFAULT 0, "
        "registrado_em TIMESTAMP DEFAULT NOW(), "
        "UNIQUE (indicador, mes_referencia))"
    )

    _ind_imprensa = [
        {"indicador": "Envios do boletim semanal via WhatsApp", "meta": 52,      "unidade": ""},
        {"indicador": "Artigos enviados",                        "meta": 100,     "unidade": ""},
        {"indicador": "Artigos publicados",                      "meta": 180,     "unidade": ""},
        {"indicador": "Releases produzidos",                     "meta": 142,     "unidade": ""},
        {"indicador": "Clipping",                                "meta": 3058,    "unidade": ""},
        {"indicador": "Radios parceiras",                        "meta": 209,     "unidade": ""},
        {"indicador": "Entrevistas (Radio, TV e Portais)",       "meta": 955,     "unidade": ""},
        {"indicador": "Insercoes medicas em veiculos municipais","meta": 128,     "unidade": ""},
        {"indicador": "Inscritos na Newsletter",                 "meta": 2061,    "unidade": ""},
        {"indicador": "Treinamentos",                            "meta": 10,      "unidade": ""},
    ]
    _ind_digital = [
        {"indicador": "Seguidores no Instagram",                        "meta": 116397,  "unidade": ""},
        {"indicador": "Seguidores no Facebook",                         "meta": 73400,   "unidade": ""},
        {"indicador": "Seguidores no LinkedIn",                         "meta": 1108,    "unidade": ""},
        {"indicador": "Seguidores no Twitter/X",                        "meta": 2027,    "unidade": ""},
        {"indicador": "Inscritos no YouTube",                           "meta": 670,     "unidade": ""},
        {"indicador": "Inscritos no TikTok",                            "meta": 31000,   "unidade": ""},
        {"indicador": "Cliques no Google ADS",                          "meta": 34664,   "unidade": ""},
        {"indicador": "Conversao de Leads (novos cadastros p/ doacao)", "meta": 100,     "unidade": ""},
        {"indicador": "Taxa de Engajamento Media",                      "meta": 5.0,     "unidade": "%"},
        {"indicador": "Alcance total (redes sociais)",                  "meta": 2000300, "unidade": ""},
    ]

    _mes_atual_c   = datetime.now().month
    _mes_atual_str = datetime.now().strftime("%Y-%m")
    _meses_opcoes  = [f"2026-{m:02d}" for m in range(1, 13)]
    _idx_mes_pad   = _meses_opcoes.index(_mes_atual_str) if _mes_atual_str in _meses_opcoes else 0

    df_ultimos_com = run_query(
        "SELECT DISTINCT ON (indicador) indicador, valor, mes_referencia "
        "FROM Indicadores_Comunicacao_2026 ORDER BY indicador, mes_referencia DESC"
    )
    _vals_atual_com = dict(zip(df_ultimos_com['indicador'], df_ultimos_com['valor'])) if not df_ultimos_com.empty else {}

    def _barra_com(ind, atual, mes_c):
        meta    = ind["meta"]
        unidade = ind["unidade"]
        pct     = min(atual / meta, 1.0) if meta > 0 else 0.0
        prorata = meta / 12 * mes_c
        pct_vs  = atual / prorata if prorata > 0 else 0.0
        prorata_pct = min(prorata / meta, 1.0) if meta > 0 else 0.0
        if atual == 0:
            badge, badge_cor = "Sem registro", "#94A3B8"
        elif pct_vs >= 1.0:
            badge, badge_cor = "No prazo", "#059669"
        elif pct_vs >= 0.7:
            badge, badge_cor = "Em risco", "#D97706"
        else:
            badge, badge_cor = "Atrasado", "#DC2626"
        cor_bar = badge_cor
        def _fmt(v):
            return f"{v:.1f}{unidade}" if unidade == "%" else f"{v:,.0f}".replace(",", ".")
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:1px;">'
            f'  <span style="font-size:13px;font-weight:600;">{ind["indicador"]}</span>'
            f'  <span style="font-size:11px;font-weight:700;color:{badge_cor};">{badge}</span>'
            f'</div>'
            f'<div style="position:relative;background:#2D3748;border-radius:6px;height:10px;margin-bottom:3px;">'
            f'  <div style="background:{cor_bar};width:{pct*100:.1f}%;height:10px;border-radius:6px;"></div>'
            f'  <div style="position:absolute;top:0;left:{prorata_pct*100:.1f}%;width:2px;height:10px;background:#F59E0B;opacity:.8;"></div>'
            f'  <span style="position:absolute;right:5px;top:0;font-size:9px;line-height:10px;color:#fff;font-weight:700;">{pct*100:.0f}%</span>'
            f'</div>'
            f'<div style="display:flex;gap:12px;font-size:11px;color:#888;margin-bottom:6px;">'
            f'  <span>Meta: <b style="color:#ccc;">{_fmt(meta)}</b></span>'
            f'  <span>Realizado: <b style="color:{cor_bar};">{_fmt(atual)}</b></span>'
            f'  <span>Pro-rata ({mes_c}m): <b style="color:#F59E0B;">{_fmt(prorata)}</b></span>'
            f'</div>'
            f'<hr style="margin:2px 0 6px 0;border-color:rgba(255,255,255,0.06);">',
            unsafe_allow_html=True
        )

    def _render_aba_com(lista, prefix, form_key):
        mes_sel = st.selectbox("Mes de referencia", _meses_opcoes,
                               index=_idx_mes_pad, key=f"mes_sel_{prefix}",
                               format_func=lambda m: datetime.strptime(m, "%Y-%m").strftime("%B/%Y").capitalize())
        df_mes_com = run_query(
            "SELECT indicador, valor FROM Indicadores_Comunicacao_2026 WHERE mes_referencia = %s",
            (mes_sel,)
        )
        _vals_mes_com = dict(zip(df_mes_com['indicador'], df_mes_com['valor'])) if not df_mes_com.empty else {}

        with st.expander("Registrar valores do mes", expanded=False):
            with st.form(form_key, clear_on_submit=False):
                cols = st.columns(2)
                vals = {}
                for i, ind in enumerate(lista):
                    key = ind["indicador"]
                    _eh_pct = ind["unidade"] == "%"
                    _val_db = float(_vals_mes_com.get(key, _vals_atual_com.get(key, 0)))
                    if _eh_pct:
                        vals[key] = cols[i % 2].number_input(
                            ind["indicador"], value=_val_db,
                            min_value=0.0, step=0.1, format="%.1f", key=f"{prefix}_pct_{i}"
                        )
                    else:
                        vals[key] = cols[i % 2].number_input(
                            ind["indicador"], value=int(_val_db),
                            min_value=0, step=1, key=f"{prefix}_int_{i}"
                        )
                if st.form_submit_button("Salvar mes", type="primary", use_container_width=True):
                    for nome_ind, valor in vals.items():
                        run_exec(
                            "INSERT INTO Indicadores_Comunicacao_2026 (indicador, mes_referencia, valor) "
                            "VALUES (%s, %s, %s) ON CONFLICT (indicador, mes_referencia) DO UPDATE "
                            "SET valor = EXCLUDED.valor, registrado_em = NOW()",
                            (nome_ind, mes_sel, valor)
                        )
                    st.success(f"Valores de {mes_sel} salvos.")
                    st.rerun()

        nomes_lista = [ind["indicador"] for ind in lista]
        df_hist_c = run_query(
            "SELECT indicador, mes_referencia, valor FROM Indicadores_Comunicacao_2026 "
            "ORDER BY indicador, mes_referencia"
        )
        if not df_hist_c.empty:
            df_hist_f = df_hist_c[df_hist_c['indicador'].isin(nomes_lista)]
            if not df_hist_f.empty:
                with st.expander("Ver evolucao mes a mes", expanded=False):
                    df_piv = df_hist_f.pivot(index='indicador', columns='mes_referencia', values='valor')
                    df_piv.columns.name = None
                    df_piv.index.name = "Indicador"
                    df_piv.columns = [
                        datetime.strptime(c, "%Y-%m").strftime("%b/%y") if len(str(c)) == 7 else c
                        for c in df_piv.columns
                    ]
                    st.dataframe(df_piv.fillna("—"), use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        for ind in lista:
            _barra_com(ind, float(_vals_atual_com.get(ind["indicador"], 0)), _mes_atual_c)

    with tab_imp:
        _render_aba_com(_ind_imprensa, "imp", "form_imp_mensal")

    with tab_dig:
        _render_aba_com(_ind_digital, "dig", "form_dig_mensal")


elif menu == "Ações":
    user      = st.session_state.user_data
    eh_gerente = user["perfil"] == "gerencia"
    meu_setor  = user["setor"]
    meu_nome   = user["nome"]

    page_header("Centro de Ações", "Gerencie demandas, acompanhe a equipe e veja follow-ups de CRM.")

    # ── Reset diário de tarefas recorrentes ──────────────────────────────────
    run_exec("""
        UPDATE Demandas_Estrategicas
        SET status = 'PENDENTE'
        WHERE is_diaria = 1
          AND status = 'REALIZADO'
          AND data_ultima_conclusao::date < CURRENT_DATE
    """)

    # ── KPI rápido ───────────────────────────────────────────────────────────
    def _cnt(status):
        sql = f"SELECT COUNT(*) AS n FROM Demandas_Estrategicas WHERE status = '{status}'"
        if not eh_gerente:
            sql += f" AND setor = '{meu_setor}'"
        r = run_query(sql)
        return int(r.iloc[0]["n"]) if not r.empty else 0

    _pend = _cnt("PENDENTE")
    _bloq = _cnt("BLOQUEADO")
    _real = _cnt("REALIZADO")

    kpi_row([
        {"label": "Pendentes",    "value": _pend, "accent": _pend > 0},
        {"label": "Com barreira", "value": _bloq, "accent": _bloq > 0},
        {"label": "Concluídas",  "value": _real},
    ])

    # ── Formulário de nova demanda ───────────────────────────────────────────
    dados_equipe = {
        "MARKETING DIGITAL": ["Produção de Peças Avulsas", "Edição de Vídeo/Reels", "Gestão de Redes Sociais", "Campanha Google Ads", "Atualização de Site"],
        "IMPRENSA":          ["Redação de Release", "Clipping de Projetos", "Agendamento de Pauta", "Artigos Institucionais", "Boletim Informativo"],
        "PROJETOS":          ["Escrita de Novo Edital", "Relatório de Prestação de Contas", "Pesquisa de Editais", "Inscrição em Prêmios"],
        "GERÊNCIA":          ["Manutenção de Parcerias", "Análise de Relatórios", "Planejamento Anual", "Gestão de Equipe"],
    }

    with st.expander("Nova demanda", expanded=False):
        with st.form("form_nova_demanda", clear_on_submit=True):
            _fc1, _fc2, _fc3 = st.columns(3)
            _setor_opcoes = list(dados_equipe.keys())
            _setor_sel = _fc1.selectbox(
                "Setor", _setor_opcoes,
                index=_setor_opcoes.index(meu_setor) if meu_setor in _setor_opcoes else 0,
                disabled=not eh_gerente,
            )
            _tarefa_sel  = _fc2.selectbox("Tipo de tarefa", dados_equipe[_setor_sel])
            _data_p      = _fc3.date_input("Prazo", datetime.now())

            _fd1, _fd2 = st.columns(2)
            _detalhes    = _fd1.text_input("Descrição / complemento")
            _nomes_eq    = ["-- A definir --"] + sorted(
                c["nome"] for c in CONTAS.values() if c["setor"] == _setor_sel
            )
            _resp_sel    = _fd2.selectbox("Responsável", _nomes_eq)
            _is_diaria   = _fd2.checkbox("Tarefa diária (repete todo dia)")

            st.markdown("**Prioridade GUT**")
            _pg1, _pg2, _pg3 = st.columns(3)
            _g = _pg1.select_slider("Gravidade",  [1,2,3,4,5], 3, key="gut_g")
            _u = _pg2.select_slider("Urgência",   [1,2,3,4,5], 3, key="gut_u")
            _t = _pg3.select_slider("Tendência",  [1,2,3,4,5], 3, key="gut_t")

            if st.form_submit_button("Lançar demanda", use_container_width=True, type="primary"):
                _score     = _g * _u * _t
                _resp_db   = None if _resp_sel == "-- A definir --" else _resp_sel
                _titulo_db = f"[{_tarefa_sel}] {_detalhes} | POR: {meu_nome}".upper()
                run_exec(
                    """INSERT INTO Demandas_Estrategicas
                       (tarefa, setor, gravidade, urgencia, tendencia, score_gut,
                        status, data_prevista, is_diaria, responsavel)
                       VALUES (%s,%s,%s,%s,%s,%s,'PENDENTE',%s,%s,%s)""",
                    (_titulo_db, _setor_sel, _g, _u, _t, _score,
                     _data_p.strftime("%Y-%m-%d"), 1 if _is_diaria else 0, _resp_db),
                )
                st.success("Demanda lançada!")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Fila de trabalho ─────────────────────────────────────────────────────
    section("Fila de trabalho")

    _qsql  = "SELECT * FROM Demandas_Estrategicas WHERE status IN ('PENDENTE','BLOQUEADO')"
    _qpars = []
    if not eh_gerente:
        _qsql += " AND setor = %s"
        _qpars.append(meu_setor)
    _demandas = run_query(_qsql + " ORDER BY status DESC, score_gut DESC", tuple(_qpars))

    if _demandas.empty:
        empty_state("—", "Tudo em dia!", "Nenhuma demanda pendente no momento.")
    else:
        for _, _row in _demandas.iterrows():
            _is_b = _row["status"] == "BLOQUEADO"
            _cor  = "#7030A0" if _is_b else (
                "#DC2626" if _row["score_gut"] >= 80 else
                "#D97706" if _row["score_gut"] >= 40 else "#1D9E75"
            )
            _cc1, _cc2, _cc3 = st.columns([0.5, 7.5, 2], vertical_alignment="center")
            with _cc1:
                if st.checkbox("", key=f"chk_{_row['id']}"):
                    run_exec(
                        "UPDATE Demandas_Estrategicas SET status='REALIZADO', data_ultima_conclusao=CURRENT_TIMESTAMP WHERE id=%s",
                        (_row["id"],)
                    )
                    st.toast("Concluida.")
                    st.rerun()
            with _cc2:
                _dt_prev = str(_row["data_prevista"])[:10] if _row.get("data_prevista") else "—"
                _tag_d   = '<span style="background:#378ADD22;color:#378ADD;border:1px solid #378ADD55;border-radius:10px;font-size:9px;padding:1px 6px;margin-left:6px;">DIÁRIA</span>' if _row.get("is_diaria") else ""
                _prefix  = '<b style="color:#DC2626;">[BLOQUEADO]</b> ' if _is_b else ""
                st.markdown(
                    f'<div style="border-left:3px solid {_cor};padding:6px 10px;border-radius:0 6px 6px 0;'
                    f'background:rgba(255,255,255,0.02);margin:2px 0;">'
                    f'<div style="font-size:13px;font-weight:600;">{_prefix}{_row["tarefa"]}{_tag_d}</div>'
                    f'<div style="font-size:11px;color:rgba(255,255,255,0.4);margin-top:2px;">'
                    f'Setor: {_row["setor"]} · Prazo: {_dt_prev}'
                    + (f' · Resp.: {_row["responsavel"]}' if _row.get("responsavel") else "")
                    + f'</div></div>',
                    unsafe_allow_html=True,
                )
            with _cc3:
                st.markdown(
                    f'<div style="text-align:center;font-size:14px;font-weight:800;color:{_cor};">'
                    f'{_row["score_gut"]} pts</div>',
                    unsafe_allow_html=True,
                )
                _label_b = "Liberar" if _is_b else "Pedir ajuda"
                if st.button(_label_b, key=f"btn_{_row['id']}", use_container_width=True,
                             type="primary" if _is_b else "secondary"):
                    run_exec(
                        "UPDATE Demandas_Estrategicas SET status=%s WHERE id=%s",
                        ("PENDENTE" if _is_b else "BLOQUEADO", _row["id"]),
                    )
                    st.rerun()

    # ── Realizadas + Métricas ────────────────────────────────────────────────
    with st.expander("Histórico e métricas"):
        _sql_hist = "SELECT tarefa, TO_CHAR(data_ultima_conclusao,'DD/MM/YYYY HH24:MI') AS concluido_em FROM Demandas_Estrategicas WHERE status='REALIZADO'"
        if not eh_gerente:
            _sql_hist += f" AND setor='{meu_setor}'"
        _hist = run_query(_sql_hist + " ORDER BY data_ultima_conclusao DESC LIMIT 10")
        if not _hist.empty:
            st.dataframe(_hist, use_container_width=True, hide_index=True)

        _sql_stats = """SELECT TO_CHAR(data_ultima_conclusao,'MM/YYYY') AS mes,
                               COUNT(*) AS total
                        FROM Demandas_Estrategicas
                        WHERE status='REALIZADO' AND data_ultima_conclusao IS NOT NULL"""
        if not eh_gerente:
            _sql_stats += f" AND setor='{meu_setor}'"
        _sql_stats += " GROUP BY TO_CHAR(data_ultima_conclusao,'MM/YYYY') ORDER BY MIN(data_ultima_conclusao) DESC LIMIT 6"
        _df_stats = run_query(_sql_stats)
        if not _df_stats.empty:
            st.markdown("---")
            _sc = st.columns(len(_df_stats))
            for _i, (_idx, _r) in enumerate(zip(range(len(_df_stats)), _df_stats.itertuples())):
                _sc[_i].markdown(
                    f'<div style="text-align:center;border-left:1px solid rgba(255,255,255,0.1);padding:4px;">'
                    f'<div style="font-size:10px;opacity:.5;">{_r.mes}</div>'
                    f'<div style="font-size:22px;font-weight:800;color:#1D9E75;">{_r.total}</div>'
                    f'<div style="font-size:9px;opacity:.3;">FEITAS</div></div>',
                    unsafe_allow_html=True,
                )

    # ── Follow-ups de CRM ────────────────────────────────────────────────────
    with st.expander("Follow-ups de relacionamento"):
        _df_crm = run_query("SELECT * FROM View_Tarefas_Abertas")
        if _df_crm.empty:
            st.info("Nenhum follow-up pendente.")
        else:
            _tot_c  = len(_df_crm)
            _atras  = len(_df_crm[_df_crm["Situacao"].str.contains("ATRASADA", na=False)])
            kpi_row([
                {"label": "Total",     "value": _tot_c},
                {"label": "Atrasadas", "value": _atras, "accent": _atras > 0},
            ])
            _tp = st.selectbox("Filtrar tipo", ["TODOS"] + sorted(_df_crm["tipo_tarefa"].unique().tolist()), key="crm_tipo")
            if _tp != "TODOS":
                _df_crm = _df_crm[_df_crm["tipo_tarefa"] == _tp]
            for _, _r in _df_crm.iterrows():
                _cor_c = "#DC2626" if "ATRASADA" in str(_r.get("Situacao","")) else "#D97706" if "URGENTE" in str(_r.get("Situacao","")) else "#1D9E75"
                st.markdown(
                    f'<div style="border-left:3px solid {_cor_c};padding:5px 10px;border-radius:0 6px 6px 0;'
                    f'background:rgba(255,255,255,0.02);margin:3px 0;">'
                    f'<div style="font-size:12px;font-weight:600;">{_r.get("Empresa","—")} — {_r.get("tipo_tarefa","")}</div>'
                    f'<div style="font-size:11px;color:rgba(255,255,255,0.4);">{_r.get("Situacao","")}'
                    + (f' · Prazo: {str(_r.get("data_prazo",""))[:10]}' if _r.get("data_prazo") else "")
                    + f'</div></div>',
                    unsafe_allow_html=True,
                )

    # ── Admin (gerência) ─────────────────────────────────────────────────────
    if eh_gerente:
        with st.expander("Gestão de usuários"):
            section("Usuários do sistema")
            for _login, _dados in CONTAS.items():
                _ua1, _ua2, _ua3 = st.columns([3, 2, 1])
                _ua1.markdown(f"**{_dados['nome']}** — {_dados['setor']}")
                _ua2.markdown(f"`{_login}` · perfil: `{_dados['perfil']}`")

    # ── Minha Senha ──────────────────────────────────────────────────────────
    with st.expander("Alterar minha senha"):
        _login_cur = next((k for k, v in CONTAS.items() if v.get("nome") == meu_nome), None)
        run_exec("""CREATE TABLE IF NOT EXISTS Usuario_Senhas (login TEXT PRIMARY KEY, senha TEXT NOT NULL)""")
        with st.form("form_senha_acao", clear_on_submit=True):
            _s1 = st.text_input("Senha atual",        type="password", placeholder="••••••")
            _s2 = st.text_input("Nova senha",         type="password", placeholder="Mínimo 6 caracteres")
            _s3 = st.text_input("Confirmar nova senha", type="password", placeholder="Repita a nova senha")
            if st.form_submit_button("Salvar", use_container_width=True, type="primary"):
                _df_s = run_query("SELECT senha FROM Usuario_Senhas WHERE login=%s", (_login_cur,))
                _senha_ok = _df_s.iloc[0]["senha"] if not _df_s.empty else CONTAS.get(_login_cur,{}).get("senha","")
                if not _s1:
                    st.error("Informe a senha atual.")
                elif _s1 != _senha_ok:
                    st.error("Senha atual incorreta.")
                elif len(_s2) < 6:
                    st.error("A nova senha deve ter pelo menos 6 caracteres.")
                elif _s2 != _s3:
                    st.error("As senhas não conferem.")
                else:
                    run_exec("INSERT INTO Usuario_Senhas (login,senha) VALUES (%s,%s) ON CONFLICT (login) DO UPDATE SET senha=EXCLUDED.senha", (_login_cur, _s2))
                    st.success("Senha alterada com sucesso.")


elif menu == "Almoço CDP":
    # datetime, timedelta e pandas já importados no topo
    # CSS (.glass-card e .guest-item) já está no CSS_GLOBAL

    page_header("Almoço CDP", "Controle de convidados, confirmações e check-in do mês.")
    
    # 1. Definição do Mês de Referência
    mes_atual = datetime.now().strftime("%m/%Y")
    
    # Busca todos os meses que já têm algum cadastro no banco de dados
    df_meses = run_query_slow("SELECT DISTINCT mes_referencia FROM Convidados_Almoco")
    meses_cadastrados = df_meses['mes_referencia'].tolist() if not df_meses.empty else []
    
    # Junta o mês atual, os meses do banco e meses futuros para planejamento (evita duplicidade usando set)
    lista_meses = list(set([mes_atual, "04/2026", "05/2026", "06/2026"] + meses_cadastrados))
    
    # Ordena a lista cronologicamente do mais recente para o mais antigo
    lista_meses.sort(key=lambda x: datetime.strptime(x, "%m/%Y"), reverse=True)
    
    _idx_mes = lista_meses.index(mes_atual) if mes_atual in lista_meses else 0
    mes_ref = st.selectbox("Mês do evento", lista_meses, index=_idx_mes, help="Selecione o mês do evento")
    
    # BUSCA OS DADOS
    df_almoco = run_query("SELECT * FROM Convidados_Almoco WHERE mes_referencia = ?", (mes_ref,))
    
    metas = {
        "Influencers": 3, "Imprensa": 3, "Doadores alto valor": 6, 
        "Cofrinhos": 2, "Parlamentar": 3, "Parceiros CDP": 12
    }

    tab_recepcao, tab_planejamento = st.tabs(["Check-in e recepção", "Planejamento mensal"])

    # ==========================================
    # ABA 1: RECEPÇÃO (MODO INTELIGENTE)
    # ==========================================
    with tab_recepcao:
        df_conf = df_almoco[df_almoco['confirmado'] == 1].copy() if not df_almoco.empty else pd.DataFrame()
        pres = len(df_conf[df_conf['compareceu'] == 1]) if not df_conf.empty else 0
        tot = len(df_conf)
        pct_ocup = int(100 * pres / tot) if tot > 0 else 0

        kpi_row([
            {"label": "Confirmados", "value": tot},
            {"label": "Presentes",   "value": pres, "accent": True},
            {"label": "Ocupação",    "value": f"{pct_ocup}%"},
        ])
        if tot > 0:
            st.progress(pres/tot, text=f"{pres} de {tot} confirmados presentes")

        section("Lista de recepção")
        col_fila, col_brief = st.columns([1.5, 1])

        with col_fila:
            # --- NOVO: CADASTRO RÁPIDO COM WHATSAPP ---
            with st.expander("Adicionar convidado extra (última hora)"):
                with st.form("form_fast_checkin", clear_on_submit=True):
                    st.caption("Cadastre o contato e libere a entrada. A presença será confirmada automaticamente.")
                    fc1, fc2 = st.columns(2)
                    fast_nome = fc1.text_input("Nome *")
                    fast_telefone = fc2.text_input("WhatsApp *")
                    fast_cargo = fc1.text_input("Cargo")
                    fast_empresa = fc2.text_input("Empresa/Instituição")
                    fast_seg = st.selectbox("Segmento *", list(metas.keys()))
                    
                    if st.form_submit_button("Liberar entrada e fazer check-in", type="primary"):
                        if fast_nome:
                            # Insere a pessoa já com telefone, confirmado=1 e compareceu=1
                            run_insert("""
                                INSERT INTO Convidados_Almoco 
                                (mes_referencia, segmento, nome, cargo, empresa, telefone, confirmado, compareceu) 
                                VALUES (%s,%s,%s,%s,%s,%s, TRUE, TRUE)
                            """, (mes_ref, fast_seg, fast_nome.title(), fast_cargo.title(), fast_empresa, fast_telefone))
                            st.toast(f"Entrada liberada para {fast_nome}!")
                            st.rerun()
                        else:
                            st.error("O nome é obrigatório.")
            
            # --- BUSCA E LISTA DE CHECK-IN ---
            busca = st.text_input("Buscar por nome...", label_visibility="collapsed", placeholder="Buscar na lista...")
            
            if not df_conf.empty:
                df_v = df_conf[df_conf['nome'].str.contains(busca, case=False, na=False)] if busca else df_conf
                for _, row in df_v.iterrows():
                    with st.container():
                        st.markdown(f"""
                        <div class="guest-item">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <b>{str(row['nome']).title()}</b><br>
                                    <small style="opacity:0.7;">{str(row['cargo']).title() if pd.notna(row['cargo']) else ''} | {row['empresa'] if pd.notna(row['empresa']) else ''} | Tel: {row['telefone'] if pd.notna(row['telefone']) else 'Sem número'}</small>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        label_btn = "Fazer Check-in" if not row['compareceu'] else "Anular Presença"
                        if st.button(label_btn, key=f"btn_{row['id']}", type="primary" if not row['compareceu'] else "secondary", use_container_width=True):
                            novo_status = not bool(row['compareceu'])
                            run_insert("UPDATE Convidados_Almoco SET compareceu = %s WHERE id = %s", (novo_status, row['id']))
                            st.rerun()

        # --- DOSSIÊ EXECUTIVO ---
        with col_brief:
            section("Dossiê executivo")
            df_p = df_conf[df_conf['compareceu'] == 1] if not df_conf.empty else pd.DataFrame()
            
            if not df_p.empty:
                msg_whatsapp = f"*PRESENTES NO ALMOÇO CDP - {mes_ref}*\n\n"
                
                html_visual = f"""
                <div class="glass-card">
                    <h4 style="color: #00CC96; margin-top: 0; text-align: center; font-size: 1.1rem;">LISTA DE PRESENÇA</h4>
                    <hr style="border-color: rgba(255,255,255,0.05); margin-bottom: 15px;">
                """
                
                for seg, gp in df_p.groupby('segmento'):
                    msg_whatsapp += f"*{seg.upper()}*\n"
                    html_visual += f"<h6 style='color: #00FFC2; margin-top: 15px; font-size: 0.9rem; letter-spacing: 1px;'>{seg.upper()}</h6><ul style='list-style-type: none; padding-left: 5px;'>"
                    
                    for _, p in gp.iterrows():
                        nome_fmt = str(p['nome']).title()
                        cargo_raw = str(p['cargo']).strip()
                        tem_cargo = cargo_raw and cargo_raw.lower() not in ['nan', 'none', '']
                        
                        if tem_cargo:
                            cargo_fmt = cargo_raw.title()
                            msg_whatsapp += f"• {nome_fmt} ({cargo_fmt})\n"
                            html_visual += f"<li style='margin-bottom: 10px;'><b>{nome_fmt}</b><br><span style='opacity: 0.6; font-size: 0.85em; margin-left: 20px;'>— {cargo_fmt}</span></li>"
                        else:
                            msg_whatsapp += f"• {nome_fmt}\n"
                            html_visual += f"<li style='margin-bottom: 10px;'><b>{nome_fmt}</b></li>"
                    
                    msg_whatsapp += "\n"
                    html_visual += "</ul>"
                
                html_visual += "</div>"
                st.markdown(html_visual, unsafe_allow_html=True)
                
                with st.expander("Copiar para WhatsApp"):
                    st.code(msg_whatsapp, language="markdown")
            else:
                st.info("Nenhum convidado presente no momento.")

        # --- DOWNLOAD PDF DE CONFIRMADOS ---
        st.divider()
        _col_pdf_info, _col_pdf_btn = st.columns([3, 1])
        _n_conf = len(df_conf)
        _col_pdf_info.markdown(
            f"<span style='font-size:0.95rem;opacity:0.8;'>"
            f"<b style='color:#00CC96;'>{_n_conf}</b> confirmados para o Almoço CDP de <b>{mes_ref}</b>"
            f"</span>",
            unsafe_allow_html=True
        )

        if _n_conf > 0:
            import os as _os
            from io import BytesIO
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors as _rl_colors
            from reportlab.lib.units import cm as _rl_cm
            from reportlab.platypus import (BaseDocTemplate as _RLBase, Frame as _RLFrame,
                                            PageTemplate as _RLPageTpl,
                                            Table as _RLTable, TableStyle as _RLTableStyle,
                                            Paragraph as _RLPar, Spacer as _RLSpacer)
            from reportlab.lib.styles import ParagraphStyle as _RLParStyle
            from reportlab.lib.enums import TA_CENTER as _TA_CENTER, TA_LEFT as _TA_LEFT

            def _gerar_pdf_confirmados(df_c, mes_r):
                _buf = BytesIO()
                _PW, _PH = A4   # 595.27 x 841.89 pt

                _assets      = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets")
                _img_lateral = _os.path.join(_assets, "timbrado_lateral.jpeg")
                _img_logo    = _os.path.join(_assets, "timbrado_logo.png")
                _img_rodape  = _os.path.join(_assets, "timbrado_rodape.png")

                # Margens
                _LM = 2.9 * _rl_cm
                _RM = 1.6 * _rl_cm
                _TM = 4.0 * _rl_cm
                _BM = 3.4 * _rl_cm
                _CW = _PW - _LM - _RM   # largura útil do conteúdo

                def _draw_timbrado(canvas, doc):
                    canvas.saveState()
                    if _os.path.exists(_img_lateral):
                        canvas.drawImage(_img_lateral, 0, 0,
                                         width=1.6*_rl_cm, height=_PH,
                                         preserveAspectRatio=False)
                    if _os.path.exists(_img_logo):
                        _lh = 2.8 * _rl_cm
                        _lw = _lh * (645 / 595)
                        canvas.drawImage(_img_logo,
                                         1.8*_rl_cm, _PH - _lh - 0.55*_rl_cm,
                                         width=_lw, height=_lh, mask="auto")
                    if _os.path.exists(_img_rodape):
                        _fh = 2.8 * _rl_cm
                        _fw = _PW - 1.7*_rl_cm
                        canvas.drawImage(_img_rodape,
                                         1.7*_rl_cm, 0.2*_rl_cm,
                                         width=_fw, height=_fh,
                                         preserveAspectRatio=True, anchor="sw", mask="auto")

                    # Linha verde fina separando área do logo do conteúdo
                    from reportlab.lib import colors as _c
                    canvas.setStrokeColor(_c.HexColor("#00CC96"))
                    canvas.setLineWidth(1.2)
                    canvas.line(_LM, _PH - _TM + 0.3*_rl_cm,
                                _PW - _RM, _PH - _TM + 0.3*_rl_cm)
                    # Linha verde fina separando conteúdo do rodapé
                    canvas.line(_LM, _BM - 0.3*_rl_cm,
                                _PW - _RM, _BM - 0.3*_rl_cm)
                    canvas.restoreState()

                _frame = _RLFrame(_LM, _BM, _CW, _PH - _TM - _BM,
                                  leftPadding=0, rightPadding=0,
                                  topPadding=0, bottomPadding=0)
                _tpl  = _RLPageTpl(id="timbrado", frames=[_frame], onPage=_draw_timbrado)
                _doc  = _RLBase(_buf, pagesize=A4, pageTemplates=[_tpl])

                # ── Cores e estilos ───────────────────────────────────────
                _GREEN     = _rl_colors.HexColor("#00CC96")
                _GREEN_DK  = _rl_colors.HexColor("#009970")
                _DARK      = _rl_colors.HexColor("#1A1A2E")
                _LGRAY     = _rl_colors.HexColor("#F6FAFA")
                _MGRAY     = _rl_colors.HexColor("#E8F5F2")
                _GRAY_TXT  = _rl_colors.HexColor("#666666")
                _GRAY_LINE = _rl_colors.HexColor("#D5E8E3")

                _st_titulo = _RLParStyle("cdp_titulo",
                    fontSize=18, textColor=_DARK, leading=22,
                    spaceAfter=2, alignment=_TA_LEFT,
                    fontName="Helvetica-Bold")
                _st_evento = _RLParStyle("cdp_evento",
                    fontSize=10, textColor=_GREEN_DK, leading=14,
                    spaceAfter=0, alignment=_TA_LEFT,
                    fontName="Helvetica-Bold")
                _st_total  = _RLParStyle("cdp_total",
                    fontSize=8.5, textColor=_GRAY_TXT, leading=12,
                    alignment=_TA_LEFT, fontName="Helvetica")
                _st_rodape = _RLParStyle("cdp_rodape",
                    fontSize=7.5, textColor=_GRAY_TXT, leading=11,
                    alignment=_TA_CENTER, fontName="Helvetica")

                # ── Cabeçalho do documento ────────────────────────────────
                from reportlab.platypus import HRFlowable as _RLHR
                _elems = []
                _elems.append(_RLSpacer(1, 0.15*_rl_cm))
                _elems.append(_RLPar("Lista de Confirmados", _st_titulo))
                _elems.append(_RLPar(f"Almoço CDP &nbsp;&mdash;&nbsp; {mes_r}", _st_evento))
                _elems.append(_RLSpacer(1, 0.35*_rl_cm))
                _elems.append(_RLHR(width="100%", thickness=0.8,
                                    color=_GRAY_LINE, spaceAfter=6))

                # ── Tabela ────────────────────────────────────────────────
                _cw = [_CW * 0.37, _CW * 0.31, _CW * 0.32]
                _data = [["NOME", "CARGO / FUNÇÃO", "EMPRESA"]]

                for _, _row in df_c.assign(
                        _emp_sort=df_c["empresa"].fillna("").str.upper().str.strip().apply(lambda v: ("Z_" + v) if v in ("", "-", "NAN", "NONE") else v),
                        _nom_sort=df_c["nome"].fillna("").str.upper().str.strip()
                    ).sort_values(["_emp_sort", "_nom_sort"]).iterrows():
                    _nome = str(_row.get("nome", "")).upper()
                    _car  = str(_row.get("cargo",   "")) if pd.notna(_row.get("cargo",   "")) else ""
                    _emp  = str(_row.get("empresa", "")) if pd.notna(_row.get("empresa", "")) else ""
                    _car  = _car.upper() if _car.lower() not in ["nan", "none", ""] else "-"
                    _emp  = _emp.upper() if _emp.lower() not in ["nan", "none", ""] else "-"
                    _data.append([_nome, _car, _emp])

                _t = _RLTable(_data, colWidths=_cw, repeatRows=1)
                _n_rows = len(_data)
                _row_bgs = []
                for _ri in range(1, _n_rows):
                    _bg = _LGRAY if _ri % 2 == 0 else _rl_colors.white
                    _row_bgs.append(("BACKGROUND", (0, _ri), (-1, _ri), _bg))

                _t.setStyle(_RLTableStyle([
                    # Cabeçalho
                    ("BACKGROUND",     (0, 0), (-1, 0), _GREEN),
                    ("TEXTCOLOR",      (0, 0), (-1, 0), _rl_colors.white),
                    ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE",       (0, 0), (-1, 0), 9),
                    ("ALIGN",          (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN",         (0, 0), (-1, 0), "MIDDLE"),
                    ("TOPPADDING",     (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING",  (0, 0), (-1, 0), 9),
                    ("LEFTPADDING",    (0, 0), (-1, 0), 10),
                    ("RIGHTPADDING",   (0, 0), (-1, 0), 10),
                    # Corpo
                    ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE",       (0, 1), (-1, -1), 8.5),
                    ("TEXTCOLOR",      (0, 1), (-1, -1), _DARK),
                    ("ALIGN",          (0, 1), (-1, -1), "LEFT"),
                    ("VALIGN",         (0, 1), (-1, -1), "MIDDLE"),
                    ("TOPPADDING",     (0, 1), (-1, -1), 7),
                    ("BOTTOMPADDING",  (0, 1), (-1, -1), 7),
                    ("LEFTPADDING",    (0, 1), (-1, -1), 10),
                    ("RIGHTPADDING",   (0, 1), (-1, -1), 10),
                    # Bordas
                    ("LINEBELOW",      (0, 0), (-1, -2), 0.4, _GRAY_LINE),
                    ("LINEBELOW",      (0, -1), (-1, -1), 0.8, _GREEN),
                    ("LINEBEFORE",     (1, 0), (1, -1), 0.4, _GRAY_LINE),
                    ("LINEBEFORE",     (2, 0), (2, -1), 0.4, _GRAY_LINE),
                    ("BOX",            (0, 0), (-1, -1), 0.4, _GRAY_LINE),
                ] + _row_bgs))

                _elems.append(_t)
                _elems.append(_RLSpacer(1, 0.3*_rl_cm))

                # Linha de total + data
                _total_tbl = _RLTable(
                    [[f"Sistema DI  •  {len(df_c)} confirmados",
                      f"Gerado em {(datetime.now() - timedelta(hours=3)).strftime('%d/%m/%Y  %H:%M')} (Brasília)"]],
                    colWidths=[_CW * 0.5, _CW * 0.5]
                )
                _total_tbl.setStyle(_RLTableStyle([
                    ("FONTNAME",  (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE",  (0, 0), (-1, -1), 8),
                    ("TEXTCOLOR", (0, 0), (-1, -1), _GRAY_TXT),
                    ("ALIGN",     (0, 0), (0, 0), "LEFT"),
                    ("ALIGN",     (1, 0), (1, 0), "RIGHT"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ]))
                _elems.append(_total_tbl)

                _doc.build(_elems)
                _buf.seek(0)
                return _buf.read()

            _pdf_bytes = _gerar_pdf_confirmados(df_conf, mes_ref)
            _col_pdf_btn.download_button(
                label="Baixar PDF",
                data=_pdf_bytes,
                file_name=f"almoco_cdp_{mes_ref.replace('/', '-')}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
        else:
            _col_pdf_btn.button("Baixar PDF", disabled=True, use_container_width=True,
                                help="Nenhum confirmado ainda para este mês.")

    # ==========================================
    # ABA 2: PLANEJAMENTO
    # ==========================================
    with tab_planejamento:
        section("Cadastro e edição completa")
        with st.expander("NOVO CONVIDADO (Completo)"):
            with st.form("form_planejamento_completo", clear_on_submit=True):
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
                        st.toast(f"{n_c} adicionado ao planejamento!")
                        st.rerun()

        st.divider()
        if not df_almoco.empty:
            df_ed = df_almoco.copy()
            for col in ['contato_1', 'contato_2', 'confirmado']:
                df_ed[col] = df_ed[col].astype(bool)

            edited = st.data_editor(
                df_ed[['id', 'nome', 'cargo', 'empresa', 'telefone', 'segmento', 'contato_1', 'contato_2', 'confirmado']],
                column_config={
                    "id": None, 
                    "confirmado": st.column_config.CheckboxColumn("Confirmou"),
                    "telefone": st.column_config.TextColumn("WhatsApp")
                },
                hide_index=True, 
                use_container_width=True
            )
            
            if st.button("Guardar Alterações da Tabela", type="primary"):
                for _, r in edited.iterrows():
                    run_insert("""
                        UPDATE Convidados_Almoco 
                        SET contato_1=?, contato_2=?, confirmado=?, telefone=?, cargo=?, empresa=?, nome=?
                        WHERE id=?
                    """, (bool(r['contato_1']), bool(r['contato_2']), bool(r['confirmado']), r['telefone'], r['cargo'], r['empresa'], r['nome'], r['id']))
                st.success("Tabela atualizada com sucesso!")
                st.rerun()

# --- 2. PARCEIROS E PROJETOS ---
elif menu == "Parcerias":
    page_header("Gestão de parceiros e projetos", "Cadastro, edição e acompanhamento de parceiros e projetos ativos.")
    tab1, tab2, tab3, tab4 = st.tabs(["Parceiros", "Projetos", "Funil de conversão", "Importar em lote"])
    
    with tab1:

        # 1. BUSCA DE DADOS
        try:
            query = """
                SELECT p.*, c.nome_categoria 
                FROM Parceiro p 
                LEFT JOIN Categoria_Parceiro c ON p.id_categoria = c.id_categoria
            """
            df_p = run_query_cached(query)
        except Exception:
            df_p = run_query_cached("SELECT * FROM Parceiro")

        # KPIs no topo
        if not df_p.empty:
            s_limpo = df_p['status'].fillna("").str.upper().str.strip()
            kpi_row([
                {"label": "Total de parceiros", "value": len(df_p)},
                {"label": "Ativos",       "value": int(s_limpo.str.contains("ATIVO", na=False).sum()), "accent": True},
                {"label": "Prospecção",   "value": int(s_limpo.str.contains("PROSPEC", na=False).sum())},
                {"label": "Inativos",     "value": int(s_limpo.str.contains("INATIVO", na=False).sum())},
            ])

        section("Buscar e visualizar")

        # Filtro de Busca
        busca = st.text_input("Pesquisar parceiro", placeholder="Digite para filtrar por nome...")
        df_view = df_p.copy()
        if busca and not df_view.empty:
            df_view = df_view[df_view['nome_instituicao'].str.contains(busca, case=False, na=False)]

        # Tabela amigável — renomeia colunas e esconde técnicas
        if not df_view.empty:
            df_show = df_view.rename(columns={
                'nome_instituicao': 'Parceiro',
                'status': 'Status',
                'data_adesao': 'Adesão',
                'subcategoria': 'Subcategoria',
                'nome_categoria': 'Categoria',
            })
            colunas_exibir = [c for c in ['Parceiro', 'Status', 'Categoria', 'Subcategoria', 'Adesão'] if c in df_show.columns]
            st.dataframe(
                df_show[colunas_exibir],
                use_container_width=True, hide_index=True, height=320,
                column_config={
                    "Adesão": st.column_config.DateColumn("Adesão", format="DD/MM/YYYY"),
                }
            )
        else:
            empty_state("—", "Nada encontrado", "Ajuste a busca ou cadastre um novo parceiro.")

        section("Ficha do parceiro")

        # Cria uma lista de nomes para o selectbox
        lista_nomes = df_p['nome_instituicao'].tolist() if not df_p.empty else []
        parceiro_selecionado = st.selectbox("Selecione um parceiro para ver os contatos vinculados:", ["Selecione..."] + lista_nomes)

        if parceiro_selecionado != "Selecione...":
            id_selecionado = df_p[df_p['nome_instituicao'] == parceiro_selecionado]['id_parceiro'].values[0]
            query_contatos = f"""
                SELECT nome_pessoa as Nome, cargo as Cargo, telefone as WhatsApp, email as Email 
                FROM Contato_Direto 
                WHERE id_parceiro = {id_selecionado}
            """
            df_contatos_parceiro = run_query(query_contatos)

            if not df_contatos_parceiro.empty:
                st.write(f"**Pessoas de contato em {parceiro_selecionado}:**")
                st.dataframe(df_contatos_parceiro, hide_index=True, use_container_width=True)
            else:
                empty_state("—", f"Sem contatos em {parceiro_selecionado}", "Use o botao NOVO no topo do menu para cadastrar um contato.")

        # 2. SEÇÃO DE CADASTRO
        # Auto-abre se o usuário veio do botão "+ Novo > Parceiro"
        _abrir_p = (st.session_state.open_form == "parceiro")
        if _abrir_p:
            st.session_state.open_form = None  # consome a flag
            st.info("Cadastrando novo parceiro — preencha os campos abaixo.")

        with st.expander("**CADASTRAR NOVO PARCEIRO**", expanded=_abrir_p):
            # Busca categorias para o menu
            df_cat_list = run_query_slow("SELECT id_categoria, nome_categoria FROM Categoria_Parceiro")
            opcoes_cat = dict(zip(df_cat_list['nome_categoria'], df_cat_list['id_categoria']))
            
            with st.form("form_novo_p", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    nome = st.text_input("Nome da instituição *", placeholder="ex: TIM Brasil S.A.")
                    data_input = st.date_input("Data de adesão")
                    sem_data = st.checkbox("Não possuo a data de adesão")

                with col2:
                    status = st.selectbox("Status", ["Ativo", "Inativo", "Prospecção"])
                    cat_nome = st.selectbox("Categoria principal", options=list(opcoes_cat.keys()))
                    sub_txt = st.text_input("Subcategoria / Detalhe", placeholder="ex: Telecom")

                if st.form_submit_button("Salvar parceiro", type="primary", use_container_width=True):
                    if nome:
                        id_cat = opcoes_cat[cat_nome]
                        data_final = None if sem_data else data_input.strftime('%Y-%m-%d')

                        try:
                            sql = """
                                INSERT INTO Parceiro (nome_instituicao, status, id_categoria, data_adesao, subcategoria)
                                VALUES (?, ?, ?, ?, ?)
                            """
                            run_insert(sql, (nome, status, id_cat, data_final, sub_txt))
                            st.session_state.parceiro_cadastrado = nome  # para feedback pós-save
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro técnico ao salvar: {e}")
                    else:
                        st.warning("O nome da instituição é obrigatório.")

        # Feedback pós-cadastro com próxima ação sugerida
        if st.session_state.get("parceiro_cadastrado"):
            nome_p = st.session_state.pop("parceiro_cadastrado")
            st.success(f"**{nome_p}** cadastrado com sucesso!")
            cf1, cf2 = st.columns(2)
            if cf1.button("Adicionar contato deste parceiro", use_container_width=True, key="post_add_contato"):
                _trigger_quick_add("contato"); st.rerun()
            if cf2.button("Registrar doação deste parceiro", use_container_width=True, key="post_add_doacao"):
                _trigger_quick_add("doacao"); st.rerun()

# --- ABA DE PROJETOS ---
    with tab2:
        
        
        # 1. Query para a TABELA (Filtra 'GERAL' e vazios)
        query_projetos = """
            SELECT
                UPPER(nome_projeto) AS "Projeto",
                TO_CHAR(data_doacao, 'YYYY') AS "Ano",
                COUNT(*) AS "Qtd Repasses",
                SUM(valor_estimado) AS "Total"
            FROM Doacao
            WHERE nome_projeto IS NOT NULL
              AND nome_projeto != ''
              AND UPPER(nome_projeto) != 'GERAL'
            GROUP BY "Projeto", "Ano"
            ORDER BY "Ano" DESC, "Total" DESC
        """
        df_proj = run_query(query_projetos)
        
        # 2. KPIs de projetos
        total_projetos = df_proj['Total'].sum() if not df_proj.empty else 0
        qtd_projetos = df_proj['Projeto'].nunique() if not df_proj.empty else 0

        kpi_row([
            {"label": "Total em projetos",      "value": format_br(total_projetos)},
            {"label": "Projetos executados",    "value": qtd_projetos, "accent": True},
        ])

        section("Detalhamento")

        if not df_proj.empty:
            # Filtro de Ano
            anos_lista = ["Todos"] + sorted(df_proj['Ano'].unique().tolist(), reverse=True)
            ano_escolhido = st.selectbox("Filtrar por ano de recebimento", anos_lista, key="filtro_proj_ano")

            df_exibir = df_proj.copy()
            if ano_escolhido != "Todos":
                df_exibir = df_exibir[df_exibir['Ano'] == ano_escolhido]

            df_exibir_copy = df_exibir.copy()
            df_exibir_copy['Total'] = df_exibir_copy['Total'].apply(format_br)

            st.dataframe(df_exibir_copy, use_container_width=True, hide_index=True)
        else:
            empty_state("—", "Nenhum projeto vinculado", "Doações sem projeto específico aparecem na categoria GERAL.")

    # ============================================================
    # ABA 3 — FUNIL DE CONVERSÃO
    # ============================================================
    with tab3:
        st.markdown("#### Funil de conversão")
        st.caption("Acompanhe o pipeline de prospecção e as conversões recentes para parceiro ativo.")

        df_funil = run_query_cached("""
            SELECT nome_instituicao, status, data_adesao,
                   (CURRENT_DATE - data_adesao::date) AS dias_na_base
            FROM Parceiro
            WHERE data_adesao IS NOT NULL
            ORDER BY data_adesao DESC
        """)

        df_funil_all = run_query_cached("SELECT nome_instituicao, status, data_adesao FROM Parceiro")

        if df_funil_all.empty:
            empty_state("—", "Sem dados", "Cadastre parceiros para visualizar o funil.")
        else:
            s = df_funil_all['status'].fillna("").str.upper().str.strip()
            n_prospec  = int(s.str.contains("PROSPEC").sum())
            n_ativo    = int(s.str.contains("ATIVO").sum())
            n_inativo  = int(s.str.contains("INATIVO").sum())
            total      = len(df_funil_all)
            tx_conv    = round(n_ativo / total * 100, 1) if total > 0 else 0

            # KPIs do funil
            kpi_row([
                {"label": "Em prospecção",      "value": n_prospec},
                {"label": "Convertidos (ativos)","value": n_ativo, "accent": True},
                {"label": "Inativos",           "value": n_inativo},
                {"label": "Taxa de conversão",  "value": f"{tx_conv}%", "hint": "Ativos / Total"},
            ])

            # Barra visual do funil
            st.markdown("<br>", unsafe_allow_html=True)
            for label, valor, cor in [
                ("Prospecção", n_prospec, "#3B82F6"),
                ("Ativo",      n_ativo,   "#059669"),
                ("Inativo",    n_inativo,  "#6B7280"),
            ]:
                pct = round(valor / total * 100, 1) if total > 0 else 0
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">'
                    f'  <span style="width:130px;font-size:13px;">{label}</span>'
                    f'  <div style="flex:1;background:#2D3748;border-radius:6px;height:20px;">'
                    f'    <div style="background:{cor};width:{pct}%;height:20px;border-radius:6px;"></div>'
                    f'  </div>'
                    f'  <span style="width:60px;font-size:13px;color:#888;">{valor} ({pct}%)</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            st.markdown("<br>", unsafe_allow_html=True)
            col_pf, col_pc = st.columns(2)

            with col_pf:
                section("Em prospecção — tempo na fila")
                df_prospec = df_funil[df_funil['status'].str.upper().str.contains("PROSPEC", na=False)].copy()
                if not df_prospec.empty:
                    df_prospec['dias_na_base'] = pd.to_numeric(df_prospec['dias_na_base'], errors='coerce').fillna(0).astype(int)
                    df_prospec = df_prospec.sort_values('dias_na_base', ascending=False)
                    for _, r in df_prospec.iterrows():
                        dias = r['dias_na_base']
                        cor_d = "#DC2626" if dias > 180 else "#D97706" if dias > 90 else "#059669"
                        st.markdown(
                            f'<div style="display:flex;justify-content:space-between;padding:5px 8px;'
                            f'border-left:3px solid {cor_d};margin-bottom:3px;border-radius:0 4px 4px 0;'
                            f'background:rgba(255,255,255,0.02);">'
                            f'  <span style="font-size:13px;">{r["nome_instituicao"]}</span>'
                            f'  <span style="font-size:12px;color:{cor_d};">{dias}d</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                else:
                    st.caption("Nenhum parceiro em prospecção.")

            with col_pc:
                section("Convertidos nos últimos 90 dias")
                df_conv = run_query_cached("""
                    SELECT nome_instituicao, data_adesao,
                           (CURRENT_DATE - data_adesao::date) AS dias_na_base
                    FROM Parceiro
                    WHERE UPPER(status) LIKE '%ATIVO%'
                      AND data_adesao IS NOT NULL
                      AND (CURRENT_DATE - data_adesao::date) <= 90
                    ORDER BY data_adesao DESC
                """)
                if not df_conv.empty:
                    for _, r in df_conv.iterrows():
                        _da = r['data_adesao']
                        _da_fmt = (_da if hasattr(_da, 'strftime') else datetime.strptime(str(_da), '%Y-%m-%d')).strftime('%d/%m/%Y')
                        st.markdown(
                            f'<div style="display:flex;justify-content:space-between;padding:5px 8px;'
                            f'border-left:3px solid #059669;margin-bottom:3px;border-radius:0 4px 4px 0;'
                            f'background:rgba(5,150,105,0.05);">'
                            f'  <span style="font-size:13px;">{r["nome_instituicao"]}</span>'
                            f'  <span style="font-size:12px;color:#059669;">{_da_fmt}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                else:
                    st.caption("Nenhuma conversão nos últimos 90 dias.")

    # ============================================================
    # ABA 4 — IMPORTAÇÃO EM LOTE
    # ============================================================
    with tab4:
        st.markdown("#### Importar parceiros em lote")
        st.caption("Suba uma planilha Excel com múltiplos parceiros para cadastrar de uma vez.")

        st.markdown("""
        **Como usar:**
        1. Baixe o modelo abaixo
        2. Preencha com os dados dos parceiros
        3. Suba o arquivo e confirme a importação
        """)

        # Gera modelo para download
        df_modelo = pd.DataFrame({
            'nome_instituicao': ['Exemplo Empresa S.A.', 'Outra Empresa Ltda'],
            'status':           ['Ativo', 'Prospecção'],
            'subcategoria':     ['Tecnologia', 'Alimentação'],
            'data_adesao':      ['2026-01-15', '2026-03-20'],
        })
        modelo_csv = df_modelo.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "⬇️ Baixar modelo CSV",
            data=modelo_csv,
            file_name="modelo_importacao_parceiros.csv",
            mime="text/csv",
        )

        st.markdown("---")
        arquivo = st.file_uploader("Suba sua planilha (Excel .xlsx ou CSV .csv)", type=["xlsx", "csv"])

        if arquivo is not None:
            try:
                if arquivo.name.endswith('.csv'):
                    df_import = pd.read_csv(arquivo)
                else:
                    df_import = pd.read_excel(arquivo)

                # Valida colunas mínimas
                if 'nome_instituicao' not in df_import.columns:
                    st.error("A coluna **nome_instituicao** é obrigatória na planilha.")
                else:
                    # Preenche defaults
                    df_import['status']       = df_import.get('status',       pd.Series(['Prospecção'] * len(df_import))).fillna('Prospecção')
                    df_import['subcategoria'] = df_import.get('subcategoria', pd.Series([''] * len(df_import))).fillna('')
                    df_import['data_adesao']  = df_import.get('data_adesao',  pd.Series([None] * len(df_import)))

                    # Remove linhas sem nome
                    df_import = df_import[df_import['nome_instituicao'].notna() & (df_import['nome_instituicao'].str.strip() != '')]

                    st.success(f"**{len(df_import)} parceiros** identificados na planilha. Confira antes de importar:")
                    st.dataframe(
                        df_import[['nome_instituicao', 'status', 'subcategoria', 'data_adesao']],
                        use_container_width=True, hide_index=True, height=250
                    )

                    if st.button(f"Confirmar importação de {len(df_import)} parceiros", type="primary", use_container_width=True):
                        # Busca id_categoria padrão (primeira disponível)
                        df_cat_imp = run_query_slow("SELECT id_categoria FROM Categoria_Parceiro LIMIT 1")
                        id_cat_default = int(df_cat_imp['id_categoria'].values[0]) if not df_cat_imp.empty else 1

                        erros = 0
                        ok = 0
                        _erros_detalhe: list[str] = []
                        for _, row in df_import.iterrows():
                            try:
                                _data = None
                                if pd.notna(row['data_adesao']) and str(row['data_adesao']).strip() != '':
                                    try:
                                        _data = pd.to_datetime(row['data_adesao']).strftime('%Y-%m-%d')
                                    except Exception:
                                        _data = None
                                run_exec(
                                    """INSERT INTO Parceiro (nome_instituicao, status, id_categoria, subcategoria, data_adesao)
                                       VALUES (%s, %s, %s, %s, %s)
                                       ON CONFLICT DO NOTHING""",
                                    (str(row['nome_instituicao']).strip(), str(row['status']).strip(),
                                     id_cat_default, str(row['subcategoria']).strip(), _data)
                                )
                                ok += 1
                            except Exception as e:
                                erros += 1
                                _erros_detalhe.append(
                                    f"• {str(row.get('nome_instituicao','?'))[:40]}: {e}"
                                )

                        if ok > 0:
                            st.success(f"**{ok} parceiros importados** com sucesso! {f'({erros} ignorados por erro)' if erros else ''}")
                        if erros > 0:
                            with st.expander(f"{erros} registro(s) com erro — ver detalhes"):
                                st.code("\n".join(_erros_detalhe))
                        if erros > 0 and ok == 0:
                            st.error("Nenhum registro foi importado. Verifique o formato da planilha.")

            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")

# --- 3. REGISTRAR DOAÇÃO ---
elif menu == "Entrada de Recursos":
    page_header("Entrada de recursos", "Ponto único para registrar qualquer captação financeira.")

    df_p = _parceiros_lista()

    if df_p.empty:
        empty_state("—", "Nenhum parceiro cadastrado", "Cadastre um parceiro antes de registrar doações.")
        if st.button("Cadastrar parceiro agora", type="primary", key="doa_go_parc"):
            _trigger_quick_add("parceiro"); st.rerun()
    else:
        # Inicializa estado para edição de registro
        if "doa_edit_id" not in st.session_state:
            st.session_state.doa_edit_id = None

        _tab_idx = 0
        if st.session_state.open_form == "doacao":
            st.session_state.open_form = None
            _tab_idx = 0

        tab_novo, tab_hist, tab_alertas = st.tabs([
            "Registrar nova",
            "Histórico",
            "Doadores recorrentes",
        ])

        # ════════════════════════════════════════════════════════
        # ABA 1 — REGISTRAR NOVA DOAÇÃO
        # ════════════════════════════════════════════════════════
        with tab_novo:
            section("Nova entrada de recurso")

            # ── Passo 1: escolha da categoria ──────────────────
            _FONTES_EVENTO = {
                "Bazar CDP":              "BAZAR_CDP",
                "Bazar RFB (Mercadorias)":"BAZAR_RFB",
                "Bazar RFB (Brinquedos)":"BAZAR_RFB_BRINQUEDOS",
                "Campanha Troco":         "TROCO",
                "Nota Potiguar":          "NOTA_POTIGUAR",
                "Doação On-line (site)":  "DOACAO_ONLINE",
            }
            _CATEGORIAS = {
                "Evento / Campanha (Bazar, Troco, Nota Potiguar, Site)": "evento",
                "Parceria institucional (repasse de empresa)":            "parceria",
                "Projeto / Emenda parlamentar":                           "projeto",
                "Outros":                                                 "outros",
                "Estimada / Midiatica (calhau, espaco de midia, materiais)": "estimada",
            }

            categoria = st.selectbox(
                "Qual é a natureza desta entrada? *",
                list(_CATEGORIAS.keys()),
                help="Isso determina quais campos aparecem e em qual tabela o valor é salvo.",
            )
            tipo_cat = _CATEGORIAS[categoria]

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # ── Passo 2: formulário adaptativo ─────────────────
            if tipo_cat == "evento":
                # → Registro_Captacao_DI (sem parceiro, com mês de referência)
                df_fontes_ev = run_query(
                    "SELECT id_fonte, nome_fonte FROM Meta_Fonte_2026 "
                    "WHERE codigo_fonte = ANY(%s) AND ativa=1 ORDER BY nome_fonte",
                    (list(_FONTES_EVENTO.values()),),
                )
                with st.form("form_entrada_evento", clear_on_submit=True):
                    ea, eb = st.columns(2)
                    _data_repasse = ea.date_input(
                        "Data do repasse *",
                        value=datetime.now().date(),
                        help="Informe o dia exato em que o valor foi repassado.",
                    )
                    mes_lancto = _data_repasse.strftime("%Y-%m-%d")
                    fonte_ev    = eb.selectbox("Evento / Campanha *",
                                               df_fontes_ev['nome_fonte'].tolist() if not df_fontes_ev.empty
                                               else list(_FONTES_EVENTO.keys()))
                    valor_ev    = ea.number_input("Valor realizado (R$) *", min_value=0.0,
                                                  step=100.0, format="%.2f")
                    resp_ev     = eb.text_input("Registrado por",
                                               value=st.session_state.user_data["nome"])
                    obs_ev      = st.text_area("Observação",
                                              placeholder="ex: Bazar CDP realizado em 15/04, 3 dias de evento.")

                    if st.form_submit_button("Registrar entrada", type="primary", use_container_width=True):
                        if valor_ev <= 0:
                            st.warning("Informe um valor maior que zero.")
                        else:
                            _id_fonte = int(df_fontes_ev[df_fontes_ev['nome_fonte'] == fonte_ev]['id_fonte'].values[0])
                            run_exec(
                                """INSERT INTO Registro_Captacao_DI
                                   (id_fonte, mes_referencia, valor_realizado, observacao, registrado_por)
                                   VALUES (%s, %s, %s, %s, %s)""",
                                (_id_fonte, mes_lancto, valor_ev,
                                 obs_ev.upper() if obs_ev else None, resp_ev),
                            )
                            st.success(f"{fonte_ev} — {format_br(valor_ev)} registrado para {mes_lancto}.")
                            st.rerun()

            elif tipo_cat == "estimada":
                # → Doacao com tipo nao-financeiro (nao conta nas metas do Plano DI)
                st.info(
                    "Valores declarados pelos parceiros — espaco de midia, materiais, alimentos etc. "
                    "Sao registrados para controle de impacto e relacionamento, mas **não entram no caixa** "
                    "e **não contam para as metas financeiras** do Plano DI.",
                )
                _tipos_estimado = ["Midiatica", "Vestuario", "Alimentos", "Servicos", "Outros (estimado)"]
                with st.form("form_entrada_estimada", clear_on_submit=True):
                    opcoes_pe = ["Selecione o parceiro..."] + df_p["nome_instituicao"].tolist()
                    se1, se2  = st.columns(2)
                    nome_est  = se1.selectbox("Parceiro / Fonte *", opcoes_pe)
                    tipo_est  = se2.selectbox("Tipo de doacao estimada", _tipos_estimado)
                    valor_est = se1.number_input("Valor estimado declarado (R$) *",
                                                 min_value=0.0, step=100.0, format="%.2f")
                    data_est  = se2.date_input("Data", datetime.now())
                    desc_est  = st.text_area("Descricao do que foi doado",
                                             placeholder="ex: 4 inserções de 30s no Jornal do Meio-Dia, val. est. R$ 8.000")
                    if st.form_submit_button("Registrar estimada", type="primary", use_container_width=True):
                        if nome_est == "Selecione o parceiro...":
                            st.warning("Selecione o parceiro.")
                        elif valor_est <= 0:
                            st.warning("Informe o valor estimado declarado pelo parceiro.")
                        else:
                            id_pe = int(df_p[df_p["nome_instituicao"] == nome_est]["id_parceiro"].values[0])
                            run_insert(
                                """INSERT INTO Doacao (
                                    id_parceiro, valor_estimado, tipo_doacao,
                                    data_doacao, descricao, nome_projeto, origem_captacao
                                ) VALUES (?,?,?,?,?,?,?)""",
                                (id_pe, valor_est, tipo_est,
                                 data_est.strftime("%Y-%m-%d"),
                                 desc_est.upper() if desc_est else "",
                                 "GERAL", "Estimada"),
                            )
                            st.success(f"Registrado: {nome_est} — {format_br(valor_est)} ({tipo_est}). Não conta para metas financeiras.")
                            st.rerun()

            else:
                # → Doacao (com parceiro identificado)
                _tipo_map = {
                    "parceria": ("Financeira",  "Parcerias"),
                    "projeto":  ("Projetos",    "Projetos"),
                    "online":   ("Financeira",  "Doações Online"),
                    "outros":   ("Financeira",  "Outros"),
                }
                tipo_doa, origem_doa = _tipo_map[tipo_cat]

                with st.form("form_entrada_parceiro", clear_on_submit=True):
                    opcoes_p2   = ["Selecione o parceiro..."] + df_p['nome_instituicao'].tolist()
                    pa, pb      = st.columns(2)
                    nome_sel    = pa.selectbox("Parceiro / Fonte *", opcoes_p2)
                    valor_doa   = pb.number_input("Valor (R$) *", min_value=0.0,
                                                  step=100.0, format="%.2f")
                    data_doa    = pa.date_input("Data do recebimento", datetime.now())
                    projeto_doa = pb.text_input("Projeto / Emenda / Finalidade",
                                               placeholder="ex: Projeto Vida")
                    desc_doa    = st.text_area("Observações",
                                              placeholder="Contexto, forma de pagamento, referências…")

                    if st.form_submit_button("Registrar entrada", type="primary", use_container_width=True):
                        if nome_sel == "Selecione o parceiro...":
                            st.warning("Selecione o parceiro.")
                        elif valor_doa <= 0:
                            st.warning("Informe um valor maior que zero.")
                        else:
                            id_p = int(df_p[df_p['nome_instituicao'] == nome_sel]['id_parceiro'].values[0])
                            run_insert(
                                """INSERT INTO Doacao (
                                    id_parceiro, valor_estimado, tipo_doacao,
                                    data_doacao, descricao, nome_projeto, origem_captacao
                                ) VALUES (?,?,?,?,?,?,?)""",
                                (id_p, valor_doa, tipo_doa,
                                 data_doa.strftime('%Y-%m-%d'),
                                 desc_doa.upper() if desc_doa else "",
                                 projeto_doa.upper() if projeto_doa else "GERAL",
                                 origem_doa),
                            )
                            st.success(f"{nome_sel} — {format_br(valor_doa)} registrado com sucesso.")
                            st.rerun()

        # ════════════════════════════════════════════════════════
        # ABA 2 — HISTÓRICO COM BUSCA E EDIÇÃO
        # ════════════════════════════════════════════════════════
        with tab_hist:
            # ── KPIs do período ────────────────────────────────
            df_kpi_doa = run_query_cached("""
                SELECT
                    COUNT(*)                                                   AS total_registros,
                    COALESCE(SUM(CASE WHEN tipo_doacao IN ('Financeira','Projetos')
                                     THEN valor_estimado END), 0)              AS total_financeiro,
                    COALESCE(SUM(valor_estimado), 0)                           AS total_geral,
                    MAX(data_doacao)                                           AS ultima_entrada
                FROM Doacao
                WHERE data_doacao >= (CURRENT_DATE - INTERVAL '365 days')
            """)
            if not df_kpi_doa.empty:
                _r = df_kpi_doa.iloc[0]
                _ult = str(_r['ultima_entrada'])[:10] if _r['ultima_entrada'] else "—"
                kpi_row([
                    {"label": "Registros (12 meses)",   "value": int(_r['total_registros'])},
                    {"label": "Financeiro (12 meses)",  "value": format_br(float(_r['total_financeiro'])), "accent": True},
                    {"label": "Total c/ estimado",      "value": format_br(float(_r['total_geral']))},
                    {"label": "Última entrada",         "value": _ult},
                ])

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            section("Filtros")

            # ── Filtros ────────────────────────────────────────
            fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
            busca_txt   = fc1.text_input("Buscar por parceiro, projeto ou descrição",
                                         placeholder="Digite para filtrar…", label_visibility="collapsed")
            tipo_filtro = fc2.selectbox("Tipo", ["Todos", "Financeira", "Projetos", "Estimado"], label_visibility="collapsed")
            origem_filtro = fc3.selectbox("Origem", ["Todas", "Bazar do Caquito", "Campanha Troco", "Parcerias",
                                                      "Nota Potiguar", "Doações Online", "Projetos", "Troco"],
                                          label_visibility="collapsed")
            periodo = fc4.selectbox("Período", ["Últimos 12 meses", "2026", "2025", "Todos"], label_visibility="collapsed")

            # ── Query base ─────────────────────────────────────
            query_hist = """
                SELECT d.id_doacao, p.nome_instituicao AS parceiro, d.valor_estimado,
                       d.data_doacao, d.nome_projeto, d.descricao, d.tipo_doacao, d.origem_captacao
                FROM Doacao d
                JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
                ORDER BY d.data_doacao DESC
            """
            df_h = run_query_cached(query_hist)

            if not df_h.empty:
                df_h['data_doacao'] = pd.to_datetime(df_h['data_doacao'])

                # Aplica filtros em memória (mais rápido que round-trips ao banco)
                if busca_txt:
                    mask = (
                        df_h['parceiro'].str.contains(busca_txt, case=False, na=False) |
                        df_h['nome_projeto'].str.contains(busca_txt, case=False, na=False) |
                        df_h['descricao'].str.contains(busca_txt, case=False, na=False) |
                        df_h['origem_captacao'].str.contains(busca_txt, case=False, na=False)
                    )
                    df_h = df_h[mask]

                if tipo_filtro == "Estimado":
                    df_h = df_h[~df_h['tipo_doacao'].isin(['Financeira', 'Projetos'])]
                elif tipo_filtro != "Todos":
                    df_h = df_h[df_h['tipo_doacao'] == tipo_filtro]

                if origem_filtro != "Todas":
                    df_h = df_h[df_h['origem_captacao'] == origem_filtro]

                hoje = pd.Timestamp.now()
                if periodo == "Últimos 12 meses":
                    df_h = df_h[df_h['data_doacao'] >= hoje - pd.DateOffset(months=12)]
                elif periodo == "2026":
                    df_h = df_h[df_h['data_doacao'].dt.year == 2026]
                elif periodo == "2025":
                    df_h = df_h[df_h['data_doacao'].dt.year == 2025]

            section("Registros")

            if df_h is not None and not df_h.empty:
                total_filtrado = df_h['valor_estimado'].sum()
                st.caption(f"**{len(df_h)} registros** encontrados · Total: **{format_br(total_filtrado)}**")

                # Tabela limpa
                df_exib = df_h.copy()
                df_exib['data_doacao'] = df_exib['data_doacao'].dt.strftime('%d/%m/%Y')
                df_exib['valor_fmt']   = df_exib['valor_estimado'].apply(format_br)

                sel = st.dataframe(
                    df_exib[['id_doacao', 'data_doacao', 'parceiro', 'valor_fmt',
                              'tipo_doacao', 'nome_projeto', 'origem_captacao', 'descricao']],
                    column_config={
                        "id_doacao":       st.column_config.NumberColumn("ID",         width="small"),
                        "data_doacao":     st.column_config.TextColumn("Data",         width="small"),
                        "parceiro":        st.column_config.TextColumn("Parceiro",     width="medium"),
                        "valor_fmt":       st.column_config.TextColumn("Valor",        width="small"),
                        "tipo_doacao":     st.column_config.TextColumn("Tipo",         width="small"),
                        "nome_projeto":    st.column_config.TextColumn("Projeto"),
                        "origem_captacao": st.column_config.TextColumn("Origem"),
                        "descricao":       st.column_config.TextColumn("Observações"),
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=320,
                )

                # ── Edição por ID ──────────────────────────────
                section("Editar / excluir registro")
                _ids_disp = df_h['id_doacao'].tolist()
                _id_sel = st.number_input(
                    "ID do registro para editar",
                    min_value=1, step=1, value=_ids_disp[0] if _ids_disp else 1,
                    help="Veja o ID na coluna 'ID' da tabela acima.",
                )

                _row_edit = df_h[df_h['id_doacao'] == _id_sel]
                if not _row_edit.empty:
                    row = _row_edit.iloc[0]
                    with st.form(f"edit_doa_{_id_sel}"):
                        st.markdown(
                            f"<span style='font-size:12px;color:var(--ds-text-muted);'>"
                            f"Editando: <strong>{row['parceiro']}</strong> · "
                            f"{row['data_doacao'].strftime('%d/%m/%Y')} · {format_br(row['valor_estimado'])}"
                            f"</span>",
                            unsafe_allow_html=True,
                        )
                        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                        ea, eb, ec = st.columns(3)
                        novo_valor   = ea.number_input("Valor (R$)", value=float(row['valor_estimado']))
                        _dv          = row['data_doacao'].date()
                        nova_data    = eb.date_input("Data", value=_dv)
                        novo_projeto = ec.text_input("Projeto", value=row['nome_projeto'] or "")
                        nova_desc    = st.text_area("Observações", value=row['descricao'] or "")

                        cb1, cb2 = st.columns(2)
                        if cb1.form_submit_button("Salvar alterações", use_container_width=True, type="primary"):
                            run_exec(
                                "UPDATE Doacao SET valor_estimado=%s, data_doacao=%s, nome_projeto=%s, descricao=%s WHERE id_doacao=%s",
                                (novo_valor, str(nova_data), novo_projeto.upper(), nova_desc.upper() if nova_desc else "", int(_id_sel)),
                            )
                            st.success("Registro atualizado com sucesso!")
                            st.rerun()
                        if cb2.form_submit_button("Excluir registro", use_container_width=True):
                            run_exec("DELETE FROM Doacao WHERE id_doacao=%s", (int(_id_sel),))
                            st.warning("Registro excluído.")
                            st.rerun()
                else:
                    st.caption("ID não encontrado nos registros filtrados.")
            else:
                empty_state("—", "Nenhum registro encontrado", "Ajuste os filtros ou registre uma nova entrada na aba ao lado.")

        # ════════════════════════════════════════════════════════
        # ABA 3 — ALERTAS DE RECORRÊNCIA
        # ════════════════════════════════════════════════════════
        with tab_alertas:
            section("Doadores que pararam de contribuir")
            st.caption("Parceiros com histórico financeiro em 2025 que ainda não registraram entrada em 2026.")

            df_inativos = run_query_cached("""
                SELECT
                    p.nome_instituicao                          AS parceiro,
                    p.status,
                    COUNT(DISTINCT EXTRACT(YEAR FROM d25.data_doacao))::INT AS anos_ativo,
                    SUM(d25.valor_estimado)                     AS total_2025,
                    MAX(d25.data_doacao)::DATE                  AS ultima_doacao,
                    (CURRENT_DATE - MAX(d25.data_doacao)::DATE)::INT AS dias_sem_doacao
                FROM Parceiro p
                JOIN Doacao d25
                    ON d25.id_parceiro = p.id_parceiro
                   AND d25.tipo_doacao IN ('Financeira','Projetos')
                   AND EXTRACT(YEAR FROM d25.data_doacao) = 2025
                WHERE p.id_parceiro NOT IN (
                    SELECT DISTINCT id_parceiro FROM Doacao
                    WHERE tipo_doacao IN ('Financeira','Projetos')
                      AND EXTRACT(YEAR FROM data_doacao) = 2026
                )
                GROUP BY p.id_parceiro, p.nome_instituicao, p.status
                ORDER BY total_2025 DESC
            """)

            if df_inativos.empty:
                st.success("Todos os doadores recorrentes de 2025 ja registraram entrada em 2026.")
            else:
                kpi_row([
                    {"label": "Doadores em alerta",       "value": len(df_inativos)},
                    {"label": "Valor em risco (base 2025)",
                     "value": format_br(float(df_inativos['total_2025'].sum()))},
                ])
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                for _, r in df_inativos.iterrows():
                    dias = int(r['dias_sem_doacao']) if r['dias_sem_doacao'] else 999
                    if dias > 180:
                        tom = "danger"
                    elif dias > 90:
                        tom = "warning"
                    else:
                        tom = "info"

                    ultima = str(r['ultima_doacao'])[:10] if r['ultima_doacao'] else "—"
                    action_card(
                        titulo=r['parceiro'],
                        meta_parts=[
                            f"Última entrada: {ultima}",
                            f"{dias} dias sem doação",
                            f"Total 2025: {format_br(float(r['total_2025']))}",
                            f"Status: {r['status'] or 'N/D'}",
                        ],
                        tom=tom,
                        extra_badges=[(f"{dias}d sem entrada", tom)],
                    )

            # ── Doadores mais recorrentes ───────────────────────
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            section("Maiores contribuidores históricos")
            st.caption("Top 10 parceiros por volume financeiro acumulado.")

            df_top = run_query_cached("""
                SELECT
                    p.nome_instituicao                          AS parceiro,
                    COUNT(DISTINCT EXTRACT(YEAR FROM d.data_doacao)) AS anos_ativo,
                    COUNT(*)                                    AS num_entradas,
                    SUM(d.valor_estimado)                       AS total_acumulado,
                    MAX(d.data_doacao)::DATE                    AS ultima_entrada
                FROM Doacao d
                JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
                WHERE d.tipo_doacao IN ('Financeira','Projetos')
                GROUP BY p.id_parceiro, p.nome_instituicao
                ORDER BY total_acumulado DESC
                LIMIT 10
            """)

            if not df_top.empty:
                df_top['total_fmt'] = df_top['total_acumulado'].apply(format_br)
                df_top['ultima_entrada'] = df_top['ultima_entrada'].astype(str).str[:10]
                st.dataframe(
                    df_top[['parceiro', 'anos_ativo', 'num_entradas', 'total_fmt', 'ultima_entrada']],
                    column_config={
                        "parceiro":       st.column_config.TextColumn("Parceiro",          width="large"),
                        "anos_ativo":     st.column_config.NumberColumn("Anos ativo",      width="small"),
                        "num_entradas":   st.column_config.NumberColumn("Entradas",        width="small"),
                        "total_fmt":      st.column_config.TextColumn("Total acumulado",   width="medium"),
                        "ultima_entrada": st.column_config.TextColumn("Última entrada",    width="small"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )

elif menu == "Contatos":
    page_header("Agenda", "Contatos diretos de parceiros, com acesso rápido a WhatsApp e e-mail.")
    st.markdown("Gerencie sua rede de contatos, parceiros e tomadores de decisão.")

    # Busca os dados no banco
    query_view = """
        SELECT c.id_contato, p.nome_instituicao AS "Empresa", c.nome_pessoa AS "Nome",
               c.cargo AS "Cargo", c.telefone AS "WhatsApp", c.email AS "Email"
        FROM Contato_Direto c
        LEFT JOIN Parceiro p ON c.id_parceiro = p.id_parceiro
        ORDER BY c.nome_pessoa ASC
    """
    df_contatos = run_query(query_view)

    # Se veio do botão "+ Novo > Contato", mostra atalho de cadastro no topo
    if st.session_state.open_form == "contato":
        st.session_state.open_form = None  # consome a flag
        st.info("Cadastrando novo contato — preencha os campos abaixo.")
        with st.container(border=True):
            df_p_qa = _parceiros_lista()
            if df_p_qa.empty:
                st.warning("Cadastre um parceiro antes de adicionar contatos.")
                if st.button("Cadastrar parceiro agora", type="primary", key="qa_go_parceiro"):
                    _trigger_quick_add("parceiro"); st.rerun()
            else:
                with st.form("form_qa_contato", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    qa_nome   = col1.text_input("Nome *",            placeholder="ex: João Silva")
                    qa_cargo  = col2.text_input("Cargo/Função",      placeholder="ex: Diretor de Marketing")
                    qa_email  = col1.text_input("E-mail",            placeholder="ex: joao@empresa.com")
                    qa_tel    = col2.text_input("WhatsApp (com DDD) *", placeholder="ex: 84 99999-9999")
                    qa_parc   = st.selectbox("Instituição vinculada *", options=df_p_qa['nome_instituicao'].tolist())
                    if st.form_submit_button("Salvar contato", type="primary", use_container_width=True):
                        if qa_nome and qa_tel:
                            id_p = int(df_p_qa[df_p_qa['nome_instituicao'] == qa_parc]['id_parceiro'].values[0])
                            run_insert(
                                "INSERT INTO Contato_Direto (id_parceiro, nome_pessoa, cargo, telefone, email) VALUES (?, ?, ?, ?, ?)",
                                (id_p, qa_nome, qa_cargo, qa_tel, qa_email)
                            )
                            st.success(f"**{qa_nome}** adicionado à agenda!")
                            st.rerun()
                        else:
                            st.warning("Nome e WhatsApp são obrigatórios.")

    # --- NAVEGAÇÃO POR ABAS (Design Limpo) ---
    tab_lista, tab_novo, tab_gerir = st.tabs(["Contatos", "Adicionar novo", "Gerenciar"])

    # ==========================================
    # ABA 1: VISUALIZAÇÃO ELEGANTE
    # ==========================================
    with tab_lista:
        if not df_contatos.empty:
            kpi_row([
                {"label": "Total de contatos",   "value": len(df_contatos)},
                {"label": "Empresas vinculadas", "value": df_contatos['Empresa'].nunique()},
            ])

            section("Buscar")

            # 2. Barra de Busca
            busca = st.text_input("Buscar contato por nome, empresa ou cargo", placeholder="Digite para filtrar...", label_visibility="collapsed")
            
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

                # 4. Exibição da Tabela com Column Config
                st.dataframe(
                    df_filtrado,
                    column_config={
                        "id_contato": None,
                        "Empresa":    st.column_config.TextColumn("Empresa",      width="medium"),
                        "Nome":       st.column_config.TextColumn("Nome",         width="medium"),
                        "Cargo":      st.column_config.TextColumn("Cargo/Função"),
                        "WhatsApp":   st.column_config.TextColumn("Telefone"),
                        "Ação_WA":    st.column_config.LinkColumn("WhatsApp",     display_text="Abrir conversa"),
                        "Email":      None,
                        "Ação_Email": st.column_config.LinkColumn("E-mail",       display_text="Enviar e-mail"),
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
        section("Cadastrar contato")
        df_p_contatos = _parceiros_lista()

        if not df_p_contatos.empty:
            with st.form("form_novo_contato", clear_on_submit=True, border=False):
                col1, col2 = st.columns(2)
                nome_f  = col1.text_input("Nome *",            placeholder="ex: João Silva")
                cargo_f = col2.text_input("Cargo/Função",      placeholder="ex: Diretor de Marketing")
                email_f = col1.text_input("E-mail",            placeholder="ex: joao@empresa.com")
                tel_f   = col2.text_input("WhatsApp (com DDD) *", placeholder="ex: 84 99999-9999")

                parceiro_nome = st.selectbox("Instituição vinculada *", options=df_p_contatos['nome_instituicao'].tolist())

                submit_btn = st.form_submit_button("Salvar contato", type="primary", use_container_width=True)

                if submit_btn:
                    if nome_f and tel_f:
                        id_p = df_p_contatos[df_p_contatos['nome_instituicao'] == parceiro_nome]['id_parceiro'].values[0]
                        sql = "INSERT INTO Contato_Direto (id_parceiro, nome_pessoa, cargo, telefone, email) VALUES (?, ?, ?, ?, ?)"
                        run_insert(sql, (int(id_p), nome_f, cargo_f, tel_f, email_f))
                        st.success(f"**{nome_f}** adicionado à agenda!")
                        st.rerun()
                    else:
                        st.warning("Nome e WhatsApp são obrigatórios.")
        else:
            st.warning("Cadastre um parceiro primeiro (use o botao NOVO no topo do menu).")

    # ==========================================
    # ABA 3: GERENCIAMENTO DE DADOS (Exclusão)
    # ==========================================
    with tab_gerir:
        section("Gerenciar cadastros")
        if not df_contatos.empty:
            st.write("Selecione um contato abaixo para remover do sistema.")
            
            # Cria uma lista formatada para o selectbox
            opcoes_exclusao = df_contatos.apply(lambda row: f"{row['Nome']} ({row['Empresa']}) - ID: {row['id_contato']}", axis=1).tolist()
            contato_selecionado = st.selectbox("Selecionar contato para exclusão:", [""] + opcoes_exclusao)
            
            if contato_selecionado != "":
                # Extrai o ID do texto do selectbox
                id_para_excluir = int(contato_selecionado.split("ID: ")[-1])
                
                st.error("Atenção: Esta ação não pode ser desfeita.")
                if st.button("Confirmar Exclusão", use_container_width=True):
                    run_insert("DELETE FROM Contato_Direto WHERE id_contato = ?", (id_para_excluir,))
                    st.success("Contato excluído com sucesso!")
                    st.rerun()
        else:
            st.info("Não há contatos para gerenciar.")

# --- COLOQUE ISSO NO FINAL DO ARQUIVO ---
elif menu == "Relacionamento":
    import plotly.graph_objects as go

    # ══════════════════════════════════════════════════════════════
    # SETUP E MIGRAÇÃO
    # ══════════════════════════════════════════════════════════════
    for _col, _tipo in [
        ("tipo_interacao", "TEXT"), ("canal", "TEXT"), ("responsavel", "TEXT")
    ]:
        try:
            run_exec(f"ALTER TABLE Registro_Relacionamento ADD COLUMN IF NOT EXISTS {_col} {_tipo}")
        except Exception as e:
            pass  # coluna já existe ou driver sinalizou IF NOT EXISTS

    try:
        run_exec("ALTER TABLE Parceiro ADD COLUMN IF NOT EXISTS tipo_publico_regua TEXT")
    except Exception as e:
        pass  # coluna já existe ou driver sinalizou IF NOT EXISTS

    run_exec("""
        CREATE TABLE IF NOT EXISTS Regua_Pendencias (
            id            SERIAL PRIMARY KEY,
            id_parceiro   INTEGER REFERENCES Parceiro(id_parceiro) ON DELETE CASCADE,
            tipo_acao     TEXT NOT NULL,
            canal_sugerido TEXT,
            data_sugerida DATE,
            status        TEXT DEFAULT 'PENDENTE',
            gerado_em     TIMESTAMP DEFAULT NOW(),
            feito_em      TIMESTAMP,
            observacao    TEXT
        )
    """)

    run_exec("""
        CREATE TABLE IF NOT EXISTS Regua_Matriz (
            id           SERIAL PRIMARY KEY,
            tipo_publico TEXT NOT NULL,
            acao         TEXT NOT NULL,
            periodo_dias INTEGER,
            canal        TEXT,
            responsavel  TEXT DEFAULT 'DI',
            ativo        BOOLEAN DEFAULT TRUE,
            UNIQUE (tipo_publico, acao)
        )
    """)


    # ── Dados base ────────────────────────────────────────────────────────────
    df_parceiros = run_query_cached(
        "SELECT id_parceiro, nome_instituicao, UPPER(TRIM(status)) AS status_limpo, "
        "data_adesao, tipo_publico_regua FROM Parceiro"
    )
    df_rel = run_query_cached("SELECT * FROM View_Relacionamento_Critico")
    df_interacoes = run_query_cached(
        "SELECT id_registro, id_parceiro, id_contato, data_interacao, "
        "descricao_do_que_foi_feito, proxima_acao_data, tipo_interacao, canal, responsavel "
        "FROM Registro_Relacionamento ORDER BY data_interacao DESC"
    )
    df_doacoes_rel = run_query_cached(
        "SELECT id_parceiro, data_doacao, tipo_doacao, valor_estimado, descricao "
        "FROM Doacao WHERE tipo_doacao IN (\'Financeira\',\'Projetos\') ORDER BY data_doacao DESC"
    )
    df_regua_pend = run_query_cached(
        "SELECT rp.*, p.nome_instituicao FROM Regua_Pendencias rp "
        "JOIN Parceiro p ON rp.id_parceiro = p.id_parceiro "
        "WHERE rp.status = \'PENDENTE\' ORDER BY rp.data_sugerida ASC"
    )

    page_header("Relacionamento", "Registro, automações da régua e histórico de parceiros.")


    hoje = datetime.now().date()
    m_a  = df_parceiros["status_limpo"].str.contains("ATIVO",   na=False)
    m_p  = df_parceiros["status_limpo"].str.contains("PROSPEC", na=False)
    m_i  = df_parceiros["status_limpo"].str.contains("INATIVO", na=False)

    vencidos = 0
    if not df_interacoes.empty and "proxima_acao_data" in df_interacoes.columns:
        _d = pd.to_datetime(df_interacoes["proxima_acao_data"], errors="coerce").dt.date
        vencidos = int((_d < hoje).sum())

    pendencias_regua = len(df_regua_pend) if not df_regua_pend.empty else 0

    kpi_row([
        {"label": "Ativos",              "value": int(m_a.sum()), "accent": True},
        {"label": "Prospecção",          "value": int(m_p.sum())},
        {"label": "Inativos",            "value": int(m_i.sum())},
        {"label": "Follow-ups vencidos", "value": vencidos},
        {"label": "Pendências da régua", "value": pendencias_regua, "hint": "ações da régua não realizadas"},
    ])


    tab_reg, tab_parceiros, tab_followups, tab_regua, tab_relatorio = st.tabs([
        "Registrar", "Parceiros", "Follow-ups", "Régua", "Relatório"
    ])


    with tab_reg:
        _rel_tab_registrar(df_parceiros, df_interacoes)
    with tab_parceiros:
        _rel_tab_parceiros(df_parceiros, hoje)
    with tab_followups:
        _rel_tab_followups(df_regua_pend, hoje)
    with tab_regua:
        _rel_tab_regua()
    with tab_relatorio:
        _rel_tab_relatorio(df_rel)

def _gerar_backup_completo():
    """Gera backup de todas as tabelas como XLSX ou ZIP de CSVs."""
    tabelas = [
        ("Parceiro",               "SELECT * FROM Parceiro"),
        ("Doação",                 "SELECT * FROM Doacao"),
        ("Registro_Relacionamento","SELECT * FROM Registro_Relacionamento"),
        ("Demandas_Estrategicas",  "SELECT * FROM Demandas_Estrategicas"),
        ("Registro_Captacao_DI",   "SELECT * FROM Registro_Captacao_DI"),
        ("Meta_Fonte_2026",        "SELECT * FROM Meta_Fonte_2026"),
        ("Contato_Direto",         "SELECT * FROM Contato_Direto"),
    ]
    try:
        dfs = {nome: run_query(sql) for nome, sql in tabelas}
    except Exception:
        return None

    for engine in ("openpyxl", "xlsxwriter"):
        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine=engine) as writer:
                for nome, df in dfs.items():
                    df.to_excel(writer, index=False, sheet_name=nome[:31])
            return (
                output.getvalue(),
                "xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception:
            continue

    import zipfile
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, df in dfs.items():
            zf.writestr(f"{nome}.csv", df.to_csv(index=False))
    return output.getvalue(), "zip", "application/zip"

if _is_gerente():
    _backup = _gerar_backup_completo()
    if _backup:
        dados, ext, mime = _backup
        hoje = __import__('datetime').date.today().isoformat()
        st.sidebar.download_button(
            label="Baixar backup completo",
            data=dados,
            file_name=f"backup_cdp_{hoje}.{ext}",
            mime=mime,
            use_container_width=True,
        )
