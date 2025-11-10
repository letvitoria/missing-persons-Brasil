#Antigo run.py / agora manage.py para funcionar como gerenciador
#Funcionalidades:
# - Iniciará o agendador (APScheduler).
# - Configurará o agendador para rodar seu web_scraping.py todos os dias em um horário específico 
# - Iniciará o seu servidor web waitress (que ficará rodando 24/7 para servir o mapa).

import os
import logging
from waitress import serve
from apscheduler.schedulers.background import BackgroundScheduler
from app.main import create_app


#usando a função main from web scraping.py
try:
    from web_scraping import main as scraper_main
    SCRAPER_DISPONIVEL = True
except ImportError as e:
    print(f"AVISO: 'web_scraping.py' não foi encontrado. {e}")
    SCRAPER_DISPONIVEL = False

# Configuração de Log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#DEfinicção de tarefa agendada 
def agendar_tarefa_scraping():
    #Essa função será chamada diariamente
    if not SCRAPER_DISPONIVEL:
        logging.warning("[AGENDADO] Scraping ignorado (arquivo não encontrado)")
        return
    logging.info("---[AGENDADO] SCRAPING DIÁRIO CONCLUÍDO ---")
    try:
        scraper_main()
        logging.info("-- [AGENDADO] SCRAPING DIÁRIO CONCLUÍDO")
    except Exception as e:
        logging.info("[AGENDADO] ERRO AO EXECUTAR SCRAPING DIÁRIO {e}", exc_info=True)

if __name__ == "__main__":
    logging.info("Configurando o agendador de tarefas...")
    scheduler = BackgroundScheduler(daemon=True)
    #Configurando o trigger para rodar no horário definido:
    scheduler.add_job(agendar_tarefa_scraping, trigger='cron', hour=10, minute =35)
    #Inicia o agendador em um thread de fundo
    scheduler.start()
    logging.info("Agendador iniciado. O scraping rodará diariamente às #.")
    
    logging.info("--- [INICIALIZAÇÃO] Executando o scraping pela primeira vez... ---")
    agendar_tarefa_scraping()
    logging.info("--- [INICIALIZAÇÃO] Scraping inicial concluído. ---")
    
    #Iniciando servidor web
    logging.info("Inicniando servidor Web")
    app = create_app()
    port = int(os.environ.get("PORT", 5001)) 
    logging.info(f"Servidor pronto. Acesse na sua rede em: http://0.0.0.0:{port}")
    serve(app, host='0.0.0.0', port=port)



