# 🎓 Trilha de Aprendizagem

Gamificação no ensino de Estatística do Ensino Médio: o aluno estuda a teoria, responde às missões, ganha XP e o professor acompanha o acerto da turma em cada habilidade da BNCC.

<p align="center">
  <a href="https://trilha-aprendizagem.streamlit.app/"><b>🚀 ABRIR O APLICATIVO</b></a>
</p>

---

## 📖 SOBRE O PROJETO

A **Trilha de Aprendizagem** nasceu no TCC de Licenciatura em Computação (UFT/UAB). A ideia é simples: transformar os exercícios de Estatística em uma **trilha de missões**, com **pontos de experiência (XP)**, **placar da turma** e **correção na hora**.

> *O erro deixa de ser motivo de frustração e passa a fazer parte do aprendizado.*

---

## ✨ FUNCIONALIDADES

### 👩‍🎓 Para o aluno

- 🎮 **Entra com um apelido**, sem precisar de cadastro nem senha.
- 📚 **Estuda a teoria** com exemplos resolvidos passo a passo.
- 🎯 **Responde às missões** em sequência, com **correção imediata**.
- ⭐ **Ganha XP** a cada acerto. Cada erro diminui um pouco o XP da missão, *mas nunca zera*.
- 🏆 **Acompanha o Placar da Turma**, que se atualiza sozinho.

### 👨‍🏫 Para o professor

- 🛡️ **Painel do Professor**, protegido por senha.
- 📊 **Desempenho da turma**: XP, erros e missões concluídas por aluno.
- 🟢🟡🔴 **Acerto por habilidade da BNCC**, com cores:
  - 🟢 **verde**: a partir de 70%;
  - 🟡 **amarelo**: de 40% a 69%;
  - 🔴 **vermelho**: abaixo de 40%.
- 📄 **Relatório em PDF** de cada conteúdo, pronto para imprimir.
- ➕ **Conteúdos novos** de qualquer disciplina, com a habilidade da BNCC escolhida numa **lista pesquisável**.
- 🔢 **Troca dos dados** usados nos cálculos, para a turma refazer a atividade com valores novos.

---

## 📊 CONTEÚDOS DE ESTATÍSTICA

São **6 conteúdos** e **44 missões**, cada um ligado a uma habilidade da BNCC do Ensino Médio.

| Conteúdo | Habilidade | Missões |
|---|:---:|:---:|
| 📈 Estatística Descritiva | `EM13MAT316` | 10 |
| 📊 Tabela e Gráfico de Frequência | `EM13MAT408` | 8 |
| 🔍 Leitura Crítica de Gráficos | `EM13MAT102` | 8 |
| 📦 Comparando Diagramas | `EM13MAT409` | 6 |
| 📝 Planejando uma Pesquisa | `EM13MAT202` | 6 |
| 🔗 Relação entre Duas Variáveis | `EM13MAT510` | 6 |

---

## 🛠️ TECNOLOGIAS

- 🐍 **Python** com **Streamlit**
- 🗄️ **SQLite** para o progresso dos alunos
- 📄 **fpdf2** para o relatório em PDF
- 📉 **Altair** e **pandas** para os gráficos e as tabelas

---

## 🚀 COMO RODAR

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\streamlit run trilha_aprendizagem.py
```

🔑 Senha padrão do Painel do Professor: `123`. *Troque em Configurações.*

---

## 🙌 AUTORIA

Desenvolvido por **Wenes Gomes Aquino** no TCC de Licenciatura em Computação (UFT/UAB):
*Trilha de Aprendizagem: Gamificação no Ensino de Estatística*.

## 📜 LICENÇA

**MIT**. As fontes CMU Serif seguem a licença OFL (ver `fonts/OFL.txt`).
