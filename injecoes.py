"""Trechos de JavaScript e manifest do app instalado injetados na página."""

import os

import streamlit as st


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
    st.iframe(
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
        height=1,
        width=1,
    )


def _injetar_bloqueio_espaco_apelido():
    """
    Remove espaços do campo de apelido assim que aparecem, digitando, colando ou em qualquer
    teclado, inclusive o virtual do celular.

    Usa o evento 'input', que dispara sempre que o valor do campo muda (ao contrário de 'keydown',
    que muitos teclados virtuais não emitem). A checagem `if (limpo === el.value) return` evita laço
    infinito: o valor só é reescrito quando há espaço a remover.

    É conveniência de digitação, não validação: apelido_invalido() continua valendo no servidor.
    """
    st.iframe(
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
        height=1,
        width=1,
    )


def _injetar_aviso_saida():
    """
    Mostra o aviso nativo do navegador ('Sair do site?') ao fechar, atualizar ou sair da página.

    O app é uma SPA: o conteúdo muda via WebSocket dentro de uma única página, então o botão Voltar
    do navegador sai do app sem aviso. O texto do aviso é fixo (definido pelo navegador); só é
    possível ligá-lo ou desligá-lo.
    """
    st.iframe(
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
        height=1,
        width=1,
    )


def _injetar_liberar_scroll_grafico():
    """
    Permite rolar a página normalmente quando o mouse está sobre um gráfico (Altair/Vega-Lite).

    O wrapper .stVegaLiteChart do Streamlit intercepta o scroll sobre qualquer gráfico, mesmo sem
    zoom/pan ligado. Como a captura ocorre em um listener interno, a solução é ouvir o evento de
    scroll na fase de captura (que roda antes) e, se o alvo estiver dentro de um gráfico, rolar
    manualmente a área principal (.stMain).
    """
    st.iframe(
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
        height=1,
        width=1,
    )


def _injetar_clique_logo_inicio():
    """
    Faz a logo também levar à Início ao clicar, como o título.

    st.image() não aceita on_click nem link. O código escuta cliques no cabeçalho
    (".st-key-sidebar_cabecalho") e, se não foi um clique direto no botão do título, simula um
    clique nele, reaproveitando a navegação existente.
    """
    st.iframe(
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
        height=1,
        width=1,
    )


def aplicar_injecoes():
    """Injeta o JavaScript e o manifest do app instalado na página."""
    _injetar_manifest_pwa()
    _injetar_bloqueio_espaco_apelido()
    _injetar_aviso_saida()
    _injetar_liberar_scroll_grafico()
    _injetar_clique_logo_inicio()
