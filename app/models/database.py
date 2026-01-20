import sqlite3
import os
import pandas as pd
import unicodedata
import re


# Pega o diretório onde este arquivo (database.py) está: .../app/models
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Sobe dois níveis para chegar na raiz do projeto: .../DESAPARECIDOS_MVC1
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

# Define o caminho ABSOLUTO do banco de dados
DB_PATH = os.path.join(PROJECT_ROOT, "pessoasdesaparecidas.db")


# Ajuste de caminhos para imagens (se necessário)
IMG_DIR = os.path.join(PROJECT_ROOT, "source")

PROXIES = {
    "http": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080',
    "https": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080'
}


def connection_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn



estados_uf = {
    "Rondônia": "RO", "Acre": "AC", "Amazonas": "AM", "Roraima": "RR", "Pará": "PA",
    "Amapá": "AP", "Tocantins": "TO", "Maranhão": "MA", "Piauí": "PI", "Ceará": "CE",
    "Rio Grande do Norte": "RN", "Paraíba": "PB", "Pernambuco": "PE", "Alagoas": "AL",
    "Sergipe": "SE", "Bahia": "BA", "Minas Gerais": "MG", "Espírito Santo": "ES",
    "Rio de Janeiro": "RJ", "São Paulo": "SP", "Paraná": "PR", "Santa Catarina": "SC",
    "Rio Grande do Sul": "RS", "Mato Grosso": "MT", "Mato Grosso do Sul": "MS",
    "Goiás": "GO", "Distrito Federal": "DF"
}

uf_estados = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins"
}

