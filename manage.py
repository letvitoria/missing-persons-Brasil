import os
import logging
import runpy
from waitress import serve
from apscheduler.schedulers.background import BackgroundScheduler
from app.main import create_app

#Importa init_db para garantir que o banco existe
from app.models.database import init_db 

#Importa o scraper
try:
    from web_scraping import main as scraper_main
    SCRAPER_DISPONIVEL = True
except ImportError as e:
    print(f"ERRO: 'web_scraping.py' não foi encontrado. {e}")
    SCRAPER_DISPONIVEL = False

#Local dos scripts adicionais que devem rodar após o scraping

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENVIAR_FF_PATH = os.path.join(BASE_DIR, "enviar_ff.py")
INACTIVATE_CARDS_PATH =  os.path.join(BASE_DIR, "inactivate_cards.py")

ENVIAR_FF_DISPONIVEL = os.path.exists(ENVIAR_FF_PATH)
INACTIVATE_CARDS_DISPONIVEL = os.path.exists(INACTIVATE_CARDS_PATH)

# Configuração de Log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def agendar_tarefa_scraping():
    # Chamada diariamente
    if not SCRAPER_DISPONIVEL:
        logging.warning("[AGENDADO] Scraping ignorado (arquivo não encontrado)")
        return
    logging.info("[AGENDADO] INICIANDO SCRAPING DIÁRIO ---")
    try:
        print("XXXXXX")
    except:
        print("XXXXX")
    try:
        scraper_main()
        logging.info("--- [AGENDADO] SCRAPING DIÁRIO CONCLUÍDO ---")
            #Após atualizar o mapa (scraping), executar os scripts auxiliares, se disponíveis
        try:
            if ENVIAR_FF_DISPONIVEL:
                logging.info("Executando script: enviar_ff.py")
                runpy.run_path(ENVIAR_FF_PATH, run_name="__main__")
                logging.info("Script enviar_ff.py concluído")
            else:
                logging.warning("Script enviar_ff.py não encontrado; pulando execução")
        except Exception as e:
            logging.error(f"Erro ao executar enviar_ff.py: {e}", exc_info=True)

        try:
            if INACTIVATE_CARDS_DISPONIVEL:
                logging.info("Executando script: inactivate_cards.py")
                runpy.run_path(INACTIVATE_CARDS_PATH, run_name="__main__")
                logging.info("Script inactivate_cards.py concluído")
            else:
                logging.warning("Script inactivate_cards.py não encontrado; pulando execução")

        except Exception as e:
            logging.error(f"Erro ao executar inactivate_cards.py: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"[AGENDADO] ERRO AO EXECUTAR SCRAPING DIÁRIO: {e}", exc_info=True)

if __name__ == "__main__":
    
    # Iniciar o banco de dados
    logging.info("Verificando/Inicializando banco de dados...")
    try:
        init_db()
        logging.info("Banco de dados pronto.")
    except Exception as e:
        logging.error(f"Erro fatal ao inicializar banco de dados: {e}")
        exit(1) # Para o script se não tiver banco


    logging.info("Configurando o agendador de tarefas...")
    scheduler = BackgroundScheduler(daemon=True)
    # Configurando o trigger para rodar no horário definido:
    scheduler.add_job(agendar_tarefa_scraping, trigger='cron', hour=10, minute=00)
    scheduler.start()
    logging.info("Agendador iniciado. O scraping rodará diariamente às 10:00h")
    
    # Iniciando servidor web
    logging.info("Iniciando servidor Web")
    app = create_app()
    port = int(os.environ.get("PORT", 5001)) 
    logging.info(f"Servidor pronto. Acesse na sua rede em: http://localhost:{port}")
    serve(app, host='0.0.0.0', port=port)