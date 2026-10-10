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


"""
Ancora o diretório de trabalho na pasta deste arquivo, para que os caminhos relativos (logo, banner,
bancos) funcionem de onde quer que o script seja iniciado.
"""
os.chdir(os.path.dirname(os.path.abspath(__file__)))


"""
==========================================
1. CONFIGURAÇÃO E ARQUIVOS DE MEMÓRIA
==========================================
As artes ficam no topo porque st.set_page_config() precisa do caminho da logo e deve ser a primeira
chamada st.* do script.

imagens/ guarda as artes do projeto e fonts/ as fontes. static/ é diferente: o Streamlit serve essa
pasta em app/static/ (enableStaticServing em .streamlit/config.toml) e o manifest e os ícones do PWA
dependem desse caminho, então ela não deve ser movida.
"""
ARQUIVO_LOGO = "static/logo.svg"                 # opcional: marca quadrada do projeto em vetor, um arquivo só para barra lateral, ícone da aba e ícone do app instalado (por isso fica em static/, que o manifest alcança por URL)
ARQUIVO_BANNER = "imagens/banner.svg"            # opcional: arte pronta para o topo da Página Inicial (ideal 1200x400px ou 1500x500px, formato "capa" tipo Facebook/Twitter — pode já vir com a logo embutida, feita no Photoshop)
ARQUIVO_CABECALHO = "imagens/cabecalho.png"      # opcional: timbre institucional no topo de toda página do relatório em PDF. Tem que ser PNG (o fpdf2 não embute PDF); exportar com ~2008px de largura = 300 DPI nos 170mm da página. A altura é livre, o código lê a proporção do arquivo

st.set_page_config(
    page_title="Trilha de Aprendizagem",
    page_icon=ARQUIVO_LOGO if os.path.exists(ARQUIVO_LOGO) else "🎓",
    layout="wide"
)


def _injetar_manifest_pwa():
    """
    Troca o <link rel="manifest"> e o <link rel="apple-touch-icon"> do <head> da página (via
    window.parent, pois o componente roda em um iframe) pelos do projeto, servidos como arquivos em
    /static (ver enableStaticServing em .streamlit/config.toml).

    O Streamlit já injeta essas tags com valores genéricos, então é preciso localizar a tag
    existente e trocar o href. O href deve ser uma URL de arquivo real: URIs "data:" não são aceitas
    de forma confiável em ícones de manifest e o Android recai no ícone genérico.
    """
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
    """
    Remove espaços do campo de apelido assim que aparecem, digitando, colando ou em qualquer
    teclado, inclusive o virtual do celular.

    Usa o evento 'input', que dispara sempre que o valor do campo muda (ao contrário de 'keydown',
    que muitos teclados virtuais não emitem). A checagem `if (limpo === el.value) return` evita laço
    infinito: o valor só é reescrito quando há espaço a remover.

    É conveniência de digitação, não validação: apelido_invalido() continua valendo no servidor.
    """
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
    """
    Mostra o aviso nativo do navegador ('Sair do site?') ao fechar, atualizar ou sair da página.

    O app é uma SPA: o conteúdo muda via WebSocket dentro de uma única página, então o botão Voltar
    do navegador sai do app sem aviso. O texto do aviso é fixo (definido pelo navegador); só é
    possível ligá-lo ou desligá-lo.
    """
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
    """
    Permite rolar a página normalmente quando o mouse está sobre um gráfico (Altair/Vega-Lite).

    O wrapper .stVegaLiteChart do Streamlit intercepta o scroll sobre qualquer gráfico, mesmo sem
    zoom/pan ligado. Como a captura ocorre em um listener interno, a solução é ouvir o evento de
    scroll na fase de captura (que roda antes) e, se o alvo estiver dentro de um gráfico, rolar
    manualmente a área principal (.stMain).
    """
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
    """
    Faz a logo também levar à Início ao clicar, como o título.

    st.image() não aceita on_click nem link. O código escuta cliques no cabeçalho
    (".st-key-sidebar_cabecalho") e, se não foi um clique direto no botão do título, simula um
    clique nele, reaproveitando a navegação existente.
    """
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

"""
Pasta dos dados que mudam durante o uso (banco de alunos, conteúdos, configuração). Localmente é a
pasta do projeto; no Fly.io aponta para o volume persistente via TRILHA_DIR_DADOS=/data, pois só o
volume sobrevive a reinícios e publicações.
"""
DIR_DADOS = os.environ.get("TRILHA_DIR_DADOS", ".")
os.makedirs(DIR_DADOS, exist_ok=True)

ARQUIVO_DADOS_ESTATISTICA = os.path.join(DIR_DADOS, "dados_turma.json")   # amostra numérica usada pelo conteúdo nativo de Estatística
ARQUIVO_ALUNOS = os.path.join(DIR_DADOS, "banco_alunos.json")             # formato antigo (só lido uma vez, pra migrar pro SQLite abaixo)
ARQUIVO_ALUNOS_DB = os.path.join(DIR_DADOS, "banco_alunos.db")            # progresso dos alunos (SQLite — suporta vários alunos salvando ao mesmo tempo sem corromper dados)
ARQUIVO_CONTEUDOS = os.path.join(DIR_DADOS, "conteudos.json")             # conteúdos cadastrados (nativos + criados pelo professor)
ARQUIVO_CONFIG = os.path.join(DIR_DADOS, "config_sistema.json")           # configurações gerais (senha do professor)

SENHA_PADRAO_PROFESSOR = "123"

"""
Cores suaves dos cartões de conteúdo, usadas em ciclo (ver CSS .cartao-cor-*).
"""
PALETA_CORES_CARTAO = ["azul", "roxo", "rosa", "amarelo", "verde", "ciano"]

ID_CONTEUDO_ESTATISTICA = "estatistica"                    # id fixo do conteúdo nativo do sistema
ID_CONTEUDO_FREQUENCIA = "estatistica_frequencia"          # id fixo do 2º conteúdo nativo (EM13MAT408, reusa os mesmos dados)
ID_CONTEUDO_LEITURA_GRAFICA = "estatistica_leitura_grafica"  # id fixo do 3º conteúdo nativo (EM13MAT102, cenário fixo)
ID_CONTEUDO_COMPARACAO = "estatistica_comparacao_diagramas"  # id fixo do 4º conteúdo nativo (EM13MAT409, reusa os mesmos dados)
ID_CONTEUDO_PESQUISA_AMOSTRAL = "estatistica_pesquisa_amostral"  # id fixo do 5º conteúdo nativo (EM13MAT202, decisões de planejamento)
ID_CONTEUDO_TENDENCIA = "estatistica_tendencia"  # id fixo do 6º conteúdo nativo (EM13MAT510, cenário próprio — não usa dados_estatistica)