def normalize(text):
    if pd.isna(text):
        return ""
    s = str(text).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s



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
            instituicao TEXT,
            estado TEXT,
            foto_url TEXT,
            img_path TEXT,
            pagina INTEGER,
            status TEXT,
            fonte TEXT,
            situacao TEXT,
            UNIQUE(cnpd_id, fonte)
            )
    """)
    #Campo "situação" inserido para diferenciar desaparecidos de encontrados (falecidos e localizados)
    colunas_necessarias = [
        "cnpd_id", "idade", "instituicao", "estado",
        "foto_url", "img_path", "pagina", "status", "fonte", "situacao"
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


def apagar_desaparecido_por_nome(nome):
    """
    Apaga todos os registros da tabela `desaparecidos` onde `nome` é exatamente igual
    ao valor passado. Retorna o número de registros apagados.

    Uso:
        deletados = apagar_desaparecido_por_nome('Nome Sobrenome')
    """
    conn = connection_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM desaparecidos WHERE nome = ?", (nome,))
        deleted = cursor.rowcount
        conn.commit()
        print(f"Registros apagados para '{nome}': {deleted}")
        return deleted
    except Exception as e:
        print(f"Erro ao apagar registros para '{nome}': {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

def get_dados_mapa(query_corrigida,conn):
    """
    Retorna o DataFrame para o mapa. 
    Ignora a query passada e usa uma query interna com COUNT(DISTINCT) (verifica a relação entre nome, idade e local)
    para evitar duplicatas.
    """
    try:
        # Usa concatenação (||) para simular DISTINCT em múltiplas colunas
        # Modifique a query SQL dentro do try:
        query_corrigida = """
            SELECT 
                estado, 
                COUNT(DISTINCT nome || IFNULL(idade,'') || IFNULL(local,'')) as quantidade 
            FROM desaparecidos 
            WHERE situacao = 'desaparecido' OR situacao IS NULL
            GROUP BY estado
        """
                
        df = pd.read_sql_query(query_corrigida, conn)
        
        if "estado" not in df.columns:
            df["estado"] = None
        if "quantidade" not in df.columns:
            df["quantidade"] = 0

        # normaliza a coluna
        df["estado_norm"] = df["estado"].apply(normalize)

        # cria mapeamento normalizado
        normalized_to_uf = {normalize(k): v for k, v in estados_uf.items()}

        # mapear para UF
        df["uf"] = df["estado_norm"].map(normalized_to_uf)

        # lidar com siglas já fornecidas
        mask_no_uf = df["uf"].isna() & df["estado"].notna()
        maybe_sigla = df.loc[mask_no_uf, "estado"].astype(str).str.strip().str.upper()
        valid_ufs = set(uf_estados.keys())
        mask_sigla_valida = maybe_sigla.str.len().eq(2) & maybe_sigla.isin(valid_ufs)
        df.loc[mask_no_uf & mask_sigla_valida, "uf"] = maybe_sigla[mask_sigla_valida].values

        # obter nome canônico (nome por extenso dos UF)
        df["estado_canonico"] = df["uf"].map(uf_estados).fillna(df["estado"])

        # agregar por UF / estado canônico
        result = df.groupby(["uf", "estado_canonico"], dropna=False, as_index=False)["quantidade"].sum()
        result = result.rename(columns={"estado_canonico": "estado"})
        return result[["estado", "uf", "quantidade"]]
    except Exception as e:
        print(f"Erro crítico em get_dados_mapa: {e}")
        return pd.DataFrame(columns=["estado", "uf", "quantidade"])
def apagar_registros_cnpd():
    """
    Apaga todos os registros da tabela `desaparecidos` que pertencem 
    à fonte 'cnpd.mj.gov.br'. Retorna o número de registros removidos.
    """
    conn = connection_db()
    cursor = conn.cursor()
    fonte_cnpd = 'cnpd.mj.gov.br'
    
    try:
        # Executa a remoção filtrando pela fonte específica
        cursor.execute("DELETE FROM desaparecidos WHERE fonte = ?", (fonte_cnpd,))
        removidos = cursor.rowcount
        conn.commit()
        
        print(f"🗑️ Sucesso: {removidos} registros da fonte CNPD foram apagados.")
        return removidos
    except Exception as e:
        print(f"❌ Erro ao apagar registros do CNPD: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

def mostrar_estatisticas_por_estado(cursor):
    print("\n--- 📊 Estatísticas por Estado ---")
    
    # Consulta via query para retornar apenas resultados não duplicados
    query = """
            SELECT 
                estado, 
                COUNT(DISTINCT nome || IFNULL(idade,'') || IFNULL(local,'')) as qtd
            FROM desaparecidos 
            WHERE situacao = 'desaparecido' OR situacao IS NULL
            GROUP BY estado 
            ORDER BY qtd DESC
        """
    
    cursor.execute(query)
    resultados = cursor.fetchall()

    if not resultados:
        print("Nenhum dado encontrado.")
        return

   
    normalized_to_uf = {normalize(k): v for k, v in estados_uf.items()}
    #Retorna os nomes dos estados por extenso:
    def format_nome_estado(estado_value):
        if not estado_value:
            return "Não especificado"
        s = str(estado_value).strip()
        maybe = s.upper()
        if len(maybe) == 2 and maybe in uf_estados:
            return uf_estados[maybe]
        m = re.search(r'(.+?)\s*-\s*([A-Za-z]{2})$', s)
        if m:
            uf = m.group(2).upper()
            if uf in uf_estados:
                return uf_estados[uf]
            return m.group(1).strip()
        nn = normalize(s)
        if nn in normalized_to_uf:
            uf = normalized_to_uf[nn]
            return uf_estados.get(uf, s)
        for uf, full in uf_estados.items():
            if normalize(full) == nn:
                return full
        return s

    for estado, qtd in resultados:
        estado_nome = format_nome_estado(estado)
        print(f"📍 {estado_nome}: {qtd} desaparecidos")

    # Total Geral 
    cursor.execute("SELECT COUNT(DISTINCT nome || IFNULL(idade,'') || IFNULL(local,'')) FROM desaparecidos")
    total = cursor.fetchone()[0]
    print(f"Total geral: {total}")

if __name__ == "__main__":
    
    print("--- EXECUTANDO SCRIPT DE BANCO DE DADOS DIRETAMENTE ---")
    init_db()
    apagar_registros_cnpd()
    mostrar_estatisticas_por_estado(connection_db().cursor())
    
    #apagar_desaparecido_por_nome('nome_completo')
    print("--- SCRIPT DE BANCO DE DADOS CONCLUÍDO ---")