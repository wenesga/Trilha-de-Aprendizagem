"""Painel do Professor: Visão Geral (desempenho da turma)."""

import html
import functools

import altair as alt
import pandas as pd
import streamlit as st

from banco import (
    carregar_todos_alunos_do_banco,
    contar_acessos,
    excluir_alunos,
    limpar_banco,
    salvar_nomes_relatorio,
)
from bncc import acerto_por_aluno_e_habilidade, desempenho_por_bncc
from config import CORES_DESEMPENHO
from conteudos import obter_total_missoes, xp_maximo_catalogo_atual
from desempenho import (
    _fundo_acerto,
    _percentual_acerto,
    _texto_acerto,
    cor_por_percentual_concluido,
)
from relatorio_pdf import formatar_data_relatorio, gerar_pdf_relatorio, nome_de_arquivo
from sessao import flash


def _titulo_html(titulo):
    """Título de coluna; o que vier depois de uma quebra de linha fica menor e sem negrito."""
    primeira, _, resto = str(titulo).partition(chr(10))
    if not resto:
        return html.escape(primeira)
    return (
        f'{html.escape(primeira)}<br>'
        f'<span style="font-weight: normal; font-size: 0.85em; opacity: 0.6;">{html.escape(resto)}</span>'
    )


def tabela_centralizada(df, estilos=None):
    """Tabela em HTML com títulos em negrito e centralizados. Usada no lugar do
    st.dataframe quando a tabela não precisa de seleção de linha: o dataframe não
    deixa centralizar o título das colunas. A primeira coluna fica à esquerda;
    estilos é um DataFrame opcional, do mesmo formato, com o CSS de cada célula."""
    borda = "border: 1px solid rgba(128, 128, 128, 0.25); padding: 8px 12px;"
    colunas = list(df.columns)
    cabecalho = "".join(
        f'<th style="{borda} text-align: {"left" if i == 0 else "center"};">{_titulo_html(c)}</th>'
        for i, c in enumerate(colunas)
    )
    corpo = ""
    for r in range(len(df)):
        celulas = ""
        for i, c in enumerate(colunas):
            estilo = estilos.iloc[r, i] if estilos is not None else ""
            alinhamento = "left" if i == 0 else "center"
            celulas += f'<td style="{borda} text-align: {alinhamento}; {estilo}">{html.escape(str(df.iloc[r, i]))}</td>'
        corpo += f"<tr>{celulas}</tr>"
    st.markdown(
        '<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse;">'
        f"<thead><tr>{cabecalho}</tr></thead><tbody>{corpo}</tbody></table></div>",
        unsafe_allow_html=True,
    )


ESTILO_LINHA_TURMA = "background-color: #f1f3f5; color: #1f3a6e; font-weight: bold"


def tabela_de_acerto(alunos, conteudo_id=None):
    """Dados da tabela aluno × habilidade: (habilidades, linhas), com linhas =
    [(rótulo, [[acertos, tentativas] ou None por habilidade])], a da Turma
    primeiro. Usada pela tela (turma toda) e pelo PDF (só o conteúdo da aba)."""
    acertos, _ = acerto_por_aluno_e_habilidade(conteudo_id)
    if not acertos:
        return [], []
    habilidades = sorted({h for (_, h) in acertos})
    nomes = [n for n in alunos if any((n, h) in acertos for h in habilidades)]
    turma = {h: [0, 0] for h in habilidades}
    for n in nomes:
        for h in habilidades:
            par = acertos.get((n, h))
            if par:
                turma[h][0] += par[0]
                turma[h][1] += par[1]
    linhas = [("Turma", [turma[h] for h in habilidades])]
    linhas += [(n, [acertos.get((n, h)) for h in habilidades]) for n in nomes]
    return habilidades, linhas


