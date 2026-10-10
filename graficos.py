"""Gráficos Altair usados nos conteúdos de Estatística."""

import altair as alt
import pandas as pd
import streamlit as st

from config import LARGURA_GRAFICO
from estatistica import prever_pela_reta


def grafico_barras_simples(categorias, valores, titulo_y):
    """
    Gráfico de barras comum (eixo Y começando em zero), com Altair puro em vez de st.bar_chart, que
    prende o scroll do mouse quando o cursor está sobre ele. Mantém a mesma altura e largura dos
    demais gráficos.
    """
    df = pd.DataFrame({"Categoria": categorias, "Valor": valores})
    grafico = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("Categoria:N", sort=None, title=None),
            y=alt.Y("Valor:Q", title=titulo_y),
        )
        .properties(height=260, width=LARGURA_GRAFICO)
    )
    st.altair_chart(grafico, use_container_width=False)


def grafico_barras_eixo_controlado(categorias, valores, eixo_min, eixo_max, titulo_eixo):
    """
    Gráfico de barras com o eixo Y fixado manualmente entre eixo_min e eixo_max. O st.bar_chart
    sempre inclui o zero, o que impede demonstrar o truque do eixo cortado; o Altair permite fixar o
    domínio à mão (usado em Leitura Crítica de Gráficos).

    zero=False e clip=True são obrigatórios: por padrão o Vega-Lite ancora toda barra no zero e não
    desenha o que fica fora do domínio visível, e as barras do eixo cortado não apareceriam.

    Largura própria, menor que LARGURA_GRAFICO, porque o gráfico tem só 2 categorias (Produto A /
    Produto B).
    """
    LARGURA_DUAS_CATEGORIAS = 220
    df = pd.DataFrame({"Categoria": categorias, "Valor": valores})
    grafico = (
        alt.Chart(df)
        .mark_bar(clip=True)
        .encode(
            x=alt.X("Categoria:N", sort=None, title=None),
            y=alt.Y("Valor:Q", scale=alt.Scale(domain=[eixo_min, eixo_max], zero=False), title=titulo_eixo),
        )
        .properties(height=240, width=LARGURA_DUAS_CATEGORIAS)
    )
    st.altair_chart(grafico, use_container_width=False)


def grafico_boxplot_manual(q):
    """
    Desenha o box-plot à mão (mark_rule para os limites min-max, mark_bar para a caixa Q1-Q3 e
    mark_tick para a mediana), em vez de usar mark_boxplot() do Altair.

    mark_boxplot() calcula os próprios quartis por interpolação, diferente da mediana das metades de
    calcular_quartis(), e os números poderiam divergir do que a missão pede ao aluno. Desenhando a
    partir de "q" (o mesmo dict das missões), o gráfico mostra exatamente os mesmos valores.

    Largura própria, bem menor que LARGURA_GRAFICO, pois há uma única categoria ("Amostra"); na
    largura padrão a caixa ficaria perdida no meio de espaço vazio (mesmo raciocínio de
    LARGURA_DUAS_CATEGORIAS).
    """
    LARGURA_UMA_CATEGORIA = 160
    categoria = ["Amostra"]
    df_caixa = pd.DataFrame({"Categoria": categoria, "q1": [q["q1"]], "q3": [q["q3"]]})
    df_bigode = pd.DataFrame({"Categoria": categoria, "min": [q["val_min"]], "max": [q["val_max"]]})
    df_mediana = pd.DataFrame({"Categoria": categoria, "mediana": [q["mediana"]]})

    bigode = alt.Chart(df_bigode).mark_rule().encode(
        x=alt.X("Categoria:N", title=None), y=alt.Y("min:Q", title="Valor"), y2="max:Q",
    )
    caixa = alt.Chart(df_caixa).mark_bar(size=44).encode(
        x="Categoria:N", y="q1:Q", y2="q3:Q",
    )
    linha_mediana = alt.Chart(df_mediana).mark_tick(size=44, thickness=3, color="white").encode(
        x="Categoria:N", y="mediana:Q",
    )
    grafico = (bigode + caixa + linha_mediana).properties(height=280, width=LARGURA_UMA_CATEGORIA)
    st.altair_chart(grafico, use_container_width=False)


def grafico_dispersao_com_reta(xs, ys, reta, titulo_x, titulo_y):
    """
    Gráfico de dispersão (um ponto por par x,y) com a reta de tendência por cima. A reta é traçada a
    partir de "reta" (inclinação e intercepto de calcular_reta_tendencia), e não de um ajuste
    automático do Altair, para o desenho coincidir com os números que as missões pedem ao aluno.
    """
    df_pontos = pd.DataFrame({"x": xs, "y": ys})
    x_min, x_max = min(xs), max(xs)
    df_reta = pd.DataFrame({
        "x": [x_min, x_max],
        "y": [prever_pela_reta(reta, x_min), prever_pela_reta(reta, x_max)],
    })
    pontos = alt.Chart(df_pontos).mark_point(filled=True, size=80).encode(
        x=alt.X("x:Q", title=titulo_x), y=alt.Y("y:Q", title=titulo_y),
    )
    linha = alt.Chart(df_reta).mark_line(color="firebrick").encode(x="x:Q", y="y:Q")
    grafico = (pontos + linha).properties(height=280, width=LARGURA_GRAFICO)
    st.altair_chart(grafico, use_container_width=False)
