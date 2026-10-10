"""Páginas de teoria dos conteúdos de Estatística."""

import pandas as pd
import streamlit as st

from config import (
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
    rotulo_faixa,
    texto_ramo_folhas,
)
from graficos import (
    grafico_barras_eixo_controlado,
    grafico_barras_simples,
    grafico_boxplot_manual,
    grafico_dispersao_com_reta,
)


def render_pagina_estatistica():
    dados = st.session_state.dados_estatistica
    s = calcular_estatisticas(dados)

    st.markdown("A Estatística Descritiva resume um conjunto de números em poucas medidas. "
                "Nesta teoria, vamos calcular as principais medidas desta amostra:")
    st.info("**Dados:** " + " ".join(formatar_numero(x, 1) for x in dados))
    st.markdown("Estes são os resultados. Abaixo, veja como cada um é calculado, passo a passo.")

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><div class="metric-title">Média</div><div class="metric-value">{formatar_numero(s["media"], 1)}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><div class="metric-title">Mediana</div><div class="metric-value">{formatar_numero(s["mediana"], 1)}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><div class="metric-title">Moda</div><div class="metric-value">{s["texto_moda"]}</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-card"><div class="metric-title">Desvio Padrão</div><div class="metric-value">{formatar_numero(s["desvio_padrao"], 1)}</div></div>', unsafe_allow_html=True)

    st.write("---")
    st.markdown("### 1️⃣ Organizando a Casa (Rol)")
    st.write("Antes de qualquer cálculo, precisamos organizar os dados do menor para o maior.")
    st.info("**Rol:** " + " ".join(formatar_numero(x, 1) for x in s["dados_ordenados"]))

    with st.expander("📚 Ver Teoria: População, Amostra e Rol"):
        st.markdown("""
        A **População** é o conjunto de tudo o que queremos estudar. Como nem sempre dá para analisar todos, escolhemos uma parte dela: a **Amostra**.
        Os valores coletados, do jeito que foram anotados, são os **Dados Brutos**. O **Rol** é esses mesmos dados colocados em ordem, do menor para o maior. Em ordem, fica mais fácil achar a mediana e conferir as contas.
        """)

    st.markdown("### 2️⃣ O Ponto de Equilíbrio (Média)")
    st.write(f"Para achar a Média, nós somamos todos os **{s['n']}** valores e dividimos pelo total de itens:")
    soma_str = " + ".join([formatar_numero(x, 1) for x in s['dados_ordenados']])
    st.success(f"**Média =** ({soma_str}) ÷ {s['n']} **= {formatar_numero(s['media'], 1)}**")

    with st.expander("📚 Ver Teoria: Média Aritmética"):
        st.markdown("""
        A **Média** é a soma de todos os valores dividida pela quantidade deles. Ela é o valor que cada item teria se todos fossem iguais e a soma total continuasse a mesma.
        Exemplo: a média de 2, 3 e 4 é 3. Se trocarmos o 4 por 40, a média passa a ser 15. Um único valor muito diferente dos outros muda bastante a média.
        """)

    st.markdown("### 3️⃣ O Centro Exato (Mediana)")
    n = s['n']; dados_ordenados = s['dados_ordenados']
    if n % 2 == 0:
        meio1 = dados_ordenados[n // 2 - 1]
        meio2 = dados_ordenados[n // 2]
        st.write(f"Como temos uma quantidade **par** de números ({n}), a Mediana é a média dos dois números centrais ({formatar_numero(meio1, 1)} e {formatar_numero(meio2, 1)}):")
        st.success(f"**Mediana =** ({formatar_numero(meio1, 1)} + {formatar_numero(meio2, 1)}) ÷ 2 **= {formatar_numero(s['mediana'], 1)}**")
    else:
        meio = dados_ordenados[n // 2]
        st.write(f"Como temos uma quantidade **ímpar** de números ({n}), a Mediana é exatamente o número que está no meio da lista ordenada:")
        st.success(f"**Mediana = {formatar_numero(meio, 1)}**")

    with st.expander("📚 Ver Teoria: Mediana"):
        st.markdown("""
        A **Mediana** é o valor que fica no meio do Rol, que são os dados em ordem. Metade dos valores é menor que ela e a outra metade é maior.
        Exemplo: no Rol 2, 3, 4, a mediana é 3. Se trocarmos o 4 por 40, o Rol 2, 3, 40 continua com mediana 3. Um único valor muito diferente dos outros quase não muda a mediana.
        """)

    st.markdown("### 4️⃣ O Valor Mais Comum (Moda)")
    st.write("A Moda é simplesmente o número que mais se repete na nossa lista.")
    st.success(f"**Moda = {s['texto_moda']}**")

    with st.expander("📚 Ver Teoria: Moda"):
        st.markdown("""
        A **Moda** é o valor que mais aparece nos dados.
        Exemplo: nos dados 2, 3, 3, 4, a moda é 3, porque aparece duas vezes. Pode haver mais de uma moda, se dois valores aparecem o mesmo número de vezes. Se nenhum valor se repete, não há moda.
        """)

    st.markdown("### 5️⃣ A Distância (Amplitude)")
    st.write("A Amplitude mostra a diferença entre o maior e o menor valor alcançado.")
    st.success(f"**Amplitude =** {formatar_numero(s['val_max'], 1)} (Maior) - {formatar_numero(s['val_min'], 1)} (Menor) **= {formatar_numero(s['amplitude'], 1)}**")

    with st.expander("📚 Ver Teoria: Medidas de Dispersão"):
        st.markdown("""
        Média e Mediana mostram o centro dos dados. As medidas de dispersão (**Amplitude**, **Variância** e **Desvio Padrão**) mostram o quanto os dados estão espalhados em volta desse centro.
        Exemplo: os dados 4, 5, 6 e os dados 1, 5, 9 têm a mesma média, 5. Mas o segundo grupo é mais espalhado, e as medidas de dispersão mostram isso.
        A **Amplitude** é a diferença entre o maior e o menor valor. Nos dados 1, 5, 9 ela é 9 − 1 = 8.
        """)


def render_pagina_frequencia():
    dados = st.session_state.dados_estatistica
    freq = calcular_frequencia(dados)

    st.markdown("Veja como transformar uma lista de números soltos numa tabela de frequência — e depois num gráfico, a forma mais comum de resumir os dados de uma pesquisa por amostragem.")

    st.write("---")
    st.markdown("### 1️⃣ Por Que Agrupar em Faixas?")
    st.write(
        f"Com **{freq['total']}** valores espalhados (de {formatar_numero(min(dados), 1)} a "
        f"{formatar_numero(max(dados), 1)}), olhar número por número não ajuda a enxergar o panorama geral. "
        f"Agrupamos os dados em **faixas de tamanho igual** e contamos quantos itens caem em cada uma."
    )

    with st.expander("📚 Ver Teoria: Frequência Absoluta e Relativa"):
        st.markdown("""
        A **Frequência Absoluta** de uma faixa é simplesmente quantos itens da amostra caem dentro dela.
        A **Frequência Relativa** é essa mesma contagem em porcentagem do total — útil para comparar amostras de tamanhos diferentes: dizer "40% da turma" é mais claro do que dizer "8 alunos" para quem nem sabe quantos alunos tem a turma.
        """)

    st.markdown("### 2️⃣ Montando a Tabela de Frequência")
    tabela = pd.DataFrame([
        {
            "Faixa": rotulo_faixa(f),
            "Frequência Absoluta": f["freq"],
            "Frequência Relativa": f"{formatar_numero(f['freq_relativa'], 1)}%",
        }
        for f in freq["faixas"]
    ])
    st.table(tabela)

    with st.expander("📚 Ver Teoria: Por Que a Soma das Frequências Bate com o Total?"):
        st.markdown("""
        Cada item da amostra pertence a exatamente uma faixa — nenhum fica de fora, nenhum é contado duas vezes.
        Por isso, somando a Frequência Absoluta de todas as faixas, o resultado tem que ser igual ao total de itens da amostra. É uma forma simples de conferir se a tabela foi montada certa.
        """)

    st.markdown("### 3️⃣ O Gráfico de Frequência")
    st.write("A mesma tabela, agora em forma de gráfico de barras — cada barra é uma faixa, e a altura dela é a frequência absoluta.")
    grafico_barras_simples(
        [rotulo_faixa(f) for f in freq["faixas"]],
        [f["freq"] for f in freq["faixas"]],
        "Frequência",
    )

    with st.expander("📚 Ver Teoria: Lendo um Gráfico de Frequência"):
        st.markdown("""
        A faixa com a barra mais alta é chamada de **faixa modal** — é onde a maioria dos itens da amostra se concentra.
        Isso é diferente da Moda que você já viu na Estatística Descritiva: lá era um valor específico que se repete; aqui é uma FAIXA INTEIRA que concentra mais itens.
        """)


def render_pagina_leitura_grafica():
    st.markdown("Nem todo gráfico ou pesquisa que aparece na internet, no jornal ou nas redes sociais está mostrando a informação de forma honesta. Aqui você aprende a desconfiar — e a checar — antes de acreditar numa manchete.")

    st.write("---")
    st.markdown("### 1️⃣ O Truque do Eixo Cortado")
    st.write("Um gráfico de barras honesto normalmente começa em zero. Quando o eixo começa em outro valor, diferenças pequenas parecem enormes.")
    grafico_barras_eixo_controlado(
        LEITURA_CASO1_CATEGORIAS, LEITURA_CASO1_VALORES,
        LEITURA_CASO1_EIXO_CORTADO, max(LEITURA_CASO1_VALORES), "Vendas (eixo cortado)",
    )
    st.caption(f"Repare: o eixo vertical começa em {LEITURA_CASO1_EIXO_CORTADO}, não em 0.")

    with st.expander("📚 Ver Teoria: Por Que Isso Engana"):
        st.markdown("""
        Cortar o eixo não é ilegal, e às vezes nem é proposital — mas o efeito visual é sempre o mesmo: exagera a diferença entre as barras.
        A mesma diferença numérica pode parecer gigante ou quase nula, dependendo só de onde o eixo começa a ser desenhado.
        """)

    st.markdown("### 2️⃣ O Mesmo Gráfico, Honesto")
    grafico_barras_eixo_controlado(
        LEITURA_CASO1_CATEGORIAS, LEITURA_CASO1_VALORES,
        0, max(LEITURA_CASO1_VALORES), "Vendas (eixo começando em 0)",
    )
    diferenca_real = LEITURA_CASO1_VALORES[1] - LEITURA_CASO1_VALORES[0]
    st.write(f"Com o eixo começando em 0, fica claro que a diferença real é pequena: só **{diferenca_real}** unidades.")

    st.write("---")
    st.markdown("### 3️⃣ O Truque da Amostra")
    st.write("Além da escala, é preciso desconfiar de QUEM foi ouvido numa pesquisa. Uma manchete pode estar certa nos números e mesmo assim enganar, se a amostra não representa quem ela diz representar.")

    with st.expander("📚 Ver Teoria: Amostra Representativa"):
        st.markdown("""
        Uma amostra representativa precisa se parecer com o grupo inteiro que ela pretende descrever — em tamanho e em quem é ouvido.
        Perguntar só a fãs de uma marca sobre aquela marca, ou entrevistar 8 pessoas e falar em nome de "todo mundo", são formas comuns de distorcer uma conclusão sem inventar nenhum número.
        """)


def render_pagina_comparacao_diagramas():
    dados = st.session_state.dados_estatistica
    q = calcular_quartis(dados)
    ramos = calcular_ramo_folhas(dados)

    st.markdown("Os mesmos dados podem ser mostrados de formas diferentes — cada forma revela um aspecto diferente da amostra. Aqui você compara três: histograma, box-plot e ramos-e-folhas.")

    st.write("---")
    st.markdown("### 1️⃣ O Histograma (Você Já Viu Esse)")
    st.write("É a mesma forma usada no conteúdo de Frequência: barras mostrando quantos itens caem em cada faixa. Ótimo pra ver ONDE a amostra se concentra.")

    st.markdown("### 2️⃣ O Box-Plot (Diagrama de Caixa)")
    st.write("Resume a amostra em 5 números: o menor valor, o 1º quartil (Q1), a Mediana, o 3º quartil (Q3) e o maior valor. A \"caixa\" guarda os 50% centrais da amostra.")
    grafico_boxplot_manual(q)
    st.info(
        f"**Mínimo:** {formatar_numero(q['val_min'], 1)} · **Q1:** {formatar_numero(q['q1'], 1)} · "
        f"**Mediana:** {formatar_numero(q['mediana'], 1)} · **Q3:** {formatar_numero(q['q3'], 1)} · "
        f"**Máximo:** {formatar_numero(q['val_max'], 1)}"
    )

    with st.expander("📚 Ver Teoria: Quartis"):
        st.markdown("""
        Assim como a Mediana divide a amostra ordenada ao meio (50% abaixo, 50% acima), os **Quartis** dividem em quatro partes iguais.
        **Q1** é a mediana da metade de baixo (25% da amostra está abaixo dele); **Q3** é a mediana da metade de cima (75% da amostra está abaixo dele). A distância entre Q1 e Q3 mostra onde os 50% centrais da amostra estão concentrados.
        """)

    st.markdown("### 3️⃣ O Diagrama de Ramos e Folhas")
    st.write("Cada valor vira um \"ramo\" (a parte inteira) e uma \"folha\" (a primeira casa decimal) — mantém TODOS os valores originais visíveis, o que o histograma e o box-plot não fazem.")
    st.code(texto_ramo_folhas(ramos), language=None)

    with st.expander("📚 Ver Teoria: Lendo o Ramo e Folhas"):
        st.markdown("""
        Cada linha é um "ramo" — por exemplo, o ramo 8 junta todos os valores entre 8,0 e 8,9. As "folhas" ao lado são a casa decimal de cada valor que caiu naquele ramo, em ordem.
        Contando as folhas de um ramo, você sabe quantos valores caem ali — igual à frequência de uma faixa, só que sem perder o valor exato de cada um.
        """)

    st.markdown("### 4️⃣ Qual Usar?")
    st.write("Nenhum dos três é \"o melhor\" sempre — cada um responde uma pergunta diferente: o histograma mostra a forma geral da distribuição; o box-plot destaca a dispersão e valores fora do padrão; o ramos-e-folhas preserva o dado original.")


def render_pagina_pesquisa_amostral():
    dados = st.session_state.dados_estatistica
    s = calcular_estatisticas(dados)

    st.markdown("Antes de calcular qualquer coisa, uma pesquisa estatística começa com DECISÕES: o que perguntar, quem ouvir, e o que fazer com a resposta. Aqui você acompanha essas decisões, usando a amostra que o professor já coletou.")

    st.write("---")
    st.markdown("### 1️⃣ População x Amostra")
    st.write(
        f"Imagine que você quer saber a nota média de Matemática de TODOS os alunos do Ensino Médio da escola — "
        f"esse grupo inteiro é a **população**. Não dá pra ouvir todo mundo, então se usa uma **amostra**: um pedaço "
        f"da população, coletado de verdade. Aqui, a amostra tem **{s['n']}** valores."
    )

    with st.expander("📚 Ver Teoria: Por Que Usar Amostra em Vez da População Inteira"):
        st.markdown("""
        Ouvir a população inteira (um **censo**) é caro, demorado ou às vezes impossível. Uma amostra bem escolhida — grande o suficiente e sem viés (ver o conteúdo Leitura Crítica de Gráficos, sobre amostra não representativa) — permite estimar como a população se comporta sem precisar ouvir todo mundo.
        """)

    st.markdown("### 2️⃣ Planejando a Coleta")
    st.write("Antes de sair coletando, um bom planejamento decide: qual pergunta exatamente será respondida, e como os dados serão coletados (nesse caso, já foi feito — os dados foram definidos pelo professor).")

    with st.expander("📚 Ver Teoria: Uma Boa Pergunta de Pesquisa"):
        st.markdown("""
        Uma boa pergunta de pesquisa é **específica e mensurável** — dá pra responder com um número ou um dado concreto. "Os alunos gostam de Matemática?" é vago (gostar quanto? como medir?). "Qual é a nota média da turma em Matemática?" é mensurável: existe uma resposta numérica exata, calculável a partir dos dados.
        """)

    st.markdown("### 3️⃣ Do Dado ao Relatório")
    st.write(
        "Depois de coletar, os dados viram um **relatório**: gráficos e medidas que resumem a amostra. "
        f"Com essa mesma amostra, a média é **{formatar_numero(s['media'], 1)}** e o desvio padrão é "
        f"**{formatar_numero(s['desvio_padrao'], 1)}** — a medida de tendência central e a de dispersão que "
        "todo relatório de pesquisa amostral deveria mostrar."
    )

    with st.expander("📚 Ver Teoria: Onde Está Esse Relatório no App"):
        st.markdown("""
        Você já viu um relatório assim de verdade: é o conteúdo **Estatística Descritiva**, na aba Teoria. Ele mostra passo a passo como a amostra vira Média, Mediana, Moda, Amplitude, Variância e Desvio Padrão — exatamente o que um relatório de pesquisa amostral precisa comunicar.
        """)


def render_pagina_tendencia():
    xs, ys = TENDENCIA_HORAS_ESTUDO, TENDENCIA_NOTAS
    reta = calcular_reta_tendencia(xs, ys)

    st.markdown("Até agora cada item tinha UM número. E se tivesse DOIS, por exemplo horas de estudo e nota? Dá pra investigar se as duas coisas andam juntas.")

    st.write("---")
    st.markdown("### 1️⃣ Duas Variáveis, Um Gráfico")
    st.write("Cada ponto do gráfico abaixo é um aluno: a posição no eixo horizontal é quantas horas ele estudou, e no eixo vertical, a nota que tirou.")
    grafico_dispersao_com_reta(xs, ys, reta, "Horas de Estudo", "Nota")

    with st.expander("📚 Ver Teoria: Gráfico de Dispersão"):
        st.markdown("""
        Esse tipo de gráfico se chama **gráfico de dispersão** — cada ponto é um item da amostra, posicionado pelas suas DUAS variáveis ao mesmo tempo. Ele existe justamente pra revelar se duas variáveis parecem estar relacionadas: os pontos sobem juntos, descem juntos, ou não seguem padrão nenhum?
        """)

    st.markdown("### 2️⃣ A Reta de Tendência")
    st.write(
        f"A linha vermelha é a **reta de tendência**: ela resume, numa linha só, a direção geral dos pontos. "
        f"Aqui, a cada 1 hora de estudo a mais, a nota tende a subir cerca de **{formatar_numero(reta['inclinacao'], 1)}** ponto."
    )

    with st.expander("📚 Ver Teoria: A Reta Não Passa em Cima de Todo Mundo"):
        st.markdown("""
        A reta não precisa (e normalmente não consegue) passar exatamente em cima de cada ponto — ela é um RESUMO da tendência geral, calculado pra ficar o mais perto possível de todos os pontos ao mesmo tempo. Pontos que ficam longe da reta são os que fogem mais do padrão — vale a pena investigar por quê.
        """)

    st.markdown("### 3️⃣ Usando a Reta pra Prever")
    st.write("Depois de traçada, a reta serve pra estimar um valor que você não tem: dado um número de horas de estudo, dá pra prever (não garantir) a nota esperada, só olhando onde a reta passa naquele ponto.")


def render_pagina_conteudo_dinamico(conteudo):
    if conteudo.get("descricao"):
        st.markdown(f"*{conteudo['descricao']}*")
    st.write("---")

    secoes = conteudo.get("teoria", [])
    if not secoes:
        st.info("📭 Este conteúdo ainda não possui teoria cadastrada. Peça ao professor para adicioná-la no Painel do Professor.")
        return

    for i, secao in enumerate(secoes, start=1):
        with st.expander(f"{i}️⃣ {secao.get('titulo', '')}", expanded=True):
            st.markdown(secao.get("texto", ""))
        st.write("")
