"""Estado da sessão, login do aluno e do professor, mensagens rápidas."""

import time

import streamlit as st

from banco import carregar_perfil_aluno
from config import (
    ABA_PROFESSOR_VISAO,
    ABA_TEORIA,
    ID_CONTEUDO_ESTATISTICA,
    MINUTOS_SESSAO_PROFESSOR,
    PAGINA_ESTATISTICA_HUB,
    PAGINA_INICIO,
    PAGINA_MATERIA,
    PAGINA_PROFESSOR,
    TAMANHO_MAX_APELIDO,
    TAMANHO_MIN_APELIDO,
)
from configuracao import carregar_config
from conteudos import carregar_conteudos, carregar_dados_estatistica




def sessao_professor_ativa():
    return time.time() < st.session_state.professor_auth_expira_em

def abrir_sessao_professor():
    """
    Também renova o prazo enquanto o painel está em uso, contando o tempo a partir do último uso.
    """
    st.session_state.professor_auth_expira_em = time.time() + MINUTOS_SESSAO_PROFESSOR * 60

def encerrar_sessao_professor():
    st.session_state.professor_auth_expira_em = 0.0


def apelido_invalido(apelido):
    """
    Retorna a mensagem de erro do apelido, ou "" se for válido.

    Regra: uma palavra, só letras e números. str.isalnum() cobre isso e aceita acentos ("João"), por
    isso não se usa regex.

    O apelido é a chave primária do aluno: um espaço faria "Ana Paula" e "AnaPaula" virarem dois
    perfis. O limite de caracteres também protege a coluna 'Login' do relatório em PDF (38 mm).
    """
    if len(apelido) < TAMANHO_MIN_APELIDO:
        return f"Use pelo menos {TAMANHO_MIN_APELIDO} caracteres."
    if len(apelido) > TAMANHO_MAX_APELIDO:
        return f"Use no máximo {TAMANHO_MAX_APELIDO} caracteres."
    if not apelido.isalnum():
        return "Só letras e números, sem espaços."
    return ""


def entrar_como_aluno(nome):
    """
    Entrar como aluno encerra a sessão do professor. Os dois papéis compartilham a mesma sessão do
    navegador, então sem isso o aluno herdaria o painel destravado. Também sai da página do
    professor, para não mostrar uma tela de senha inesperada.
    """
    carregar_perfil_aluno(nome)
    encerrar_sessao_professor()
    if st.session_state.pagina == PAGINA_PROFESSOR:
        st.session_state.pagina = PAGINA_INICIO
    st.rerun()

def ir_para_materia(cid, aba=ABA_TEORIA):
    """
    Caminho único para abrir uma matéria, usado pelo menu lateral e pelos cartões da Início e do hub
    de Estatística, para que todos cheguem ao mesmo estado.
    """
    st.session_state.pagina = PAGINA_MATERIA
    st.session_state.conteudo_ativo = cid
    st.session_state.aba_materia = aba
    st.rerun()

def ir_para_hub_estatistica():
    """Abre a vitrine de Estatística (PAGINA_ESTATISTICA_HUB), não uma
    matéria específica — por isso não usa ir_para_materia, que sempre define
    um conteudo_ativo."""
    st.session_state.pagina = PAGINA_ESTATISTICA_HUB
    st.rerun()


def flash(mensagem):
    """
    Guarda uma mensagem de sucesso para mostrar depois do st.rerun(), em um pop-up fixo no canto
    superior direito (ver renderizar_flash_pendente, chamado uma vez no roteamento principal).
    """
    st.session_state["_flash_pendente"] = mensagem


def renderizar_flash_pendente():
    """
    Mostra e consome a mensagem guardada por flash(), se houver, como um card fixo no canto superior
    direito, visível sem rolar a tela (st.toast() não funciona neste ambiente).
    """
    mensagem = st.session_state.pop("_flash_pendente", None)
    if mensagem:
        st.markdown(
            f'<div class="flash-toast">✅ {mensagem}</div>',
            unsafe_allow_html=True,
        )


def inicializar_estado():
    """Cria no estado da sessão as chaves que ainda não existem."""

    if 'conteudos' not in st.session_state: st.session_state.conteudos = carregar_conteudos()
    if 'config' not in st.session_state: st.session_state.config = carregar_config()
    if 'dados_estatistica' not in st.session_state: st.session_state.dados_estatistica = carregar_dados_estatistica()
    if 'aluno_ativo' not in st.session_state: st.session_state.aluno_ativo = ""
    if 'conteudo_ativo' not in st.session_state: st.session_state.conteudo_ativo = ID_CONTEUDO_ESTATISTICA
    """
    Guarda o instante em que a sessão expira em vez de um booleano 'logado', para que a autenticação
    sempre tenha prazo. 0.0 = sem sessão.
    """
    if 'professor_auth_expira_em' not in st.session_state: st.session_state.professor_auth_expira_em = 0.0
    if 'pagina' not in st.session_state: st.session_state.pagina = PAGINA_INICIO
    if 'aba_materia' not in st.session_state: st.session_state.aba_materia = ABA_TEORIA
    if 'aba_professor' not in st.session_state: st.session_state.aba_professor = ABA_PROFESSOR_VISAO
    if 'novas_secoes_teoria' not in st.session_state: st.session_state.novas_secoes_teoria = []
    if 'novas_missoes' not in st.session_state: st.session_state.novas_missoes = []