"""
Os 3 conteúdos nativos de Estatística aparecem como um único item no menu e na Início (ver
PAGINA_ESTATISTICA_HUB). Cada um segue sendo um conteúdo independente (progresso, XP e BNCC
separados); o agrupamento é só de navegação.
"""
IDS_ESTATISTICA_HUB = [ID_CONTEUDO_ESTATISTICA, ID_CONTEUDO_FREQUENCIA, ID_CONTEUDO_LEITURA_GRAFICA, ID_CONTEUDO_COMPARACAO, ID_CONTEUDO_PESQUISA_AMOSTRAL, ID_CONTEUDO_TENDENCIA]

"""
Número de faixas da tabela de frequência; as faixas vêm do menor e do maior valor da amostra (ver
calcular_frequencia).
"""
FREQ_N_FAIXAS = 5

LARGURA_GRAFICO = 380

"""
Cenário fixo do Caso 1 (eixo cortado) de Leitura Crítica de Gráficos. A habilidade EM13MAT102 trata
de gráficos divulgados na mídia, então os números são um exemplo ilustrativo, escolhido para que uma
diferença real pequena pareça grande no gráfico manipulado.
"""
LEITURA_CASO1_CATEGORIAS = ["Produto A", "Produto B"]
LEITURA_CASO1_VALORES = [48, 50]
LEITURA_CASO1_EIXO_CORTADO = 45

"""
Cenário fixo de "Relação entre Duas Variáveis" (EM13MAT510). A habilidade exige duas variáveis
numéricas por item, e os dados nativos guardam só uma lista, então o conteúdo usa um exemplo
ilustrativo fixo.
"""
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
    """
    Nativos agrupados no topo, na ordem de IDS_ESTATISTICA_HUB, como ponto de partida.
    mover_conteudo() permite reordenar qualquer card depois.
    """
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


"""
---------- Banco de alunos (SQLite) ----------
Usa SQLite porque vários alunos respondem ao mesmo tempo: cada um grava só a própria linha
(UPDATE/INSERT pontual), sem reescrever um arquivo inteiro e sem sobrescrever o progresso de outro.
"""
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
        """
        "erros" é o total do conteúdo, usado no relatório. "erros_missao_atual" é zerado ao avançar
        de missão e alimenta o desconto de XP por tentativa (ver calcular_xp_por_desempenho).
        """
        colunas_progresso = {row["name"] for row in conn.execute("PRAGMA table_info(progresso)")}
        if "erros_missao_atual" not in colunas_progresso:
            conn.execute("ALTER TABLE progresso ADD COLUMN erros_missao_atual INTEGER NOT NULL DEFAULT 0")
        """
        "respostas" guarda {"1": "8", "2": "61.7", ...}: a resposta dada em cada missão concluída,
        para exibi-la em qualquer sessão (o estado da sessão do navegador não persiste).
        """
        if "respostas" not in colunas_progresso:
            conn.execute("ALTER TABLE progresso ADD COLUMN respostas TEXT NOT NULL DEFAULT '{}'")
        """
        Nome exibido no relatório ("João Batista"), separado do "nome" de login ("Goku99"). "nome" é
        a chave primária que liga o aluno ao progresso, então renomeá-lo perderia o vínculo. Esta
        coluna é só de exibição e nunca é usada em buscas.
        """
        colunas_alunos = {row["name"] for row in conn.execute("PRAGMA table_info(alunos)")}
        if "nome_relatorio" not in colunas_alunos:
            conn.execute("ALTER TABLE alunos ADD COLUMN nome_relatorio TEXT NOT NULL DEFAULT ''")
        """
        Contador de acessos: uma linha por dia com quantas vezes o app foi aberto (cada sessão nova
        do navegador conta uma vez). Guarda só o número, sem IP, aparelho ou identificação.
        """
        conn.execute("""
            CREATE TABLE IF NOT EXISTS acessos (
                dia TEXT PRIMARY KEY,
                total INTEGER NOT NULL DEFAULT 0
            )
        """)
        """
        Uma linha por tentativa de resposta (acerto ou erro). Alimenta o acerto por aluno em cada
        habilidade do Painel do Professor, que não pode ser derivado de missao_atual (só indica até
        onde o aluno chegou).
        """
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
    """
    Data de hoje no horário de Brasília (UTC-3). O servidor do Fly.io usa UTC, então date.today()
    trocaria de dia às 21h.
    """
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
    """
    Importa o banco_alunos.json antigo para o SQLite, uma única vez (se o banco novo estiver vazio e
    o arquivo existir).
    """
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
            # Compatibilidade com um formato de dados mais antigo (só Estatística, sem progresso por conteúdo).
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
    """
    Lê o estado atual de todos os alunos direto do banco, para o Painel do Professor refletir a
    turma em tempo real.
    """
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


"""
 ==========================================
2. ESTADO DA SESSÃO
 ==========================================
"""
inicializar_banco_db()
migrar_json_para_sqlite_se_necessario()
registrar_acesso_se_novo()

"""
A navegação tem um único eixo: 'pagina' indica onde o aluno está. 'conteudo_ativo' só tem
significado quando pagina == PAGINA_MATERIA, e 'aba_materia' só existe dentro de uma matéria. Isso
evita estados sem sentido (por exemplo, Início + uma matéria).
"""
PAGINA_INICIO = "inicio"
PAGINA_MATERIA = "materia"
PAGINA_PROFESSOR = "professor"
PAGINA_ESTATISTICA_HUB = "estatistica_hub"  # vitrine com os 3 sub-temas de Estatística (ver IDS_ESTATISTICA_HUB)

ABA_TEORIA = "📖 Teoria"
ABA_MISSOES = "🎮 Missões"

ABA_PROFESSOR_VISAO = "📊 Visão Geral"
ABA_PROFESSOR_CONTEUDOS = "➕ Gerenciar Conteúdos"
ABA_PROFESSOR_CONFIG = "⚙️ Configurações"

