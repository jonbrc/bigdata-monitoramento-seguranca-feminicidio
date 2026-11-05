"""Funções de padronização reutilizadas pelo ETL (nomes de município, códigos IBGE e idade do SIM)."""

import re
import unicodedata

import pandas as pd


def normalizar_nome(texto) -> str | None:
    if texto is None or pd.isna(texto):
        return None
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    s = s.upper()
    s = re.sub(r"['`´\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def idade_em_anos(idade: pd.Series) -> pd.Series:
    s = idade.astype("string").str.strip()
    valido = s.str.fullmatch(r"\d{3}").fillna(False)
    unidade = s.str[0]
    qtd = pd.to_numeric(s.str[1:], errors="coerce")
    anos = pd.Series(pd.NA, index=idade.index, dtype="Int64")
    anos[valido & unidade.isin(["0", "1", "2", "3"])] = 0
    anos[valido & (unidade == "4")] = qtd[valido & (unidade == "4")]
    anos[valido & (unidade == "5")] = 100 + qtd[valido & (unidade == "5")]
    return anos


def codigo_ibge_6(codigo) -> str | None:
    if codigo is None or pd.isna(codigo):
        return None
    s = str(codigo).strip()
    return s[:6] if len(s) >= 6 else None
