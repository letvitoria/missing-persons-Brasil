from time import sleep
import re
from unidecode import unidecode
import sqlite3
import os
import base64
import requests
import json
from datetime import datetime
#from app.models import database

def converter_data(data):
  try:
    # Tenta converter a data no formato DD/MM/AAAA
    ano = data[:4]
    mes = data[4:6]
    dia = data[6:8]
    
    # Retorna a data formatada
    return f"{ano}-{mes}-{dia}"
  except ValueError:
    # Caso a data não esteja no formato correto
    data_formatada=""
    return data_formatada
  

# Caminho para o banco de dados SQLite
db_path = "desaparecidos.db"

# Conectar ao banco de dados SQLite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()


# Detalhes de autenticação básica
username = 'linux'  # Substitua pelo seu nome de usuário (From Findface)
password = 'ubuntuff2025'     # Substitua pela sua senha (From Findface)

# Codificar o par username:password em base64 para a autenticação básica
credentials = f'{username}:{password}'
encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

# URL para obter o token de autenticação
auth_url = 'http://10.69.7.31/auth/login/'

# Corpo da requisição (dados do dispositivo)
auth_data = {
    "video_auth_token": "A",  # Substitua com o token de autenticação de vídeo, se necessário
    "uuid": "1D9D84D5-E18C-1407-4F77-8F29EF7F5A07",  # Substitua pelo UUID real do seu dispositivo
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

url_cards = 'http://10.69.7.31/cards/humans/'

# Selecionar as linhas com Status = "new"
cursor.execute("SELECT * FROM desaparecidos WHERE observacao = 'new'")  #adaptar para o db
linhas = cursor.fetchall()
def tratar_null(valor):
  return unidecode(valor) if valor is not None else ""

# Verificar e processar as linhas
for linha in linhas:
  # Supondo que as colunas estão na ordem: CPF, BNMP, Nome, Filiacao1, Filiacao2, DN, Natural de:, RG:, Sexo, Tipificação Penal:, Status
  #id = linha[0]
  cpf = tratar_null(linha[5])
  nome = tratar_null(linha[1])
  filiacao1 = tratar_null(linha[4])
  filiacao2 = tratar_null(linha[3])
  dn = tratar_null(linha[2])
  dn_transf = converter_data(dn)
  #natural_de = tratar_null(linha[12])
  rg_raw = tratar_null(linha[6])
  rg = rg_raw.replace('*','')
  img_path = linha[8]
  nif = linha[0]
  #sexo = tratar_null(linha[14])
  #sexo_value = sexo.replace('Masculino','M').replace('Feminino','F')
  #tipificacao_penal = tratar_null(linha[15])

  data = {
    'active':True,
    'name': nome,  # Substitua pelo nome que você deseja pesquisa
    'watch_lists': [9],
    'meta':{
      'cpf':cpf,
      'mae':filiacao1,
      'pai':filiacao2,
      'documento': rg,
      'data_nascimento':dn_transf,
      
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
    cursor.execute("UPDATE pessoas SET observacao = 'OK' WHERE nif = ?", (nif,))  #mudar para o status desejado
    print(rf"{nome} Inserido com sucesso no FindFace 10.69.7.31")
    conn.commit()

  else:
    print(f'Falha na requisição para /cards/humans/: {response.status_code}')
    print(f'{response}')
  
sleep(2)
conn.close