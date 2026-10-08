import os
import sys
import subprocess
import time
import json
import hashlib
import uuid
import html
import functools
import re
import unicodedata
import base64
import sqlite3
from datetime import date, datetime, timedelta, timezone
import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import pandas as pd
import altair as alt
from fpdf import FPDF
from PIL import Image  # só pra ler a proporção do cabecalho.png (ver _PDFComCabecalho)


# Ancora o diretório de trabalho na pasta deste arquivo. Sem isso, todos os
# caminhos relativos (logo.png, banner.png, banco_alunos.json, etc.) só
# funcionam se quem rodar o script já estiver "dentro" desta pasta no
# terminal — o botão Play do VS Code, por exemplo, nem sempre garante isso.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ==========================================
# 1. CONFIGURAÇÃO E ARQUIVOS DE MEMÓRIA
# ==========================================
# As artes ficam aqui em cima, e não junto dos outros ARQUIVO_* mais abaixo,
# porque st.set_page_config() precisa do caminho da logo e tem que ser a
# PRIMEIRA chamada st.* do script — não dá pra declarar depois. Antes o caminho
# estava repetido literalmente dentro do set_page_config; quando as imagens
# foram pra pasta imagens/, essa cópia esquecida faria o ícone da aba cair no
# fallback 🎓 silenciosamente, sem erro nenhum. Uma constante só evita isso.
#
# imagens/ é para as artes do projeto (como fonts/ é para as fontes). Não
# confundir com static/, que é funcional: o Streamlit serve aquela pasta em
# app/static/ (enableStaticServing no .streamlit/config.toml) e o manifest e os
# ícones do PWA dependem daquele caminho literal — não mover.
ARQUIVO_LOGO = "static/logo.svg"                 # opcional: marca quadrada do projeto em vetor, um arquivo só para barra lateral, ícone da aba e ícone do app instalado (por isso fica em static/, que o manifest alcança por URL)
ARQUIVO_BANNER = "imagens/banner.svg"            # opcional: arte pronta para o topo da Página Inicial (ideal 1200x400px ou 1500x500px, formato "capa" tipo Facebook/Twitter — pode já vir com a logo embutida, feita no Photoshop)
ARQUIVO_CABECALHO = "imagens/cabecalho.png"      # opcional: timbre institucional no topo de toda página do relatório em PDF. Tem que ser PNG (o fpdf2 não embute PDF); exportar com ~2008px de largura = 300 DPI nos 170mm da página. A altura é livre, o código lê a proporção do arquivo

st.set_page_config(
    page_title="Trilha de Aprendizagem",
    page_icon=ARQUIVO_LOGO if os.path.exists(ARQUIVO_LOGO) else "🎓",
    layout="wide"
)


def _injetar_manifest_pwa():
    """Substitui o <link rel="manifest"> e o <link rel="apple-touch-icon"> no
    <head> real da página (via window.parent, já que este componente roda
    num iframe à parte) pelos nossos, apontando pros ícones da logo do projeto
    servidos como arquivo de verdade em /static (ver .streamlit/config.toml,
    "enableStaticServing").

    O próprio Streamlit já injeta essas duas tags por padrão (manifest
    genérico com name "Streamlit" e favicon_256.png do framework) — por isso
    não dá pra só acrescentar quando "não existir": a tag do Streamlit sempre
    existe primeiro, então é preciso achar a que já está lá e trocar o href.

    Importante: o href do manifest e dos ícones precisa ser uma URL de
    arquivo real — uma tentativa anterior usando "data:" URI embutida veio
    vazia porque não é um formato garantido pra src de ícone de manifest, e
    o Android silenciosamente ignorava e caía no ícone genérico."""
    if not os.path.exists("static/manifest.json"):
        return
    components.html(
        """
        <script>
        (function() {
            const doc = window.parent.document;
            let manifestLink = doc.querySelector('link[rel="manifest"]');
            if (!manifestLink) {
                manifestLink = doc.createElement('link');
                manifestLink.rel = 'manifest';
                doc.head.appendChild(manifestLink);
            }
            manifestLink.href = 'app/static/manifest.json?v=8';

            let appleIcon = doc.querySelector('link[rel="apple-touch-icon"]');
            if (!appleIcon) {
                appleIcon = doc.createElement('link');
                appleIcon.rel = 'apple-touch-icon';
                doc.head.appendChild(appleIcon);
            }
            appleIcon.href = 'app/static/logo.svg?v=2';
        })();
        </script>
        """,
        height=0,
        width=0,
    )


_injetar_manifest_pwa()


