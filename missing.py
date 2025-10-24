import requests
import sqlite3
from bs4 import BeautifulSoup
import os
import pandas as pd #gerar gráfico 
import plotly.express as px
import requests #Para baixar o arquivo JSON
import numpy as np 
import json
import time
from tqdm import tqdm #Barra de progresso
from urllib.parse import urljoin
from flask import Flask 

BASE_URL = "https://desaparecidosbrasil.org/?page={}"
DB_NAME = "desaparecidos.db"
IMG_DIR = r"C:\mitra\desaparecidos\source"

app = Flask(__name__) 

PROXIES = {
    "http": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080',
    "https": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080'
}
# Garantir pasta
os.makedirs(IMG_DIR, exist_ok=True)

# Criar banco
conn = sqlite3.connect(DB_NAME, check_same_thread=False) # check_same_thread=False (Boa prática para Flask)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS desaparecidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    idade TEXT,
    sexo TEXT,
    desapareceu_em TEXT,
    local TEXT,
    vestimenta TEXT,
    instituicao TEXT,
    estado TEXT,
    foto_url TEXT UNIQUE,
    img_path TEXT,
    pagina INTEGER,
    status TEXT, 
    fonte TEXT
)
""")
conn.commit()

#consulta por nome
print("\n Consultando por nome do desaparecido\n")
nome = 'MARIA EDUARDA ROCHA ALMEIDA'
cursor.execute("SELECT * FROM desaparecidos WHERE nome = ?", (nome,))
resultado = cursor.fetchone()
if resultado:
    print(f"Registro encontrado para {nome}: {resultado}")
else:
    print("Nenhum registro encontrado.\n")

#flask
@app.route('/')
def index():
    conn_local = sqlite3.connect(DB_NAME)
    cursor_local = conn_local.cursor() # Criamos um cursor local
    
    # 1. Gera o HTML do mapa
    mapa_html = mapa_database(conn_local)
    
    # 2. Gera o HTML das estatísticas
    stats_html = gerar_estatisticas_htm(cursor_local) 
    
    conn_local.close()
    
    # 3. Retorna a página final com as duas partes e um layout de 2 colunas
    return f"""
    <html>
        <head>
            <title> Mapa de desaparecidos </title>
            <style>
                body {{ font-family: sans-serif; margin: 0; padding: 0; display: flex; height: 100vh; }}
                
                /* Coluna da Esquerda (Estatísticas) */
                #stats {{
                    flex: 1; /* Ocupa 1 parte do espaço */
                    padding: 20px;
                    overflow-y: auto; /* Adiciona barra de rolagem se for muito longo */
                    box-shadow: 2px 0 5px rgba(0,0,0,0.1); /* Sombra sutil */
                    background-color: #f9f9f9;
                }}
                
                /* Coluna da Direita (Mapa) */
                #mapa {{
                    flex: 6; /* Ocupa 3 partes do espaço (é maior) */
                    height: 100%;
                }}
                
                h2, h3 {{ border-bottom: 1px solid #ccc; padding-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div id="stats">
                {stats_html}
            </div>
            
            <div id="mapa">
                {mapa_html}
            </div>
        </body>
    </html>
    """

def gerar_estatisticas_htm(cursor_local):
    #Cosulta os dados no banco de dados e retorna as estatísticas em HTML
    print("Gerando estatísticas html...")
    query = "SELECT estado, COUNT(*) FROM desaparecidos GROUP BY estado ORDER BY COUNT(*) DESC"
    cursor_local.execute(query)
    resultados = cursor_local.fetchall()
    #string HTML
    html_output = "<h2> Estatísticas por Estado</h2>"
    if not resultados:
        html_output += "<p> Nenhum estado encontrado para gerar estatísticas.</p>"
    else:
        html_output += "<ul style = 'padding-left: 20px'>"
        for estado, quantidade in resultados:
            #Tratamento para casos do estado ser nulo ou vazio
            estado_nome = estado if estado else "Não especificado"
            html_output += f"<li style = 'margin-bottom: 5px;'> {estado_nome}: <strong>{quantidade}</strong></li>"
        html_output += "</ul>"
    #Adionando Total geral de desaparecidos:
    cursor_local.execute("SELECT COUNT (*) FROM desaparecidos")
    total_geral = cursor_local.fetchone()[0]
    html_output += f"<hr><h3>Total de Registros: {total_geral}</h3>"

    return html_output


# --- FUNÇÕES ---s
def baixar_imagem(foto_url, registro_id): 
    # Verificação de segurança: se a URL for Nula, simplesmente não faz nada.
    if not foto_url:
        # print(f"⚠️  Foto não disponível para o registro ID {registro_id}.") # Comentado para limpar o log
        return

    try:
        r = requests.get(foto_url, stream=True, timeout=30, verify=False, proxies=PROXIES)
        if r.status_code == 200:
            file_path = os.path.join(IMG_DIR, f"{registro_id}.jpg")
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            cursor.execute("UPDATE desaparecidos SET img_path = ? WHERE id = ?", (file_path, registro_id))
            conn.commit()
        else:
            print(f"⚠️ Erro ao baixar imagem {foto_url} (Status: {r.status_code})")
    except Exception as e:
        print(f"❌ Falha ao salvar imagem {foto_url}: {e}")

# --------- SCRAPING PORTAL DE DESAPARECIDOS DO BRASIL  ---------
def scrape_desaparecidos_brasil(stop_on_duplicate: bool):
    """Faz o web scraping do site desaparecidosbrasil.org."""
    print("\n---  scraping desaparecidosbrasil.org ---")
    BASE_URL = "https://desaparecidosbrasil.org/?page={}"
    
    page = 1
    while True: #alterado para não precisar informar número máximo de páginas
        url = BASE_URL.format(page)
        try:
            r = requests.get(url, proxies=PROXIES, timeout=30, verify=False)
            if r.status_code != 200:
                print(f"❌ Erro ao acessar página {page} de desaparecidosbrasil.org")
                continue # Pula para a próxima página
        except requests.RequestException as e:
            print(f"❌ Falha de conexão na página {page} de desaparecidosbrasil.org: {e}")
            break # Se falhar a conexão, provavelmente não há mais páginas

        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.person-card")

        if not cards:
            print("Nenhum card encontrado na página, encerrando a busca neste site.")
            break

        for card in cards:
            #Adicionando verificação para Localizado e Falecido
            card_text = card.get_text().lower()
            if "localizada" in card_text or "localizado" in card_text or \
                "falecida" in card_text or "falecido" in card_text:
                nome_ignorado = card.find("h4").get_text(strip=True) if card.find("h4") else "ID Desconhecido"
                print(f" Registro '{nome_ignorado}' ignorado (status 'localizado ou 'falecido).")
                continue

            foto_tag = card.find("img", class_="pessoa-img")
            if foto_tag and foto_tag.get('src'):
                foto_url = urljoin("https://desaparecidosbrasil.org/", foto_tag['src'])
            else:
                foto_url = None

            # 1. Verifica duplicata ANTES de processar o resto
            cursor.execute("SELECT id FROM desaparecidos WHERE foto_url = ?", (foto_url,))
            if cursor.fetchone():
                if stop_on_duplicate:
                    print(f"⚠️ Foto já existe no banco ({foto_url}). Encerrando varredura incremental de desaparecidosbrasil.org.")
                    return True 
                else:
                    continue # Ignora e segue para o próximo card

            # 2. Extrai os outros dados
            nome = card.find("h4").get_text(strip=True) if card.find("h4") else None
            idade = sexo = desapareceu_em = local = vestimenta = instituicao = None

            for p in card.find_all("p"):
                strong = p.find("strong")
                if not strong: continue
                label = strong.get_text(strip=True).lower()
                value = p.get_text(" ", strip=True).replace(strong.get_text(), "").strip(" :")

                if "idade" in label: idade = value
                elif "sexo" in label: sexo = value
                elif "desapareceu" in label: desapareceu_em = value
                elif label.startswith("local"): local = value
                elif "vestimenta" in label: vestimenta = value
                elif "instituição" in label: instituicao = value
            
            estado_tag = card.find("div", class_="estado-bandeira-container")
            estado = estado_tag.img['title'] if (estado_tag and estado_tag.img) else None # Extrai o estado do título da imagem

            # 3. Insere no banco
            cursor.execute("""
            INSERT INTO desaparecidos 
            (nome, idade, sexo, desapareceu_em, local, vestimenta, instituicao, estado, foto_url, pagina, status, fonte)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nome, idade, sexo, desapareceu_em, local, vestimenta, instituicao, estado, foto_url, page, "new", "desaparecidosbrasil.org"))
            conn.commit()
            registro_id = cursor.lastrowid

            # 4. Baixa a imagem
            baixar_imagem(foto_url, registro_id)
            
        print(f"✅ Página {page} de desaparecidosbrasil.org processada.")
        page += 1
        time.sleep(0.3)  
    return False # Varredura concluída sem parada por duplicata

