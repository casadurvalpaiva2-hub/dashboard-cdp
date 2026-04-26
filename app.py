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
                if user_login in CONTAS and CONTAS[user_login]["senha"] == pass_login:
                    st.session_state.autenticado = True
                    st.session_state.user_data = CONTAS[user_login]
                    # Tela de transição enquanto o app carrega
                    st.markdown("""
                    <style>
                        [data-testid="stMainBlockContainer"], .block-container { opacity: 0 !important; }
                    </style>
                    <div style="
                        position: fixed; inset: 0; z-index: 9999;
                        background: linear-gradient(135deg, #0f0f0f 0%, #1a0a0a 50%, #0f0f0f 100%);
                        display: flex; flex-direction: column;
                        align-items: center; justify-content: center; gap: 20px;
                    ">
                        <div style="font-size:13px;letter-spacing:4px;color:#C0392B;font-weight:700;">
                            CASA DURVAL PAIVA
                        </div>
                        <div style="font-size:28px;font-weight:800;color:#fff;letter-spacing:-1px;">
                            Sistema DI
                        </div>
                        <div style="
                            width: 40px; height: 40px; margin-top: 12px;
                            border: 3px solid rgba(192,57,43,0.2);
                            border-top-color: #C0392B;
                            border-radius: 50%;
                            animation: spin 0.8s linear infinite;
                        "></div>
                        <style>@keyframes spin { to { transform: rotate(360deg); } }</style>
                    </div>
                    """, unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

        st.markdown('<div class="login-footer">© 2026 · Acesso restrito à equipe autorizada</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # JS: mostra overlay imediatamente no clique em ENTRAR e persiste no rerun
    st.markdown("""
    <div id="cdp-loading-overlay" style="
        display:none; position:fixed; inset:0; z-index:99999;
        background:linear-gradient(135deg,#0f0f0f 0%,#1a0a0a 50%,#0f0f0f 100%);
        flex-direction:column; align-items:center; justify-content:center; gap:16px;
    ">
        <div style="font-size:12px;letter-spacing:4px;color:#C0392B;font-weight:700;">CASA DURVAL PAIVA</div>
        <div style="font-size:26px;font-weight:800;color:#fff;letter-spacing:-1px;">Sistema DI</div>
        <div style="width:36px;height:36px;margin-top:10px;border:3px solid rgba(192,57,43,0.2);
             border-top-color:#C0392B;border-radius:50%;animation:spin .8s linear infinite;"></div>
        <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
    </div>
    <script>
    (function() {
        function attachHandler() {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                if (b.innerText.trim() === 'ENTRAR' && !b._cdpBound) {
                    b._cdpBound = true;
                    b.addEventListener('click', function() {
                        const ov = document.getElementById('cdp-loading-overlay');
                        if (ov) ov.style.display = 'flex';
                    });
                }
            }
        }
        attachHandler();
        const obs = new MutationObserver(attachHandler);
        obs.observe(document.body, {childList:true, subtree:true});
    })();
    </script>
    """, unsafe_allow_html=True)

    st.stop()

# ------------------------------------------------------------
#  CONFIG DA PÁGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Casa Durval Paiva · DI",
    layout="wide",
    page_icon="https://casadurvalpaiva.org.br/wp-content/themes/durvalpaiva/dist/img/header/logo.png",
)


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

# Remove o overlay de loading do login se ainda estiver visível
st.markdown("""
<script>
(function() {
    function removeOverlay() {
        const ov = document.getElementById('cdp-loading-overlay');
        if (ov) { ov.style.opacity='0'; ov.style.transition='opacity .3s'; setTimeout(()=>ov.remove(),300); }
    }
    if (document.readyState === 'complete') removeOverlay();
    else window.addEventListener('load', removeOverlay);
})();
</script>
""", unsafe_allow_html=True)


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
    if "🔴" in situacao or "ATRASAD" in situacao:   return "danger"
    if "🟡" in situacao or "URGENTE" in situacao:   return "warning"
    if "🟢" in situacao or "ESTA SEMANA" in situacao: return "success"
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
st.sidebar.markdown("---")

# ── Navegação — inicialização antecipada para o menu renderizar imediatamente ──
if "current_page" not in st.session_state:
    st.session_state.current_page = "Painel Geral"
if "open_form" not in st.session_state:
    st.session_state.open_form = None
if "_qa_nonce" not in st.session_state:
    st.session_state._qa_nonce = 0

_opcoes_menu = ["Painel Geral", "Plano DI 2026", "Parcerias", "Contatos", "Eventos", "Ações", "Registrar Doação", "Relacionamento"]

def _trigger_quick_add(tipo: str):
    """Navega para a página certa e sinaliza abertura de formulário."""
    mapa_menu = {
        "parceiro": "Parcerias",
        "contato":  "Contatos",
        "doacao":   "Registrar Doação",
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

    # ── Navegação principal ─────────────────────────────────────
    st.markdown("""<p style="font-size:10px;letter-spacing:1.8px;text-transform:uppercase;
    color:rgba(255,255,255,0.25);font-weight:600;margin:20px 0 2px 4px;">Navegação</p>""",
    unsafe_allow_html=True)

    _opcoes_nav = ["Painel Geral", "Plano DI 2026", "Parcerias", "Contatos",
                   "Eventos", "Ações", "Registrar Doação", "Relacionamento"]
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
                        WHEN d.data_prevista IS NULL                        THEN '⚪ SEM PRAZO'
                        WHEN d.data_prevista < CURRENT_DATE                 THEN '🔴 ATRASADA'
                        WHEN (d.data_prevista - CURRENT_DATE) <= 2          THEN '🟡 URGENTE'
                        WHEN (d.data_prevista - CURRENT_DATE) <= 7          THEN '🟢 ESTA SEMANA'
                        ELSE '⚪ FUTURA'
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
                        WHEN t.data_prazo < CURRENT_DATE               THEN '🔴 ATRASADA'
                        WHEN (t.data_prazo - CURRENT_DATE) <= 2        THEN '🟡 URGENTE'
                        WHEN (t.data_prazo - CURRENT_DATE) <= 7        THEN '🟢 ESTA SEMANA'
                        ELSE '⚪ FUTURA'
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
                        WHEN t.data_prazo < CURRENT_DATE               THEN '🔴 ATRASADA'
                        WHEN (t.data_prazo - CURRENT_DATE) <= 2        THEN '🟡 URGENTE'
                        WHEN (t.data_prazo - CURRENT_DATE) <= 7        THEN '🟢 ESTA SEMANA'
                        ELSE '⚪ FUTURA'
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
                        WHEN MAX(r.data_interacao) IS NULL                          THEN '⚫ SEM HISTÓRICO'
                        WHEN (CURRENT_DATE - MAX(r.data_interacao)::date) > 90      THEN '🔴 CRÍTICO (+3 meses)'
                        WHEN (CURRENT_DATE - MAX(r.data_interacao)::date) > 45      THEN '🟡 ATENÇÃO (+45 dias)'
                        ELSE '🟢 EM DIA'
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
                        WHEN COALESCE(SUM(c.valor_realizado),0) >= m.meta_2026          THEN '🟢 ATINGIDO'
                        WHEN COALESCE(SUM(c.valor_realizado),0) / m.meta_2026 >= 0.7    THEN '🟡 EM PROGRESSO'
                        WHEN COALESCE(SUM(c.valor_realizado),0) > 0                     THEN '🟠 ABAIXO DO ESPERADO'
                        ELSE '⚪ SEM REGISTRO'
                    END AS status_meta
                FROM Meta_Fonte_2026 m
                LEFT JOIN (
                    SELECT id_fonte, valor_realizado
                    FROM Registro_Captacao_DI
                    WHERE mes_referencia BETWEEN '2026-01' AND '2026-12'
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





# --- 1. DASHBOARD GERAL ---
if menu == "Painel Geral":
    page_header("Painel geral", "Visão consolidada do Desenvolvimento Institucional.")

    # ============================================================
    # BUSCA DE DADOS TRANSVERSAL (com cache para reduzir latência)
    # ============================================================
    df_doacoes      = run_query_cached("SELECT data_doacao, valor_estimado, tipo_doacao, origem_captacao, id_parceiro FROM Doacao")
    df_parceiros_pg = run_query_cached("SELECT id_parceiro, nome_instituicao, status, data_adesao FROM Parceiro")
    df_acoes_pg     = run_query_cached("SELECT fonte, situacao FROM View_Acoes_Unificadas")
    df_eventos_pg   = run_query_cached("""
        SELECT mes_referencia,
               SUM(CASE WHEN confirmado = TRUE THEN 1 ELSE 0 END) as confirmados,
               COUNT(*) as total
        FROM Convidados_Almoco
        GROUP BY mes_referencia
        ORDER BY mes_referencia DESC
        LIMIT 1
    """)
    df_rel_pg = run_query_cached("SELECT * FROM View_Relacionamento_Critico")

    # ============================================================
    # SELETOR DE ANO
    # ============================================================
    if df_doacoes.empty:
        empty_state("📋", "Nenhum dado cadastrado", "Comece registrando doações, parceiros e eventos.")
    else:
        df_doacoes['data_doacao'] = pd.to_datetime(df_doacoes['data_doacao'])
        anos = sorted(df_doacoes['data_doacao'].dt.year.unique(), reverse=True)
        ano_sel = st.selectbox("Ano de referência", anos, key="pg_ano")

        df_atual  = df_doacoes[df_doacoes['data_doacao'].dt.year == ano_sel]
        df_passado = df_doacoes[df_doacoes['data_doacao'].dt.year == (ano_sel - 1)]

        # Separação crítica: financeiro (entra na conta) vs estimado (mídia/espécie)
        _tipos_fin = ['Financeira', 'Projetos']
        df_fin    = df_atual[df_atual['tipo_doacao'].isin(_tipos_fin)]
        df_est    = df_atual[~df_atual['tipo_doacao'].isin(_tipos_fin)]
        df_fin_pa = df_passado[df_passado['tipo_doacao'].isin(_tipos_fin)]

        total_fin    = df_fin['valor_estimado'].sum()
        total_est    = df_est['valor_estimado'].sum()
        total_fin_pa = df_fin_pa['valor_estimado'].sum()
        qtd_atual    = len(df_atual)
        qtd_passada  = len(df_passado)
        media_fin    = total_fin / len(df_fin) if len(df_fin) > 0 else 0

        # ============================================================
        # BLOCO 1 — ARRECADAÇÃO (somente financeiro — entra na conta)
        # ============================================================
        section("Arrecadação financeira (entra na conta)")

        def _fmt(v): return format_br(v)

        diff_fin = total_fin - total_fin_pa
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Financeiro no ano", _fmt(total_fin),
            delta=(f"{'+' if diff_fin >= 0 else '-'} {_fmt(abs(diff_fin))}" if (ano_sel - 1) in anos else None)
        )
        c2.metric("Registros financeiros", f"{len(df_fin)} un")
        c3.metric("Ticket médio financeiro", _fmt(media_fin))

        col_esq, col_dir = st.columns(2)
        with col_esq:
            st.caption("Captação por tipo")
            if not df_fin.empty:
                dados_cat = (
                    df_fin.groupby('tipo_doacao')['valor_estimado']
                    .sum().sort_values(ascending=False).reset_index()
                )
                dados_cat.columns = ["Tipo", "Valor"]
                # Paleta sequencial: azul mais forte nos maiores valores
                n = len(dados_cat)
                palette = [f"rgba(55,138,221,{0.55 + 0.45*(1-(i/max(n-1,1))):.2f})" for i in range(n)]
                fig_cat = px.bar(
                    dados_cat, x="Tipo", y="Valor",
                    color="Tipo",
                    color_discrete_sequence=palette,
                    text=dados_cat["Valor"].apply(lambda v: f"R$ {v:,.0f}".replace(",",".")),
                )
                fig_cat.update_traces(
                    marker_line_width=0,
                    textposition="outside",
                    textfont=dict(size=10, color="rgba(255,255,255,0.70)"),
                    hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
                    cliponaxis=False,
                )
                _ly = _chart_layout(260)
                _ly["yaxis"]["tickformat"] = ",.0f"
                _ly["yaxis"]["tickprefix"] = "R$ "
                _ly["showlegend"] = False
                fig_cat.update_layout(**_ly)
                st.plotly_chart(fig_cat, use_container_width=True, config={"displayModeBar": False})
            else:
                st.caption("Sem registros financeiros no período.")

        with col_dir:
            st.caption("Evolução mensal")
            if not df_fin.empty:
                df_fin_plot = df_fin.copy()
                df_fin_plot['Mês'] = df_fin_plot['data_doacao'].dt.strftime('%b/%y')
                dados_mes = df_fin_plot.groupby(
                    df_fin_plot['data_doacao'].dt.to_period('M')
                )['valor_estimado'].sum().reset_index()
                dados_mes.columns = ["Período", "Valor"]
                dados_mes["Mês"] = dados_mes["Período"].dt.strftime('%b/%y')
                dados_mes = dados_mes.sort_values("Período")
                fig_mes = go.Figure()
                fig_mes.add_trace(go.Scatter(
                    x=dados_mes["Mês"],
                    y=dados_mes["Valor"],
                    mode="lines+markers",
                    line=dict(color="#378ADD", width=2.5, shape="spline", smoothing=0.8),
                    marker=dict(color="#378ADD", size=6, line=dict(color="rgba(15,17,22,0.95)", width=2)),
                    fill="tozeroy",
                    fillcolor="rgba(55,138,221,0.08)",
                    hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
                ))
                _ly = _chart_layout(260)
                _ly["yaxis"]["tickformat"] = "~s"
                _ly["yaxis"]["tickprefix"] = "R$ "
                fig_mes.update_layout(**_ly)
                st.plotly_chart(fig_mes, use_container_width=True, config={"displayModeBar": False})
            else:
                st.caption("Sem dados financeiros mensais.")

        df_origem_fin = df_fin[df_fin['origem_captacao'].notna() & (df_fin['origem_captacao'] != 'Selecione...')]
        if not df_origem_fin.empty:
            st.caption("Mix por origem")
            dados_orig = (
                df_origem_fin.groupby('origem_captacao')['valor_estimado']
                .sum().sort_values(ascending=True).reset_index()
            )
            dados_orig.columns = ["Origem", "Valor"]
            n2 = len(dados_orig)
            palette2 = [f"rgba(55,138,221,{0.45 + 0.55*(i/max(n2-1,1)):.2f})" for i in range(n2)]
            fig_orig = px.bar(
                dados_orig, x="Valor", y="Origem", orientation='h',
                color="Origem",
                color_discrete_sequence=palette2,
                text=dados_orig["Valor"].apply(lambda v: f"R$ {v:,.0f}".replace(",",".")),
            )
            fig_orig.update_traces(
                marker_line_width=0,
                textposition="outside",
                textfont=dict(size=10, color="rgba(255,255,255,0.70)"),
                hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
                cliponaxis=False,
            )
            _ly2 = _chart_layout(max(180, n2 * 44), margin=dict(l=0, r=80, t=8, b=0))
            _ly2["xaxis"]["tickformat"] = ",.0f"
            _ly2["xaxis"]["tickprefix"] = "R$ "
            _ly2["showlegend"] = False
            fig_orig.update_layout(**_ly2)
            st.plotly_chart(fig_orig, use_container_width=True, config={"displayModeBar": False})

        # Doações estimadas: colapsado, informativo
        if total_est > 0:
            with st.expander(f"Doações estimadas (mídia/espécie) — {_fmt(total_est)} declarados — não entram no caixa"):
                st.caption("Valores declarados pelos parceiros (espaço de mídia, sessões de foto, materiais etc.). Contam para impacto e relacionamento, não para metas financeiras.")
                dados_est = df_est.groupby('tipo_doacao')['valor_estimado'].sum().sort_values(ascending=False).reset_index()
                dados_est.columns = ["Tipo", "Valor"]
                ne = len(dados_est)
                palette_e = [f"rgba(136,135,128,{0.45 + 0.45*(1-(i/max(ne-1,1))):.2f})" for i in range(ne)]
                fig_est = px.bar(
                    dados_est, x="Tipo", y="Valor",
                    color="Tipo", color_discrete_sequence=palette_e,
                    text=dados_est["Valor"].apply(lambda v: f"R$ {v:,.0f}".replace(",",".")),
                )
                fig_est.update_traces(
                    marker_line_width=0,
                    textposition="outside",
                    textfont=dict(size=10, color="rgba(255,255,255,0.60)"),
                    hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
                    cliponaxis=False,
                )
                _lye = _chart_layout(200)
                _lye["showlegend"] = False
                fig_est.update_layout(**_lye)
                st.plotly_chart(fig_est, use_container_width=True, config={"displayModeBar": False})

        # ============================================================
        # BLOCO 2 — PARCEIROS (saúde da base)
        # ============================================================
        section("Parceiros")

        if not df_parceiros_pg.empty:
            s_limpo = df_parceiros_pg['status'].fillna("").str.upper().str.strip()
            ativos    = int(s_limpo.str.contains("ATIVO",   na=False).sum())
            prospec   = int(s_limpo.str.contains("PROSPEC", na=False).sum())
            inativos  = int(s_limpo.str.contains("INATIVO", na=False).sum())

            # Novos parceiros no ano selecionado
            df_parceiros_pg['data_adesao_dt'] = pd.to_datetime(df_parceiros_pg['data_adesao'], errors='coerce')
            novos_ano = int((df_parceiros_pg['data_adesao_dt'].dt.year == ano_sel).sum())

            kpi_row([
                {"label": "Total",        "value": len(df_parceiros_pg)},
                {"label": "Ativos",       "value": ativos, "accent": True},
                {"label": "Prospecção",   "value": prospec},
                {"label": "Inativos",     "value": inativos},
                {"label": f"Novos em {ano_sel}", "value": novos_ano},
            ])
        else:
            st.caption("Nenhum parceiro cadastrado ainda.")

        # ============================================================
        # BLOCO 3 — AÇÕES PENDENTES (operação)
        # ============================================================
        section("Ações pendentes")

        if not df_acoes_pg.empty:
            total_acoes   = len(df_acoes_pg)
            atrasadas_pg  = int((df_acoes_pg['situacao'] == 'ATRASADA').sum())
            urgentes_pg   = int((df_acoes_pg['situacao'] == 'URGENTE').sum())
            n_demandas    = int((df_acoes_pg['fonte'] == 'DEMANDA').sum())
            n_tarefas     = int((df_acoes_pg['fonte'] == 'TAREFA').sum())

            kpi_row([
                {"label": "Total pendente", "value": total_acoes},
                {"label": "Atrasadas",      "value": atrasadas_pg, "accent": atrasadas_pg > 0},
                {"label": "Urgentes",       "value": urgentes_pg},
                {"label": "Operacional",    "value": n_demandas, "hint": "Demandas internas"},
                {"label": "Relacionamento", "value": n_tarefas,  "hint": "Tarefas CRM"},
            ])
        else:
            st.caption("Nenhuma ação pendente.")

        # ============================================================
        # BLOCO 4 — RELACIONAMENTO (saúde da base)
        # ============================================================
        section("Saúde do relacionamento")

        if not df_rel_pg.empty:
            df_rel_pg['Dias_Sem_Contato'] = pd.to_numeric(df_rel_pg['Dias_Sem_Contato'], errors='coerce')

            # Filtra só quem tem histórico
            df_rel_com = df_rel_pg[df_rel_pg['Status_Relacionamento'] != '⚫ SEM HISTÓRICO'].copy()

            em_dia      = int(df_rel_com['Status_Relacionamento'].str.contains("DIA",    na=False, case=False).sum())
            atencao     = int(df_rel_com['Status_Relacionamento'].str.contains("ATEN",   na=False, case=False).sum())
            criticos    = int(df_rel_com['Status_Relacionamento'].str.contains("CRIT",   na=False, case=False).sum())
            sem_hist    = int((df_rel_pg['Status_Relacionamento'] == '⚫ SEM HISTÓRICO').sum())

            kpi_row([
                {"label": "Em dia",            "value": em_dia},
                {"label": "Atenção (+45 dias)","value": atencao,  "accent": atencao > 0},
                {"label": "Crítico (+90 dias)","value": criticos, "accent": criticos > 0},
                {"label": "Sem histórico",     "value": sem_hist, "hint": "Nunca registrado"},
            ])

            # Alertas nominais — mostra quem precisa de ação imediata
            alertas = df_rel_com[df_rel_com['Status_Relacionamento'].str.contains("CRIT|ATEN", na=False)].copy()
            alertas = alertas.sort_values('Dias_Sem_Contato', ascending=False)

            if not alertas.empty:
                st.markdown("<br>", unsafe_allow_html=True)
                for _, a in alertas.iterrows():
                    is_crit = "CRIT" in str(a['Status_Relacionamento'])
                    cor   = "#DC2626" if is_crit else "#D97706"
                    icone = "🔴" if is_crit else "🟡"
                    dias  = int(a['Dias_Sem_Contato']) if pd.notna(a['Dias_Sem_Contato']) else "?"
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;padding:6px 10px;'
                        f'border-left:3px solid {cor};margin-bottom:4px;border-radius:0 6px 6px 0;'
                        f'background:rgba(255,255,255,0.03);">'
                        f'{icone} <span style="flex:1;font-size:14px;">{a["Empresa"]}</span>'
                        f'<span style="font-size:12px;color:#888;">{dias} dias sem contato</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        else:
            st.caption("Sem dados de relacionamento.")

        # ============================================================
        # BLOCO 5 — EVENTOS (almoço do mês)
        # ============================================================
        if not df_eventos_pg.empty:
            section("Eventos do mês")
            ev = df_eventos_pg.iloc[0]
            mes_ev        = ev['mes_referencia']
            confirmados   = int(ev['confirmados'] or 0)
            total_conv    = int(ev['total'] or 0)
            pct = int(100 * confirmados / total_conv) if total_conv > 0 else 0

            kpi_row([
                {"label": f"Convidados ({mes_ev})", "value": total_conv},
                {"label": "Confirmados",             "value": confirmados, "accent": True},
                {"label": "Taxa de confirmação",     "value": f"{pct}%"},
            ])

        # ============================================================
        # BLOCO 6 — RANKING (top doadores)
        # ============================================================
        section("Maiores doadores do ano")
        query_top = """
            SELECT p.nome_instituicao AS "Parceiro", SUM(d.valor_estimado) AS "Total", COUNT(*) AS "Repasses"
            FROM Doacao d
            JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
            WHERE TO_CHAR(d.data_doacao, 'YYYY') = %s
            GROUP BY p.nome_instituicao
            ORDER BY "Total" DESC
            LIMIT 5
        """
        df_top = run_query(query_top, (str(ano_sel),))
        if not df_top.empty:
            df_top['Total'] = df_top['Total'].apply(_fmt)
            st.dataframe(
                df_top,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Parceiro": "Parceiro",
                    "Total":    "Valor total",
                    "Repasses": st.column_config.NumberColumn("Repasses", format="%d"),
                }
            )
        else:
            st.caption("Sem doações registradas para este ano.")

        # ============================================================
        # BLOCO 7 — QUALIDADE DOS DADOS
        # ============================================================
        section("Qualidade dos dados")

        df_qd_sem_contato = run_query_slow("""
            SELECT p.nome_instituicao AS "Parceiro"
            FROM Parceiro p
            WHERE UPPER(p.status) LIKE '%ATIVO%'
              AND NOT EXISTS (SELECT 1 FROM Contato_Direto c WHERE c.id_parceiro = p.id_parceiro)
            ORDER BY p.nome_instituicao
        """)

        df_qd_sem_doacao = run_query_slow("""
            SELECT p.nome_instituicao AS "Parceiro"
            FROM Parceiro p
            WHERE UPPER(p.status) LIKE '%ATIVO%'
              AND NOT EXISTS (
                  SELECT 1 FROM Doacao d
                  WHERE d.id_parceiro = p.id_parceiro
                    AND EXTRACT(YEAR FROM d.data_doacao) = 2026
              )
            ORDER BY p.nome_instituicao
        """)

        df_qd_sem_interacao = run_query_slow("""
            SELECT p.nome_instituicao AS "Parceiro"
            FROM Parceiro p
            WHERE UPPER(p.status) LIKE '%ATIVO%'
              AND NOT EXISTS (SELECT 1 FROM Registro_Relacionamento r WHERE r.id_parceiro = p.id_parceiro)
            ORDER BY p.nome_instituicao
        """)

        df_qd_sem_tipo = run_query_slow("""
            SELECT p.nome_instituicao AS "Parceiro",
                   TO_CHAR(d.data_doacao, 'DD/MM/YYYY') AS "Data",
                   d.valor_estimado AS "Valor"
            FROM Doacao d
            JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
            WHERE EXTRACT(YEAR FROM d.data_doacao) = 2026
              AND (d.tipo_doacao IS NULL OR d.tipo_doacao = '' OR d.tipo_doacao = 'Selecione...')
            ORDER BY d.data_doacao DESC
        """)

        # ── Cartões de pendência ──────────────────────────────────────────────
        _checks = [
            {
                "icone": "",
                "titulo": "Doações de 2026 não registradas",
                "acao": "Vá em Registrar Doação e lance os repasses pendentes.",
                "impacto": "Alta — afeta diretamente as metas do Plano DI",
                "cor": "#E31D24",
                "df": df_qd_sem_doacao,
                "tipo": "lista",
            },
            {
                "icone": "",
                "titulo": "Doações sem tipo definido",
                "acao": "Abra cada doação e defina se é Financeira, Mídia, Projetos etc.",
                "impacto": "Alta — distorce o cálculo das metas",
                "cor": "#E31D24",
                "df": df_qd_sem_tipo,
                "tipo": "tabela",
            },
            {
                "icone": "",
                "titulo": "Parceiros sem contato cadastrado",
                "acao": "Vá em Contatos e cadastre ao menos uma pessoa de referência.",
                "impacto": "Média — dificulta o follow-up e o relacionamento",
                "cor": "#D97706",
                "df": df_qd_sem_contato,
                "tipo": "lista",
            },
            {
                "icone": "",
                "titulo": "Parceiros sem nenhuma interação",
                "acao": "Registre a primeira interação pelo sidebar ou pela aba Relacionamento.",
                "impacto": "Média — parceiro ativo sem histórico é invisível para o sistema",
                "cor": "#D97706",
                "df": df_qd_sem_interacao,
                "tipo": "lista",
            },
        ]

        _com_pend = [c for c in _checks if not c["df"].empty]
        _total_cats = len(_com_pend)

        if _total_cats == 0:
            st.markdown(
                '<div style="padding:12px 16px;background:rgba(34,197,94,0.1);'
                'border-left:3px solid #22C55E;border-radius:0 8px 8px 0;font-size:14px;">'
                '✅ <strong>Banco de dados completo.</strong> Todos os campos críticos estão preenchidos.</div>',
                unsafe_allow_html=True
            )
        else:
            # Score de completude
            _score = round((4 - _total_cats) / 4 * 100)
            st.markdown(
                f'<div style="margin-bottom:16px;padding:12px 16px;background:rgba(255,255,255,0.03);'
                f'border-radius:8px;border:1px solid rgba(255,255,255,0.07);">'
                f'<div style="font-size:13px;color:#888;margin-bottom:6px;">Completude do banco de dados</div>'
                f'<div style="display:flex;align-items:center;gap:12px;">'
                f'<div style="flex:1;height:8px;background:rgba(255,255,255,0.1);border-radius:4px;">'
                f'<div style="width:{_score}%;height:100%;background:#22C55E;border-radius:4px;"></div></div>'
                f'<span style="font-size:16px;font-weight:700;color:#fff;">{_score}%</span></div>'
                f'<div style="font-size:12px;color:#888;margin-top:6px;">'
                f'{_total_cats} categoria(s) com pendências — priorize as de impacto alto primeiro.</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            for _chk in _com_pend:
                _n = len(_chk["df"])
                _label = f"{_chk['titulo']} — {_n} {'registro' if _n == 1 else 'registros'}"
                with st.expander(_label):
                    _c1, _c2 = st.columns([1, 1])
                    with _c1:
                        st.markdown(f"**O que fazer:** {_chk['acao']}")
                    with _c2:
                        st.markdown(
                            f'<div style="font-size:12px;padding:4px 10px;border-radius:4px;'
                            f'background:rgba(255,255,255,0.05);color:{_chk["cor"]};">'
                            f'Impacto: {_chk["impacto"]}</div>',
                            unsafe_allow_html=True
                        )
                    st.divider()
                    if _chk["tipo"] == "tabela":
                        st.dataframe(
                            _chk["df"], hide_index=True, use_container_width=True,
                            column_config={"Valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f")}
                        )
                    else:
                        # Mostra os primeiros 15, com aviso se houver mais
                        _lista = _chk["df"]["Parceiro"].tolist()
                        _cols = st.columns(2)
                        _metade = (len(_lista[:15]) + 1) // 2
                        for _i, _nome in enumerate(_lista[:15]):
                            _cols[_i // _metade].markdown(f"• {_nome}")
                        if _n > 15:
                            st.caption(f"… e mais {_n - 15} registros. Exporte a lista completa pelo relatório PDF.")


elif menu == "Plano DI 2026":
    page_header("Plano de Ação DI 2026", "Metas × Realizado por fonte de captação — monitoramento financeiro.")

    eh_gerente_plano = st.session_state.user_data["perfil"] == "gerencia"

    # ── Dados base ──────────────────────────────────────────────────────────
    df_prog = run_query("SELECT * FROM View_Progresso_PlanoAnual ORDER BY meta_2026 DESC")
    df_hist = run_query("""
        SELECT rc.mes_referencia, mf.nome_fonte, rc.valor_realizado,
               rc.observacao, rc.registrado_por, rc.data_registro
        FROM Registro_Captacao_DI rc
        JOIN Meta_Fonte_2026 mf ON rc.id_fonte = mf.id_fonte
        ORDER BY rc.mes_referencia DESC, mf.nome_fonte
    """)

    # ── KPIs globais ────────────────────────────────────────────────────────
    if not df_prog.empty:
        meta_total     = df_prog['meta_2026'].sum()
        captado_total  = df_prog['captado_2026'].sum()
        saldo_total    = meta_total - captado_total
        pct_geral      = round(captado_total / meta_total * 100, 1) if meta_total > 0 else 0
        fontes_ok      = int((df_prog['status_meta'].str.contains("🟢", na=False)).sum())
        fontes_risco   = int((df_prog['status_meta'].str.contains("⚪", na=False)).sum())

        kpi_row([
            {"label": "Meta total anual DI",    "value": format_br(meta_total)},
            {"label": "Captado em 2026",         "value": format_br(captado_total), "accent": captado_total > 0},
            {"label": "% da meta",               "value": f"{pct_geral}%"},
            {"label": "Saldo a captar",          "value": format_br(saldo_total)},
            {"label": "Fontes sem registro",     "value": fontes_risco, "hint": "Precisam de lançamento"},
        ])

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Barra de progresso global ────────────────────────────────────
        st.markdown(
            f'<div style="font-size:13px;color:#555;margin-bottom:4px;">Progresso geral: <b>{pct_geral}%</b> da meta anual</div>',
            unsafe_allow_html=True
        )
        st.progress(min(pct_geral / 100, 1.0))

        # ── Progresso por fonte ─────────────────────────────────────────
        section("Progresso por fonte de captação")

        # Mês atual para calcular pró-rata
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

            # Cor da barra por status
            if "🟢" in status:
                cor_bar = "#059669"
            elif "🟡" in status:
                cor_bar = "#D97706"
            elif "🟠" in status:
                cor_bar = "#EA580C"
            else:
                cor_bar = "#94A3B8"

            # Badge pró-rata: no prazo / em risco / atrasado
            if captado == 0:
                badge_txt, badge_cor = "⚪ Sem registro", "#94A3B8"
            elif pct_prorate >= 100:
                badge_txt, badge_cor = "✅ No prazo", "#059669"
            elif pct_prorate >= 70:
                badge_txt, badge_cor = "⚠️ Em risco", "#D97706"
            else:
                badge_txt, badge_cor = "🔴 Atrasado", "#DC2626"

            barra_val   = min(pct / 100, 1.0)
            prorata_pct = min(prorate / meta, 1.0) if meta > 0 else 0

            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2px;">'
                f'  <span style="font-size:14px;font-weight:600;">{nome}</span>'
                f'  <span style="font-size:12px;font-weight:700;color:{badge_cor};">{badge_txt}</span>'
                f'</div>'
                # Barra de progresso com marcador pró-rata
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
        st.info("Nenhuma fonte de captação cadastrada. Execute o setup do banco para popular Meta_Fonte_2026.")

    # ── Formulário de lançamento mensal ─────────────────────────────────────
    section("Lançar realizado mensal")

    df_fontes = run_query("SELECT id_fonte, nome_fonte, codigo_fonte FROM Meta_Fonte_2026 WHERE ativa=1 ORDER BY nome_fonte")

    if df_fontes.empty:
        st.warning("Nenhuma fonte ativa cadastrada.")
    else:
        with st.form("form_captacao_mensal", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                # Gera lista de meses 2026
                meses_2026 = [f"2026-{str(m).zfill(2)}" for m in range(1, 13)]
                mes_lancto = col_a.selectbox("Mês de referência *", meses_2026,
                    index=min(datetime.now().month - 1, 11))
                fonte_nome = col_a.selectbox("Fonte de captação *",
                    df_fontes['nome_fonte'].tolist())
            with col_b:
                valor_lancto = col_b.number_input(
                    "Valor realizado (R$) — somente financeiro *",
                    min_value=0.0, step=100.0, format="%.2f",
                    help="Informe apenas o valor que efetivamente entrou na conta. Doações midiáticas/estimadas NÃO entram aqui."
                )
                resp_lancto = col_b.text_input("Registrado por", value=st.session_state.user_data["nome"])

            obs_lancto = st.text_area("Observação", placeholder="ex: Bazar CDP realizado em 15/04, 3 dias de evento.")

            submitted_lancto = st.form_submit_button("Registrar realizado", type="primary", use_container_width=True)
            if submitted_lancto:
                if valor_lancto <= 0:
                    st.warning("Informe um valor maior que zero.")
                else:
                    id_fonte_sel = df_fontes[df_fontes['nome_fonte'] == fonte_nome]['id_fonte'].values[0]
                    run_exec(
                        """INSERT INTO Registro_Captacao_DI
                           (id_fonte, mes_referencia, valor_realizado, observacao, registrado_por)
                           VALUES (?, ?, ?, ?, ?)""",
                        (int(id_fonte_sel), mes_lancto, valor_lancto,
                         obs_lancto.upper() if obs_lancto else None, resp_lancto)
                    )
                    st.success(f"✅ {fonte_nome} — {format_br(valor_lancto)} registrado para {mes_lancto}.")
                    st.rerun()

    # ── Histórico de lançamentos ─────────────────────────────────────────────
    if not df_hist.empty:
        section("Histórico de lançamentos")

        # Totais por fonte
        df_resumo = df_hist.groupby('nome_fonte')['valor_realizado'].sum().reset_index()
        df_resumo.columns = ['Fonte', 'Total Registrado']
        df_resumo['Total Registrado'] = df_resumo['Total Registrado'].apply(format_br)
        st.dataframe(df_resumo, use_container_width=True, hide_index=True)

        with st.expander("Ver todos os lançamentos"):
            df_hist_exib = df_hist.copy()
            df_hist_exib['valor_realizado'] = df_hist_exib['valor_realizado'].apply(format_br)
            df_hist_exib.columns = ['Mês', 'Fonte', 'Valor', 'Observação', 'Registrado por', 'Data registro']
            st.dataframe(df_hist_exib, use_container_width=True, hide_index=True)

        # Permite exclusão (apenas gerência)
        if eh_gerente_plano:
            df_hist_del = run_query("""
                SELECT rc.id, mf.nome_fonte, rc.mes_referencia, rc.valor_realizado
                FROM Registro_Captacao_DI rc
                JOIN Meta_Fonte_2026 mf ON rc.id_fonte = mf.id_fonte
                ORDER BY rc.id DESC LIMIT 20
            """)
            if not df_hist_del.empty:
                with st.expander("🗑 Excluir lançamento incorreto (gerência)"):
                    opcoes_del = {
                        f"#{r['id']} — {r['nome_fonte']} / {r['mes_referencia']} — {format_br(r['valor_realizado'])}": r['id']
                        for _, r in df_hist_del.iterrows()
                    }
                    sel_del = st.selectbox("Selecione o lançamento para excluir:", list(opcoes_del.keys()))
                    if st.button("Confirmar exclusão", type="secondary"):
                        run_exec("DELETE FROM Registro_Captacao_DI WHERE id = ?", (opcoes_del[sel_del],))
                        st.success("Lançamento excluído.")
                        st.rerun()
    else:
        st.info("Nenhum lançamento registrado ainda. Use o formulário acima para registrar os realizados mensais.")


elif menu == "Ações":
    user = st.session_state.user_data
    eh_gerente = user["perfil"] == "gerencia"
    meu_setor = user["setor"]
    meu_nome = user["nome"]

    page_header("Centro de ações", "Tudo que está pendente — operação interna e relacionamento.")

    tab_mim, tab_op, tab_rel = st.tabs(["Pra mim", "Planejamento operacional", "Relacionamento"])

    # ========== ABA 1: PRA MIM (inbox unificado) ==========
    with tab_mim:
        # Busca tudo da view unificada
        df_acoes = run_query("SELECT * FROM View_Acoes_Unificadas")

        if df_acoes.empty:
            empty_state("🎉", "Tudo em dia!", "Nenhuma ação pendente no momento.")
        else:
            # Filtrar o que é MEU: setor bate OU responsavel bate OU gerência vê tudo
            if eh_gerente:
                df_mim = df_acoes.copy()
            else:
                mask_setor = df_acoes["setor"] == meu_setor
                mask_resp  = df_acoes["responsavel"] == meu_nome
                mask_livre = df_acoes["responsavel"].isna() & df_acoes["setor"].isna()
                df_mim = df_acoes[mask_setor | mask_resp | mask_livre].copy()

            # Ordenar por prioridade real: situação + score
            ordem_sit = {"🔴 ATRASADA": 1, "🟡 URGENTE": 2, "🟢 ESTA SEMANA": 3, "⚪ FUTURA": 4, "⚪ SEM PRAZO": 5}
            df_mim["_ord"] = df_mim["situacao"].map(ordem_sit).fillna(9)
            df_mim = df_mim.sort_values(by=["_ord", "score"], ascending=[True, False])

            # KPIs — via Design System
            n_atrasadas = int((df_mim["situacao"] == "🔴 ATRASADA").sum())
            kpi_row([
                {"label": "Total",        "value": len(df_mim)},
                {"label": "Atrasadas",    "value": n_atrasadas, "accent": n_atrasadas > 0},
                {"label": "Urgentes",     "value": int((df_mim["situacao"] == "🟡 URGENTE").sum())},
                {"label": "Esta semana",  "value": int((df_mim["situacao"] == "🟢 ESTA SEMANA").sum())},
            ])

            section("Filtrar")
            fc1, fc2 = st.columns(2)
            fonte_fil = fc1.selectbox("Tipo",     ["TODOS", "DEMANDA", "TAREFA"], key="mim_fonte")
            sit_fil   = fc2.selectbox("Situação", ["TODAS"] + list(ordem_sit.keys()), key="mim_sit")

            df_view = df_mim.copy()
            if fonte_fil != "TODOS":
                df_view = df_view[df_view["fonte"] == fonte_fil]
            if sit_fil != "TODAS":
                df_view = df_view[df_view["situacao"] == sit_fil]

            section(f"Ações ({len(df_view)})")

            if df_view.empty:
                empty_state("✨", "Nada aqui", "Nenhuma ação corresponde aos filtros.")
            else:
                # Lista com action_card do DS + botão de ação na coluna lateral
                for _, a in df_view.iterrows():
                    ci, cb = st.columns([6, 1])
                    with ci:
                        tom = situacao_to_tom(a["situacao"])
                        extra = [(a["fonte"], "accent" if a["fonte"] == "DEMANDA" else "info")]

                        meta_parts = []
                        if pd.notna(a["data_prazo"]) and a["data_prazo"]:
                            meta_parts.append(f"📅 <strong>{a['data_prazo']}</strong>")
                        if pd.notna(a["setor"]) and a["setor"]:
                            meta_parts.append(f"🏷️ {a['setor']}")
                        if pd.notna(a["responsavel"]) and a["responsavel"]:
                            meta_parts.append(f"👤 {a['responsavel']}")
                        if pd.notna(a["parceiro"]) and a["parceiro"]:
                            meta_parts.append(f"🏢 {a['parceiro']}")
                        meta_parts.append(f"{int(a['score'])} pts")

                        action_card(
                            titulo=a["titulo"],
                            meta_parts=meta_parts,
                            tom=tom,
                            situacao_badge=a["situacao"],
                            extra_badges=extra,
                        )
                    with cb:
                        st.write("")  # spacer para alinhar verticalmente
                        if st.button("✅ Concluir", key=f"mim_ok_{a['id_uniforme']}", use_container_width=True):
                            real_id = int(a["id_uniforme"][1:])
                            if a["fonte"] == "DEMANDA":
                                run_insert("UPDATE Demandas_Estrategicas SET status='REALIZADO', data_ultima_conclusao=CURRENT_TIMESTAMP WHERE id=?", (real_id,))
                            else:
                                run_insert("UPDATE Tarefas_Pendentes SET status='CONCLUIDA', data_conclusao=? WHERE id_tarefa=?",
                                           (datetime.now().strftime("%Y-%m-%d"), real_id))
                            st.toast("Concluído"); st.rerun()

    # ========== ABA 2: PLANEJAMENTO OPERACIONAL (DEMANDAS) ==========
    with tab_op:
        # Captura dados do usuário logado
        user = st.session_state.user_data
        eh_gerente = user['perfil'] == 'gerencia'
        meu_setor = user['setor']

        # --- LÓGICA DE TAREFAS DIÁRIAS (RESET) ---
        # Se a tarefa for diária e foi concluída em um dia anterior, volta para PENDENTE
        run_insert("""
            UPDATE Demandas_Estrategicas
            SET status = 'PENDENTE'
            WHERE is_diaria = 1
              AND status = 'REALIZADO'
              AND data_ultima_conclusao::date < CURRENT_DATE
        """)

        # 1. DEFINIÇÃO DOS DADOS (PITs)
        dados_equipe = {
            "MARKETING DIGITAL": {"Produção de Peças Avulsas": 2, "Edição de Vídeo/Reels": 3, "Gestão de Redes Sociais": 1, "Campanha Google Ads": 5, "Atualização de Site": 2},
            "IMPRENSA": {"Redação de Release": 3, "Clipping de Projetos": 7, "Agendamento de Pauta": 2, "Artigos Institucionais": 5, "Boletim Informativo": 2},
            "PROJETOS": {"Escrita de Novo Edital": 15, "Relatório de Prestação de Contas": 10, "Pesquisa de Editais": 5, "Inscrição em Prêmios": 7},
            "GERÊNCIA": {"Manutenção de Parcerias": 7, "Análise de Relatórios": 2, "Planejamento Anual": 30, "Gestão de Equipe": 2}
        }

        # CSS das métricas e task-card já está no CSS_GLOBAL (topo do arquivo)

        # 3. DASHBOARD FILTRADO
        def contar_status_filtrado(status_nome):
            try:
                sql = f"SELECT COUNT(*) as total FROM Demandas_Estrategicas WHERE status = '{status_nome}'"
                if not eh_gerente: sql += f" AND setor = '{meu_setor}'"
                res = run_query(sql)
                return res.iloc[0]['total'] if not res.empty else 0
            except: return 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Pendentes", contar_status_filtrado('PENDENTE'))
        c2.metric("Com barreira", contar_status_filtrado('BLOQUEADO'), delta_color="inverse")
        c3.metric("Concluídas", contar_status_filtrado('REALIZADO'))

        st.divider()

        # 4. FORMULÁRIO DE CADASTRO
        with st.expander("**NOVA SOLICITAÇÃO**", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                setor_opcoes = list(dados_equipe.keys())
                setor_sel = st.selectbox("Setor responsável:", setor_opcoes, index=setor_opcoes.index(meu_setor) if meu_setor in setor_opcoes else 0, disabled=not eh_gerente)
                solicitante = st.text_input("SOLICITANTE", value=user['nome'])
                data_p = st.date_input("Data prevista (Prazo):", datetime.now())
            with col_b:
                tarefa_sel = st.selectbox("O que precisa ser feito?", list(dados_equipe[setor_sel].keys()))
                detalhes = st.text_input("Complemento/Descrição:")
                nomes_equipe = [c["nome"] for c in CONTAS.values() if c["setor"] == setor_sel]
                resp_opcoes = ["-- A definir --"] + sorted(nomes_equipe)
                responsavel_sel = st.selectbox("Responsável direto (pessoa):", resp_opcoes)
                is_diaria = st.checkbox("Tarefa diária")

            st.write("**Prioridade (GUT):**")
            g1, u1, t1 = st.columns(3)
            g = g1.select_slider("Gravidade", [1,2,3,4,5], 3, key="g_d")
            u = u1.select_slider("Urgência", [1,2,3,4,5], 3, key="u_d")
            t = t1.select_slider("Tendência", [1,2,3,4,5], 3, key="t_d")

            if st.button("Lançar demanda", use_container_width=True):
                score = g * u * t
                resp_final = None if responsavel_sel == "-- A definir --" else responsavel_sel
                sql = """INSERT INTO Demandas_Estrategicas 
                         (tarefa, setor, gravidade, urgencia, tendencia, score_gut, status, data_prevista, is_diaria, responsavel) 
                         VALUES (?,?,?,?,?,?,'PENDENTE',?,?,?)"""
                run_insert(sql, (f"[{tarefa_sel}] {detalhes} | POR: {solicitante}".upper(), 
                                setor_sel, g, u, t, score, data_p.strftime('%Y-%m-%d'), 1 if is_diaria else 0, resp_final))
                st.success("Registrado!"); st.rerun()

        # 5. FILA DE TRABALHO COMPACTA
        section("Fila de trabalho")
    
        query_sql = "SELECT * FROM Demandas_Estrategicas WHERE status IN ('PENDENTE', 'BLOQUEADO')"
        params = []
        if not eh_gerente:
            query_sql += " AND setor = ?"
            params.append(meu_setor)
    
        demandas = run_query(query_sql + " ORDER BY status DESC, score_gut DESC", tuple(params))

        if not demandas.empty:
            for _, row in demandas.iterrows():
                is_b = row['status'] == 'BLOQUEADO'
                cor = "#7030a0" if is_b else ("#FF4B4B" if row['score_gut'] >= 80 else "#FFA500" if row['score_gut'] >= 40 else "#28A745")
            
                with st.container():
                    # NOVIDADE: 3 colunas perfeitamente alinhadas ao centro (requer Streamlit atualizado)
                    col_chk, col_info, col_acao = st.columns([0.5, 7.5, 2], vertical_alignment="center")
                
                    with col_chk:
                        marcar_feito = st.checkbox("", key=f"chk_{row['id']}", help="Marcar como concluída")
                        if marcar_feito:
                            run_insert("UPDATE Demandas_Estrategicas SET status = 'REALIZADO', data_ultima_conclusao = CURRENT_TIMESTAMP WHERE id = ?", (row['id'],))
                            st.toast("Tarefa concluída ✅!")
                            st.rerun()
                
                    with col_info:
                        _dc = row['data_criacao']
                        dt_cad = (_dc if hasattr(_dc, 'strftime') else datetime.strptime(str(_dc), '%Y-%m-%d %H:%M:%S')).strftime('%d/%m')
                        dt_prev = row['data_prevista'] if row['data_prevista'] else "---"
                        tag_d = '<span class="tag-diaria">DIÁRIA</span>' if row['is_diaria'] else ""
                        prefixo = '🚨 <b style="color:#FF4B4B;">[BLOQUEADO]</b> ' if is_b else ''
                    
                        st.markdown(f"""
                            <div class="task-card" style="border-left-color: {cor};">
                                <div class="task-title">{prefixo}{row['tarefa']} {tag_d}</div>
                                <div class="task-meta">Cadastrada: {dt_cad} | <b>Prazo: {dt_prev}</b> | Setor: {row['setor']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                
                    with col_acao:
                        # Pontuação e botão agrupados na direita
                        st.markdown(f"<div style='text-align:center; font-size:15px; font-weight:bold; margin-bottom:5px;'>{row['score_gut']} pts</div>", unsafe_allow_html=True)
                    
                        label_btn = "Liberar" if is_b else "Pedir ajuda"
                        tipo_btn = "primary" if is_b else "secondary"
                    
                        if st.button(label_btn, key=f"btn_{row['id']}", type=tipo_btn, use_container_width=True):
                            novo_st = 'PENDENTE' if is_b else 'BLOQUEADO'
                            run_insert("UPDATE Demandas_Estrategicas SET status = ? WHERE id = ?", (novo_st, row['id']))
                            st.rerun()
            
                st.write("") # Dá um pequeno respiro invisível entre uma linha e outra
        else:
            st.info("Nenhuma demanda pendente para o seu setor no momento.")

        # 6. HISTÓRICO
        with st.expander("Realizadas"):
            sql_hist = "SELECT tarefa, data_ultima_conclusao as 'Concluído em' FROM Demandas_Estrategicas WHERE status = 'REALIZADO'"
            if not eh_gerente: sql_hist += f" AND setor = '{meu_setor}'"
            hist = run_query(sql_hist + " ORDER BY data_ultima_conclusao DESC LIMIT 10")
            st.table(hist)

        # 7. ESTATÍSTICAS DE PRODUTIVIDADE (O toque final elegante)
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()
    
        # Título sutil
        st.markdown("<p style='opacity:0.5; font-size:11px; text-align:center; letter-spacing:2px;'>MÉTRICAS DE ENTREGA MENSAL</p>", unsafe_allow_html=True)
    
        # Query para contar tarefas realizadas por mês/ano
        # Filtramos por setor se o usuário não for gerente
        sql_stats = """
            SELECT TO_CHAR(data_ultima_conclusao, 'MM/YYYY') AS "MesAno", COUNT(*) AS "Total"
            FROM Demandas_Estrategicas
            WHERE status = 'REALIZADO'
              AND data_ultima_conclusao IS NOT NULL
        """
        if not eh_gerente:
            sql_stats += f" AND setor = '{meu_setor}'"
    
        sql_stats += " GROUP BY MesAno ORDER BY data_ultima_conclusao DESC LIMIT 6"
    
        df_stats = run_query(sql_stats)
    
        if not df_stats.empty:
            # Criamos colunas dinâmicas para as estatísticas
            num_stats = len(df_stats)
            cols_stats = st.columns(num_stats)
        
            for i, row in df_stats.iterrows():
                with cols_stats[i]:
                    # Estilo de mini-card minimalista
                    st.markdown(f"""
                        <div style="text-align:center; padding: 5px; border-left: 1px solid rgba(255,255,255,0.1);">
                            <div style="font-size:10px; opacity:0.6; text-transform: uppercase;">{row['MesAno']}</div>
                            <div style="font-size:22px; font-weight:800; color:#28A745; margin: -5px 0;">{row['Total']}</div>
                            <div style="font-size:9px; opacity:0.4;">TAREFAS FEITAS</div>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("<p style='opacity:0.4; font-size:10px; text-align:center;'>Ainda não há dados de conclusão para gerar estatísticas.</p>", unsafe_allow_html=True)
        


    # ========== ABA 3: RELACIONAMENTO (CRM) ==========
    with tab_rel:
        section("Tarefas de CRM pendentes")
        st.caption("Agradecimentos, follow-ups e ações que precisam ser feitas.")

        # Buscar todas as tarefas abertas
        df_tarefas = run_query("SELECT * FROM View_Tarefas_Abertas")

        if df_tarefas.empty:
            empty_state("✨", "Nenhuma tarefa pendente", "Nenhum follow-up nem agradecimento em aberto.")
        else:
            total     = len(df_tarefas)
            atrasadas = len(df_tarefas[df_tarefas['Situacao'].str.contains('ATRASADA', na=False)])
            urgentes  = len(df_tarefas[df_tarefas['Situacao'].str.contains('URGENTE',  na=False)])
            semana    = len(df_tarefas[df_tarefas['Situacao'].str.contains('ESTA SEMANA', na=False)])

            kpi_row([
                {"label": "Total",       "value": total},
                {"label": "Atrasadas",   "value": atrasadas, "accent": atrasadas > 0},
                {"label": "Urgentes",    "value": urgentes},
                {"label": "Esta semana", "value": semana},
            ])

            section("Filtrar")
            col_f1, col_f2 = st.columns(2)
            tipo_filtro = col_f1.selectbox(
                "Tipo", ["TODOS"] + sorted(df_tarefas['tipo_tarefa'].unique().tolist()),
                key="rel_tipo"
            )
            # Remove emojis das situações se existirem na view antiga
            sit_opcoes = ["TODAS"] + sorted(df_tarefas['Situacao'].dropna().unique().tolist())
            situacao_filtro = col_f2.selectbox("Situação", sit_opcoes, key="rel_sit")

            df_filtrado = df_tarefas.copy()
            if tipo_filtro != "TODOS":
                df_filtrado = df_filtrado[df_filtrado['tipo_tarefa'] == tipo_filtro]
            if situacao_filtro != "TODAS":
                df_filtrado = df_filtrado[df_filtrado['Situacao'] == situacao_filtro]

            section(f"Tarefas ({len(df_filtrado)})")

            if df_filtrado.empty:
                empty_state("🔍", "Nenhuma tarefa nos filtros atuais", "Ajuste os filtros acima.")
            else:
                for _, tarefa in df_filtrado.iterrows():
                    col_info, col_acao = st.columns([6, 1])

                    with col_info:
                        situacao_clean = str(tarefa['Situacao']).replace('🔴', '').replace('🟡', '').replace('🟢', '').replace('⚪', '').strip()
                        tom = situacao_to_tom(situacao_clean)

                        meta_parts = []
                        if tarefa['Parceiro']:
                            meta_parts.append(f"<strong>Parceiro:</strong> {tarefa['Parceiro']}")
                        if tarefa['Contato']:
                            meta_parts.append(f"Contato: {tarefa['Contato']}")
                        meta_parts.append(f"Prazo: <strong>{tarefa['data_prazo']}</strong> ({tarefa['Dias_Ate_Prazo']} dias)")
                        if tarefa['prioridade']:
                            meta_parts.append(f"Prioridade: {tarefa['prioridade']}")

                        action_card(
                            titulo=f"{tarefa['tipo_tarefa']} — {tarefa['descricao']}",
                            meta_parts=meta_parts,
                            tom=tom,
                            situacao_badge=situacao_clean,
                        )

                    with col_acao:
                        st.write("")
                        if st.button("Concluir", key=f"concluir_{tarefa['id_tarefa']}", use_container_width=True, type="primary"):
                            run_insert(
                                "UPDATE Tarefas_Pendentes SET status='CONCLUIDA', data_conclusao=? WHERE id_tarefa=?",
                                (datetime.now().strftime('%Y-%m-%d'), int(tarefa['id_tarefa']))
                            )
                            st.toast("Concluída"); st.rerun()
                        if st.button("Cancelar", key=f"cancelar_{tarefa['id_tarefa']}", use_container_width=True):
                            run_insert(
                                "UPDATE Tarefas_Pendentes SET status='CANCELADA' WHERE id_tarefa=?",
                                (int(tarefa['id_tarefa']),)
                            )
                            st.toast("Cancelada"); st.rerun()

        # Expander para criar tarefa manual
        st.markdown("---")
        with st.expander("➕ Criar nova tarefa manual"):
            with st.form("form_nova_tarefa", clear_on_submit=True):
                df_parceiros_form = _parceiros_lista()
                p_opcoes = ["-- Sem parceiro --"] + df_parceiros_form['nome_instituicao'].tolist()
                nomes_cdp = ["-- A definir --"] + sorted([c["nome"] for c in CONTAS.values()])

                col_a, col_b = st.columns(2)
                tipo_novo = col_a.selectbox("Tipo", ["FOLLOW_UP", "RENOVACAO", "AGRADECIMENTO", "PROSPECCAO", "OUTRO"])
                prioridade_nova = col_b.selectbox("Prioridade", ["ALTA", "MEDIA", "BAIXA"])

                descricao_nova = st.text_area("Descrição da tarefa")

                col_c, col_d = st.columns(2)
                prazo_novo = col_c.date_input("Prazo", datetime.now() + timedelta(days=7))
                parceiro_novo = col_d.selectbox("Parceiro relacionado (opcional)", p_opcoes)

                responsavel_novo = st.selectbox("Responsável direto (opcional):", nomes_cdp)

                if st.form_submit_button("Criar tarefa", type="primary"):
                    if descricao_nova:
                        id_parc_novo = None
                        if parceiro_novo != "-- Sem parceiro --":
                            id_parc_novo = int(df_parceiros_form[df_parceiros_form['nome_instituicao'] == parceiro_novo]['id_parceiro'].values[0])
                        resp_final = None if responsavel_novo == "-- A definir --" else responsavel_novo

                        run_insert(
                            "INSERT INTO Tarefas_Pendentes (tipo_tarefa, descricao, data_prazo, prioridade, id_parceiro, responsavel) VALUES (?, ?, ?, ?, ?, ?)",
                            (tipo_novo, descricao_nova, prazo_novo.strftime('%Y-%m-%d'), prioridade_nova, id_parc_novo, resp_final)
                        )
                        st.toast("Tarefa criada!")
                        st.rerun()
                    else:
                        st.warning("Preencha a descrição.")


elif menu == "Eventos":
    # datetime, timedelta e pandas já importados no topo
    # CSS (.glass-card e .guest-item) já está no CSS_GLOBAL

    page_header("Almoço CDP", "Controle de convidados, confirmações e check-in do mês.")
    
    # 1. Definição do Mês de Referência
    mes_atual = datetime.now().strftime("%m/%Y")
    
    # Busca todos os meses que já têm algum cadastro no banco de dados
    df_meses = run_query("SELECT DISTINCT mes_referencia FROM Convidados_Almoco")
    meses_cadastrados = df_meses['mes_referencia'].tolist() if not df_meses.empty else []
    
    # Junta o mês atual, os meses do banco e meses futuros para planejamento (evita duplicidade usando set)
    lista_meses = list(set([mes_atual, "04/2026", "05/2026", "06/2026"] + meses_cadastrados))
    
    # Ordena a lista cronologicamente do mais recente para o mais antigo
    lista_meses.sort(key=lambda x: datetime.strptime(x, "%m/%Y"), reverse=True)
    
    mes_ref = st.selectbox("Mês do evento", lista_meses, help="Selecione o mês do evento")
    
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
                                VALUES (?,?,?,?,?,?, 1, 1)
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
                                    <small style="opacity:0.7;">{str(row['cargo']).title() if pd.notna(row['cargo']) else ''} | {row['empresa'] if pd.notna(row['empresa']) else ''} | 📞 {row['telefone'] if pd.notna(row['telefone']) else 'Sem número'}</small>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        label_btn = "Fazer Check-in" if not row['compareceu'] else "Anular Presença"
                        if st.button(label_btn, key=f"btn_{row['id']}", type="primary" if not row['compareceu'] else "secondary", use_container_width=True):
                            novo_status = 1 if not row['compareceu'] else 0
                            run_insert("UPDATE Convidados_Almoco SET compareceu = ? WHERE id = ?", (novo_status, row['id']))
                            st.rerun()

        # --- DOSSIÊ EXECUTIVO ---
        with col_brief:
            section("Dossiê executivo")
            df_p = df_conf[df_conf['compareceu'] == 1] if not df_conf.empty else pd.DataFrame()
            
            if not df_p.empty:
                msg_whatsapp = f"*PRESENTES NO ALMOÇO CDP - {mes_ref}*\n\n"
                
                html_visual = f"""
                <div class="glass-card">
                    <h4 style="color: #00CC96; margin-top: 0; text-align: center; font-size: 1.1rem;">🍽️ LISTA DE PRESENÇA</h4>
                    <hr style="border-color: rgba(255,255,255,0.05); margin-bottom: 15px;">
                """
                
                for seg, gp in df_p.groupby('segmento'):
                    msg_whatsapp += f"✅ *{seg.upper()}*\n"
                    html_visual += f"<h6 style='color: #00FFC2; margin-top: 15px; font-size: 0.9rem; letter-spacing: 1px;'>{seg.upper()}</h6><ul style='list-style-type: none; padding-left: 5px;'>"
                    
                    for _, p in gp.iterrows():
                        nome_fmt = str(p['nome']).title()
                        cargo_raw = str(p['cargo']).strip()
                        tem_cargo = cargo_raw and cargo_raw.lower() not in ['nan', 'none', '']
                        
                        if tem_cargo:
                            cargo_fmt = cargo_raw.title()
                            msg_whatsapp += f"• {nome_fmt} ({cargo_fmt})\n"
                            html_visual += f"<li style='margin-bottom: 10px;'>👤 <b>{nome_fmt}</b><br><span style='opacity: 0.6; font-size: 0.85em; margin-left: 20px;'>— {cargo_fmt}</span></li>"
                        else:
                            msg_whatsapp += f"• {nome_fmt}\n"
                            html_visual += f"<li style='margin-bottom: 10px;'>👤 <b>{nome_fmt}</b></li>"
                    
                    msg_whatsapp += "\n"
                    html_visual += "</ul>"
                
                html_visual += "</div>"
                st.markdown(html_visual, unsafe_allow_html=True)
                
                with st.expander("Copiar para WhatsApp"):
                    st.code(msg_whatsapp, language="markdown")
            else:
                st.info("Nenhum convidado presente no momento.")

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
                    """, (int(r['contato_1']), int(r['contato_2']), int(r['confirmado']), r['telefone'], r['cargo'], r['empresa'], r['nome'], r['id']))
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
            df_p = run_query(query)
        except:
            df_p = run_query("SELECT * FROM Parceiro")

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
            empty_state("🔍", "Nada encontrado", "Ajuste a busca ou cadastre um novo parceiro.")

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
                empty_state("👤", f"Sem contatos em {parceiro_selecionado}", "Use o botão **➕ NOVO** no topo do menu para cadastrar um contato.")

        # 2. SEÇÃO DE CADASTRO
        # Auto-abre se o usuário veio do botão "+ Novo > Parceiro"
        _abrir_p = (st.session_state.open_form == "parceiro")
        if _abrir_p:
            st.session_state.open_form = None  # consome a flag
            st.info("✨ Cadastrando novo parceiro — preencha os campos abaixo.", icon="🏢")

        with st.expander("**CADASTRAR NOVO PARCEIRO**", expanded=_abrir_p):
            # Busca categorias para o menu
            df_cat_list = run_query("SELECT id_categoria, nome_categoria FROM Categoria_Parceiro")
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
            if cf1.button("👤 Adicionar contato deste parceiro", use_container_width=True, key="post_add_contato"):
                _trigger_quick_add("contato"); st.rerun()
            if cf2.button("💰 Registrar doação deste parceiro", use_container_width=True, key="post_add_doacao"):
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
            empty_state("📊", "Nenhum projeto vinculado", "Doações sem projeto específico aparecem na categoria GERAL.")

    # ============================================================
    # ABA 3 — FUNIL DE CONVERSÃO
    # ============================================================
    with tab3:
        st.markdown("#### Funil de conversão")
        st.caption("Acompanhe o pipeline de prospecção e as conversões recentes para parceiro ativo.")

        df_funil = run_query("""
            SELECT nome_instituicao, status, data_adesao,
                   (CURRENT_DATE - data_adesao::date) AS dias_na_base
            FROM Parceiro
            WHERE data_adesao IS NOT NULL
            ORDER BY data_adesao DESC
        """)

        df_funil_all = run_query("SELECT nome_instituicao, status, data_adesao FROM Parceiro")

        if df_funil_all.empty:
            empty_state("📊", "Sem dados", "Cadastre parceiros para visualizar o funil.")
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
                ("🔵 Prospecção", n_prospec, "#3B82F6"),
                ("🟢 Ativo",      n_ativo,   "#059669"),
                ("⚫ Inativo",    n_inativo,  "#6B7280"),
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
                df_conv = run_query("""
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
                            f'  <span style="font-size:13px;">✅ {r["nome_instituicao"]}</span>'
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

                    if st.button(f"✅ Confirmar importação de {len(df_import)} parceiros", type="primary", use_container_width=True):
                        # Busca id_categoria padrão (primeira disponível)
                        df_cat_imp = run_query("SELECT id_categoria FROM Categoria_Parceiro LIMIT 1")
                        id_cat_default = int(df_cat_imp['id_categoria'].values[0]) if not df_cat_imp.empty else 1

                        erros = 0
                        ok = 0
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
                            except Exception:
                                erros += 1

                        if ok > 0:
                            st.success(f"**{ok} parceiros importados** com sucesso! {f'({erros} ignorados por erro)' if erros else ''}")
                        if erros > 0 and ok == 0:
                            st.error("Nenhum registro foi importado. Verifique o formato da planilha.")

            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")

# --- 3. REGISTRAR DOAÇÃO ---
elif menu == "Registrar Doação":
    page_header("Entrada de recursos", "Registro de doações recebidas e histórico editável.")

    # Se veio do botão "+ Novo > Doação", mostra aviso
    _veio_qa_doacao = (st.session_state.open_form == "doacao")
    if _veio_qa_doacao:
        st.session_state.open_form = None
        st.info("✨ Registrando nova doação — preencha os campos abaixo.", icon="💰")

    # 1. Buscamos os nomes para o usuário escolher
    df_p = _parceiros_lista()

    if df_p.empty:
        empty_state("🏢", "Nenhum parceiro cadastrado", "Cadastre um parceiro antes de registrar doações.")
        if st.button("🏢 Cadastrar parceiro agora", type="primary", key="doa_go_parc"):
            _trigger_quick_add("parceiro"); st.rerun()
    else:
        with st.form("nova_doacao", clear_on_submit=True):
            col_a, col_b = st.columns(2)

            with col_a:
                opcoes_p = ["Selecione o parceiro..."] + df_p['nome_instituicao'].tolist()
                nome_sel = st.selectbox("Parceiro / Fonte *", opcoes_p)
                valor    = st.number_input("Valor do repasse (R$) *", min_value=0.0, step=100.0, format="%.2f")
                data     = st.date_input("Data do recebimento", datetime.now())

            with col_b:
                projeto = st.text_input("Projeto / Emenda / Finalidade", placeholder="ex: Projeto Vida")
                tipo    = st.selectbox("Tipo de recurso", ["Financeira", "Vestuário", "Alimentos", "Serviços", "Midiática", "Projetos"])
                origens_plano = ["Selecione...", "Bazar do Caquito", "Campanha Troco", "Parcerias", "Nota Potiguar", "Doações Online", "Projetos", "Troco"]
                origem_sel = st.selectbox("Origem da captação (estratégia)", origens_plano)

            desc = st.text_area("Observações", placeholder="Contexto, forma de pagamento, referências…")

            if st.form_submit_button("Confirmar doação", type="primary", use_container_width=True):
                if nome_sel == "Selecione o parceiro...":
                    st.warning("Selecione o parceiro.")
                elif valor <= 0:
                    st.warning("Informe um valor maior que zero.")
                else:
                    projeto_final = projeto.upper() if projeto else "GERAL"
                    id_p = df_p[df_p['nome_instituicao'] == nome_sel]['id_parceiro'].values[0]

                    sql = """
                        INSERT INTO Doacao (
                            id_parceiro, valor_estimado, tipo_doacao,
                            data_doacao, descricao, nome_projeto, origem_captacao
                        )
                        VALUES (?,?,?,?,?,?,?)
                    """
                    run_insert(sql, (
                        int(id_p), valor, tipo,
                        data.strftime('%Y-%m-%d'),
                        desc.upper(), projeto_final, origem_sel
                    ))
                    st.success(f"Doação de **{nome_sel}** ({format_br(valor)}) registrada!")
                    st.rerun()

    # --- CENTRAL DE GESTÃO DE LANÇAMENTOS (EXTRATO POR PARCEIRO) ---
    st.divider()
    section("Histórico e lançamentos")

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
                    _dd = row['data_doacao']
                    _dd_val = _dd if hasattr(_dd, 'year') else datetime.strptime(str(_dd), '%Y-%m-%d').date()
                    nova_data = c2.date_input("Data", value=_dd_val, key=f"d_{row['id_doacao']}")
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
        st.info("✨ Cadastrando novo contato — preencha os campos abaixo.", icon="👤")
        with st.container(border=True):
            df_p_qa = _parceiros_lista()
            if df_p_qa.empty:
                st.warning("Cadastre um parceiro antes de adicionar contatos.")
                if st.button("🏢 Cadastrar parceiro agora", type="primary", key="qa_go_parceiro"):
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
            st.warning("Cadastre um parceiro primeiro (use o botão **➕ NOVO** no topo do menu).")

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
                
                st.error("⚠️ Atenção: Esta ação não pode ser desfeita.")
                if st.button("🗑️ Confirmar Exclusão", use_container_width=True):
                    run_insert("DELETE FROM Contato_Direto WHERE id_contato = ?", (id_para_excluir,))
                    st.success("Contato excluído com sucesso!")
                    st.rerun()
        else:
            st.info("Não há contatos para gerenciar.")

# --- COLOQUE ISSO NO FINAL DO ARQUIVO ---
elif menu == "Relacionamento":
    # datetime, timedelta e pandas já importados no topo
    import plotly.graph_objects as go

    # 1. BUSCA DE DADOS (Blindagem de Nomes e Colunas)
    df_parceiros = run_query_cached("SELECT id_parceiro, nome_instituicao, UPPER(TRIM(status)) as status_limpo FROM Parceiro")

    # SQL para View — usa os nomes reais das colunas do banco
    df_rel = run_query_cached("SELECT * FROM View_Relacionamento_Critico")

    # Buscar última data de retorno agendada
    df_retornos = run_query_cached("SELECT id_parceiro, MAX(proxima_acao_data) as data_retorno FROM Registro_Relacionamento GROUP BY id_parceiro")

    # CSS (.glass-card, .stat-value, .suggestion-box, .date-badge) já está no CSS_GLOBAL

    page_header("Manutenção de relacionamento", "Régua de contato por parceiro e relatório para diretoria.")

    # KPIs com DS (substitui glass-card antigo)
    m_p = df_parceiros['status_limpo'].str.contains('PROSPEC',  na=False)
    m_a = df_parceiros['status_limpo'].str.contains('ATIVO',    na=False)
    m_i = df_parceiros['status_limpo'].str.contains('INATIVO',  na=False)

    kpi_row([
        {"label": "Prospecção", "value": int(m_p.sum())},
        {"label": "Ativos",     "value": int(m_a.sum()), "accent": True},
        {"label": "Inativos",   "value": int(m_i.sum())},
    ])

    # 4. Plano de ação — sugestões do mês
    section("Sugestões do mês")
    semente = int(datetime.now().strftime('%Y%m'))
    cs1, cs2 = st.columns(2)

    with cs1:
        st.caption("Foco: conversão")
        sug_p = df_parceiros[m_p].sample(min(2, len(df_parceiros[m_p])), random_state=semente) if any(m_p) else pd.DataFrame()
        for _, r in sug_p.iterrows():
            action_card(
                titulo=r['nome_instituicao'],
                meta_parts=["Enviar apresentação atualizada e solicitar agenda de 15 min."],
                tom="success",
            )
        if sug_p.empty:
            st.caption("Sem parceiros em prospecção.")

    with cs2:
        st.caption("Foco: reativação")
        sug_i = df_parceiros[m_i].sample(min(2, len(df_parceiros[m_i])), random_state=semente) if any(m_i) else pd.DataFrame()
        for _, r in sug_i.iterrows():
            action_card(
                titulo=r['nome_instituicao'],
                meta_parts=["Ligação de cortesia para entender a pausa e oferecer novo benefício."],
                tom="danger",
            )
        if sug_i.empty:
            st.caption("Sem parceiros inativos.")

    # 5. Diagnóstico — abas
    tab_saude, tab_hist, tab_diretoria = st.tabs(["Saúde e retornos", "Histórico detalhado", "Relatório para diretoria"])

    with tab_saude:
        if df_rel.empty:
            empty_state("📊", "Sem dados de relacionamento", "Cadastre interações em parceiros ativos para popular esta aba.")
        else:
            df_join = df_rel.merge(df_parceiros[['nome_instituicao', 'id_parceiro']], left_on='Empresa', right_on='nome_instituicao', how='left')
            df_final = df_join.merge(df_retornos, on='id_parceiro', how='left')

            # Separa parceiros COM e SEM histórico
            df_com_hist  = df_final[df_final['Status_Relacionamento'] != '⚫ SEM HISTÓRICO'].copy()
            df_sem_hist  = df_final[df_final['Status_Relacionamento'] == '⚫ SEM HISTÓRICO']
            qtd_sem_hist = len(df_sem_hist)

            # Aviso discreto sobre parceiros sem histórico
            if qtd_sem_hist > 0:
                st.info(f"**{qtd_sem_hist} parceiros** ainda não têm nenhum contato registrado no sistema e foram ocultados deste painel.")

            if df_com_hist.empty:
                empty_state("📋", "Nenhum contato registrado", "Registre a primeira interação com um parceiro para ativar o painel de saúde.")
            else:
                cg, ct = st.columns([1, 1.4])
                with cg:
                    # Ordem de exibição: Crítico → Atenção → Em dia
                    ordem_status = {'🔴 CRÍTICO (+3 meses)': 0, '🟡 ATENÇÃO (+45 dias)': 1, '🟢 EM DIA': 2}
                    df_g = (
                        df_com_hist.groupby('Status_Relacionamento')
                        .size().reset_index(name='qtd')
                        .assign(ordem=lambda d: d['Status_Relacionamento'].map(ordem_status))
                        .sort_values('ordem')
                    )
                    cor_map = {
                        '🔴 CRÍTICO (+3 meses)': '#DC2626',
                        '🟡 ATENÇÃO (+45 dias)':  '#D97706',
                        '🟢 EM DIA':              '#059669',
                    }
                    cores = [cor_map.get(s, '#888') for s in df_g['Status_Relacionamento']]
                    fig = go.Figure(data=[go.Pie(
                        labels=df_g['Status_Relacionamento'], values=df_g['qtd'], hole=.78,
                        marker_colors=cores, textinfo='none'
                    )])
                    fig.update_layout(
                        height=260, margin=dict(t=10, b=10, l=0, r=0), showlegend=True,
                        paper_bgcolor='rgba(0,0,0,0)',
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                        annotations=[dict(text='STATUS<br>SAÚDE', x=0.5, y=0.5, font_size=14, showarrow=False)]
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with ct:
                    st.markdown("**Cronograma de follow-up:**")
                    # Ordena: críticos primeiro, depois atenção, depois em dia
                    df_tabela = df_com_hist.copy()
                    df_tabela['_ordem'] = df_tabela['Status_Relacionamento'].map(ordem_status).fillna(9)
                    df_tabela = df_tabela.sort_values(['_ordem', 'Dias_Sem_Contato'], ascending=[True, False])
                    st.dataframe(
                        df_tabela[['Empresa', 'Dias_Sem_Contato', 'Proxima_Acao_Planejada', 'Status_Relacionamento']],
                        column_config={
                            "Empresa": "Parceiro",
                            "Dias_Sem_Contato": st.column_config.NumberColumn("Dias parado", format="%d d"),
                            "Proxima_Acao_Planejada": st.column_config.DateColumn("Próxima ação", format="DD/MM/YYYY"),
                            "Status_Relacionamento": "Saúde"
                        },
                        use_container_width=True, hide_index=True, height=280
                    )
            

    with tab_hist:
        p_lista = ["--"] + sorted(df_parceiros['nome_instituicao'].tolist())
        sel_h = st.selectbox("Selecione o parceiro para histórico:", p_lista)
        if sel_h != "--":
            id_p = df_parceiros[df_parceiros['nome_instituicao'] == sel_h]['id_parceiro'].values[0]
            h = run_query(f"SELECT data_interacao, descricao_do_que_foi_feito FROM Registro_Relacionamento WHERE id_parceiro = {id_p} ORDER BY data_interacao DESC")
            for _, r in h.iterrows():
                st.markdown(f"""<div style="margin-bottom:15px; padding:10px; border-bottom:1px solid rgba(255,255,255,0.1)">
                <span class="date-badge">{r['data_interacao']}</span><br>
                <p style="margin-top:8px; font-size:0.95rem;">{r['descricao_do_que_foi_feito']}</p></div>""", unsafe_allow_html=True)

    # ==========================================
    # ABA 3: RELATÓRIO PARA A DIRETORIA
    # ==========================================
    with tab_diretoria:
        st.markdown("### Extrair atualizações de parcerias")
        st.write("Gerar um resumo estratégico (ações manuais e doações recebidas) para reportar à direção.")

        # Filtro de datas
        c_inicio, c_fim = st.columns(2)
        data_inicio = c_inicio.date_input("Data inicial", datetime.now() - timedelta(days=7), key="dt_ini_rel")
        data_fim = c_fim.date_input("Data final", datetime.now(), key="dt_fim_rel")

        if st.button("Gerar relatório de atividades", type="primary", use_container_width=True):
            d_ini = data_inicio.strftime('%Y-%m-%d')
            d_fim = data_fim.strftime('%Y-%m-%d')

            # Duas queries separadas para evitar problemas com UNION ALL + psycopg2
            df_rel_int = run_query("""
                SELECT p.nome_instituicao,
                       r.data_interacao AS data_registro,
                       'RELACIONAMENTO' AS tipo,
                       r.descricao_do_que_foi_feito AS descricao,
                       0 AS valor_estimado
                FROM Registro_Relacionamento r
                JOIN Parceiro p ON r.id_parceiro = p.id_parceiro
                WHERE r.data_interacao BETWEEN ? AND ?
                  AND r.descricao_do_que_foi_feito NOT LIKE 'Sistema:%%'
            """, (d_ini, d_fim))

            df_rel_doa = run_query("""
                SELECT p.nome_instituicao,
                       d.data_doacao AS data_registro,
                       CONCAT('DOAÇÃO (', d.tipo_doacao, ')') AS tipo,
                       d.descricao AS descricao,
                       d.valor_estimado
                FROM Doacao d
                JOIN Parceiro p ON d.id_parceiro = p.id_parceiro
                WHERE d.data_doacao BETWEEN ? AND ?
            """, (d_ini, d_fim))

            df_relatorio = pd.concat([df_rel_int, df_rel_doa], ignore_index=True)
            if not df_relatorio.empty:
                df_relatorio = df_relatorio.sort_values('data_registro', ascending=False)

            if not df_relatorio.empty:
                dt_ini_fmt = data_inicio.strftime('%d/%m/%Y')
                dt_fim_fmt = data_fim.strftime('%d/%m/%Y')
                
                texto_diretoria = f"*RESUMO ESTRATÉGICO DI - {dt_ini_fmt} a {dt_fim_fmt}*\n\n"

                html_relatorio = f"""
                <div class="glass-card">
                    <h4 style="color: #00CC96; margin-top: 0; text-align: center;">RESUMO: {dt_ini_fmt} a {dt_fim_fmt}</h4>
                    <hr style="border-color: rgba(255,255,255,0.05); margin-bottom: 15px;">
                    <ul style='list-style-type: none; padding-left: 5px;'>
                """

                for _, row in df_relatorio.iterrows():
                    _dr = row['data_registro']
                    data_reg_fmt = (_dr if hasattr(_dr, 'strftime') else datetime.strptime(str(_dr), '%Y-%m-%d')).strftime('%d/%m')
                    nome_parceiro = str(row['nome_instituicao']).upper()
                    descricao = str(row['descricao']).capitalize() if pd.notna(row['descricao']) and str(row['descricao']).strip() != "" else "Sem observações adicionais."
                    tipo = row['tipo']
                    
                    # Lógica de formatação condicional se for doação (mostra o valor se for maior que 0)
                    if "DOAÇÃO" in tipo and row['valor_estimado'] > 0:
                        valor_fmt = f"R$ {row['valor_estimado']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        texto_extra = f" | Valor: {valor_fmt}"
                        html_extra = f" <span style='color:#00FFC2; font-weight:bold;'>| {valor_fmt}</span>"
                    else:
                        texto_extra = ""
                        html_extra = ""

                    # Adiciona ao texto do WhatsApp
                    texto_diretoria += f"🔹 *{nome_parceiro}* ({data_reg_fmt})\n"
                    texto_diretoria += f"{tipo}{texto_extra}\n"
                    texto_diretoria += f"Detalhe: {descricao}\n\n"

                    # Adiciona ao visual HTML
                    html_relatorio += f"<li style='margin-bottom: 18px;'>"
                    html_relatorio += f"🏢 <b style='font-size:1.05em;'>{nome_parceiro}</b> <span class='date-badge' style='margin-left: 10px;'>{data_reg_fmt}</span><br>"
                    html_relatorio += f"<span style='font-size: 0.85em; color: #FFB74D; font-weight: 600; margin-left: 25px; display: inline-block; margin-top: 4px; margin-bottom: 4px;'>{tipo}{html_extra}</span><br>"
                    html_relatorio += f"<span style='opacity: 0.85; font-size: 0.95em; margin-left: 25px;'>↳ {descricao}</span>"
                    html_relatorio += f"</li>"
                
                html_relatorio += "</ul></div>"

                # Exibe visualmente no Streamlit
                st.markdown(html_relatorio, unsafe_allow_html=True)

                # Caixa para o usuário copiar o texto
                with st.expander("Copiar texto para WhatsApp / E-mail"):
                    st.code(texto_diretoria, language="markdown")

                # ── Botão PDF ────────────────────────────────────────────
                st.markdown("<br>", unsafe_allow_html=True)

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
                    doc = SimpleDocTemplate(
                        buf, pagesize=A4,
                        leftMargin=2*cm, rightMargin=2*cm,
                        topMargin=2*cm, bottomMargin=2*cm,
                    )

                    estilos = getSampleStyleSheet()
                    cor_principal = colors.HexColor("#C0392B")
                    cor_cinza     = colors.HexColor("#555555")
                    cor_fundo     = colors.HexColor("#F7F7F7")

                    st_titulo = ParagraphStyle("titulo", parent=estilos["Title"],
                        fontSize=20, textColor=cor_principal, spaceAfter=4)
                    st_subtitulo = ParagraphStyle("sub", parent=estilos["Normal"],
                        fontSize=11, textColor=cor_cinza, spaceAfter=12)
                    st_secao = ParagraphStyle("secao", parent=estilos["Heading2"],
                        fontSize=13, textColor=cor_principal, spaceBefore=14, spaceAfter=6)
                    st_item = ParagraphStyle("item", parent=estilos["Normal"],
                        fontSize=10, textColor=colors.HexColor("#222222"), spaceAfter=2, leading=14)
                    st_detalhe = ParagraphStyle("detalhe", parent=estilos["Normal"],
                        fontSize=9, textColor=cor_cinza, leftIndent=12, spaceAfter=8, leading=13)
                    st_rodape = ParagraphStyle("rodape", parent=estilos["Normal"],
                        fontSize=8, textColor=cor_cinza, alignment=1)

                    story = []

                    # Cabeçalho
                    story.append(Paragraph("Casa Durval Paiva", st_titulo))
                    story.append(Paragraph(
                        f"Relatório Estratégico de Parcerias — {d_ini_fmt} a {d_fim_fmt}",
                        st_subtitulo
                    ))
                    story.append(HRFlowable(width="100%", thickness=1.5, color=cor_principal, spaceAfter=10))

                    # KPIs do período
                    doacoes_period = df_rel[df_rel['tipo'].str.contains("DOA", na=False, case=False)]
                    relac_period   = df_rel[df_rel['tipo'] == 'RELACIONAMENTO']
                    total_fin      = doacoes_period['valor_estimado'].sum()
                    n_parcerias    = df_rel['nome_instituicao'].nunique()

                    dados_kpi = [
                        ["Parceiros movimentados", "Interações registradas", "Doações no período"],
                        [str(n_parcerias), str(len(relac_period)), f"R$ {total_fin:,.2f}".replace(",","X").replace(".",",").replace("X",".")]
                    ]
                    t_kpi = Table(dados_kpi, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
                    t_kpi.setStyle(TableStyle([
                        ("BACKGROUND", (0,0), (-1,0), cor_fundo),
                        ("TEXTCOLOR",  (0,0), (-1,0), cor_cinza),
                        ("FONTSIZE",   (0,0), (-1,0), 9),
                        ("FONTSIZE",   (0,1), (-1,1), 14),
                        ("FONTNAME",   (0,1), (-1,1), "Helvetica-Bold"),
                        ("TEXTCOLOR",  (0,1), (-1,1), cor_principal),
                        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
                        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
                        ("ROWBACKGROUNDS", (0,0), (-1,-1), [cor_fundo, colors.white]),
                        ("BOX",        (0,0), (-1,-1), 0.5, cor_cinza),
                        ("INNERGRID",  (0,0), (-1,-1), 0.3, colors.HexColor("#DDDDDD")),
                        ("TOPPADDING", (0,0), (-1,-1), 8),
                        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                    ]))
                    story.append(t_kpi)
                    story.append(Spacer(1, 0.4*cm))

                    # Interações
                    if not relac_period.empty:
                        story.append(Paragraph("Interações com parceiros", st_secao))
                        for _, row in relac_period.iterrows():
                            _dr = row['data_registro']
                            drf = (_dr if hasattr(_dr,'strftime') else datetime.strptime(str(_dr),'%Y-%m-%d')).strftime('%d/%m/%Y')
                            story.append(Paragraph(
                                f"<b>{str(row['nome_instituicao']).upper()}</b> &nbsp;&nbsp; <font color='#888888' size='9'>{drf}</font>",
                                st_item
                            ))
                            desc = str(row['descricao']).capitalize() if pd.notna(row['descricao']) else "—"
                            story.append(Paragraph(f"↳ {desc}", st_detalhe))

                    # Doações
                    if not doacoes_period.empty:
                        story.append(Paragraph("Doações recebidas no período", st_secao))
                        dados_doa = [["Parceiro", "Tipo", "Valor"]]
                        for _, row in doacoes_period.iterrows():
                            _dr = row['data_registro']
                            drf = (_dr if hasattr(_dr,'strftime') else datetime.strptime(str(_dr),'%Y-%m-%d')).strftime('%d/%m')
                            val = row['valor_estimado'] or 0
                            val_fmt = f"R$ {val:,.2f}".replace(",","X").replace(".",",").replace("X",".")
                            dados_doa.append([
                                str(row['nome_instituicao']).upper()[:35],
                                str(row['tipo']).replace("DOAÇÃO (","").replace(")",""),
                                val_fmt
                            ])
                        t_doa = Table(dados_doa, colWidths=[8*cm, 4*cm, 4.5*cm])
                        t_doa.setStyle(TableStyle([
                            ("BACKGROUND",    (0,0), (-1,0), cor_principal),
                            ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
                            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
                            ("FONTSIZE",      (0,0), (-1,-1), 9),
                            ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, cor_fundo]),
                            ("GRID",          (0,0), (-1,-1), 0.3, colors.HexColor("#CCCCCC")),
                            ("ALIGN",         (2,0), (2,-1), "RIGHT"),
                            ("TOPPADDING",    (0,0), (-1,-1), 5),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                        ]))
                        story.append(t_doa)

                    # Rodapé
                    story.append(Spacer(1, 1*cm))
                    story.append(HRFlowable(width="100%", thickness=0.5, color=cor_cinza))
                    story.append(Spacer(1, 0.2*cm))
                    story.append(Paragraph(
                        f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} · Sistema de Gestão DI — Casa Durval Paiva",
                        st_rodape
                    ))

                    doc.build(story)
                    buf.seek(0)
                    return buf.read()

                pdf_bytes = _gerar_pdf_diretoria(df_relatorio, dt_ini_fmt, dt_fim_fmt)
                st.download_button(
                    label="📄 Baixar relatório em PDF",
                    data=pdf_bytes,
                    file_name=f"relatorio_di_{data_inicio.strftime('%Y%m')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

            else:
                st.info("Nenhuma ação estratégica manual ou doação foi registrada neste período.")

    # 6. REGISTRO GLASS (Ação + Retorno)
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("REGISTRAR INTERAÇÃO E AGENDAR RETORNO"):
        with st.form("form_glass_final", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            d_acao = c1.date_input("Data do Contato", datetime.now())
            d_retorno = c2.date_input("Próximo Retorno", datetime.now() + timedelta(days=15))
            p_sel = c3.selectbox("Parceiro", p_lista)
            
            st_novo = st.selectbox("Atualizar Status?", ["Manter atual", "ATIVO", "PROSPECÇÃO", "INATIVO"])
            relato = st.text_area("Descrição da conversa:")
            
            if st.form_submit_button("SALVAR GESTÃO", type="primary"):
                if p_sel != "--" and relato:
                    id_p = int(df_parceiros[df_parceiros['nome_instituicao'] == p_sel]['id_parceiro'].values[0])
                    # Inserção com proxima_acao_data
                    run_insert("INSERT INTO Registro_Relacionamento (id_parceiro, data_interacao, descricao_do_que_foi_feito, proxima_acao_data) VALUES (?, ?, ?, ?)",
                              (id_p, d_acao.strftime('%Y-%m-%d'), relato.upper(), d_retorno.strftime('%Y-%m-%d')))
                    if st_novo != "Manter atual":
                        run_insert("UPDATE Parceiro SET status = ? WHERE id_parceiro = ?", (st_novo, id_p))
                    st.toast("Registro salvo!"); st.rerun()



# ============================================================
#  SIDEBAR — FERRAMENTAS FIXAS (sempre visíveis, independente do menu)
# ============================================================
st.sidebar.markdown("---")
st.sidebar.subheader("Extrair dados")

# Backup completo — Excel com uma aba por tabela principal
@st.cache_data(ttl=300, show_spinner=False)
def _gerar_backup_completo():
    """Exporta todas as tabelas principais em um único arquivo Excel (.xlsx).
    Fallback para ZIP de CSVs se openpyxl/xlsxwriter não estiverem disponíveis."""
    tabelas = {
        "Parceiros":        "SELECT * FROM Parceiro",
        "Contatos":         "SELECT * FROM Contato_Direto",
        "Doações":          "SELECT * FROM Doacao",
        "Relacionamentos":  "SELECT * FROM Registro_Relacionamento",
        "Demandas":         "SELECT * FROM Demandas_Estrategicas",
        "Tarefas":          "SELECT * FROM Tarefas_Pendentes",
        "Captacao_DI":      "SELECT * FROM Registro_Captacao_DI",
    }
    dfs = {nome: run_query(sql) for nome, sql in tabelas.items()}

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
                f"backup_cdp_{datetime.now().strftime('%Y%m%d')}.xlsx",
            )
        except (ImportError, ModuleNotFoundError, ValueError):
            continue

    # Fallback: ZIP com um CSV por tabela
    import zipfile
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, df in dfs.items():
            zf.writestr(f"{nome}.csv", df.to_csv(index=False, encoding="utf-8-sig"))
    return (
        zip_buffer.getvalue(),
        "zip",
        "application/zip",
        f"backup_cdp_{datetime.now().strftime('%Y%m%d')}.zip",
    )

if st.sidebar.button("⬇️ Preparar backup completo", use_container_width=True):
    st.session_state["_bk_pronto"] = _gerar_backup_completo()

if "_bk_pronto" in st.session_state:
    _bk_data, _bk_ext, _bk_mime, _bk_nome = st.session_state["_bk_pronto"]
    st.sidebar.download_button(
        label=f"📥 Baixar ({_bk_ext.upper()})",
        data=_bk_data,
        file_name=_bk_nome,
        mime=_bk_mime,
        use_container_width=True,
    )

st.sidebar.markdown("---")

# 3. Sair
if st.sidebar.button("Sair", use_container_width=True):
    st.session_state.clear()
    st.rerun()