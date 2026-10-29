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


def idade_em_anos(idade: pd.Series) -> pd.Series:
    """Decodifica o campo IDADE do SIM (3 dígitos) para anos completos.

    1º dígito = unidade, 2 últimos = quantidade:
      0 minutos, 1 horas, 2 dias, 3 meses  -> menos de 1 ano (0)
      4 anos                                -> 0 a 99
      5 anos acima de 100                   -> 100 + quantidade
      9 (ou valor inválido)                 -> ignorada (nulo)
    "428" -> 28; "310" -> 0; "501" -> 101; "999" -> nulo
    """
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
    """Converte o código IBGE de 7 dígitos para o de 6 (sem o dígito verificador),
    formato usado pelo SIM/DataSUS."""
    if codigo is None or pd.isna(codigo):
        return None
    s = str(codigo).strip()
    return s[:6] if len(s) >= 6 else None
