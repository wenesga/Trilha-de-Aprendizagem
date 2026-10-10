"""Verificação de respostas e cálculo de XP."""

import streamlit as st

from banco import (
    perfil_atual,
    progresso_atual,
    registrar_tentativa_missao,
    salvar_perfil_e_progresso,
)


"""
O XP de cada missão diminui a cada erro nela, mas nunca fica negativo nem chega a zero: o aluno
sempre ganha algo por terminar. Não há perda de XP ao errar, o que contradiria a proposta pedagógica
do sistema, que trata o erro como parte do processo.
"""
DESCONTO_XP_POR_ERRO = 0.20   # cada erro NESTA missão reduz 20% do XP dela
PISO_XP_FRACAO = 0.20         # nunca menos que 20% do valor configurado pelo professor

def calcular_xp_por_desempenho(pontos_base, erros_nesta_missao):
    """
    XP realmente concedido por uma missão, considerando quantas vezes o aluno errou ela (não o
    conteúdo inteiro) antes de acertar.

    É proporcional ao XP configurado pelo professor, então vale para missões de 10, 20 ou 100
    pontos. Com XP muito baixo (1 ou 2), o arredondamento pode esconder o desconto, pois o piso de 1
    ponto prevalece.
    """
    fracao = max(1 - erros_nesta_missao * DESCONTO_XP_POR_ERRO, PISO_XP_FRACAO)
    return max(round(pontos_base * fracao), 1)


def verificar_resposta(conteudo_id, missao_id, resposta_aluno, resposta_certa, pontos, tipo="numero"):
    if st.button("Verificar Resposta", key=f"btn_{conteudo_id}_{missao_id}"):
        if resposta_aluno is None or str(resposta_aluno).strip() == "":
            st.error("⚠️ Escolha uma alternativa antes de verificar!" if tipo == "multipla"
                     else "⚠️ Digite um valor antes de verificar!")
            return

        acertou = False
        if tipo == "multipla":
            """
            Comparação exata: o aluno escolhe uma alternativa cadastrada, então os dois lados vêm do
            mesmo texto. Isso evita que, em resposta digitada, "media" e "média" sejam strings
            diferentes e o aluno perca o ponto por causa do acento.
            """
            acertou = str(resposta_aluno).strip() == str(resposta_certa).strip()
        elif tipo == "numero":
            try:
                acertou = abs(float(resposta_aluno) - float(resposta_certa)) < 0.1
            except (ValueError, TypeError):
                acertou = False
        elif tipo == "texto":
            resp_txt, certa_txt = str(resposta_aluno).strip().lower(), str(resposta_certa).strip().lower()
            if resp_txt == certa_txt:
                acertou = True
            else:
                try:
                    if abs(float(resp_txt.replace(",", ".")) - float(certa_txt.replace(",", "."))) < 0.1:
                        acertou = True
                except Exception:
                    pass

        perfil = perfil_atual()
        prog = progresso_atual(conteudo_id)

        nome_aluno = st.session_state.aluno_ativo
        registrar_tentativa_missao(nome_aluno, conteudo_id, missao_id, acertou)

        if acertou:
            erros_desta_missao = prog.get("erros_missao_atual", 0)
            xp_ganho = calcular_xp_por_desempenho(pontos, erros_desta_missao)
            if erros_desta_missao > 0:
                mensagem = f"🎉 Correto! +{xp_ganho} XP de {pontos} XP (descontado pelas tentativas)"
            else:
                mensagem = f"🎉 Correto! +{xp_ganho} XP!"
            """
            Guardado em session_state em vez de um st.success() imediato: o st.rerun() logo abaixo
            troca a tela quase na hora e a mensagem não daria tempo de ser lida.
            renderizar_ultimo_resultado() exibe o texto de forma persistente, no fim da aba Missões,
            perto de onde o aluno clicou.
            """
            st.session_state[f"ultimo_resultado_{conteudo_id}"] = mensagem
            perfil["xp_total"] = perfil.get("xp_total", 0) + xp_ganho
            prog["missao_atual"] += 1
            prog["erros_missao_atual"] = 0  # zera para a próxima missão começar sem desconto
            prog["historico"].append(f"✅ Missão {missao_id} concluída. Resposta: `{resposta_aluno}` (+{xp_ganho} XP)")
            st.session_state[f"m_{conteudo_id}_{missao_id}"] = resposta_aluno
            """
            Grava também no banco (prog["respostas"], persistido por salvar_perfil_e_progresso): o
            session_state vale só para a aba do navegador e some em uma sessão nova, quando as
            missões já feitas apareceriam com "(Resposta: None)".
            """
            prog.setdefault("respostas", {})[str(missao_id)] = resposta_aluno
            salvar_perfil_e_progresso(nome_aluno, conteudo_id, perfil, prog)
            st.rerun()
        else:
            prog["erros"] = prog.get("erros", 0) + 1
            prog["erros_missao_atual"] = prog.get("erros_missao_atual", 0) + 1
            salvar_perfil_e_progresso(nome_aluno, conteudo_id, perfil, prog)
            """
            Limpa o "🎉 Correto!" da missão anterior: sem isso, ele ficava em session_state pra
            sempre (só é sobrescrito num ACERTO) e aparecia junto do "❌ Resposta incorreta" da
            tentativa atual — as duas mensagens empilhadas, tumultuado. Errar tem que apagar o
            acerto de antes, não só somar mais uma mensagem em cima.
            """
            st.session_state.pop(f"ultimo_resultado_{conteudo_id}", None)
            st.error("❌ Resposta incorreta. Revise o conteúdo e tente de novo!")


def renderizar_ultimo_resultado(conteudo_id):
    """
    Mostra o resultado da última missão respondida corretamente neste conteúdo, de forma
    persistente: fica visível até o aluno responder a missão seguinte (um st.success() sumiria
    no st.rerun(); ver verificar_resposta).

    É chamada depois de desenhar as missões, para aparecer embaixo do botão "Verificar Resposta", na
    mesma posição do "❌ Resposta incorreta".
    """
    mensagem = st.session_state.get(f"ultimo_resultado_{conteudo_id}")
    if mensagem:
        st.success(mensagem)
