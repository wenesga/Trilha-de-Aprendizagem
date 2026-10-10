"""Trilha de missões dos conteúdos de Estatística e dos conteúdos cadastrados."""

import streamlit as st

from banco import progresso_atual
from config import (
    FREQ_N_FAIXAS,
    ID_CONTEUDO_COMPARACAO,
    ID_CONTEUDO_ESTATISTICA,
    ID_CONTEUDO_FREQUENCIA,
    ID_CONTEUDO_LEITURA_GRAFICA,
    ID_CONTEUDO_PESQUISA_AMOSTRAL,
    ID_CONTEUDO_TENDENCIA,
    LEITURA_CASO1_CATEGORIAS,
    LEITURA_CASO1_EIXO_CORTADO,
    LEITURA_CASO1_VALORES,
    TENDENCIA_HORAS_ESTUDO,
    TENDENCIA_NOTAS,
)
from estatistica import (
    calcular_estatisticas,
    calcular_frequencia,
    calcular_quartis,
    calcular_ramo_folhas,
    calcular_reta_tendencia,
    formatar_numero,
    prever_pela_reta,
    rotulo_faixa,
    texto_ramo_folhas,
)
from graficos import (
    grafico_barras_eixo_controlado,
    grafico_barras_simples,
    grafico_boxplot_manual,
    grafico_dispersao_com_reta,
)
from missoes import verificar_resposta


def render_missoes_estatistica():
    dados = st.session_state.dados_estatistica
    s = calcular_estatisticas(dados)
    prog = progresso_atual(ID_CONTEUDO_ESTATISTICA)
    cid = ID_CONTEUDO_ESTATISTICA

    st.info("**Dados:** " + " ".join(formatar_numero(x, 1) for x in dados))

    if prog["missao_atual"] > 1: st.success(f"✅ Missão 1 Concluída! (Amostra: {st.session_state.get(f'm_{cid}_1')})")
    elif prog["missao_atual"] == 1:
        st.markdown('### 📍 Missão 1: O Tamanho da Amostra')
        resp_1 = st.number_input("Quantos valores existem na nossa lista?", step=1, value=None, key=f"in_{cid}_1")
        verificar_resposta(cid, 1, resp_1, s["n"], 10)

    if prog["missao_atual"] > 2: st.success(f"✅ Missão 2 Concluída! (Soma: {st.session_state.get(f'm_{cid}_2')})")
    elif prog["missao_atual"] == 2:
        st.markdown('### 📍 Missão 2: A Soma de Tudo')
        resp_2 = st.number_input("Qual é o resultado da soma?", step=0.1, value=None, key=f"in_{cid}_2")
        verificar_resposta(cid, 2, resp_2, s["soma"], 20)

    if prog["missao_atual"] > 3: st.success(f"✅ Missão 3 Concluída! (Média: {st.session_state.get(f'm_{cid}_3')})")
    elif prog["missao_atual"] == 3:
        st.markdown('### 📍 Missão 3: O Ponto de Equilíbrio (Média)')
        resp_3 = st.number_input("Qual é a Média dos nossos dados?", step=0.1, value=None, key=f"in_{cid}_3")
        verificar_resposta(cid, 3, resp_3, s["media"], 30)

    if prog["missao_atual"] > 4: st.success(f"✅ Missão 4 Concluída! (Menor Valor: {st.session_state.get(f'm_{cid}_4')})")
    elif prog["missao_atual"] == 4:
        st.markdown('### 📍 Missão 4: O Menor Valor')
        resp_4 = st.number_input("Qual foi o menor número registrado?", step=0.1, value=None, key=f"in_{cid}_4")
        verificar_resposta(cid, 4, resp_4, s["val_min"], 10)

    if prog["missao_atual"] > 5: st.success(f"✅ Missão 5 Concluída! (Maior Valor: {st.session_state.get(f'm_{cid}_5')})")
    elif prog["missao_atual"] == 5:
        st.markdown('### 📍 Missão 5: O Maior Valor')
        resp_5 = st.number_input("Qual foi o maior número alcançado?", step=0.1, value=None, key=f"in_{cid}_5")
        verificar_resposta(cid, 5, resp_5, s["val_max"], 10)

    if prog["missao_atual"] > 6: st.success(f"✅ Missão 6 Concluída! (Amplitude: {st.session_state.get(f'm_{cid}_6')})")
    elif prog["missao_atual"] == 6:
        st.markdown('### 📍 Missão 6: A Distância (Amplitude)')
        resp_6 = st.number_input("Qual é a Amplitude dessa amostra?", step=0.1, value=None, key=f"in_{cid}_6")
        verificar_resposta(cid, 6, resp_6, s["amplitude"], 20)

    if prog["missao_atual"] > 7: st.success(f"✅ Missão 7 Concluída! (Mediana: {st.session_state.get(f'm_{cid}_7')})")
    elif prog["missao_atual"] == 7:
        st.markdown('### 📍 Missão 7: O Centro Exato (Mediana)')
        resp_7 = st.number_input("Qual é a Mediana?", step=0.1, value=None, key=f"in_{cid}_7")
        verificar_resposta(cid, 7, resp_7, s["mediana"], 40)

    if prog["missao_atual"] > 8: st.success(f"✅ Missão 8 Concluída! (Moda: {st.session_state.get(f'm_{cid}_8')})")
    elif prog["missao_atual"] == 8:
        st.markdown('### 📍 Missão 8: O Valor Mais Comum (Moda)')
        resp_8 = st.text_input("Qual número mais se repete? (Digite 'Não possui' se nenhum)", key=f"in_{cid}_8")
        verificar_resposta(cid, 8, resp_8, s["texto_moda"], 40, tipo="texto")

    if prog["missao_atual"] > 9: st.success(f"✅ Missão 9 Concluída! (Variância: {st.session_state.get(f'm_{cid}_9')})")
    elif prog["missao_atual"] == 9:
        st.markdown('### 📍 Missão 9: O Grau de Afastamento (Variância)')
        resp_9 = st.number_input("Calcule a Variância Amostral:", step=0.1, value=None, key=f"in_{cid}_9")
        verificar_resposta(cid, 9, resp_9, s["variancia"], 60)

    if prog["missao_atual"] > 10: st.success(f"🏆 PARABÉNS! Trilha concluída! (Desvio Padrão: {st.session_state.get(f'm_{cid}_10')})")
    elif prog["missao_atual"] == 10:
        st.markdown('### 📍 Missão 10: O Desvio Padrão')
        resp_10 = st.number_input("Qual é o Desvio Padrão geral?", step=0.1, value=None, key=f"in_{cid}_10")
        verificar_resposta(cid, 10, resp_10, s["desvio_padrao"], 80)


