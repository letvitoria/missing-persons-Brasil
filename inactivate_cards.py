from unidecode import unidecode
import sqlite3
import base64
import requests
import json
import os

# --- 1. Garantia do Caminho do Banco ---
# Isso garante que o Python abra o banco na mesma pasta do script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "pessoasdesaparecidas.db")

if not os.path.exists(db_path):
    print(f"ERRO: O arquivo {db_path} não foi encontrado!")
    exit()

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

def tratar_null(valor):
    return unidecode(str(valor)).strip() if valor is not None else ""

# --- 2. Autenticação ---
username, password = 'linux', 'ubuntuff2025'
encoded_credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')
auth_url = 'http://10.69.7.31/auth/login/'

try:
    auth_response = requests.post(auth_url, 
                                 headers={'Authorization': f'Basic {encoded_credentials}'}, 
                                 json={"uuid": "1D9D84D5-E18C-1407-4F77-8F29EF7F5A07", "mobile": False},
                                 timeout=10)
    token = auth_response.json().get('token')
    if not token:
        print("Erro: Token não obtido.")
        exit()
except Exception as e:
    print(f"Erro na conexão: {e}")
    exit()

# --- 3. Busca no Banco com 'LIKE' (Mais potente que 'IN') ---
# O LIKE com % contorna espaços extras ou problemas de caracteres
query = """
SELECT * FROM desaparecidos 
WHERE situacao LIKE '%localizado%' 
   OR situacao LIKE '%falecido%'
"""
cursor.execute(query)
linhas = cursor.fetchall()

print(f"DEBUG: Registros encontrados no SQLite: {len(linhas)}")

# --- 4. Processamento ---
url_cards = 'http://10.69.7.31/cards/humans/'

for linha in linhas:
    nome = tratar_null(linha['nome'])
    idade_raw = tratar_null(linha['idade'])
    
    print(f"\n>> Tentando inativar: {nome}")

    headers = {'Authorization': f'Token {token}', 'Content-Type': 'application/json'}
    params = {'name_contains': nome, 'watch_lists': '22'}
    
    try:
        resp_busca = requests.get(url_cards, headers=headers, params=params, timeout=10)
        if resp_busca.status_code == 200:
            resultados = resp_busca.json().get('results', [])
            
            for res in resultados:
                # Normalização de idade (apenas dígitos)
                id_local = "".join(filter(str.isdigit, idade_raw))
                id_api = "".join(filter(str.isdigit, tratar_null(res.get('meta', {}).get('idade'))))
                
                if tratar_null(res.get('name')).upper() == nome.upper():
                    human_id = res['id']
                    face_count = res.get('face_objects', 0)
                    
                    url_action = f'http://10.69.7.31/cards/humans/{human_id}/'
                    
                    if face_count == 0:
                        res_api = requests.delete(url_action, headers=headers)
                        status_ok = (res_api.status_code == 204)
                    else:
                        res_api = requests.patch(url_action, headers=headers, json={"active": False})
                        status_ok = (res_api.status_code == 200)

                    if status_ok:
                        print(f"✅ SUCESSO: {nome} inativado na API.")
                        cursor.execute("UPDATE desaparecidos SET situacao = 'inactive' WHERE nome = ?", (linha['nome'],))
                        conn.commit()
                    else:
                        print(f"❌ ERRO API: {res_api.status_code} - {res_api.text}")
                    break
        else:
            print(f"Erro na busca: {resp_busca.status_code}")
    except Exception as e:
        print(f"Erro no processamento de {nome}: {e}")

conn.close()
print("\n--- Processo Finalizado ---")