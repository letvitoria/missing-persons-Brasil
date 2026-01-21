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
import zipfile
import sys
import hashlib
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager #GErenciador de Drivers
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from selenium.webdriver.chrome.service import Service
from webdriver_manager.core.os_manager import OperationSystemManager
from webdriver_manager.core.http import HttpClient
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select


# Desativa os warnings de SSL (verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


#Identifica que o arquivo está na raiz do projero.
BASE_DIR_SCRAPER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR_SCRAPER)
#Garante que o python consiga 'ver' a pasta app
if BASE_DIR_SCRAPER not in sys.path:
    sys.path.insert(0, BASE_DIR_SCRAPER)
#Importa configurações from database
try:
    from app.models.database import DB_PATH, PROXIES, IMG_DIR
    DB_NAME = DB_PATH
    print(f"✅ Configurações importadas com sucesso!")
    print(f"Banco de dados: {DB_NAME}")
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("--- Usando configurações de feedback forçadas ---")
    #Informando manualmente o caminho para o arquivo do banco de dados. 
    DB_NAME = os.path.join(BASE_DIR_SCRAPER, "pessoasdesaparecidas.db")
    PROXIES = {
        "http": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080',
        "https": 'https://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080'
    }
    IMG_DIR = os.path.join(BASE_DIR_SCRAPER, "source")
#Classe para forçar o download sem verificar SSL
class WDMHttpClient(HttpClient):
    def get(self, url, params=None, **kwargs):
        # Adicionamos verify=False aqui para ignorar o erro de certificado
        return requests.get(url, params, verify=False, proxies=PROXIES, **kwargs)

# Configuração de variáveis de ambiente para o sistema
os.environ['WDM_SSL_VERIFY'] = '0' # Comando específico do WebDriver Manager
os.environ['HTTP_PROXY'] = PROXIES['http']
os.environ['HTTPS_PROXY'] = PROXIES['https']
os.environ['no_proxy'] = 'localhost,127.0.0.1'

print(f"✔️ Tentando baixar ChromeDriver com bypass SSL...")

print(f"✔️ Tentando baixar ChromeDriver com bypass SSL...")

try:
    # Criamos a instância do cliente que usa suas credenciais do DPF
    wdm_client = WDMHttpClient()
    chrome_service = Service(ChromeDriverManager(http_client=wdm_client).install())
    
    print(f"✅ ChromeDriver localizado e iniciado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao instalar driver: {e}")

print(f"ChromeDriver localizado com sucesso!")

