"""Leitura e gravação dos conteúdos cadastrados, dados de Estatística e contas de XP."""

import os
import json

import streamlit as st

from config import (
    ARQUIVO_CONTEUDOS,
    ARQUIVO_DADOS_ESTATISTICA,
    IDS_ESTATISTICA_HUB,
    ID_CONTEUDO_COMPARACAO,
    ID_CONTEUDO_ESTATISTICA,
    ID_CONTEUDO_FREQUENCIA,
    ID_CONTEUDO_LEITURA_GRAFICA,
    ID_CONTEUDO_PESQUISA_AMOSTRAL,
    ID_CONTEUDO_TENDENCIA,
    TOTAL_MISSOES_NATIVAS,
    XP_MAXIMO_CONTEUDO_NATIVO,
    XP_MAXIMO_POR_CONTEUDO_NATIVO,
)


# ---------- Conteúdos (menu / sumário) ----------
def conteudo_padrao_estatistica():
    return {
        "titulo": "Estatística Descritiva",
        "icone": "📊",
        "tipo": "estatico",  # conteúdo nativo: cálculo dinâmico a partir dos dados da turma
        "descricao": "Medidas de tendência central e dispersão calculadas sobre um conjunto de dados."
    }

def conteudo_padrao_frequencia():
    return {
        "titulo": "Tabela e Gráfico de Frequência",
        "icone": "📶",
        "tipo": "estatico",  # conteúdo nativo: mesma amostra da Estatística Descritiva, agrupada em faixas
        "descricao": "Organize uma amostra em faixas e leia o gráfico de frequência resultante."
    }

def conteudo_padrao_leitura_grafica():
    return {
        "titulo": "Leitura Crítica de Gráficos",
        "icone": "🔍",
        "tipo": "estatico",  # conteúdo nativo: cenário fixo, não depende dos dados da turma
        "descricao": "Aprenda a desconfiar de gráfico e pesquisa da mídia: escala manipulada e amostra não representativa."
    }

def conteudo_padrao_comparacao():
    return {
        "titulo": "Comparando Diagramas",
        "icone": "📦",
        "tipo": "estatico",  # conteúdo nativo: mesma amostra da Estatística Descritiva, em 3 diagramas diferentes
        "descricao": "Histograma, box-plot e ramos-e-folhas: três formas de olhar pra mesma amostra, cada uma boa pra uma pergunta diferente."
    }

def conteudo_padrao_pesquisa_amostral():
    return {
        "titulo": "Planejando uma Pesquisa",
        "icone": "📋",
        "tipo": "estatico",  # conteúdo nativo: decisões de planejamento, não cálculo — reusa a amostra da turma
        "descricao": "População x amostra, e como os dados de uma amostra viram um relatório de verdade: da coleta até as medidas."
    }

def conteudo_padrao_tendencia():
    return {
        "titulo": "Relação entre Duas Variáveis",
        "icone": "📈",
        "tipo": "estatico",  # conteúdo nativo: cenário fixo próprio, não depende dos dados da turma
        "descricao": "Horas de estudo e nota: como duas variáveis se relacionam, e como uma reta ajuda a enxergar (e prever) essa relação."
    }

def carregar_conteudos():
    conteudos = {}
    if os.path.exists(ARQUIVO_CONTEUDOS):
        try:
            with open(ARQUIVO_CONTEUDOS, "r", encoding="utf-8") as f:
                conteudos = json.load(f)
        except Exception:
            conteudos = {}
    if ID_CONTEUDO_ESTATISTICA not in conteudos:
        conteudos[ID_CONTEUDO_ESTATISTICA] = conteudo_padrao_estatistica()
    if ID_CONTEUDO_FREQUENCIA not in conteudos:
        conteudos[ID_CONTEUDO_FREQUENCIA] = conteudo_padrao_frequencia()
    if ID_CONTEUDO_LEITURA_GRAFICA not in conteudos:
        conteudos[ID_CONTEUDO_LEITURA_GRAFICA] = conteudo_padrao_leitura_grafica()
    if ID_CONTEUDO_COMPARACAO not in conteudos:
        conteudos[ID_CONTEUDO_COMPARACAO] = conteudo_padrao_comparacao()
    if ID_CONTEUDO_PESQUISA_AMOSTRAL not in conteudos:
        conteudos[ID_CONTEUDO_PESQUISA_AMOSTRAL] = conteudo_padrao_pesquisa_amostral()
    if ID_CONTEUDO_TENDENCIA not in conteudos:
        conteudos[ID_CONTEUDO_TENDENCIA] = conteudo_padrao_tendencia()
    """
    Nativos agrupados no topo, na ordem de IDS_ESTATISTICA_HUB, como ponto de partida.
    mover_conteudo() permite reordenar qualquer card depois.
    """
    conteudos = {
        **{cid: conteudos[cid] for cid in IDS_ESTATISTICA_HUB if cid in conteudos},
        **{cid: c for cid, c in conteudos.items() if cid not in IDS_ESTATISTICA_HUB},
    }
    return conteudos

def salvar_conteudos(conteudos):
    with open(ARQUIVO_CONTEUDOS, "w", encoding="utf-8") as f:
        json.dump(conteudos, f, ensure_ascii=False, indent=2)


# ---------- Dados numéricos usados pelo conteúdo nativo de Estatística ----------
def carregar_dados_estatistica():
    if os.path.exists(ARQUIVO_DADOS_ESTATISTICA):
        try:
            with open(ARQUIVO_DADOS_ESTATISTICA, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return [8.5, 7.0, 9.2, 6.5, 10.0, 5.5, 8.0, 7.0]

def salvar_dados_estatistica(lista_dados):
    with open(ARQUIVO_DADOS_ESTATISTICA, "w") as f:
        json.dump(lista_dados, f)


def xp_maximo_de_conteudo(cid, c):
    """
    XP máximo de um conteúdo, acertando tudo de primeira: nativo (tabela acima) ou cadastrado (soma
    o "Pontos (XP)" de cada missão). Usado no badge "Total X XP" de cada card (Gerenciar Conteúdos)
    e no seletor de "Meta de XP" em Configurações.
    """
    if cid in XP_MAXIMO_POR_CONTEUDO_NATIVO:
        return XP_MAXIMO_POR_CONTEUDO_NATIVO[cid]
    return sum(m.get("pontos", 10) for m in c.get("missoes", []))


def xp_maximo_catalogo_atual():
    """
    (nativo, cadastrado, total): XP máximo de todo o catálogo atual, separado por grupo. É
    recalculado a cada chamada, então acompanha novos conteúdos. Aparece em Configurações como
    referência para definir a Meta de XP.
    """
    nativo = XP_MAXIMO_CONTEUDO_NATIVO
    cadastrado = sum(
        xp_maximo_de_conteudo(cid, c)
        for cid, c in st.session_state.conteudos.items()
        if c["tipo"] != "estatico"
    )
    return nativo, cadastrado, nativo + cadastrado


def obter_total_missoes(conteudo_id):
    if conteudo_id in TOTAL_MISSOES_NATIVAS:
        return TOTAL_MISSOES_NATIVAS[conteudo_id]
    conteudo = st.session_state.conteudos.get(conteudo_id, {})
    return len(conteudo.get("missoes", []))
