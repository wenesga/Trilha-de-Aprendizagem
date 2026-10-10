"""Habilidades da BNCC: lista, descrições e desempenho por habilidade."""

import os
import json
import sqlite3

import streamlit as st

from banco import obter_conexao_db
from config import ARQUIVO_HABILIDADES_BNCC, BNCC_MISSOES_NATIVAS
from conteudos import obter_total_missoes


def obter_bncc_missao(conteudo_id, indice_missao):
    """Habilidade BNCC de uma missão (string vazia se não mapeada).
    indice_missao é 1-based, igual ao usado em progresso['missao_atual']."""
    if conteudo_id in BNCC_MISSOES_NATIVAS:
        return BNCC_MISSOES_NATIVAS[conteudo_id].get(indice_missao, "")
    missoes = st.session_state.conteudos.get(conteudo_id, {}).get("missoes", [])
    if 1 <= indice_missao <= len(missoes):
        return str(missoes[indice_missao - 1].get("bncc", "")).strip()
    return ""


@st.cache_data
def _ler_habilidades_bncc(data_do_arquivo):
    # O parâmetro só existe para o cache se renovar quando o arquivo mudar.
    try:
        with open(ARQUIVO_HABILIDADES_BNCC, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def carregar_habilidades_bncc():
    """{código: descrição oficial} da BNCC do Ensino Médio (e Computação). Dicionário
    vazio se o arquivo não existir — aí os campos de habilidade voltam a ser texto livre."""
    try:
        data = os.path.getmtime(ARQUIVO_HABILIDADES_BNCC)
    except OSError:
        data = 0
    return _ler_habilidades_bncc(data)


def descricao_curta_bncc(codigo, limite=85):
    """Começo da descrição oficial, cortado numa palavra inteira. Vazio se o
    código não está no banco (por exemplo, um código digitado à mão antes)."""
    texto = carregar_habilidades_bncc().get(str(codigo).strip(), "")
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def rotulo_habilidade_bncc(codigo):
    """'EM13MAT316 · Resolver e elaborar problemas…' (ou só o código, se não houver descrição)."""
    curta = descricao_curta_bncc(codigo)
    return f"{codigo} · {curta}" if curta else str(codigo)


def campo_habilidade_bncc(rotulo, valor_atual="", chave=None, ajuda=""):
    """Campo de habilidade BNCC: lista pesquisável (código + descrição curta) quando
    o banco existe; texto livre quando não. Devolve só o código ('' se vazio)."""
    habilidades = carregar_habilidades_bncc()
    valor_atual = str(valor_atual or "").strip()
    if not habilidades:
        return st.text_input(rotulo, value=valor_atual, placeholder="Ex.: EM13MAT316", key=chave, help=ajuda).strip()
    opcoes = sorted(habilidades)
    if valor_atual and valor_atual not in habilidades:
        opcoes.append(valor_atual)  # código antigo, digitado à mão: não some do cadastro
    indice = opcoes.index(valor_atual) if valor_atual else None
    escolhida = st.selectbox(
        rotulo, opcoes, index=indice, key=chave, help=ajuda,
        # Rótulo com a descrição inteira, pois o Streamlit só pesquisa dentro do rótulo.
        format_func=lambda c: f"{c} · {habilidades[c]}" if c in habilidades else c,
        placeholder="Digite o código ou uma palavra da habilidade",
    )
    return (escolhida or "").strip()


def habilidades_bncc_do_conteudo(cid, c):
    """
    Códigos BNCC (sem repetição, ordenados) usados pelas missões de um conteúdo, nativo ou
    cadastrado. Lista vazia se nenhuma missão foi mapeada. Usado só no Painel do Professor
    (planejamento curricular).
    """
    if cid in BNCC_MISSOES_NATIVAS:
        return sorted(set(BNCC_MISSOES_NATIVAS[cid].values()))
    codigos = {str(m.get("bncc", "")).strip() for m in c.get("missoes", [])}
    codigos.discard("")
    return sorted(codigos)


def desempenho_por_bncc(alunos, conteudo_id=None):
    """
    Agrega o progresso da turma por habilidade da BNCC (de um conteúdo, se conteudo_id for dado).

    Retorna [{Habilidade, Missões, Conclusões, Possíveis, % Concluído}]: 'Conclusões' conta cada par
    (aluno, missão concluída) das missões com aquela habilidade, e 'Possíveis' é o total se todos
    concluíssem tudo.

    O banco guarda onde o aluno parou (missao_atual) e o total de erros, não o acerto de cada
    missão. 'Concluída' significa 'o aluno passou por ela', o que na trilha só ocorre após acertar;
    não equivale a 'acertou de primeira'.
    """
    acumulado = {}
    for cid in st.session_state.conteudos:
        if conteudo_id and cid != conteudo_id:
            continue
        total_missoes = obter_total_missoes(cid)
        for idx in range(1, total_missoes + 1):
            habilidade = obter_bncc_missao(cid, idx)
            if not habilidade:
                continue
            registro = acumulado.setdefault(habilidade, {"missoes": 0, "feitas": 0, "possiveis": 0})
            registro["missoes"] += 1
            for perfil in alunos.values():
                prog = perfil.get("progresso", {}).get(cid, {"missao_atual": 1})
                concluidas = max(prog.get("missao_atual", 1) - 1, 0)
                registro["possiveis"] += 1
                if idx <= concluidas:
                    registro["feitas"] += 1

    linhas = []
    for habilidade in sorted(acumulado):
        r = acumulado[habilidade]
        pct = (r["feitas"] / r["possiveis"] * 100) if r["possiveis"] else 0
        linhas.append({
            "Habilidade": habilidade,
            "Missões": r["missoes"],
            "Conclusões": r["feitas"],
            "Possíveis": r["possiveis"],
            "% Concluído": round(pct),
        })
    return linhas


def acerto_por_aluno_e_habilidade(conteudo_id=None):
    """Acerto de cada aluno em cada habilidade da BNCC, a partir das tentativas
    (só as de um conteúdo, se conteudo_id for dado).

    Retorna (acertos, desde): acertos é {(aluno, habilidade): [acertos, tentativas]}
    e desde é o dia (AAAA-MM-DD) da primeira tentativa gravada, ou '' se não há
    nenhuma. Acerto = respostas certas ÷ todas as tentativas (cada erro conta como
    uma tentativa), só das missões que têm habilidade mapeada."""
    acertos = {}
    desde = ""
    try:
        conn = obter_conexao_db()
        try:
            linhas = conn.execute(
                "SELECT aluno, conteudo_id, missao, acertou, momento FROM tentativas_missao"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return acertos, desde
    for linha in linhas:
        if conteudo_id and linha["conteudo_id"] != conteudo_id:
            continue
        if not desde or linha["momento"] < desde:
            desde = linha["momento"]
        habilidade = obter_bncc_missao(linha["conteudo_id"], linha["missao"])
        if not habilidade:
            continue
        par = acertos.setdefault((linha["aluno"], habilidade), [0, 0])
        par[0] += linha["acertou"]
        par[1] += 1
    return acertos, desde
