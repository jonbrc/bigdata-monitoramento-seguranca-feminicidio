"""Cálculo dos KPIs do dashboard (regras RN10–RN17 do README) a partir das views vw_taxa_sim_uf e vw_kpi_uf, com variação em relação ao ano anterior e alerta de estimativa instável."""

from dataclasses import dataclass

import pandas as pd

import db
from filtros import Filtros

MINIMO_ESTAVEL = 10
GRUPOS_FORA_DA_RAZAO = {"Branca", "Ignorada"}


@dataclass
class Kpi:
    titulo: str
    valor: str
    legenda: str
    ajuda: str
    delta: str | None = None
    delta_cor: str = "inverse"
    alerta: str | None = None


def numero(n, casas: int = 0) -> str:
    if n is None or pd.isna(n):
        return "—"
    return f"{n:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def taxa(casos, populacao, meses: int = 12) -> float | None:
    if not populacao:
        return None
    return casos * 100000 / populacao * 12 / meses


def razao(a, b) -> float | None:
    if a is None or b is None or not b:
        return None
    return a / b


def variacao(atual, anterior, ano_anterior: int | None, casas: int = 2, sufixo: str = "") -> str | None:
    if ano_anterior is None or atual is None or anterior is None:
        return None
    diferenca = atual - anterior
    sinal = "+" if diferenca >= 0 else ""
    return f"{sinal}{numero(diferenca, casas)}{sufixo} vs {ano_anterior}"


def instavel(*contagens) -> str | None:
    if any(c is not None and c < MINIMO_ESTAVEL for c in contagens):
        return f"Menos de {MINIMO_ESTAVEL} casos: estimativa instável."
    return None


def _sim(f: Filtros, ano: int) -> pd.DataFrame:
    where, params = f.where(ano=ano, ignorar=("sexo", "grupo"))
    return db.consultar(
        "SELECT sexo, grupo_racial, SUM(obitos) AS obitos, SUM(populacao) AS populacao, "
        "SUM(obitos_domicilio) AS domicilio, MAX(meses_cobertos) AS meses "
        f"FROM vw_taxa_sim_uf WHERE {where} GROUP BY sexo, grupo_racial",
        tuple(params),
    )


def _sinesp(f: Filtros, ano: int) -> pd.Series:
    where, params = f.where(perfil=False, ano=ano)
    return db.consultar(
        "SELECT COALESCE(SUM(feminicidios), 0) AS feminicidios, "
        "COALESCE(SUM(mortes_violentas_fem), 0) AS mortes_violentas, "
        "COALESCE(SUM(pop_fem), 0) AS pop_fem, "
        "COALESCE(SUM(feminicidios) FILTER (WHERE tentativas_feminicidio > 0), 0) AS fem_com_tentativa, "
        "COALESCE(SUM(feminicidios + tentativas_feminicidio) FILTER (WHERE tentativas_feminicidio > 0), 0) AS base_letalidade, "
        "COUNT(*) FILTER (WHERE tentativas_feminicidio = 0) AS ufs_sem_tentativa "
        f"FROM vw_kpi_uf WHERE {where}",
        tuple(params),
    ).iloc[0]


def grupos_alvo(f: Filtros) -> list[str]:
    if not f.grupos:
        return ["Negra"]
    return [g for g in f.grupos if g not in GRUPOS_FORA_DA_RAZAO]


def _recorte(df: pd.DataFrame, sexos: list[str] | None, grupos: list[str] | None) -> tuple[int, int, int, int]:
    d = df
    if sexos:
        d = d[d["sexo"].isin(sexos)]
    if grupos:
        d = d[d["grupo_racial"].isin(grupos)]
    meses = int(df["meses"].max()) if len(df) else 12
    return int(d["obitos"].sum()), int(d["populacao"].sum()), int(d["domicilio"].sum()), meses


def _sexos(f: Filtros) -> list[str] | None:
    return None if f.sexo == "todos" else [f.sexo]


