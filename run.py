import os
# 1. Importa o "criador de app" do seu app/main.py
from app.main import create_app

# 2. Importa a função 'main' principal do seu web_scraping.py
#    Damos a ela um nome diferente para evitar confusão.
try:
    from web_scraping import main as scraper_main
    SCRAPER_DISPONIVEL = True
except ImportError as e:
    print(f"AVISO: 'web_scraping.py' não foi encontrado ou tem um erro. {e}")
    print("O scraping não será executado.")
    SCRAPER_DISPONIVEL = False

# --- PONTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":
    
    # --- ETAPA 1: EXECUTAR O SCRAPING ---
    # É aqui que suas funções de scraping são inseridas e executadas
    if SCRAPER_DISPONIVEL:
        print("--- INICIANDO SCRIPT DE SCRAPING ---")
        scraper_main() 
        
        print("--- SCRAPING CONCLUÍDO ---")
    else:
        print("--- SCRAPING IGNORADO ---")
    
    
    app = create_app()
    print("\n--- INICIANDO SERVIDOR WEB ---")
    print(f"Acesse o mapa em: http://127.0.0.1:5001")
    app.run(debug=True, port=5001)