# --------- WEB SCRAPING CADASTRO NACIONAL DE PESSOAS DESAPARECIDAS (CNPD) ---------
def scrape_cnpd(stop_on_duplicate: bool):
    """Faz o scraping da API do site cnpd.mj.gov.br usando o endpoint de filtro REAL."""
    print("\n---  scraping cnpd.mj.gov.br ---")
    
    API_URL = "https://cnpd.mj.gov.br/api/api/painel-publico/desaparecidos/filtrar"
    
    HEADERS = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://cnpd.mj.gov.br',
        'Referer': 'https://cnpd.mj.gov.br/painel-publico',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    }

    mapa_uf_estado = { 'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo', 'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina', 'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins' }

    pagina_atual = 0
    
    while True:
        # Parâmetros para paginação e ordenação
        params = {
            'ordenacao': 'MAIS_RECENTE',
            'pagina': pagina_atual,
            'quantidade': 50,
        }
     
        json_data = {}

        try:
            
            response = requests.post(
                API_URL,
                headers=HEADERS, 
                params=params,
                json=json_data,
                proxies=PROXIES,
                verify=False,
                timeout=60 
            )
            response.raise_for_status()
            data = response.json()
            
            # A API de filtro retorna os dados dentro da chave 'desaparecidos' from JSON da API
            pessoas_na_pagina = data.get('desaparecidos', [])
            
            if not pessoas_na_pagina:
                print("\nExtração do CNPD concluída: Não há mais páginas.")
                break

            for pessoa in tqdm(pessoas_na_pagina, desc=f"CNPD página {pagina_atual}", unit="registro"):
                pessoa_id = pessoa.get('id')
                foto_url = f"https://cnpd.mj.gov.br/api/pessoas/{pessoa_id}/foto" if pessoa_id else None
                #Verifica o ID da pessoa
                cursor.execute("SELECT id FROM desaparecidos WHERE id = ? AND fonte = ?", (pessoa_id, "cnpd.mj.gov.br"))
                if cursor.fetchone():
                    if stop_on_duplicate:
                        print(f"\n⚠️ Registro ID {pessoa_id} já existe no banco. Encerrando varredura incremental do CNPD.")
                        return   
                    else:
                        continue
                #Corrigindo o erro "não especificados"
                uf = pessoa.get('ufRegistro')
                if uf and uf in mapa_uf_estado:
                    estado_nome = mapa_uf_estado.get(uf)
                else:
                    estado_nome= None #Salva null no db de a UF for inválida
                nome = pessoa.get('nome')
                idade = str(pessoa.get('idadeAtual')) if pessoa.get('idadeAtual') else None
                sexo = pessoa.get('sexo')
                desapareceu_em = pessoa.get('dataRegistroDesaparecimento')
                local = pessoa.get('localRegistro')

                cursor.execute("""
                                INSERT INTO desaparecidos (id, nome, idade, sexo, desapareceu_em, local, estado, foto_url, pagina, status, fonte)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                                """, (pessoa_id, nome, idade, sexo, desapareceu_em, local, estado_nome, foto_url, pagina_atual, "new", "cnpd.mj.gov.br"))
                conn.commit()
                baixar_imagem(foto_url, pessoa_id)
            
            pagina_atual += 1
            time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            print(f"\n❌ Erro ao conectar à API do CNPD na página {pagina_atual}: {e}")
            break

