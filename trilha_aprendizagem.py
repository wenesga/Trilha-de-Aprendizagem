import os
import subprocess
import sys

"""
Ancora o diretório de trabalho na pasta deste arquivo, para que os caminhos relativos (logo, banner,
bancos) funcionem de onde quer que o script seja iniciado.
"""
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from config import ARQUIVO_LOGO

st.set_page_config(
    page_title="Trilha de Aprendizagem",
    page_icon=ARQUIVO_LOGO if os.path.exists(ARQUIVO_LOGO) else "🎓",
    layout="wide"
)

from banco import (
    inicializar_banco_db,
    migrar_json_para_sqlite_se_necessario,
    registrar_acesso_se_novo,
)
from config import PAGINA_ESTATISTICA_HUB, PAGINA_INICIO, PAGINA_MATERIA, PAGINA_PROFESSOR
from estilo import aplicar_estilo
from injecoes import aplicar_injecoes
from paginas.inicio import render_pagina_estatistica_hub, render_pagina_inicial
from paginas.materia import render_pagina_materia
from paginas.menu import render_menu_lateral
from paginas.professor import render_pagina_professor
from sessao import inicializar_estado, renderizar_flash_pendente

aplicar_injecoes()
inicializar_banco_db()
migrar_json_para_sqlite_se_necessario()
registrar_acesso_se_novo()
inicializar_estado()
aplicar_estilo()

with st.sidebar:
    render_menu_lateral()

pagina = st.session_state.pagina
renderizar_flash_pendente()

if pagina == PAGINA_INICIO:
    render_pagina_inicial()

elif pagina == PAGINA_ESTATISTICA_HUB:
    render_pagina_estatistica_hub()

elif pagina == PAGINA_MATERIA:
    render_pagina_materia()

elif pagina == PAGINA_PROFESSOR:
    render_pagina_professor()


if __name__ == '__main__':
    if not os.environ.get("RODANDO_STREAMLIT"):
        os.environ["RODANDO_STREAMLIT"] = "1"
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