"""
A sessão do professor expira após esse tempo sem uso do painel (cada renderização do painel
autenticado renova o prazo). Professor e aluno compartilham a mesma sessão do navegador (computador
da sala), então um painel destravado esquecido expõe notas, exclusão de alunos e troca de senha.
"""
MINUTOS_SESSAO_PROFESSOR = 30

if 'conteudos' not in st.session_state: st.session_state.conteudos = carregar_conteudos()
if 'config' not in st.session_state: st.session_state.config = carregar_config()
if 'dados_estatistica' not in st.session_state: st.session_state.dados_estatistica = carregar_dados_estatistica()
if 'aluno_ativo' not in st.session_state: st.session_state.aluno_ativo = ""
if 'conteudo_ativo' not in st.session_state: st.session_state.conteudo_ativo = ID_CONTEUDO_ESTATISTICA
"""
Guarda o instante em que a sessão expira em vez de um booleano 'logado', para que a autenticação
sempre tenha prazo. 0.0 = sem sessão.
"""
if 'professor_auth_expira_em' not in st.session_state: st.session_state.professor_auth_expira_em = 0.0
if 'pagina' not in st.session_state: st.session_state.pagina = PAGINA_INICIO
if 'aba_materia' not in st.session_state: st.session_state.aba_materia = ABA_TEORIA
if 'aba_professor' not in st.session_state: st.session_state.aba_professor = ABA_PROFESSOR_VISAO
if 'novas_secoes_teoria' not in st.session_state: st.session_state.novas_secoes_teoria = []
if 'novas_missoes' not in st.session_state: st.session_state.novas_missoes = []


def sessao_professor_ativa():
    return time.time() < st.session_state.professor_auth_expira_em

def abrir_sessao_professor():
    """
    Também renova o prazo enquanto o painel está em uso, contando o tempo a partir do último uso.
    """
    st.session_state.professor_auth_expira_em = time.time() + MINUTOS_SESSAO_PROFESSOR * 60

def encerrar_sessao_professor():
    st.session_state.professor_auth_expira_em = 0.0

TAMANHO_MIN_APELIDO = 2
TAMANHO_MAX_APELIDO = 20


def apelido_invalido(apelido):
    """
    Retorna a mensagem de erro do apelido, ou "" se for válido.

    Regra: uma palavra, só letras e números. str.isalnum() cobre isso e aceita acentos ("João"), por
    isso não se usa regex.

    O apelido é a chave primária do aluno: um espaço faria "Ana Paula" e "AnaPaula" virarem dois
    perfis. O limite de caracteres também protege a coluna 'Login' do relatório em PDF (38 mm).
    """
    if len(apelido) < TAMANHO_MIN_APELIDO:
        return f"Use pelo menos {TAMANHO_MIN_APELIDO} caracteres."
    if len(apelido) > TAMANHO_MAX_APELIDO:
        return f"Use no máximo {TAMANHO_MAX_APELIDO} caracteres."
    if not apelido.isalnum():
        return "Só letras e números, sem espaços."
    return ""


def entrar_como_aluno(nome):
    """
    Entrar como aluno encerra a sessão do professor. Os dois papéis compartilham a mesma sessão do
    navegador, então sem isso o aluno herdaria o painel destravado. Também sai da página do
    professor, para não mostrar uma tela de senha inesperada.
    """
    carregar_perfil_aluno(nome)
    encerrar_sessao_professor()
    if st.session_state.pagina == PAGINA_PROFESSOR:
        st.session_state.pagina = PAGINA_INICIO
    st.rerun()

def ir_para_materia(cid, aba=ABA_TEORIA):
    """
    Caminho único para abrir uma matéria, usado pelo menu lateral e pelos cartões da Início e do hub
    de Estatística, para que todos cheguem ao mesmo estado.
    """
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
        """
        Recoloca as respostas salvas em st.session_state, de onde o código lê o valor exibido em "✅
        Missão N Concluída! (Resposta: ...)" (ver verificar_resposta). Só preenche o que ainda não
        está em memória, para não sobrescrever uma resposta mais recente da mesma sessão.
        """
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

"""
Mapeamento das missões dos conteúdos nativos para habilidades da BNCC (um dicionário por conteúdo,
indexado pelo id). Fica no código porque essas missões não estão em conteudos.json.

- Estatística Descritiva (10 missões): EM13MAT316, medidas de tendência central e de dispersão.
- Tabela e Gráfico de Frequência (FREQ_N_FAIXAS+3): EM13MAT408, tabelas e gráficos de frequência.
  Não confundir com EM13MAT406 (linguagem de programação).
- Leitura Crítica de Gráficos (8): EM13MAT102, análise de gráficos e amostras divulgados na mídia.
- Comparando Diagramas (6): EM13MAT409, comparação de diagramas (histograma, box-plot, ramos e
  folhas).
- Planejando uma Pesquisa (6): EM13MAT202, planejamento de pesquisa amostral. Como o app não coleta
  dado real, a sequência é de decisões (população x amostra, tamanho, conteúdo do relatório).
- Relação entre Duas Variáveis (6): EM13MAT510, reta de tendência para descrever e prever relações.

Só estas habilidades são definidas no código. Nos demais conteúdos, o professor preenche o campo
livre do cadastro consultando a BNCC (http://basenacionalcomum.mec.gov.br/), pois um código errado
no relatório é pior que nenhum.
"""
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
        # Rótulo com a descrição inteira, pois o Streamlit só pesquisa dentro do rótulo.
        format_func=lambda c: f"{c} · {habilidades[c]}" if c in habilidades else c,
        placeholder="Digite o código ou uma palavra da habilidade",
    )
    return (escolhida or "").strip()


def habilidades_bncc_do_conteudo(cid, c):
    """
    Códigos BNCC (sem repetição, ordenados) usados pelas missões de um conteúdo, nativo ou
    cadastrado. Lista vazia se nenhuma missão foi mapeada. Usado só no Painel do Professor
    (planejamento curricular).
    """
    if cid in BNCC_MISSOES_NATIVAS:
        return sorted(set(BNCC_MISSOES_NATIVAS[cid].values()))
    codigos = {str(m.get("bncc", "")).strip() for m in c.get("missoes", [])}
    codigos.discard("")
    return sorted(codigos)


