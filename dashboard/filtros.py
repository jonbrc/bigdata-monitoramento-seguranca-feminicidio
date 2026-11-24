"""Filtros cruzados do dashboard: opções lidas do banco, widgets da barra lateral, persistência na URL e montagem segura (parametrizada) das cláusulas WHERE."""

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

import db

SEXOS = {"todos": "Todos", "feminino": "Mulheres", "masculino": "Homens"}
CHAVES = {"ano": "f_ano", "regiao": "f_regiao", "uf": "f_uf", "sexo": "f_sexo",
          "raca": "f_raca", "faixa": "f_faixa"}
LISTAS = {"regiao", "uf", "raca", "faixa"}


@dataclass
class Opcoes:
    anos: dict[int, int]
    ufs: pd.DataFrame
    grupos: list[str]
    faixas: dict[str, str]

    @property
    def regioes(self) -> list[str]:
        return list(dict.fromkeys(self.ufs["regiao"]))

    def ufs_de(self, regioes: list[str]) -> list[str]:
        base = self.ufs if not regioes else self.ufs[self.ufs["regiao"].isin(regioes)]
        return base["sigla_uf"].tolist()

    def nome_uf(self, sigla: str) -> str:
        return self.ufs.set_index("sigla_uf").at[sigla, "nome_uf"]


@dataclass
class Filtros:
    ano: int
    meses_sim: int
    regioes: list[str] = field(default_factory=list)
    ufs: list[str] = field(default_factory=list)
    sexo: str = "todos"
    grupos: list[str] = field(default_factory=list)
    faixas: list[str] = field(default_factory=list)

    @property
    def sim_parcial(self) -> bool:
        return self.meses_sim < 12

    def where(self, colunas: dict[str, str] | None = None, perfil: bool = True,
              ano: int | None = None, ignorar: tuple[str, ...] = ()) -> tuple[str, list]:
        c = {"ano": "ano", "regiao": "regiao", "uf": "sigla_uf", "sexo": "sexo",
             "grupo": "grupo_racial", "faixa": "faixa_etaria", **(colunas or {})}
        partes, params = ["TRUE"], []
        if "ano" not in ignorar:
            partes, params = [f"{c['ano']} = %s"], [ano or self.ano]
        filtros = [("regiao", self.regioes), ("uf", self.ufs)]
        if perfil:
            filtros += [(k, v) for k, v in (("grupo", self.grupos), ("faixa", self.faixas)) if k not in ignorar]
            if self.sexo != "todos" and "sexo" not in ignorar:
                partes.append(f"{c['sexo']} = %s")
                params.append(self.sexo)
        for chave, valores in filtros:
            if valores:
                partes.append(f"{c[chave]} = ANY(%s)")
                params.append(list(valores))
        return " AND ".join(partes), params

    def resumo(self, opcoes: Opcoes) -> str:
        itens = [str(self.ano)]
        if self.ufs:
            itens.append(", ".join(self.ufs))
        elif self.regioes:
            itens.append(", ".join(self.regioes))
        else:
            itens.append("Brasil")
        itens.append("Ambos os sexos" if self.sexo == "todos" else SEXOS[self.sexo])
        itens.append(", ".join(self.grupos) if self.grupos else "Todas as raças/cores")
        itens.append(", ".join(opcoes.faixas[f] for f in self.faixas) if self.faixas else "Todas as idades")
        return " · ".join(itens)


@st.cache_data(ttl=db.CACHE_SEGUNDOS, show_spinner=False)
def carregar_opcoes() -> Opcoes:
    anos = db.consultar("""
        SELECT ano, COUNT(*) FILTER (WHERE sim_periodo_coberto) AS meses_sim
        FROM dim_tempo GROUP BY ano ORDER BY ano""")
    ufs = db.consultar("""
        SELECT sigla_uf, nome_uf, regiao FROM dim_uf
        ORDER BY CASE regiao WHEN 'Norte' THEN 1 WHEN 'Nordeste' THEN 2 WHEN 'Sudeste' THEN 3
                             WHEN 'Sul' THEN 4 ELSE 5 END, nome_uf""")
    grupos = db.consultar("SELECT grupo FROM dim_raca_cor GROUP BY grupo ORDER BY MIN(ordem)")
    faixas = db.consultar("SELECT codigo, descricao FROM dim_faixa_etaria ORDER BY ordem")
    return Opcoes(
        anos={int(a): int(m) for a, m in zip(anos["ano"], anos["meses_sim"])},
        ufs=ufs,
        grupos=grupos["grupo"].tolist(),
        faixas=dict(zip(faixas["codigo"], faixas["descricao"])),
    )


