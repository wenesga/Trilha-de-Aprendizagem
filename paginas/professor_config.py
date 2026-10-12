"""Painel do Professor: Configurações."""

import hashlib

import streamlit as st

from configuracao import salvar_config, senha_correta
from conteudos import xp_maximo_catalogo_atual, xp_maximo_de_conteudo
from sessao import flash


def render_configuracoes():
    st.subheader("🏫 Instituição")
    st.caption("Exibidos no cabeçalho do relatório em PDF. Deixe em branco pra não mostrar.")
    with st.form("form_instituicao"):
        nome_instituicao = st.text_input(
            "Nome da instituição",
            value=st.session_state.config.get("nome_instituicao", ""),
        )
        nome_professor = st.text_input(
            "Nome do professor",
            value=st.session_state.config.get("nome_professor", ""),
        )
        turma = st.text_input(
            "Turma/Série",
            value=st.session_state.config.get("turma", ""),
            placeholder="Ex.: 1º Ano - Ensino Médio, EJA, 9º Ano",
        )
        cidade = st.text_input(
            "Cidade (para a data do relatório)",
            value=st.session_state.config.get("cidade", ""),
            placeholder="Ex.: Arraias - TO",
        )
        st.caption("A data do relatório é sempre a data em que ele foi gerado — preenchida sozinha, não precisa digitar.")
        if st.form_submit_button("Salvar"):
            st.session_state.config["nome_instituicao"] = nome_instituicao.strip()
            st.session_state.config["nome_professor"] = nome_professor.strip()
            st.session_state.config["turma"] = turma.strip()
            st.session_state.config["cidade"] = cidade.strip()
            salvar_config(st.session_state.config)
            flash("Salvo com sucesso!")
            st.rerun()

    st.markdown("---")
    st.subheader("🎯 Meta de XP")
    st.caption(
        "Usada só pra colorir o gráfico \"Desempenho da Turma\" (Visão Geral): "
        "quem chegou a 70% da meta fica verde, entre 40% e 69% fica amarelo, "
        "abaixo de 40% fica vermelho."
    )
    xp_nativo_hoje, xp_cadastrado_hoje, xp_catalogo_hoje = xp_maximo_catalogo_atual()
    col_xp_nativo, col_xp_cadastrado, col_xp_total = st.columns(3)
    with col_xp_nativo:
        st.markdown(
            f'<div class="resumo-xp-card resumo-xp-nativo">'
            f'<div class="rotulo">⚙️ Matéria Padrão</div>'
            f'<div class="valor">{xp_nativo_hoje} XP</div></div>',
            unsafe_allow_html=True,
        )
    with col_xp_cadastrado:
        st.markdown(
            f'<div class="resumo-xp-card resumo-xp-cadastrado">'
            f'<div class="rotulo">📚 Matérias Cadastradas</div>'
            f'<div class="valor">{xp_cadastrado_hoje} XP</div></div>',
            unsafe_allow_html=True,
        )
    with col_xp_total:
        st.markdown(
            f'<div class="resumo-xp-card resumo-xp-total">'
            f'<div class="rotulo">Total do catálogo</div>'
            f'<div class="valor">{xp_catalogo_hoje} XP</div></div>',
            unsafe_allow_html=True,
        )

    """
    Seletor de conteúdo: o professor escolhe a disciplina do dia e vê o XP dela. Fica fora do form
    de propósito: precisa rerodar ao trocar a escolha, para atualizar o campo de meta antes de
    Salvar (widgets de form só atualizam no submit).
    """
    opcoes_conteudo = {"__catalogo__": "— Catálogo inteiro (todos os conteúdos) —"}
    opcoes_conteudo.update({cid: c["titulo"] for cid, c in st.session_state.conteudos.items()})
    opcoes_ids = list(opcoes_conteudo.keys())

    """
    A última escolha é salva no próprio config_sistema.json, e não só em session_state, que é
    perdido a cada F5 (sessão nova). meta_xp já é salvo em disco por esse arquivo; o foco escolhido
    segue o mesmo caminho.

    O widget usa key= e não recebe index=: calcular index= a partir de um valor que a mesma execução
    do script reescreve em session_state cria uma corrida, e o Streamlit pode descartar o clique do
    usuário (a seleção oscilava). Com key= apenas, o valor fica em st.session_state[key] e o
    Streamlit o gerencia sozinho.
    """
    if "meta_xp_foco_selecionado" not in st.session_state:
        st.session_state["meta_xp_foco_selecionado"] = st.session_state.config.get("ultimo_foco_meta_xp", "__catalogo__")
    if st.session_state["meta_xp_foco_selecionado"] not in opcoes_ids:
        st.session_state["meta_xp_foco_selecionado"] = "__catalogo__"
    conteudo_foco = st.selectbox(
        "Foco de hoje (opcional)",
        options=opcoes_ids,
        format_func=lambda cid: opcoes_conteudo[cid],
        help="Escolha o conteúdo que a turma vai estudar hoje pra já preencher o campo de meta com o XP dele.",
        key="meta_xp_foco_selecionado",
    )
    if conteudo_foco != st.session_state.config.get("ultimo_foco_meta_xp"):
        st.session_state.config["ultimo_foco_meta_xp"] = conteudo_foco
        salvar_config(st.session_state.config)
    if conteudo_foco == "__catalogo__":
        valor_padrao_meta = int(st.session_state.get("meta_xp_sessao") or xp_catalogo_hoje)
    else:
        xp_referencia = xp_maximo_de_conteudo(conteudo_foco, st.session_state.conteudos[conteudo_foco])
        st.caption(f"💡 \"{opcoes_conteudo[conteudo_foco]}\" vale até **{xp_referencia} XP** — já preenchido abaixo. Reduza se quiser uma meta mais fácil.")
        valor_padrao_meta = xp_referencia

    """
    A key inclui o conteúdo escolhido de propósito: trocar a escolha cria um widget novo, que
    preenche de novo com valor_padrao_meta, em vez de manter o número digitado antes. O campo
    continua editável para uma meta menor que o total.
    """
    with st.form("form_meta_xp"):
        meta_xp_input = st.number_input(
            "Meta de XP (referência pra colorir o gráfico)",
            min_value=1, step=10,
            value=int(valor_padrao_meta),
            key=f"meta_xp_input_{conteudo_foco}",
        )
        if st.form_submit_button("Salvar"):
            # A meta digitada vale só nesta sessão; não é gravada em disco.
            st.session_state["meta_xp_sessao"] = int(meta_xp_input)
            flash("Salvo com sucesso!")
            st.rerun()

    st.markdown("---")
    st.subheader("📝 Pesquisa")
    with st.form("form_pesquisa"):
        url_pesquisa = st.text_input(
            "Endereço do formulário",
            value=st.session_state.config.get("url_pesquisa", ""),
            placeholder="https://docs.google.com/forms/...",
            help="Deixe em branco pra esconder o botão \"Responder Pesquisa\" do menu.",
        )
        if st.form_submit_button("Salvar"):
            url_pesquisa = url_pesquisa.strip()
            if url_pesquisa and not url_pesquisa.startswith("https://"):
                st.error("O endereço precisa começar com https://")
            else:
                st.session_state.config["url_pesquisa"] = url_pesquisa
                salvar_config(st.session_state.config)
                flash("Salvo com sucesso!")
                st.rerun()

    st.markdown("---")
    st.subheader("🔑 Alterar Senha do Professor")
    with st.form("form_senha"):
        senha_atual = st.text_input("Senha atual", type="password")
        senha_nova = st.text_input("Nova senha", type="password")
        senha_nova_conf = st.text_input("Confirme a nova senha", type="password")
        if st.form_submit_button("Alterar Senha"):
            if not senha_correta(senha_atual, st.session_state.config):
                st.error("Senha atual incorreta.")
            elif not senha_nova or senha_nova != senha_nova_conf:
                st.error("As novas senhas não coincidem ou estão vazias.")
            else:
                st.session_state.config["senha_hash"] = hashlib.sha256(senha_nova.encode()).hexdigest()
                salvar_config(st.session_state.config)
                st.success("Senha alterada com sucesso!")
