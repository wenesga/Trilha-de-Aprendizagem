"""Constantes, caminhos de arquivos e identificadores do sistema."""

import os


"""
As artes ficam no topo porque st.set_page_config() precisa do caminho da logo e deve ser a primeira
chamada st.* do script.

imagens/ guarda as artes do projeto e fonts/ as fontes. static/ é diferente: o Streamlit serve essa
pasta em app/static/ (enableStaticServing em .streamlit/config.toml) e o manifest e os ícones do PWA
dependem desse caminho, então ela não deve ser movida.
"""
ARQUIVO_LOGO = "static/logo.svg"                 # opcional: marca quadrada do projeto em vetor, um arquivo só para barra lateral, ícone da aba e ícone do app instalado (por isso fica em static/, que o manifest alcança por URL)
ARQUIVO_BANNER = "imagens/banner.svg"            # opcional: arte pronta para o topo da Página Inicial (ideal 1200x400px ou 1500x500px, formato "capa" tipo Facebook/Twitter — pode já vir com a logo embutida, feita no Photoshop)
ARQUIVO_CABECALHO = "imagens/cabecalho.png"      # opcional: timbre institucional no topo de toda página do relatório em PDF. Tem que ser PNG (o fpdf2 não embute PDF); exportar com ~2008px de largura = 300 DPI nos 170mm da página. A altura é livre, o código lê a proporção do arquivo

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
ID_CONTEUDO_FREQUENCIA = "estatistica_frequencia"          # id fixo do 2º conteúdo nativo (EM13MAT406, reusa os mesmos dados)
ID_CONTEUDO_LEITURA_GRAFICA = "estatistica_leitura_grafica"  # id fixo do 3º conteúdo nativo (EM13MAT102, cenário fixo)
ID_CONTEUDO_COMPARACAO = "estatistica_comparacao_diagramas"  # id fixo do 4º conteúdo nativo (EM13MAT407, reusa os mesmos dados)
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

TAMANHO_MIN_APELIDO = 2
TAMANHO_MAX_APELIDO = 20

"""
Mapeamento das missões dos conteúdos nativos para habilidades da BNCC (um dicionário por conteúdo,
indexado pelo id). Fica no código porque essas missões não estão em conteudos.json.

- Estatística Descritiva (10 missões): EM13MAT316, medidas de tendência central e de dispersão.
- Tabela e Gráfico de Frequência (FREQ_N_FAIXAS+3): EM13MAT406, tabelas e gráficos de frequência.
- Leitura Crítica de Gráficos (8): EM13MAT102, análise de gráficos e amostras divulgados na mídia.
- Comparando Diagramas (6): EM13MAT407, comparação de diagramas (histograma, box-plot, ramos e
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
    ID_CONTEUDO_FREQUENCIA: {i: "EM13MAT406" for i in range(1, FREQ_N_FAIXAS + 4)},
    ID_CONTEUDO_LEITURA_GRAFICA: {i: "EM13MAT102" for i in range(1, 9)},
    ID_CONTEUDO_COMPARACAO: {i: "EM13MAT407" for i in range(1, 7)},
    ID_CONTEUDO_PESQUISA_AMOSTRAL: {i: "EM13MAT202" for i in range(1, 7)},
    ID_CONTEUDO_TENDENCIA: {i: "EM13MAT510" for i in range(1, 7)},
}


ARQUIVO_HABILIDADES_BNCC = "habilidades_bncc.json"  # gerado por arquivos/gerar_habilidades_bncc.py (Ensino Médio)


"""
Total de missões de cada conteúdo nativo. Como as missões são funções Python (ver paginas/trilha_missoes.py) e não uma
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


CORES_DESEMPENHO = ["#2ecc71", "#f1c40f", "#e74c3c"]  # verde, amarelo, vermelho
