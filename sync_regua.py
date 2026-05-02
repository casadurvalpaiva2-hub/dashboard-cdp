"""
sync_regua.py — Sincronização automática da Régua de Relacionamento
Executa _gerar_regua_pendencias para todos os parceiros ativos com tipo_publico_regua definido.
Projetado para rodar semanalmente via tarefa agendada.

Uso:
    python sync_regua.py
    DATABASE_URL=postgresql://... python sync_regua.py
"""

import os
import sys
from datetime import datetime, timedelta

try:
    import psycopg2
    import pandas as pd
except ImportError:
    print("Dependencias ausentes. Execute: pip install psycopg2-binary pandas")
    sys.exit(1)


# ── Conexão ──────────────────────────────────────────────────────────────────

def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        # Tenta ler do secrets.toml do Streamlit se existir localmente
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            with open(secrets_path) as f:
                for line in f:
                    if line.strip().startswith("DATABASE_URL"):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def run_query(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params or None)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def run_exec(conn, query, params=()):
    with conn.cursor() as cur:
        cur.execute(query, params or None)
    conn.commit()


# ── Lógica da régua ──────────────────────────────────────────────────────────

def get_regua_config(conn) -> dict:
    """Lê a config da régua do banco (Regua_Matriz)."""
    rows = run_query(
        conn,
        "SELECT tipo_publico, acao, periodo_dias, canal "
        "FROM Regua_Matriz WHERE ativo = TRUE ORDER BY tipo_publico, id"
    )
    config = {}
    for row in rows:
        tp = row["tipo_publico"]
        if tp not in config:
            config[tp] = []
        config[tp].append({
            "acao": row["acao"],
            "periodo_dias": row["periodo_dias"],
            "canal": row["canal"] or "",
        })
    return config


def gerar_pendencias(conn, id_parceiro: int, tipo_publico: str, config: dict) -> int:
    """Gera pendências para um parceiro. Retorna número de novas pendências criadas."""
    if not tipo_publico or tipo_publico not in config:
        return 0

    gerados = 0
    hoje = datetime.now()
    data_sug = (hoje + timedelta(days=7)).date()

    for item in config[tipo_publico]:
        # Verificar se já existe pendente
        ex_pend = run_query(
            conn,
            "SELECT id FROM Regua_Pendencias WHERE id_parceiro=%s AND tipo_acao=%s AND status='PENDENTE'",
            (id_parceiro, item["acao"])
        )
        if ex_pend:
            continue

        # Verificar periodicidade
        if item["periodo_dias"]:
            ex_feito = run_query(
                conn,
                "SELECT feito_em FROM Regua_Pendencias WHERE id_parceiro=%s AND tipo_acao=%s "
                "AND status='FEITO' ORDER BY feito_em DESC LIMIT 1",
                (id_parceiro, item["acao"])
            )
            if ex_feito:
                ultima = ex_feito[0]["feito_em"]
                if ultima and (hoje - ultima).days < item["periodo_dias"]:
                    continue

        run_exec(
            conn,
            "INSERT INTO Regua_Pendencias (id_parceiro, tipo_acao, canal_sugerido, data_sugerida) "
            "VALUES (%s, %s, %s, %s)",
            (id_parceiro, item["acao"], item["canal"], data_sug)
        )
        gerados += 1

    return gerados


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] Iniciando sincronizacao da regua...")

    url = _db_url()
    if not url:
        print("ERRO: DATABASE_URL nao encontrada. Configure a variavel de ambiente.")
        sys.exit(1)

    conn = psycopg2.connect(url, connect_timeout=10)

    try:
        config = get_regua_config(conn)
        if not config:
            print("AVISO: Regua_Matriz vazia ou inativa. Nenhuma acao gerada.")
            return

        parceiros = run_query(
            conn,
            "SELECT id_parceiro, tipo_publico_regua FROM Parceiro "
            "WHERE tipo_publico_regua IS NOT NULL AND tipo_publico_regua != '' "
            "AND UPPER(TRIM(status)) IN ('ATIVO', 'PROSPECCAO', 'PROSPECÇÃO')"
        )

        total_parceiros = len(parceiros)
        total_gerados   = 0

        for p in parceiros:
            n = gerar_pendencias(conn, int(p["id_parceiro"]), p["tipo_publico_regua"], config)
            total_gerados += n

        print(
            f"[{datetime.now():%Y-%m-%d %H:%M}] Concluido: "
            f"{total_gerados} pendencia(s) gerada(s) para {total_parceiros} parceiro(s)."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