def _injetar_bloqueio_espaco_apelido():
    """Tira o espaço do campo de apelido assim que ele aparece, como em campo
    de nome de usuário de site — funciona digitando, colando ou em qualquer
    teclado, inclusive o virtual de celular.

    Versão anterior escutava 'keydown' (a tecla sendo pressionada) e bloqueava
    o espaço antes de entrar. Funcionava em teclado físico, mas boa parte dos
    teclados virtuais de celular (Android, iPhone) não dispara um 'keydown' de
    verdade pra cada tecla — o texto entra no campo por outro caminho, sem
    passar pelo evento que a versão antiga escutava. Resultado: bloqueava no
    computador e deixava passar no celular.

    A correção ouve 'input' em vez de 'keydown'. 'input' dispara sempre que o
    VALOR do campo muda de verdade, não importa como — teclado físico, teclado
    virtual, colar, ditado por voz. Deixa o espaço entrar e tira na mesma hora,
    então o efeito visual pro aluno é o mesmo (o espaço nunca fica ali), só que
    funciona em qualquer aparelho.

    O guard `if (limpo === el.value) return` evita loop infinito: só mexemos
    no campo quando há espaço de verdade pra tirar; sem espaço, o handler não
    reescreve o valor e não dispara a si mesmo de novo.

    Isto é conveniência de digitação, NÃO validação: apelido_invalido() continua
    valendo no servidor e é ela que garante a regra mesmo se o JS estiver
    desligado ou o navegador se comportar diferente do esperado."""
    components.html(
        """
        <script>
        (function() {
            const win = window.parent;
            if (win.__bloqueioEspacoApelido) return;
            win.__bloqueioEspacoApelido = true;

            function ehCampoApelido(el) {
                return el && el.tagName === 'INPUT'
                    && (el.getAttribute('aria-label') || '').toLowerCase().includes('apelido');
            }

            win.document.addEventListener('input', function(e) {
                const el = e.target;
                if (!ehCampoApelido(el)) return;
                const limpo = el.value.replace(/\\s+/g, '');
                if (limpo === el.value) return;
                const setter = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
                setter.call(el, limpo);
                el.dispatchEvent(new Event('input', {bubbles: true}));
            }, true);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


_injetar_bloqueio_espaco_apelido()


def _injetar_aviso_saida():
    """Aviso nativo do navegador ('Sair do site? Alterações podem não ser
    salvas') antes de fechar a aba, atualizar ou navegar pra fora.

    Esse app é uma SPA (single page application, ver conversa de 2026-09-03):
    tudo acontece dentro de uma única página carregada, trocando de conteúdo
    via WebSocket — nunca existe uma "página anterior" de verdade. Por isso
    o botão Voltar do navegador não tem pra onde voltar dentro do app, e sai
    fora dele sem aviso nenhum, confundindo quem tá usando. O texto do aviso
    é fixo, definido pelo próprio navegador por segurança (nenhum site pode
    customizar essa mensagem desde ~2011) — só dá pra ligar/desligar, não
    mudar a aparência."""
    components.html(
        """
        <script>
        (function() {
            const win = window.parent;
            if (win.__avisoSaidaAtivo) return;
            win.__avisoSaidaAtivo = true;
            win.addEventListener('beforeunload', function (e) {
                e.preventDefault();
                e.returnValue = '';
            });
        })();
        </script>
        """,
        height=0,
        width=0,
    )


_injetar_aviso_saida()


def _injetar_liberar_scroll_grafico():
    """Deixa a página rolar normalmente quando o mouse está em cima de um
    gráfico (Altair/Vega-Lite).

    O wrapper do próprio Streamlit (.stVegaLiteChart) intercepta o scroll do
    mouse em cima de QUALQUER gráfico, mesmo sem nenhuma opção de zoom/pan
    ligada no gráfico em si — confirmado direto no navegador (nenhum gráfico
    deste app usa .interactive(), e mesmo assim o scroll travava; e trocar
    st.bar_chart por Altair puro, testado antes, não resolveu — o bloqueio
    vem do wrapper do Streamlit, não da biblioteca do gráfico). Quem tenta
    rolar a página com o cursor em cima de um gráfico ficava "preso" ali.

    Como a captura acontece num listener interno do Streamlit/Vega, não dá
    pra simplesmente "desligar" essa opção — a correção é ouvir o evento de
    scroll ANTES dele (fase de captura, que sempre roda primeiro, não importa
    o que outro listener faça depois) e, se o alvo for dentro de um gráfico,
    rolar a área principal da página (.stMain, que é quem de fato tem a
    barra de rolagem no Streamlit) manualmente."""
    components.html(
        """
        <script>
        (function() {
            const win = window.parent;
            if (win.__liberaScrollGraficoAtivo) return;
            win.__liberaScrollGraficoAtivo = true;
            win.document.addEventListener('wheel', function (e) {
                const dentroDeGrafico = e.target.closest && e.target.closest('.stVegaLiteChart');
                if (!dentroDeGrafico) return;
                const areaPrincipal = win.document.querySelector('.stMain');
                if (!areaPrincipal) return;
                areaPrincipal.scrollTop += e.deltaY;
                e.preventDefault();
            }, { capture: true, passive: false });
        })();
        </script>
        """,
        height=0,
        width=0,
    )


_injetar_liberar_scroll_grafico()


def _injetar_clique_logo_inicio():
    """Faz a LOGO (imagem) também levar pra Início ao clicar, não só o texto
    "Trilha de Aprendizagem" ao lado — pedido do Wenes (2026-09-13): pra ele
    logo+título são "um objeto só" (é assim que funciona em praticamente todo
    site/app), então clicar em qualquer parte tem que navegar.

    st.image() não tem on_click nem aceita link. A solução é ouvir clique em
    qualquer lugar dentro do cabeçalho (".st-key-sidebar_cabecalho") e, se não
    foi um clique direto no botão de título, simular um clique nele — reaproveita
    a navegação que o botão já faz, sem duplicar lógica de rerun/session_state."""
    components.html(
        """
        <script>
        (function() {
            const win = window.parent;
            if (win.__cliqueLogoInicioAtivo) return;
            win.__cliqueLogoInicioAtivo = true;
            win.document.addEventListener('click', function (e) {
                const cabecalho = e.target.closest && e.target.closest('div[class*="st-key-sidebar_cabecalho"]');
                if (!cabecalho) return;
                const botao = cabecalho.querySelector('div[class*="st-key-nav_titulo_inicio"] button');
                if (!botao || e.target.closest('button') === botao) return;
                botao.click();
            }, { capture: true });
        })();
        </script>
        """,
        height=0,
        width=0,
    )


_injetar_clique_logo_inicio()

# Pasta dos dados que mudam durante o uso (banco de alunos, conteúdos, configuração).
# Localmente é a própria pasta do projeto. Na hospedagem (Fly.io) aponta para o
# volume de disco persistente, via variável TRILHA_DIR_DADOS=/data — só o volume
# sobrevive a reinícios; o resto do disco do servidor é refeito a cada publicação.
DIR_DADOS = os.environ.get("TRILHA_DIR_DADOS", ".")
os.makedirs(DIR_DADOS, exist_ok=True)

ARQUIVO_DADOS_ESTATISTICA = os.path.join(DIR_DADOS, "dados_turma.json")   # amostra numérica usada pelo conteúdo nativo de Estatística
ARQUIVO_ALUNOS = os.path.join(DIR_DADOS, "banco_alunos.json")             # formato antigo (só lido uma vez, pra migrar pro SQLite abaixo)
ARQUIVO_ALUNOS_DB = os.path.join(DIR_DADOS, "banco_alunos.db")            # progresso dos alunos (SQLite — suporta vários alunos salvando ao mesmo tempo sem corromper dados)
ARQUIVO_CONTEUDOS = os.path.join(DIR_DADOS, "conteudos.json")             # conteúdos cadastrados (nativos + criados pelo professor)
ARQUIVO_CONFIG = os.path.join(DIR_DADOS, "config_sistema.json")           # configurações gerais (senha do professor)
                                                 # ARQUIVO_LOGO / ARQUIVO_BANNER / ARQUIVO_CABECALHO ficam lá no topo do
                                                 # arquivo, antes do st.set_page_config() — ver o comentário de lá.

# Senha inicial do Painel do Professor.
# O professor pode (e deve) trocá-la dentro do próprio painel, em "⚙️ Configurações".
SENHA_PADRAO_PROFESSOR = "computa258"

# Paleta de cores suaves pra destacar os cartões de "Conteúdos disponíveis" do
# fundo (funciona em tema claro e escuro — ver CSS ".cartao-cor-*" mais abaixo).
# Cicla nessa ordem conforme novos conteúdos são cadastrados.
PALETA_CORES_CARTAO = ["azul", "roxo", "rosa", "amarelo", "verde", "ciano"]

ID_CONTEUDO_ESTATISTICA = "estatistica"                    # id fixo do conteúdo nativo do sistema
ID_CONTEUDO_FREQUENCIA = "estatistica_frequencia"          # id fixo do 2º conteúdo nativo (EM13MAT408, reusa os mesmos dados)
ID_CONTEUDO_LEITURA_GRAFICA = "estatistica_leitura_grafica"  # id fixo do 3º conteúdo nativo (EM13MAT102, cenário fixo)
ID_CONTEUDO_COMPARACAO = "estatistica_comparacao_diagramas"  # id fixo do 4º conteúdo nativo (EM13MAT409, reusa os mesmos dados)
ID_CONTEUDO_PESQUISA_AMOSTRAL = "estatistica_pesquisa_amostral"  # id fixo do 5º conteúdo nativo (EM13MAT202, decisões de planejamento)
ID_CONTEUDO_TENDENCIA = "estatistica_tendencia"  # id fixo do 6º conteúdo nativo (EM13MAT510, cenário próprio — não usa dados_estatistica)

# Os 3 conteúdos nativos de Estatística aparecem pro aluno como UM item só
# ("📊 Estatística", ver PAGINA_ESTATISTICA_HUB) em vez de 3 itens soltos no
# menu/Início — 3 itens diluíam a identidade de Estatística no meio das
# outras matérias, exatamente o problema que o orientador apontou (pedido de
# 2026-09-11: reforçar o foco original em Estatística). Cada um continua
# sendo seu próprio conteúdo (progresso, XP e BNCC separados) — a mudança é
# só de navegação/vitrine, não de dado.
IDS_ESTATISTICA_HUB = [ID_CONTEUDO_ESTATISTICA, ID_CONTEUDO_FREQUENCIA, ID_CONTEUDO_LEITURA_GRAFICA, ID_CONTEUDO_COMPARACAO, ID_CONTEUDO_PESQUISA_AMOSTRAL, ID_CONTEUDO_TENDENCIA]

# Número de faixas da tabela de frequência do conteúdo nativo acima. As faixas
# são calculadas a partir do menor e maior valor REAL de cada vez (não fixas em
# "0 a 10"), pra funcionar com qualquer amostra que o professor cadastrar em
# "Editar dados numéricos" — nota, idade, altura — igual ao resto da
# Estatística (ver calcular_frequencia).
FREQ_N_FAIXAS = 5

# Largura fixa (px) dos gráficos de barra do conteúdo de Estatística (Frequência
# e Leitura Crítica). Sem isso, use_container_width deixa o gráfico esticado até
# a largura inteira da coluna — exagerado pra um gráfico de só 2 a 5 barras,
# e sem nenhum motivo (o relatório em PDF também usa tabela estreita e
# centralizada, não esticada de ponta a ponta, pelo mesmo motivo).
LARGURA_GRAFICO = 380

# Cenário fixo do Caso 1 (eixo cortado) do conteúdo de Leitura Crítica de
# Gráficos. Diferente de Estatística e Frequência, EM13MAT102 fala de gráfico
# e pesquisa DIVULGADOS NA MÍDIA — não faz sentido usar as notas da turma
# aqui, então os números são um exemplo ilustrativo fixo, pensado pra deixar
# o efeito do eixo cortado bem visível (diferença real pequena, mas que
# parece enorme no gráfico manipulado).
LEITURA_CASO1_CATEGORIAS = ["Produto A", "Produto B"]
LEITURA_CASO1_VALORES = [48, 50]
LEITURA_CASO1_EIXO_CORTADO = 45

# Cenário fixo do conteúdo "Relação entre Duas Variáveis" (EM13MAT510). Esta
# habilidade pede DUAS variáveis numéricas por item (ex.: horas de estudo e
# nota) -- o resto da Estatística nativa guarda só UMA lista de números
# (dados_estatistica), então não dá pra reaproveitar: precisaria de uma tela
# nova pro professor digitar pares e um arquivo de dado novo pra guardar
# isso. Optou-se por um cenário ilustrativo fixo (mesmo padrão já usado em
# Leitura Crítica de Gráficos), evitando essa infraestrutura nova.
TENDENCIA_HORAS_ESTUDO = [1, 2, 2, 3, 4, 4, 5, 6, 7, 8]
TENDENCIA_NOTAS = [4.0, 4.5, 5.5, 6.0, 6.0, 7.0, 7.5, 7.5, 8.5, 9.0]


# ---------- Conteúdos (menu / sumário) ----------
def conteudo_padrao_estatistica():
    return {
        "titulo": "Estatística Descritiva",
        "icone": "📊",
        "tipo": "estatico",  # conteúdo nativo: cálculo dinâmico a partir dos dados da turma
        "descricao": "Medidas de tendência central e dispersão calculadas sobre um conjunto de dados."
    }

def conteudo_padrao_frequencia():
    return {
        "titulo": "Tabela e Gráfico de Frequência",
        "icone": "📶",
        "tipo": "estatico",  # conteúdo nativo: mesma amostra da Estatística Descritiva, agrupada em faixas
        "descricao": "Organize uma amostra em faixas e leia o gráfico de frequência resultante."
    }

def conteudo_padrao_leitura_grafica():
    return {
        "titulo": "Leitura Crítica de Gráficos",
        "icone": "🔍",
        "tipo": "estatico",  # conteúdo nativo: cenário fixo, não depende dos dados da turma
        "descricao": "Aprenda a desconfiar de gráfico e pesquisa da mídia: escala manipulada e amostra não representativa."
    }

def conteudo_padrao_comparacao():
    return {
        "titulo": "Comparando Diagramas",
        "icone": "📦",
        "tipo": "estatico",  # conteúdo nativo: mesma amostra da Estatística Descritiva, em 3 diagramas diferentes
        "descricao": "Histograma, box-plot e ramos-e-folhas: três formas de olhar pra mesma amostra, cada uma boa pra uma pergunta diferente."
    }

def conteudo_padrao_pesquisa_amostral():
    return {
        "titulo": "Planejando uma Pesquisa",
        "icone": "📋",
        "tipo": "estatico",  # conteúdo nativo: decisões de planejamento, não cálculo — reusa a amostra da turma
        "descricao": "População x amostra, e como os dados de uma amostra viram um relatório de verdade: da coleta até as medidas."
    }

def conteudo_padrao_tendencia():
    return {
        "titulo": "Relação entre Duas Variáveis",
        "icone": "📈",
        "tipo": "estatico",  # conteúdo nativo: cenário fixo próprio, não depende dos dados da turma
        "descricao": "Horas de estudo e nota: como duas variáveis se relacionam, e como uma reta ajuda a enxergar (e prever) essa relação."
    }

def carregar_conteudos():
    conteudos = {}
    if os.path.exists(ARQUIVO_CONTEUDOS):
        try:
            with open(ARQUIVO_CONTEUDOS, "r", encoding="utf-8") as f:
                conteudos = json.load(f)
        except Exception:
            conteudos = {}
    if ID_CONTEUDO_ESTATISTICA not in conteudos:
        conteudos[ID_CONTEUDO_ESTATISTICA] = conteudo_padrao_estatistica()
    if ID_CONTEUDO_FREQUENCIA not in conteudos:
        conteudos[ID_CONTEUDO_FREQUENCIA] = conteudo_padrao_frequencia()
    if ID_CONTEUDO_LEITURA_GRAFICA not in conteudos:
        conteudos[ID_CONTEUDO_LEITURA_GRAFICA] = conteudo_padrao_leitura_grafica()
    if ID_CONTEUDO_COMPARACAO not in conteudos:
        conteudos[ID_CONTEUDO_COMPARACAO] = conteudo_padrao_comparacao()
    if ID_CONTEUDO_PESQUISA_AMOSTRAL not in conteudos:
        conteudos[ID_CONTEUDO_PESQUISA_AMOSTRAL] = conteudo_padrao_pesquisa_amostral()
    if ID_CONTEUDO_TENDENCIA not in conteudos:
        conteudos[ID_CONTEUDO_TENDENCIA] = conteudo_padrao_tendencia()
    # Nativos agrupados no topo, na ordem pedagógica de IDS_ESTATISTICA_HUB,
    # como ponto de partida — sem isso, "Estatística Descritiva" carregava
    # do JSON na posição em que foi salva (o topo), mas os outros 5 nativos
    # só existiam nos "if not in conteudos" acima, indo parar no FIM do
    # dict, espalhados atrás de todo conteúdo cadastrado pelo professor
    # (confuso, relatado pelo Wenes, 2026-09-14). Depois desse ponto de
    # partida, mover_conteudo() já deixa reordenar QUALQUER card livremente,
    # nativo ou não — isto aqui só evita começar bagunçado.
    conteudos = {
        **{cid: conteudos[cid] for cid in IDS_ESTATISTICA_HUB if cid in conteudos},
        **{cid: c for cid, c in conteudos.items() if cid not in IDS_ESTATISTICA_HUB},
    }
    return conteudos

def salvar_conteudos(conteudos):
    with open(ARQUIVO_CONTEUDOS, "w", encoding="utf-8") as f:
        json.dump(conteudos, f, ensure_ascii=False, indent=2)


# ---------- Configurações / Senha do professor ----------
def carregar_config():
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"senha_hash": hashlib.sha256(SENHA_PADRAO_PROFESSOR.encode()).hexdigest()}

def salvar_config(config):
    with open(ARQUIVO_CONFIG, "w") as f:
        json.dump(config, f)

def senha_correta(digitada, config):
    if not digitada:
        return False
    return hashlib.sha256(digitada.encode()).hexdigest() == config.get("senha_hash", "")


# ---------- Logo do projeto (opcional) ----------
def obter_logo_base64():
    """Retorna o logo.svg em base64 para uso em HTML customizado (banner), ou None se o arquivo não existir."""
    if os.path.exists(ARQUIVO_LOGO):
        try:
            with open(ARQUIVO_LOGO, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return None
    return None


# ---------- Dados numéricos usados pelo conteúdo nativo de Estatística ----------
def carregar_dados_estatistica():
    if os.path.exists(ARQUIVO_DADOS_ESTATISTICA):
        try:
            with open(ARQUIVO_DADOS_ESTATISTICA, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return [8.5, 7.0, 9.2, 6.5, 10.0, 5.5, 8.0, 7.0]

def salvar_dados_estatistica(lista_dados):
    with open(ARQUIVO_DADOS_ESTATISTICA, "w") as f:
        json.dump(lista_dados, f)


# ---------- Banco de alunos (SQLite) ----------
# Trocado de JSON pra SQLite porque, numa aula de verdade, vários alunos
# respondem missões ao mesmo tempo. O jeito antigo lia o arquivo inteiro,
# mudava um pedaço e regravava o arquivo inteiro — se dois alunos salvassem
# quase juntos, o segundo podia sobrescrever e apagar o progresso do
# primeiro. Com SQLite, cada aluno grava só a própria linha (UPDATE/INSERT
# pontual), então um não pisa no dado do outro.
def perfil_padrao():
    return {"xp_total": 0, "progresso": {}, "inicio_sessao": time.time()}

def progresso_padrao():
    return {"missao_atual": 1, "erros": 0, "erros_missao_atual": 0, "historico": [], "respostas": {}}

def obter_conexao_db():
    conn = sqlite3.connect(ARQUIVO_ALUNOS_DB, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")     # permite ler e escrever ao mesmo tempo sem travar
    conn.execute("PRAGMA busy_timeout=10000")   # se o banco estiver ocupado, espera até 10s em vez de falhar na hora
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_banco_db():
    conn = obter_conexao_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alunos (
                nome TEXT PRIMARY KEY,
                xp_total INTEGER NOT NULL DEFAULT 0,
                inicio_sessao REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS progresso (
                aluno TEXT NOT NULL,
                conteudo_id TEXT NOT NULL,
                missao_atual INTEGER NOT NULL DEFAULT 1,
                erros INTEGER NOT NULL DEFAULT 0,
                historico TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (aluno, conteudo_id)
            )
        """)
        # "erros" (acima) é o total do conteúdo inteiro, usado no relatório do
        # professor. "erros_missao_atual" é zerado a cada vez que o aluno avança
        # de missão — é o que alimenta o desconto de XP por tentativa (ver
        # calcular_xp_por_desempenho): sem separar os dois, não teria como saber
        # quantas vezes o aluno errou NA MISSÃO ATUAL antes de acertar.
        colunas_progresso = {row["name"] for row in conn.execute("PRAGMA table_info(progresso)")}
        if "erros_missao_atual" not in colunas_progresso:
            conn.execute("ALTER TABLE progresso ADD COLUMN erros_missao_atual INTEGER NOT NULL DEFAULT 0")
        # "respostas" guarda {"1": "8", "2": "61.7", ...} — a resposta que o
        # aluno deu em cada missão já concluída. Faltava desde o começo: só
        # ficava em st.session_state (memória da sessão do navegador), nunca
        # no banco. "missao_atual" sim é salvo, então o aluno reabrindo o
        # app noutra sessão continuava exatamente de onde parou, mas as
        # linhas "✅ Missão N Concluída! (Resposta: ...)" das missões
        # anteriores apareciam com "None" — a sessão nova nunca teve aquele
        # valor em memória (bug relatado pelo Wenes, 2026-09-14).
        if "respostas" not in colunas_progresso:
            conn.execute("ALTER TABLE progresso ADD COLUMN respostas TEXT NOT NULL DEFAULT '{}'")
        # Nome que o professor quer ver NO RELATÓRIO ("João Batista"), separado
        # do "nome" com que o aluno faz login ("Goku99", "Player1"). São coisas
        # diferentes de propósito: "nome" é chave primária e liga o aluno ao
        # progresso dele, então renomear quebraria o vínculo — no próximo login
        # o aluno cairia num perfil vazio e perderia o XP. Esta coluna é só
        # exibição, nunca é usada pra buscar nada.
        colunas_alunos = {row["name"] for row in conn.execute("PRAGMA table_info(alunos)")}
        if "nome_relatorio" not in colunas_alunos:
            conn.execute("ALTER TABLE alunos ADD COLUMN nome_relatorio TEXT NOT NULL DEFAULT ''")
        # Contador de acessos: uma linha por dia com quantas vezes o app foi
        # aberto (cada sessão nova do navegador conta uma vez). Só o número:
        # não guarda IP, aparelho nem quem abriu.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS acessos (
                dia TEXT PRIMARY KEY,
                total INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Uma linha por TENTATIVA de resposta (acerto ou erro). É daqui que sai o
        # "acerto por aluno em cada habilidade" do Painel do Professor: o campo
        # "missao_atual" só diz até onde o aluno chegou, não quanto ele acertou.
        # Só passa a existir a partir da primeira resposta depois desta versão:
        # o histórico antigo não guardava o resultado de cada missão.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tentativas_missao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aluno TEXT NOT NULL,
                conteudo_id TEXT NOT NULL,
                missao INTEGER NOT NULL,
                acertou INTEGER NOT NULL,
                momento TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tentativas_aluno ON tentativas_missao (aluno)")
        conn.commit()
    finally:
        conn.close()

def dia_de_hoje_brasilia():
    """Data de hoje no horário de Brasília (UTC-3, sem horário de verão). O
    servidor do Fly.io roda em UTC, então date.today() viraria o dia às 21h."""
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d")

def registrar_acesso_se_novo():
    """Conta um acesso por sessão do navegador (não a cada clique). Atualizar
    a página (F5) abre sessão nova e conta de novo."""
    if st.session_state.get("_acesso_registrado"):
        return
    st.session_state["_acesso_registrado"] = True
    conn = obter_conexao_db()
    try:
        conn.execute(
            "INSERT INTO acessos (dia, total) VALUES (?, 1) "
            "ON CONFLICT(dia) DO UPDATE SET total = total + 1",
            (dia_de_hoje_brasilia(),),
        )
        conn.commit()
    finally:
        conn.close()

def contar_acessos():
    """Devolve (acessos de hoje, acessos no total)."""
    conn = obter_conexao_db()
    try:
        hoje = conn.execute("SELECT total FROM acessos WHERE dia = ?", (dia_de_hoje_brasilia(),)).fetchone()
        total = conn.execute("SELECT COALESCE(SUM(total), 0) FROM acessos").fetchone()[0]
        return (hoje[0] if hoje else 0), total
    finally:
        conn.close()

def migrar_json_para_sqlite_se_necessario():
    """Importa o banco_alunos.json antigo pro SQLite, uma única vez (se o
    banco novo ainda estiver vazio e o arquivo antigo existir)."""
    if not os.path.exists(ARQUIVO_ALUNOS):
        return
    conn = obter_conexao_db()
    try:
        ja_tem_dados = conn.execute("SELECT COUNT(*) FROM alunos").fetchone()[0] > 0
        if ja_tem_dados:
            return
        try:
            with open(ARQUIVO_ALUNOS, "r", encoding="utf-8") as f:
                dados_antigos = json.load(f)
        except Exception:
            return

        alunos_antigos = dados_antigos.get("alunos", {})
        for nome, perfil in alunos_antigos.items():
            # Compatibilidade com um formato ainda mais antigo (só Estatística,
            # sem "progresso" por conteúdo).
            if "progresso" not in perfil:
                perfil["progresso"] = {
                    ID_CONTEUDO_ESTATISTICA: {
                        "missao_atual": perfil.get("missao_atual", 1),
                        "erros": perfil.get("erros", 0),
                        "historico": perfil.get("historico", []),
                    }
                }
                perfil["xp_total"] = perfil.get("xp", 0)

            conn.execute(
                "INSERT OR REPLACE INTO alunos (nome, xp_total, inicio_sessao) VALUES (?, ?, ?)",
                (nome, perfil.get("xp_total", 0), perfil.get("inicio_sessao", time.time())),
            )
            for conteudo_id, prog in perfil.get("progresso", {}).items():
                conn.execute(
                    """INSERT OR REPLACE INTO progresso
                       (aluno, conteudo_id, missao_atual, erros, historico)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        nome, conteudo_id,
                        prog.get("missao_atual", 1),
                        prog.get("erros", 0),
                        json.dumps(prog.get("historico", []), ensure_ascii=False),
                    ),
                )
        conn.commit()
        try:
            os.rename(ARQUIVO_ALUNOS, ARQUIVO_ALUNOS + ".migrado_para_sqlite.bak")
        except OSError:
            pass
    finally:
        conn.close()

def carregar_todos_alunos_do_banco():
    """Lê o estado atual de TODOS os alunos direto do banco. Usado no Painel
    do Professor, que precisa ver o progresso da turma inteira em tempo
    real — não só o que a sessão do navegador do professor carregou uma vez."""
    conn = obter_conexao_db()
    try:
        alunos = {}
        for row in conn.execute("SELECT nome, xp_total, inicio_sessao, nome_relatorio FROM alunos"):
            alunos[row["nome"]] = {
                "xp_total": row["xp_total"],
                "inicio_sessao": row["inicio_sessao"],
                "nome_relatorio": row["nome_relatorio"] or "",
                "progresso": {},
            }
        for row in conn.execute("SELECT aluno, conteudo_id, missao_atual, erros, historico FROM progresso"):
            if row["aluno"] in alunos:
                alunos[row["aluno"]]["progresso"][row["conteudo_id"]] = {
                    "missao_atual": row["missao_atual"],
                    "erros": row["erros"],
                    "historico": json.loads(row["historico"]) if row["historico"] else [],
                }
        return alunos
    finally:
        conn.close()


# ==========================================
# 2. ESTADO DA SESSÃO
# ==========================================
inicializar_banco_db()
migrar_json_para_sqlite_se_necessario()
registrar_acesso_se_novo()

# A navegação tem UM eixo só: 'pagina' diz onde o aluno está.
# 'conteudo_ativo' só significa alguma coisa quando pagina == PAGINA_MATERIA, e
# 'aba_materia' só existe dentro de uma matéria. Antes eram dois eixos
# independentes ("qual página" x "qual matéria"), o que permitia estados sem
# sentido (Início + Frações) e fazia a Trilha de Missões depender de uma escolha
# feita em outro canto da tela — o aluno clicava sem saber onde ia parar.
PAGINA_INICIO = "inicio"
PAGINA_MATERIA = "materia"
PAGINA_PROFESSOR = "professor"
PAGINA_ESTATISTICA_HUB = "estatistica_hub"  # vitrine com os 3 sub-temas de Estatística (ver IDS_ESTATISTICA_HUB)

ABA_TEORIA = "📖 Teoria"
ABA_MISSOES = "🎮 Missões"

ABA_PROFESSOR_VISAO = "📊 Visão Geral"
ABA_PROFESSOR_CONTEUDOS = "➕ Gerenciar Conteúdos"
ABA_PROFESSOR_CONFIG = "⚙️ Configurações"

# A sessão do professor expira sozinha depois desse tempo SEM uso do painel
# (cada renderização do painel autenticado renova o prazo). Motivo: professor e
# aluno dividem a mesma sessão do navegador — é o computador da sala de aula
# passando de mão em mão —, então um painel destravado esquecido aberto entrega
# notas da turma, exclusão de alunos e troca de senha pra quem sentar depois.
MINUTOS_SESSAO_PROFESSOR = 30

if 'conteudos' not in st.session_state: st.session_state.conteudos = carregar_conteudos()
if 'config' not in st.session_state: st.session_state.config = carregar_config()
if 'dados_estatistica' not in st.session_state: st.session_state.dados_estatistica = carregar_dados_estatistica()
if 'aluno_ativo' not in st.session_state: st.session_state.aluno_ativo = ""
if 'conteudo_ativo' not in st.session_state: st.session_state.conteudo_ativo = ID_CONTEUDO_ESTATISTICA
# Guardamos o INSTANTE EM QUE A SESSÃO EXPIRA, não um booleano "está logado":
# com o booleano, ficar autenticado era um estado sem prazo nenhum, que só
# terminava se alguém lembrasse de clicar em "Sair do Painel". 0.0 = sem sessão.
if 'professor_auth_expira_em' not in st.session_state: st.session_state.professor_auth_expira_em = 0.0
if 'pagina' not in st.session_state: st.session_state.pagina = PAGINA_INICIO
if 'aba_materia' not in st.session_state: st.session_state.aba_materia = ABA_TEORIA
if 'aba_professor' not in st.session_state: st.session_state.aba_professor = ABA_PROFESSOR_VISAO
if 'novas_secoes_teoria' not in st.session_state: st.session_state.novas_secoes_teoria = []
if 'novas_missoes' not in st.session_state: st.session_state.novas_missoes = []


def sessao_professor_ativa():
    return time.time() < st.session_state.professor_auth_expira_em

def abrir_sessao_professor():
    """Também usada pra RENOVAR o prazo enquanto o professor está usando o
    painel — assim o tempo conta a partir do último uso, e a sessão não morre
    no meio de um cadastro longo de conteúdo."""
    st.session_state.professor_auth_expira_em = time.time() + MINUTOS_SESSAO_PROFESSOR * 60

def encerrar_sessao_professor():
    st.session_state.professor_auth_expira_em = 0.0

TAMANHO_MIN_APELIDO = 2
TAMANHO_MAX_APELIDO = 20


def apelido_invalido(apelido):
    """Retorna a mensagem de erro do apelido, ou "" se estiver válido.

    Regra: UMA palavra só, apenas letras e números. str.isalnum() já entrega
    exatamente isso e ainda aceita acento ("João" é alfanumérico em Python),
    o que importa em português — por isso não usamos regex aqui.

    O apelido é a chave primária do aluno no banco: é por ele que o progresso é
    encontrado no login seguinte. Espaço no meio faz o aluno digitar "Ana Paula"
    hoje e "AnaPaula" amanhã, virando dois perfis e perdendo o XP. O limite de
    caracteres também protege a coluna 'Login' do relatório em PDF, que tem
    38mm — acima disso o texto seria cortado com reticências."""
    if len(apelido) < TAMANHO_MIN_APELIDO:
        return f"Use pelo menos {TAMANHO_MIN_APELIDO} caracteres."
    if len(apelido) > TAMANHO_MAX_APELIDO:
        return f"Use no máximo {TAMANHO_MAX_APELIDO} caracteres."
    if not apelido.isalnum():
        return "Só letras e números, sem espaços."
    return ""


def entrar_como_aluno(nome):
    """Entrar como aluno ENCERRA a sessão do professor. Os dois papéis dividem a
    mesma sessão do navegador (é a mesma aba, no computador da sala), então sem
    isso o aluno herda o painel já destravado — notas da turma inteira, excluir
    aluno, apagar o banco e trocar a senha do professor — sem nunca ter digitado
    senha nenhuma. Também sai da página do professor, porque continuar nela
    depois de perder o acesso só mostraria a tela de senha do nada."""
    carregar_perfil_aluno(nome)
    encerrar_sessao_professor()
    if st.session_state.pagina == PAGINA_PROFESSOR:
        st.session_state.pagina = PAGINA_INICIO
    st.rerun()

def ir_para_materia(cid, aba=ABA_TEORIA):
    """Caminho ÚNICO para abrir uma matéria — usado pelo menu lateral e pelos
    cartões da página inicial e do hub de Estatística. Ter uma função só é o
    que impede a divergência de antes, quando cada ponto de entrada montava
    sua própria combinação de 'trocar matéria' + 'trocar de página' e cada um
    parava num lugar diferente."""
    st.session_state.pagina = PAGINA_MATERIA
    st.session_state.conteudo_ativo = cid
    st.session_state.aba_materia = aba
    st.rerun()

def ir_para_hub_estatistica():
    """Abre a vitrine de Estatística (PAGINA_ESTATISTICA_HUB), não uma
    matéria específica — por isso não usa ir_para_materia, que sempre define
    um conteudo_ativo."""
    st.session_state.pagina = PAGINA_ESTATISTICA_HUB
    st.rerun()


def perfil_atual():
    """Lê o perfil do aluno logado direto do banco (não fica em cache na
    sessão) — assim cada leitura já reflete o que foi salvo por último."""
    nome = st.session_state.aluno_ativo
    if not nome:
        return None
    conn = obter_conexao_db()
    try:
        row = conn.execute("SELECT xp_total, inicio_sessao FROM alunos WHERE nome = ?", (nome,)).fetchone()
        if row is None:
            agora = time.time()
            conn.execute("INSERT INTO alunos (nome, xp_total, inicio_sessao) VALUES (?, 0, ?)", (nome, agora))
            conn.commit()
            return {"xp_total": 0, "inicio_sessao": agora}
        return {"xp_total": row["xp_total"], "inicio_sessao": row["inicio_sessao"]}
    finally:
        conn.close()

def progresso_atual(conteudo_id=None):
    conteudo_id = conteudo_id or st.session_state.conteudo_ativo
    nome = st.session_state.aluno_ativo
    if not nome:
        return progresso_padrao()
    conn = obter_conexao_db()
    try:
        row = conn.execute(
            "SELECT missao_atual, erros, erros_missao_atual, historico, respostas FROM progresso WHERE aluno = ? AND conteudo_id = ?",
            (nome, conteudo_id),
        ).fetchone()
        if row is None:
            return progresso_padrao()
        respostas = json.loads(row["respostas"]) if row["respostas"] else {}
        # Recoloca as respostas salvas em st.session_state: é de lá que todo
        # "✅ Missão N Concluída! (Resposta: ...)" já espalhado pelo código
        # lê o valor (ver verificar_resposta) — sem essa "hidratação" aqui,
        # cada um desses 40+ pontos de exibição precisaria ser reescrito pra
        # ler de outro lugar. Só preenche o que ainda não está em memória
        # (não pisa numa resposta desta MESMA sessão, mais recente que a
        # gravada no banco no meio de uma missão em andamento).
        for idx_str, resp in respostas.items():
            chave = f"m_{conteudo_id}_{idx_str}"
            if chave not in st.session_state:
                st.session_state[chave] = resp
        return {
            "missao_atual": row["missao_atual"],
            "erros": row["erros"],
            "erros_missao_atual": row["erros_missao_atual"],
            "historico": json.loads(row["historico"]) if row["historico"] else [],
            "respostas": respostas,
        }
    finally:
        conn.close()

def salvar_perfil_e_progresso(nome, conteudo_id, perfil, prog):
    """Grava só a linha desse aluno (xp) e só a linha desse aluno+conteúdo
    (progresso) — nunca o banco inteiro. É isso que permite vários alunos
    salvando ao mesmo tempo sem um sobrescrever o outro."""
    conn = obter_conexao_db()
    try:
        conn.execute("UPDATE alunos SET xp_total = ? WHERE nome = ?", (perfil.get("xp_total", 0), nome))
        conn.execute(
            """INSERT INTO progresso (aluno, conteudo_id, missao_atual, erros, erros_missao_atual, historico, respostas)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(aluno, conteudo_id) DO UPDATE SET
                   missao_atual = excluded.missao_atual,
                   erros = excluded.erros,
                   erros_missao_atual = excluded.erros_missao_atual,
                   historico = excluded.historico,
                   respostas = excluded.respostas""",
            (
                nome, conteudo_id,
                prog.get("missao_atual", 1),
                prog.get("erros", 0),
                prog.get("erros_missao_atual", 0),
                json.dumps(prog.get("historico", []), ensure_ascii=False),
                json.dumps(prog.get("respostas", {}), ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

def carregar_perfil_aluno(nome):
    st.session_state.aluno_ativo = nome
    conn = obter_conexao_db()
    try:
        existe = conn.execute("SELECT 1 FROM alunos WHERE nome = ?", (nome,)).fetchone()
        if not existe:
            conn.execute("INSERT INTO alunos (nome, xp_total, inicio_sessao) VALUES (?, 0, ?)", (nome, time.time()))
            conn.commit()
    finally:
        conn.close()

def limpar_banco():
    conn = obter_conexao_db()
    try:
        conn.execute("DELETE FROM progresso")
        conn.execute("DELETE FROM tentativas_missao")
        conn.execute("DELETE FROM alunos")
        conn.commit()
    finally:
        conn.close()
    st.session_state.aluno_ativo = ""
    st.rerun()

def salvar_nomes_relatorio(mapa_nomes):
    """{nome_de_login: nome_no_relatorio}. Só grava a coluna de exibição —
    a chave 'nome' nunca é tocada, é o que garante que o aluno continue
    encontrando o progresso dele no próximo login."""
    conn = obter_conexao_db()
    try:
        for nome, nome_relatorio in mapa_nomes.items():
            conn.execute("UPDATE alunos SET nome_relatorio = ? WHERE nome = ?",
                         ((nome_relatorio or "").strip(), nome))
        conn.commit()
    finally:
        conn.close()

def excluir_alunos(nomes):
    conn = obter_conexao_db()
    try:
        for nome in nomes:
            conn.execute("DELETE FROM progresso WHERE aluno = ?", (nome,))
            conn.execute("DELETE FROM tentativas_missao WHERE aluno = ?", (nome,))
            conn.execute("DELETE FROM alunos WHERE nome = ?", (nome,))
        conn.commit()
    finally:
        conn.close()
    if st.session_state.aluno_ativo in nomes:
        st.session_state.aluno_ativo = ""
    st.rerun()

# As missões dos conteúdos NATIVOS (Estatística Descritiva e Tabela de
# Frequência) ficam no código (não em conteudos.json), então o mapeamento delas
# para a BNCC também precisa ficar aqui — um dicionário por conteúdo nativo,
# indexado pelo id dele.
#
# Estatística Descritiva: todas as 10 exercitam a MESMA habilidade —
# EM13MAT316, que trata de calcular e interpretar medidas de tendência central
# (média, moda, mediana) e de dispersão (amplitude, variância e desvio padrão).
#
# Tabela e Gráfico de Frequência: todas as FREQ_N_FAIXAS+3 exercitam
# EM13MAT408 — construir e interpretar tabelas e gráficos de frequência a
# partir de dados de uma amostra. (CUIDADO: não confundir com EM13MAT406, que
# é outra habilidade — "utilizar conceitos básicos de linguagem de
# programação". Erro real que já aconteceu aqui, corrigido em 2026-09-13
# depois de conferir o PDF oficial da BNCC do Ensino Médio.)
#
# Leitura Crítica de Gráficos: as 8 exercitam EM13MAT102 — analisar
# tabelas/gráficos/amostras divulgados na mídia, identificando quando a
# amostra ou a escala usada pode induzir a erro de interpretação.
#
# Comparando Diagramas: as 6 exercitam EM13MAT409 — interpretar e comparar
# conjuntos de dados por meio de diferentes diagramas (histograma, box-plot,
# ramos e folhas), reconhecendo o mais eficiente pra cada análise.
#
# Planejando uma Pesquisa: as 6 exercitam EM13MAT202 — planejar e executar
# pesquisa amostral, comunicando o resultado em relatório com gráficos e
# medidas de tendência central e dispersão. Adaptado: em vez de fazer o
# aluno coletar dado real (o app não tem como), a sequência é de DECISÃO
# (população x amostra, tamanho, o que vai no relatório), fechando com uma
# missão que aponta de volta pro conteúdo de Estatística Descritiva como o
# relatório de exemplo pronto.
#
# Relação entre Duas Variáveis: as 6 exercitam EM13MAT510 — investigar
# conjuntos de dados de duas variáveis numéricas, usando uma reta de
# tendência pra descrever e prever a relação entre elas.
#
# Só estas habilidades são definidas no código, de propósito: os demais
# conteúdos têm campo livre no cadastro, preenchido pelo professor consultando
# a BNCC. Não convém "chutar" códigos aqui, porque um código errado no
# relatório é pior que nenhum. Confira em http://basenacionalcomum.mec.gov.br/
# antes de usar no TCC.
BNCC_MISSOES_NATIVAS = {
    ID_CONTEUDO_ESTATISTICA: {i: "EM13MAT316" for i in range(1, 11)},
    ID_CONTEUDO_FREQUENCIA: {i: "EM13MAT408" for i in range(1, FREQ_N_FAIXAS + 4)},
    ID_CONTEUDO_LEITURA_GRAFICA: {i: "EM13MAT102" for i in range(1, 9)},
    ID_CONTEUDO_COMPARACAO: {i: "EM13MAT409" for i in range(1, 7)},
    ID_CONTEUDO_PESQUISA_AMOSTRAL: {i: "EM13MAT202" for i in range(1, 7)},
    ID_CONTEUDO_TENDENCIA: {i: "EM13MAT510" for i in range(1, 7)},
}


def obter_bncc_missao(conteudo_id, indice_missao):
    """Habilidade BNCC de uma missão (string vazia se não mapeada).
    indice_missao é 1-based, igual ao usado em progresso['missao_atual']."""
    if conteudo_id in BNCC_MISSOES_NATIVAS:
        return BNCC_MISSOES_NATIVAS[conteudo_id].get(indice_missao, "")
    missoes = st.session_state.conteudos.get(conteudo_id, {}).get("missoes", [])
    if 1 <= indice_missao <= len(missoes):
        return str(missoes[indice_missao - 1].get("bncc", "")).strip()
    return ""


ARQUIVO_HABILIDADES_BNCC = "habilidades_bncc.json"  # gerado por arquivos/gerar_habilidades_bncc.py (Ensino Médio)


@st.cache_data
def _ler_habilidades_bncc(data_do_arquivo):
    # O parâmetro só existe para o cache se renovar quando o arquivo mudar.
    try:
        with open(ARQUIVO_HABILIDADES_BNCC, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def carregar_habilidades_bncc():
    """{código: descrição oficial} da BNCC do Ensino Médio (e Computação). Dicionário
    vazio se o arquivo não existir — aí os campos de habilidade voltam a ser texto livre."""
    try:
        data = os.path.getmtime(ARQUIVO_HABILIDADES_BNCC)
    except OSError:
        data = 0
    return _ler_habilidades_bncc(data)


def descricao_curta_bncc(codigo, limite=85):
    """Começo da descrição oficial, cortado numa palavra inteira. Vazio se o
    código não está no banco (por exemplo, um código digitado à mão antes)."""
    texto = carregar_habilidades_bncc().get(str(codigo).strip(), "")
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def rotulo_habilidade_bncc(codigo):
    """'EM13MAT316 · Resolver e elaborar problemas…' (ou só o código, se não houver descrição)."""
    curta = descricao_curta_bncc(codigo)
    return f"{codigo} · {curta}" if curta else str(codigo)


def campo_habilidade_bncc(rotulo, valor_atual="", chave=None, ajuda=""):
    """Campo de habilidade BNCC: lista pesquisável (código + descrição curta) quando
    o banco existe; texto livre quando não. Devolve só o código ('' se vazio)."""
    habilidades = carregar_habilidades_bncc()
    valor_atual = str(valor_atual or "").strip()
    if not habilidades:
        return st.text_input(rotulo, value=valor_atual, placeholder="Ex.: EM13MAT316", key=chave, help=ajuda).strip()
    opcoes = sorted(habilidades)
    if valor_atual and valor_atual not in habilidades:
        opcoes.append(valor_atual)  # código antigo, digitado à mão: não some do cadastro
    indice = opcoes.index(valor_atual) if valor_atual else None
    escolhida = st.selectbox(
        rotulo, opcoes, index=indice, key=chave, help=ajuda,
        # Rótulo com a descrição INTEIRA: o Streamlit só pesquisa dentro do rótulo, e
        # a lista já corta a linha sozinha. Assim dá para achar "mediana" mesmo que a
        # palavra esteja no fim da descrição.
        format_func=lambda c: f"{c} · {habilidades[c]}" if c in habilidades else c,
        placeholder="Digite o código ou uma palavra da habilidade",
    )
    return (escolhida or "").strip()


def habilidades_bncc_do_conteudo(cid, c):
    """Códigos BNCC (sem repetição, ordenados) usados pelas missões de um
    conteúdo — nativo ou cadastrado pelo professor. Lista vazia se nenhuma
    missão foi mapeada. Usado só no Painel do Professor (Gerenciar
    Conteúdos): é informação de planejamento curricular, sem utilidade pro
    aluno durante o jogo — decisão do Wenes (2026-09-14)."""
    if cid in BNCC_MISSOES_NATIVAS:
        return sorted(set(BNCC_MISSOES_NATIVAS[cid].values()))
    codigos = {str(m.get("bncc", "")).strip() for m in c.get("missoes", [])}
    codigos.discard("")
    return sorted(codigos)


def desempenho_por_bncc(alunos, conteudo_id=None):
    """Agrega o progresso da turma por habilidade da BNCC (só de um conteúdo,
    se conteudo_id for dado: é o caso do PDF exportado de uma aba).

    Retorna [{Habilidade, Missões, Conclusões, Possíveis, % Concluído}], onde
    'Conclusões' conta cada par (aluno, missão concluída) das missões marcadas
    com aquela habilidade, e 'Possíveis' é o total se todos concluíssem tudo.

    Nota sobre o que este número significa: o banco guarda o ponto onde o aluno
    parou na trilha (missao_atual) e o total de erros por conteúdo — não o acerto
    de cada missão isolada. Então 'concluída' aqui é 'o aluno passou por ela',
    que na mecânica da trilha só acontece após acertar. Não confundir com
    'acertou de primeira'."""
    acumulado = {}
    for cid in st.session_state.conteudos:
        if conteudo_id and cid != conteudo_id:
            continue
        total_missoes = obter_total_missoes(cid)
        for idx in range(1, total_missoes + 1):
            habilidade = obter_bncc_missao(cid, idx)
            if not habilidade:
                continue
            registro = acumulado.setdefault(habilidade, {"missoes": 0, "feitas": 0, "possiveis": 0})
            registro["missoes"] += 1
            for perfil in alunos.values():
                prog = perfil.get("progresso", {}).get(cid, {"missao_atual": 1})
                concluidas = max(prog.get("missao_atual", 1) - 1, 0)
                registro["possiveis"] += 1
                if idx <= concluidas:
                    registro["feitas"] += 1

    linhas = []
    for habilidade in sorted(acumulado):
        r = acumulado[habilidade]
        pct = (r["feitas"] / r["possiveis"] * 100) if r["possiveis"] else 0
        linhas.append({
            "Habilidade": habilidade,
            "Missões": r["missoes"],
            "Conclusões": r["feitas"],
            "Possíveis": r["possiveis"],
            "% Concluído": round(pct),
        })
    return linhas


def registrar_tentativa_missao(aluno, conteudo_id, missao, acertou):
    """Grava uma tentativa de resposta (acerto ou erro). Falha em silêncio: o
    registro serve só ao relatório do professor, e um erro de banco aqui não
    pode travar o aluno no meio da missão."""
    if not aluno:
        return
    try:
        conn = obter_conexao_db()
        try:
            conn.execute(
                "INSERT INTO tentativas_missao (aluno, conteudo_id, missao, acertou, momento) VALUES (?, ?, ?, ?, ?)",
                (aluno, conteudo_id, int(missao), 1 if acertou else 0, dia_de_hoje_brasilia()),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        pass


def acerto_por_aluno_e_habilidade(conteudo_id=None):
    """Acerto de cada aluno em cada habilidade da BNCC, a partir das tentativas
    (só as de um conteúdo, se conteudo_id for dado).

    Retorna (acertos, desde): acertos é {(aluno, habilidade): [acertos, tentativas]}
    e desde é o dia (AAAA-MM-DD) da primeira tentativa gravada, ou '' se não há
    nenhuma. Acerto = respostas certas ÷ todas as tentativas (cada erro conta como
    uma tentativa), só das missões que têm habilidade mapeada."""
    acertos = {}
    desde = ""
    try:
        conn = obter_conexao_db()
        try:
            linhas = conn.execute(
                "SELECT aluno, conteudo_id, missao, acertou, momento FROM tentativas_missao"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return acertos, desde
    for linha in linhas:
        if conteudo_id and linha["conteudo_id"] != conteudo_id:
            continue
        if not desde or linha["momento"] < desde:
            desde = linha["momento"]
        habilidade = obter_bncc_missao(linha["conteudo_id"], linha["missao"])
        if not habilidade:
            continue
        par = acertos.setdefault((linha["aluno"], habilidade), [0, 0])
        par[0] += linha["acertou"]
        par[1] += 1
    return acertos, desde


# Total de missões de cada conteúdo NATIVO — não dá pra contar
# len(conteudo["missoes"]) como se faz com os conteúdos do professor, porque
# aqui não existe essa lista: as missões são funções Python (ver bloco 7). Um
# dicionário por conteúdo nativo, em vez de supor "todo tipo=='estatico' tem
# 10 missões" (o que quebraria em silêncio se um novo conteúdo nativo tivesse
# uma quantidade diferente — foi exatamente o que aconteceu ao criar o
# conteúdo de Frequência).
TOTAL_MISSOES_NATIVAS = {
    ID_CONTEUDO_ESTATISTICA: 10,
    ID_CONTEUDO_FREQUENCIA: FREQ_N_FAIXAS + 3,  # 1 por faixa + total + freq. relativa + gráfico
    ID_CONTEUDO_LEITURA_GRAFICA: 8,  # 4 missões no Caso 1 (escala) + 4 no Caso 2 (amostra)
    ID_CONTEUDO_COMPARACAO: 6,
    ID_CONTEUDO_PESQUISA_AMOSTRAL: 6,
    ID_CONTEUDO_TENDENCIA: 6,
}

# XP máximo de CADA conteúdo NATIVO, acertando tudo de primeira — não tem
# como calcular isso sozinho porque os pontos de cada missão estão escritos
# direto como argumento em cada chamada de verificar_resposta(...), não numa
# tabela; se o XP de alguma missão nativa mudar, os números aqui precisam
# ser somados à mão de novo (2026-09-14):
#   Estatística Descritiva: 10+20+30+10+10+20+40+40+60+80 = 320
#   Frequência:              20*5 + 20 + 30 + 20           = 170
#   Leitura Crítica:         20+20+20+30 + 20+20+20+30     = 180
#   Comparando Diagramas:    20+30+30+20+20+30             = 150
#   Planejando uma Pesquisa: 20+20+20+20+20+30             = 130
#   Relação entre Duas Variáveis: 20+20+20+30+30+30        = 150
XP_MAXIMO_POR_CONTEUDO_NATIVO = {
    ID_CONTEUDO_ESTATISTICA: 320,
    ID_CONTEUDO_FREQUENCIA: 170,
    ID_CONTEUDO_LEITURA_GRAFICA: 180,
    ID_CONTEUDO_COMPARACAO: 150,
    ID_CONTEUDO_PESQUISA_AMOSTRAL: 130,
    ID_CONTEUDO_TENDENCIA: 150,
}
XP_MAXIMO_CONTEUDO_NATIVO = sum(XP_MAXIMO_POR_CONTEUDO_NATIVO.values())  # 1100


def xp_maximo_de_conteudo(cid, c):
    """XP máximo de UM conteúdo específico, acertando tudo de primeira —
    nativo (tabela acima) ou cadastrado pelo professor (soma o "Pontos (XP)"
    de cada missão dele). Usado tanto pro badge "Total X XP" em cada card
    (Painel do Professor > Gerenciar Conteúdos) quanto pro seletor de
    "Meta de XP" em Configurações — pedido do Wenes (2026-09-17) e sugestão
    parecida do orientador (ver "Conversar com orientador 02.txt": escolher
    a disciplina, mostrar o XP dela, definir a meta como % disso)."""
    if cid in XP_MAXIMO_POR_CONTEUDO_NATIVO:
        return XP_MAXIMO_POR_CONTEUDO_NATIVO[cid]
    return sum(m.get("pontos", 10) for m in c.get("missoes", []))


def xp_maximo_catalogo_atual():
    """(nativo, cadastrado, total) — XP máximo do catálogo INTEIRO agora,
    separado por grupo. Recalculado toda vez que é chamado, então sempre
    reflete o catálogo ATUAL — cresce sozinho quando o professor cadastra
    conteúdo novo. Mostrado em Configurações como referência pra decidir a
    Meta de XP (pedido do Wenes, 2026-09-14): sem esse número, não tem como
    saber se 500 XP é "quase tudo" ou "quase nada" do que existe pra jogar.
    Separado em dois números (não só um total misturado) porque o Wenes
    achou confuso um valor só somando as duas coisas (2026-09-17)."""
    nativo = XP_MAXIMO_CONTEUDO_NATIVO
    cadastrado = sum(
        xp_maximo_de_conteudo(cid, c)
        for cid, c in st.session_state.conteudos.items()
        if c["tipo"] != "estatico"
    )
    return nativo, cadastrado, nativo + cadastrado



def obter_total_missoes(conteudo_id):
    if conteudo_id in TOTAL_MISSOES_NATIVAS:
        return TOTAL_MISSOES_NATIVAS[conteudo_id]
    conteudo = st.session_state.conteudos.get(conteudo_id, {})
    return len(conteudo.get("missoes", []))

def ranking_turma(limite=10):
    """[(apelido, xp)] dos alunos com mais XP, em ordem decrescente.

    Consulta enxuta de propósito: só nome e xp_total, ordenado e limitado pelo
    próprio SQLite. O placar recarrega sozinho a cada poucos segundos no
    navegador de cada aluno (ver render_placar_turma), então ele roda muito mais
    vezes que o resto do app — não pode carregar o progresso da turma inteira
    como carregar_todos_alunos_do_banco() faz."""
    conn = obter_conexao_db()
    try:
        return [
            (linha["nome"], linha["xp_total"])
            for linha in conn.execute(
                "SELECT nome, xp_total FROM alunos ORDER BY xp_total DESC, nome ASC LIMIT ?",
                (limite,),
            )
        ]
    finally:
        conn.close()


def progresso_resumo_aluno():
    """{conteudo_id: missoes_concluidas} do aluno logado, em UMA consulta.
    O menu lateral mostra o progresso de todas as matérias ao mesmo tempo;
    chamar progresso_atual() uma vez por matéria abriria (e fecharia) uma
    conexão pra cada uma, a cada rerun — e a Trilha de Missões faz rerun a
    cada resposta respondida."""
    nome = st.session_state.aluno_ativo
    if not nome:
        return {}
    conn = obter_conexao_db()
    try:
        linhas = conn.execute(
            "SELECT conteudo_id, missao_atual FROM progresso WHERE aluno = ?", (nome,)
        ).fetchall()
    finally:
        conn.close()
    # missao_atual aponta pra PRÓXIMA missão a responder (começa em 1), então o
    # que já foi concluído é sempre missao_atual - 1.
    return {linha["conteudo_id"]: max(linha["missao_atual"] - 1, 0) for linha in linhas}


# ==========================================
# 3. ESTÉTICA CSS
# ==========================================
st.markdown("""
<style>
    /* Limita a largura do conteúdo principal e centraliza (estilo ChatGPT/X.com)
       em vez de esticar de ponta a ponta em monitores grandes. Não afeta a
       barra lateral, que tem sua própria largura fixa. O Streamlit já aplica
       um padding interno grande por padrão; reduzimos ele aqui pra sobrar
       mais espaço de conteúdo dentro do limite. */
    .stMainBlockContainer {
        max-width: 870px;
        padding-left: 2rem;
        padding-right: 2rem;
        margin-left: auto;
        margin-right: auto;
        /* O Streamlit reserva 96px (6rem) de padding-top por padrão, pra
           sobrar espaço embaixo da barra flutuante (Deploy/menu) — mas
           aqui essa barra é baixa e o conteúdo já tem título próprio logo
           abaixo, então sobrava um vão vazio grande no topo de toda
           página, banner ou não (relatado pelo Wenes, 2026-09-17,
           print mostrando o espaço em ambos os casos). Medido: era 96px,
           cortado pra 24px, depois pra 0 — aí ficou colado demais ("vixe,
           agora ficou colado"), então 38px (~1cm a 96dpi) de volta, pra
           dar uma folga mínima. Mais 19px (~5mm) depois que a barra de
           ferramentas do Streamlit voltou a mostrar o ícone de abrir/
           fechar a barra lateral, pra não ficar colado nele — depois
           ajustado à mão pelo Wenes direto no arquivo pra 60px ("ficou
           perfeito", 2026-09-17). */
        padding-top: 60px;
    }

    /* Só o botão "Deploy" (chrome do Streamlit Cloud) — NÃO a barra inteira.
       O "⋮" fica visível (2026-09-25, pedido do Wenes) pra trocar o tema
       claro/escuro. Versão
       anterior escondia a barra toda (`[data-testid="stHeader"]
       {display:none}`), e isso quebrou o botão de expandir a barra
       lateral: quando o Wenes encolhia a barra lateral e recarregava a
       página, o botão pra abrir de novo (`stExpandSidebarButton`) mora
       DENTRO dessa mesma barra escondida, então ficava sem jeito nenhum
       de reabrir (bug relatado 2026-09-17). Escondendo só os dois botões
       específicos, o resto da barra (inclusive esse controle) continua
       funcionando normalmente. */
    [data-testid="stAppDeployButton"] {
        display: none;
    }

    /* Cada bloco invisível (os 5 components.html(..., height=0) que injetam
       JS — bloqueio de espaço no apelido, aviso de saída, clique na logo etc.
       — e o próprio <style> deste CSS) ainda ocupa uma "vaga" na lista vertical
       da página, com o gap de 16px entre itens contando mesmo pra quem tem
       altura zero. No topo da página isso somava 96px de vão vazio — medido
       ao vivo, era o resto do espaço que sobrava depois do padding-top e da
       barra Deploy já cortados (Wenes, 2026-09-17: "ainda tá uns 2cm"). Achado
       inspecionando o DOM: 6 stElementContainer de altura 0 antes do primeiro
       botão. display:none tira da lista de vez, sem gap nenhum — e um <style>
       escondido continua valendo normalmente, isso é comportamento padrão do
       HTML/CSS, não depende do elemento estar visível. */
    .stElementContainer:has([data-testid="stIFrame"]),
    .stElementContainer:has(style) {
        display: none;
    }

    .metric-card { background-color: #ffffff; border-left: 5px solid #1e40af; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 15px; }
    .metric-title { color: #64748b; font-size: 14px; font-weight: 700; text-transform: uppercase; }
    .metric-value { color: #1e3a8a; font-size: 28px; font-weight: 800; margin-top: 5px; }
    .gamification-box { background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: white; padding: 15px 20px; border-radius: 10px; font-size: 16px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3); }
    /* .gamification-box acima nunca chegou a ser usada em lugar nenhum do app —
       sobra de uma versão antiga. Deixada como está (não é deste ajuste),
       mas fica o registro pra quem for limpar código depois. */

    /* Selo de XP acima da Trilha de Missões (2026-09-05) — pedido do usuário
       pra dar mais destaque ao XP acumulado, além do texto pequeno que já
       existe na barra lateral. Gradiente opaco + texto branco (mesma técnica
       do .home-banner), não rgba() semi-transparente: aqui o objetivo é
       "saltar aos olhos" como um emblema de jogo, não se misturar ao tema. */
    .xp-destaque-missoes {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: #ffffff;
        padding: 10px 24px;
        border-radius: 999px;
        box-shadow: 0 4px 10px rgba(59, 130, 246, 0.35);
        margin-bottom: 18px;
    }
    .xp-destaque-missoes .icone { font-size: 22px; }
    .xp-destaque-missoes .valor { font-size: 19px; font-weight: 700; letter-spacing: 0.01em; }

    /* Banner da página inicial */
    .home-banner {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 60%, #60a5fa 100%);
        color: white;
        padding: 40px 35px;
        border-radius: 16px;
        margin-bottom: 30px;
        box-shadow: 0 10px 25px -5px rgba(30, 64, 175, 0.4);
    }
    .home-banner-logo { font-size: 48px; margin-bottom: 8px; }
    .home-banner-logo-img { width: 76px; height: 76px; object-fit: cover; border-radius: 16px; margin-bottom: 10px; background-color: #ffffff; padding: 4px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); }
    .home-banner-titulo { font-size: 32px; font-weight: 800; margin: 0; }
    .home-banner-subtitulo { font-size: 16px; opacity: 0.92; margin-top: 6px; max-width: 640px; }

    /* O tema claro/escuro do Streamlit pode ser trocado dentro do próprio
       app (menu ⋮ > Settings), sem relação com o tema do sistema — então
       "@media (prefers-color-scheme)" não pega essa troca de jeito nenhum
       (é por isso que a versão anterior falhou: fundo claro + texto branco
       herdado do tema escuro real = ilegível). A saída é não tentar
       detectar o tema: rgba() semi-transparente vira um "tingimento" sobre
       o que estiver por trás, então se adapta sozinho. Opacidade calibrada
       pra bater com os tons reais que o Streamlit usa (~#f0f2f6 no claro,
       ~#262730 no escuro — conferido ao vivo nos dois). Sem "color" no
       texto, ele herda a cor certa do tema automaticamente. */
    .home-step-card {
        background-color: rgba(148, 163, 184, 0.16); border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 12px;
        padding: 18px; height: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        margin-bottom: 16px;
    }
    /* Placar da turma. Mesma técnica de cor dos cartões da home: rgba() por
       cima do fundo, sem "color" fixo no texto, pra funcionar no tema claro e
       no escuro sem tentar detectar qual está ativo. */
    .placar-caixa {
        border: 1px solid rgba(148, 163, 184, 0.4);
        border-radius: 12px;
        overflow: hidden;
    }
    .placar-linha {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.22);
    }
    .placar-linha:last-child { border-bottom: none; }
    .placar-linha.eu {
        background-color: rgba(59, 130, 246, 0.14);
        font-weight: 700;
    }
    .placar-pos {
        min-width: 34px;
        font-size: 17px;
        text-align: center;
        opacity: 0.85;
    }
    .placar-nome { flex: 1; font-size: 16px; }
    .placar-xp {
        font-variant-numeric: tabular-nums;  /* números alinhados entre as linhas */
        font-weight: 700;
        color: #16a34a;
    }

    .home-step-numero { color: #3b82f6; font-size: 13px; font-weight: 800; text-transform: uppercase; }
    .home-step-titulo { font-size: 17px; font-weight: 700; margin: 4px 0 6px 0; }
    .home-step-texto { opacity: 0.75; font-size: 14px; }

    /* Cartões com borda (st.container(border=True)) dentro de colunas lado a
       lado: por padrão cada um só cresce até onde o próprio texto termina,
       ficando com alturas diferentes. A coluna em si já é esticada pelo
       Streamlit pra acompanhar a mais alta do grupo, mas isso é feito via
       flexbox (não uma altura fixa), então "height: 100%" sozinho não
       resolve — precisa de flex-grow pra herdar esse espaço extra. */
    div[data-testid="stColumn"] div[data-testid="stLayoutWrapper"] {
        flex-grow: 1;
    }
    div[data-testid="stColumn"] div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] {
        height: 100%;
    }

    /* Cores suaves dos cartões de "Conteúdos disponíveis" (ver PALETA_CORES_CARTAO
       e o key="cartao_..._cor_X" passado a st.container). Usa rgba() com opacidade
       baixa em vez de cor sólida, pra funcionar bem tanto no tema claro quanto no
       escuro — a cor vira um "tingimento" leve por cima do fundo de cada tema,
       em vez de uma cor fixa que combina com um só dos dois. */
    [class*="_cor_azul"]    { background-color: rgba(59, 130, 246, 0.12) !important; border-color: rgba(59, 130, 246, 0.4) !important; }
    [class*="_cor_roxo"]    { background-color: rgba(168, 85, 247, 0.12) !important; border-color: rgba(168, 85, 247, 0.4) !important; }
    [class*="_cor_rosa"]    { background-color: rgba(236, 72, 153, 0.12) !important; border-color: rgba(236, 72, 153, 0.4) !important; }
    [class*="_cor_amarelo"] { background-color: rgba(245, 158, 11, 0.14) !important; border-color: rgba(245, 158, 11, 0.45) !important; }
    [class*="_cor_verde"]   { background-color: rgba(16, 185, 129, 0.12) !important; border-color: rgba(16, 185, 129, 0.4) !important; }
    [class*="_cor_ciano"]   { background-color: rgba(6, 182, 212, 0.12) !important; border-color: rgba(6, 182, 212, 0.4) !important; }

    /* Título dos painéis expansíveis (st.expander) um pouco maior — vale tanto
       pro conteúdo estático (Estatística) quanto pros conteúdos dinâmicos,
       já que os dois usam o mesmo componente e ficam consistentes entre si. */
    div[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p {
        font-size: 20px !important;
        font-weight: 600 !important;
    }

    /* Título principal de cada página (st.title = h1) vinha no tamanho padrão do
       Streamlit (44px), bem maior que os títulos de seção da própria home
       ("Como funciona", "Conteúdos disponíveis", 28px/600 via h3) — igualado
       aqui pra manter a mesma hierarquia visual em todas as páginas (Painel do
       Professor, Trilha de Missões, Conteúdo). Line-height é relativo (em), então
       acompanha o font-size automaticamente. */
    h1 {
        font-size: 28px !important;
        font-weight: 600 !important;
    }

    /* Título dentro dos cartões de "Conteúdos disponíveis" (h4, ver PALETA_CORES_CARTAO)
       vinha em 24px, maior que o título dos cartões "Como funciona" (17px/700,
       .home-step-titulo) — reduzido pra bater com esse tamanho. Escopado só aos
       cartões de conteúdo via [class*="_cor_"] (mesma classe usada pra cor de fundo),
       pra não afetar outros h4 do app. */
    [class*="_cor_"] h4 {
        font-size: 17px !important;
        font-weight: 700 !important;
    }

    /* Cartões "Como funciona" (Passo 1/2/3) usam st.markdown com HTML cru
       (.home-step-card), não st.container(border=True) — por isso o fix de altura
       igual acima (stLayoutWrapper) não se aplica a eles: o texto do Passo 3 é mais
       longo, então só aquele cartão cresce. stVerticalBlock/stColumn já esticam pra
       acompanhar o mais alto do grupo (comportamento nativo do Streamlit), mas o
       stElementContainer por dentro não geda esse espaço extra sem flex-grow.
       :has() escopa a regra só aos cartões com .home-step-card, sem mexer em outras
       colunas do app. */
    div[data-testid="stElementContainer"]:has(.home-step-card) {
        flex-grow: 1;
        display: flex;
    }
    div[data-testid="stElementContainer"]:has(.home-step-card) [data-testid="stMarkdown"],
    div[data-testid="stElementContainer"]:has(.home-step-card) [data-testid="stMarkdown"] > div,
    div[data-testid="stElementContainer"]:has(.home-step-card) [data-testid="stMarkdownContainer"] {
        height: 100%;
    }

    /* Cada conteúdo cadastrado (Painel do Professor > Gerenciar Conteúdos) é
       um st.container(border=True) — cartão de verdade, com borda e cantos
       arredondados, em vez da lista em colunas com uma linha horizontal
       entre cada item. Pedido do Wenes (2026-09-14): "mais elegante e
       estilizado", mas com estilo PRÓPRIO do painel do professor — não é
       pra copiar o card do aluno na Início, que mostra outra informação. */
    div[class*="st-key-card_conteudo_"] {
        margin-bottom: 12px;
    }

    /* Badges (pílulas) dentro do cartão: resumo do tipo/quantidade de
       missões e da habilidade BNCC mapeada, visível sem precisar abrir
       "Editar". */
    .badge-conteudo {
        display: inline-block;
        padding: 5px 14px;
        border-radius: 999px;
        font-size: 14px;
        font-weight: 700;
        margin: 6px 6px 0 0;
    }
    .badge-conteudo-tipo {
        background: #eef2ff;
        color: #4338ca;
    }
    .badge-conteudo-bncc {
        background: #ecfdf5;
        color: #047857;
    }

    /* Cards suaves dos 3 totais de XP em Configurações (Matéria Padrão /
       Matérias Cadastradas / Total do catálogo) — antes usava st.metric(),
       que só desenha número preto puro sem nenhuma cor de fundo; o Wenes
       achou "feio" pro Painel do Professor (2026-09-17), queria algo mais
       suave. Reaproveita as MESMAS cores dos badges de card (indigo dos
       badges de tipo, verde do BNCC) + um terceiro tom neutro pro total,
       que é soma dos outros dois, não uma categoria própria. */
    .resumo-xp-card {
        border-radius: 12px;
        padding: 14px 16px;
        text-align: center;
    }
    .resumo-xp-card .rotulo {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        opacity: 0.75;
        margin-bottom: 4px;
    }
    .resumo-xp-card .valor {
        font-size: 21px;
        font-weight: 700;
    }
    /* Em tela estreita (celular), st.columns empilha os 3 cards um embaixo
       do outro — e aí eles ficavam colados (relatado pelo Wenes, 2026-09-22).
       Causa: o stMarkdownContainer do Streamlit já vem com margin-bottom:
       -16px por padrão (serve pra cancelar um espaçamento dele mesmo quando
       tem mais coisa depois dentro do mesmo bloco). Em coluna lado a lado
       isso não se nota — o espaço entre colunas é horizontal (column-gap),
       não vertical. Empilhado, essa margem negativa passa a comer o
       row-gap vertical entre as colunas, cancelando os 16px de respiro.
       Zerar a margem só nas colunas com .resumo-xp-card devolve o respiro
       sem mexer no espaçamento de mais nada no app. */
    div[data-testid="stColumn"]:has(.resumo-xp-card) div[data-testid="stMarkdownContainer"] {
        margin-bottom: 0 !important;
    }
    .resumo-xp-nativo { background: #ecfdf5; }
    .resumo-xp-nativo .rotulo, .resumo-xp-nativo .valor { color: #047857; }
    .resumo-xp-cadastrado { background: #f0f9ff; }
    .resumo-xp-cadastrado .rotulo, .resumo-xp-cadastrado .valor { color: #0284c7; }
    .resumo-xp-total { background: #f1f5f9; }
    .resumo-xp-total .rotulo, .resumo-xp-total .valor { color: #334155; }

    /* Pop-up de "Salvo com sucesso" (ver renderizar_flash_pendente): fixo no
       canto superior direito, por cima de tudo, pra não precisar rolar a
       tela pra ver — bug relatado pelo Wenes (2026-09-17), editou um
       conteúdo longo, salvou, e a mensagem apareceu lá em cima, fora da
       tela. st.toast() faria isso nativamente (mesma posição, canto
       superior direito), mas parou de funcionar neste ambiente. Pequeno de
       propósito ("espero que não seja grandão", Wenes 2026-09-17): não é um
       modal, não bloqueia clique em nada por trás. Some sozinho em 3s via
       animação CSS (Wenes, 2026-09-17: "rápido, um dois três segundos, não
       pode ficar lá a vida toda") — st.markdown não executa <script>, então
       não dá pra usar um timer JS; keyframes resolve sem precisar de JS. */
    @keyframes flash-toast-sumir {
        0%, 80% { opacity: 1; }
        100% { opacity: 0; }
    }
    .flash-toast {
        position: fixed;
        top: 70px;
        right: 20px;
        z-index: 999999;
        max-width: 300px;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #047857;
        font-size: 14px;
        font-weight: 600;
        padding: 12px 16px;
        border-radius: 10px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
        animation: flash-toast-sumir 3s ease forwards;
        pointer-events: none;
    }

    /* Botões "Editar"/"Excluir" de cada conteúdo cadastrado: por padrão as duas
       colunas do st.columns(2) dividem o espaço em duas metades iguais, então
       sobra um vão grande entre os botões (cada um bem mais estreito que sua
       metade da coluna) e o par fica "flutuando" à esquerda do espaço
       reservado. Aqui as colunas encolhem pro tamanho do próprio botão
       (flex: 0 0 auto), o vão entre elas fica pequeno, e o par todo é
       empurrado pra direita — só dentro do key deste container. */
    div[class*="st-key-acoes_conteudo_"] div[data-testid="stHorizontalBlock"] {
        gap: 8px !important;
        justify-content: flex-end;
    }
    div[class*="st-key-acoes_conteudo_"] div[data-testid="stColumn"] {
        width: auto !important;
        flex: 0 0 auto !important;
    }
    /* Em tela estreita (celular), o Streamlit faz duas coisas ao mesmo tempo
       que juntas quebravam essa fileira de botões (confirmado testando ao
       vivo no celular, 2026-09-14): empilha QUALQUER st.columns() na
       vertical, E força min-width: calc(100% - 24px) em cada coluna —
       quase a largura inteira do card, pensado pra layout empilhado. A
       primeira tentativa de correção só forçou a linha a ficar horizontal
       (flex-wrap: nowrap), mas cada coluna continuou "querendo" quase 100%
       de largura por causa do min-width — o resultado foi as 4 colunas se
       empurrando pra fora do card, e só a última ("Excluir") sobrava
       visível. A correção de verdade precisa zerar esse min-width também,
       senão width:auto não tem efeito nenhum (min-width vence no flexbox). */
    @media (max-width: 640px) {
        div[class*="st-key-acoes_conteudo_"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
        }
        div[class*="st-key-acoes_conteudo_"] div[data-testid="stColumn"] {
            width: auto !important;
            min-width: 0 !important;
        }
    }

    /* Botão "Sair" do Painel do Professor: empurra pra borda direita da
       coluna sem esticar o botão. Duas pegadinhas encontradas medindo ao
       vivo (2026-09-14), não adivinhando:
       1) O container do Streamlit por baixo dos panos já é flex-direction:
          COLUNA — então justify-content controla o eixo VERTICAL, não o
          horizontal (por isso não tinha efeito nenhum). Quem alinha no eixo
          horizontal, numa coluna, é align-items.
       2) O filho direto do container vem com width:100% do próprio
          Streamlit — um filho largo assim não sobra espaço nenhum pra
          alinhar, então a largura dele também precisa ser travada pro
          tamanho do próprio conteúdo. */
    div[class*="st-key-acao_sair_professor"] {
        display: flex;
        align-items: flex-end;
    }
    div[class*="st-key-acao_sair_professor"] > div {
        width: fit-content !important;
    }

    /* Sobe o conteúdo inteiro da barra lateral (Início + tudo abaixo) uns 5mm
       (~19px) pra cima — pedido do Wenes (2026-09-13). O espaço de origem não
       é nosso: é margin-bottom:16px do próprio cabeçalho do Streamlit (ícone
       de recolher a barra), medido ao vivo via getBoundingClientRect(); não
       dá pra mexer nesse cabeçalho sem arriscar cortar o ícone, então o ajuste
       é uma margem negativa no bloco de conteúdo logo abaixo dele. */
    div[data-testid="stSidebarUserContent"] {
        margin-top: -19px;
    }

    /* Menu lateral estilo app (Gmail/ChatGPT): botões colados, alinhados à esquerda,
       com destaque visual para o item ativo e hover suave no restante. */
    div[data-testid="stSidebar"] button {
        margin-bottom: 4px;
        text-align: left;
        justify-content: flex-start;
        border-radius: 8px;
        transition: background-color 0.15s ease;
    }
    div[data-testid="stSidebar"] button p {
        text-align: left;
    }
    div[data-testid="stSidebar"] button[kind="secondary"]:hover {
        background-color: #eef2ff;
        border-color: #c7d2fe;
    }
    div[data-testid="stSidebar"] button[kind="primary"] {
        box-shadow: none;
    }

    /* A cor principal do app é azul (.streamlit/config.toml), mas os botões
       de confirmar exclusão ("Sim, excluir", "Sim, apagar tudo") continuam
       vermelhos: ali a cor avisa do perigo. */
    div[class*="st-key-confirmar_"] button[kind="primary"] {
        background-color: #dc2626;
        border-color: #dc2626;
    }
    div[class*="st-key-confirmar_"] button[kind="primary"]:hover {
        background-color: #b91c1c;
        border-color: #b91c1c;
    }

    /* Cartões dos conteúdos (Gerenciar Conteúdos): fundo cinza suave, pra separar um
       do outro. Transparência, pra valer no tema claro e no escuro. */
    div[class*="st-key-card_conteudo_"] {
        background-color: rgba(128, 128, 128, 0.06);
    }

    /* Abas do Detalhamento por Conteúdo: formato de aba de navegador. A aba
       ativa leva o azul do tema (traço no topo e fundo azulado); as outras ficam
       cinza discretas. Cores com transparência, pra valer no tema claro e no escuro. */
    div[role="tablist"] {
        gap: 4px;
        border-bottom: 1px solid rgba(128, 128, 128, 0.35);
    }
    div[role="tablist"] .react-aria-SelectionIndicator {
        display: none;
    }
    div[data-testid="stTab"] {
        background-color: rgba(128, 128, 128, 0.10);
        border: 1px solid rgba(128, 128, 128, 0.30);
        border-bottom: none;
        border-radius: 10px 10px 0 0;
        padding: 8px 16px;
        margin-bottom: 0;
    }
    div[data-testid="stTab"]:hover {
        background-color: rgba(31, 78, 154, 0.10);
    }
    div[data-testid="stTab"][aria-selected="true"] {
        background-color: rgba(31, 78, 154, 0.14);
        border-color: rgba(31, 78, 154, 0.55);
        border-top: 3px solid #1f4e9a;
        font-weight: 600;
    }

    /* Barrinha na borda esquerda dos itens do menu — diferencia "Matéria
       Padrão" (roxo/azul) de "Matérias Cadastradas" (verde) mesmo em
       repouso, sem pintar o botão inteiro (encostaria na cor do item
       ativo e viraria parque de diversão). Primeira versão era cinza neutro,
       mas ficou imperceptível demais — trocada por cor de verdade a pedido
       do Wenes (2026-09-14), mantendo elegante por ser só um traço fino, não
       um preenchimento. Cores emprestadas dos badges do Painel do Professor
       (.badge-conteudo-tipo / .badge-conteudo-bncc), pra usar a mesma
       linguagem visual em vez de inventar uma terceira paleta. Some quando o
       botão está ativo (kind="primary", já azul): a barrinha só faz
       sentido como pista discreta no estado normal. */
    div[class*="st-key-nav_hub_estatistica"] button[kind="secondary"] {
        border-left: 3px solid #6366f1;
    }
    div[class*="st-key-nav_conteudo_"] button[kind="secondary"] {
        border-left: 3px solid #10b981;
    }

    /* Bloco de identidade do aluno no topo da barra lateral: as duas versões
       (deslogado = campo de nome + "Acessar"; logado = nome + XP + "Sair")
       têm alturas naturais diferentes, e como o Streamlit desenha de cima pra
       baixo, essa diferença empurrava TODO o menu de navegação alguns pixels
       pra baixo ao logar. A altura mínima reserva o espaço da versão mais
       alta (a deslogada), então os itens do menu ficam sempre na mesma
       coordenada — dá pra clicar "Início" no mesmo lugar antes e depois de
       entrar. Valor conferido no DOM real das duas versões, não estimado. */
    div[class*="st-key-sidebar_identidade"] {
        min-height: 148px;
        /* O conteúdo logado (nome + XP + Sair) é mais baixo que o deslogado
           (campo + dica + Acessar), que é quem define os 148px. Sem isso,
           a sobra de altura ficava toda embaixo, abrindo um vão grande entre
           o botão "Sair" e o divisor — display:flex + justify-content:center
           reparte essa sobra em cima e embaixo, sem mudar a altura total
           (o que continua garantindo que o menu abaixo não se mexa). */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    /* Linha de dica/erro do apelido. Existe sempre (com a dica ou com o erro),
       nunca aparece e some — senão o bloco de identidade mudaria de altura e
       empurraria o menu, que é justamente o que o min-height acima evita. */
    .apelido-aviso {
        font-size: 12px;
        opacity: 0.65;
        margin: -8px 0 6px 2px;
        min-height: 18px;
    }
    .apelido-aviso.erro {
        color: #ff4b4b;
        opacity: 1;
    }

    /* Rótulo do grupo "Matérias": não é um item clicável, é o cabeçalho do
       nível 2 da navegação. Menor, em caixa alta e apagado justamente pra
       não competir com os botões e deixar a hierarquia visível de relance
       (Início e Painel do Professor são nível 1, sem rótulo de grupo). */
    .sidebar-secao {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        opacity: 0.55;
        margin: 4px 0 6px 4px;
    }

    /* "Matérias Cadastradas" fica um pouco mais separada do botão de cima
       ("📊 Estatística") do que o espaçamento padrão do .sidebar-secao —
       reforça visualmente que é o início de um grupo novo, não uma
       continuação do mesmo. */
    .sidebar-secao-espacada {
        margin-top: 16px;
    }

    /* Linha entre "Acessar" e "Início": margem ASSIMÉTRICA de propósito, não
       erro — o st.form do login (que fica logo acima) soma ~19px de espaço
       próprio que o <hr> sozinho não tem embaixo. Medido no DOM (não
       chutado): sem isso, o espaço de cima ficava 27px e o de baixo só 8px.
       margin-top:0 (deixa só o espaço que o form já garante) e
       margin-bottom:19px (iguala ao que sobra em cima) deixam os dois lados
       com a MESMA distância final. */
    .sidebar-divisor-identidade {
        border: none;
        border-top: 1px solid rgba(128, 128, 128, 0.25);
        margin: 0px 4px 19px 4px !important;
    }

    /* Linha entre a última matéria cadastrada e "Painel do Professor":
       margem assimétrica de propósito (mesmo raciocínio da
       .sidebar-divisor-identidade) — medido no DOM, com 8px dos dois lados o
       espaço de cima ficava 24px e o de baixo só 8px. margin-bottom maior
       iguala os dois. */
    .sidebar-divisor-professor {
        border: none;
        border-top: 1px solid rgba(128, 128, 128, 0.25);
        margin: 8px 4px 24px 4px !important;
    }

    /* Cabeçalho da barra lateral: logo EM CIMA, título EMBAIXO, os dois
       centralizados — não lado a lado (a versão anterior deixava o título
       desalinhado com a logo, com cara de gambiarra). */
    div[class*="st-key-sidebar_cabecalho"] {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        /* Aproxima o título da logo — pedido do Wenes (2026-09-13). O
           espaçamento de origem (16px) não vem de nenhuma margem nossa: é o
           "gap" padrão que o Streamlit aplica entre elementos empilhados
           dentro de um container, confirmado medindo ao vivo (getBoundingClientRect
           batendo exatamente com o "gap" do flex, 16px). Reduzir esse gap é o
           jeito direto de aproximar; um "margin-top" negativo no botão do
           título, tentado antes, tem efeito inconsistente aqui porque o botão
           fica dentro de um item flex (que não deixa a margem colapsar com o
           container do jeito esperado) — medido ao vivo, não deu o resultado
           previsto, por isso o ajuste é no gap, não em margem. */
        gap: 2px;
    }
    div[class*="st-key-sidebar_cabecalho"] img {
        margin: 0 auto 0 auto;
        cursor: pointer;
    }

    /* Título "Trilha de Aprendizagem": é um st.button de verdade (leva pra
       Início ao clicar — ver bloco 9), mas precisa PARECER um título, não
       um botão, senão ficaria estranho um retângulo com borda logo abaixo
       da logo. Zera fundo/borda/sombra do botão padrão do Streamlit e deixa
       só o texto, em negrito, centralizado; o :hover sutil (fundo leve) é a
       única pista visual de que aquilo é clicável. */
    div[class*="st-key-nav_titulo_inicio"] button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 4px 6px !important;
        justify-content: center !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        color: inherit !important;
    }
    div[class*="st-key-nav_titulo_inicio"] button:hover {
        background: rgba(128, 128, 128, 0.12) !important;
    }
</style>
""", unsafe_allow_html=True)

def formatar_numero(value, casas=2):
    return f"{value:.{casas}f}".replace(".", ",")


# ==========================================
# 4. CÁLCULOS DO CONTEÚDO NATIVO DE ESTATÍSTICA
# ==========================================
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
    """Tabela de frequência com faixas de largura igual, calculadas a partir do
    intervalo REAL dos dados (do menor ao maior valor da amostra) — não faixas
    fixas tipo "0 a 10". É isso que deixa esse conteúdo funcionar com qualquer
    amostra que o professor cadastrar (nota, idade, altura), igual ao resto da
    Estatística nativa.

    Cada faixa é [início, fim) — fechada no início, aberta no fim — exceto a
    ÚLTIMA, que fecha em val_max (inclusive), senão o próprio valor máximo da
    amostra ficaria de fora de toda faixa."""
    val_min = min(dados)
    val_max = max(dados)
    amplitude = val_max - val_min
    # amplitude 0 (todo mundo com o mesmo valor): usa largura 1 só pra não
    # dividir por zero — as faixas ficam sem sentido prático, mas o cálculo
    # não quebra (caso raro, professor dificilmente cadastra amostra assim).
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

    # Faixa modal: a de maior frequência (empate resolvido pela primeira que
    # aparece — caso raro, não crítico pra fins didáticos).
    faixa_moda = max(faixas, key=lambda f: f["freq"])

    return dict(faixas=faixas, total=total, faixa_moda=faixa_moda)


def rotulo_faixa(f):
    """'X a Y' formatado — usado tanto no texto da missão quanto na resposta
    certa da missão de leitura de gráfico, pra garantir que os dois batem."""
    return f"{formatar_numero(f['inicio'], 1)} a {formatar_numero(f['fim'], 1)}"


def calcular_quartis(dados):
    """Q1, Mediana (Q2) e Q3 pelo método da mediana das metades: ordena os
    dados, divide ao meio pela mediana. Se a quantidade for ÍMPAR, a própria
    mediana NÃO entra em nenhuma das duas metades — é a convenção mais comum
    ensinada no Ensino Médio brasileiro pra box-plot (existe mais de um
    método de calcular quartil; este foi o escolhido de propósito, pra bater
    com o que costuma ser ensinado em sala)."""
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
    """Diagrama de ramos e folhas: ramo = parte inteira, folha = primeira
    casa decimal (assume até 1 casa decimal, a mesma precisão usada no resto
    do app — ver formatar_numero). Retorna {ramo: [folhas], ...} com os
    ramos em ordem crescente (dict preserva a ordem de inserção, e os dados
    entram já ordenados)."""
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
    """Formata {ramo: [folhas]} como texto monoespaçado 'Ramo | Folhas',
    alinhado à direita pelo ramo mais largo -- é assim que o diagrama de
    ramos e folhas é tradicionalmente apresentado (uma tabela de texto, não
    um gráfico)."""
    largura_ramo = max((len(str(r)) for r in ramos), default=1)
    linhas = [
        f"{str(ramo).rjust(largura_ramo)} | {' '.join(str(f) for f in folhas)}"
        for ramo, folhas in ramos.items()
    ]
    return "\n".join(linhas)


def calcular_reta_tendencia(xs, ys):
    """Inclinação e intercepto da reta de tendência (regressão linear
    simples, mínimos quadrados) que melhor descreve a relação entre duas
    variáveis numéricas. Usa np.polyfit em vez de fórmula feita à mão, pra
    não arriscar erro de conta."""
    inclinacao, intercepto = np.polyfit(xs, ys, 1)
    return dict(inclinacao=float(inclinacao), intercepto=float(intercepto))


def prever_pela_reta(reta, x):
    return reta["inclinacao"] * x + reta["intercepto"]


# ==========================================
# 5. VERIFICAÇÃO GENÉRICA DE RESPOSTAS
# ==========================================
# Sem isso, um aluno que acerta de primeira e um que erra 20 vezes na mesma
# missão ganhavam o mesmo XP — o professor orientador apontou esse problema
# (2026-09-05). A correção NÃO pode ser "perder XP ao errar": além de zerar o
# aluno que erra metade das vezes (o próprio Wenes notou isso), contradiria a
# Justificativa do TCC, que trata o erro como parte do processo, não motivo de
# perda. A solução é o XP da missão diminuir com as tentativas, mas nunca ficar
# negativo nem chegar a zero — o aluno sempre ganha algo por terminar.
DESCONTO_XP_POR_ERRO = 0.20   # cada erro NESTA missão reduz 20% do XP dela
PISO_XP_FRACAO = 0.20         # nunca menos que 20% do valor configurado pelo professor

def calcular_xp_por_desempenho(pontos_base, erros_nesta_missao):
    """XP realmente concedido por uma missão, considerando quantas vezes o
    aluno errou ELA (não o conteúdo inteiro) antes de acertar.

    É proporcional ao XP que o professor configurou, então funciona igual pra
    missão de 10, de 20 ou de 100 pontos. Com XP muito baixo (1 ou 2), o
    desconto pode não aparecer por causa do arredondamento — o piso de "ganha
    pelo menos 1" prevalece. Aceito como caso raro: professor dificilmente
    configura XP tão baixo a ponto de a diferença sumir."""
    fracao = max(1 - erros_nesta_missao * DESCONTO_XP_POR_ERRO, PISO_XP_FRACAO)
    return max(round(pontos_base * fracao), 1)


def verificar_resposta(conteudo_id, missao_id, resposta_aluno, resposta_certa, pontos, tipo="numero"):
    # Rótulo curto: o cabeçalho "### 📍 Missão N: ..." logo acima já diz qual
    # missão é — repetir "da Missão N" no botão era informação redundante
    # (mesmo padrão de simplificação pedido pelo Wenes em 2026-09-14 pros
    # botões do Painel do Professor, aplicado aqui porque este é o botão de
    # missão que aparece em TODO conteúdo do app, nativo ou cadastrado).
    if st.button("Verificar Resposta", key=f"btn_{conteudo_id}_{missao_id}"):
        if resposta_aluno is None or str(resposta_aluno).strip() == "":
            st.error("⚠️ Escolha uma alternativa antes de verificar!" if tipo == "multipla"
                     else "⚠️ Digite um valor antes de verificar!")
            return

        acertou = False
        if tipo == "multipla":
            # Comparação exata: o aluno não digita nada, apenas escolhe uma das
            # alternativas cadastradas, então os dois lados vêm do mesmo texto.
            # É justamente isso que a múltipla escolha resolve — em resposta
            # digitada, "media" e "média" são strings diferentes e o aluno perde
            # o ponto por causa do acento, não por causa do conteúdo.
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
            # Guardado em session_state em vez de um st.success() mostrado
            # aqui na hora: o st.rerun() logo abaixo troca a tela quase
            # instantaneamente, e a mensagem só ficava visível por uma fração
            # de segundo — sem tempo de leitura nenhum (relatado pelo Wenes,
            # 2026-09-14: não dava tempo de ler nem tirando
            # print). Quem desenha esse texto na tela, de forma PERSISTENTE
            # (sem sumir sozinha), é renderizar_ultimo_resultado(), chamada
            # embaixo de tudo na aba Missões (perto de onde o aluno clicou).
            st.session_state[f"ultimo_resultado_{conteudo_id}"] = mensagem
            perfil["xp_total"] = perfil.get("xp_total", 0) + xp_ganho
            prog["missao_atual"] += 1
            prog["erros_missao_atual"] = 0  # zera para a próxima missão começar sem desconto
            prog["historico"].append(f"✅ Missão {missao_id} concluída. Resposta: `{resposta_aluno}` (+{xp_ganho} XP)")
            st.session_state[f"m_{conteudo_id}_{missao_id}"] = resposta_aluno
            # Guarda TAMBÉM no banco (prog["respostas"], persistido por
            # salvar_perfil_e_progresso): o session_state acima é só desta
            # aba do navegador, some numa sessão nova. Sem isso, quem volta
            # depois via outra sessão via as missões já feitas mostrando
            # "(Resposta: None)" — bug relatado pelo Wenes (2026-09-14).
            prog.setdefault("respostas", {})[str(missao_id)] = resposta_aluno
            salvar_perfil_e_progresso(nome_aluno, conteudo_id, perfil, prog)
            st.rerun()
        else:
            prog["erros"] = prog.get("erros", 0) + 1
            prog["erros_missao_atual"] = prog.get("erros_missao_atual", 0) + 1
            salvar_perfil_e_progresso(nome_aluno, conteudo_id, perfil, prog)
            # Limpa o "🎉 Correto!" da missão anterior: sem isso, ele ficava
            # em session_state pra sempre (só é sobrescrito num ACERTO) e
            # aparecia junto do "❌ Resposta incorreta" da tentativa atual —
            # as duas mensagens empilhadas, tumultuado (relatado pelo Wenes,
            # 2026-09-14). Errar tem que apagar o acerto de antes, não só
            # somar mais uma mensagem em cima.
            st.session_state.pop(f"ultimo_resultado_{conteudo_id}", None)
            st.error("❌ Resposta incorreta. Revise o conteúdo e tente de novo!")


def renderizar_ultimo_resultado(conteudo_id):
    """Mostra o resultado da última missão respondida CORRETAMENTE dentro
    deste conteúdo, de forma persistente — sem sumir sozinha, ao contrário do
    st.success() antigo que ficava só uma fração de segundo antes do
    st.rerun() trocar a tela (ver verificar_resposta). Fica visível até o
    aluno responder a missão seguinte, quando o texto é substituído.

    Chamada DEPOIS de desenhar a(s) missão(ões) (não antes, perto do selo de
    XP): tem que cair perto de onde o aluno já está olhando, embaixo do botão
    "Verificar Resposta" que ele acabou de clicar — a mesma posição de onde
    já fica o "❌ Resposta incorreta" quando erra."""
    mensagem = st.session_state.get(f"ultimo_resultado_{conteudo_id}")
    if mensagem:
        st.success(mensagem)


def flash(mensagem):
    """Guarda uma mensagem de sucesso pra mostrar DEPOIS do st.rerun(), num
    pop-up fixo no canto superior direito (ver renderizar_flash_pendente,
    chamado uma vez só no roteamento principal — não precisa de "onde"
    mostrar, por isso, ao contrário de renderizar_ultimo_resultado, não
    recebe posição nenhuma)."""
    st.session_state["_flash_pendente"] = mensagem


def renderizar_flash_pendente():
    """Mostra (e consome) a mensagem guardada por flash(), se tiver alguma,
    como um card fixo no canto superior direito — não precisa rolar a tela
    pra ver, ao contrário de um st.success() desenhado no meio do formulário
    (bug relatado pelo Wenes, 2026-09-17: editou um conteúdo longo, salvou, e
    a mensagem ficou fora da tela, lá em cima). st.toast() faria a mesma
    coisa nativamente, mas parou de funcionar neste ambiente."""
    mensagem = st.session_state.pop("_flash_pendente", None)
    if mensagem:
        st.markdown(
            f'<div class="flash-toast">✅ {mensagem}</div>',
            unsafe_allow_html=True,
        )


# ==========================================
# ==========================================
# 6. PÁGINA INICIAL (BANNER + ATALHOS)
# ==========================================
@st.fragment(run_every="5s")
def render_placar_turma():
    """Placar da turma, no estilo Kahoot: apelido + XP, atualizando sozinho.

    O @st.fragment(run_every="5s") faz SÓ este bloco recarregar de 5 em 5
    segundos, sem repintar a página nem interromper o aluno que está no meio de
    uma missão. Não é push — o Streamlit não avisa as outras sessões; é o
    navegador de cada aluno consultando o banco. Com uma turma pequena e a
    consulta enxuta de ranking_turma(), a carga é desprezível.

    Mostrar o desempenho em público só é aceitável porque o aluno entra com
    apelido (ver "O aluno entra com APELIDO" no CLAUDE.md): o objetivo não é
    anonimato, é não expor o nome de quem está atrás. Quem quiser se revelar,
    se revela — e isso vira parte da brincadeira."""
    placar = ranking_turma()
    if not placar:
        return

    eu = st.session_state.aluno_ativo
    medalhas = {1: "🥇", 2: "🥈", 3: "🥉"}
    linhas_html = []
    for posicao, (apelido, xp) in enumerate(placar, start=1):
        destaque = " eu" if apelido == eu else ""
        marcador = medalhas.get(posicao, f"{posicao}º")
        linhas_html.append(
            f'<div class="placar-linha{destaque}">'
            f'<span class="placar-pos">{marcador}</span>'
            f'<span class="placar-nome">{apelido}</span>'
            f'<span class="placar-xp">{xp} XP</span>'
            f"</div>"
        )
    st.markdown(
        f'<div class="placar-caixa">{"".join(linhas_html)}</div>',
        unsafe_allow_html=True,
    )
    if not eu:
        st.caption("Entre com um apelido na barra lateral para aparecer no placar.")


def renderizar_grade_cartoes(cartoes, prefixo_key):
    """Grade de cartões (ícone, título, descrição, botão "Acessar →"), 3 por
    linha. cartoes é uma lista de dicts {icone, titulo, descricao, on_click,
    progresso} — on_click é uma função SEM argumento, chamada ao clicar no
    botão (varia: pode abrir uma matéria direto, ou abrir o hub de
    Estatística). "progresso" é opcional: uma string tipo "3/8" ou "✓" pra
    mostrar quantas missões DAQUELE card específico já foram concluídas —
    pedido do Wenes (2026-09-14), porque o "8/44" do menu lateral soma os 6
    sub-temas de Estatística juntos e não dá pra saber, olhando só ali, quanto
    cada um já rendeu individualmente.

    Usada tanto pelos "Conteúdos disponíveis" da Início quanto pelos 6
    sub-temas do hub de Estatística — prefixo_key garante keys únicas nos
    widgets mesmo quando a mesma matéria aparece nas duas telas."""
    for inicio_linha in range(0, len(cartoes), 3):
        colunas = st.columns(3)
        for i, cartao in enumerate(cartoes[inicio_linha:inicio_linha + 3]):
            idx_global = inicio_linha + i
            cor = PALETA_CORES_CARTAO[idx_global % len(PALETA_CORES_CARTAO)]
            with colunas[i]:
                with st.container(border=True, key=f"{prefixo_key}_cartao_{idx_global}_cor_{cor}"):
                    # Progresso na MESMA linha do título, texto simples (sem
                    # badge colorido) — mesmo padrão já usado no menu lateral
                    # ("📊 Estatística · 1/44"). Uma versão anterior usava um
                    # badge numa linha própria, mas isso deixava o card mais
                    # alto que o necessário só por causa de uma informação
                    # curta — pedido do Wenes (2026-09-14).
                    titulo_linha = f"#### {cartao['icone']} {cartao['titulo']}"
                    if cartao.get("progresso"):
                        titulo_linha += f"  ·  {cartao['progresso']}"
                    st.markdown(titulo_linha)
                    st.caption(cartao.get("descricao", ""))
                    if st.button("Acessar →", key=f"{prefixo_key}_btn_{idx_global}", use_container_width=True):
                        cartao["on_click"]()


def render_pagina_estatistica_hub():
    if st.button("← Voltar", key="voltar_inicio_hub"):
        st.session_state.pagina = PAGINA_INICIO
        st.rerun()
    st.title("📊 Estatística")
    st.markdown("Escolha o tema que você quer estudar.")
    st.write("---")
    concluidas_por_conteudo = progresso_resumo_aluno()
    cartoes = []
    for cid in IDS_ESTATISTICA_HUB:
        total = obter_total_missoes(cid)
        progresso = None
        if st.session_state.aluno_ativo and total:
            feitas = min(concluidas_por_conteudo.get(cid, 0), total)
            progresso = "✓" if feitas >= total else f"{feitas}/{total}"
        cartoes.append({
            "icone": st.session_state.conteudos[cid]["icone"],
            "titulo": st.session_state.conteudos[cid]["titulo"],
            "descricao": st.session_state.conteudos[cid].get("descricao", ""),
            "on_click": (lambda cid=cid: ir_para_materia(cid)),
            "progresso": progresso,
        })
    renderizar_grade_cartoes(cartoes, prefixo_key="hub_estatistica")


def render_pagina_inicial():
    aluno = st.session_state.aluno_ativo

    if aluno:
        perfil = perfil_atual()
        saudacao = f"Bem-vindo(a) de volta, {aluno}! 🏆 Você já tem {perfil['xp_total']} XP acumulados."
    else:
        saudacao = "Escolha um apelido na barra lateral para começar a acumular XP e salvar seu progresso."

    logo_b64 = obter_logo_base64()
    if logo_b64:
        logo_html = f'<img class="home-banner-logo-img" src="data:image/svg+xml;base64,{logo_b64}" alt="Logo" />'
    else:
        logo_html = '<div class="home-banner-logo">🎓</div>'

    if os.path.exists(ARQUIVO_BANNER):
        # Banner pronto (arte finalizada, com a logo já embutida) tem prioridade sobre o banner gerado por CSS.
        st.image(ARQUIVO_BANNER, use_container_width=True)
        st.markdown(f"##### {saudacao}")
    else:
        st.markdown(f"""
        <div class="home-banner">
            {logo_html}
            <p class="home-banner-titulo">Trilha de Aprendizagem</p>
            <p class="home-banner-subtitulo">
                Uma plataforma interativa e gamificada para estudar qualquer disciplina —
                de Estatística a Probabilidade, Equações, História ou o que o seu professor cadastrar.
                {saudacao}
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Dentro de um expander, FECHADO por padrão — quem tem curiosidade clica e
    # vê, quem não tem, nem repara que existe (decisão de 2026-09-05, a pedido
    # do usuário). Cada navegador é uma sessão isolada do Streamlit: o
    # professor abrir ou fechar no notebook projetado no data show não afeta
    # o que aparece no celular de nenhum aluno. Também ajuda com turma grande,
    # onde a lista ficaria comprida antes do resto da página.
    with st.expander("🏆 Placar da Turma", expanded=False):
        render_placar_turma()
    st.write("")

    st.markdown("### 🧭 Como funciona")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="home-step-card">
            <div class="home-step-numero">Passo 1</div>
            <div class="home-step-titulo">📚 Escolha uma matéria</div>
            <div class="home-step-texto">Clique em uma das matérias na barra lateral (ou nos cartões abaixo) para abrir a disciplina que quer estudar.</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="home-step-card">
            <div class="home-step-numero">Passo 2</div>
            <div class="home-step-titulo">📖 Estude a teoria</div>
            <div class="home-step-texto">Veja as explicações passo a passo antes de partir para os desafios.</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="home-step-card">
            <div class="home-step-numero">Passo 3</div>
            <div class="home-step-titulo">🎮 Jogue as Missões</div>
            <div class="home-step-texto">Na própria matéria, troque para a aba Missões: responda os desafios, ganhe XP e acompanhe seu progresso.</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.markdown("### 📚 Conteúdos disponíveis")
    st.caption("Clique para ir direto ao conteúdo.")

    # Os 3 conteúdos nativos de Estatística viram UM cartão só ("📊 Estatística",
    # desenhado à mão porque a ação dele é diferente: abre o hub, não uma
    # matéria) — o resto vem dos conteúdos de verdade, via renderizar_grade_cartoes.
    cartoes = [{
        "icone": "📊", "titulo": "Estatística",
        "descricao": "Escolha o tema que você quer estudar.",
        "on_click": ir_para_hub_estatistica,
    }]
    for cid in st.session_state.conteudos:
        if cid in IDS_ESTATISTICA_HUB:
            continue
        info = st.session_state.conteudos[cid]
        cartoes.append({
            "icone": info["icone"], "titulo": info["titulo"], "descricao": info.get("descricao", ""),
            "on_click": (lambda cid=cid: ir_para_materia(cid)),
        })
    renderizar_grade_cartoes(cartoes, prefixo_key="home")

    if not aluno:
        st.info("💡 Dica: professores encontram o cadastro de novos conteúdos e as senhas em **🛡️ Painel do Professor**, na barra lateral.")


def render_pagina_estatistica():
    dados = st.session_state.dados_estatistica
    s = calcular_estatisticas(dados)

    # O título da matéria é desenhado pelo roteador (bloco 10), junto com os
    # botões Teoria/Missões — aqui entra só o conteúdo da aba Teoria.
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

    # O título da matéria é desenhado pelo roteador (bloco 10), junto com os
    # botões Teoria/Missões — aqui entra só o conteúdo da aba Teoria.
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


def grafico_barras_simples(categorias, valores, titulo_y):
    """Gráfico de barras comum (eixo Y sempre começando em zero), desenhado
    com Altair puro em vez de st.bar_chart. O st.bar_chart nativo do
    Streamlit prende o scroll do mouse quando o cursor está em cima dele —
    quem tenta rolar a página fica "preso" dando zoom no gráfico em vez de
    descer a tela (bug relatado, confirmado só nele: os outros gráficos do
    app já usam Altair puro, sem esse problema). Trocar por Altair aqui
    resolve, mantendo a mesma altura/largura dos demais."""
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
    """Gráfico de barras com o eixo Y fixado manualmente entre eixo_min e
    eixo_max. O st.bar_chart nativo do Streamlit sempre inclui o zero no
    eixo — o que é ótimo pra não enganar ninguém, mas impede DEMONSTRAR o
    truque do eixo cortado. O Altair (já usado no projeto) permite fixar o
    domínio do eixo à mão, então é ele quem desenha os gráficos do conteúdo
    de Leitura Crítica de Gráficos.

    zero=False + clip=True são obrigatórios aqui: por padrão o Vega-Lite
    ANCORA toda barra no zero e corta (não desenha) o que fica fora do
    domínio visível — proteção do próprio Vega-Lite contra gráfico enganoso.
    Sem esses dois, a barra do eixo cortado simplesmente não aparecia (testado:
    tela em branco onde deveriam estar as barras).

    Largura própria, menor que LARGURA_GRAFICO: esse gráfico só tem 2
    categorias (Produto A / Produto B) — na largura padrão (pensada pra 5
    faixas ou 10 pontos de dispersão) as barras ficavam enormes, largas
    demais pra só 2 categorias."""
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


def render_pagina_leitura_grafica():
    # O título da matéria é desenhado pelo roteador (bloco 10), junto com os
    # botões Teoria/Missões — aqui entra só o conteúdo da aba Teoria.
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


def grafico_boxplot_manual(q):
    """Desenha o box-plot à mão (mark_rule pros limites min-max + mark_bar pra
    caixa Q1-Q3 + mark_tick pra linha da mediana), em vez de usar o
    mark_boxplot() pronto do Altair.

    Motivo: mark_boxplot() calcula os próprios quartis, por um método
    diferente do usado em calcular_quartis() (interpolação, não mediana das
    metades) — os números podiam não bater com o que a missão pede pro aluno
    calcular. Desenhando à mão a partir de "q" (o mesmo dict usado nas
    missões), o gráfico mostra EXATAMENTE os números certos, sem essa
    divergência.

    Largura própria, bem menor que LARGURA_GRAFICO: só existe UMA categoria
    ("Amostra") — na largura padrão (pensada pra 5 faixas ou 10 pontos de
    dispersão) a caixa ficava uma única barra grossa cercada de espaço vazio
    dos dois lados, visivelmente desproporcional (reclamação do Wenes,
    2026-09-14, confirmada ao vivo no navegador: caixa de 60px perdida no
    meio de 380px). Reduzir largura E espessura da caixa/mediana deixa o
    gráfico compacto em vez de esparramado, mesmo raciocínio já aplicado em
    LARGURA_DUAS_CATEGORIAS pro gráfico de Leitura Crítica."""
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


def render_pagina_comparacao_diagramas():
    dados = st.session_state.dados_estatistica
    q = calcular_quartis(dados)
    ramos = calcular_ramo_folhas(dados)

    # O título da matéria é desenhado pelo roteador (bloco 10), junto com os
    # botões Teoria/Missões — aqui entra só o conteúdo da aba Teoria.
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

    # O título da matéria é desenhado pelo roteador (bloco 10), junto com os
    # botões Teoria/Missões — aqui entra só o conteúdo da aba Teoria.
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


def grafico_dispersao_com_reta(xs, ys, reta, titulo_x, titulo_y):
    """Gráfico de dispersão (um ponto por par x,y) com a reta de tendência
    desenhada por cima. A reta é traçada a partir de "reta" (inclinação e
    intercepto já calculados por calcular_reta_tendencia), não de um ajuste
    automático do Altair -- mesmo motivo do box-plot: garantir que o desenho
    bate exatamente com os números que as missões pedem pro aluno ler."""
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


def render_pagina_tendencia():
    xs, ys = TENDENCIA_HORAS_ESTUDO, TENDENCIA_NOTAS
    reta = calcular_reta_tendencia(xs, ys)

    # O título da matéria é desenhado pelo roteador (bloco 10), junto com os
    # botões Teoria/Missões — aqui entra só o conteúdo da aba Teoria.
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
    # Título desenhado pelo roteador (bloco 10), junto com os botões Teoria/Missões.
    if conteudo.get("descricao"):
        st.markdown(f"*{conteudo['descricao']}*")
    st.write("---")

    secoes = conteudo.get("teoria", [])
    if not secoes:
        st.info("📭 Este conteúdo ainda não possui teoria cadastrada. Peça ao professor para adicioná-la no Painel do Professor.")
        return

    # st.expander de verdade (o mesmo componente do conteúdo estático, não uma
    # imitação) com expanded=True — já abre mostrando o conteúdo, mas o aluno
    # pode recolher se quiser limpar a tela.
    for i, secao in enumerate(secoes, start=1):
        with st.expander(f"{i}️⃣ {secao.get('titulo', '')}", expanded=True):
            st.markdown(secao.get("texto", ""))
        st.write("")


# ==========================================
# 7. PÁGINA "TRILHA DE MISSÕES" — ESTÁTICA E DINÂMICA
# ==========================================
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

    # Missões 1 a FREQ_N_FAIXAS: uma por faixa, na ordem — cada uma pede a
    # frequência absoluta de UMA faixa, igual ao "passo a passo" das 10
    # missões nativas de Estatística Descritiva.
    for i, f in enumerate(faixas, start=1):
        rotulo = rotulo_faixa(f)
        if prog["missao_atual"] > i:
            st.success(f"✅ Missão {i} Concluída! (Faixa {rotulo}: {st.session_state.get(f'm_{cid}_{i}')})")
        elif prog["missao_atual"] == i:
            st.markdown(f'### 📍 Missão {i}: Faixa {i} de {FREQ_N_FAIXAS} ({rotulo})')
            resp = st.number_input(f"Quantos itens da amostra estão entre {rotulo}?", step=1, value=None, key=f"in_{cid}_{i}")
            verificar_resposta(cid, i, resp, f["freq"], 20)

    # Missão FREQ_N_FAIXAS+1: soma das frequências, tem que bater com o total
    # da amostra — confirma que nenhum item ficou de fora, nenhum foi contado
    # duas vezes (o mesmo raciocínio do expander "Ver Teoria" da aba Teoria).
    idx_total = FREQ_N_FAIXAS + 1
    if prog["missao_atual"] > idx_total:
        st.success(f"✅ Missão {idx_total} Concluída! (Total: {st.session_state.get(f'm_{cid}_{idx_total}')})")
    elif prog["missao_atual"] == idx_total:
        st.markdown(f'### 📍 Missão {idx_total}: Conferindo o Total')
        resp = st.number_input(f"Somando a frequência das {FREQ_N_FAIXAS} faixas, quantos itens tem a amostra ao todo?", step=1, value=None, key=f"in_{cid}_{idx_total}")
        verificar_resposta(cid, idx_total, resp, freq["total"], 20)

    # Missão FREQ_N_FAIXAS+2: frequência relativa (%) da faixa modal.
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

    # Missão FREQ_N_FAIXAS+3 (última): fecha ligando a conta ao gráfico —
    # leitura visual, não cálculo, por isso é múltipla escolha em vez de
    # número digitado (mesmo tipo já usado nas missões dos conteúdos
    # cadastrados pelo professor).
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

    # Sem cabeçalho "Caso 1" aqui de propósito: nenhum outro conteúdo da
    # Trilha tem sub-título antes da primeira missão, só "### 📍 Missão N" —
    # esse cabeçalho quebrava esse padrão e confundia mais do que ajudava
    # (relatado pelo Wenes, 2026-09-14).
    #
    # O gráfico manipulado (eixo cortado) fica visível durante as 3 primeiras
    # missões — é em cima dele que o aluno responde. Na missão 4, troca pelo
    # gráfico honesto (eixo em 0), que é o que a última pergunta usa.
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

    # Sem cabeçalho "Caso 2" (mesmo motivo do Caso 1, acima) — e sem "---"
    # separador também, que nenhum outro conteúdo usa entre missões. A
    # manchete continua aparecendo, só que agora tratada como o gráfico lá
    # de cima: visível SÓ enquanto for relevante (missões 5 a 8), não a
    # trilha inteira depois disso.
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

    # Missões 1-3: os três números que formam o box-plot, um de cada vez —
    # mesma lógica de "passo a passo" das outras missões nativas.
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

    # Missão 4: agora com os 3 números calculados, mostra o box-plot de
    # verdade e pede pra ler o Q3 nele — fecha o ciclo conta -> gráfico.
    if prog["missao_atual"] == 4:
        grafico_boxplot_manual(q)
    if prog["missao_atual"] > 4: st.success(f"✅ Missão 4 Concluída! (Q3 no gráfico: {st.session_state.get(f'm_{cid}_4')})")
    elif prog["missao_atual"] == 4:
        st.markdown('### 📍 Missão 4: Lendo o Box-Plot')
        resp = st.number_input("Olhando o box-plot acima, qual valor marca o TOPO da caixa (Q3)?", step=0.1, value=None, key=f"in_{cid}_4")
        verificar_resposta(cid, 4, resp, q["q3"], 20)

    # Missão 5: ramos e folhas — contar quantos valores caem no ramo mais
    # frequente (empate resolvido pelo primeiro ramo encontrado, mesmo
    # critério já usado na faixa modal da Frequência).
    ramo_mais_comum = max(ramos, key=lambda r: len(ramos[r]))
    if prog["missao_atual"] == 5:
        st.code(texto_ramo_folhas(ramos), language=None)
    if prog["missao_atual"] > 5: st.success(f"✅ Missão 5 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_5')})")
    elif prog["missao_atual"] == 5:
        st.markdown('### 📍 Missão 5: Contando as Folhas')
        resp = st.number_input(f"No diagrama acima, quantos valores tem o ramo {ramo_mais_comum}?", step=1, value=None, key=f"in_{cid}_5")
        verificar_resposta(cid, 5, resp, len(ramos[ramo_mais_comum]), 20)

    # Missão 6 (última): fecha comparando os três diagramas de verdade, não
    # só calculando — vai direto no "reconhecendo os mais eficientes pra cada
    # análise" da própria habilidade EM13MAT409.
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

    # Missões 1-2: distinguir população de amostra no cenário dado — decisão
    # conceitual, não conta, por isso são múltipla escolha.
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

    # Missão 3: confirma o tamanho real da amostra — a única missão numérica
    # do conteúdo, ligando a decisão conceitual a um número concreto.
    if prog["missao_atual"] > 3: st.success(f"✅ Missão 3 Concluída! (Tamanho da amostra: {st.session_state.get(f'm_{cid}_3')})")
    elif prog["missao_atual"] == 3:
        st.markdown('### 📍 Missão 3: O Tamanho da Amostra')
        resp = st.number_input("Quantos valores tem essa amostra?", step=1, value=None, key=f"in_{cid}_3")
        verificar_resposta(cid, 3, resp, s["n"], 20)

    # Missão 4: reconhecer o que é uma boa pergunta de pesquisa.
    if prog["missao_atual"] > 4: st.success(f"✅ Missão 4 Concluída! (Resposta: {st.session_state.get(f'm_{cid}_4')})")
    elif prog["missao_atual"] == 4:
        st.markdown('### 📍 Missão 4: Uma Boa Pergunta de Pesquisa')
        resp = st.radio(
            "Qual dessas perguntas é mais fácil de responder com um número exato, calculado a partir dos dados?",
            ["Os alunos gostam de Matemática?", "Qual é a nota média da turma em Matemática?", "A Matemática é importante?"],
            index=None, key=f"in_{cid}_4",
        )
        verificar_resposta(cid, 4, resp, "Qual é a nota média da turma em Matemática?", 20, tipo="multipla")

    # Missões 5-6: separar tendência central de dispersão — o conteúdo do
    # relatório que a habilidade pede explicitamente.
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

    # O gráfico fica visível o tempo todo nas missões 1-3 (leitura/conceito);
    # nas 4-5 (previsão) ele reaparece porque é nele que a resposta se lê.
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
                # index=None deixa a missão começar SEM alternativa marcada. Com a
                # primeira já selecionada, o aluno poderia clicar em "Verificar"
                # sem ter escolhido nada e levar um erro que não foi escolha dele.
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


# ==========================================
# 8. PAINEL DO PROFESSOR (PROTEGIDO POR SENHA)
# ==========================================
def hex_para_rgb(cor_hex):
    """'#2ecc71' -> (46, 204, 113). fpdf2 quer três inteiros pro set_fill_color,
    não aceita hex direto como o Altair/CSS aceitam."""
    cor_hex = cor_hex.lstrip("#")
    return tuple(int(cor_hex[i:i + 2], 16) for i in (0, 2, 4))


class _PDFComCabecalho(FPDF):
    """FPDF que desenha o timbre institucional (ARQUIVO_CABECALHO) só no topo
    da PRIMEIRA página do relatório (decisão do Wenes, 2026-09-20: as demais
    páginas ficam com o espaço todo para tabelas e gráficos).

    Continua sendo via header() e não um pdf.image() solto depois do
    add_page(): assim a primeira página sempre leva o timbre, e o fpdf2 cuida
    de não desenhá-lo nas páginas seguintes, inclusive nas criadas pela
    quebra automática de página.

    Se o arquivo não existir, o relatório sai sem timbre e nada quebra —
    mesma lógica de fallback do logo.png/banner.png na tela."""

    def header(self):
        if self.page_no() != 1 or not os.path.exists(ARQUIVO_CABECALHO):
            return
        largura = self.w - self.l_margin - self.r_margin
        self.image(ARQUIVO_CABECALHO, x=self.l_margin, y=10, w=largura)
        # pdf.image() não move o cursor no fpdf2, então o Y de onde o conteúdo
        # começa tem que ser calculado: a altura vem da proporção real do
        # arquivo (lida com PIL, não chutada — trocar a arte por uma de outra
        # proporção continua funcionando sem mexer no código).
        with Image.open(ARQUIVO_CABECALHO) as img:
            altura = largura * img.height / img.width
        self.set_y(10 + altura + 6)


def _texto_que_cabe(pdf, texto, largura_celula, folga=2):
    """Encurta o texto com '...' até caber na célula.

    pdf.cell() não quebra linha nem corta: texto maior que a largura vaza por
    cima da célula vizinha. Foi o que aconteceu no teste com o login
    'VingadorDoFuturo3' invadindo a coluna do nome completo ao lado. Login e
    nome no relatório são digitados livremente pelo aluno e pelo professor, então
    não dá pra confiar em limite fixo de caracteres — aqui a medida é em mm, na
    fonte que está ativa no momento da chamada."""
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
    """Data de hoje por extenso (ex.: 'Arraias - TO, 07 de setembro de 2026').

    Calculada fora da função cacheada (gerar_pdf_relatorio) e passada como
    argumento: assim ela entra na chave do @st.cache_data, e o cache se
    renova sozinho quando o dia muda, sem precisar excluir a função do cache."""
    hoje = date.today()
    texto = f"{hoje.day:02d} de {MESES_PT[hoje.month - 1]} de {hoje.year}"
    return f"{cidade}, {texto}" if cidade else texto


LARGURA_ROTULO_CABECALHO_PDF = 32  # mm — cabe "Professor(a):" em negrito 10pt


def _linha_dado_pdf(pdf, rotulo, valor):
    """Uma linha 'Rótulo: valor' alinhada à esquerda — rótulo em negrito com
    largura fixa, pra várias linhas seguidas alinharem o valor na mesma
    coluna (padrão que o Wenes já usa nos documentos curtos de outras
    disciplinas: Acadêmico / Curso / Disciplina / Professor / Data)."""
    pdf.set_font("CMU", 'B', 10)
    pdf.cell(LARGURA_ROTULO_CABECALHO_PDF, 6, text=f"{rotulo}:", align='L')
    pdf.set_font("CMU", '', 10)
    pdf.cell(0, 6, text=valor, align='L', new_x="LMARGIN", new_y="NEXT")


ALTURA_TITULO_GRAFICO_PDF = 10   # título (8mm) + respiro (2mm)
ALTURA_LINHA_GRAFICO_PDF = 7
MINIMO_BARRAS_POR_PAGINA = 3     # nunca deixa 1 ou 2 barras soltas numa página


def _grafico_barras_pdf(pdf, titulo, itens, x_tabela, largura_tabela):
    """Gráfico de barras horizontais (uma por aluno), desenhado à mão com rect().

    itens: lista de (rótulo, fração 0-1 da barra, texto do valor, cor hex).

    Regras de página (pedido do Wenes, 2026-09-20):
    - cabe no espaço que sobrou na página: fica onde está;
    - não cabe: começa numa página nova, e o gráfico ocupa só a(s) página(s)
      dele (quem chamou deve abrir outra página antes do próximo conteúdo);
    - passa de uma página (turma grande): quebra sem deixar barra solta
      (mínimo de MINIMO_BARRAS_POR_PAGINA por página) e repete o título com
      "(continuação)".
    Retorna True se o gráfico usou páginas próprias, False se coube no lugar."""
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
    """'Estatística Descritiva' -> 'estatistica_descritiva' (sem acento nem símbolo)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_") or "conteudo"


def gerar_pdf_relatorio(lista_geral, conteudo_titulo, linhas_conteudo, nome_instituicao="", nome_professor="", turma="", data_relatorio="", linhas_bncc=None, acerto=None):
    """Gera o PDF com margens laterais simétricas, título centralizado e as
    duas tabelas: Desempenho da Turma + Detalhamento do conteúdo que estava em tela.

    Cacheado com @st.cache_data: o st.tabs() do Streamlit renderiza TODAS as
    abas por trás mesmo com só uma visível, então sem cache esse PDF (com
    fonte embutida, nada barato de gerar) era recalculado do zero pra cada
    um dos 5 conteúdos a cada clique na página — mesmo sem nada ter mudado.
    Com o cache, só recalcula quando os argumentos (dados do aluno, nome da
    instituição/professor) realmente mudam entre uma chamada e outra.

    Fonte: CMU Serif (Computer Modern Unicode) embutida via TTF em vez da Arial
    padrão do fpdf2 — visual de documento LaTeX/acadêmico. Os arquivos ficam em
    fonts/ (licença OFL, ver fonts/OFL.txt); precisam ser embutidos porque o
    fpdf2 não vem com essa fonte, e "CMU" não existe nos leitores de PDF por
    padrão. Negrito fica só no título, subtítulos e cabeçalho das tabelas —
    linhas de dado ficam em peso normal, de propósito."""
    pdf = _PDFComCabecalho()
    pdf.add_font("CMU", "", "fonts/CMUSerif-Roman.ttf")
    pdf.add_font("CMU", "B", "fonts/CMUSerif-Bold.ttf")
    pdf.set_margins(left=20, top=20, right=20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    largura_util = pdf.w - pdf.l_margin - pdf.r_margin  # 170mm em A4 com margens de 20mm

    # --- Dados do relatório (Instituição/Professor/Turma opcionais, Data sempre) ---
    # Rótulo em negrito + dois pontos, alinhado à esquerda (pedido do Wenes,
    # 2026-09-07) — é o padrão que ele já usa em documentos curtos de outras
    # disciplinas. Substituiu o bloco centralizado que tinha antes.
    if nome_instituicao:
        _linha_dado_pdf(pdf, "Instituição", nome_instituicao)
    if nome_professor:
        _linha_dado_pdf(pdf, "Professor(a)", nome_professor)
    if turma:
        _linha_dado_pdf(pdf, "Turma", turma)
    _linha_dado_pdf(pdf, "Conteúdo", conteudo_titulo)  # o PDF sai de uma aba e fala só dela
    _linha_dado_pdf(pdf, "Data", data_relatorio)
    pdf.ln(3)

    # --- Título centralizado ---
    pdf.set_font("CMU", 'B', 16)
    pdf.cell(largura_util, 10, text="Relatório de Desempenho - Trilha de Aprendizagem", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # --- Tabela 1: Desempenho da turma ---
    # Tabelas mais estreitas que a largura útil e centralizadas na página (em
    # vez de esticadas de margem a margem) — fica com cara de tabela de
    # relatório/artigo, não de planilha crua. pdf.cell() com new_x="LMARGIN"
    # sempre volta pra margem esquerda da página no fim da linha, então cada
    # linha precisa reposicionar o X pro início da tabela centralizada de novo.
    # A coluna "Nome no Relatório" só entra se ALGUÉM tiver preenchido: professor
    # que não usa o recurso continua recebendo o PDF de 3 colunas de sempre, sem
    # uma coluna vazia ocupando espaço. Quem preencheu só metade da turma recebe
    # as células dos outros em branco, de propósito — dá pra completar à caneta
    # depois de imprimir. As larguras abaixo somam os MESMOS 150mm nos dois
    # casos: o espaço da coluna nova sai da folga das colunas numéricas (45mm
    # pra escrever "175" era exagero), não das margens, que ficam intocadas.
    usar_nome_relatorio = any(str(l.get("Nome no Relatório", "")).strip() for l in lista_geral)

    # COM a coluna de nome a tabela ocupa a largura útil inteira (170mm, ou seja,
    # exatamente de margem a margem) — os 20mm que sobravam de cada lado vão
    # todos pra coluna do nome, que passa de 52 pra 72mm e para de cortar nome
    # completo. SEM a coluna de nome ficam os 150mm centralizados de sempre: com
    # 3 colunas curtas, esticar de margem a margem deixaria a tabela com cara de
    # planilha esticada, e aí a folga é proposital (ver comentário abaixo).
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

    # --- Gráfico de barras: XP por aluno (ver _grafico_barras_pdf: regras de página) ---
    grafico_xp_isolado = False
    if lista_geral:
        maior_xp = max((linha["XP Total"] for linha in lista_geral), default=0) or 1
        itens_xp = [(l["Aluno"], l["XP Total"] / maior_xp, str(l["XP Total"]), l.get("Cor", "#ff4b4b")) for l in lista_geral]
        grafico_xp_isolado = _grafico_barras_pdf(pdf, "Gráfico de XP por Aluno", itens_xp, x_tabela1, largura_tabela1)

    # --- Tabela de habilidades da BNCC (só se houver missão mapeada) ---
    # Fica logo depois do Desempenho da Turma, ainda na primeira página quando
    # cabe: é a tabela que responde "o que a turma aprendeu", enquanto as outras
    # respondem "quanto cada aluno fez".
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

    # --- Acerto por aluno em cada habilidade (igual à tabela da Visão Geral) ---
    # Em blocos de 5 habilidades por tabela, pra caber na largura da página.
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

    # Desempenho da Turma (tabela + gráfico de XP) numa página, Detalhamento
    # por Conteúdo (tabela + gráfico de %) começando limpo na próxima — em vez
    # de deixar as duas seções disputarem espaço na mesma página e a quebra
    # automática cair no meio de qualquer coisa.
    pdf.add_page()

    # --- Tabela 2: Detalhamento do conteúdo que o professor estava vendo ---
    # Mesma regra da tabela 1: com nome vai de margem a margem (170mm) pra dar
    # 68mm ao nome completo; sem nome, 150mm centralizados.
    largura_tabela2 = largura_util if usar_nome_relatorio else 150  # 38+68+26+20+18 | 50+30+40+30
    x_tabela2 = pdf.l_margin + (largura_util - largura_tabela2) / 2
    pdf.set_font("CMU", 'B', 13)
    pdf.set_x(x_tabela2)
    pdf.cell(largura_tabela2, 8, text=f"Detalhamento - {conteudo_titulo}", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CMU", 'B', 11)
    pdf.set_x(x_tabela2)
    if usar_nome_relatorio:
        # 38+68+26+20+18 = 170 (largura útil inteira). A coluna de login tem os
        # mesmos 38mm da tabela 1 de propósito: com 32mm um login comprido
        # colidia com o nome da coluna vizinha (visto no teste). Cabeçalhos
        # encurtados ("Total" em vez de "Total Missões") porque com 5 colunas o
        # texto longo não cabe mais.
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

    # --- Gráfico de barras: % concluído nesse conteúdo, por aluno (escala 0-100) ---
    if linhas_conteudo:
        itens_pct = []
        for linha in linhas_conteudo:
            total_linha = linha["Total de Missões"]
            pct = (linha["Missões Concluídas"] / total_linha * 100) if total_linha else 0
            itens_pct.append((linha["Aluno"], pct / 100, f"{pct:.0f}%", cor_por_percentual_concluido(pct)))
        _grafico_barras_pdf(pdf, "Gráfico de % Concluído", itens_pct, x_tabela2, largura_tabela2)

    return bytes(pdf.output())


CORES_DESEMPENHO = ["#2ecc71", "#f1c40f", "#e74c3c"]  # verde, amarelo, vermelho


def cor_por_percentual_concluido(percentual):
    """Verde (>=70%), amarelo (40-69%) ou vermelho (<40%) — sinaliza de longe
    quem tá indo bem, mediano ou precisando de atenção num conteúdo."""
    verde, amarelo, vermelho = CORES_DESEMPENHO
    if percentual >= 70:
        return verde
    if percentual >= 40:
        return amarelo
    return vermelho


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


def _fundo_acerto(percentual):
    """Fundo suave da célula (mesmas faixas do resto do painel: >=70 verde, 40-69
    amarelo, <40 vermelho), claro o bastante para o texto escuro ler bem nos
    dois temas."""
    if percentual >= 70:
        return "background-color: #c9f0d6; color: #1f2937"
    if percentual >= 40:
        return "background-color: #fbefb5; color: #1f2937"
    return "background-color: #f6c9c4; color: #1f2937"


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


def _percentual_acerto(par):
    """Porcentagem de acerto de um [acertos, tentativas], ou None se não houve tentativa."""
    if not par or not par[1]:
        return None
    return round(par[0] / par[1] * 100)


def _texto_acerto(par):
    """Texto da célula: '62% (24/39)', ou '—' sem tentativa."""
    pct = _percentual_acerto(par)
    return "—" if pct is None else f"{pct}% ({par[0]}/{par[1]})"


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
            # A linha da turma tem cor própria (fundo cinza, texto azul escuro, sem verde/amarelo/vermelho),
            # pra não ser confundida com um aluno.
            linhas_css.append([ESTILO_LINHA_TURMA] * (len(pcts) + 1))
        else:
            linhas_css.append([""] + [_fundo_acerto(p) if p is not None else "" for p in pcts])
    # Título de cada coluna com o total de missões da habilidade, pra dar a medida
    # do "(acertos/tentativas)".
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
    """Popup modal de verdade (st.dialog) em vez do aviso aparecer mais embaixo
    na página, obrigando a rolar pra achar."""
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
    """Tabela e gráfico de conclusão por habilidade da BNCC (da turma toda, ou de um conteúdo)."""
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
        # Duas colunas (Conclusões, Possíveis) juntas numa só ("12/20"), do mesmo jeito
        # que o PDF já mostra — eram números soltos aqui na tela, sem a fração que dá
        # sentido a "Possíveis" (ver conversa de 2026-09-05: até o próprio autor do app
        # leu a tabela e não conseguiu adivinhar o que "Possíveis 20" queria dizer).
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
                # Tooltip explícito: sem isso, o Altair mostra também "Cor" (o
                # hexadecimal da faixa de cor) e "_Cor_sort_index" (campo
                # interno do Vega-Lite), que não dizem nada útil (2026-09-06).
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

    # Meta de XP: o professor define em Configurações; sem valor salvo
    # ainda, cai pra metade do catálogo atual — um chute razoável de
    # partida, que ele pode ajustar a qualquer momento.
    _, _, xp_catalogo_total = xp_maximo_catalogo_atual()
    meta_xp = st.session_state.config.get("meta_xp") or (xp_catalogo_total / 2)

    lista_geral = []
    for nome, perfil in alunos.items():
        erros_totais = sum(p.get("erros", 0) for p in perfil.get("progresso", {}).values())
        xp_total = perfil.get("xp_total", 0)
        # Cor por FAIXA DE XP (ver cor_por_xp) — nesse gráfico o comprimento
        # da barra já É o XP, então a cor precisa falar da mesma coisa que o
        # comprimento, senão vira duas leituras diferentes disputando o
        # mesmo desenho (confuso, relatado pelo Wenes, 2026-09-14). Reaproveita
        # cor_por_percentual_concluido — a MESMA função/faixa (≥70% verde,
        # 40-69% amarelo, <40% vermelho) que já colore os outros gráficos do
        # painel — em vez de uma faixa própria só pra este gráfico: um
        # critério só pro app inteiro, mais fácil de entender e de explicar.
        pct_da_meta = min(xp_total / meta_xp * 100, 100) if meta_xp else 0
        lista_geral.append({
            "Aluno": nome, "Nome no Relatório": perfil.get("nome_relatorio", ""),
            "XP Total": xp_total, "Erros Totais": erros_totais,
            "Cor": cor_por_percentual_concluido(pct_da_meta),
        })

    # ---------- Abas no topo: tudo abaixo segue a aba escolhida ----------
    # "Geral" mostra a turma em todos os conteúdos (XP, exclusão de aluno, nomes do
    # relatório); cada conteúdo mostra só os dados dele, e o PDF sai da aba dele.
    # on_change="rerun": só a aba aberta é calculada e enviada (as outras ficam vazias).
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
            # Tabela em HTML (título em negrito, como as outras). A exclusão deixou de ser
            # por caixinha na tabela e passou a ser por lista de nomes, logo acima dela.
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

            # Editor num expander separado, e NÃO um st.data_editor no lugar da tabela
            # acima: aquela tabela usa on_select pra escolher o aluno a excluir, e
            # st.data_editor não tem seleção de linha — trocar uma pela outra mataria
            # o botão de excluir aluno individual.
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

            # Cor por faixa de % de missões concluídas (verde/amarelo/vermelho), somando
            # todos os conteúdos — mesma lógica e mesma técnica (Altair com domain==range)
            # do gráfico de "Detalhamento por Conteúdo", pra não reintroduzir o bug de
            # cor trocada do st.bar_chart(..., color=coluna).
            grafico_geral = (
                alt.Chart(df_geral)
                .mark_bar()
                .encode(
                    x=alt.X("XP Total:Q"),
                    y=alt.Y("Aluno:N", sort=None),
                    color=alt.Color("Cor:N", scale=alt.Scale(domain=CORES_DESEMPENHO, range=CORES_DESEMPENHO), legend=None),
                    # Sem isso, o Altair mostra TODOS os campos codificados no tooltip
                    # ao passar o mouse — incluindo "Cor" (o hexadecimal por trás da
                    # faixa verde/amarelo/vermelho) e "_Cor_sort_index" (campo interno
                    # que o Vega-Lite cria sozinho pra ordenar a escala de cor). Nenhum
                    # dos dois diz algo útil pro professor; a lista explícita abaixo
                    # restringe o tooltip só ao que interessa.
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
                # missao_atual aponta pra próxima missão a responder (começa em 1);
                # "concluídas" é sempre missao_atual - 1, com limite no total.
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
                # st.bar_chart(..., color="Cor") passava por aqui antes, mas o Vega-Lite
                # (motor por trás) às vezes trocava verde por amarelo — ele monta a
                # ordem das cores sozinho a partir dos valores únicos da coluna, e essa
                # ordem podia não bater com a ordem em que os dados aparecem. Usando
                # Altair direto com domain==range idênticos, cada cor sempre mapeia
                # pra ela mesma não importa a ordem que o Vega-Lite decidir usar por
                # baixo dos panos.
                grafico = (
                    alt.Chart(df_conteudo)
                    .mark_bar()
                    .encode(
                        x=alt.X("% Concluído:Q"),
                        y=alt.Y("Aluno:N", sort=None),
                        color=alt.Color("Cor:N", scale=alt.Scale(domain=CORES_DESEMPENHO, range=CORES_DESEMPENHO), legend=None),
                        # Tooltip explícito, mesmo motivo dos outros dois gráficos de
                        # barra colorida por faixa (2026-09-06): sem isso, "Cor" e
                        # "_Cor_sort_index" (interno do Vega-Lite) apareciam à toa.
                        tooltip=[alt.Tooltip("Aluno:N", title="Aluno"), alt.Tooltip("% Concluído:Q", title="% Concluído")],
                    )
                )
                st.altair_chart(grafico, use_container_width=True)

            # O PDF só é gerado quando o professor clica em Exportar (data recebe uma
            # função, não os bytes). Antes eram gerados os 10 PDFs, um por aba, a cada
            # troca de página, e a tela ficava velha e apagada esperando.
            gerar_este_pdf = functools.partial(
                gerar_pdf_relatorio,
                lista_geral, conteudo_info["titulo"], linhas,
                nome_instituicao=st.session_state.config.get("nome_instituicao", ""),
                nome_professor=st.session_state.config.get("nome_professor", ""),
                turma=st.session_state.config.get("turma", ""),
                data_relatorio=formatar_data_relatorio(st.session_state.config.get("cidade", "")),
                # Habilidades e acerto só deste conteúdo: o PDF sai da aba e fala dela.
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


@st.dialog("🗑️ Excluir conteúdo")
def _dialog_confirmar_exclusao_conteudo(cid, c):
    st.warning(f"⚠️ Tem certeza que deseja excluir **{c['icone']} {c['titulo']}**? A teoria e as missões cadastradas serão perdidas permanentemente.")
    col_conf, col_canc = st.columns(2)
    with col_conf:
        if st.button("✅ Sim, excluir", key=f"confirmar_del_{cid}", type="primary", use_container_width=True):
            del st.session_state.conteudos[cid]
            salvar_conteudos(st.session_state.conteudos)
            if st.session_state.conteudo_ativo == cid:
                st.session_state.conteudo_ativo = ID_CONTEUDO_ESTATISTICA
            st.rerun()
    with col_canc:
        if st.button("❌ Cancelar", key=f"cancelar_del_{cid}", use_container_width=True):
            st.rerun()


def mover_conteudo(cid, direcao):
    """Sobe (direcao=-1) ou desce (direcao=+1) um conteúdo CADASTRADO PELO
    PROFESSOR uma posição — só entre si, nunca em relação aos nativos.

    Regra final, confirmada pelo Wenes (2026-09-14) depois de duas voltas:
    os nativos são conteúdo FIXO e PADRÃO — sem seta nenhuma, nem pra cima
    nem pra baixo — e ficam sempre agrupados no topo (ver a normalização em
    carregar_conteudos()); todo conteúdo cadastrado pelo professor vem
    sempre DEPOIS de todos os nativos, e só entre eles a ordem é livre.

    Como carregar_conteudos() já garante nativos contíguos no início do
    dict, "mover" aqui é simples: reordena só a lista de dinâmicos e
    reconstrói o dict inteiro como nativos (nessa mesma ordem) + dinâmicos
    (na ordem nova) — o que também AUTO-CORRIGE qualquer bagunça antiga."""
    chaves = list(st.session_state.conteudos.keys())
    nativos = [k for k in chaves if st.session_state.conteudos[k]["tipo"] == "estatico"]
    dinamicos = [k for k in chaves if st.session_state.conteudos[k]["tipo"] != "estatico"]
    idx = dinamicos.index(cid)
    novo_idx = idx + direcao
    if not (0 <= novo_idx < len(dinamicos)):
        return
    dinamicos[idx], dinamicos[novo_idx] = dinamicos[novo_idx], dinamicos[idx]
    nova_ordem = nativos + dinamicos
    st.session_state.conteudos = {k: st.session_state.conteudos[k] for k in nova_ordem}
    salvar_conteudos(st.session_state.conteudos)


def render_gerenciar_conteudos():
    st.session_state.setdefault("editando_conteudo_id", None)
    st.session_state.setdefault("mostrar_form_conteudo", False)

    # Fica ANTES da lista de cards, não depois — pedido do Wenes (2026-09-14).
    # Faz sentido: esses dados alimentam 4 conteúdos nativos ao mesmo tempo
    # (Estatística Descritiva, Frequência, Comparando Diagramas e Planejando
    # uma Pesquisa usam a MESMA amostra, ver dados_estatistica), não é algo
    # ligado só a um card — e é a ação mais usada antes de uma aula nova.
    with st.expander("📝 Editar dados numéricos do conteúdo de Estatística"):
        dados_atuais_str = " ".join(str(x).replace('.', ',') for x in st.session_state.dados_estatistica)
        novo_input_dados = st.text_area("Dados de Estatística (separados por espaço):", value=dados_atuais_str)
        if st.button("🔄 Atualizar"):
            try:
                novos_dados = [float(x.strip().replace(',', '.')) for x in novo_input_dados.split() if x.strip()]
                if novos_dados:
                    st.session_state.dados_estatistica = novos_dados
                    salvar_dados_estatistica(novos_dados)
                    flash("Salvo com sucesso!")
                    st.rerun()
            except ValueError:
                st.error("⚠️ Formato inválido! Digite apenas números separados por espaço.")

    # Antes tinha UM título geral ("📚 Conteúdos Cadastrados") cobrindo os
    # nativos e os cadastrados juntos, o que não fazia sentido pros nativos
    # (ninguém "cadastrou" eles). Virou dois subtítulos, um por grupo — no
    # MESMO estilo de destaque (st.subheader) que aquele título tinha, e
    # reaproveitando o vocabulário já usado na barra lateral ("Matéria
    # Padrão" / "Matérias Cadastradas") — pedido do Wenes, 2026-09-14.
    nativos_em_ordem = [k for k, v in st.session_state.conteudos.items() if v["tipo"] == "estatico"]
    dinamicos_em_ordem = [k for k, v in st.session_state.conteudos.items() if v["tipo"] != "estatico"]

    def _renderizar_card_conteudo(cid):
        c = st.session_state.conteudos[cid]
        with st.container(border=True, key=f"card_conteudo_{cid}"):
            col_titulo, col_acoes = st.columns([3, 2])
            with col_titulo:
                st.markdown(f"##### {c['icone']} {c['titulo']}")
            with col_acoes:
                if c["tipo"] != "estatico":
                    with st.container(key=f"acoes_conteudo_{cid}"):
                        col_subir, col_descer, col_editar, col_excluir = st.columns(4)
                        posicao = dinamicos_em_ordem.index(cid)
                        with col_subir:
                            if st.button("▲", key=f"subir_{cid}", disabled=(posicao == 0),
                                         help="Mover para cima"):
                                mover_conteudo(cid, -1)
                                st.rerun()
                        with col_descer:
                            if st.button("▼", key=f"descer_{cid}", disabled=(posicao == len(dinamicos_em_ordem) - 1),
                                         help="Mover para baixo"):
                                mover_conteudo(cid, 1)
                                st.rerun()
                        with col_editar:
                            if st.button("✏️ Editar", key=f"edit_{cid}"):
                                st.session_state.editando_conteudo_id = cid
                                st.session_state.mostrar_form_conteudo = True
                                st.session_state.novas_secoes_teoria = [dict(s) for s in c.get("teoria", [])]
                                st.session_state.novas_missoes = [dict(m) for m in c.get("missoes", [])]
                                st.session_state["novo_titulo_conteudo"] = c["titulo"]
                                st.session_state["novo_icone_conteudo"] = c["icone"]
                                st.session_state["nova_descricao_conteudo"] = c.get("descricao", "")
                                st.rerun()
                        with col_excluir:
                            if st.button("🗑️ Excluir", key=f"del_{cid}"):
                                _dialog_confirmar_exclusao_conteudo(cid, c)

            if c.get("descricao"):
                st.caption(c["descricao"])

            badges = []
            if c["tipo"] == "estatico":
                # "Padrão", não "Nativo do sistema" — a seção logo acima já
                # se chama "Matéria Padrão"; usar uma palavra diferente aqui
                # pra dizer a MESMA coisa só confundia (apontado pelo Wenes
                # com print, 2026-09-17). Um termo só, usado em todo canto.
                badges.append('<span class="badge-conteudo badge-conteudo-tipo">⚙️ Conteúdo Padrão</span>')
            else:
                n_missoes = len(c.get("missoes", []))
                badges.append(f'<span class="badge-conteudo badge-conteudo-tipo">🧩 {n_missoes} missão(ões)</span>')
            # Total de XP do conteúdo (acertando tudo de primeira) — pedido
            # do Wenes (2026-09-17): sem isso, ele tinha que abrir cada
            # missão e somar o XP na mão pra saber quanto vale um conteúdo
            # inteiro, e errava a conta (supôs 20 XP por missão em todas,
            # quando na real varia entre 10 e 80 dependendo da missão).
            badges.append(f'<span class="badge-conteudo badge-conteudo-tipo">💯 Total {xp_maximo_de_conteudo(cid, c)} XP</span>')
            habilidades = habilidades_bncc_do_conteudo(cid, c)
            if habilidades:
                badges.append(f'<span class="badge-conteudo badge-conteudo-bncc">🎯 BNCC: {", ".join(habilidades)}</span>')
            st.markdown(" ".join(badges), unsafe_allow_html=True)
            # Legenda de cada habilidade (código + começo da descrição oficial), pra o
            # professor não ter que decorar o que significa cada código da BNCC.
            # Só as que têm descrição no banco: o código das demais já está no selo acima.
            com_descricao = [h for h in habilidades if descricao_curta_bncc(h)]
            for hab in com_descricao:
                st.caption(f"🎯 **{hab}** · {descricao_curta_bncc(hab, limite=170)}")

    if nativos_em_ordem:
        st.subheader("⚙️ Matéria Padrão")
        for cid in nativos_em_ordem:
            _renderizar_card_conteudo(cid)

    if dinamicos_em_ordem:
        st.subheader("📚 Matérias Cadastradas")
        for cid in dinamicos_em_ordem:
            _renderizar_card_conteudo(cid)

    st.markdown('<div id="ancora-form-conteudo"></div>', unsafe_allow_html=True)
    st.markdown("---")

    # O formulário (criar ou editar) só aparece quando pedido — clicar em
    # "Editar" já liga isso sozinho; pra criar do zero, precisa desse botão.
    # Antes o formulário ficava sempre visível embaixo da lista, então
    # "Cancelar" só limpava os campos em vez de fazer a caixa toda sumir —
    # confuso, parecia que tinha ficado alguma coisa pra trás esperando.
    if not st.session_state.mostrar_form_conteudo:
        if st.button("➕ Criar Novo Conteúdo"):
            st.session_state.mostrar_form_conteudo = True
            st.rerun()
        return

    editando = st.session_state.editando_conteudo_id
    if editando:
        conteudo_original = st.session_state.conteudos.get(editando, {})
        st.subheader(f"✏️ Editando: {conteudo_original.get('icone', '')} {conteudo_original.get('titulo', '')}")
        st.caption("Altere o que quiser abaixo — título, teoria, missões — e clique em Salvar. "
                   "Os campos já vieram preenchidos com o que existe hoje.")
        # Ao clicar em "Editar" na lista lá em cima, o formulário reaparece
        # aqui embaixo sem nenhum aviso — quem clicou fica sem saber que
        # precisa rolar a tela pra achar. Rola a tela sozinha até aqui, pra
        # não repetir o mesmo problema da caixa de exclusão de antes.
        components.html(
            """
            <script>
            const ancora = window.parent.document.getElementById('ancora-form-conteudo');
            if (ancora) { ancora.scrollIntoView({behavior: 'smooth', block: 'start'}); }
            </script>
            """,
            height=0,
            width=0,
        )
    else:
        st.subheader("➕ Criar Novo Conteúdo")
        st.caption("Cadastre um conteúdo de qualquer disciplina.")

    novo_titulo = st.text_input("Título do conteúdo:", key="novo_titulo_conteudo")
    col_ic, col_desc = st.columns([1, 4])
    with col_ic:
        novo_icone = st.text_input("Ícone (emoji):", value="📘", key="novo_icone_conteudo")
    with col_desc:
        nova_descricao = st.text_input("Descrição curta:", key="nova_descricao_conteudo")

    st.markdown("#### Teoria")
    st.caption("Adicione quantas seções quiser.")
    with st.expander("❔ Como formatar o texto"):
        st.markdown(
            "**Texto**\n"
            "- Negrito: `**texto**`\n"
            "- Itálico: `*texto*`\n"
            "- Sublinhado: o Markdown não tem esse comando — use negrito ou itálico pra destacar.\n"
            "- Título de sub-seção dentro do texto: `## Título`\n"
            "- Lista: uma linha por item, começando com `-`\n"
            "- Bloco destacado (exemplo, fórmula, etc.): três crases ` ``` ` antes e depois do trecho\n\n"
            "**Matemática (LaTeX)** — entre `$...$` pra ficar no meio da frase, ou `$$...$$` "
            "numa linha própria pra centralizar:\n"
            "- Fração: `$\\frac{a}{b}$`\n"
            "- Raiz: `$\\sqrt{x}$`\n"
            "- Expoente: `$x^2$`"
        )
    for i, secao in enumerate(st.session_state.novas_secoes_teoria):
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                secao["titulo"] = st.text_input(f"Título da seção {i + 1}", value=secao.get("titulo", ""), key=f"edit_titulo_secao_{i}")
                secao["texto"] = st.text_area(f"Conteúdo da seção {i + 1} (aceita markdown)", value=secao.get("texto", ""), key=f"edit_texto_secao_{i}", height=140)
            with c2:
                if st.button("🗑️ Excluir", key=f"del_secao_{i}"):
                    st.session_state.novas_secoes_teoria.pop(i)
                    st.rerun()

    with st.form("form_add_secao", clear_on_submit=True):
        titulo_secao = st.text_input("Título da seção")
        texto_secao = st.text_area("Conteúdo da seção (aceita markdown)")
        if st.form_submit_button("➕ Adicionar Seção de Teoria"):
            if titulo_secao and texto_secao:
                st.session_state.novas_secoes_teoria.append({"titulo": titulo_secao, "texto": texto_secao})
                st.rerun()
            else:
                st.error("Preencha o título e o texto da seção.")

    st.markdown("#### Missões da Trilha")
    st.caption("Adicione as perguntas do jogo.")
    for i, missao in enumerate(st.session_state.novas_missoes):
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                missao["titulo"] = st.text_input(f"Título curto da missão {i + 1}", value=missao.get("titulo", ""), key=f"edit_titulo_missao_{i}")
                missao["pergunta"] = st.text_area(f"Pergunta/desafio {i + 1}", value=missao.get("pergunta", ""), key=f"edit_pergunta_missao_{i}")
                col_r, col_t, col_p = st.columns(3)
                with col_r:
                    missao["resposta"] = st.text_input(f"Resposta correta {i + 1}", value=str(missao.get("resposta", "")), key=f"edit_resposta_missao_{i}")
                with col_t:
                    tipos = ["numero", "texto", "multipla"]
                    tipo_atual = missao.get("tipo", "numero")
                    missao["tipo"] = st.selectbox(
                        f"Tipo de resposta {i + 1}", tipos,
                        index=tipos.index(tipo_atual) if tipo_atual in tipos else 0,
                        key=f"edit_tipo_missao_{i}",
                        format_func=lambda t: {"numero": "número", "multipla": "múltipla escolha"}.get(t, t),
                    )
                with col_p:
                    missao["pontos"] = int(st.number_input(
                        f"Pontos (XP) {i + 1}", min_value=1, value=int(missao.get("pontos", 10)),
                        step=1, key=f"edit_pontos_missao_{i}",
                    ))
                # Fora de st.form, então aqui dá pra mostrar o campo só quando o
                # tipo escolhido é múltipla escolha.
                if missao["tipo"] == "multipla":
                    texto_alts = st.text_area(
                        f"Alternativas {i + 1} — uma por linha",
                        value="\n".join(missao.get("alternativas", [])),
                        key=f"edit_alts_missao_{i}",
                        help="A resposta correta precisa ser idêntica a uma destas linhas.",
                    )
                    missao["alternativas"] = [l.strip() for l in texto_alts.splitlines() if l.strip()]
                    if len(missao["alternativas"]) < 2:
                        st.warning(f"⚠️ Missão {i + 1}: múltipla escolha precisa de pelo menos duas alternativas.")
                    elif str(missao.get("resposta", "")).strip() not in missao["alternativas"]:
                        st.warning(
                            f"⚠️ Missão {i + 1}: a resposta correta \"{missao.get('resposta', '')}\" "
                            "não está entre as alternativas. O aluno não teria como acertar."
                        )
                elif "alternativas" in missao:
                    # Trocou de múltipla escolha para outro tipo: as alternativas
                    # antigas não valem mais e não devem ir para o conteudos.json.
                    del missao["alternativas"]
                missao["bncc"] = campo_habilidade_bncc(
                    f"Habilidade BNCC {i + 1} (opcional)", valor_atual=missao.get("bncc", ""),
                    chave=f"edit_bncc_missao_{i}",
                    ajuda="Habilidade da Base Nacional Comum Curricular que esta missão exercita. "
                          "Deixe em branco se não quiser mapear.",
                )
                if missao["bncc"] and descricao_curta_bncc(missao["bncc"]):
                    st.caption(carregar_habilidades_bncc()[missao["bncc"]])
            with c2:
                if st.button("🗑️ Excluir", key=f"del_missao_{i}"):
                    st.session_state.novas_missoes.pop(i)
                    st.rerun()

    with st.form("form_add_missao", clear_on_submit=True):
        titulo_missao = st.text_input("Título curto da missão")
        pergunta_missao = st.text_area(
            "Pergunta/desafio apresentado ao aluno",
            help="Para escrever cifrão, use \\$ (ex.: R\\$ 50,00). Um $ sozinho é lido como "
                 "início de fórmula matemática e o texto entre dois cifrões desaparece da tela.",
        )
        col_r, col_t, col_p = st.columns(3)
        with col_r:
            resposta_missao = st.text_input("Resposta correta")
        with col_t:
            tipo_missao = st.selectbox(
                "Tipo de resposta", ["numero", "texto", "multipla"],
                format_func=lambda t: {"numero": "número", "multipla": "múltipla escolha"}.get(t, t),
            )
        with col_p:
            pontos_missao = st.number_input("Pontos (XP)", min_value=1, value=10, step=1)
        # O campo de alternativas fica sempre visível, mesmo quando o tipo não é
        # múltipla escolha: dentro de um st.form os widgets não disparam rerun,
        # então não há como mostrá-lo só depois que o professor escolhe o tipo.
        alternativas_missao = st.text_area(
            "Alternativas (só para múltipla escolha) — uma por linha",
            placeholder="média\nmediana\nmoda",
            help="Escreva uma alternativa por linha. A \"Resposta correta\" acima precisa ser "
                 "idêntica a uma delas. Na múltipla escolha o aluno não digita nada, só escolhe, "
                 "então não erra por causa de acento ou de letra trocada.",
        )
        bncc_missao = campo_habilidade_bncc(
            "Habilidade BNCC (opcional)", chave="nova_bncc_missao",
            ajuda="Habilidade da Base Nacional Comum Curricular que esta missão exercita. "
                  "É o que permite ao Painel do Professor relatar o desempenho por habilidade.",
        )
        if st.form_submit_button("➕ Adicionar Missão"):
            alternativas = [linha.strip() for linha in alternativas_missao.splitlines() if linha.strip()]
            erro_missao = ""
            if not (titulo_missao and pergunta_missao and resposta_missao):
                erro_missao = "Preencha o título, a pergunta e a resposta correta."
            elif tipo_missao == "multipla":
                # Validado no cadastro, e não na hora da aula: uma missão de
                # múltipla escolha sem alternativas, ou cuja resposta correta não
                # está entre elas, viraria uma questão impossível de acertar —
                # e o professor só descobriria com o aluno travado na frente.
                if len(alternativas) < 2:
                    erro_missao = "Múltipla escolha precisa de pelo menos duas alternativas, uma por linha."
                elif resposta_missao.strip() not in alternativas:
                    erro_missao = ("A resposta correta precisa ser idêntica a uma das alternativas. "
                                   f"Você escreveu \"{resposta_missao.strip()}\", e as alternativas são: "
                                   + ", ".join(f'"{a}"' for a in alternativas) + ".")
            if erro_missao:
                st.error(erro_missao)
            else:
                nova_missao = {
                    "titulo": titulo_missao,
                    "pergunta": pergunta_missao,
                    "resposta": resposta_missao.strip(),
                    "tipo": tipo_missao,
                    "pontos": int(pontos_missao),
                    "bncc": bncc_missao.strip(),
                }
                if tipo_missao == "multipla":
                    nova_missao["alternativas"] = alternativas
                st.session_state.novas_missoes.append(nova_missao)
                st.rerun()

    st.markdown("---")

    def limpar_formulario_conteudo():
        st.session_state.editando_conteudo_id = None
        st.session_state.mostrar_form_conteudo = False
        st.session_state.novas_secoes_teoria = []
        st.session_state.novas_missoes = []
        for campo in ("novo_titulo_conteudo", "novo_icone_conteudo", "nova_descricao_conteudo"):
            st.session_state.pop(campo, None)

    # Colunas estreitas (não st.columns(2), que divide a largura toda ao
    # meio): aqui o formulário ocupa a página inteira, não um modal estreito
    # como nos diálogos de exclusão — com 50/50 o Cancelar ficava largado no
    # meio da tela, sem nenhuma relação visual com o Salvar (relatado pelo
    # Wenes, 2026-09-17). Os dois ficam colados, junto da ação principal.
    col_salvar, col_cancelar, _ = st.columns([1, 1, 4])
    with col_salvar:
        if st.button("💾 Salvar", type="primary", key="salvar_conteudo_btn"):
            if not novo_titulo:
                st.error("Dê um título ao conteúdo antes de salvar.")
            elif not st.session_state.novas_secoes_teoria and not st.session_state.novas_missoes:
                st.error("Adicione ao menos uma seção de teoria ou uma missão antes de salvar.")
            else:
                alvo_id = editando if editando else f"conteudo_{uuid.uuid4().hex[:8]}"
                st.session_state.conteudos[alvo_id] = {
                    "titulo": novo_titulo,
                    "icone": novo_icone or "📘",
                    "descricao": nova_descricao,
                    "tipo": "dinamico",
                    "teoria": st.session_state.novas_secoes_teoria,
                    "missoes": st.session_state.novas_missoes,
                }
                salvar_conteudos(st.session_state.conteudos)
                limpar_formulario_conteudo()
                flash("Salvo com sucesso!")
                st.rerun()
    with col_cancelar:
        if st.button("❌ Cancelar", key="cancelar_edicao_btn"):
            limpar_formulario_conteudo()
            st.rerun()


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
    # Dois números separados, não um total misturado — o Wenes achou
    # confuso um valor só somando Matéria Padrão + Matérias Cadastradas
    # (2026-09-17): sem separar, não dá pra saber quanto vem de cada grupo.
    # Cards com cor suave (ver .resumo-xp-card no CSS) em vez de
    # st.metric() puro, que ele achou feio pro painel (2026-09-17).
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

    # Seletor de conteúdo — sugestão do orientador ("Conversar com
    # orientador 02.txt", 2026-09-17): o professor escolhe a disciplina do
    # dia e vê o XP dela. Fora do form de propósito — precisa rerodar assim
    # que troca a escolha, pra atualizar o campo de meta antes de clicar
    # Salvar; widget de form só atualiza no submit, o que travaria isso.
    opcoes_conteudo = {"__catalogo__": "— Catálogo inteiro (todos os conteúdos) —"}
    opcoes_conteudo.update({cid: c["titulo"] for cid, c in st.session_state.conteudos.items()})
    opcoes_ids = list(opcoes_conteudo.keys())

    # Lembra a última escolha no PRÓPRIO config_sistema.json, não só em
    # session_state: session_state morre inteiro com um F5 de verdade (é
    # uma sessão nova pro Streamlit), então guardar só na sessão fazia a
    # escolha "sobreviver a trocar de aba" mas sumir de novo ao atualizar a
    # página — reportado pelo Wenes (2026-09-17). meta_xp já é salvo em
    # disco por esse mesmo arquivo; o foco escolhido segue o mesmo caminho.
    #
    # O widget usa key= e NÃO recebe index= — as duas coisas juntas foram a
    # causa de um bug sério, também relatado pelo Wenes (2026-09-17,
    # descrito com muito detalhe): trocar a escolha sem clicar Salvar fazia
    # a seleção "oscilar", voltando pra anterior a cada segunda troca.
    # Calcular index=... a partir de um valor que a MESMA rodada do script
    # também escreve de volta em session_state cria uma corrida — o
    # Streamlit não consegue distinguir com segurança "isso é o clique novo
    # do usuário" de "isso é só o padrão que acabei de recalcular", e às
    # vezes descarta o clique. Com key= só, o valor mora inteiramente em
    # st.session_state[key] e o Streamlit cuida de tudo sozinho, sem essa
    # corrida — é o padrão mais robusto pra widget com estado.
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
        valor_padrao_meta = int(st.session_state.config.get("meta_xp") or (xp_catalogo_hoje / 2))
    else:
        xp_referencia = xp_maximo_de_conteudo(conteudo_foco, st.session_state.conteudos[conteudo_foco])
        st.caption(f"💡 \"{opcoes_conteudo[conteudo_foco]}\" vale até **{xp_referencia} XP** — já preenchido abaixo. Reduza se quiser uma meta mais fácil.")
        valor_padrao_meta = xp_referencia

    # key inclui o conteúdo escolhido de propósito: assim, trocar a escolha
    # no seletor acima cria um widget "novo" pro Streamlit, que preenche de
    # novo com valor_padrao_meta — sem isso, o campo manteria o número
    # digitado antes mesmo depois de trocar de conteúdo (pedido do Wenes,
    # 2026-09-17: quer o campo preenchendo sozinho a cada troca, e editável
    # se ele quiser uma meta menor do que o total).
    with st.form("form_meta_xp"):
        meta_xp_input = st.number_input(
            "Meta de XP (referência pra colorir o gráfico)",
            min_value=1, step=10,
            value=int(valor_padrao_meta),
            key=f"meta_xp_input_{conteudo_foco}",
        )
        if st.form_submit_button("Salvar"):
            st.session_state.config["meta_xp"] = int(meta_xp_input)
            salvar_config(st.session_state.config)
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


# ==========================================
# 9. MENU LATERAL (NAVEGAÇÃO)
# ==========================================
# Ordem fixa, sempre os mesmos blocos, sempre nas mesmas posições:
#   cabeçalho/Início (a própria marca) > identidade (altura reservada) >
#   Matérias > Professor.
# Nada aparece e some conforme a página, e o bloco de identidade tem altura
# mínima fixa no CSS justamente pra que logar/deslogar não empurre o menu
# inteiro pra baixo — o Streamlit desenha de cima pra baixo, então qualquer
# bloco condicional acima da navegação move tudo que vem depois.
with st.sidebar:
    # Botão "🏠 Início" bem no topo, ACIMA da logo — pedido explícito do Wenes
    # (2026-09-14), mesmo já existindo um segundo caminho pro mesmo lugar (a
    # logo/título logo abaixo, também clicável). Os dois juntos não são
    # redundância por engano: é o mesmo padrão que existe em muito site/app
    # por aí (ex.: YouTube tem o logo clicável E um item "Início" à parte,
    # com ícone de casa) — reforça o mesmo destino por dois caminhos.
    if st.button("🏠  Início", key="nav_inicio", use_container_width=True,
                 type="primary" if st.session_state.pagina == PAGINA_INICIO else "secondary"):
        st.session_state.pagina = PAGINA_INICIO
        st.rerun()

    # A logo/título TAMBÉM leva pra Início ao clicar — é o segundo caminho
    # citado acima. Streamlit não deixa um st.image() disparar clique; por
    # isso quem carrega a ação é o texto do título, estilizado por CSS (ver
    # ".st-key-nav_titulo_inicio") pra não parecer um botão comum.
    with st.container(key="sidebar_cabecalho"):
        if os.path.exists(ARQUIVO_LOGO):
            st.image(ARQUIVO_LOGO, width=69)  # 69 e não 64: o SVG tem um anel cinza por fora, e com 69 o círculo azul fica do tamanho de antes
        if st.button("Trilha de Aprendizagem",
                     key="nav_titulo_inicio", use_container_width=True):
            st.session_state.pagina = PAGINA_INICIO
            st.rerun()

    with st.container(key="sidebar_identidade"):
        if st.session_state.aluno_ativo:
            perfil = perfil_atual()
            st.markdown(f"**👤 {st.session_state.aluno_ativo}**  \n🏆 {perfil['xp_total']} XP acumulados")
            if st.button("❌ Sair", use_container_width=True, key="sidebar_sair"):
                st.session_state.aluno_ativo = ""
                st.rerun()
        else:
            # "Apelido no jogo", não "Nome do Aluno": entrar com um nome
            # inventado é parte da dinâmica, não um detalhe técnico. O aluno joga
            # sem se expor quando erra, e é o professor que liga o apelido ao
            # nome real, na hora do relatório (ver 'Nomes para o relatório').
            #
            # Em st.form (2026-09-07): sem form, o texto digitado só é
            # sincronizado com o backend no blur/Enter do campo, num evento
            # separado do clique do botão — clicar em "Acessar" logo depois de
            # digitar podia disparar o rerun do botão ANTES desse sync chegar,
            # e o clique via nome_digitado vazio, sem erro nenhum na tela
            # (só um F5 — que força tudo a sincronizar de novo — resolvia). O
            # form agrupa campo e botão numa única mensagem, então o valor que
            # chega é sempre o mais atual. Custo: a legenda de erro deixa de
            # atualizar a cada tecla e passa a atualizar só ao tentar entrar
            # — a linha continua sempre presente (mesmo motivo de altura de
            # sempre), só a atualização que virou "ao enviar" em vez de "ao
            # digitar".
            with st.form("form_login_aluno", border=False):
                nome_digitado = st.text_input(
                    "🎮 Seu apelido no jogo:", placeholder="Ex.: Goku99",
                    help="Invente um apelido — não precisa ser seu nome de verdade. "
                         "Uma palavra só, letras e números.",
                ).strip()
                erro_apelido = apelido_invalido(nome_digitado) if nome_digitado else ""
                if erro_apelido:
                    st.markdown(f'<div class="apelido-aviso erro">❌ {erro_apelido}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="apelido-aviso">Uma palavra, sem espaços.</div>', unsafe_allow_html=True)
                if st.form_submit_button("✅ Acessar", use_container_width=True):
                    if nome_digitado and not erro_apelido:
                        entrar_como_aluno(nome_digitado)

    # <hr> com classe própria (não "---" cru): o <hr> padrão do Streamlit tem
    # margem maior em cima do que embaixo, então a linha ficava mais perto de
    # "Matéria Padrão" do que do "Acessar" — medido no DOM (51px acima, 32px
    # abaixo), não só impressão visual. Margem assimétrica própria (ver CSS)
    # corrige, compensando o espaço extra que o st.form do login já soma.
    st.markdown('<hr class="sidebar-divisor-identidade">', unsafe_allow_html=True)

    # --- Nível 2: as matérias. Clicar aqui ABRE a matéria (não "seleciona"
    # uma matéria pra usar num botão lá de cima) — é isso que acaba com o
    # modo escondido de antes. O progresso vai no próprio rótulo, então o
    # menu responde "onde parei em cada matéria" sem nenhum bloco extra que
    # cresça ou encolha. ---
    concluidas_por_conteudo = progresso_resumo_aluno()

    # Estatística vira UM item só no menu (Descritiva + Frequência + Leitura
    # Crítica ficam dentro do hub, ver PAGINA_ESTATISTICA_HUB) — antes eram 3
    # itens soltos competindo com Frações, Regra de Três etc., diluindo a
    # identidade de Estatística que o orientador apontou como foco original
    # do TCC (2026-09-11). Fica marcado como "ativo" também quando o aluno
    # está DENTRO de um dos 3 sub-temas, não só na tela do hub em si.
    #
    # "Matéria Padrão" / "Matérias Cadastradas": dois rótulos, não um
    # "Matérias" genérico, pra separar visualmente o conteúdo padrão do
    # sistema (Estatística, o tema da defesa do TCC) dos que o professor
    # cadastrou por conta própria — bate o olho e já dá pra distinguir os
    # dois grupos. "Cadastradas" repete a mesma palavra que o Painel do
    # Professor já usa ("📚 Conteúdos Cadastrados"), de propósito.
    st.markdown('<div class="sidebar-secao">Matéria Padrão</div>', unsafe_allow_html=True)
    total_hub = sum(obter_total_missoes(cid) for cid in IDS_ESTATISTICA_HUB)
    rotulo_hub = "📊  Estatística"
    if st.session_state.aluno_ativo and total_hub:
        feitas_hub = sum(min(concluidas_por_conteudo.get(cid, 0), obter_total_missoes(cid)) for cid in IDS_ESTATISTICA_HUB)
        rotulo_hub += "  ✓" if feitas_hub >= total_hub else f"  ·  {feitas_hub}/{total_hub}"
    ativo_hub = (
        st.session_state.pagina == PAGINA_ESTATISTICA_HUB
        or (st.session_state.pagina == PAGINA_MATERIA and st.session_state.conteudo_ativo in IDS_ESTATISTICA_HUB)
    )
    if st.button(rotulo_hub, key="nav_hub_estatistica", use_container_width=True,
                 type="primary" if ativo_hub else "secondary"):
        ir_para_hub_estatistica()

    # Fica em branco se o professor não tiver cadastrado nada ainda (o for
    # de baixo simplesmente não desenha nenhum botão) — só o rótulo aparece.
    st.markdown('<div class="sidebar-secao sidebar-secao-espacada">Matérias Cadastradas</div>', unsafe_allow_html=True)

    for cid, conteudo_info in st.session_state.conteudos.items():
        if cid in IDS_ESTATISTICA_HUB:
            continue
        rotulo = f"{conteudo_info['icone']}  {conteudo_info['titulo']}"
        total_missoes = obter_total_missoes(cid)
        if st.session_state.aluno_ativo and total_missoes:
            feitas = min(concluidas_por_conteudo.get(cid, 0), total_missoes)
            rotulo += "  ✓" if feitas >= total_missoes else f"  ·  {feitas}/{total_missoes}"
        ativo = (st.session_state.pagina == PAGINA_MATERIA and cid == st.session_state.conteudo_ativo)
        if st.button(rotulo, key=f"nav_conteudo_{cid}", use_container_width=True,
                     type="primary" if ativo else "secondary"):
            ir_para_materia(cid)

    # Mesma classe da linha entre Acessar/Matéria Padrão (ver acima): o <hr>
    # cru do Streamlit não fica com espaço igual dos dois lados sozinho.
    st.markdown('<hr class="sidebar-divisor-professor">', unsafe_allow_html=True)

    # --- Nível 1 de novo, separado: não faz parte do fluxo do aluno ---
    # O 🔓 existe porque "estar autenticado como professor" era um modo
    # escondido: dava pra continuar com o painel destravado sem nenhum sinal na
    # tela, e só descobrir isso clicando. Mesmo problema que a navegação tinha.
    rotulo_professor = "🛡️  Painel do Professor"
    if sessao_professor_ativa():
        rotulo_professor += "  🔓"
    if st.button(rotulo_professor, key="nav_professor", use_container_width=True,
                 type="primary" if st.session_state.pagina == PAGINA_PROFESSOR else "secondary"):
        st.session_state.pagina = PAGINA_PROFESSOR
        st.rerun()

    # Botão da pesquisa (formulário externo): só aparece se o professor
    # colou o endereço em Configurações. Abre em outra aba.
    url_pesquisa = st.session_state.config.get("url_pesquisa", "")
    if url_pesquisa:
        st.markdown('<hr class="sidebar-divisor-professor">', unsafe_allow_html=True)
        st.link_button("📝  Responder Pesquisa", url_pesquisa, use_container_width=True)

pagina = st.session_state.pagina
renderizar_flash_pendente()


# ==========================================
# 10. ROTEAMENTO DE PÁGINAS
# ==========================================
if pagina == PAGINA_INICIO:
    render_pagina_inicial()

elif pagina == PAGINA_ESTATISTICA_HUB:
    render_pagina_estatistica_hub()

elif pagina == PAGINA_MATERIA:
    # Se o professor excluiu a matéria que estava aberta, cai no conteúdo nativo
    # em vez de estourar KeyError.
    if st.session_state.conteudo_ativo not in st.session_state.conteudos:
        st.session_state.conteudo_ativo = ID_CONTEUDO_ESTATISTICA
    cid = st.session_state.conteudo_ativo
    conteudo = st.session_state.conteudos[cid]

    # Botão "← Voltar" em TODA matéria — sem ele, quem chegou aqui clicando
    # num cartão da Início ou no hub de Estatística só tem como sair clicando
    # de novo no menu lateral, o que nem todo aluno pensa em fazer sozinho. O
    # botão Voltar do navegador não ajuda aqui (é uma SPA, não existe "página
    # anterior" de verdade pro navegador voltar). Rótulo só "Voltar", sem
    # dizer pra onde — não precisa, é óbvio pelo lugar. Os 6 sub-temas de
    # Estatística voltam pro hub (é de lá que vieram); as demais matérias
    # (cadastradas pelo professor) voltam direto pra Início, que é o único
    # lugar de onde elas são abertas.
    if st.button("← Voltar", key="voltar_materia"):
        if cid in IDS_ESTATISTICA_HUB:
            ir_para_hub_estatistica()
        else:
            st.session_state.pagina = PAGINA_INICIO
            st.rerun()

    st.title(f"{conteudo['icone']} {conteudo['titulo']}")

    # Teoria x Missões é uma troca DENTRO da matéria (e a de maior frequência no
    # app: o aluno lê a fórmula, tenta a missão, volta na fórmula), por isso fica
    # colada no conteúdo e não no menu lateral. Dois botões em vez de
    # st.segmented_control de propósito: o segmented_control desmarca a opção
    # quando você clica nela de novo (vira None), e aqui não existe "nenhuma
    # seção selecionada". Botões também mantêm a mesma linguagem visual do menu
    # lateral (ativo = type="primary").
    col_teoria, col_missoes, _ = st.columns([1, 1, 3])
    with col_teoria:
        if st.button(ABA_TEORIA, use_container_width=True, key="aba_btn_teoria",
                     type="primary" if st.session_state.aba_materia == ABA_TEORIA else "secondary"):
            st.session_state.aba_materia = ABA_TEORIA
            st.rerun()
    with col_missoes:
        rotulo_missoes = ABA_MISSOES
        total_missoes = obter_total_missoes(cid)
        if st.session_state.aluno_ativo and total_missoes:
            feitas = min(max(progresso_atual(cid)["missao_atual"] - 1, 0), total_missoes)
            rotulo_missoes += f"  {feitas}/{total_missoes}"
        if st.button(rotulo_missoes, use_container_width=True, key="aba_btn_missoes",
                     type="primary" if st.session_state.aba_materia == ABA_MISSOES else "secondary"):
            st.session_state.aba_materia = ABA_MISSOES
            st.rerun()

    st.markdown("")

    if st.session_state.aba_materia == ABA_MISSOES:
        if not st.session_state.aluno_ativo:
            st.warning("⚠️ Olá! Escolha um apelido na barra lateral à esquerda para carregar o seu perfil e começar a ganhar XP.")
        else:
            # Selo de XP em destaque no topo da Trilha de Missões — um lugar só,
            # vale tanto pro conteúdo nativo de Estatística quanto pros
            # cadastrados pelo professor, sem duplicar em cada função de missão.
            xp_atual = perfil_atual()["xp_total"]
            st.markdown(
                f'<div class="xp-destaque-missoes">'
                f'<span class="icone">🏆</span><span class="valor">{xp_atual} XP</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if cid == ID_CONTEUDO_ESTATISTICA:
                render_missoes_estatistica()
            elif cid == ID_CONTEUDO_FREQUENCIA:
                render_missoes_frequencia()
            elif cid == ID_CONTEUDO_LEITURA_GRAFICA:
                render_missoes_leitura_grafica()
            elif cid == ID_CONTEUDO_COMPARACAO:
                render_missoes_comparacao_diagramas()
            elif cid == ID_CONTEUDO_PESQUISA_AMOSTRAL:
                render_missoes_pesquisa_amostral()
            elif cid == ID_CONTEUDO_TENDENCIA:
                render_missoes_tendencia()
            else:
                render_missoes_dinamicas(conteudo)
            # Embaixo, não em cima: é onde o olhar do aluno já está depois de
            # clicar em "Verificar Resposta" (mesma posição do "❌ Resposta
            # incorreta", que fica logo abaixo do botão). Uma versão anterior
            # mostrava isso no topo, junto do selo de XP — só visível rolando
            # a tela pra cima, o que o Wenes apontou (2026-09-14) que recriava
            # o mesmo problema de antes (informação fora de vista), só que
            # em vez de sumir rápido, ficava escondida longe do clique.
            renderizar_ultimo_resultado(cid)
    elif cid == ID_CONTEUDO_ESTATISTICA:
        render_pagina_estatistica()
    elif cid == ID_CONTEUDO_FREQUENCIA:
        render_pagina_frequencia()
    elif cid == ID_CONTEUDO_LEITURA_GRAFICA:
        render_pagina_leitura_grafica()
    elif cid == ID_CONTEUDO_COMPARACAO:
        render_pagina_comparacao_diagramas()
    elif cid == ID_CONTEUDO_PESQUISA_AMOSTRAL:
        render_pagina_pesquisa_amostral()
    elif cid == ID_CONTEUDO_TENDENCIA:
        render_pagina_tendencia()
    else:
        render_pagina_conteudo_dinamico(conteudo)

elif pagina == PAGINA_PROFESSOR:
    # "← Voltar" pra Início — diferente de "🚪 Sair" mais abaixo:
    # Voltar só troca de tela, sem encerrar a sessão do professor (se
    # estiver autenticado, continua autenticado ao clicar em Estatística ou
    # Painel do Professor de novo, dentro dos 30 min); Sair encerra de
    # propósito, pra passar o computador pra um aluno com segurança.
    if st.button("← Voltar", key="voltar_professor"):
        st.session_state.pagina = PAGINA_INICIO
        st.rerun()

    st.title("🛡️ Painel do Professor")

    if not sessao_professor_ativa():
        st.warning("🔒 Esta área é restrita ao professor. Digite a senha para continuar.")
        senha_digitada = st.text_input("Senha:", type="password", key="senha_professor_input")
        if st.button("🔓 Entrar"):
            if senha_correta(senha_digitada, st.session_state.config):
                abrir_sessao_professor()
                st.rerun()
            else:
                st.error("❌ Senha incorreta.")
    else:
        # Renova o prazo a cada uso do painel: o tempo passa a contar do último
        # uso, não do login, então a sessão não expira no meio de um cadastro.
        abrir_sessao_professor()
        _, colB = st.columns([4, 1])
        with colB:
            # Empurra o botão pra borda direita SEM esticar ele — usar
            # use_container_width=True (tentativa anterior) alargava o botão
            # até preencher a coluna inteira, o que não é a mesma coisa que
            # MOVER um botão de tamanho normal pra direita (Wenes, 2026-09-14
            # apontou a diferença). O container vira flex com
            # justify-content:flex-end, que empurra o filho (o botão, do
            # próprio tamanho) pra ponta, sem mudar a largura dele.
            with st.container(key="acao_sair_professor"):
                if st.button("🚪 Sair"):
                    encerrar_sessao_professor()
                    st.rerun()

        # Botões em vez de st.tabs(): a seleção do st.tabs() é client-side e
        # volta pra primeira aba sozinha quando a árvore de elementos muda —
        # e é exatamente o que acontece aqui (o formulário de editar
        # conteúdo desaparece da tela ao salvar). Relatado pelo Wenes
        # (2026-09-17): editou um conteúdo, salvou, e caiu de volta em
        # "Visão Geral" em vez de continuar em "Gerenciar Conteúdos". Mesmo
        # padrão e mesmo motivo do toggle Teoria/Missões (ver ir_para_materia).
        col_ab1, col_ab2, col_ab3 = st.columns(3)
        with col_ab1:
            if st.button(ABA_PROFESSOR_VISAO, use_container_width=True, key="aba_btn_professor_visao",
                         type="primary" if st.session_state.aba_professor == ABA_PROFESSOR_VISAO else "secondary"):
                st.session_state.aba_professor = ABA_PROFESSOR_VISAO
                st.rerun()
        with col_ab2:
            if st.button(ABA_PROFESSOR_CONTEUDOS, use_container_width=True, key="aba_btn_professor_conteudos",
                         type="primary" if st.session_state.aba_professor == ABA_PROFESSOR_CONTEUDOS else "secondary"):
                st.session_state.aba_professor = ABA_PROFESSOR_CONTEUDOS
                st.rerun()
        with col_ab3:
            if st.button(ABA_PROFESSOR_CONFIG, use_container_width=True, key="aba_btn_professor_config",
                         type="primary" if st.session_state.aba_professor == ABA_PROFESSOR_CONFIG else "secondary"):
                st.session_state.aba_professor = ABA_PROFESSOR_CONFIG
                st.rerun()

        st.markdown("")
        if st.session_state.aba_professor == ABA_PROFESSOR_VISAO:
            render_desempenho_turma()
        elif st.session_state.aba_professor == ABA_PROFESSOR_CONTEUDOS:
            render_gerenciar_conteudos()
        else:
            render_configuracoes()


# ==========================================
# 11. AUTO-RUN DO STREAMLIT
# ==========================================
if __name__ == '__main__':
    if not os.environ.get("RODANDO_STREAMLIT"):
        os.environ["RODANDO_STREAMLIT"] = "1"
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