def desempenho_por_bncc(alunos, conteudo_id=None):
    """
    Agrega o progresso da turma por habilidade da BNCC (de um conteúdo, se conteudo_id for dado).

    Retorna [{Habilidade, Missões, Conclusões, Possíveis, % Concluído}]: 'Conclusões' conta cada par
    (aluno, missão concluída) das missões com aquela habilidade, e 'Possíveis' é o total se todos
    concluíssem tudo.

    O banco guarda onde o aluno parou (missao_atual) e o total de erros, não o acerto de cada
    missão. 'Concluída' significa 'o aluno passou por ela', o que na trilha só ocorre após acertar;
    não equivale a 'acertou de primeira'.
    """
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


"""
Total de missões de cada conteúdo nativo. Como as missões são funções Python (ver bloco 7) e não uma
lista, o total fica em um dicionário por conteúdo, em vez de supor uma quantidade igual para todos.
"""
TOTAL_MISSOES_NATIVAS = {
    ID_CONTEUDO_ESTATISTICA: 10,
    ID_CONTEUDO_FREQUENCIA: FREQ_N_FAIXAS + 3,  # 1 por faixa + total + freq. relativa + gráfico
    ID_CONTEUDO_LEITURA_GRAFICA: 8,  # 4 missões no Caso 1 (escala) + 4 no Caso 2 (amostra)
    ID_CONTEUDO_COMPARACAO: 6,
    ID_CONTEUDO_PESQUISA_AMOSTRAL: 6,
    ID_CONTEUDO_TENDENCIA: 6,
}

"""
XP máximo de cada conteúdo nativo, acertando tudo de primeira. Os pontos de cada missão estão como
argumento em cada chamada de verificar_resposta(...), não em uma tabela; se o XP de alguma missão
mudar, os totais abaixo precisam ser recalculados à mão:
   Estatística Descritiva: 10+20+30+10+10+20+40+40+60+80 = 320
   Frequência:              20*5 + 20 + 30 + 20           = 170
   Leitura Crítica:         20+20+20+30 + 20+20+20+30     = 180
   Comparando Diagramas:    20+30+30+20+20+30             = 150
   Planejando uma Pesquisa: 20+20+20+20+20+30             = 130
   Relação entre Duas Variáveis: 20+20+20+30+30+30        = 150
"""
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
    """
    XP máximo de um conteúdo, acertando tudo de primeira: nativo (tabela acima) ou cadastrado (soma
    o "Pontos (XP)" de cada missão). Usado no badge "Total X XP" de cada card (Gerenciar Conteúdos)
    e no seletor de "Meta de XP" em Configurações.
    """
    if cid in XP_MAXIMO_POR_CONTEUDO_NATIVO:
        return XP_MAXIMO_POR_CONTEUDO_NATIVO[cid]
    return sum(m.get("pontos", 10) for m in c.get("missoes", []))


def xp_maximo_catalogo_atual():
    """
    (nativo, cadastrado, total): XP máximo de todo o catálogo atual, separado por grupo. É
    recalculado a cada chamada, então acompanha novos conteúdos. Aparece em Configurações como
    referência para definir a Meta de XP.
    """
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
    """
    [(apelido, xp)] dos alunos com mais XP, em ordem decrescente.

    Consulta enxuta (só nome e xp_total, ordenada e limitada pelo SQLite) porque o placar recarrega
    a cada poucos segundos no navegador de cada aluno (ver render_placar_turma) e roda muito mais
    vezes que o resto do app.
    """
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
    """
    {conteudo_id: missoes_concluidas} do aluno logado, em uma única consulta. O menu lateral mostra
    o progresso de todas as matérias e a Trilha de Missões faz rerun a cada resposta; consultar
    matéria por matéria abriria uma conexão para cada uma.
    """
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
    """
    missao_atual aponta pra PRÓXIMA missão a responder (começa em 1), então o que já foi concluído é
    sempre missao_atual - 1.
    """
    return {linha["conteudo_id"]: max(linha["missao_atual"] - 1, 0) for linha in linhas}