# --- FIM FUNÇÕES DE WEB SCRAPING ---


#Fução de estatísticas
def mostrar_estatisticas_por_estado(cursor):
    """Consulta o banco de dados e exibe o total de desaparecidos por estado."""
    print("\n--- 📊 Estatísticas por Estado ---")
    
    # Query para contar todos os registros, agrupá-los por estado e ordenar do maior para o menor
    query = "SELECT estado, COUNT(*) FROM desaparecidos GROUP BY estado ORDER BY COUNT(*) DESC"
    
    cursor.execute(query)
    resultados = cursor.fetchall()

    if not resultados:
        print("Nenhum dado encontrado para gerar estatísticas.")
        return

    for estado, quantidade in resultados:
        # Trata casos onde o estado pode ser nulo ou vazio no banco
        estado_nome = estado if estado else "Não especificado"
        print(f"📍 {estado_nome}: {quantidade} desaparecidos")

    cursor.execute("SELECT COUNT(*) FROM desaparecidos")
    total_geral = cursor.fetchone()[0]
    print(f"Total: {total_geral}")
# O que falta:
#Deixar o mapa responsivo, adicionar verificação de nomes repetidos, 
#Criando mapa de desaparecidos
def mapa_database(conn):
    # 1. Pega os dados do banco
    print("\n Gerando mapeamento...")
    query = "SELECT estado, COUNT(*) as quantidade FROM desaparecidos GROUP BY estado"
    df_dados = pd.read_sql_query(query, conn)

    # 2. Calcula o valor máximo para o range
    if not df_dados.empty:
        valor_maximo = df_dados['quantidade'].max()
    else:
        valor_maximo = 100 
    
    mapeamentos_estados = {
        'Acre': 'AC', 'Alagoas': 'AL', 'Amapá': 'AP', 'Amazonas': 'AM', 'Bahia': 'BA', 
        'Ceará': 'CE', 'Distrito Federal': 'DF', 'Espírito Santo': 'ES', 'Goiás': 'GO', 
        'Maranhão': 'MA', 'Mato Grosso': 'MT', 'Mato Grosso do Sul': 'MS', 'Minas Gerais': 'MG', 
        'Pará': 'PA', 'Paraíba': 'PB', 'Paraná': 'PR', 'Pernambuco': 'PE', 'Piauí': 'PI', 
        'Rio de Janeiro': 'RJ', 'Rio Grande do Norte': 'RN', 'Rio Grande do Sul': 'RS', 
        'Rondônia': 'RO', 'Roraima': 'RR', 'Santa Catarina': 'SC', 'São Paulo': 'SP', 
        'Sergipe': 'SE', 'Tocantins': 'TO'
    }
    df_dados['id'] = df_dados['estado'].map(mapeamentos_estados)

    # 3. Carrega o GeoJSON
    geojson_url = "brazil_geo.json" 
    try:
        with open(geojson_url, 'r', encoding='utf-8') as f:
            geojson = json.load(f)
    except FileNotFoundError:
        print(f"Arquivo {geojson_url} não encontrado. Verifique o caminho.")
        return
    
    # 4. Lógica para incluir todos os estados
    todos_os_estados = {
        feature['id']: feature['properties']['name'] 
        for feature in geojson['features']
    }
    df_completo = pd.DataFrame(list(todos_os_estados.items()), columns=['id', 'estado'])
    df_mapa = pd.merge(df_completo, df_dados[['id', 'quantidade']], on='id', how='left')
    df_mapa['quantidade'].fillna(0, inplace=True)

    fig = px.choropleth(
        df_mapa,
        geojson=geojson,
        locations='id',
        featureidkey="id",
        color='quantidade',
        hover_name='estado',
        color_continuous_scale="blues",
        title='<b>Mapeamento de desaparecidos no Brasil</b>',
        labels={'quantidade': 'Nº de Desaparecidos'}
    ) 
    fig.update_geos(
        fitbounds="locations",
        visible=False
    )
    #LAYOUT mapa

    fig.update_layout(
        title_x=0.5,
        margin={"r":0, "t":40, "l":0, "b":0},
        
        coloraxis=dict(
            cmin=0,
            cmax=valor_maximo,
            colorscale="blues",
            # Força as marcações (ticks) na barra de cores
            colorbar=dict(
                title="<b>Total de Desaparecidos</b>",
                x=0.8, 
                y=0.5,
                len=0.75,
                thickness=20,
                #--- Rótulos ---
                tickvals=np.linspace(0, valor_maximo, 5),
                ticktext=[f"{int(v)}" for v in np.linspace(0, valor_maximo, 5)],
                #--- Estilo da borda e fundo ---
                bgcolor="rgba(255,255,255,0.7)", #funco branco semi-transparente
                borderwidth=0.1,
                bordercolor="#000000"           
            )
        )
    )
    #fig.show() #usado para gerar o mapa, cria uma janela no navegador
    
    #mudança para o mapa retornar como Web Service
    map_html = fig.to_html(full_html = False, include_plotlyjs='cdn') 
    return map_html