def render_missoes_frequencia():
    dados = st.session_state.dados_estatistica
    freq = calcular_frequencia(dados)
    faixas = freq["faixas"]
    prog = progresso_atual(ID_CONTEUDO_FREQUENCIA)
    cid = ID_CONTEUDO_FREQUENCIA

    st.info("**Amostra da Turma:** " + " ".join(formatar_numero(x, 1) for x in dados))

    for i, f in enumerate(faixas, start=1):
        rotulo = rotulo_faixa(f)
        if prog["missao_atual"] > i:
            st.success(f"✅ Missão {i} Concluída! (Faixa {rotulo}: {st.session_state.get(f'm_{cid}_{i}')})")
        elif prog["missao_atual"] == i:
            st.markdown(f'### 📍 Missão {i}: Faixa {i} de {FREQ_N_FAIXAS} ({rotulo})')
            resp = st.number_input(f"Quantos itens da amostra estão entre {rotulo}?", step=1, value=None, key=f"in_{cid}_{i}")
            verificar_resposta(cid, i, resp, f["freq"], 20)

    idx_total = FREQ_N_FAIXAS + 1
    if prog["missao_atual"] > idx_total:
        st.success(f"✅ Missão {idx_total} Concluída! (Total: {st.session_state.get(f'm_{cid}_{idx_total}')})")
    elif prog["missao_atual"] == idx_total:
        st.markdown(f'### 📍 Missão {idx_total}: Conferindo o Total')
        resp = st.number_input(f"Somando a frequência das {FREQ_N_FAIXAS} faixas, quantos itens tem a amostra ao todo?", step=1, value=None, key=f"in_{cid}_{idx_total}")
        verificar_resposta(cid, idx_total, resp, freq["total"], 20)

    idx_relativa = FREQ_N_FAIXAS + 2
    faixa_moda = freq["faixa_moda"]
    rotulo_moda = rotulo_faixa(faixa_moda)
    if prog["missao_atual"] > idx_relativa:
        st.success(f"✅ Missão {idx_relativa} Concluída! (Frequência Relativa: {st.session_state.get(f'm_{cid}_{idx_relativa}')}%)")
    elif prog["missao_atual"] == idx_relativa:
        st.markdown(f'### 📍 Missão {idx_relativa}: A Faixa Modal')
        st.write(f"A faixa modal (a que concentra mais itens) é a de **{rotulo_moda}**.")
        resp = st.number_input("Qual é a frequência relativa (%) dessa faixa?", step=0.1, value=None, key=f"in_{cid}_{idx_relativa}")
        verificar_resposta(cid, idx_relativa, resp, round(faixa_moda["freq_relativa"], 1), 30)

    idx_grafico = FREQ_N_FAIXAS + 3
    if prog["missao_atual"] > idx_grafico:
        st.success(f"🏆 PARABÉNS! Trilha concluída! (Faixa mais alta no gráfico: {st.session_state.get(f'm_{cid}_{idx_grafico}')})")
    elif prog["missao_atual"] == idx_grafico:
        st.markdown(f'### 📍 Missão {idx_grafico}: Lendo o Gráfico')
        grafico_barras_simples(
            [rotulo_faixa(f) for f in faixas],
            [f["freq"] for f in faixas],
            "Frequência",
        )
        alternativas = [rotulo_faixa(f) for f in faixas]
        resp = st.radio("No gráfico acima, qual faixa tem a barra mais alta?", alternativas, index=None, key=f"in_{cid}_{idx_grafico}")
        verificar_resposta(cid, idx_grafico, resp, rotulo_moda, 20, tipo="multipla")