def renderizar_acerto_por_aluno_e_habilidade(alunos, conteudo_id=None):
    """Tabela aluno × habilidade da BNCC com o % de acerto (acertos ÷ tentativas),
    mais uma linha com a turma toda. Quem não tentou nenhuma missão da
    habilidade fica com '—'."""
    st.subheader("🎯 Acerto por Habilidade")
    habilidades, linhas = tabela_de_acerto(alunos, conteudo_id)
    if not habilidades:
        st.info(
            "Ainda não há respostas registradas por habilidade. Elas passam a aparecer aqui "
            "conforme os alunos respondem as missões que têm uma **Habilidade BNCC** mapeada."
        )
        return
    st.caption(
        "Entre parênteses: acertos e tentativas. Verde a partir de 70%. Amarelo de 40% a 69%. Vermelho abaixo de 40%. Traço: sem tentativa."
    )
    linhas_txt, linhas_css = [], []
    for rotulo, pares in linhas:
        pcts = [_percentual_acerto(par) for par in pares]
        linhas_txt.append([("👥 " if rotulo == "Turma" else "") + rotulo] + [_texto_acerto(par) for par in pares])
        if rotulo == "Turma":
            linhas_css.append([ESTILO_LINHA_TURMA] * (len(pcts) + 1))
        else:
            linhas_css.append([""] + [_fundo_acerto(p) if p is not None else "" for p in pcts])
    total_missoes = {l["Habilidade"]: l["Missões"] for l in desempenho_por_bncc(alunos, conteudo_id)}
    titulos = [f"{h}" + chr(10) + f"({total_missoes[h]} missões)" if h in total_missoes else h for h in habilidades]
    df_txt = pd.DataFrame(linhas_txt, columns=["Aluno"] + titulos)
    df_css = pd.DataFrame(linhas_css, columns=["Aluno"] + titulos)
    tabela_centralizada(df_txt, df_css)


def _desmarcar_tabela_alunos():
    """Apagar a chave do session_state não limpa a marcação (o navegador guarda
    a seleção); trocar a chave da tabela cria uma tabela nova, sem nada marcado."""
    st.session_state["versao_tabela_alunos"] = st.session_state.get("versao_tabela_alunos", 0) + 1


@st.dialog("🗑️ Excluir aluno")
def _dialog_confirmar_exclusao_alunos(nomes_alvo):
    if len(nomes_alvo) == 1:
        st.warning(f"⚠️ Tem certeza que deseja excluir **{nomes_alvo[0]}** e todo o progresso dele(a)? Essa ação não pode ser desfeita.")
    else:
        lista = ", ".join(f"**{n}**" for n in nomes_alvo)
        st.warning(f"⚠️ Tem certeza que deseja excluir {len(nomes_alvo)} alunos ({lista}) e todo o progresso deles? Essa ação não pode ser desfeita.")
    col_conf, col_canc = st.columns(2)
    with col_conf:
        if st.button("✅ Sim, excluir", key="confirmar_excluir_aluno", type="primary", use_container_width=True):
            _desmarcar_tabela_alunos()
            excluir_alunos(nomes_alvo)  # já chama st.rerun() no final, fechando o popup
    with col_canc:
        if st.button("❌ Cancelar", key="cancelar_excluir_aluno", use_container_width=True):
            _desmarcar_tabela_alunos()
            st.rerun()


@st.dialog("🗑️ Apagar todo o banco de alunos")
def _dialog_confirmar_apagar_banco():
    st.error("⚠️ Isso apaga o progresso de **todos** os alunos, de todos os conteúdos, permanentemente. Tem certeza?")
    col_conf, col_canc = st.columns(2)
    with col_conf:
        if st.button("✅ Sim, apagar tudo", key="confirmar_apagar_banco_btn", type="primary", use_container_width=True):
            limpar_banco()  # já chama st.rerun() no final, fechando o popup
    with col_canc:
        if st.button("❌ Cancelar", key="cancelar_apagar_banco", use_container_width=True):
            st.rerun()


