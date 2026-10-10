"""Página inicial e hub de Estatística."""

import os

import streamlit as st

from banco import perfil_atual, progresso_resumo_aluno, ranking_turma
from config import ARQUIVO_BANNER, IDS_ESTATISTICA_HUB, PAGINA_INICIO, PALETA_CORES_CARTAO
from conteudos import obter_total_missoes
from estilo import obter_logo_base64
from sessao import ir_para_hub_estatistica, ir_para_materia


@st.fragment(run_every="5s")
def render_placar_turma():
    """
    Placar da turma: apelido + XP, atualizando sozinho.

    @st.fragment(run_every="5s") recarrega só este bloco a cada 5 segundos, sem repintar a página
    nem interromper o aluno no meio de uma missão. Não é push: cada navegador consulta o banco, e
    com uma turma pequena e a consulta enxuta de ranking_turma() a carga é desprezível.

    Exibir o desempenho em público só é aceitável porque o aluno entra com apelido: o objetivo não é
    o anonimato, é não expor o nome de quem está por trás.
    """
    placar = ranking_turma()
    if not placar:
        return

    eu = st.session_state.aluno_ativo
    medalhas = {1: "🥇", 2: "🥈", 3: "🥉"}
    linhas_html = []
    for posicao, (apelido, xp) in enumerate(placar, start=1):
        destaque = " eu" if apelido == eu else ""
        marcador = medalhas.get(posicao, f"{posicao}º")
        linhas_html.append(
            f'<div class="placar-linha{destaque}">'
            f'<span class="placar-pos">{marcador}</span>'
            f'<span class="placar-nome">{apelido}</span>'
            f'<span class="placar-xp">{xp} XP</span>'
            f"</div>"
        )
    st.markdown(
        f'<div class="placar-caixa">{"".join(linhas_html)}</div>',
        unsafe_allow_html=True,
    )
    if not eu:
        st.caption("Entre com um apelido na barra lateral para aparecer no placar.")


def renderizar_grade_cartoes(cartoes, prefixo_key):
    """
    Grade de cartões (ícone, título, descrição, botão "Acessar →"), 3 por linha. cartoes é uma lista
    de dicts {icone, titulo, descricao, on_click, progresso}. on_click é uma função sem argumento
    chamada ao clicar (abre uma matéria ou o hub de Estatística). "progresso" é opcional ("3/8" ou
    "✓") e mostra quantas missões daquele card já foram concluídas, pois o "8/44" do menu lateral
    soma os 6 sub-temas de Estatística.

    Usada nos "Conteúdos disponíveis" da Início e nos 6 sub-temas do hub de Estatística; prefixo_key
    garante keys únicas quando a mesma matéria aparece nas duas telas.
    """
    for inicio_linha in range(0, len(cartoes), 3):
        colunas = st.columns(3)
        for i, cartao in enumerate(cartoes[inicio_linha:inicio_linha + 3]):
            idx_global = inicio_linha + i
            cor = PALETA_CORES_CARTAO[idx_global % len(PALETA_CORES_CARTAO)]
            with colunas[i]:
                with st.container(border=True, key=f"{prefixo_key}_cartao_{idx_global}_cor_{cor}"):
                    titulo_linha = f"#### {cartao['icone']} {cartao['titulo']}"
                    if cartao.get("progresso"):
                        titulo_linha += f"  ·  {cartao['progresso']}"
                    st.markdown(titulo_linha)
                    st.caption(cartao.get("descricao", ""))
                    if st.button("Acessar →", key=f"{prefixo_key}_btn_{idx_global}", use_container_width=True):
                        cartao["on_click"]()


def render_pagina_estatistica_hub():
    if st.button("← Voltar", key="voltar_inicio_hub"):
        st.session_state.pagina = PAGINA_INICIO
        st.rerun()
    st.title("📊 Estatística")
    st.markdown("Escolha o tema que você quer estudar.")
    st.write("---")
    concluidas_por_conteudo = progresso_resumo_aluno()
    cartoes = []
    for cid in IDS_ESTATISTICA_HUB:
        total = obter_total_missoes(cid)
        progresso = None
        if st.session_state.aluno_ativo and total:
            feitas = min(concluidas_por_conteudo.get(cid, 0), total)
            progresso = "✓" if feitas >= total else f"{feitas}/{total}"
        cartoes.append({
            "icone": st.session_state.conteudos[cid]["icone"],
            "titulo": st.session_state.conteudos[cid]["titulo"],
            "descricao": st.session_state.conteudos[cid].get("descricao", ""),
            "on_click": (lambda cid=cid: ir_para_materia(cid)),
            "progresso": progresso,
        })
    renderizar_grade_cartoes(cartoes, prefixo_key="hub_estatistica")