os.makedirs(IMG_DIR, exist_ok=True) 


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
    print("\n--- 🕵️ scraping desaparecidosbrasil.org (Ajustes Finais de Localidade) ---")
    BASE_URL = "https://desaparecidosbrasil.org/?page={}"
    page = 1
    
    # Variável para controlar duplicadas consecutivas
    consecutive_duplicates = 0
    
    while True:
        url = BASE_URL.format(page)
        print(f"--- Acessando página {page}... ---")
        try:
            r = requests.get(url, proxies=PROXIES, timeout=30, verify=False)
            if r.status_code != 200: break
        except Exception: break

        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.person-card")
        if not cards: break

        novos_nesta_pagina = 0

        for card in cards:
            # 1. EXTRAÇÃO DA SITUAÇÃO
            card_text = card.get_text().lower()
            situacao = "desaparecido" 
            if "localizada" in card_text or "localizado" in card_text:
                situacao = "localizado" 
            elif "falecida" in card_text or "falecido" in card_text:
                situacao = "falecido"

            nome = card.find("h4").get_text(strip=True) if card.find("h4") else "Desconhecido"
            
            foto_tag = card.find("img", class_="pessoa-img")
            foto_url_rel = foto_tag['src'] if foto_tag and foto_tag.get('src') else ""
            if 'sem-foto' in foto_url_rel.lower() or not foto_url_rel:
                continue

            foto_url = urljoin("https://desaparecidosbrasil.org/", foto_url_rel)

            
            cursor.execute("SELECT id FROM desaparecidos WHERE foto_url = ?", (foto_url,))
            if cursor.fetchone():
                if stop_on_duplicate:
                    consecutive_duplicates += 1
                    print(f"⚠️ Registro repetido ({nome}). Duplicadas seguidas: {consecutive_duplicates}")
                    
                    if consecutive_duplicates >= 2:
                        print(f"🛑 Duas duplicadas seguidas encontradas. Encerrando scraping.")
                        return True
                    
                    # Pula para o próximo card sem encerrar o loop total ainda
                    continue
                continue

            #Registro Novo
            consecutive_duplicates = 0 # Reseta o contador pois achou um registro inédito
            novos_nesta_pagina += 1
            
            foto_id_hash = hashlib.md5(foto_url.encode()).hexdigest()
            file_path = os.path.join(IMG_DIR, f"{foto_id_hash}.jpg")

            #Extração de UF
            estado_tag = card.find("div", class_="estado-bandeira-container")
            estado = estado_tag.img['title'] if (estado_tag and estado_tag.img) else None

            idade = sexo = desapareceu_em = local = instituicao = None
            for p in card.find_all("p"):
                txt = p.get_text().lower()
                val_bruto = p.get_text(" ", strip=True).split(':')[-1].strip()
                
                if "idade" in txt: idade = val_bruto
                elif "sexo" in txt: sexo = val_bruto
                elif "desapareceu" in txt: desapareceu_em = val_bruto
                elif "instituição" in txt: instituicao = val_bruto
                elif "local" in txt and "localizado" not in txt:
                    local = re.split(r'[\-,/]', val_bruto)[0].strip()

            try:
                img_data = requests.get(foto_url, verify=False, proxies=PROXIES, timeout=20).content
                with open(file_path, 'wb') as f:
                    f.write(img_data)
                print(f"📸 Foto salva: {nome} ✅")
            except Exception as e:
                print(f"❌ Erro ao baixar foto de {nome}: {e}")
                continue

            #Inserção no BD
            cursor.execute("""
                INSERT INTO desaparecidos 
                (cnpd_id, nome, idade, sexo, desapareceu_em, local, instituicao, estado, foto_url, img_path, pagina, status, fonte, situacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (foto_id_hash, nome, idade, sexo, desapareceu_em, local, instituicao, estado, foto_url, file_path, page, "new", "desaparecidosbrasil.org", situacao))
            
            conn.commit()
            
        print(f"✅ Página {page} processada. ({novos_nesta_pagina} novos registros)")
        page += 1
        time.sleep(1)

    return False
#Fim da função desaparecidos do Brasil
#JavaScript para extração dos dados em CNPD
JS_SCRAPER_SCRIPT = """
    function matchRegex(texto, regex) {
        let m = texto.match(regex);
        return m ? m[1].trim() : null;
    }

    let card = arguments[0];
    if (!card) return null;

    let textoCard = card.innerText;
    let textoPagina = document.body.innerText;

    return {
        modal_carregado: true,

        idade: matchRegex(textoCard, /(\\d+\\s+anos?)/i),

        desapareceu_em: matchRegex(textoCard, /(\\d{2}\\/\\d{2}\\/\\d{4})/),

        local: matchRegex(
            textoPagina,
            /Local do registro\\s*:\\s*([A-Za-zÀ-ÿ\\s]+\\/\\s*[A-Z]{2})/
        ),

        sexo: matchRegex(
            textoPagina,
            /Sexo\\/Gênero\\s*:\\s*(Masculino|Feminino)/i
        )
    };
"""

# Scraping_CNPD
def scrape_cnpd(conn, cursor, stop_on_duplicate=True):
    print("\n--- 🕵️ Iniciando scraping de cnpd.mj.gov.br (Arrumando apenas o path da imagem) ---")

    # --- Preparação do plugin de proxy ---
    plugin_file = os.path.join(BASE_DIR_SCRAPER, 'proxy_auth_plugin.zip')
    try:
        with zipfile.ZipFile(plugin_file, 'w') as zp:
            zp.write(os.path.join(BASE_DIR_SCRAPER, 'manifest.json'), 'manifest.json')
            zp.write(os.path.join(BASE_DIR_SCRAPER, 'background.js'), 'background.js')
    except Exception as e:
        logging.error(f"❌ Erro ao preparar proxy: {e}")
        return
    try:
        chrome_service = Service(ChromeDriverManager().install())
    except Exception as e:
        logging.error(f"❌ Erro ao iniciar ChromeDriver: {e}")
        return
    

    options = Options()
    options.add_extension(plugin_file)
    options.add_argument("--proxy-bypass-list=localhost;127.0.0.1")
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--no-sandbox')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(service=chrome_service, options=options)
    stealth(driver, languages=["pt-BR", "pt"], vendor="Google Inc.", platform="Win32", fix_hairline=True)

    try:
        driver.get("https://cnpd.mj.gov.br/painel-publico")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".pessoa-card"))
        )

        pagina_atual = 1

        while True:
            print(f"\n📄 Processando página {pagina_atual}...")
            time.sleep(3)

            index = 0
            novos_registros_encontrados_pagina = 0

            while True:
                cards_elements = driver.find_elements(By.CSS_SELECTOR, ".pessoa-card")

                if index >= len(cards_elements):
                    break

                card_el = cards_elements[index]
                nome_atual = "Localizando..."

                try:
                    nome_atual = card_el.find_element(By.TAG_NAME, "h3").text.strip()

                    # --- Expansão do card ---
                    modal_abriu = False
                    card_data = None

                    for _ in range(3):
                        try:
                            driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'center'});",
                                card_el
                            )
                            time.sleep(1)

                            btn = card_el.find_element(By.CSS_SELECTOR, "button, .fa-plus")
                            driver.execute_script("arguments[0].click();", btn)

                            for _ in range(15):
                                card_data = driver.execute_script(JS_SCRAPER_SCRIPT, card_el)
                                if card_data and card_data.get("modal_carregado"):
                                    modal_abriu = True
                                    break
                                time.sleep(1)

                            if modal_abriu:
                                break
                        except Exception:
                            time.sleep(1)

                    if not modal_abriu or not card_data:
                        logging.warning(f"⚠️ Falha ao carregar dados de {nome_atual}")
                        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        index += 1
                        continue

                    # --- Limpeza dos dados ---
                    idade_valor = card_data.get("idade")
                    sexo = card_data.get("sexo")
                    if idade_valor != "Não informado":
                        m = re.search(r"\d+\s+anos?", idade_valor)
                        idade_valor = m.group(0) if m else idade_valor
                    

                    desapareceu_em = card_data.get("desapareceu_em")
                    if desapareceu_em != "Não informado":
                        m = re.search(r"\d{2}/\d{2}/\d{4}", desapareceu_em)
                        desapareceu_em = m.group(0) if m else desapareceu_em
                    local_match = card_data.get("local")

                    cidade = "Não informado"
                    estado = "Não informado"

                    if local_match:
                        partes = re.split(r"/", local_match)
                        if len(partes) == 2:
                            cidade = partes[0].strip()
                            estado = partes[1].strip()

                    # --- Duplicados ---
                    cursor.execute(
                        "SELECT id FROM desaparecidos WHERE nome = ? AND local = ?",
                        (nome_atual, cidade)
                    )
                    if cursor.fetchone():
                        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        index += 1
                        continue

                    # --- ID único ---
                    cnpd_id_hash = hashlib.md5(
                        f"{nome_atual}{cidade}{desapareceu_em}".encode()
                    ).hexdigest()

                    img_path = os.path.join(IMG_DIR, f"{cnpd_id_hash}.jpg")

                    # --- Inserção no banco ---
                    cursor.execute("""
                        INSERT OR IGNORE INTO desaparecidos (
                            cnpd_id, nome, idade, sexo, desapareceu_em,
                            local, estado, foto_url, img_path,
                            pagina, status, fonte, situacao
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        cnpd_id_hash,
                        nome_atual,
                        idade_valor,
                        sexo,
                        desapareceu_em,
                        cidade,
                        estado,
                        f"cnpd_hash_{cnpd_id_hash}",
                        img_path,
                        pagina_atual,
                        "new",
                        "cnpd.mj.gov.br",
                        "desaparecido"
                    ))

                    conn.commit()
                    novos_registros_encontrados_pagina += 1

                    print(f"✅ Salvo: {nome_atual} | Data: {desapareceu_em}")

                    webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                    time.sleep(0.5)

                except Exception as e:
                    logging.error(f"❌ Erro no card {index}: {e}")
                    webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()

                index += 1

            if novos_registros_encontrados_pagina <= 0:
                print("ℹ️ Nenhum novo registro nesta página. Avançando...")

            try:
                next_button = driver.find_element(
                    By.CSS_SELECTOR, 'button[aria-label="Próxima página"]'
                )
                if next_button.is_enabled():
                    driver.execute_script("arguments[0].click();", next_button)
                    pagina_atual += 1
                    time.sleep(5)
                else:
                    break
            except:
                break

    finally:
        driver.quit()
        if os.path.exists(plugin_file):
            os.remove(plugin_file)

    print("✅ Scraping CNPD finalizado.")


    #Fim da função de CNPD
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

# --- FUNÇÃO MAIN ---
def main():
    """Função principal para executar o scraping."""
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    os.makedirs(IMG_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM desaparecidos")
    total = cursor.fetchone()[0]
    stop_on_duplicate = True
    

    print(f"📊 Registros atuais no banco: {total}")
    if stop_on_duplicate:
        print("🔎 Modo incremental (parar ao encontrar duplicata).")
    else:
        print("🆕 Modo completo (varrendo todas as páginas).")
    scrape_desaparecidos_brasil(conn, cursor, stop_on_duplicate) 
    scrape_cnpd(conn, cursor, stop_on_duplicate) 
    
    print("\n 🚀 Varredura de todas as fontes concluída.")
    
    consulta_nao_especificados(cursor)

    conn.close()
    print("Conexão do Scraper com o banco de dados fechada.")

if __name__ == "__main__":
    print("--- EXECUTANDO SCRAPER DIRETAMENTE PARA TESTES ---")
    main()