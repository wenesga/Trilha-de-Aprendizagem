"""Painel do Professor: autenticação e abas."""

import streamlit as st

from config import ABA_PROFESSOR_CONFIG, ABA_PROFESSOR_CONTEUDOS, ABA_PROFESSOR_VISAO, PAGINA_INICIO
from configuracao import senha_correta
from paginas.professor_config import render_configuracoes
from paginas.professor_conteudos import render_gerenciar_conteudos
from paginas.professor_visao import render_desempenho_turma
from sessao import abrir_sessao_professor, encerrar_sessao_professor, sessao_professor_ativa




def render_pagina_professor():
    """Painel do Professor: senha, abas e o conteúdo da aba escolhida."""
    """
    "← Voltar" para a Início só troca de tela, sem encerrar a sessão do professor (se estiver
    autenticado, continua dentro do prazo de 30 min); "🚪 Sair" encerra de propósito, para passar o
    computador a um aluno com segurança.
    """
    if st.button("← Voltar", key="voltar_professor"):
        st.session_state.pagina = PAGINA_INICIO
        st.rerun()

    st.title("🛡️ Painel do Professor")

    if not sessao_professor_ativa():
        st.warning("🔒 Esta área é restrita ao professor. Digite a senha para continuar.")
        senha_digitada = st.text_input("Senha:", type="password", key="senha_professor_input")
        if st.button("🔓 Entrar"):
            if senha_correta(senha_digitada, st.session_state.config):
                abrir_sessao_professor()
                st.rerun()
            else:
                st.error("❌ Senha incorreta.")
    else:
        """
        Renova o prazo a cada uso do painel: o tempo passa a contar do último uso, não do login,
        então a sessão não expira no meio de um cadastro.
        """
        abrir_sessao_professor()
        _, colB = st.columns([4, 1])
        with colB:
            """
            Empurra o botão para a borda direita sem esticá-lo: use_container_width=True alargaria o
            botão até preencher a coluna. O container vira flex com justify-content:flex-end, que
            leva o botão, do próprio tamanho, até a ponta.
            """
            with st.container(key="acao_sair_professor"):
                if st.button("🚪 Sair"):
                    encerrar_sessao_professor()
                    st.rerun()

        """
        Botões em vez de st.tabs(): a seleção do st.tabs() é client-side e volta pra primeira aba
        sozinha quando a árvore de elementos muda — e é exatamente o que acontece aqui (o formulário
        de editar conteúdo desaparece da tela ao salvar). Caso típico: editar um conteúdo, salvar, e
        cair de volta em "Visão Geral" em vez de continuar em "Gerenciar Conteúdos". Mesmo padrão e
        mesmo motivo do toggle Teoria/Missões (ver ir_para_materia).
        """
        col_ab1, col_ab2, col_ab3 = st.columns(3)
        with col_ab1:
            if st.button(ABA_PROFESSOR_VISAO, use_container_width=True, key="aba_btn_professor_visao",
                         type="primary" if st.session_state.aba_professor == ABA_PROFESSOR_VISAO else "secondary"):
                st.session_state.aba_professor = ABA_PROFESSOR_VISAO
                st.rerun()
        with col_ab2:
            if st.button(ABA_PROFESSOR_CONTEUDOS, use_container_width=True, key="aba_btn_professor_conteudos",
                         type="primary" if st.session_state.aba_professor == ABA_PROFESSOR_CONTEUDOS else "secondary"):
                st.session_state.aba_professor = ABA_PROFESSOR_CONTEUDOS
                st.rerun()
        with col_ab3:
            if st.button(ABA_PROFESSOR_CONFIG, use_container_width=True, key="aba_btn_professor_config",
                         type="primary" if st.session_state.aba_professor == ABA_PROFESSOR_CONFIG else "secondary"):
                st.session_state.aba_professor = ABA_PROFESSOR_CONFIG
                st.rerun()

        st.markdown("")
        if st.session_state.aba_professor == ABA_PROFESSOR_VISAO:
            render_desempenho_turma()
        elif st.session_state.aba_professor == ABA_PROFESSOR_CONTEUDOS:
            render_gerenciar_conteudos()
        else:
            render_configuracoes()