def render_pagina_inicial():
    aluno = st.session_state.aluno_ativo

    if aluno:
        perfil = perfil_atual()
        saudacao = f"Bem-vindo(a) de volta, {aluno}! 🏆 Você já tem {perfil['xp_total']} XP acumulados."
    else:
        saudacao = "Escolha um apelido na barra lateral para começar a acumular XP e salvar seu progresso."

    logo_b64 = obter_logo_base64()
    if logo_b64:
        logo_html = f'<img class="home-banner-logo-img" src="data:image/svg+xml;base64,{logo_b64}" alt="Logo" />'
    else:
        logo_html = '<div class="home-banner-logo">🎓</div>'

    if os.path.exists(ARQUIVO_BANNER):
        st.image(ARQUIVO_BANNER, use_container_width=True)
        st.markdown(f"##### {saudacao}")
    else:
        st.markdown(f"""
        <div class="home-banner">
            {logo_html}
            <p class="home-banner-titulo">Trilha de Aprendizagem</p>
            <p class="home-banner-subtitulo">
                Uma plataforma interativa e gamificada para estudar qualquer disciplina —
                de Estatística a Probabilidade, Equações, História ou o que o seu professor cadastrar.
                {saudacao}
            </p>
        </div>
        """, unsafe_allow_html=True)

    """
    Dentro de um expander, fechado por padrão, para quem tiver curiosidade. Cada navegador é uma
    sessão isolada: abrir ou fechar no computador do professor não afeta o celular de nenhum aluno.
    Também evita uma lista longa antes do resto da página em turmas grandes.
    """
    with st.expander("🏆 Placar da Turma", expanded=False):
        render_placar_turma()
    st.write("")

    st.markdown("### 🧭 Como funciona")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="home-step-card">
            <div class="home-step-numero">Passo 1</div>
            <div class="home-step-titulo">📚 Escolha uma matéria</div>
            <div class="home-step-texto">Clique em uma das matérias na barra lateral (ou nos cartões abaixo) para abrir a disciplina que quer estudar.</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="home-step-card">
            <div class="home-step-numero">Passo 2</div>
            <div class="home-step-titulo">📖 Estude a teoria</div>
            <div class="home-step-texto">Veja as explicações passo a passo antes de partir para os desafios.</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="home-step-card">
            <div class="home-step-numero">Passo 3</div>
            <div class="home-step-titulo">🎮 Jogue as Missões</div>
            <div class="home-step-texto">Na própria matéria, troque para a aba Missões: responda os desafios, ganhe XP e acompanhe seu progresso.</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.markdown("### 📚 Conteúdos disponíveis")
    st.caption("Clique para ir direto ao conteúdo.")

    """
    Os 3 conteúdos nativos de Estatística viram um único cartão ("📊 Estatística"), desenhado à mão
    porque a ação dele abre o hub, não uma matéria. O resto vem dos conteúdos reais, via
    renderizar_grade_cartoes.
    """
    cartoes = [{
        "icone": "📊", "titulo": "Estatística",
        "descricao": "Escolha o tema que você quer estudar.",
        "on_click": ir_para_hub_estatistica,
    }]
    for cid in st.session_state.conteudos:
        if cid in IDS_ESTATISTICA_HUB:
            continue
        info = st.session_state.conteudos[cid]
        cartoes.append({
            "icone": info["icone"], "titulo": info["titulo"], "descricao": info.get("descricao", ""),
            "on_click": (lambda cid=cid: ir_para_materia(cid)),
        })
    renderizar_grade_cartoes(cartoes, prefixo_key="home")

    if not aluno:
        st.info("💡 Dica: professores encontram o cadastro de novos conteúdos e as senhas em **🛡️ Painel do Professor**, na barra lateral.")