def render_missoes_leitura_grafica():
    prog = progresso_atual(ID_CONTEUDO_LEITURA_GRAFICA)
    cid = ID_CONTEUDO_LEITURA_GRAFICA
    diferenca_real = LEITURA_CASO1_VALORES[1] - LEITURA_CASO1_VALORES[0]

    """
    Sem cabeçalho "Caso 1" aqui: nenhum outro conteúdo tem subtítulo antes da primeira missão, só
    "### 📍 Missão N".

    O gráfico manipulado (eixo cortado) fica visível nas 3 primeiras missões, pois o aluno responde
    em cima dele. Na missão 4, o gráfico honesto (eixo em 0) o substitui, e é ele que a última
    pergunta usa.
    """
    if prog["missao_atual"] <= 3:
        grafico_barras_eixo_controlado(
            LEITURA_CASO1_CATEGORIAS, LEITURA_CASO1_VALORES,
            LEITURA_CASO1_EIXO_CORTADO, max(LEITURA_CASO1_VALORES), "Vendas do mês",
        )

    if prog["missao_atual"] > 1:
        st.success(f"✅ Missão 1 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_1')})")
    elif prog["missao_atual"] == 1:
        st.markdown('### 📍 Missão 1: A Primeira Impressão')
        opcoes = LEITURA_CASO1_CATEGORIAS + ["Venderam quase igual"]
        resp = st.radio("Olhando o gráfico acima, qual produto parece ter vendido muito mais?", opcoes, index=None, key=f"in_{cid}_1")
        verificar_resposta(cid, 1, resp, LEITURA_CASO1_CATEGORIAS[1], 20, tipo="multipla")

    if prog["missao_atual"] > 2:
        st.success(f"✅ Missão 2 Concluída! (Eixo começa em: {st.session_state.get(f'm_{cid}_2')})")
    elif prog["missao_atual"] == 2:
        st.markdown('### 📍 Missão 2: Olhando o Eixo')
        resp = st.number_input("Em que valor o eixo vertical (Vendas) começa?", step=1, value=None, key=f"in_{cid}_2")
        verificar_resposta(cid, 2, resp, LEITURA_CASO1_EIXO_CORTADO, 20)

    if prog["missao_atual"] > 3:
        st.success(f"✅ Missão 3 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_3')})")
    elif prog["missao_atual"] == 3:
        st.markdown('### 📍 Missão 3: E Se Começasse em Zero?')
        resp = st.radio("Se o eixo começasse em 0, a diferença entre as barras pareceria maior, menor ou igual?", ["Maior", "Menor", "Igual"], index=None, key=f"in_{cid}_3")
        verificar_resposta(cid, 3, resp, "Menor", 20, tipo="multipla")

    if prog["missao_atual"] == 4:
        st.write("Agora observe o mesmo gráfico, com o eixo começando em 0:")
        grafico_barras_eixo_controlado(
            LEITURA_CASO1_CATEGORIAS, LEITURA_CASO1_VALORES,
            0, max(LEITURA_CASO1_VALORES), "Vendas do mês",
        )

    if prog["missao_atual"] > 4:
        st.success(f"✅ Missão 4 Concluída! (Diferença real: {st.session_state.get(f'm_{cid}_4')} unidades)")
    elif prog["missao_atual"] == 4:
        st.markdown('### 📍 Missão 4: A Diferença Real')
        resp = st.number_input("Quantas unidades a mais o Produto B vendeu, de fato?", step=1, value=None, key=f"in_{cid}_4")
        verificar_resposta(cid, 4, resp, diferenca_real, 30)

    """
    Sem cabeçalho "Caso 2" nem separador "---", pelo mesmo motivo do Caso 1. A manchete aparece só
    enquanto é relevante (missões 5 a 8).
    """
    if 5 <= prog["missao_atual"] <= 8:
        st.info('**Manchete:** "Corredor@s aprovam o novo modelo!" — pesquisa feita com 8 pessoas, todas já fãs da marca nas redes sociais.')

    if prog["missao_atual"] > 5:
        st.success(f"✅ Missão 5 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_5')})")
    elif prog["missao_atual"] == 5:
        st.markdown('### 📍 Missão 5: O Que a Manchete Sugere')
        resp = st.radio(
            "Pela forma como foi escrita, a manchete parece falar de:",
            ["Só das 8 pessoas entrevistadas", "Corredores em geral, no país inteiro"],
            index=None, key=f"in_{cid}_5",
        )
        verificar_resposta(cid, 5, resp, "Corredores em geral, no país inteiro", 20, tipo="multipla")

    if prog["missao_atual"] > 6:
        st.success(f"✅ Missão 6 Concluída! (Pessoas ouvidas: {st.session_state.get(f'm_{cid}_6')})")
    elif prog["missao_atual"] == 6:
        st.markdown('### 📍 Missão 6: O Tamanho da Amostra')
        resp = st.number_input("Quantas pessoas de fato participaram da pesquisa?", step=1, value=None, key=f"in_{cid}_6")
        verificar_resposta(cid, 6, resp, 8, 20)

    if prog["missao_atual"] > 7:
        st.success(f"✅ Missão 7 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_7')})")
    elif prog["missao_atual"] == 7:
        st.markdown('### 📍 Missão 7: Quem Foi Ouvido')
        resp = st.radio(
            "Essas 8 pessoas foram escolhidas ao acaso, ou já eram fãs da marca?",
            ["Ao acaso, de qualquer lugar", "Já eram fãs, seguiam a página da marca"],
            index=None, key=f"in_{cid}_7",
        )
        verificar_resposta(cid, 7, resp, "Já eram fãs, seguiam a página da marca", 20, tipo="multipla")

    if prog["missao_atual"] > 8:
        st.success("🏆 PARABÉNS! Trilha concluída!")
    elif prog["missao_atual"] == 8:
        st.markdown('### 📍 Missão 8: Dá Pra Confiar?')
        resp = st.radio(
            "Com só 8 pessoas, todas já fãs da marca, dá pra dizer que isso representa 'corredores em geral'?",
            ["Sim, representa bem", "Não — amostra pequena e só de quem já gostava"],
            index=None, key=f"in_{cid}_8",
        )
        verificar_resposta(cid, 8, resp, "Não — amostra pequena e só de quem já gostava", 30, tipo="multipla")


