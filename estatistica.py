"""Cálculos do conteúdo nativo de Estatística."""

import numpy as np
import pandas as pd

from config import FREQ_N_FAIXAS


def formatar_numero(value, casas=2):
    return f"{value:.{casas}f}".replace(".", ",")


def calcular_estatisticas(dados):
    n = len(dados)
    dados_ordenados = sorted(dados)
    soma = sum(dados)
    media = float(np.mean(dados))
    val_min = min(dados)
    val_max = max(dados)
    amplitude = val_max - val_min
    mediana = float(np.median(dados))

    modas = pd.Series(dados).mode().tolist()
    texto_moda = "Amodal" if len(modas) == n else ", ".join(formatar_numero(float(m)) for m in modas)

    soma_quadrados = sum((x - media) ** 2 for x in dados) if n > 1 else 0
    variancia = soma_quadrados / (n - 1) if n > 1 else 0
    desvio_padrao = variancia ** 0.5 if n > 1 else 0

    return dict(n=n, dados_ordenados=dados_ordenados, soma=soma, media=media, val_min=val_min,
                val_max=val_max, amplitude=amplitude, mediana=mediana, texto_moda=texto_moda,
                variancia=variancia, desvio_padrao=desvio_padrao)


def calcular_frequencia(dados, n_faixas=FREQ_N_FAIXAS):
    """
    Tabela de frequência com faixas de largura igual, calculadas a partir do intervalo real dos
    dados (do menor ao maior valor), e não faixas fixas, para funcionar com qualquer amostra
    cadastrada (nota, idade, altura).

    Cada faixa é [início, fim), exceto a última, que inclui val_max para que o maior valor da
    amostra não fique de fora.
    """
    val_min = min(dados)
    val_max = max(dados)
    amplitude = val_max - val_min
    """
    amplitude 0 (todos com o mesmo valor): usa largura 1 para não dividir por zero; as faixas perdem
    o sentido prático, mas o cálculo não quebra.
    """
    largura = amplitude / n_faixas if amplitude > 0 else 1

    faixas = []
    for i in range(n_faixas):
        inicio = val_min + i * largura
        eh_ultima = (i == n_faixas - 1)
        fim = val_max if eh_ultima else val_min + (i + 1) * largura
        freq = sum(1 for x in dados if inicio <= x <= fim) if eh_ultima else sum(1 for x in dados if inicio <= x < fim)
        faixas.append({"inicio": inicio, "fim": fim, "freq": freq})

    total = sum(f["freq"] for f in faixas)
    for f in faixas:
        f["freq_relativa"] = (f["freq"] / total * 100) if total else 0

    faixa_moda = max(faixas, key=lambda f: f["freq"])

    return dict(faixas=faixas, total=total, faixa_moda=faixa_moda)


def rotulo_faixa(f):
    """
    'X a Y' formatado, usado no texto da missão e na resposta certa da missão de leitura de gráfico,
    para garantir que os dois coincidam.
    """
    return f"{formatar_numero(f['inicio'], 1)} a {formatar_numero(f['fim'], 1)}"


def calcular_quartis(dados):
    """
    Q1, mediana (Q2) e Q3 pelo método da mediana das metades: ordena os dados e divide ao meio pela
    mediana; se a quantidade for ímpar, a mediana não entra em nenhuma das metades. É a convenção
    mais ensinada no Ensino Médio brasileiro para box-plot (existem outros métodos de quartil).
    """
    dados_ordenados = sorted(dados)
    n = len(dados_ordenados)
    metade = n // 2
    metade_inferior = dados_ordenados[:metade]
    metade_superior = dados_ordenados[n - metade:]
    return dict(
        val_min=dados_ordenados[0],
        q1=float(np.median(metade_inferior)),
        mediana=float(np.median(dados_ordenados)),
        q3=float(np.median(metade_superior)),
        val_max=dados_ordenados[-1],
    )


def calcular_ramo_folhas(dados):
    """
    Diagrama de ramos e folhas: ramo = parte inteira, folha = primeira casa decimal (assume até 1
    casa decimal, como no resto do app; ver formatar_numero). Retorna {ramo: [folhas], ...} em ordem
    crescente (os dados entram ordenados e o dict preserva a ordem de inserção).
    """
    ramos = {}
    for x in sorted(dados):
        ramo = int(x)
        folha = round((x - ramo) * 10)
        if folha == 10:  # caso raro de arredondamento (ex.: 7.99 -> ramo 8, folha 0)
            ramo += 1
            folha = 0
        ramos.setdefault(ramo, []).append(folha)
    return ramos


def texto_ramo_folhas(ramos):
    largura_ramo = max((len(str(r)) for r in ramos), default=1)
    linhas = [
        f"{str(ramo).rjust(largura_ramo)} | {' '.join(str(f) for f in folhas)}"
        for ramo, folhas in ramos.items()
    ]
    return "\n".join(linhas)


def calcular_reta_tendencia(xs, ys):
    """
    Inclinação e intercepto da reta de tendência (mínimos quadrados) via np.polyfit.
    """
    inclinacao, intercepto = np.polyfit(xs, ys, 1)
    return dict(inclinacao=float(inclinacao), intercepto=float(intercepto))


def prever_pela_reta(reta, x):
    return reta["inclinacao"] * x + reta["intercepto"]
