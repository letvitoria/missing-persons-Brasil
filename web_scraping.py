import requests
import sqlite3
from bs4 import BeautifulSoup
import os
import time
from tqdm import tqdm
from urllib.parse import urljoin
import logging
import base64
import urllib3
import json
import zipfile 

# --- IMPORTAÇÕES PARA V44 (SELENIUM) ---
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth 
# --- FIM DAS NOVAS IMPORTAÇÕES ---

# Desativa os warnings de SSL (verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configurações do Scraper (V44) ---
# (Adiciona o path para corrigir a importação)
BASE_DIR_SCRAPER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR_SCRAPER)

try:
    from app.models.database import DB_NAME, PROXIES, IMG_DIR
    print(f"--- V44: Configurações importadas de database.py (IMG_DIR: {IMG_DIR}) ---")
except ImportError:
    print("Erro: Não foi possível importar 'app.models.database'.")
    DB_NAME = "desaparecidos.db"
    PROXIES = {
        "http": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080',
        "https": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080'
    }
    IMG_DIR = os.path.join(BASE_DIR_SCRAPER, "source")
    print(f"--- V44: Usando IMG_DIR de fallback: {IMG_DIR} ---")

os.makedirs(IMG_DIR, exist_ok=True) 


# --- Funções de Scraping (V44) ---

def baixar_imagem(conn, cursor, foto_url, registro_id, headers_para_download=None):
    if not foto_url:
        return
    file_path = os.path.join(IMG_DIR, f"{registro_id}.jpg")
    
    if os.path.exists(file_path):
        cursor.execute("UPDATE desaparecidos SET img_path = ? WHERE id = ?", (file_path, registro_id))
        conn.commit()
        return 
    try:
        r = requests.get(
            foto_url,
            stream=True,
            timeout=30,
            verify=False,
            proxies=PROXIES, 
            headers=headers_para_download
        )
        if r.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            cursor.execute("UPDATE desaparecidos SET img_path = ? WHERE id = ?", (file_path, registro_id))
            conn.commit()
            logging.info(f"✅ Foto baixada (requests) com sucesso para ID {registro_id}")
        else:
            logging.warning(f"⚠️ Falha ao baixar imagem {foto_url} (status {r.status_code})")
    except Exception as e:
        logging.error(f"❌ Falha ao salvar imagem {foto_url}: {e}")


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
        
        novos_registros_encontrados_pagina = 0
        cards_processados_pagina = 0 # <-- V46/V44: Contador de cards

        for card in cards:
            cards_processados_pagina += 1 # <-- V46/V44: Conta este card
            
            card_text = card.get_text().lower()
            if "localizada" in card_text or "localizado" in card_text or \
               "falecida" in card_text or "falecido" in card_text:
                nome_ignorado = card.find("h4").get_text(strip=True) if card.find("h4") else "ID Desconhecido"
                print(f"↪️  Registro '{nome_ignorado}' ignorado (status 'localizado ou 'falecido).")
                continue
            foto_tag = card.find("img", class_="pessoa-img")
            foto_url = urljoin("https://desaparecidosbrasil.org/", foto_tag['src']) if foto_tag and foto_tag.get('src') else None
            
            cursor.execute("SELECT id, img_path FROM desaparecidos WHERE foto_url = ?", (foto_url,))
            registro_existente = cursor.fetchone()
            
            if registro_existente:
                if stop_on_duplicate:
                    registro_id = registro_existente['id']
                    img_path = registro_existente['img_path']
                    if not img_path or not os.path.exists(img_path):
                        logging.warning(f"⚠️ Registro {registro_id} existe no DB, mas imagem falta no disco. Baixando...")
                        baixar_imagem(conn, cursor, foto_url, registro_id)
                    print(f"⚠️ Foto já existe no banco ({foto_url}). Encerrando varredura incremental.")
                    return True 
                else:
                    continue 
            
            novos_registros_encontrados_pagina += 1
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
            
            # (Assume que database.py (V43) foi aplicado)
            cursor.execute("""
            INSERT INTO desaparecidos (nome, idade, sexo, desapareceu_em, local, vestimenta, instituicao, estado, foto_url, pagina, status, fonte)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nome, idade, sexo, desapareceu_em, local, vestimenta, instituicao, estado, foto_url, page, "new", "desaparecidosbrasil.org"))
            conn.commit()
            registro_id = cursor.lastrowid
            baixar_imagem(conn, cursor, foto_url, registro_id)
        
        # --- CORREÇÃO V46/V44: Lógica Anti-Loop Infinito ---
        if stop_on_duplicate and novos_registros_encontrados_pagina == 0:
            print(f"--- V44: Nenhum registro novo encontrado na página {page}. Encerrando modo incremental. ---")
            break
        
        if not stop_on_duplicate and novos_registros_encontrados_pagina == 0 and cards_processados_pagina > 0:
            print(f"--- V44: Página {page} só continha duplicatas/localizados. Encerrando (provável redirect). ---")
            break
        # --- FIM DA CORREÇÃO ---

        print(f"✅ Página {page} de desaparecidosbrasil.org processada.")
        page += 1
        time.sleep(0.3)
    return False

# --- FUNÇÃO CNPD (V44 - Scraper JS Corrigido) ---
JS_SCRAPER_SCRIPT = """
    var cards = document.querySelectorAll('.pessoa-card');
    var data = [];
    
    for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        
        // --- CORREÇÃO V44: Seletores corretos ---
        var nomeEl = card.querySelector('.pessoa-info h3');
        var imgEl = card.querySelector('.pessoa-foto');
        var pEls = card.querySelectorAll('.pessoa-info p'); // Procura por <p> DENTRO de .pessoa-info
        // --- FIM DA CORREÇÃO ---
        
        var nome = nomeEl ? nomeEl.innerText : null;
        var base64_src = imgEl ? imgEl.getAttribute('src') : null;
        var estado = null;
        
        // --- V44: Adicionar campos faltantes ---
        var idade = null;
        var sexo = null;
        var desapareceu_em = null;
        var local = null;
        // --- FIM DA ADIÇÃO ---

        // --- CORREÇÃO V44: Loop em <p> ---
        if (pEls) {
            for (var j = 0; j < pEls.length; j++) {
                var textoP = pEls[j].innerText;
                if (textoP.includes('Idade atual:')) {
                    try { idade = textoP.split(':')[1].trim(); } catch (e) {}
                } else if (textoP.includes('Sexo:')) {
                    try { sexo = textoP.split(':')[1].trim(); } catch (e) {}
                } else if (textoP.includes('Data de registro do desaparecimento:')) {
                    try { desapareceu_em = textoP.split(':')[1].trim(); } catch (e) {}
                } else if (textoP.includes('Local de registro:')) {
                    try {
                        var localCompleto = textoP.split(':')[1].trim();
                        local = localCompleto.split('/')[0]; // Get "Maceió"
                        estado = localCompleto.split('/')[1]; // Get "AL"
                    } catch (e) { }
                }
            }
        }
        // --- FIM DA CORREÇÃO ---
        
        data.push({
            "nome": nome, 
            "estado": estado, 
            "base64_src": base64_src,
            "idade": idade,
            "sexo": sexo,
            "desapareceu_em": desapareceu_em,
            "local": local
        });
    }
    
    return data;