def render_missoes_comparacao_diagramas():
    dados = st.session_state.dados_estatistica
    q = calcular_quartis(dados)
    ramos = calcular_ramo_folhas(dados)
    prog = progresso_atual(ID_CONTEUDO_COMPARACAO)
    cid = ID_CONTEUDO_COMPARACAO

    st.info("**Amostra da Turma:** " + " ".join(formatar_numero(x, 1) for x in dados))

    if prog["missao_atual"] > 1: st.success(f"✅ Missão 1 Concluída! (Mediana: {st.session_state.get(f'm_{cid}_1')})")
    elif prog["missao_atual"] == 1:
        st.markdown('### 📍 Missão 1: O Centro (Mediana)')
        resp = st.number_input("Qual é a Mediana (Q2) da amostra?", step=0.1, value=None, key=f"in_{cid}_1")
        verificar_resposta(cid, 1, resp, q["mediana"], 20)

    if prog["missao_atual"] > 2: st.success(f"✅ Missão 2 Concluída! (Q1: {st.session_state.get(f'm_{cid}_2')})")
    elif prog["missao_atual"] == 2:
        st.markdown('### 📍 Missão 2: O Primeiro Quartil (Q1)')
        st.write("Q1 é a mediana da METADE DE BAIXO da amostra ordenada.")
        resp = st.number_input("Qual é o Q1?", step=0.1, value=None, key=f"in_{cid}_2")
        verificar_resposta(cid, 2, resp, q["q1"], 30)

    if prog["missao_atual"] > 3: st.success(f"✅ Missão 3 Concluída! (Q3: {st.session_state.get(f'm_{cid}_3')})")
    elif prog["missao_atual"] == 3:
        st.markdown('### 📍 Missão 3: O Terceiro Quartil (Q3)')
        st.write("Q3 é a mediana da METADE DE CIMA da amostra ordenada.")
        resp = st.number_input("Qual é o Q3?", step=0.1, value=None, key=f"in_{cid}_3")
        verificar_resposta(cid, 3, resp, q["q3"], 30)

    if prog["missao_atual"] == 4:
        grafico_boxplot_manual(q)
    if prog["missao_atual"] > 4: st.success(f"✅ Missão 4 Concluída! (Q3 no gráfico: {st.session_state.get(f'm_{cid}_4')})")
    elif prog["missao_atual"] == 4:
        st.markdown('### 📍 Missão 4: Lendo o Box-Plot')
        resp = st.number_input("Olhando o box-plot acima, qual valor marca o TOPO da caixa (Q3)?", step=0.1, value=None, key=f"in_{cid}_4")
        verificar_resposta(cid, 4, resp, q["q3"], 20)

    ramo_mais_comum = max(ramos, key=lambda r: len(ramos[r]))
    if prog["missao_atual"] == 5:
        st.code(texto_ramo_folhas(ramos), language=None)
    if prog["missao_atual"] > 5: st.success(f"✅ Missão 5 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_5')})")
    elif prog["missao_atual"] == 5:
        st.markdown('### 📍 Missão 5: Contando as Folhas')
        resp = st.number_input(f"No diagrama acima, quantos valores tem o ramo {ramo_mais_comum}?", step=1, value=None, key=f"in_{cid}_5")
        verificar_resposta(cid, 5, resp, len(ramos[ramo_mais_comum]), 20)

    if prog["missao_atual"] > 6:
        st.success("🏆 PARABÉNS! Trilha concluída!")
    elif prog["missao_atual"] == 6:
        st.markdown('### 📍 Missão 6: Qual Diagrama Usar?')
        resp = st.radio(
            "Se você quer identificar rápido se tem algum valor muito fora do padrão (outlier) na amostra, qual diagrama ajuda mais?",
            ["Histograma", "Box-plot", "Ramos e folhas"],
            index=None, key=f"in_{cid}_6",
        )
        verificar_resposta(cid, 6, resp, "Box-plot", 30, tipo="multipla")


