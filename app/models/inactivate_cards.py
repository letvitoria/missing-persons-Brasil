from unidecode import unidecode
import sqlite3
import base64
import requests
import json


# Caminho para o banco de dados SQLite
db_path = "desaparecidos.db"

# Conectar ao banco de dados SQLite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()


# Detalhes de autenticação básica
username = 'linux'  # Substitua pelo seu nome de usuário ?
password = 'ubuntuff2025'     # Substitua pela sua senha ?

# Codificar o par username:password em base64 para a autenticação básica
credentials = f'{username}:{password}'
encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

# URL para obter o token de autenticação
auth_url = 'http://10.69.7.31/auth/login/'

# Corpo da requisição (dados do dispositivo)
auth_data = {
    "video_auth_token": "A",  # Substitua com o token de autenticação de vídeo, se necessário
    "uuid": "1D9D84D5-E18C-1407-4F77-8F29EF7F5A07",       # Substitua pelo UUID real do seu dispositivo
    "mobile": False,          # Se for um dispositivo móvel ou não
    "device_info": {}         # Informações adicionais sobre o dispositivo (se necessário)
}

# Cabeçalhos da requisição com a autenticação básica
header = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {encoded_credentials}'  # Cabeçalho Basic com a codificação base64
}

# Enviar a requisição POST para obter o token
response = requests.post(auth_url, headers=header, data=json.dumps(auth_data))

# Verificar se a requisição foi bem-sucedida
if response.status_code == 200:
    # O token de autenticação estará na resposta JSON
    auth_response = response.json()
    token = auth_response.get('token')  # Ajuste conforme o nome da chave na resposta
    if token:
        print(f'Token de autenticação obtido: Token {token}')
    else:
        print('Token não encontrado na resposta.')
else:
    print(f'Falha ao obter o token: {response.status_code}')
    print(response.text)

url_cards = 'http://10.69.7.31/cards/humans/' # Da onde? 

# Selecionar as linhas com Status = "new"
cursor.execute("SELECT * FROM desaparecidos WHERE Status = 'new'") #adaptar para o db
linhas = cursor.fetchall()
def tratar_null(valor):
    return unidecode(valor) if valor is not None else ""

for linha in linhas:
    #O que é bnmp?
    bnmp = linha[3]
    nome = tratar_null(linha[4])

    params = {
        'name_contains': nome,
        'meta':{
            'bnmp':bnmp
        }, 
        'watch_lists': '6'
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Token {token}' 
    }

    response2 = requests.get(url_cards, headers=headers, params=params)
    if response2.status_code == 200:
        data = response2.json()
        print (data)
        human_id = None
        for resultado in data.get('results', []):
            nome_encontrado = resultado.get('name')
            bnmp_encontrado = resultado.get('meta', {}).get('bnmp')
            face_objects = resultado.get('face_objects', 0)
            if nome_encontrado == nome and bnmp_encontrado == bnmp:
                human_id =resultado['id']
                print(f'ID encontrado: {human_id}')
            
            # Agora, fazer a requisição GET para o endpoint
        

        if human_id != None: 
            if face_objects == 0:
                url_delete = f'http://10.69.7.31/cards/humans/{human_id}/'
                response = requests.delete(url_delete, headers=headers)
                if response.status_code == 204:
                    print("Card humano sem foto apagado com sucesso!")
                    cursor.execute("UPDATE dados_csv SET Status = 'inactive' WHERE BNMP = ?", (bnmp,))
                    
                else:
                    print("Erro ao atualizar o card humano!")
                    print("Status Code:", response.status_code)
                    print("Mensagem de erro:", response.text)
            
            else:

                url_patch = f'http://10.69.7.31/cards/humans/{human_id}/'
                data = {
                    'active': False,
                }
                    
                response = requests.patch(url_patch, headers=headers,data=json.dumps(data))
                if response.status_code == 200:
                    print("Card humano atualizado com sucesso!")
                    cursor.execute("UPDATE dados_csv SET Status = 'inactive' WHERE BNMP = ?", (bnmp,))
                    print("Resposta da API:", response.json())  # Exibindo a resposta da API
                else:
                    print("Erro ao atualizar o card humano!")
                    print("Status Code:", response.status_code)
                    print("Mensagem de erro:", response.text)

        
# Confirmar a alteração
conn.commit()
        
print("Todos os MPs baixados foram inativados")