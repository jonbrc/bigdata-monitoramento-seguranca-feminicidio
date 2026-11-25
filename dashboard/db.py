"""Acesso ao PostgreSQL (Aiven) para o dashboard: lê as credenciais dos Secrets do Streamlit ou do .env da raiz e executa consultas somente leitura com cache."""

import os
from pathlib import Path

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

CHAVES = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
CACHE_SEGUNDOS = 3600


class ConfiguracaoAusente(RuntimeError):
    pass


def _segredos() -> dict:
    try:
        return {k: str(v) for k, v in st.secrets.items() if not isinstance(v, dict)}
    except Exception:
        return {}


def credenciais() -> dict:
    load_dotenv(ENV_FILE)
    segredos = _segredos()
    valores = {k: segredos.get(k) or os.getenv(k) for k in CHAVES + ["DB_SSLMODE"]}
    faltando = [k for k in CHAVES if not valores[k]]
    if faltando:
        raise ConfiguracaoAusente(", ".join(faltando))
    return valores


def conectar() -> psycopg.Connection:
    c = credenciais()
    return psycopg.connect(
        host=c["DB_HOST"], port=c["DB_PORT"], dbname=c["DB_NAME"],
        user=c["DB_USER"], password=c["DB_PASSWORD"],
        sslmode=c["DB_SSLMODE"] or "require", connect_timeout=15,
        options="-c default_transaction_read_only=on -c search_path=dw",
    )


@st.cache_data(ttl=CACHE_SEGUNDOS, show_spinner="Consultando o banco...")
def consultar(sql: str, params: tuple = ()) -> pd.DataFrame:
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        colunas = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=colunas)
