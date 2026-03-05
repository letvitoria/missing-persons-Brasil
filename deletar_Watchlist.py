import requests
import base64
import json

#Configurações de Acesso 
HOST = '10.69.7.31'
WATCHLIST_ID = 22  # ID da Watch list
username = 'linux'
password = 'ubuntuff2025'

#Autenticação 
encoded_credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')
auth_url = f'http://{HOST}/auth/login/'

print(f"Iniciando processo para limpar a Watchlist ID: {WATCHLIST_ID}")

try:
    auth_response = requests.post(
        auth_url, 
        headers={'Authorization': f'Basic {encoded_credentials}'}, 
        json={"uuid": "1D9D84D5-E18C-1407-4F77-8F29EF7F5A07", "mobile": False},
        timeout=10
    )
    token = auth_response.json().get('token')
    if not token:
        print("❌ Erro: Não foi possível obter o token.")
        exit()
except Exception as e:
    print(f"❌ Erro na conexão: {e}")
    exit()

headers = {'Authorization': f'Token {token}', 'Content-Type': 'application/json'}

#Buscar todos os Cards da Watchlist 
#O FindFace permite filtrar por watch_lists na URL de busca
url_cards = f'http://{HOST}/cards/humans/'
params = {
    'watch_lists': WATCHLIST_ID,
    'limit': 1000  # Ajuste o limite conforme necessário
}

try:
    response = requests.get(url_cards, headers=headers, params=params)
    if response.status_code == 200:
        cards = response.json().get('results', [])
        total = len(cards)
        print(f"🔍 Encontrados {total} cards para exclusão.")
        
        #Deletar cada Card encontrado ---
        sucesso = 0
        erro = 0
        
        for card in cards:
            card_id = card['id']
            nome = card.get('name', 'Sem Nome')
            url_delete = f'{url_cards}{card_id}/'
            
            del_resp = requests.delete(url_delete, headers=headers)
            
            if del_resp.status_code == 204:
                print(f"✅ Card {card_id} ({nome}) deletado.")
                sucesso += 1
            else:
                print(f"❌ Falha ao deletar card {card_id}: {del_resp.status_code}")
                erro += 1
        
        print("\n" + "="*30)
        print(f"RELATÓRIO FINAL:")
        print(f"Sucessos: {sucesso}")
        print(f"Falhas: {erro}")
        print("="*30)
        
    else:
        print(f"❌ Erro ao buscar cards: {response.status_code} - {response.text}")

except Exception as e:
    print(f"❌ Ocorreu um erro durante o processamento: {e}")

print("\n--- Processo Finalizado ---")