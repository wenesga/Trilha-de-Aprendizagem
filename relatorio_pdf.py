"""Geração do relatório em PDF."""

import os
import re
import unicodedata
from datetime import date

import streamlit as st
from PIL import Image
from fpdf import FPDF

from config import ARQUIVO_CABECALHO
from desempenho import (
    _fundo_acerto,
    _percentual_acerto,
    _texto_acerto,
    cor_por_percentual_concluido,
)


def hex_para_rgb(cor_hex):
    """
    '#2ecc71' -> (46, 204, 113): fpdf2 exige três inteiros em set_fill_color e não aceita hex.
    """
    cor_hex = cor_hex.lstrip("#")
    return tuple(int(cor_hex[i:i + 2], 16) for i in (0, 2, 4))


class _PDFComCabecalho(FPDF):
    """
    FPDF que desenha o timbre institucional (ARQUIVO_CABECALHO) só no topo da primeira página do
    relatório (as demais ficam com o espaço todo para tabelas e gráficos).

    Usa header() em vez de pdf.image() solto: assim a primeira página sempre leva o timbre e o fpdf2
    não o repete nas seguintes, inclusive nas criadas por quebra automática. Se o arquivo não
    existir, o relatório sai sem timbre.
    """

    def header(self):
        if self.page_no() != 1 or not os.path.exists(ARQUIVO_CABECALHO):
            return
        largura = self.w - self.l_margin - self.r_margin
        self.image(ARQUIVO_CABECALHO, x=self.l_margin, y=10, w=largura)
        """
        pdf.image() não move o cursor no fpdf2, então o Y inicial do conteúdo é calculado a partir
        da proporção real do arquivo (lida com PIL), e trocar a arte por outra proporção continua
        funcionando.
        """
        with Image.open(ARQUIVO_CABECALHO) as img:
            altura = largura * img.height / img.width
        self.set_y(10 + altura + 6)


def _texto_que_cabe(pdf, texto, largura_celula, folga=2):
    """
    Encurta o texto com '...' até caber na célula. pdf.cell() não quebra nem corta: texto maior que
    a largura vaza sobre a célula vizinha. Login e nome são digitados livremente, então não há
    limite fixo de caracteres; a medida é em mm, na fonte ativa na chamada.
    """
    texto = str(texto)
    limite = largura_celula - folga
    if pdf.get_string_width(texto) <= limite:
        return texto
    while texto and pdf.get_string_width(texto + "...") > limite:
        texto = texto[:-1]
    return texto + "..." if texto else ""


MESES_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def formatar_data_relatorio(cidade=""):
    """
    Data de hoje por extenso (ex.: 'Arraias - TO, 07 de setembro de 2026'). É calculada fora da
    função cacheada (gerar_pdf_relatorio) e passada como argumento, entrando na chave do
    @st.cache_data: o cache se renova quando o dia muda.
    """
    hoje = date.today()
    texto = f"{hoje.day:02d} de {MESES_PT[hoje.month - 1]} de {hoje.year}"
    return f"{cidade}, {texto}" if cidade else texto


LARGURA_ROTULO_CABECALHO_PDF = 32  # mm — cabe "Professor(a):" em negrito 10pt


def _linha_dado_pdf(pdf, rotulo, valor):
    pdf.set_font("CMU", 'B', 10)
    pdf.cell(LARGURA_ROTULO_CABECALHO_PDF, 6, text=f"{rotulo}:", align='L')
    pdf.set_font("CMU", '', 10)
    pdf.cell(0, 6, text=valor, align='L', new_x="LMARGIN", new_y="NEXT")


ALTURA_TITULO_GRAFICO_PDF = 10   # título (8mm) + respiro (2mm)
ALTURA_LINHA_GRAFICO_PDF = 7
MINIMO_BARRAS_POR_PAGINA = 3     # nunca deixa 1 ou 2 barras soltas numa página