def render_missoes_pesquisa_amostral():
    dados = st.session_state.dados_estatistica
    s = calcular_estatisticas(dados)
    prog = progresso_atual(ID_CONTEUDO_PESQUISA_AMOSTRAL)
    cid = ID_CONTEUDO_PESQUISA_AMOSTRAL

    st.info(f"**Cenário:** você quer saber a nota média de Matemática de todos os alunos do Ensino Médio da escola, usando a amostra que o professor já coletou: " + " ".join(formatar_numero(x, 1) for x in dados))

    if prog["missao_atual"] > 1: st.success(f"✅ Missão 1 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_1')})")
    elif prog["missao_atual"] == 1:
        st.markdown('### 📍 Missão 1: Qual é a População?')
        resp = st.radio(
            "Nesse cenário, qual é a POPULAÇÃO da pesquisa (o grupo inteiro que você quer descrever)?",
            ["Só a sua turma", "Todos os alunos do Ensino Médio da escola", "Só os alunos que tiraram nota alta"],
            index=None, key=f"in_{cid}_1",
        )
        verificar_resposta(cid, 1, resp, "Todos os alunos do Ensino Médio da escola", 20, tipo="multipla")

    if prog["missao_atual"] > 2: st.success(f"✅ Missão 2 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_2')})")
    elif prog["missao_atual"] == 2:
        st.markdown('### 📍 Missão 2: Qual é a Amostra?')
        resp = st.radio(
            "E qual é a AMOSTRA (o grupo de quem os dados foram realmente coletados)?",
            ["Só a sua turma", "Todos os alunos do Ensino Médio da escola", "Só os alunos que tiraram nota baixa"],
            index=None, key=f"in_{cid}_2",
        )
        verificar_resposta(cid, 2, resp, "Só a sua turma", 20, tipo="multipla")

    if prog["missao_atual"] > 3: st.success(f"✅ Missão 3 Concluída! (Tamanho da amostra: {st.session_state.get(f'm_{cid}_3')})")
    elif prog["missao_atual"] == 3:
        st.markdown('### 📍 Missão 3: O Tamanho da Amostra')
        resp = st.number_input("Quantos valores tem essa amostra?", step=1, value=None, key=f"in_{cid}_3")
        verificar_resposta(cid, 3, resp, s["n"], 20)

    if prog["missao_atual"] > 4: st.success(f"✅ Missão 4 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_4')})")
    elif prog["missao_atual"] == 4:
        st.markdown('### 📍 Missão 4: Uma Boa Pergunta de Pesquisa')
        resp = st.radio(
            "Qual dessas perguntas é mais fácil de responder com um número exato, calculado a partir dos dados?",
            ["Os alunos gostam de Matemática?", "Qual é a nota média da turma em Matemática?", "A Matemática é importante?"],
            index=None, key=f"in_{cid}_4",
        )
        verificar_resposta(cid, 4, resp, "Qual é a nota média da turma em Matemática?", 20, tipo="multipla")

    if prog["missao_atual"] > 5: st.success(f"✅ Missão 5 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_5')})")
    elif prog["missao_atual"] == 5:
        st.markdown('### 📍 Missão 5: Tendência Central')
        resp = st.radio(
            "Qual dessas é uma medida de TENDÊNCIA CENTRAL (não de dispersão)?",
            ["Média", "Amplitude", "Desvio Padrão"],
            index=None, key=f"in_{cid}_5",
        )
        verificar_resposta(cid, 5, resp, "Média", 20, tipo="multipla")

    if prog["missao_atual"] > 6:
        st.success("🏆 PARABÉNS! Trilha concluída!")
    elif prog["missao_atual"] == 6:
        st.markdown('### 📍 Missão 6: Onde Está o Relatório')
        resp = st.radio(
            "Você já calculou a média e o desvio padrão dessa amostra. Onde no app você já viu esse relatório pronto, com gráfico e tudo?",
            ["No conteúdo de Estatística Descritiva", "No Painel do Professor", "Não existe isso no app"],
            index=None, key=f"in_{cid}_6",
        )
        verificar_resposta(cid, 6, resp, "No conteúdo de Estatística Descritiva", 30, tipo="multipla")