def renderizar_desempenho_por_habilidade(alunos, conteudo_id=None):
    st.subheader("🎯 Desempenho por Habilidade da BNCC")
    linhas_bncc = desempenho_por_bncc(alunos, conteudo_id)
    if not linhas_bncc:
        st.info(
            "Nenhuma missão foi mapeada para uma habilidade da BNCC ainda. "
            "Preencha o campo **Habilidade BNCC** ao cadastrar ou editar as missões, "
            "em ➕ Gerenciar Conteúdos, para que este relatório seja gerado."
        )
    else:
        st.caption(
            "Missões agrupadas pela habilidade da BNCC. "
            "Concluído: missões feitas por todos os alunos, do total possível (missões × alunos)."
        )
        df_bncc = pd.DataFrame(linhas_bncc)
        """
        Duas colunas (Conclusões, Possíveis) juntas numa só ("12/20"), do mesmo jeito que o PDF já
        mostra — eram números soltos aqui na tela, sem a fração que dá sentido a "Possíveis" (sem a
        fração, não ficava claro o que "Possíveis 20" queria dizer).
        """
        df_bncc_exibicao = df_bncc.copy()
        df_bncc_exibicao["Concluído"] = (
            df_bncc_exibicao["Conclusões"].astype(str) + "/" + df_bncc_exibicao["Possíveis"].astype(str)
        )
        df_bncc_exibicao = df_bncc_exibicao[["Habilidade", "Missões", "Concluído", "% Concluído"]]
        tabela_centralizada(df_bncc_exibicao)
        df_bncc_grafico = df_bncc.copy()
        df_bncc_grafico["Cor"] = df_bncc_grafico["% Concluído"].apply(cor_por_percentual_concluido)
        st.altair_chart(
            alt.Chart(df_bncc_grafico).mark_bar().encode(
                x=alt.X("% Concluído:Q", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("Habilidade:N", sort=None),
                color=alt.Color("Cor:N", scale=alt.Scale(domain=CORES_DESEMPENHO, range=CORES_DESEMPENHO), legend=None),
                # Tooltip explícito: evita mostrar "Cor" e "_Cor_sort_index" (campo interno do Vega-Lite).
                tooltip=[alt.Tooltip("Habilidade:N", title="Habilidade"), alt.Tooltip("% Concluído:Q", title="% Concluído")],
            ),
            use_container_width=True,
        )


def render_desempenho_turma():
    st.markdown("As informações abaixo mostram, em tempo real, como cada aluno está se saindo em cada conteúdo.")
    acessos_hoje, acessos_total = contar_acessos()
    st.markdown(f"👥 **Acessos:** {acessos_hoje} hoje · {acessos_total} no total")
    alunos = carregar_todos_alunos_do_banco()

    if not alunos:
        st.info("Nenhum aluno iniciou a trilha ainda.")
        return

    _, _, xp_catalogo_total = xp_maximo_catalogo_atual()
    meta_xp = st.session_state.config.get("meta_xp") or (xp_catalogo_total / 2)

    lista_geral = []
    for nome, perfil in alunos.items():
        erros_totais = sum(p.get("erros", 0) for p in perfil.get("progresso", {}).values())
        xp_total = perfil.get("xp_total", 0)
        """
        Cor por faixa de XP (ver cor_por_xp): como o comprimento da barra já é o XP, a cor segue a
        mesma lógica. Reaproveita cor_por_percentual_concluido (>=70% verde, 40-69% amarelo, <40%
        vermelho), o mesmo critério dos outros gráficos do painel.
        """
        pct_da_meta = min(xp_total / meta_xp * 100, 100) if meta_xp else 0
        lista_geral.append({
            "Aluno": nome, "Nome no Relatório": perfil.get("nome_relatorio", ""),
            "XP Total": xp_total, "Erros Totais": erros_totais,
            "Cor": cor_por_percentual_concluido(pct_da_meta),
        })

    """
    ---------- Abas no topo: tudo abaixo segue a aba escolhida ----------
    "Geral" mostra a turma em todos os conteúdos (XP, exclusão de aluno, nomes do relatório); cada
    conteúdo mostra só os dados dele, e o PDF sai da aba dele. on_change="rerun": só a aba aberta é
    calculada e enviada (as outras ficam vazias).
    """
    ids_conteudo = list(st.session_state.conteudos.keys())
    labels_abas = ["📊 Geral"] + [f"{st.session_state.conteudos[cid]['icone']} {st.session_state.conteudos[cid]['titulo']}" for cid in ids_conteudo]
    aba_geral, *abas = st.tabs(labels_abas, on_change="rerun", key="abas_detalhamento")

    with aba_geral:
        if aba_geral.open:
            # ---------- Visão Geral com exclusão individual de aluno ----------
            st.subheader("📈 Desempenho da Turma")
            espaco_botao_excluir = st.container()  # preenchido depois da tabela, que é quem sabe as linhas marcadas

            df_geral = pd.DataFrame(lista_geral)
            colunas_visiveis = ["Aluno", "XP Total", "Erros Totais"]
            if df_geral["Nome no Relatório"].str.strip().any():
                colunas_visiveis.insert(1, "Nome no Relatório")
            tabela_centralizada(df_geral[colunas_visiveis])
            with espaco_botao_excluir:
                col_nomes, col_botao = st.columns([4, 1], vertical_alignment="bottom")
                with col_nomes:
                    nomes_marcados = st.multiselect(
                        "Excluir alunos",
                        options=list(df_geral["Aluno"]),
                        placeholder="Escolha os alunos a excluir",
                        key=f"excluir_alunos_{st.session_state.get('versao_tabela_alunos', 0)}",
                    )
                with col_botao:
                    rotulo = "🗑️ Excluir" + (f" ({len(nomes_marcados)})" if nomes_marcados else "")
                    if st.button(rotulo, key="btn_excluir_selecionados", disabled=not nomes_marcados, use_container_width=True):
                        _dialog_confirmar_exclusao_alunos(nomes_marcados)

            """
            Editor em um expander separado, e não st.data_editor no lugar da tabela acima: aquela
            tabela usa on_select para escolher o aluno a excluir, e st.data_editor não tem seleção
            de linha.
            """
            with st.expander("✏️ Nomes para o relatório (opcional)"):
                st.caption(
                    "O aluno entra com um apelido inventado (Goku99, Player1, Shadow...), mas o relatório impresso "
                    "costuma precisar do nome real. Preencha aqui e o PDF sai com o nome de verdade — "
                    "**o login do aluno não muda**, então ninguém perde XP. "
                    "Deixe em branco quem você prefere completar à mão depois de imprimir."
                )
                df_nomes = st.data_editor(
                    df_geral[["Aluno", "Nome no Relatório"]],
                    use_container_width=True,
                    hide_index=True,
                    disabled=["Aluno"],
                    column_config={
                        "Aluno": st.column_config.TextColumn("Login do aluno", help="Como o aluno entra no app. Não editável."),
                        "Nome no Relatório": st.column_config.TextColumn(
                            "Nome no relatório", help="Nome que aparece no PDF. Em branco = fica vazio pra preencher à mão."),
                    },
                    key="editor_nomes_relatorio",
                )
                if st.button("💾 Salvar", key="salvar_nomes_relatorio"):
                    salvar_nomes_relatorio(dict(zip(df_nomes["Aluno"], df_nomes["Nome no Relatório"])))
                    flash("Salvo com sucesso!")
                    st.rerun()

            """
            Cor por faixa de % de missões concluídas (verde/amarelo/vermelho), somando todos os
            conteúdos. Usa a mesma técnica do gráfico de Detalhamento por Conteúdo (Altair com
            domain == range), pois st.bar_chart(..., color=coluna) pode trocar as cores.
            """
            grafico_geral = (
                alt.Chart(df_geral)
                .mark_bar()
                .encode(
                    x=alt.X("XP Total:Q"),
                    y=alt.Y("Aluno:N", sort=None),
                    color=alt.Color("Cor:N", scale=alt.Scale(domain=CORES_DESEMPENHO, range=CORES_DESEMPENHO), legend=None),
                    tooltip=[alt.Tooltip("Aluno:N", title="Aluno"), alt.Tooltip("XP Total:Q", title="XP Total")],
                )
            )
            st.altair_chart(grafico_geral, use_container_width=True)
            st.markdown("---")
            renderizar_desempenho_por_habilidade(alunos)
            st.markdown("---")
            renderizar_acerto_por_aluno_e_habilidade(alunos)

    for aba, cid in zip(abas, ids_conteudo):
        with aba:
            if not aba.open:
                continue
            conteudo_info = st.session_state.conteudos[cid]
            st.subheader(f"📈 Desempenho em {conteudo_info['titulo']}")
            total = obter_total_missoes(cid)

            linhas = []
            for nome, perfil in alunos.items():
                prog = perfil.get("progresso", {}).get(cid, {"missao_atual": 1, "erros": 0})
                concluidas = max(prog["missao_atual"] - 1, 0)
                concluidas = min(concluidas, total) if total else concluidas
                linhas.append({"Aluno": nome, "Nome no Relatório": perfil.get("nome_relatorio", ""),
                                "Missões Concluídas": concluidas, "Total de Missões": total,
                                "Erros": prog.get("erros", 0)})

            df_conteudo = pd.DataFrame(linhas)
            cols_conteudo = ["Aluno", "Missões Concluídas", "Total de Missões", "Erros"]
            if df_conteudo["Nome no Relatório"].str.strip().any():
                cols_conteudo.insert(1, "Nome no Relatório")
            tabela_centralizada(df_conteudo[cols_conteudo])

            if total:
                df_conteudo["% Concluído"] = (df_conteudo["Missões Concluídas"] / total * 100).round(0)
                df_conteudo["Cor"] = df_conteudo["% Concluído"].apply(cor_por_percentual_concluido)
                """
                Altair direto, com domain == range idênticos, em vez de st.bar_chart(...,
                color="Cor"): o Vega-Lite monta a ordem das cores a partir dos valores únicos da
                coluna e podia trocar verde por amarelo. Assim cada cor sempre mapeia para ela
                mesma.
                """
                grafico = (
                    alt.Chart(df_conteudo)
                    .mark_bar()
                    .encode(
                        x=alt.X("% Concluído:Q"),
                        y=alt.Y("Aluno:N", sort=None),
                        color=alt.Color("Cor:N", scale=alt.Scale(domain=CORES_DESEMPENHO, range=CORES_DESEMPENHO), legend=None),
                        tooltip=[alt.Tooltip("Aluno:N", title="Aluno"), alt.Tooltip("% Concluído:Q", title="% Concluído")],
                    )
                )
                st.altair_chart(grafico, use_container_width=True)

            """
            O PDF só é gerado quando o professor clica em Exportar (data recebe uma função, não os
            bytes); gerar os 10 PDFs a cada troca de página deixava a tela lenta.
            """
            gerar_este_pdf = functools.partial(
                gerar_pdf_relatorio,
                lista_geral, conteudo_info["titulo"], linhas,
                nome_instituicao=st.session_state.config.get("nome_instituicao", ""),
                nome_professor=st.session_state.config.get("nome_professor", ""),
                turma=st.session_state.config.get("turma", ""),
                data_relatorio=formatar_data_relatorio(st.session_state.config.get("cidade", "")),
                linhas_bncc=desempenho_por_bncc(alunos, cid),
                acerto=tabela_de_acerto(alunos, cid),
            )
            st.markdown("---")
            renderizar_desempenho_por_habilidade(alunos, cid)
            st.markdown("---")
            renderizar_acerto_por_aluno_e_habilidade(alunos, cid)
            st.markdown("---")
            st.download_button(
                label="📄 Exportar Relatório",
                data=gerar_este_pdf,
                file_name=f"relatorio_{nome_de_arquivo(conteudo_info['titulo'])}.pdf",
                mime="application/pdf",
                key=f"pdf_{cid}",
            )

    st.markdown("---")
    if st.button("🗑️ Apagar Todo o Banco de Alunos"):
        _dialog_confirmar_apagar_banco()