def _grafico_barras_pdf(pdf, titulo, itens, x_tabela, largura_tabela):
    """
    Gráfico de barras horizontais (uma por aluno), desenhado à mão com rect().

    itens: lista de (rótulo, fração 0-1 da barra, texto do valor, cor hex).

    Regras de página:
    - cabe no espaço restante: fica onde está;
    - não cabe: começa em uma página nova e ocupa só a(s) página(s) dele (quem chamou deve abrir
      outra página antes do próximo conteúdo);
    - passa de uma página (turma grande): quebra sem deixar barra solta (mínimo de
      MINIMO_BARRAS_POR_PAGINA por página) e repete o título com "(continuação)".
    Retorna True se o gráfico usou páginas próprias, False se coube no lugar.
    """
    largura_rotulo, largura_valor = 35, 15
    largura_barra_max = largura_tabela - largura_rotulo - largura_valor
    x_inicio_barra = x_tabela + largura_rotulo
    fundo = pdf.h - pdf.b_margin

    def cabecalho(texto):
        pdf.set_font("CMU", 'B', 13)
        pdf.set_x(x_tabela)
        pdf.cell(largura_tabela, 8, text=texto, align='C', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("CMU", '', 10)

    def desenhar(bloco):
        for rotulo, fracao, texto_valor, cor in bloco:
            y_linha = pdf.get_y()
            pdf.set_x(x_tabela)
            pdf.cell(largura_rotulo, ALTURA_LINHA_GRAFICO_PDF, text=_texto_que_cabe(pdf, rotulo, largura_rotulo))
            largura_barra = fracao * largura_barra_max
            if largura_barra > 0:
                pdf.set_fill_color(*hex_para_rgb(cor))
                pdf.rect(x_inicio_barra, y_linha + 1, largura_barra, 5, style='F')
            pdf.set_xy(x_inicio_barra + largura_barra_max, y_linha)
            pdf.cell(largura_valor, ALTURA_LINHA_GRAFICO_PDF, text=texto_valor, align='R', new_x="LMARGIN", new_y="NEXT")

    altura_total = ALTURA_TITULO_GRAFICO_PDF + len(itens) * ALTURA_LINHA_GRAFICO_PDF
    if pdf.get_y() + altura_total <= fundo:
        cabecalho(titulo)
        desenhar(itens)
        return False

    pdf.add_page()
    capacidade = int((fundo - pdf.get_y() - ALTURA_TITULO_GRAFICO_PDF) // ALTURA_LINHA_GRAFICO_PDF)
    tamanhos = []
    restante = len(itens)
    while restante > 0:
        tamanhos.append(min(capacidade, restante))
        restante -= tamanhos[-1]
    if len(tamanhos) > 1 and tamanhos[-1] < MINIMO_BARRAS_POR_PAGINA:
        falta = MINIMO_BARRAS_POR_PAGINA - tamanhos[-1]
        tamanhos[-2] -= falta
        tamanhos[-1] += falta
    inicio = 0
    for i, n in enumerate(tamanhos):
        if i > 0:
            pdf.add_page()
        cabecalho(titulo if i == 0 else f"{titulo} (continuação)")
        desenhar(itens[inicio:inicio + n])
        inicio += n
    return True


@st.cache_data
def nome_de_arquivo(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_") or "conteudo"


def gerar_pdf_relatorio(lista_geral, conteudo_titulo, linhas_conteudo, nome_instituicao="", nome_professor="", turma="", data_relatorio="", linhas_bncc=None, acerto=None):
    """
    Gera o PDF com margens laterais simétricas, título centralizado e duas tabelas: Desempenho da
    Turma e Detalhamento do conteúdo em tela.

    Cacheado com @st.cache_data: o st.tabs() renderiza todas as abas, então sem cache o PDF (com
    fonte embutida) seria gerado de novo para cada conteúdo a cada clique. O cache só recalcula
    quando os argumentos (dados dos alunos, instituição, professor) mudam.

    Fonte CMU Serif (Computer Modern Unicode) embutida via TTF, em vez da Arial padrão do fpdf2,
    para o visual de documento acadêmico. Os arquivos ficam em fonts/ (licença OFL, ver
    fonts/OFL.txt) e precisam ser embutidos porque os leitores de PDF não têm a fonte. Negrito só no
    título, subtítulos e cabeçalho das tabelas.
    """
    pdf = _PDFComCabecalho()
    pdf.add_font("CMU", "", "fonts/CMUSerif-Roman.ttf")
    pdf.add_font("CMU", "B", "fonts/CMUSerif-Bold.ttf")
    pdf.set_margins(left=20, top=20, right=20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    largura_util = pdf.w - pdf.l_margin - pdf.r_margin  # 170mm em A4 com margens de 20mm

    if nome_instituicao:
        _linha_dado_pdf(pdf, "Instituição", nome_instituicao)
    if nome_professor:
        _linha_dado_pdf(pdf, "Professor(a)", nome_professor)
    if turma:
        _linha_dado_pdf(pdf, "Turma", turma)
    _linha_dado_pdf(pdf, "Conteúdo", conteudo_titulo)  # o PDF sai de uma aba e fala só dela
    _linha_dado_pdf(pdf, "Data", data_relatorio)
    pdf.ln(3)

    pdf.set_font("CMU", 'B', 16)
    pdf.cell(largura_util, 10, text="Relatório de Desempenho - Trilha de Aprendizagem", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    """
    --- Tabela 1: Desempenho da turma ---
    Tabela mais estreita que a largura útil e centralizada, com aparência de relatório. pdf.cell()
    com new_x="LMARGIN" volta à margem esquerda no fim da linha, então cada linha reposiciona o X no
    início da tabela.

    A coluna "Nome no Relatório" só aparece se alguém tiver preenchido; sem ela, o PDF mantém as 3
    colunas. Células de quem não preencheu ficam em branco, para completar à caneta. As larguras
    somam os mesmos 150mm nos dois casos: o espaço da coluna nova sai da folga das colunas
    numéricas, não das margens.
    """
    usar_nome_relatorio = any(str(l.get("Nome no Relatório", "")).strip() for l in lista_geral)

    """
    COM a coluna de nome, a tabela ocupa a largura útil inteira (170mm) e a coluna do nome passa de
    52 para 72mm, sem cortar nomes completos. SEM ela, ficam os 150mm centralizados: com 3 colunas
    curtas, esticar de margem a margem deixaria a tabela desproporcional.
    """
    largura_tabela1 = largura_util if usar_nome_relatorio else 150  # 38+72+30+30 | 60+45+45
    x_tabela1 = pdf.l_margin + (largura_util - largura_tabela1) / 2
    pdf.set_font("CMU", 'B', 13)
    pdf.set_x(x_tabela1)
    pdf.cell(largura_tabela1, 8, text="Desempenho da Turma", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CMU", 'B', 11)
    pdf.set_x(x_tabela1)
    if usar_nome_relatorio:
        pdf.cell(38, 9, text="Login", border=1, align='C')
        pdf.cell(72, 9, text="Aluno", border=1, align='C')
        pdf.cell(30, 9, text="XP Total", border=1, align='C')
        pdf.cell(30, 9, text="Erros", border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(60, 9, text="Aluno", border=1, align='C')
        pdf.cell(45, 9, text="XP Total", border=1, align='C')
        pdf.cell(45, 9, text="Erros Totais", border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CMU", '', 11)
    for linha in lista_geral:
        pdf.set_x(x_tabela1)
        if usar_nome_relatorio:
            pdf.cell(38, 9, text=_texto_que_cabe(pdf, linha["Aluno"], 38), border=1, align='C')
            pdf.cell(72, 9, text=_texto_que_cabe(pdf, str(linha.get("Nome no Relatório", "")).strip(), 72), border=1, align='C')
            pdf.cell(30, 9, text=str(linha["XP Total"]), border=1, align='C')
            pdf.cell(30, 9, text=str(linha["Erros Totais"]), border=1, align='C', new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(60, 9, text=_texto_que_cabe(pdf, linha["Aluno"], 60), border=1, align='C')
            pdf.cell(45, 9, text=str(linha["XP Total"]), border=1, align='C')
            pdf.cell(45, 9, text=str(linha["Erros Totais"]), border=1, align='C', new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)

    grafico_xp_isolado = False
    if lista_geral:
        maior_xp = max((linha["XP Total"] for linha in lista_geral), default=0) or 1
        itens_xp = [(l["Aluno"], l["XP Total"] / maior_xp, str(l["XP Total"]), l.get("Cor", "#ff4b4b")) for l in lista_geral]
        grafico_xp_isolado = _grafico_barras_pdf(pdf, "Gráfico de XP por Aluno", itens_xp, x_tabela1, largura_tabela1)

    if linhas_bncc:
        if grafico_xp_isolado:
            pdf.add_page()
        else:
            pdf.ln(6)
        largura_bncc = 150  # 45 + 25 + 40 + 40
        x_bncc = pdf.l_margin + (largura_util - largura_bncc) / 2
        pdf.set_font("CMU", 'B', 13)
        pdf.set_x(x_bncc)
        pdf.cell(largura_bncc, 8, text="Desempenho por Habilidade da BNCC", align='C', new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("CMU", 'B', 11)
        pdf.set_x(x_bncc)
        pdf.cell(45, 9, text="Habilidade", border=1, align='C')
        pdf.cell(25, 9, text="Missões", border=1, align='C')
        pdf.cell(40, 9, text="Conclusões", border=1, align='C')
        pdf.cell(40, 9, text="% Concluído", border=1, align='C', new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("CMU", '', 11)
        for linha in linhas_bncc:
            pdf.set_x(x_bncc)
            pdf.cell(45, 9, text=_texto_que_cabe(pdf, linha["Habilidade"], 45), border=1, align='C')
            pdf.cell(25, 9, text=str(linha["Missões"]), border=1, align='C')
            pdf.cell(40, 9, text=f'{linha["Conclusões"]}/{linha["Possíveis"]}', border=1, align='C')
            pdf.cell(40, 9, text=f'{linha["% Concluído"]}%', border=1, align='C', new_x="LMARGIN", new_y="NEXT")

    if acerto and acerto[0]:
        habilidades_ac, linhas_ac = acerto
        pdf.add_page()
        pdf.set_font("CMU", 'B', 13)
        pdf.cell(largura_util, 8, text="Acerto por Habilidade", align='C', new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("CMU", '', 10)
        pdf.cell(largura_util, 6, text="Entre parênteses: acertos e tentativas.", align='C', new_x="LMARGIN", new_y="NEXT")
        pdf.cell(largura_util, 6, text="Verde a partir de 70%. Amarelo de 40% a 69%. Vermelho abaixo de 40%. Traço: sem tentativa.", align='C', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        por_tabela, larg_nome, larg_hab = 5, 30, 28
        for ini in range(0, len(habilidades_ac), por_tabela):
            bloco_h = habilidades_ac[ini:ini + por_tabela]
            x_ac = pdf.l_margin + (largura_util - (larg_nome + larg_hab * len(bloco_h))) / 2
            pdf.set_font("CMU", 'B', 9)
            pdf.set_x(x_ac)
            pdf.cell(larg_nome, 9, text="Aluno", border=1, align='C')
            for k, h in enumerate(bloco_h):
                fim = "LMARGIN" if k == len(bloco_h) - 1 else "RIGHT"
                pdf.cell(larg_hab, 9, text=h, border=1, align='C', new_x=fim, new_y="NEXT" if fim == "LMARGIN" else "TOP")
            pdf.set_font("CMU", '', 10)
            for rotulo, pares in linhas_ac:
                eh_turma = rotulo == "Turma"
                pdf.set_font("CMU", 'B' if eh_turma else '', 10)
                if eh_turma:
                    pdf.set_text_color(31, 58, 110)
                else:
                    pdf.set_text_color(0, 0, 0)
                pdf.set_x(x_ac)
                if eh_turma:
                    pdf.set_fill_color(241, 243, 245)  # cinza com texto azul escuro, cor própria da linha da turma
                    pdf.cell(larg_nome, 9, text=rotulo, border=1, align='C', fill=True)
                else:
                    pdf.cell(larg_nome, 9, text=_texto_que_cabe(pdf, rotulo, larg_nome), border=1, align='C')
                for k, par in enumerate(pares[ini:ini + por_tabela]):
                    pct = _percentual_acerto(par)
                    if eh_turma:
                        pdf.set_fill_color(241, 243, 245)
                    elif pct is None:
                        pdf.set_fill_color(255, 255, 255)
                    else:
                        cor = _fundo_acerto(pct).split("#")[1][:6]
                        pdf.set_fill_color(int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16))
                    fim = "LMARGIN" if k == len(bloco_h) - 1 else "RIGHT"
                    pdf.cell(larg_hab, 9, text=_texto_acerto(par), border=1, align='C', fill=True,
                             new_x=fim, new_y="NEXT" if fim == "LMARGIN" else "TOP")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(6)

    """
    Desempenho da Turma (tabela + gráfico de XP) em uma página e Detalhamento por Conteúdo (tabela +
    gráfico de %) começando limpo na próxima, para a quebra automática não cair no meio de uma
    seção.
    """
    pdf.add_page()

    largura_tabela2 = largura_util if usar_nome_relatorio else 150  # 38+68+26+20+18 | 50+30+40+30
    x_tabela2 = pdf.l_margin + (largura_util - largura_tabela2) / 2
    pdf.set_font("CMU", 'B', 13)
    pdf.set_x(x_tabela2)
    pdf.cell(largura_tabela2, 8, text=f"Detalhamento - {conteudo_titulo}", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CMU", 'B', 11)
    pdf.set_x(x_tabela2)
    if usar_nome_relatorio:
        """
        38+68+26+20+18 = 170 (largura útil inteira). A coluna de login tem os mesmos 38mm da tabela
        1, pois com 32mm um login comprido colidia com a coluna vizinha. Os cabeçalhos são
        encurtados ("Total" em vez de "Total Missões") para caber em 5 colunas.
        """
        pdf.cell(38, 9, text="Login", border=1, align='C')
        pdf.cell(68, 9, text="Aluno", border=1, align='C')
        pdf.cell(26, 9, text="Concluídas", border=1, align='C')
        pdf.cell(20, 9, text="Total", border=1, align='C')
        pdf.cell(18, 9, text="Erros", border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(50, 9, text="Aluno", border=1, align='C')
        pdf.cell(30, 9, text="Concluídas", border=1, align='C')
        pdf.cell(40, 9, text="Total Missões", border=1, align='C')
        pdf.cell(30, 9, text="Erros", border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CMU", '', 11)
    for linha in linhas_conteudo:
        pdf.set_x(x_tabela2)
        if usar_nome_relatorio:
            pdf.cell(38, 9, text=_texto_que_cabe(pdf, linha["Aluno"], 38), border=1, align='C')
            pdf.cell(68, 9, text=_texto_que_cabe(pdf, str(linha.get("Nome no Relatório", "")).strip(), 68), border=1, align='C')
            pdf.cell(26, 9, text=str(linha["Missões Concluídas"]), border=1, align='C')
            pdf.cell(20, 9, text=str(linha["Total de Missões"]), border=1, align='C')
            pdf.cell(18, 9, text=str(linha["Erros"]), border=1, align='C', new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(50, 9, text=_texto_que_cabe(pdf, linha["Aluno"], 50), border=1, align='C')
            pdf.cell(30, 9, text=str(linha["Missões Concluídas"]), border=1, align='C')
            pdf.cell(40, 9, text=str(linha["Total de Missões"]), border=1, align='C')
            pdf.cell(30, 9, text=str(linha["Erros"]), border=1, align='C', new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)

    if linhas_conteudo:
        itens_pct = []
        for linha in linhas_conteudo:
            total_linha = linha["Total de Missões"]
            pct = (linha["Missões Concluídas"] / total_linha * 100) if total_linha else 0
            itens_pct.append((linha["Aluno"], pct / 100, f"{pct:.0f}%", cor_por_percentual_concluido(pct)))
        _grafico_barras_pdf(pdf, "Gráfico de % Concluído", itens_pct, x_tabela2, largura_tabela2)

    return bytes(pdf.output())
