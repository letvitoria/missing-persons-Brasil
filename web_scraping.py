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
# Criamos uma classe simples para forçar o download sem verificar SSL
class WDMHttpClient(HttpClient):
    def get(self, url, params=None, **kwargs):
        # Adicionamos verify=False aqui para ignorar o erro de certificado
        return requests.get(url, params, verify=False, proxies=PROXIES, **kwargs)

# Configuração de variáveis de ambiente para o sistema
os.environ['WDM_SSL_VERIFY'] = '0' # Comando específico do WebDriver Manager
os.environ['HTTP_PROXY'] = PROXIES['http']
os.environ['HTTPS_PROXY'] = PROXIES['https']

print(f"✔️ Tentando baixar ChromeDriver com bypass SSL...")

try:
    # Passamos o nosso HttpClient customizado para o manager
    driver_path = ChromeDriverManager().install()
    
    print(f"✅ ChromeDriver localizado e iniciado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao instalar driver: {e}")
finally:
    # Limpa as variáveis de ambiente para não afetar outras partes do sistema
    if 'HTTP_PROXY' in os.environ: del os.environ['HTTP_PROXY']
    if 'HTTPS_PROXY' in os.environ: del os.environ['HTTPS_PROXY']

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
        cards_processados_pagina = 0 # <--  Contador de cards

        for card in cards:
            cards_processados_pagina += 1 # <-- Conta este card

            card_text = card.get_text().lower()
            # Definindo situação para casos de localizado e falecido;
            situacao = "desaparecido" #Sitação definida como desaparecido
            if "localizada" in card_text or "localizado" in card_text:
                situacao = "localizado" 
            elif "falecida" in card_text or "falecido" in card_text:
                situacao = "falecido"

            foto_tag = card.find("img", class_="pessoa-img")
            foto_url_relative = foto_tag['src'] if foto_tag and foto_tag.get("src") else ""
            #Monta a url 
            foto_url = urljoin("https://desaparecidosdobrasil.org/",foto_url_relative)

            #Ignorar registros sem foto válida
            if 'sem-foto' in foto_url_relative.lower() or not foto_url_relative:
                nome_ignorado = card.find("h4").get_text(strip=True) if card.find("h4") else "Desconhecido"
                logging.info(f"⏭️ Ignorando registro (Sem foto válida): {nome_ignorado}")
                continue #Passa para o próximo card

            # Daqui para baixo o código só executa se houver uma foto real
            card_text = card.get_text().lower()

            cursor.execute("SELECT id, img_path, situacao FROM desaparecidos WHERE foto_url = ?", (foto_url,))
            registro_existente = cursor.fetchone()

            if registro_existente:
                registro_id = registro_existente['id'] if hasattr(registro_existente, 'keys') else registro_existente[0]
                img_path = registro_existente['img_path'] if hasattr(registro_existente, 'keys') else registro_existente[1]
                existing_situacao = registro_existente['situacao'] if hasattr(registro_existente, 'keys') else (registro_existente[2] if len(registro_existente) > 2 else None)

                # Atualização no banco de dados para o caso da situação responder a conficional
                if situacao in ("localizado", "falecido") and existing_situacao != situacao:
                    cursor.execute("UPDATE desaparecidos SET situacao = ? WHERE id = ?", (situacao, registro_id))
                    conn.commit()
                    logging.info(f"🔄 Registro {registro_id} ('{card.find('h4').get_text(strip=True) if card.find('h4') else registro_id}') atualizado para status '{situacao}'.")

                # Ensure image exists on disk
                if not img_path or not os.path.exists(img_path):
                    logging.warning(f"⚠️ Registro {registro_id} existe no DB, mas imagem falta no disco. Baixando...")
                    baixar_imagem(conn, cursor, foto_url, registro_id)

                if stop_on_duplicate and situacao not in ("localizado", "falecido"):
                    # Existing record found and incremental mode requested -> stop
                    print(f"⚠️ Foto já existe no banco ({foto_url}). Encerrando varredura incremental.")
                    return True
                else:
                    # Existing record handled (possibly updated). Continue scanning.
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
            INSERT INTO desaparecidos (nome, idade, sexo, desapareceu_em, local, vestimenta, instituicao, estado, foto_url, pagina, status, fonte, situacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
            """, (nome, idade, sexo, desapareceu_em, local, vestimenta, instituicao, estado, foto_url, page, "new", "desaparecidosbrasil.org", situacao))
            conn.commit()
            registro_id = cursor.lastrowid
            baixar_imagem(conn, cursor, foto_url, registro_id)
        
        # ---  Lógica Anti-Loop Infinito ---
        if stop_on_duplicate and novos_registros_encontrados_pagina == 0:
            print(f"--- Nenhum registro novo encontrado na página {page}. Encerrando modo incremental. ---")
            break
        
        if not stop_on_duplicate and novos_registros_encontrados_pagina == 0 and cards_processados_pagina > 0:
            print(f"--- Página {page} só continha duplicatas! Encerrando varredura... ---")
            break
        # --- FIM DA CORREÇÃO ---

        print(f"✅ Página {page} de desaparecidosbrasil.org processada.")
        page += 1
        time.sleep(0.3)
    return False
#Fim da função desaparecidos do Brasil
#JavaScript para extração dos dados em CNPD
JS_SCRAPER_SCRIPT = """
    var cards = document.querySelectorAll('.pessoa-card');
    var data = [];
    
    cards.forEach(card => {
        var info = card.querySelector('.pessoa-info');
        if (!info) return;

        var nome = info.querySelector('h3') ? info.querySelector('h3').innerText.trim() : null;
        var imgEl = card.querySelector('.pessoa-foto');
        var base64_src = imgEl ? imgEl.getAttribute('src') : null;
        
        // Extração robusta: Pegamos todos os <p> e filtramos pelo conteúdo
        var paragrafos = Array.from(info.querySelectorAll('p')).map(p => p.innerText);
        
        // Função auxiliar para encontrar o valor após o rótulo
        function buscarValor(lista, termo) {
            let linha = lista.find(t => t.toLowerCase().includes(termo.toLowerCase()));
            return linha ? linha.split(':')[1].trim() : "Não informado";
        }

        data.push({
            "nome": nome,
            "base64_src": base64_src,
            "idade": buscarValor(paragrafos, 'idade'),
            "sexo": buscarValor(paragrafos, 'sexo'), // Busca "Sexo" ou "Sexo/Gênero"
            "desapareceu_em": buscarValor(paragrafos, 'data'),
            "local": buscarValor(paragrafos, 'local')
        });
    });
    return data;
"""

# Scraping_CNPD
def scrape_cnpd(conn, cursor, stop_on_duplicate=True):
    print("\n--- 🕵️ Iniciando scraping de cnpd.mj.gov.br ---")

    # Definimos o caminho COMPLETO para onde o zip DEVE ser criado
    plugin_file = os.path.join(BASE_DIR_SCRAPER, 'proxy_auth_plugin.zip')
    manifest_path = os.path.join(BASE_DIR_SCRAPER, 'manifest.json')
    background_path = os.path.join(BASE_DIR_SCRAPER, 'background.js')
    
    # 1. Criação do Plugin de Proxy
    try:
        # Usamos o caminho absoluto plugin_file para garantir que ele seja criado na pasta certa
        with zipfile.ZipFile(plugin_file, 'w') as zp:
            zp.write(manifest_path, 'manifest.json')
            zp.write(background_path, 'background.js')
        print(f"✅ Plugin de proxy criado com sucesso em: {plugin_file}")
    except FileNotFoundError as e:
        logging.error(f"❌ Erro ao criar plugin: Certifique-se que manifest.json e background.js estão em {BASE_DIR_SCRAPER}")
        return

    # 2. Configuração do Driver
    os.environ['WDM_SSL_VERIFY'] = '0'
    os.environ['HTTP_PROXY'] = PROXIES['http']
    os.environ['HTTPS_PROXY'] = PROXIES['https']
    
    driver = None
    try:
        # Instalamos o driver sem argumentos extras que causam erro
        chrome_service = Service(ChromeDriverManager().install())
        
        if 'HTTP_PROXY' in os.environ: del os.environ['HTTP_PROXY']
        if 'HTTPS_PROXY' in os.environ: del os.environ['HTTPS_PROXY']

        options = Options()
        # AGORA o Selenium vai encontrar o arquivo porque o caminho é absoluto
        options.add_extension(plugin_file) 
        
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")

        driver = webdriver.Chrome(service=chrome_service, options=options)
        
        print("--- Aplicando patches 'stealth' para evitar detecção... ---")
        stealth(driver,
                languages=["pt-BR", "pt"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True)

        PAGE_URL = "https://cnpd.mj.gov.br/painel-publico"
        print(f"--- Acessando a página principal ({PAGE_URL})... ---")
        driver.get(PAGE_URL) 
        
        # 3. Espera pelo carregamento inicial
        try:
            print("--- Esperando até 15s pelo primeiro card... ---")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".pessoa-card"))
            )
            print("--- Página principal carregada e cards detectados. ---")
        except TimeoutException:
            logging.error("❌ Timeout: Cards não encontrados. O bloqueio anti-bot pode estar ativo.")
            return

        pagina_atual = 1
        
        # 4. Loop de Scraping
        while True:
            # Logo após o clique no botão 'Próxima' ou no início do loop da página:
            print(f"--- Aguardando renderização completa da página {pagina_atual}... ---")
            time.sleep(5)  # Aumente de 2 para 5 segundos para garantir que o texto do <p> apareça
            page_data = driver.execute_script(JS_SCRAPER_SCRIPT)
            
            # Rolagem para carregar imagens Lazy Load
            last_height = driver.execute_script("return document.body.scrollHeight")
            for _ in range(5): 
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1) 
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height: break
                last_height = new_height

            page_data = driver.execute_script(JS_SCRAPER_SCRIPT) 

            if not page_data and pagina_atual == 1:
                logging.error("❌ Nenhum card encontrado na primeira página.")
                break

            print(f"✅ CNPD encontrou {len(page_data)} registros na página {pagina_atual}.")
            
            novos_registros_encontrados_pagina = 0
                

            for card_data in tqdm(page_data, desc=f"Página {pagina_atual}", unit="reg"):
                try:
                    nome = card_data.get('nome')
                    idade = card_data.get('idade')
                    sexo = card_data.get('sexo') or "Não informado"
                    desapareceu_em = card_data.get('desapareceu_em') or "Não informado"
                    foto_data_base64 = card_data.get('base64_src')
                    
                    # Tratamento do Local: Divide "Manaus/AM" em cidade e estado
                    local_raw = card_data.get('local') or ""
                    cidade = "Não informado"
                    estado = "Não informado"
                    
                    if "/" in local_raw:
                        partes = local_raw.split("/")
                        cidade = partes[0].strip()
                        estado = partes[1].strip()
                    elif local_raw:
                        cidade = local_raw.strip()

                    if not nome: continue

                    # Verificação de Duplicata (Nome, Idade, Cidade)
                    cursor.execute("""
                        SELECT id FROM desaparecidos 
                        WHERE nome = ? AND idade = ? AND local = ? AND fonte = 'cnpd.mj.gov.br'
                    """, (nome, idade, cidade))
                    
                    if cursor.fetchone():
                        if stop_on_duplicate:
                            novos_registros_encontrados_pagina = -1
                            break
                        continue

                    if not (foto_data_base64 and foto_data_base64.startswith("data:image")):
                        continue
                        
                    # Importante para o TCC: Use hashlib para consistência do ID
                    import hashlib
                    cnpd_id_hash = hashlib.md5(foto_data_base64.encode()).hexdigest()
                    
                    # Salva Imagem
                    img_path = os.path.join(IMG_DIR, f"{cnpd_id_hash}.jpg")
                    if not os.path.exists(img_path):
                        _, encoded_data = foto_data_base64.split(",", 1)
                        with open(img_path, "wb") as f:
                            f.write(base64.b64decode(encoded_data))

                    # Inserção Final
                    cursor.execute("""
                        INSERT OR IGNORE INTO desaparecidos (
                            cnpd_id, nome, idade, sexo, desapareceu_em, 
                            local, estado, foto_url, img_path, pagina, 
                            status, fonte, situacao
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        cnpd_id_hash, nome, idade, sexo, desapareceu_em, 
                        cidade, estado, f"cnpd_hash_{cnpd_id_hash}", 
                        img_path, pagina_atual, 'new', 'cnpd.mj.gov.br', 'desaparecido'
                    ))

                    if conn.total_changes > 0:
                        conn.commit()
                        novos_registros_encontrados_pagina += 1

                except Exception as e:
                    logging.error(f"❌ Erro no registro {card_data.get('nome')}: {e}")
                    
