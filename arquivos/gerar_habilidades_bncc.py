"""Gera o habilidades_bncc.json a partir do PDF oficial da BNCC (Ensino Médio).

Roda UMA vez (e de novo só se a BNCC mudar). O aplicativo lê o JSON pronto, nunca
o PDF. Uso, dentro da pasta Trilha_de_Aprendizagem:

    python arquivos/gerar_habilidades_bncc.py

Precisa do pdftotext (poppler ou xpdf) no PATH.

Fundamental: o PDF do Ensino Fundamental organiza as habilidades em tabelas e a
extração por regex sai irregular em parte (principalmente Língua Portuguesa, com
descrições coladas no texto vizinho). Por isso só entram as descrições que passam
em descricao_confiavel(); as outras ficam de fora e o app mostra só o código.
"""
import json
import re
import subprocess
from pathlib import Path

PASTA_ARQUIVOS = Path(__file__).resolve().parent
SAIDA = PASTA_ARQUIVOS.parent / "habilidades_bncc.json"

# (arquivo, padrão do código). A habilidade aparece como "(EM13MAT316) Texto...".
FONTES = [
    ("BNCC_EnsinoMedio.pdf", r"EM13[A-Z]{2,3}\d{2,3}"),
    # Computação na Educação Básica (complemento à BNCC): só as do Ensino Médio.
    ("BNCC - Computação.pdf", r"EM13CO\d{2}"),
]
INCLUIR_FUNDAMENTAL = True
if INCLUIR_FUNDAMENTAL:
    FONTES.append(("BNCC_EI_EF_110518_versaofinal.pdf", r"EF\d{2}[A-Z]{2}\d{2}"))

# Marcadores que encerram a descrição de uma habilidade.
FIM_DESCRICAO = r"(?:\n[ \t]*\n|\n[ \t]*(?:COMPET[ÊE]NCIA|HABILIDADES|Campo|Eixo|Quadro)\b)"


def extrair_texto(pdf, modo):
    saida = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", modo, str(pdf), "-"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return saida.stdout


def termina_bem(descricao):
    return descricao.rstrip().endswith((".", ")", ";"))


def completar(descricao_layout, descricao_raw):
    """O modo -layout separa bem as habilidades, mas corta as que a página monta
    em colunas (Língua Portuguesa). O modo -raw traz a frase inteira, mas não
    sabe onde ela acaba. Então: parte do -raw, só vale se começar igual ao
    -layout, e para na primeira pontuação final depois do ponto onde o -layout
    parou."""
    if not descricao_raw or not descricao_raw.startswith(descricao_layout[:30]):
        return descricao_layout
    for m in re.finditer(r"[.;](?=\s|$)", descricao_raw):
        if m.end() >= len(descricao_layout):
            return sem_notas_de_rodape(limpar(descricao_raw[:m.end()]))
    return descricao_layout


def sem_notas_de_rodape(texto):
    # O -raw mistura o número da nota de rodapé no meio da frase ("propostas 1 de
    # governo"). Só um algarismo solto entre palavras em minúsculas.
    return re.sub(r"(?<=[a-zà-ú,]) \d(?= [a-zà-ú])", "", texto)


def descricao_confiavel(descricao):
    """Descarta o que veio misturado: com outro código ou cabeçalho no meio, ou que
    não termina como frase."""
    if re.search(r"BASE NACIONAL|\(?EF\d{2}[A-Z]{2}\d{2}\)", descricao):
        return False
    return descricao.rstrip().endswith((".", ")", ";", ":"))


def limpar(texto):
    texto = re.sub(r"\s+", " ", texto).strip()
    # Cabeçalho/rodapé de página que cai no meio de uma habilidade.
    texto = re.sub(r"\s*BASE NACIONAL COMUM CURRICULAR\s*\d*", "", texto)
    # Números de nota de rodapé colados no fim (ex.: "... etc. 2" ou "... 1, 2,").
    texto = re.sub(r"(?:\s+\d{1,3},?)+\s*$", "", texto)
    return texto.strip()


def extrair_habilidades(texto, padrao_codigo):
    inicio = re.compile(r"^[ \t]*\((" + padrao_codigo + r")\)[ \t]+", re.M)
    achados = list(inicio.finditer(texto))
    habilidades = {}
    for i, m in enumerate(achados):
        fim = achados[i + 1].start() if i + 1 < len(achados) else len(texto)
        bloco = texto[m.end():fim]
        bloco = re.split(FIM_DESCRICAO, bloco, maxsplit=1)[0]
        descricao = limpar(bloco)
        if len(descricao) < 20:
            continue
        habilidades.setdefault(m.group(1), descricao)  # vale a primeira definição
    return habilidades


def extrair_habilidades_bruto(texto, padrao_codigo):
    """Texto cru depois de cada '(CODIGO)' até o próximo código (modo -raw, onde o
    código pode aparecer no meio da linha). Só serve de matéria-prima para completar."""
    inicio = re.compile(r"\((" + padrao_codigo + r")\)[ \t]+")
    achados = list(inicio.finditer(texto))
    bruto = {}
    for i, m in enumerate(achados):
        fim = achados[i + 1].start() if i + 1 < len(achados) else len(texto)
        bruto.setdefault(m.group(1), re.sub(r"\s+", " ", texto[m.end():fim][:1500]).strip())
    return bruto


def main():
    todas = {}
    for arquivo, padrao in FONTES:
        pdf = PASTA_ARQUIVOS / arquivo
        if not pdf.exists():
            print(f"[aviso] {arquivo} não encontrado, pulando.")
            continue
        h = extrair_habilidades(extrair_texto(pdf, "-layout"), padrao)
        bruto = extrair_habilidades_bruto(extrair_texto(pdf, "-raw"), padrao)
        corrigidas = 0
        # Código que o -layout não pegou no começo de linha, mas existe no -raw:
        # fica com a primeira frase depois do código.
        for codigo, descricao_raw in bruto.items():
            if codigo not in h:
                for m in re.finditer(r"[.;](?=\s|$)", descricao_raw):
                    if m.end() >= 25:
                        h[codigo] = sem_notas_de_rodape(limpar(descricao_raw[:m.end()]))
                        corrigidas += 1
                        break
        for codigo, descricao in list(h.items()):
            if not termina_bem(descricao):
                nova = completar(descricao, bruto.get(codigo, ""))
                if nova != descricao:
                    h[codigo] = nova
                    corrigidas += 1
        # Notas de rodapé no meio da frase só existem fora de Matemática (que já sai certa).
        for codigo in h:
            if "MAT" not in codigo:
                h[codigo] = sem_notas_de_rodape(h[codigo])
        if padrao.startswith("EF"):
            antes = len(h)
            h = {c: d for c, d in h.items() if descricao_confiavel(d)}
            print(f"{arquivo}: {antes - len(h)} descartadas por saírem misturadas")
        print(f"{arquivo}: {len(h)} habilidades ({corrigidas} completadas pelo modo -raw)")
        todas.update(h)
    SAIDA.write_text(json.dumps(dict(sorted(todas.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Gravado: {SAIDA} ({len(todas)} habilidades, {SAIDA.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