def render_missoes_tendencia():
    xs, ys = TENDENCIA_HORAS_ESTUDO, TENDENCIA_NOTAS
    reta = calcular_reta_tendencia(xs, ys)
    prog = progresso_atual(ID_CONTEUDO_TENDENCIA)
    cid = ID_CONTEUDO_TENDENCIA

    """
    O gráfico fica visível nas missões 1-3 (leitura/conceito) e reaparece nas 4-5 (previsão), pois é
    nele que a resposta se lê.
    """
    if prog["missao_atual"] <= 5:
        grafico_dispersao_com_reta(xs, ys, reta, "Horas de Estudo", "Nota")

    if prog["missao_atual"] > 1: st.success(f"✅ Missão 1 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_1')})")
    elif prog["missao_atual"] == 1:
        st.markdown('### 📍 Missão 1: A Direção da Relação')
        resp = st.radio(
            "Olhando o gráfico, quando as horas de estudo aumentam, a nota parece:",
            ["Aumentar também", "Diminuir", "Não seguir padrão nenhum"],
            index=None, key=f"in_{cid}_1",
        )
        verificar_resposta(cid, 1, resp, "Aumentar também", 20, tipo="multipla")

    if prog["missao_atual"] > 2: st.success(f"✅ Missão 2 Concluída! (Nota: {st.session_state.get(f'm_{cid}_2')})")
    elif prog["missao_atual"] == 2:
        st.markdown('### 📍 Missão 2: Lendo um Ponto')
        resp = st.number_input("Olhando os pontos do gráfico, qual é a nota de quem estudou 5 horas?", step=0.1, value=None, key=f"in_{cid}_2")
        verificar_resposta(cid, 2, resp, ys[xs.index(5)], 20)

    if prog["missao_atual"] > 3: st.success(f"✅ Missão 3 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_3')})")
    elif prog["missao_atual"] == 3:
        st.markdown('### 📍 Missão 3: O Que a Reta Representa')
        resp = st.radio(
            "A reta de tendência precisa passar exatamente em cima de todos os pontos?",
            ["Sim, sempre passa por todos", "Não, ela só resume a tendência geral"],
            index=None, key=f"in_{cid}_3",
        )
        verificar_resposta(cid, 3, resp, "Não, ela só resume a tendência geral", 20, tipo="multipla")

    if prog["missao_atual"] > 4: st.success(f"✅ Missão 4 Concluída! (Nota prevista: {st.session_state.get(f'm_{cid}_4')})")
    elif prog["missao_atual"] == 4:
        st.markdown('### 📍 Missão 4: Prevendo com a Reta')
        resp = st.number_input("Usando a reta (não os pontos), qual seria a nota esperada pra quem estuda 6 horas?", step=0.1, value=None, key=f"in_{cid}_4")
        verificar_resposta(cid, 4, resp, prever_pela_reta(reta, 6), 30)

    if prog["missao_atual"] > 5: st.success(f"✅ Missão 5 Concluída! (Nota prevista: {st.session_state.get(f'm_{cid}_5')})")
    elif prog["missao_atual"] == 5:
        st.markdown('### 📍 Missão 5: Prevendo de Novo')
        resp = st.number_input("E pra quem estuda 3 horas, qual a nota esperada pela reta?", step=0.1, value=None, key=f"in_{cid}_5")
        verificar_resposta(cid, 5, resp, prever_pela_reta(reta, 3), 30)

    if prog["missao_atual"] > 6:
        st.success("🏆 PARABÉNS! Trilha concluída!")
    elif prog["missao_atual"] == 6:
        st.markdown('### 📍 Missão 6: Fugindo do Padrão')
        resp = st.radio(
            "Um aluno estuda BEM mais horas que a média, mas tira uma nota BEM mais baixa do que a reta previa. O que isso pode indicar?",
            ["Um caso fora do padrão — a reta não garante o resultado de cada pessoa", "Que a reta está errada", "Que esse aluno não é real"],
            index=None, key=f"in_{cid}_6",
        )
        verificar_resposta(cid, 6, resp, "Um caso fora do padrão — a reta não garante o resultado de cada pessoa", 30, tipo="multipla")