"""
 ==========================================
3. ESTÉTICA CSS
 ==========================================
"""
st.markdown("""
<style>
    .stMainBlockContainer {
        max-width: 870px;
        padding-left: 2rem;
        padding-right: 2rem;
        margin-left: auto;
        margin-right: auto;
        /* O Streamlit reserva 96px de padding-top por padrão para a barra flutuante (Deploy/menu).
           Aqui a barra é baixa e o conteúdo já tem título, então o espaço é reduzido para 60px, sem
           encostar no ícone de abrir/fechar a barra lateral. */
        padding-top: 60px;
    }

    /* Esconde só o botão "Deploy", não a barra inteira; o menu "⋮" continua visível para trocar o
       tema. Esconder a barra toda (`[data-testid="stHeader"]`) esconderia também o botão de reabrir
       a barra lateral (`stExpandSidebarButton`), que fica dentro dela. */
    [data-testid="stAppDeployButton"] {
        display: none;
    }

    /* Cada bloco invisível (os components.html(..., height=0) que injetam JS e o próprio <style>)
       ocupa uma vaga na lista vertical, e o gap de 16px entre itens conta mesmo com altura zero,
       somando espaço vazio no topo. display:none remove esses itens da lista sem gap; um <style>
       escondido continua valendo normalmente. */
    .stElementContainer:has([data-testid="stIFrame"]),
    .stElementContainer:has(style) {
        display: none;
    }

    .metric-card { background-color: #ffffff; border-left: 5px solid #1e40af; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 15px; }
    .metric-title { color: #64748b; font-size: 14px; font-weight: 700; text-transform: uppercase; }
    .metric-value { color: #1e3a8a; font-size: 28px; font-weight: 800; margin-top: 5px; }
    .gamification-box { background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: white; padding: 15px 20px; border-radius: 10px; font-size: 16px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3); }
    /* Regra sem uso no app (.gamification-box); pode ser removida. */

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

    /* O tema claro/escuro pode ser trocado dentro do app (menu ⋮ > Settings), independente do tema
       do sistema, então "@media (prefers-color-scheme)" não detecta a troca. Em vez de detectar o
       tema, usa rgba() semitransparente, que tinge o fundo existente e se adapta sozinho (opacidade
       calibrada para ~#f0f2f6 no claro e ~#262730 no escuro). Sem "color" no texto, ele herda a cor
       do tema. */
    .home-step-card {
        background-color: rgba(148, 163, 184, 0.16); border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 12px;
        padding: 18px; height: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        margin-bottom: 16px;
    }
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
        font-variant-numeric: tabular-nums;  
        font-weight: 700;
        color: #16a34a;
    }

    .home-step-numero { color: #3b82f6; font-size: 13px; font-weight: 800; text-transform: uppercase; }
    .home-step-titulo { font-size: 17px; font-weight: 700; margin: 4px 0 6px 0; }
    .home-step-texto { opacity: 0.75; font-size: 14px; }

    /* Cartões com borda (st.container(border=True)) em colunas lado a lado: o Streamlit estica a
       coluna via flexbox para acompanhar a mais alta, então "height: 100%" não basta; é preciso
       flex-grow para o cartão ocupar o espaço extra e todos ficarem com a mesma altura. */
    div[data-testid="stColumn"] div[data-testid="stLayoutWrapper"] {
        flex-grow: 1;
    }
    div[data-testid="stColumn"] div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] {
        height: 100%;
    }

    [class*="_cor_azul"]    { background-color: rgba(59, 130, 246, 0.12) !important; border-color: rgba(59, 130, 246, 0.4) !important; }
    [class*="_cor_roxo"]    { background-color: rgba(168, 85, 247, 0.12) !important; border-color: rgba(168, 85, 247, 0.4) !important; }
    [class*="_cor_rosa"]    { background-color: rgba(236, 72, 153, 0.12) !important; border-color: rgba(236, 72, 153, 0.4) !important; }
    [class*="_cor_amarelo"] { background-color: rgba(245, 158, 11, 0.14) !important; border-color: rgba(245, 158, 11, 0.45) !important; }
    [class*="_cor_verde"]   { background-color: rgba(16, 185, 129, 0.12) !important; border-color: rgba(16, 185, 129, 0.4) !important; }
    [class*="_cor_ciano"]   { background-color: rgba(6, 182, 212, 0.12) !important; border-color: rgba(6, 182, 212, 0.4) !important; }

    div[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p {
        font-size: 20px !important;
        font-weight: 600 !important;
    }

    h1 {
        font-size: 28px !important;
        font-weight: 600 !important;
    }

    [class*="_cor_"] h4 {
        font-size: 17px !important;
        font-weight: 700 !important;
    }

    /* Os cartões "Como funciona" usam st.markdown com HTML (.home-step-card), então a regra de
       altura igual acima (stLayoutWrapper) não os alcança. stVerticalBlock/stColumn já esticam até
       o mais alto do grupo, mas o stElementContainer interno só ocupa esse espaço extra com
       flex-grow. :has() limita a regra aos cartões com .home-step-card. */
    div[data-testid="stElementContainer"]:has(.home-step-card) {
        flex-grow: 1;
        display: flex;
    }
    div[data-testid="stElementContainer"]:has(.home-step-card) [data-testid="stMarkdown"],
    div[data-testid="stElementContainer"]:has(.home-step-card) [data-testid="stMarkdown"] > div,
    div[data-testid="stElementContainer"]:has(.home-step-card) [data-testid="stMarkdownContainer"] {
        height: 100%;
    }

    div[class*="st-key-card_conteudo_"] {
        margin-bottom: 12px;
    }

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
    /* Em tela estreita (celular), st.columns empilha os 3 cards e eles ficavam colados. O
       stMarkdownContainer tem margin-bottom: -16px por padrão; empilhado, essa margem negativa
       consome o row-gap vertical entre as colunas. Zerá-la só nas colunas com .resumo-xp-card
       devolve o espaçamento sem afetar o resto do app. */
    div[data-testid="stColumn"]:has(.resumo-xp-card) div[data-testid="stMarkdownContainer"] {
        margin-bottom: 0 !important;
    }
    .resumo-xp-nativo { background: #ecfdf5; }
    .resumo-xp-nativo .rotulo, .resumo-xp-nativo .valor { color: #047857; }
    .resumo-xp-cadastrado { background: #f0f9ff; }
    .resumo-xp-cadastrado .rotulo, .resumo-xp-cadastrado .valor { color: #0284c7; }
    .resumo-xp-total { background: #f1f5f9; }
    .resumo-xp-total .rotulo, .resumo-xp-total .valor { color: #334155; }

    /* Pop-up de "Salvo com sucesso" (ver renderizar_flash_pendente): fixo no canto superior
       direito, por cima de tudo, para aparecer mesmo quando o formulário é longo e a mensagem
       ficaria fora da tela. st.toast() não funciona neste ambiente. É pequeno, não bloqueia cliques
       e some sozinho em 3s por animação CSS (st.markdown não executa <script>, então não há timer
       em JS). */
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

    div[class*="st-key-acoes_conteudo_"] div[data-testid="stHorizontalBlock"] {
        gap: 8px !important;
        justify-content: flex-end;
    }
    div[class*="st-key-acoes_conteudo_"] div[data-testid="stColumn"] {
        width: auto !important;
        flex: 0 0 auto !important;
    }
    /* Em tela estreita (celular), o Streamlit empilha qualquer st.columns() e força min-width:
       calc(100% - 24px) em cada coluna, o que quebrava essa fileira de botões. A correção mantém a
       linha horizontal (flex-wrap: nowrap) e zera o min-width, que prevalece sobre width:auto no
       flexbox. */
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

    /* Botão "Sair" do Painel do Professor: empurra para a borda direita da coluna sem esticar. O
       container do Streamlit já é flex-direction: column, então o alinhamento horizontal é feito
       por align-items (justify-content atuaria no eixo vertical). O filho direto vem com
       width:100%, então a largura também é travada no tamanho do conteúdo. */
    div[class*="st-key-acao_sair_professor"] {
        display: flex;
        align-items: flex-end;
    }
    div[class*="st-key-acao_sair_professor"] > div {
        width: fit-content !important;
    }

    /* Sobe o conteúdo da barra lateral (Início e abaixo) ~19px. O espaço de origem é o
       margin-bottom:16px do cabeçalho do Streamlit (ícone de recolher a barra); como esse cabeçalho
       não pode ser alterado sem cortar o ícone, o ajuste é uma margem negativa no bloco logo
       abaixo. */
    div[data-testid="stSidebarUserContent"] {
        margin-top: -19px;
    }

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

    div[class*="st-key-card_conteudo_"] {
        background-color: rgba(128, 128, 128, 0.06);
    }

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

    div[class*="st-key-nav_hub_estatistica"] button[kind="secondary"] {
        border-left: 3px solid #6366f1;
    }
    div[class*="st-key-nav_conteudo_"] button[kind="secondary"] {
        border-left: 3px solid #10b981;
    }

    /* Bloco de identidade do aluno no topo da barra lateral: a versão deslogada (campo de nome +
       "Acessar") e a logada (nome + XP + "Sair") têm alturas diferentes, o que moveria todo o menu
       abaixo ao logar. A altura mínima reserva o espaço da versão mais alta (deslogada) para que os
       itens do menu fiquem sempre na mesma posição. */
    div[class*="st-key-sidebar_identidade"] {
        min-height: 148px;
        /* A versão logada (nome + XP + Sair) é mais baixa que a deslogada, que define os 148px.
           display:flex + justify-content:center reparte a sobra de altura em cima e embaixo, sem
           abrir vão entre "Sair" e o divisor e sem mudar a altura total. */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    /* Linha de dica/erro do apelido: existe sempre (com a dica ou com o erro), para não mudar a
       altura do bloco de identidade, que o min-height acima mantém fixa. */
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

    .sidebar-secao {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        opacity: 0.55;
        margin: 4px 0 6px 4px;
    }

    .sidebar-secao-espacada {
        margin-top: 16px;
    }

    /* Linha entre "Acessar" e "Início": margem assimétrica de propósito. O st.form do login acima
       soma ~19px de espaço próprio que o <hr> não tem embaixo; margin-top:0 e margin-bottom:19px
       deixam as distâncias de cima e de baixo iguais. */
    .sidebar-divisor-identidade {
        border: none;
        border-top: 1px solid rgba(128, 128, 128, 0.25);
        margin: 0px 4px 19px 4px !important;
    }

    /* Linha entre a última matéria cadastrada e "Painel do Professor": margem assimétrica de
       propósito (mesmo raciocínio de .sidebar-divisor-identidade); o margin-bottom maior iguala as
       distâncias de cima e de baixo. */
    .sidebar-divisor-professor {
        border: none;
        border-top: 1px solid rgba(128, 128, 128, 0.25);
        margin: 8px 4px 24px 4px !important;
    }

    div[class*="st-key-sidebar_cabecalho"] {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        /* Aproxima o título da logo reduzindo o gap padrão de 16px que o Streamlit aplica entre
           elementos empilhados em um container. Um margin-top negativo no botão do título não
           funciona de forma consistente, porque o botão fica dentro de um item flex, cuja margem
           não colapsa com a do container. */
        gap: 2px;
    }
    div[class*="st-key-sidebar_cabecalho"] img {
        margin: 0 auto 0 auto;
        cursor: pointer;
    }

    /* Título "Trilha de Aprendizagem": é um st.button (leva à Início ao clicar) que precisa parecer
       um título. Zera fundo, borda e sombra do botão padrão e deixa só o texto em negrito e
       centralizado; o :hover sutil é a única pista de que é clicável. */
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


"""
 ==========================================
4. CÁLCULOS DO CONTEÚDO NATIVO DE ESTATÍSTICA
 ==========================================
"""
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


"""
==========================================
5. VERIFICAÇÃO GENÉRICA DE RESPOSTAS
==========================================
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


def flash(mensagem):
    """
    Guarda uma mensagem de sucesso para mostrar depois do st.rerun(), em um pop-up fixo no canto
    superior direito (ver renderizar_flash_pendente, chamado uma vez no roteamento principal).
    """
    st.session_state["_flash_pendente"] = mensagem


def renderizar_flash_pendente():
    """
    Mostra e consome a mensagem guardada por flash(), se houver, como um card fixo no canto superior
    direito, visível sem rolar a tela (st.toast() não funciona neste ambiente).
    """
    mensagem = st.session_state.pop("_flash_pendente", None)
    if mensagem:
        st.markdown(
            f'<div class="flash-toast">✅ {mensagem}</div>',
            unsafe_allow_html=True,
        )


"""
==========================================
6. PÁGINA INICIAL (BANNER + ATALHOS)
==========================================
"""
@st.fragment(run_every="5s")
def render_placar_turma():
    """
    Placar da turma: apelido + XP, atualizando sozinho.

    @st.fragment(run_every="5s") recarrega só este bloco a cada 5 segundos, sem repintar a página
    nem interromper o aluno no meio de uma missão. Não é push: cada navegador consulta o banco, e
    com uma turma pequena e a consulta enxuta de ranking_turma() a carga é desprezível.

    Exibir o desempenho em público só é aceitável porque o aluno entra com apelido: o objetivo não é
    o anonimato, é não expor o nome de quem está por trás.
    """
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
    """
    Grade de cartões (ícone, título, descrição, botão "Acessar →"), 3 por linha. cartoes é uma lista
    de dicts {icone, titulo, descricao, on_click, progresso}. on_click é uma função sem argumento
    chamada ao clicar (abre uma matéria ou o hub de Estatística). "progresso" é opcional ("3/8" ou
    "✓") e mostra quantas missões daquele card já foram concluídas, pois o "8/44" do menu lateral
    soma os 6 sub-temas de Estatística.

    Usada nos "Conteúdos disponíveis" da Início e nos 6 sub-temas do hub de Estatística; prefixo_key
    garante keys únicas quando a mesma matéria aparece nas duas telas.
    """
    for inicio_linha in range(0, len(cartoes), 3):
        colunas = st.columns(3)
        for i, cartao in enumerate(cartoes[inicio_linha:inicio_linha + 3]):
            idx_global = inicio_linha + i
            cor = PALETA_CORES_CARTAO[idx_global % len(PALETA_CORES_CARTAO)]
            with colunas[i]:
                with st.container(border=True, key=f"{prefixo_key}_cartao_{idx_global}_cor_{cor}"):
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

    """
    Dentro de um expander, fechado por padrão, para quem tiver curiosidade. Cada navegador é uma
    sessão isolada: abrir ou fechar no computador do professor não afeta o celular de nenhum aluno.
    Também evita uma lista longa antes do resto da página em turmas grandes.
    """
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

    """
    Os 3 conteúdos nativos de Estatística viram um único cartão ("📊 Estatística"), desenhado à mão
    porque a ação dele abre o hub, não uma matéria. O resto vem dos conteúdos reais, via
    renderizar_grade_cartoes.
    """
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


"""
 ==========================================
7. PÁGINA "TRILHA DE MISSÕES" — ESTÁTICA E DINÂMICA
 ==========================================
"""
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


"""
 ==========================================
8. PAINEL DO PROFESSOR (PROTEGIDO POR SENHA)
 ==========================================
"""
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


CORES_DESEMPENHO = ["#2ecc71", "#f1c40f", "#e74c3c"]  # verde, amarelo, vermelho


def cor_por_percentual_concluido(percentual):
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
    if not par or not par[1]:
        return None
    return round(par[0] / par[1] * 100)


def _texto_acerto(par):
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
    """
    Sobe (direcao=-1) ou desce (direcao=+1) um conteúdo cadastrado pelo professor uma posição, só
    entre os cadastrados, nunca em relação aos nativos.

    Regra: os nativos são fixos, ficam sempre agrupados no topo (ver a normalização em
    carregar_conteudos()) e não têm setas; os cadastrados vêm sempre depois, em ordem livre.

    Como os nativos já são contíguos no início do dict, mover reordena só a lista de dinâmicos e
    reconstrói o dict como nativos + dinâmicos na nova ordem (o que também corrige ordens
    bagunçadas).
    """
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

    """
    Fica antes da lista de cards porque esses dados alimentam 4 conteúdos nativos ao mesmo tempo
    (Estatística Descritiva, Frequência, Comparando Diagramas e Planejando uma Pesquisa usam a mesma
    amostra; ver dados_estatistica) e é a ação mais usada antes de uma aula nova.
    """
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
                badges.append('<span class="badge-conteudo badge-conteudo-tipo">⚙️ Conteúdo Padrão</span>')
            else:
                n_missoes = len(c.get("missoes", []))
                badges.append(f'<span class="badge-conteudo badge-conteudo-tipo">🧩 {n_missoes} missão(ões)</span>')
            badges.append(f'<span class="badge-conteudo badge-conteudo-tipo">💯 Total {xp_maximo_de_conteudo(cid, c)} XP</span>')
            habilidades = habilidades_bncc_do_conteudo(cid, c)
            if habilidades:
                badges.append(f'<span class="badge-conteudo badge-conteudo-bncc">🎯 BNCC: {", ".join(habilidades)}</span>')
            st.markdown(" ".join(badges), unsafe_allow_html=True)
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
        """
        Ao clicar em "Editar" na lista, o formulário aparece mais abaixo sem aviso; a tela rola
        sozinha até ele.
        """
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
        """
        O campo de alternativas fica sempre visível, mesmo quando o tipo não é múltipla escolha:
        dentro de um st.form os widgets não disparam rerun, então não há como mostrá-lo só depois
        que o professor escolhe o tipo.
        """
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
                """
                Validado no cadastro, e não na aula: uma missão de múltipla escolha sem
                alternativas, ou cuja resposta correta não esteja entre elas, seria impossível de
                acertar.
                """
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

    """
    Seletor de conteúdo: o professor escolhe a disciplina do dia e vê o XP dela. Fica fora do form
    de propósito: precisa rerodar ao trocar a escolha, para atualizar o campo de meta antes de
    Salvar (widgets de form só atualizam no submit).
    """
    opcoes_conteudo = {"__catalogo__": "— Catálogo inteiro (todos os conteúdos) —"}
    opcoes_conteudo.update({cid: c["titulo"] for cid, c in st.session_state.conteudos.items()})
    opcoes_ids = list(opcoes_conteudo.keys())

    """
    A última escolha é salva no próprio config_sistema.json, e não só em session_state, que é
    perdido a cada F5 (sessão nova). meta_xp já é salvo em disco por esse arquivo; o foco escolhido
    segue o mesmo caminho.

    O widget usa key= e não recebe index=: calcular index= a partir de um valor que a mesma execução
    do script reescreve em session_state cria uma corrida, e o Streamlit pode descartar o clique do
    usuário (a seleção oscilava). Com key= apenas, o valor fica em st.session_state[key] e o
    Streamlit o gerencia sozinho.
    """
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

    """
    A key inclui o conteúdo escolhido de propósito: trocar a escolha cria um widget novo, que
    preenche de novo com valor_padrao_meta, em vez de manter o número digitado antes. O campo
    continua editável para uma meta menor que o total.
    """
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


"""
==========================================
9. MENU LATERAL (NAVEGAÇÃO)
==========================================
Ordem fixa, sempre os mesmos blocos nas mesmas posições:
   cabeçalho/Início (a própria marca) > identidade (altura reservada) >
   Matérias > Professor.
Nada aparece e some conforme a página, e o bloco de identidade tem altura mínima fixa no CSS para
que logar/deslogar não empurre o menu: o Streamlit desenha de cima para baixo, então qualquer bloco
condicional acima da navegação move tudo que vem depois.
"""
with st.sidebar:
    if st.button("🏠  Início", key="nav_inicio", use_container_width=True,
                 type="primary" if st.session_state.pagina == PAGINA_INICIO else "secondary"):
        st.session_state.pagina = PAGINA_INICIO
        st.rerun()

    """
    A logo/título também leva à Início ao clicar (o segundo caminho citado acima). st.image() não
    dispara clique, então quem carrega a ação é o texto do título, estilizado por CSS (ver
    ".st-key-nav_titulo_inicio") para não parecer um botão comum.
    """
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
            """
            "Apelido no jogo", não "Nome do Aluno": entrar com um nome inventado é parte da
            dinâmica, não um detalhe técnico. O aluno joga sem se expor quando erra, e é o professor
            que liga o apelido ao nome real, na hora do relatório (ver 'Nomes para o relatório').

            Em st.form: sem form, o texto digitado só é sincronizado com o backend no blur/Enter do
            campo, num evento separado do clique do botão — clicar em "Acessar" logo depois de
            digitar podia disparar o rerun do botão ANTES desse sync chegar, e o clique via
            nome_digitado vazio, sem erro nenhum na tela (só um F5 — que força tudo a sincronizar de
            novo — resolvia). O form agrupa campo e botão numa única mensagem, então o valor que
            chega é sempre o mais atual. Custo: a legenda de erro deixa de atualizar a cada tecla e
            passa a atualizar só ao tentar entrar — a linha continua sempre presente (mesmo motivo
            de altura de sempre), só a atualização que virou "ao enviar" em vez de "ao digitar".
            """
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

    """
    <hr> com classe própria (e não "---"): o <hr> padrão do Streamlit tem margem maior em cima que
    embaixo (medido no DOM: 51px acima, 32px abaixo). A margem assimétrica própria (ver CSS) corrige
    isso, compensando o espaço extra do st.form do login.
    """
    st.markdown('<hr class="sidebar-divisor-identidade">', unsafe_allow_html=True)

    concluidas_por_conteudo = progresso_resumo_aluno()

    """
    Estatística é um único item no menu (Descritiva, Frequência e Leitura Crítica ficam dentro do
    hub; ver PAGINA_ESTATISTICA_HUB) e fica marcado como "ativo" também quando o aluno está dentro
    de um dos sub-temas.

    "Matéria Padrão" e "Matérias Cadastradas" são dois rótulos, para separar o conteúdo padrão do
    sistema (Estatística) dos conteúdos cadastrados pelo professor. "Cadastradas" repete o termo do
    Painel do Professor ("📚 Conteúdos Cadastrados").
    """
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

    st.markdown('<hr class="sidebar-divisor-professor">', unsafe_allow_html=True)

    """
    --- Nível 1 de novo, separado: não faz parte do fluxo do aluno ---
    O 🔓 indica que o painel do professor está destravado, para que esse estado não fique escondido.
    """
    rotulo_professor = "🛡️  Painel do Professor"
    if sessao_professor_ativa():
        rotulo_professor += "  🔓"
    if st.button(rotulo_professor, key="nav_professor", use_container_width=True,
                 type="primary" if st.session_state.pagina == PAGINA_PROFESSOR else "secondary"):
        st.session_state.pagina = PAGINA_PROFESSOR
        st.rerun()

    url_pesquisa = st.session_state.config.get("url_pesquisa", "")
    if url_pesquisa:
        st.markdown('<hr class="sidebar-divisor-professor">', unsafe_allow_html=True)
        st.link_button("📝  Responder Pesquisa", url_pesquisa, use_container_width=True)

pagina = st.session_state.pagina
renderizar_flash_pendente()


"""
 ==========================================
10. ROTEAMENTO DE PÁGINAS
 ==========================================
"""
if pagina == PAGINA_INICIO:
    render_pagina_inicial()

elif pagina == PAGINA_ESTATISTICA_HUB:
    render_pagina_estatistica_hub()

elif pagina == PAGINA_MATERIA:
    if st.session_state.conteudo_ativo not in st.session_state.conteudos:
        st.session_state.conteudo_ativo = ID_CONTEUDO_ESTATISTICA
    cid = st.session_state.conteudo_ativo
    conteudo = st.session_state.conteudos[cid]

    """
    Botão "← Voltar" em toda matéria: o botão Voltar do navegador não ajuda (o app é uma SPA, sem
    "página anterior"). Os 6 sub-temas de Estatística voltam para o hub; as demais matérias
    (cadastradas) voltam para a Início, único lugar de onde são abertas.
    """
    if st.button("← Voltar", key="voltar_materia"):
        if cid in IDS_ESTATISTICA_HUB:
            ir_para_hub_estatistica()
        else:
            st.session_state.pagina = PAGINA_INICIO
            st.rerun()

    st.title(f"{conteudo['icone']} {conteudo['titulo']}")

    """
    Teoria x Missões é uma troca dentro da matéria (a mais frequente do app), por isso fica junto ao
    conteúdo e não no menu lateral. Usa dois botões em vez de st.segmented_control, que desmarca a
    opção ao clicar nela de novo (vira None), e aqui sempre há uma seção selecionada. Os botões
    também mantêm a linguagem visual do menu lateral (ativo = type="primary").
    """
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
            """
            Selo de XP em destaque no topo da Trilha de Missões — um lugar só, vale tanto pro
            conteúdo nativo de Estatística quanto pros cadastrados pelo professor, sem duplicar em
            cada função de missão.
            """
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
            """
            Embaixo, não em cima: é onde o olhar do aluno já está depois de clicar em "Verificar
            Resposta" (mesma posição do "❌ Resposta incorreta", que fica logo abaixo do botão). Uma
            versão anterior mostrava isso no topo, junto do selo de XP — só visível rolando a tela
            pra cima, o que recriava o mesmo problema de antes (informação fora de vista), só que em
            vez de sumir rápido, ficava escondida longe do clique.
            """
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
    """
    "← Voltar" para a Início só troca de tela, sem encerrar a sessão do professor (se estiver
    autenticado, continua dentro do prazo de 30 min); "🚪 Sair" encerra de propósito, para passar o
    computador a um aluno com segurança.
    """
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
        """
        Renova o prazo a cada uso do painel: o tempo passa a contar do último uso, não do login,
        então a sessão não expira no meio de um cadastro.
        """
        abrir_sessao_professor()
        _, colB = st.columns([4, 1])
        with colB:
            """
            Empurra o botão para a borda direita sem esticá-lo: use_container_width=True alargaria o
            botão até preencher a coluna. O container vira flex com justify-content:flex-end, que
            leva o botão, do próprio tamanho, até a ponta.
            """
            with st.container(key="acao_sair_professor"):
                if st.button("🚪 Sair"):
                    encerrar_sessao_professor()
                    st.rerun()

        """
        Botões em vez de st.tabs(): a seleção do st.tabs() é client-side e volta pra primeira aba
        sozinha quando a árvore de elementos muda — e é exatamente o que acontece aqui (o formulário
        de editar conteúdo desaparece da tela ao salvar). Caso típico: editar um conteúdo, salvar, e
        cair de volta em "Visão Geral" em vez de continuar em "Gerenciar Conteúdos". Mesmo padrão e
        mesmo motivo do toggle Teoria/Missões (ver ir_para_materia).
        """
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


"""
 ==========================================
11. AUTO-RUN DO STREAMLIT
 ==========================================
"""
if __name__ == '__main__':
    if not os.environ.get("RODANDO_STREAMLIT"):
        os.environ["RODANDO_STREAMLIT"] = "1"
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
