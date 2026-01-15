from time import sleep
import re
from unidecode import unidecode
import sqlite3
import os
import base64
import requests
import json
from datetime import datetime

#Lista de procurados
def converter_data(data):
    if not data or str(data).strip() == "":
        return ""
    
    try:
        # Remove qualquer caractere que não seja número (trata 09.08.2001 ou 09/08/2001)
        nums = re.sub(r'\D', '', str(data))
        
        if len(nums) == 8:
            dia = nums[:2]
            mes = nums[2:4]
            ano = nums[4:]
            
            # Retorna no padrão ISO (AAAA-MM-DD), que é o padrão internacional
            # Se a sua API exige o padrão BR, use f"{dia}/{mes}/{ano}"
            return f"{ano}-{mes}-{dia}"
        return ""
    except Exception:
        return ""

# Caminho para o banco de dados SQLite
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) #Alterado 
db_path = os.path.join(BASE_DIR, "pessoasdesaparecidas.db")
# Conectar ao banco de dados SQLite
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row # Isso permite usar linha['nome'] em vez de linha[1]
cursor = conn.cursor()


# Detalhes de autenticação básica
username = 'linux'  # Alterado
password = 'ubuntuff2025'     # Alterado
# Watchlist 21

# Codificar o par username:password em base64 para a autenticação básica
credentials = f'{username}:{password}'
encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

# URL para obter o token de autenticação
auth_url = 'http://10.69.7.31/auth/login/'

# Corpo da requisição (dados do dispositivo)
auth_data = {
    "video_auth_token": "A",  # Substitua com o token de autenticação de vídeo, se necessário
    "uuid": "1D9D84D5-E18C-1407-4F77-8F29EF7F5A07",  # Alterado
    "mobile": False,          # Se for um dispositivo móvel ou não
    "device_info": {}         # Informações adicionais sobre o dispositivo (se necessário)
    #Quais informações exatamente?
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
        print('Token não encontrado na resposta. ❌')
else:
    print(f'Falha ao obter o token: {response.status_code}')
    print(response.text)

url_cards = 'http://10.69.7.31/cards/humans/' 

# Selecionar as linhas com Status = "new"
#Só envia se o status for new
cursor.execute("SELECT * FROM desaparecidos WHERE status = 'new'")  
linhas = cursor.fetchall()

def tratar_null(valor):
  return unidecode(valor) if valor is not None else ""

#Verificar se há novos registros
if not linhas:
  print(f"[{datetime.now().strftime('%H:%M:%S')}]❌ Nenhum registro novo encontrado para processamento." )
else:
  print(f"Encontrado(s): {len(linhas)} registro(s) para processar.")

# Verificar e processar as linhas
for linha in linhas:
  #Usando os nomes das colunas
  id_db = linha['id']
  nome = tratar_null(linha['nome'])
  idade = tratar_null(linha['idade'])
  sexo = tratar_null(linha['sexo'])
  sexo_value = sexo.replace('Masculino','M').replace('Feminino','F')
  img_path = linha['img_path']
  uf = tratar_null(linha['estado'])
  comment = tratar_null(linha['fonte'])
  natural_de = tratar_null(linha['local'])
  
  #Verificar se há novos registros

  data = {
    'active':True,
    'name': nome,  # Substitua pelo nome que você deseja pesquisar
    'watch_lists': [22],
    'meta':{
      'nome':nome,
      'sexo':sexo_value,
      'img_path': img_path,
      'uf': uf,#Verificar se vai salvar corretamente no campo de estado.
      'comment': comment,
      'natural_de': tratar_null(linha['local'])
      
    }
  }
  
  headers = {
    'Accept': 'application/json',
    'Authorization': f'Token {token}'  # Usando o token obtido
  }

  response = requests.post(url=url_cards, headers=headers, json=data)

  if response.status_code == 201:
    data_r = response.json()
    #print (data_r)
    # Obter o valor do 'id'
    id_value = data_r['id']
    created_date = data_r['created_date']

    #Inserir a foto
    #img_path = rf"C:\mitra\RO\images\{}"
    if os.path.exists(img_path):
      print(f'o arquivo {img_path} existe') 

      url_detect = 'http://10.69.7.31/detect'

      payload={
        'face':{
          'age': False,
          'beard': False,
          'emotions': False,
          'glasses': False,
          'gender': False,
          'medmask': False,
          'headpose': False
        }
      } 

      data = {
        'attributes': json.dumps(payload)  # Convertendo o objeto attributes para JSON
      }

      files = {
        'photo': (open(img_path, 'rb')) 
      }

      response=requests.post(url_detect,headers=headers,data=data,files=files)

      if response.status_code == 200:
        print(f"Arquivo de imagem {img_path} detectado com sucesso!")
        data_detect= response.json()
        try:
          face_id = data_detect['objects']['face'][0]['id']
        except:
          face_id =""
        url_objects = 'http://10.69.7.31/objects/faces/'
        create_from = f'detection:{face_id}'

        payload={
          'create_from': create_from ,
          'active':True,
          'card':id_value
        }
        files = {
          'source_photo': (open(img_path, 'rb')) 
        }
        response = requests.post(url_objects,headers=headers, data=payload, files=files)

        # Verificar a resposta
        if response.status_code == 201:
          print(f"Arquivo de imagem {img_path} inserido com sucesso!")
        else:
          print(f"Erro {response.status_code}: {response.text}")
      else:
        print(f'Falha na detecção de rosto {img_path}')

    
    # Alterar o Status para "OK" após processamento
    cursor.execute("UPDATE desaparecidos SET status = 'OK' WHERE id = ?", (id_db,))  #mudar para o status desejado
    print(rf"{nome} Inserido com sucesso no FindFace 10.69.7.31 ✅")
    conn.commit()

  else:
    print(f'Falha na requisição para /cards/humans/: {response.status_code}')
    print(f'{response}')

sleep(2)
conn.close()