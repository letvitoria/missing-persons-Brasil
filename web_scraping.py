import requests
import sqlite3
from bs4 import BeautifulSoup
import os
import time
from tqdm import tqdm
from urllib.parse import urljoin

# --- Configurações do Scraper ---
# (Pega as constantes do Model para evitar duplicação)
from app.models.database import DB_NAME, IMG_DIR, PROXIES

# --- Funções de Scraping (Exatamente como você as corrigiu) ---

def baixar_imagem(conn, cursor, foto_url, registro_id): 
    if not foto_url:
        print(f"⚠️  Foto não disponível para o registro ID {registro_id}.")
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

def scrape_desaparecidos_brasil(conn, cursor, stop_on_duplicate: bool):
    print("\n---  scraping desaparecidosbrasil.org ---")
    BASE_URL = "https://desaparecidosbrasil.org/?page={}"
    page = 1
    while True:
        url = BASE_URL.format(page)
        try:
            r = requests.get(url, proxies=PROXIES, timeout=30, verify=False)
            if r.status_code != 200:
                print(f"❌ Erro ao acessar página {page} de desaparecidosbrasil.org")
                continue
        except requests.RequestException as e:
            print(f"❌ Falha de conexão na página {page} de desaparecidosbrasil.org: {e}")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.person-card")
        if not cards:
            print("Nenhum card encontrado na página, encerrando a busca neste site.")
            break
        for card in cards:
            card_text = card.get_text().lower()
            if "localizada" in card_text or "localizado" in card_text or \
               "falecida" in card_text or "falecido" in card_text:
                nome_ignorado = card.find("h4").get_text(strip=True) if card.find("h4") else "ID Desconhecido"
                print(f"↪️  Registro '{nome_ignorado}' ignorado (status 'localizado ou 'falecido).")
                continue
            foto_tag = card.find("img", class_="pessoa-img")
            foto_url = urljoin("https://desaparecidosbrasil.org/", foto_tag['src']) if foto_tag and foto_tag.get('src') else None
            cursor.execute("SELECT id FROM desaparecidos WHERE foto_url = ?", (foto_url,))
            if cursor.fetchone():
                if stop_on_duplicate:
                    print(f"⚠️ Foto já existe no banco ({foto_url}). Encerrando varredura incremental.")
                    return True
                else:
                    continue
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
            estado = estado_tag.img['title'] if (estado_tag and estado_tag.img) else None
            cursor.execute("""
            INSERT INTO desaparecidos (nome, idade, sexo, desapareceu_em, local, vestimenta, instituicao, estado, foto_url, pagina, status, fonte)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nome, idade, sexo, desapareceu_em, local, vestimenta, instituicao, estado, foto_url, page, "new", "desaparecidosbrasil.org"))
            conn.commit()
            registro_id = cursor.lastrowid
            baixar_imagem(conn, cursor, foto_url, registro_id)
        print(f"✅ Página {page} de desaparecidosbrasil.org processada.")
        page += 1
        time.sleep(0.3)  
    return False

def scrape_cnpd(conn, cursor, stop_on_duplicate: bool):
    print("\n---  scraping cnpd.mj.gov.br ---")
    API_URL = "https://cnpd.mj.gov.br/api/api/painel-publico/desaparecidos/filtrar"
    HEADERS = { 'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7', 'Connection': 'keep-alive', 'Content-Type': 'application/json', 'Origin': 'https://cnpd.mj.gov.br', 'Referer': 'https://cnpd.mj.gov.br/painel-publico', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36', }
    mapa_uf_estado = { 'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo', 'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina', 'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins' }
    pagina_atual = 0
    while True:
        params = { 'ordenacao': 'MAIS_RECENTE', 'pagina': pagina_atual, 'quantidade': 50, }
        json_data = {}
        try:
            response = requests.post( API_URL, headers=HEADERS, params=params, json=json_data, proxies=PROXIES, verify=False, timeout=60 )
            response.raise_for_status()
            data = response.json()
            pessoas_na_pagina = data.get('desaparecidos', [])
            if not pessoas_na_pagina:
                print("\nExtração do CNPD concluída: Não há mais páginas.")
                break
            for pessoa in tqdm(pessoas_na_pagina, desc=f"CNPD página {pagina_atual}", unit="registro"):
                pessoa_id = pessoa.get('id')
                foto_url = f"https://cnpd.mj.gov.br/api/pessoas/{pessoa_id}/foto" if pessoa_id else None
                cursor.execute("SELECT id FROM desaparecidos WHERE id = ? AND fonte = ?", (pessoa_id, "cnpd.mj.gov.br"))
                if cursor.fetchone():
                    if stop_on_duplicate:
                        print(f"\n⚠️ Registro ID {pessoa_id} já existe no banco. Encerrando varredura incremental do CNPD.")
                        return
                    else:
                        continue
                uf = pessoa.get('ufRegistro')
                estado_nome = mapa_uf_estado.get(uf) if uf and uf in mapa_uf_estado else None
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
                baixar_imagem(conn, cursor, foto_url, pessoa_id)
            pagina_atual += 1
            time.sleep(0.5)
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Erro ao conectar à API do CNPD na página {pagina_atual}: {e}")
            break

def consulta_nao_especificados(cursor):
    """Executa a consulta de diagnósticos."""
    cursor.execute("SELECT fonte, COUNT(*) as quantidade FROM desaparecidos WHERE estado IS NULL OR estado = '' GROUP BY fonte; ")
    resultados = cursor.fetchall()
    print("Resultados da consulta 'Não Específicos':")
    if not resultados:
        print("Nenhum registro com estado não especificado.")
        return
    for row in resultados:
        print(f"Fonte: {row[0]}, Quantidade: {row[1]}")

def main():
    """Função principal para executar o scraping."""
    
    # Garante que a pasta de imagens exista
    os.makedirs(IMG_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM desaparecidos")
    total = cursor.fetchone()[0]
    stop_on_duplicate = total > 0

    print(f"📊 Registros atuais no banco: {total}")
    if stop_on_duplicate:
        print("🔎 Modo incremental (parar ao encontrar duplicata).")
    else:
        print("🆕 Banco vazio, varrendo todas as páginas.")
    
    scrape_desaparecidos_brasil(conn, cursor, stop_on_duplicate)
    scrape_cnpd(conn, cursor, stop_on_duplicate)
    
    print("\n 🚀 Varredura de todas as fontes concluída.")
    
    print("Verificando total de não especificados...")
    consulta_nao_especificados(cursor)

    conn.close()
    print("Conexão do Scraper com o banco de dados fechada.")

if __name__ == "__main__":
    # Permite que este script seja executado de forma independente para testes
    print("--- EXECUTANDO SCRAPER DIRETAMENTE PARA TESTES ---")
    main()