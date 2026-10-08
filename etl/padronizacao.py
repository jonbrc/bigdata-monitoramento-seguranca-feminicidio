"""Funções de padronização reutilizadas pelo ETL."""

import re
import unicodedata

import pandas as pd


def normalizar_nome(texto) -> str | None:
    """Gera uma chave de comparação para nomes de município.

    Usada só para casar nomes entre fontes (nunca para exibição):
    remove acentos, converte para maiúsculas, troca apóstrofos e hífens por
    espaço e colapsa espaços repetidos.

    "  Sant'Ana do Livramento " -> "SANT ANA DO LIVRAMENTO"
    "Embu-Guaçu"                -> "EMBU GUACU"
    """
    if texto is None or pd.isna(texto):
        return None
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    s = s.upper()
    s = re.sub(r"['`´\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def codigo_ibge_6(codigo) -> str | None:
    """Converte o código IBGE de 7 dígitos para o de 6 (sem o dígito verificador),
    formato usado pelo SIM/DataSUS."""
    if codigo is None or pd.isna(codigo):
        return None
    s = str(codigo).strip()
    return s[:6] if len(s) >= 6 else None
