import json
import pandas as pd
import numpy as np
import plotly.express as px
import os
import sys

# Adicionar path
sys.path.insert(0, os.getcwd())

try:
    from app.models import database
    print("[OK] Módulo database importado")
    
    # Conectar e buscar dados
    conn = database.connection_db()
    query = "SELECT estado, COUNT(*) as quantidade FROM desaparecidos GROUP BY estado"
    df_dados = database.get_dados_mapa(query, conn)
    print(f"[OK] Dados obtidos: {df_dados.shape}")
    print(f"[OK] Colunas: {df_dados.columns.tolist()}")
    print(f"[OK] Primeiras linhas:")
    print(df_dados.head())
    
    # Verificar GeoJSON
    geojson_path = "app/static/scripts/brazil_geo.json"
    with open(geojson_path, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    print(f"[OK] GeoJSON carregado: {len(geojson['features'])} features")
    
    # Verificar merge
    todos_os_estados = {
        feature['id']: feature['properties']['name'] 
        for feature in geojson['features']
    }
    print(f"[OK] Estados no GeoJSON: {len(todos_os_estados)}")
    
    df_completo = pd.DataFrame(list(todos_os_estados.items()), columns=['id', 'estado_geojson'])
    
    if 'uf' in df_dados.columns:
        df_dados_temp = df_dados.rename(columns={'uf': 'id'})
    else:
        print("[ERRO] Coluna 'uf' não existe em df_dados")
        print(f"Colunas disponíveis: {df_dados.columns.tolist()}")
        sys.exit(1)
    
    df_mapa = pd.merge(df_completo, df_dados_temp[['id', 'quantidade', 'estado']], on='id', how='left')
    print(f"[OK] Merge realizado: {df_mapa.shape}")
    print(f"[OK] Dados null no merge: {df_mapa['quantidade'].isnull().sum()}")
    
    # Preencher nulos
    df_mapa['quantidade'].fillna(0, inplace=True)
    df_mapa['hover_name'] = df_mapa['estado'].fillna(df_mapa['estado_geojson'])
    
    print(f"[OK] Hover names preenchidos")
    print(f"[OK] Sample de hover_name:")
    print(df_mapa[['id', 'hover_name', 'quantidade']].head(10))
    
    # Testar criação de figura
    valor_maximo = df_mapa['quantidade'].max()
    print(f"\n[CRIANDO FIGURA] valor_maximo={valor_maximo}")
    
    fig = px.choropleth(
        df_mapa,
        geojson=geojson,
        locations='id',         
        featureidkey="id",     
        color='quantidade',
        hover_name='hover_name', 
        color_continuous_scale="blues",
        title='<b>Mapeamento de desaparecidos no Brasil</b>',
        labels={'quantidade': 'Nº de Desaparecidos', 'hover_name': 'Estado'}
    )
    print("[OK] Figura criada com sucesso!")
    
    # Tentar gerar HTML
    map_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    print(f"[OK] HTML gerado com sucesso! Tamanho: {len(map_html)} bytes")
    
except Exception as e:
    print(f"[ERRO] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
