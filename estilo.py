"""CSS da aplicação e carregamento da logo."""

import os
import base64

import streamlit as st

from config import ARQUIVO_LOGO


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


CSS_APLICACAO = """
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

    /* Cada bloco invisível (os st.iframe(..., height=1) que injetam JS e o próprio <style>)
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
"""


def aplicar_estilo():
    """Aplica o CSS da aplicação."""
    st.markdown(CSS_APLICACAO, unsafe_allow_html=True)
