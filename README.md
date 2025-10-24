# Projeto de Unificação e Visualização de Desaparecidos no Brasil

![Status: Em Desenvolvimento](https://img.shields.io/badge/status-em_desenvolvimento-yellow)

Um web service desenvolvido com Flask e Plotly para coletar, unificar e visualizar dados de pessoas desaparecidas no Brasil.

##  Motivação

No Brasil, existem diversas iniciativas de órgãos de segurança pública para o levantamento de pessoas desaparecidas. No entanto, esses dados não são unificados, muitas vezes são incompletos e não contemplam todos os estados brasileiros de forma consistente.

Este projeto tem como objetivo principal centralizar e unificar essas informações, fornecendo um panorama mais claro e acessível sobre a situação no país.

## Objetivos do Projeto

* **Coletar:** Fazer web scraping de múltiplas fontes de dados públicas.
* **Unificar:** Armazenar e consolidar os dados coletados em um banco de dados único.
* **Visualizar:** Criar um mapa cloroplético interativo (usando Plotly) que exibe as estatísticas por estado.
* **Servir:** Disponibilizar a visualização através de um web service (Flask).

## Funcionalidades Atuais

* **Web Scraping:** Scripts para extração de dados das seguintes fontes:
    * `https://desaparecidosbrasil.org/`
    * `https://cnpd.mj.gov.br/painel-publico`
* **Banco de Dados:** Armazenamento dos dados coletados para consulta e análise.
* **Mapa Interativo:** Geração de um mapa cloroplético do Brasil que exibe a quantidade de desaparecidos por estado.
* **API/Web Service:** Aplicação Flask que serve a página com a visualização dos dados.

## Tecnologias Utilizadas

* **Backend:** Python, Flask
* **Visualização:** Plotly
* **Coleta de Dados:** (Ex: BeautifulSoup, Scrapy, Requests - *adicione a que você usou*)
* **Banco de Dados:** (Ex: SQLite, PostgreSQL - *adicione o que você usou*)

## Planos Futuros

O objetivo é expandir o projeto para incluir mais fontes de dados oficiais, aumentando a precisão e a abrangência das estatísticas apresentadas.

## Como Executar

1.  Clone o repositório:
    ```bash
    git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
    cd seu-repositorio
    ```
2.  Crie e ative um ambiente virtual:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Ou .\venv\Scripts\activate no Windows
    ```
3.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
4.  Execute a aplicação Flask:
    ```bash
    flask run
    ```