"""

def scrape_cnpd(conn, cursor, stop_on_duplicate=True):
    print("\n--- 🕵️ Iniciando scraping de cnpd.mj.gov.br (v44 - JS Corrigido) ---")

    plugin_file = 'proxy_auth_plugin.zip'
    
    try:
        with zipfile.ZipFile(plugin_file, 'w') as zp:
            zp.write('manifest.json')
            zp.write('background.js')
    except FileNotFoundError as e:
        logging.error(f"❌ Erro ao criar plugin: Arquivo '{e.filename}' não encontrado.")
        return
    
    options = Options()
    options.add_extension(plugin_file) 
    options.add_argument('--ignore-certificate-errors')
    
    # --- V44: MODO VISÍVEL (Obrigatório para o Stealth funcionar bem) ---
    # options.add_argument('--headless') # Desativado
    print("--- V44: O modo Headless está DESATIVADO. O Chrome será aberto. ---")
    
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = None
    
    DRIVER_PATH = "chromedriver.exe" 
    
    try:
        print("--- V44: Inicializando o driver do Selenium (MODO VISÍVEL)... ---")
        s = Service(DRIVER_PATH)
        driver = webdriver.Chrome(service=s, options=options)
        
        print("--- V44: Aplicando patches 'stealth' para evitar detecção... ---")
        stealth(driver,
                languages=["pt-BR", "pt"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                )

        PAGE_URL = "https://cnpd.mj.gov.br/painel-publico"
        print(f"--- V44: Acessando a página principal ({PAGE_URL})... ---")
        driver.get(PAGE_URL) 
        
        try:
            print("--- V44: Esperando até 15s pelo primeiro card... ---")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".pessoa-card"))
            )
            print("--- V44: Página principal carregada e cards detectados. ---")
        except TimeoutException:
            logging.error("❌ Timeout: A página carregou, mas nenhum card '.pessoa-card' foi encontrado após 15s.")
            logging.error("O bloqueio anti-bot (V44) ainda está ativo.")
            return

        pagina_atual = 1
        
        while True:
            print(f"--- V44: Processando página {pagina_atual}... ---")
            
            print(f"--- V44: Rolando a página {pagina_atual} para carregar imagens... ---")
            last_height = driver.execute_script("return document.body.scrollHeight")
            for _ in range(5): 
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1) 
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            print(f"--- V44: Rolagem concluída. Lendo cards... ---")

            page_data = driver.execute_script(JS_SCRAPER_SCRIPT) # <-- V44 (JS Corrigido)

            if not page_data and pagina_atual == 1:
                logging.error("❌ Nenhum card encontrado na primeira página (V44).")
                break

            print(f"✅ CNPD (JS) encontrou {len(page_data)} registros na página {pagina_atual}.")
            
            novos_registros_encontrados_pagina = 0

            for card_data in tqdm(page_data, desc=f"Processando Página {pagina_atual}", unit="registro"):
                try:
                    cnpd_id_hash = None
                    
                    # --- CORREÇÃO V44: Lendo todos os campos do JS ---
                    nome = card_data.get('nome')
                    estado = card_data.get('estado')
                    foto_data_base64 = card_data.get('base64_src')
                    idade = card_data.get('idade')
                    sexo = card_data.get('sexo')
                    desapareceu_em = card_data.get('desapareceu_em')
                    local = card_data.get('local')
                    # --- FIM DA CORREÇÃO ---

                    if not nome:
                        logging.warning(f"⚠️ Nome não encontrado (provavelmente falha no seletor JS). Pulando.")
                        continue
                    if not (foto_data_base64 and foto_data_base64.startswith("data:image")):
                        logging.warning(f"⚠️ Imagem não era Base64 para '{nome}' (provavelmente falha no lazy-load). Pulando.")
                        continue
                        
                    cnpd_id_hash = str(hash(foto_data_base64))

                    # (Verifica duplicata usando cnpd_id)
                    cursor.execute("SELECT id FROM desaparecidos WHERE cnpd_id = ? AND fonte = 'cnpd.mj.gov.br'", (cnpd_id_hash,))
                    
                    if cursor.fetchone():
                        if stop_on_duplicate:
                            novos_registros_encontrados_pagina = -1 
                            break 
                        continue 

                    novos_registros_encontrados_pagina += 1
                    
                    img_path = None 
                    foto_url_para_db = f"cnpd_hash_{cnpd_id_hash}"

                    img_path_teste = os.path.join(IMG_DIR, f"{cnpd_id_hash}.jpg")
                    if os.path.exists(img_path_teste):
                        img_path = img_path_teste
                    else:
                        try:
                            img_path = os.path.join(IMG_DIR, f"{cnpd_id_hash}.jpg")
                            _, encoded_data = foto_data_base64.split(",", 1)
                            
                            with open(img_path, "wb") as f:
                                f.write(base64.b64decode(encoded_data))
                        
                        except Exception as e_img:
                            logging.error(f"❌ Erro ao salvar imagem para ID {cnpd_id_hash}: {e_img}")
                    
                    # --- CORREÇÃO V44: Inserindo todos os dados raspados ---
                    cursor.execute("""
                        INSERT INTO desaparecidos
                        (cnpd_id, nome, idade, sexo, desapareceu_em, local, instituicao, estado, foto_url, img_path, pagina, status, fonte)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'cnpd.mj.gov.br')
                    """, (
                        cnpd_id_hash, nome, idade, sexo, desapareceu_em, local, 
                        None, # instituicao (não raspamos)
                        estado, foto_url_para_db, img_path, pagina_atual, 'new'
                    ))
                    # --- FIM DA CORREÇÃO ---
                    
                    conn.commit()
                except Exception as e:
                    logging.error(f"❌ Erro ao processar registro (JS Data): {e}")

            if (stop_on_duplicate and novos_registros_encontrados_pagina <= 0):
                if (novos_registros_encontrados_pagina == -1): 
                    print(f"--- V44: Registro duplicado encontrado. Encerrando modo incremental. ---")
                else: 
                    print(f"--- V44: Nenhum registro novo encontrado na página {pagina_atual}. Encerrando modo incremental. ---")
                break 
                
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Próxima página"]')
                
                if next_button.get_attribute("disabled"):
                    print("--- V44: Chegou na última página (botão desabilitado). Encerrando. ---")
                    break 
                else:
                    driver.execute_script("arguments[0].click();", next_button)
                    pagina_atual += 1
                    try:
                        print(f"--- V44: Página {pagina_atual} carregando (esperando 10s)... ---")
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".pessoa-card"))
                        )
                        print(f"--- V44: Página {pagina_atual} carregada. ---")
                    except TimeoutException:
                        logging.error(f"❌ Timeout: A página {pagina_atual} carregou, mas nenhum card foi encontrado.")
                        break
            
            except NoSuchElementException:
                print("--- V44: Botão 'próxima' não encontrado. Encerrando. ---")
                break 

    except Exception as e:
        logging.error(f"❌ Falha geral ao usar Selenium: {e}")
        logging.error("Verifique se o Chrome está instalado e se o proxy está correto.")

    finally:
        if driver:
            driver.quit() 
            print("--- V44: Driver do Selenium fechado. ---")
        if os.path.exists(plugin_file):
            os.remove(plugin_file) 

    print("✅ Scraping CNPD finalizado.")


# --- OUTRAS FUNÇÕES ---

def atualizar_fotos_desaparecidos_brasil(conn, cursor):
    """Verifica o disco e baixa novamente as imagens faltantes do desaparecidosbrasil.org"""
    print("\n--- ♻️ Verificando fotos faltantes (desaparecidosbrasil.org) ---")
    
    cursor.execute("""
        SELECT id, foto_url, img_path 
        FROM desaparecidos 
        WHERE fonte = 'desaparecidosbrasil.org' 
        AND (foto_url IS NOT NULL AND foto_url != '')
    """)
    registros = cursor.fetchall()

    if not registros:
        print("✅ Nenhuma imagem (desaparecidosbrasil.org) para verificar.")
        return

    print(f"--- Verificando {len(registros)} imagens de 'desaparecidosbrasil.org'... ---")
    
    for r in tqdm(registros, desc="Verificando Imagens (desaparecidosbrasil.org)", unit="registro"):
        registro_id = r["id"]
        foto_url = r["foto_url"]
        
        img_path_esperado = os.path.join(IMG_DIR, f"{registro_id}.jpg")

        if not os.path.exists(img_path_esperado):
            logging.warning(f"⚠️ Imagem faltando no disco: {img_path_esperado}. Baixando novamente...")
            baixar_imagem(conn, cursor, foto_url, registro_id)
        
    print("✅ Verificação de fotos (desaparecidosbrasil.org) concluída.")

def consulta_nao_especificados(cursor):
    """Executa a consulta de diagnósticos."""
    cursor.execute("SELECT fonte, COUNT(*) as quantidade FROM desaparecidos WHERE estado IS NULL OR estado = '' GROUP BY fonte; ")
    resultados = cursor.fetchall()
    print("\nResultados da consulta 'Não Específicos':")
    if not resultados:
        print("Nenhum registro com estado não especificado.")
        return
    for row in resultados:
        print(f"Fonte: {row[0]}, Quantidade: {row[1]}")

def atualizar_fotos_cnpd_antigas(conn, cursor):
    """Função obsoleta, mantida para integridade do arquivo."""
    print("\n--- ♻️ Atualizando fotos antigas do CNPD ---")
    
    cursor.execute("SELECT id, foto_url FROM desaparecidos WHERE fonte='cnpd.mj.gov.br' AND (img_path IS NULL OR img_path='')")
    registros = cursor.fetchall()

    if not registros:
        print("✅ Nenhuma imagem pendente para atualizar.")
        return

    for r in tqdm(registros, desc="Atualizando imagens CNPD", unit="registro"):
        pass 
        
# --- FUNÇÃO MAIN (V44) ---
def main():
    """Função principal para executar o scraping."""
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    os.makedirs(IMG_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()

    # (Assume que database.py (V43) foi aplicado)
    atualizar_fotos_desaparecidos_brasil(conn, cursor)

    print("ℹ️ Atualização de fotos antigas (obsoleta) pulada.")
    # atualizar_fotos_cnpd_antigas(conn, cursor) 

    cursor.execute("SELECT COUNT(*) FROM desaparecidos")
    total = cursor.fetchone()[0]
    
    # --- CORREÇÃO V44: Forçar o modo não-incremental (pois limpamos o banco) ---
    stop_on_duplicate = False
    # --- FIM DA CORREÇÃO ---

    print(f"📊 Registros atuais no banco: {total}")
    if stop_on_duplicate:
        print("🔎 Modo incremental (parar ao encontrar duplicata).")
    else:
        print("🆕 Modo completo (varrendo todas as páginas).")
    
    scrape_desaparecidos_brasil(conn, cursor, stop_on_duplicate) 
    scrape_cnpd(conn, cursor, stop_on_duplicate) # <-- Esta é a V44
    
    print("\n 🚀 Varredura de todas as fontes concluída.")
    
    consulta_nao_especificados(cursor)

    conn.close()
    print("Conexão do Scraper com o banco de dados fechada.")

if __name__ == "__main__":
    print("--- EXECUTANDO SCRAPER DIRETAMENTE PARA TESTES ---")
    main()