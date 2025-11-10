import sqlite3
import os
import pandas as pd

DB_NAME = "desaparecidos.db"

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
            cnpd_id TEXT,
            nome TEXT,
            idade TEXT, 
            sexo TEXT,
            desapareceu_em TEXT,
            local TEXT,
            vestimenta TEXT,
            instituicao TEXT,
            estado TEXT,
            foto_url TEXT,
            img_path TEXT,
            pagina INTEGER,
            status TEXT,
            fonte TEXT,
            UNIQUE(id, fonte)
        )
    """)

    # --- GARANTIR QUE TODAS AS COLUNAS EXISTEM ---
    colunas_necessarias = [
        "cnpd_id", "idade", "instituicao", "estado",
        "foto_url", "img_path", "pagina", "status", "fonte"
    ]

    cursor.execute("PRAGMA table_info(desaparecidos)")
    existentes = [c[1] for c in cursor.fetchall()]

    for coluna in colunas_necessarias:
        if coluna not in existentes:
            cursor.execute(f"ALTER TABLE desaparecidos ADD COLUMN {coluna} TEXT")

    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado corretamente.")

# ----- CONSULTAS -----

def buscar_desaparecido_por_nome(nome):
    conn = connection_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM desaparecidos WHERE nome = ?", (nome,))
    resultado = cursor.fetchone()
    if resultado:
        print(f"Registro encontrado para {nome}: {dict(resultado)}")
    else:
        print(f"Nenhum resultado encontrado para {nome}\n")

def get_dados_mapa(query, conn):
    try:
        df = pd.read_sql_query(query, conn)
        if "estado" not in df.columns:
            df["estado"] = None
        if "quantidade" not in df.columns:
            df["quantidade"] = 0
        return df
    except Exception as e:
        print(f"Erro em get_dados_mapa: {e}")
        return pd.DataFrame(columns=["estado", "quantidade"])

def mostrar_estatisticas_por_estado(cursor):
    print("\n--- 📊 Estatísticas por Estado ---")
    query = "SELECT estado, COUNT(*) FROM desaparecidos GROUP BY estado ORDER BY COUNT(*) DESC"
    cursor.execute(query)
    resultados = cursor.fetchall()

    if not resultados:
        print("Nenhum dado encontrado.")
        return

    for estado, qtd in resultados:
        estado_nome = estado if estado else "Não especificado"
        print(f"📍 {estado_nome}: {qtd} desaparecidos")

    cursor.execute("SELECT COUNT(*) FROM desaparecidos")
    total = cursor.fetchone()[0]
    print(f"Total geral: {total}")
