"""Cores e textos de desempenho usados na tela e no relatório em PDF."""

from config import CORES_DESEMPENHO


def cor_por_percentual_concluido(percentual):
    verde, amarelo, vermelho = CORES_DESEMPENHO
    if percentual >= 70:
        return verde
    if percentual >= 40:
        return amarelo
    return vermelho


def _fundo_acerto(percentual):
    if percentual >= 70:
        return "background-color: #c9f0d6; color: #1f2937"
    if percentual >= 40:
        return "background-color: #fbefb5; color: #1f2937"
    return "background-color: #f6c9c4; color: #1f2937"


def _percentual_acerto(par):
    if not par or not par[1]:
        return None
    return round(par[0] / par[1] * 100)


def _texto_acerto(par):
    pct = _percentual_acerto(par)
    return "—" if pct is None else f"{pct}% ({par[0]}/{par[1]})"