def _padroes(opcoes: Opcoes) -> dict:
    completos = [a for a, m in opcoes.anos.items() if m == 12]
    return {"ano": max(completos or opcoes.anos), "regiao": [], "uf": [], "sexo": "todos",
            "raca": [], "faixa": []}


def _validar(nome: str, valor, opcoes: Opcoes, regioes: list[str] | None = None):
    validos = {
        "ano": list(opcoes.anos),
        "regiao": opcoes.regioes,
        "uf": opcoes.ufs_de(regioes or []),
        "sexo": list(SEXOS),
        "raca": opcoes.grupos,
        "faixa": list(opcoes.faixas),
    }[nome]
    if nome in LISTAS:
        return [v for v in valor if v in validos]
    return valor if valor in validos else None


def _ler_url(opcoes: Opcoes) -> dict:
    estado = _padroes(opcoes)
    for nome in ("ano", "sexo"):
        bruto = st.query_params.get(nome)
        if bruto is not None:
            valor = int(bruto) if nome == "ano" and bruto.isdigit() else bruto
            estado[nome] = _validar(nome, valor, opcoes) or estado[nome]
    for nome in ("regiao", "raca", "faixa"):
        estado[nome] = _validar(nome, st.query_params.get_all(nome), opcoes)
    estado["uf"] = _validar("uf", st.query_params.get_all("uf"), opcoes, estado["regiao"])
    return estado


def _gravar_url(estado: dict, padroes: dict) -> None:
    novos = {nome: [str(v) for v in valor] if nome in LISTAS else [str(valor)]
             for nome, valor in estado.items() if valor != padroes[nome] and valor not in (None, [])}
    atuais = {nome: st.query_params.get_all(nome) for nome in st.query_params}
    if atuais != novos:
        st.query_params.from_dict(novos)


def _manter_selecao(chave: str, padrao) -> None:
    if st.session_state.get(chave) is None:
        st.session_state[chave] = padrao


def _limpar(opcoes: Opcoes) -> None:
    for nome, valor in _padroes(opcoes).items():
        st.session_state[CHAVES[nome]] = valor
    st.query_params.clear()


def barra_lateral(opcoes: Opcoes) -> Filtros:
    padroes = _padroes(opcoes)
    if "filtros_iniciados" not in st.session_state:
        for nome, valor in _ler_url(opcoes).items():
            st.session_state[CHAVES[nome]] = valor
        st.session_state["filtros_iniciados"] = True

    with st.sidebar:
        st.header("Filtros")

        ano = st.segmented_control(
            "Ano", options=list(opcoes.anos), key=CHAVES["ano"],
            on_change=_manter_selecao, args=(CHAVES["ano"], padroes["ano"]),
            format_func=lambda a: f"{a}" if opcoes.anos[a] == 12 else f"{a} (SIM parcial)",
        ) or padroes["ano"]

        st.markdown("**Território**")
        regioes = st.multiselect("Região", opcoes.regioes, key=CHAVES["regiao"], placeholder="Todas")
        validas = opcoes.ufs_de(regioes)
        st.session_state[CHAVES["uf"]] = [u for u in st.session_state.get(CHAVES["uf"], []) if u in validas]
        ufs = st.multiselect(
            "UF", validas, key=CHAVES["uf"], placeholder="Todas",
            format_func=lambda s: f"{s} · {opcoes.nome_uf(s)}",
        )

        st.markdown("**Perfil das vítimas**")
        sexo = st.segmented_control(
            "Sexo", options=list(SEXOS), key=CHAVES["sexo"], format_func=SEXOS.get,
            on_change=_manter_selecao, args=(CHAVES["sexo"], padroes["sexo"]),
        ) or padroes["sexo"]
        grupos = st.multiselect(
            "Raça/cor", opcoes.grupos, key=CHAVES["raca"], placeholder="Todas",
            help="Negra = preta + parda (padrão do IBGE).",
        )
        faixas = st.multiselect(
            "Faixa etária", list(opcoes.faixas), key=CHAVES["faixa"], placeholder="Todas",
            format_func=opcoes.faixas.get,
        )
        st.caption(
            "Sexo, raça/cor e faixa etária existem só no SIM (Ministério da Saúde). "
            "Os dados do Sinesp seguem apenas os filtros de ano e território."
        )

        st.button("Limpar filtros", on_click=_limpar, args=(opcoes,), use_container_width=True,
                  disabled=all(st.session_state[CHAVES[n]] == v for n, v in padroes.items()))

    estado = {"ano": ano, "regiao": regioes, "uf": ufs, "sexo": sexo, "raca": grupos, "faixa": faixas}
    _gravar_url(estado, padroes)
    return Filtros(ano=ano, meses_sim=opcoes.anos[ano], regioes=regioes, ufs=ufs, sexo=sexo,
                   grupos=grupos, faixas=faixas)
