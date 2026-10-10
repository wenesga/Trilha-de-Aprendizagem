"""Página de uma matéria."""

import streamlit as st

from banco import perfil_atual, progresso_atual
from config import (
    ABA_MISSOES,
    ABA_TEORIA,
    IDS_ESTATISTICA_HUB,
    ID_CONTEUDO_COMPARACAO,
    ID_CONTEUDO_ESTATISTICA,
    ID_CONTEUDO_FREQUENCIA,
    ID_CONTEUDO_LEITURA_GRAFICA,
    ID_CONTEUDO_PESQUISA_AMOSTRAL,
    ID_CONTEUDO_TENDENCIA,
    PAGINA_INICIO,
)
from conteudos import obter_total_missoes
from missoes import renderizar_ultimo_resultado
from paginas.teoria import (
    render_pagina_comparacao_diagramas,
    render_pagina_conteudo_dinamico,
    render_pagina_estatistica,
    render_pagina_frequencia,
    render_pagina_leitura_grafica,
    render_pagina_pesquisa_amostral,
    render_pagina_tendencia,
)
from paginas.trilha_missoes import (
    render_missoes_comparacao_diagramas,
    render_missoes_dinamicas,
    render_missoes_estatistica,
    render_missoes_frequencia,
    render_missoes_leitura_grafica,
    render_missoes_pesquisa_amostral,
    render_missoes_tendencia,
)
from sessao import ir_para_hub_estatistica


def render_pagina_materia():
    """Página de uma matéria: voltar, título, botões Teoria/Missões e o conteúdo da aba."""
    if st.session_state.conteudo_ativo not in st.session_state.conteudos:
        st.session_state.conteudo_ativo = ID_CONTEUDO_ESTATISTICA
    cid = st.session_state.conteudo_ativo
    conteudo = st.session_state.conteudos[cid]

    """
    Botão "← Voltar" em toda matéria: o botão Voltar do navegador não ajuda (o app é uma SPA, sem
    "página anterior"). Os 6 sub-temas de Estatística voltam para o hub; as demais matérias
    (cadastradas) voltam para a Início, único lugar de onde são abertas.
    """
    if st.button("← Voltar", key="voltar_materia"):
        if cid in IDS_ESTATISTICA_HUB:
            ir_para_hub_estatistica()
        else:
            st.session_state.pagina = PAGINA_INICIO
            st.rerun()

    st.title(f"{conteudo['icone']} {conteudo['titulo']}")

    """
    Teoria x Missões é uma troca dentro da matéria (a mais frequente do app), por isso fica junto ao
    conteúdo e não no menu lateral. Usa dois botões em vez de st.segmented_control, que desmarca a
    opção ao clicar nela de novo (vira None), e aqui sempre há uma seção selecionada. Os botões
    também mantêm a linguagem visual do menu lateral (ativo = type="primary").
    """
    col_teoria, col_missoes, _ = st.columns([1, 1, 3])
    with col_teoria:
        if st.button(ABA_TEORIA, use_container_width=True, key="aba_btn_teoria",
                     type="primary" if st.session_state.aba_materia == ABA_TEORIA else "secondary"):
            st.session_state.aba_materia = ABA_TEORIA
            st.rerun()
    with col_missoes:
        rotulo_missoes = ABA_MISSOES
        total_missoes = obter_total_missoes(cid)
        if st.session_state.aluno_ativo and total_missoes:
            feitas = min(max(progresso_atual(cid)["missao_atual"] - 1, 0), total_missoes)
            rotulo_missoes += f"  {feitas}/{total_missoes}"
        if st.button(rotulo_missoes, use_container_width=True, key="aba_btn_missoes",
                     type="primary" if st.session_state.aba_materia == ABA_MISSOES else "secondary"):
            st.session_state.aba_materia = ABA_MISSOES
            st.rerun()

    st.markdown("")

    if st.session_state.aba_materia == ABA_MISSOES:
        if not st.session_state.aluno_ativo:
            st.warning("⚠️ Olá! Escolha um apelido na barra lateral à esquerda para carregar o seu perfil e começar a ganhar XP.")
        else:
            """
            Selo de XP em destaque no topo da Trilha de Missões — um lugar só, vale tanto pro
            conteúdo nativo de Estatística quanto pros cadastrados pelo professor, sem duplicar em
            cada função de missão.
            """
            xp_atual = perfil_atual()["xp_total"]
            st.markdown(
                f'<div class="xp-destaque-missoes">'
                f'<span class="icone">🏆</span><span class="valor">{xp_atual} XP</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if cid == ID_CONTEUDO_ESTATISTICA:
                render_missoes_estatistica()
            elif cid == ID_CONTEUDO_FREQUENCIA:
                render_missoes_frequencia()
            elif cid == ID_CONTEUDO_LEITURA_GRAFICA:
                render_missoes_leitura_grafica()
            elif cid == ID_CONTEUDO_COMPARACAO:
                render_missoes_comparacao_diagramas()
            elif cid == ID_CONTEUDO_PESQUISA_AMOSTRAL:
                render_missoes_pesquisa_amostral()
            elif cid == ID_CONTEUDO_TENDENCIA:
                render_missoes_tendencia()
            else:
                render_missoes_dinamicas(conteudo)
            """
            Embaixo, não em cima: é onde o olhar do aluno já está depois de clicar em "Verificar
            Resposta" (mesma posição do "❌ Resposta incorreta", que fica logo abaixo do botão). Uma
            versão anterior mostrava isso no topo, junto do selo de XP — só visível rolando a tela
            pra cima, o que recriava o mesmo problema de antes (informação fora de vista), só que em
            vez de sumir rápido, ficava escondida longe do clique.
            """
            renderizar_ultimo_resultado(cid)
    elif cid == ID_CONTEUDO_ESTATISTICA:
        render_pagina_estatistica()
    elif cid == ID_CONTEUDO_FREQUENCIA:
        render_pagina_frequencia()
    elif cid == ID_CONTEUDO_LEITURA_GRAFICA:
        render_pagina_leitura_grafica()
    elif cid == ID_CONTEUDO_COMPARACAO:
        render_pagina_comparacao_diagramas()
    elif cid == ID_CONTEUDO_PESQUISA_AMOSTRAL:
        render_pagina_pesquisa_amostral()
    elif cid == ID_CONTEUDO_TENDENCIA:
        render_pagina_tendencia()
    else:
        render_pagina_conteudo_dinamico(conteudo)
