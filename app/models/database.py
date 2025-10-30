import sqlite3
import os
from flask import Flask
import pandas as pd
BASE_URL = "https://desaparecidosbrasil.org/?page={}"
DB_NAME = "desaparecidos.db"
IMG_DIR = r"C:\mitra\desaparecidos\source"


PROXIES = {
    "http": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080',
    "https": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080'
}
# Garantir pasta
os.makedirs(IMG_DIR, exist_ok=True)

def connection_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = connection_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS desaparecidos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                sexo TEXT,
                dessapareceu_em TEXT,
                local TEXT,
                vestimenta TEXT,
                instituicao TEXT,
                estado TEXT,
                foto_url TEXT,
                img_path TEXT,
                pagina INTEGER,
                status TEXT,
                fonte TEXT
                )
    """
    )
    conn.commit()
    conn.close()
    print("Banco de dados inicializado com sucesso.")
...
# -----Consultas-----
def buscar_desaparecido_por_nome(nome):
    '''Busca desaparecido por nome'''
    conn = connection_db()
    cursor = conn.cursor()
    nome = 'MARIA EDUARDA ROCHA ALMEIDA'
    cursor.execute("SELECT * FROM desaparecidos WHERE nome = ?", (nome))
    resultado = cursor.fetchone()
    if resultado:
        print(f"Registro encontrado para {nome}: {resultado}")
    else:
        print("Nenhum resultado encontrado\n")

def get_dados_mapa(query, conn):
    try:
        df = pd.read_sql_query(query, conn)
        if 'estado'not in df.columns:
            df['estado'] = None
        if 'quantidade' not in df.columns:
            df['quantidade'] = 0
        return df
    except Exception as e:
        print(f"Erro em get_dados_mapa: {e}")
        return pd.DataFrame(columns = ['estado', 'quantidade'])

def mostrar_estatisticas_por_estado(cursor):
    """Consulta o banco de dados e exibe o total de desaparecidos por estado."""
    print("\n--- 📊 Estatísticas por Estado ---")
    
    # Query para contar todos os registros, agrupá-los por estado e ordenar do maior para o menor
    query = "SELECT estado, COUNT(*) FROM desaparecidos GROUP BY estado ORDER BY COUNT(*) DESC"
    
    cursor.execute(query)
    resultados = cursor.fetchall()

    if not resultados:
        print("Nenhum dado encontrado para gerar estatísticas.")
        return

    for estado, quantidade in resultados:
        # Trata casos onde o estado pode ser nulo ou vazio no banco
        estado_nome = estado if estado else "Não especificado"
        print(f"📍 {estado_nome}: {quantidade} desaparecidos")

    cursor.execute("SELECT COUNT(*) FROM desaparecidos")
    total_geral = cursor.fetchone()[0]
    print(f"Total: {total_geral}")

#Funções de INSERT e UPDATE