def consulta(cursor):
    cursor.execute("SELECT fonte, COUNT(*) as quantidade FROM desaparecidos WHERE estado IS NULL OR estado = '' GROUP BY fonte; ")
    resultados = cursor.fetchall()
    print("Resultados da consulta:")
    for row in resultados:
        print(f"Fonte: {row[0]}, Quantidade: {row[1]}")

def main():
    # Verifica se já existem registros no banco
    cursor.execute("SELECT COUNT(*) FROM desaparecidos")
    total = cursor.fetchone()[0]

    stop_on_duplicate = total > 0  # True se já existir algum registro

    print(f"📊 Registros atuais no banco: {total}")
    if stop_on_duplicate:
        print("🔎 Modo incremental (parar ao encontrar duplicata).")
    else:
        print("🆕 Banco vazio, varrendo todas as páginas.")
    

    scrape_desaparecidos_brasil(stop_on_duplicate)
    scrape_cnpd(stop_on_duplicate)
    print("\n 🚀 Varredura de todas as fontes concluída.")
    mostrar_estatisticas_por_estado(cursor)
    
    #print("Verificando total de não especificados...")
    #consulta(cursor)

    #fechando conexão com db
    conn.close()
    print("Conexão com o banco de dados principal fechada com sucesso.")

    
if __name__ == "__main__":
# 1. Roda o scraping e imprime tudo no terminal PRIMEIRO
    print("--- INICIANDO SCRIPT DE SCRAPING ---")
    main()
    # 2. DEPOIS que o scraping terminar, inicia o servidor web
    print("\n--- INICIANDO SERVIDOR WEB ---")
    print(f"Acesse o mapa em: http://127.0.0.1:5001")
    app.run(debug=True, port=5001)