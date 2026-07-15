# TechHub UERN 🎓
<img width="2316" height="1115" alt="image" src="https://github.com/user-attachments/assets/5291b44a-ba21-492b-9ad2-e21e60510e34" />

O **TechHub UERN** é um agregador automático de oportunidades acadêmicas, desenvolvido como projeto para a disciplina de Banco de Dados II. 

Ele automatiza a busca por editais de estágio, bolsas e auxílios espalhados pelos portais institucionais da Universidade do Estado do Rio Grande do Norte (PRAE e PROEX), centralizando-os em uma interface única, limpa e responsiva.

---

## 🛠️ Arquitetura e Tecnologias

O projeto adota uma arquitetura separada (Decoupled), dividida em três camadas principais:

1. **Coleta e Inteligência de Dados (Web Scraping & Text Mining):** * Scripts em **Python** utilizando `BeautifulSoup4` e `Requests` para varrer páginas HTML estáticas específicas da universidade.
   * Módulo avançado de **Text Mining** com Expressões Regulares (`re`) e agentes simulados para varredura em profundidade de portais de notícias oficiais, filtrando conteúdos institucionais densos e isolando apenas oportunidades reais de estágio e editais através de correspondência de palavras-chave.
2. **Armazenamento (Banco de Dados):** **MongoDB** (NoSQL). Escolhido pela flexibilidade na inserção de documentos com esquemas variáveis (ex: editais da PRAE vs. PROEX vs. Portal de Notícias). A integração é feita via `PyMongo` utilizando uma estratégia híbrida normatizada para governança e resolução de metadados de fontes institucionais em tempo de execução.
3. **Disponibilização (API e Interface):**
    * **Back-end:** Uma API RESTful construída com **FastAPI**, servindo os dados em formato JSON com suporte nativo a paginação server-side e indexação de buscas textuais.
    * **Front-end:** Interface estática desenvolvida com **HTML, CSS e Vanilla JavaScript** (Fetch API), consumindo os dados do back-end de forma assíncrona.

---

## 🚀 Como Executar o Projeto Localmente

Siga os passos abaixo para rodar a aplicação em sua máquina.

### Pré-requisitos
* [Python 3.11 ou superior](https://www.python.org/downloads/)
* [MongoDB Community Server](https://www.mongodb.com/try/download/community) rodando localmente (porta 27017).

### Passo 1: Clonar e Instalar Dependências
Abra o terminal, clone o repositório e instale as bibliotecas necessárias. É altamente recomendado o uso de um ambiente virtual (`venv`).

```bash
git clone [https://github.com/PatoDesoxigenado/TechHub---WebScrapping-de-Editais-para-Alunos.git](https://github.com/PatoDesoxigenado/TechHub---WebScrapping-de-Editais-para-Alunos.git)
cd TechHub---WebScrapping-de-Editais-para-Alunos

# Criar e ativar ambiente virtual (Windows)
python3 -m venv venv
venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

### Passo 2: Inicializar o Banco de Dados e o Servidor (Back-end)
Entre na pasta do backend, execute os scrapers para buscar os editais nos portais, alimente a base NoSQL com a esteira de mineração de dados e, em seguida, ligue o servidor FastAPI:

```bash
cd backend

# 1. Executa a coleta automática dos portais estáticos
python scraper_prae.py
python scraper_proex.py

# 2. Alimenta a base NoSQL com os dados históricos de Text Mining do Portal UERN
python popular_portal.py

# 3. Inicializa o servidor da API RESTful (FastAPI)
python -m uvicorn main:app --reload

E depois, abrir a interface clicando no arquivo `index.html`! :)