# --- LÓGICA DE NAVEGAÇÃO COM ESPERA EXTENDIDA ---
            if novos_registros_encontrados_pagina <= 0:
                print(f"--- 🛑 Fim dos novos registros na página {pagina_atual}. ---")
                break
                
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Próxima página"]')
                
                btn_class = next_button.get_attribute("class") or ""
                btn_disabled = next_button.get_attribute("disabled")
                
                if btn_disabled or "disabled" in btn_class:
                    print("--- 🏁 Última página atingida (Botão desabilitado). ---")
                    break 
                else:
                    # Captura o texto do primeiro card ANTES de clicar (para comparar)
                    primeiro_nome_antes = page_data[0].get('nome') if page_data else ""
                    
                    # Clica no botão de próxima
                    driver.execute_script("arguments[0].click();", next_button)
                    print(f"-- 🔄 Clique efetuado. Aguardando carregamento da página {pagina_atual + 1}... --")
                    
                    # ESPERA INTELIGENTE: Tentará por até 20 segundos (40 iterações de 0.5s)
                    sucesso_mudanca = False
                    for i in range(80): 
                        time.sleep(0.5)
                        # Executa o script JS para ver o que está na tela agora
                        novos_cards = driver.execute_script(JS_SCRAPER_SCRIPT)
                        
                        if novos_cards and len(novos_cards) > 0:
                            primeiro_nome_agora = novos_cards[0].get('nome')
                            
                            # Se o nome mudou, a página finalmente carregou!
                            if primeiro_nome_agora != primeiro_nome_antes:
                                print(f"✅ Página {pagina_atual + 1} carregada com sucesso (após {i/2}s).")
                                sucesso_mudanca = True
                                break
                    
                    if not sucesso_mudanca:
                        print(f"--- ⚠️ Timeout: A página {pagina_atual + 1} demorou mais de 20s para mudar. ---")
                        break
                    
                    pagina_atual += 1

            except (NoSuchElementException, TimeoutException) as e:
                print(f"--- ❌ Falha na navegação: {e}")
                break
    except Exception as e:
        logging.error(f"❌ Falha geral no Selenium: {e}")
    finally:
        if driver:
            driver.quit() 
            logging.info("--- Driver do Selenium fechado. ---")
        if os.path.exists(plugin_file):
            os.remove(plugin_file) 

    print("✅ Scraping CNPD finalizado.")



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