def render_missoes_dinamicas(conteudo):
    cid = st.session_state.conteudo_ativo
    missoes = conteudo.get("missoes", [])
    prog = progresso_atual(cid)

    if not missoes:
        st.info("📭 Este conteúdo ainda não possui missões cadastradas. Peça ao professor para adicioná-las no Painel do Professor.")
        return

    for idx, missao in enumerate(missoes, start=1):
        if prog["missao_atual"] > idx:
            st.success(f"✅ Missão {idx} Concluída! (Resposta: {st.session_state.get(f'm_{cid}_{idx}')})")
        elif prog["missao_atual"] == idx:
            st.markdown(f"### 📍 Missão {idx}: {missao.get('titulo', f'Desafio {idx}')}")
            st.write(missao.get("pergunta", ""))
            tipo = missao.get("tipo", "numero")
            if tipo == "multipla":
                """
                index=None começa a missão sem alternativa marcada; com a primeira pré-selecionada,
                o aluno poderia verificar sem ter escolhido e levar um erro que não foi escolha
                dele.
                """
                resposta = st.radio(
                    "Escolha uma alternativa:", missao.get("alternativas", []),
                    index=None, key=f"in_{cid}_{idx}",
                )
            elif tipo == "numero":
                resposta = st.number_input("Sua resposta:", step=0.1, value=None, key=f"in_{cid}_{idx}")
            else:
                resposta = st.text_input("Sua resposta:", key=f"in_{cid}_{idx}")
            verificar_resposta(cid, idx, resposta, missao.get("resposta"), missao.get("pontos", 10), tipo=tipo)

    if prog["missao_atual"] > len(missoes):
        st.balloons()
        st.success("🏆 PARABÉNS! Você concluiu toda a trilha deste conteúdo!")
