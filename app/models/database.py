import sqlite3
import os
import pandas as pd

DB_NAME = "desaparecidos.db"


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "..", "source"))

PROXIES = {
    "http": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080',
    "https": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080'
}

def connection_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def delet():
    """Deleta APENAS os registros da fonte CNPD"""
    conn = connection_db()
    cursor = conn.cursor()
    try:
        print("--- V45: Deletando registros antigos do CNPD... ---")
        cursor.execute("DELETE FROM desaparecidos WHERE fonte = 'cnpd.mj.gov.br'")
        conn.commit() 
        
        
        print(f"✅ Dados da fonte CNPD deletados com sucesso! {cursor.rowcount} linhas afetadas.")
    
    except Exception as e:
        print(f"❌ Erro ao deletar dados: {e}")
    finally:
        conn.close()


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
            UNIQUE(cnpd_id, fonte) 
        )
    """)

    
    colunas_necessarias = [
        "cnpd_id", "idade", "instituicao", "estado",
        "foto_url", "img_path", "pagina", "status", "fonte"
    ]

    cursor.execute("PRAGMA table_info(desaparecidos)")
    existentes = [c[1] for c in cursor.fetchall()]

    for coluna in colunas_necessarias:
        if coluna not in existentes:
            try:
                cursor.execute(f"ALTER TABLE desaparecidos ADD COLUMN {coluna} TEXT")
            except sqlite3.OperationalError as e:
                print(f"Aviso: Não foi possível adicionar coluna {coluna}. {e}")

    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado corretamente.")



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


if __name__ == "__main__":
    print("--- EXECUTANDO SCRIPT DE BANCO DE DADOS DIRETAMENTE ---")
    
    init_db()
    
    
    delet()
    
    print("--- SCRIPT DE BANCO DE DADOS CONCLUÍDO ---")