def _razao_racial(df: pd.DataFrame, sexos, alvo: list[str]):
    o_a, p_a, _, m = _recorte(df, sexos, alvo)
    o_b, p_b, _, _ = _recorte(df, sexos, ["Branca"])
    return razao(taxa(o_a, p_a, m), taxa(o_b, p_b, m)), o_a, o_b


def calcular(f: Filtros, anos: dict[int, int]) -> tuple[list[Kpi], list[Kpi]]:
    anteriores = [a for a in anos if a < f.ano]
    ano_ant = max(anteriores) if anteriores else None
    sim, sim_ant = _sim(f, f.ano), (_sim(f, ano_ant) if ano_ant else None)
    sin, sin_ant = _sinesp(f, f.ano), (_sinesp(f, ano_ant) if ano_ant else None)
    sexos = _sexos(f)
    alvo = grupos_alvo(f)
    rotulo_alvo = " + ".join(alvo)
    anual = f" · anualizada (× 12 ÷ {f.meses_sim})" if f.sim_parcial else ""

    o, p, dom, meses = _recorte(sim, sexos, f.grupos or None)
    t = taxa(o, p, meses)
    t_ant = None
    if sim_ant is not None:
        oa, pa, _, ma = _recorte(sim_ant, sexos, f.grupos or None)
        t_ant = taxa(oa, pa, ma)
    k_taxa = Kpi(
        titulo="Óbitos por 100 mil hab.",
        valor=numero(t, 2),
        legenda=f"{numero(o)} óbitos por agressão · população de {numero(p)}{anual}",
        ajuda="SIM ÷ população do Censo 2022 no mesmo recorte × 100 mil (RN10). "
              "Para anos incompletos, multiplica por 12 ÷ meses cobertos (RN11).",
        delta=variacao(t, t_ant, ano_ant), alerta=instavel(o),
    )

    if alvo:
        r, n_a, n_b = _razao_racial(sim, sexos, alvo)
        r_ant = _razao_racial(sim_ant, sexos, alvo)[0] if sim_ant is not None else None
        k_razao = Kpi(
            titulo=f"Risco {rotulo_alvo} ÷ Branca",
            valor=f"{numero(r, 2)}×" if r is not None else "—",
            legenda=f"{numero(n_a)} óbitos ({rotulo_alvo}) · {numero(n_b)} (Branca)",
            ajuda="Taxa do grupo ÷ taxa do grupo branco, com os mesmos filtros de ano, território, sexo e "
                  "idade (RN13). 1,91× = 91% mais risco. Sem raça/cor filtrada, compara a população negra.",
            delta=variacao(r, r_ant, ano_ant, sufixo="×"), alerta=instavel(n_a, n_b),
        )
        rf, nf_a, nf_b = _razao_racial(sim, ["feminino"], alvo)
        rm, nm_a, nm_b = _razao_racial(sim, ["masculino"], alvo)
        k_gap = Kpi(
            titulo="Gap interseccional",
            valor=f"{numero(rf, 2)}× · {numero(rm, 2)}×" if rf is not None and rm is not None else "—",
            legenda=f"Mulheres · homens (risco {rotulo_alvo} ÷ Branca em cada sexo)",
            ajuda="Compara a desigualdade racial dentro de cada sexo (RN14). Ignora o filtro de sexo.",
            delta_cor="off", alerta=instavel(nf_a, nf_b, nm_a, nm_b),
        )
    else:
        motivo = "Selecione um grupo além de Branca/Ignorada para comparar."
        k_razao = Kpi("Risco racial", "—", motivo, "Taxa do grupo ÷ taxa do grupo branco (RN13).")
        k_gap = Kpi("Gap interseccional", "—", motivo,
                    "Compara a desigualdade racial dentro de cada sexo (RN14).", delta_cor="off")

    sexo_dom = ["masculino"] if f.sexo == "masculino" else ["feminino"]
    rotulo_dom = "homens" if f.sexo == "masculino" else "mulheres"
    o_d, _, d_d, _ = _recorte(sim, sexo_dom, f.grupos or None)
    pct = 100 * d_d / o_d if o_d else None
    pct_ant = None
    if sim_ant is not None:
        oa, _, da, _ = _recorte(sim_ant, sexo_dom, f.grupos or None)
        pct_ant = 100 * da / oa if oa else None
    outro = ["feminino"] if sexo_dom == ["masculino"] else ["masculino"]
    o_o, _, d_o, _ = _recorte(sim, outro, f.grupos or None)
    k_dom = Kpi(
        titulo=f"No domicílio · {rotulo_dom}",
        valor=f"{numero(pct, 1)}%" if pct is not None else "—",
        legenda=f"{numero(d_d)} de {numero(o_d)} óbitos de {rotulo_dom} · {'mulheres' if outro == ['feminino'] else 'homens'}: "
                f"{numero(100 * d_o / o_o, 1) + '%' if o_o else '—'}",
        ajuda="Óbitos no domicílio ÷ óbitos do mesmo sexo no recorte (RN15). Entre mulheres, é a "
              "aproximação usual de feminicídio íntimo.",
        delta=variacao(pct, pct_ant, ano_ant, 1, " p.p."), delta_cor="off", alerta=instavel(o_d),
    )

    tf = taxa(sin["feminicidios"], sin["pop_fem"])
    tf_ant = taxa(sin_ant["feminicidios"], sin_ant["pop_fem"]) if sin_ant is not None else None
    k_fem = Kpi(
        titulo="Feminicídios por 100 mil mulheres",
        valor=numero(tf, 2),
        legenda=f"{numero(sin['feminicidios'])} feminicídios registrados pela polícia",
        ajuda="Vítimas de feminicídio (Sinesp) ÷ população feminina do Censo 2022 × 100 mil (RN12).",
        delta=variacao(tf, tf_ant, ano_ant), alerta=instavel(sin["feminicidios"]),
    )

    def pct_mv(s):
        return 100 * s["feminicidios"] / s["mortes_violentas"] if s["mortes_violentas"] else None

    k_mv = Kpi(
        titulo="Tipificadas como feminicídio",
        valor=f"{numero(pct_mv(sin), 1)}%" if pct_mv(sin) is not None else "—",
        legenda=f"{numero(sin['feminicidios'])} de {numero(sin['mortes_violentas'])} mortes violentas de mulheres",
        ajuda="Feminicídios ÷ (feminicídio + homicídio doloso + lesão corporal seguida de morte + "
              "latrocínio), vítimas femininas (RN05, RN16).",
        delta=variacao(pct_mv(sin), pct_mv(sin_ant) if sin_ant is not None else None, ano_ant, 1, " p.p."),
        delta_cor="off", alerta=instavel(sin["mortes_violentas"]),
    )

    def letal(s):
        return 100 * s["fem_com_tentativa"] / s["base_letalidade"] if s["base_letalidade"] else None

    sem = int(sin["ufs_sem_tentativa"])
    k_let = Kpi(
        titulo="Letalidade do feminicídio",
        valor=f"{numero(letal(sin), 1)}%" if letal(sin) is not None else "—",
        legenda="Feminicídios ÷ (feminicídios + tentativas)"
                + (f" · {sem} UF sem registro de tentativas fora do cálculo" if sem else ""),
        ajuda="Proporção das tentativas que terminaram em morte (RN17). UFs que não registram tentativas "
              "no ano ficam de fora, para não sugerir 100% de letalidade.",
        delta=variacao(letal(sin), letal(sin_ant) if sin_ant is not None else None, ano_ant, 1, " p.p."),
        alerta=instavel(sin["base_letalidade"]),
    )
    return [k_taxa, k_razao, k_gap, k_dom], [k_fem, k_mv, k_let]
