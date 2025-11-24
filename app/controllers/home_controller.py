import pandas as pd
import numpy as np
import plotly.express as px 
import os
from flask import current_app
import json
import sqlite3
from app.models import database 
from flask import render_template
import re
import logging

class HomeController:
    def _formatar_nome_estado(self, estado_value):
        """Ajuda a formatar siglas (SP) para nomes (São Paulo) e tratar nulos."""
        if not estado_value:
            return "Não especificado"
        
        s = str(estado_value).strip()
        
        # 1. Se já é sigla válida (ex: SP)
        maybe = s.upper()
        if len(maybe) == 2 and maybe in database.uf_estados:
            return database.uf_estados[maybe]
            
        # 2. Tenta extrair padrão 'Nome - XX'
        m = re.search(r'(.+?)\s*-\s*([A-Za-z]{2})$', s)
        if m:
            uf = m.group(2).upper()
            if uf in database.uf_estados:
                return database.uf_estados[uf]
            return m.group(1).strip()
            
        # 3. Normaliza e procura no dicionário
        nn = database.normalize(s)
        normalized_to_uf = {database.normalize(k): v for k, v in database.estados_uf.items()}
        if nn in normalized_to_uf:
            uf = normalized_to_uf[nn]
            return database.uf_estados.get(uf, s)
            
        # 4. Último recurso: comparar com nomes completos
        for uf, full in database.uf_estados.items():
            if database.normalize(full) == nn:
                return full
                
        return s
    
    def _gerar_estatisticas_html(self, df_dados):
        """
        Recebe um DataFrame (com colunas 'estado', 'uf', 'quantidade')
        e retorna um bloco HTML com as estatísticas por estado.
        """
        print("Gerando estatísticas...")

        html_output = "<h2>Estatísticas por Estado 📈</h2>"

        # Caso o DataFrame esteja vazio
        if df_dados is None or df_dados.empty:
            html_output += "<p> Nenhum resultado encontrado para gerar estatísticas</p>"
            return html_output

        # Ordena por quantidade desc (garante consistência)
        df_sorted = df_dados.sort_values(by='quantidade', ascending=False)

        html_output += "<ul style='padding-left: 20px'>"

        # usa o helper já presente para formatar nomes
        for _, row in df_sorted.iterrows():
            estado_raw = row.get('estado', None)
            quantidade = int(row.get('quantidade', 0))
            estado_nome = self._formatar_nome_estado(estado_raw)
            html_output += f"<li style='margin-bottom: 5px;'>{estado_nome}: <strong>{quantidade}</strong></li>"

        html_output += "</ul>"

        # total geral (somar coluna quantidade)
        total_geral = int(df_sorted['quantidade'].sum())
        html_output += f"<h3>Total de Registros: {total_geral}</h3>"

        return html_output

    
    # Recebe o DataFrame para não duplicar a consulta.
    def _gerar_mapa_html(self, df_dados_normalizados):
        # Pega os dados do banco
        '''
        Função PRIVADA da View: Recebe dados normalizados, gera o mapa Plotly 
        e retorna seu HTML.
        '''
        print("\n Gerando mapeamento...")
        df_dados = df_dados_normalizados.copy() # Usa os dados recebidos

        # Calcula o valor máximo para o range
        if not df_dados.empty:
            valor_maximo = df_dados['quantidade'].max()
        else:
            valor_maximo = 100 
        
        # Renomeia a coluna 'uf' (que veio do get_dados_mapa) para 'id'
        if 'uf' in df_dados.columns:
            df_dados.rename(columns={'uf': 'id'}, inplace=True)
        else:
            print("ERRO: 'get_dados_mapa' não retornou a coluna 'uf'.")
            return "<h3>Erro ao gerar mapa: dados de UF ausentes.</h3>"


        #Carrega o GeoJSON
        geojson_path = os.path.join(current_app.static_folder, 'scripts', 'brazil_geo.json')
        
        try:
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson = json.load(f)
        except FileNotFoundError:
            print(f"Arquivo {geojson_path} não encontrado. Verifique o caminho.")
            return f"<h1>Erro: Arquivo GeoJSON não encontrado em {geojson_path}</h1>"
        
        #Lógica para incluir todos os estados
        todos_os_estados = {
            feature['id']: feature['properties']['name'] 
            for feature in geojson['features']
        }
        df_completo = pd.DataFrame(list(todos_os_estados.items()), columns=['id', 'estado_geojson'])
        
        # Merge dos dados do banco (df_dados) com o GeoJSON (df_completo)
        df_mapa = pd.merge(df_completo, df_dados[['id', 'quantidade', 'estado']], on='id', how='left')
        df_mapa['quantidade'].fillna(0, inplace=True)
        
        # Usa o nome do estado vindo do banco para o hover_name
        # Se for nulo, usa o nome do GeoJSON
        df_mapa['hover_name'] = df_mapa['estado'].fillna(df_mapa['estado_geojson'])


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
        fig.update_geos(
            fitbounds="locations",
            visible=False
        )
        #LAYOUT mapa
        fig.update_layout(
            title_x=0.5,
            # Aumenta margem direita para acomodar a colorbar fora do mapa
            margin={"r":0, "t":40, "l":0, "b":0},

            coloraxis=dict(
                cmin=0,
                cmax=valor_maximo,
                colorscale="blues",
                colorbar=dict(
                    # Coloca apenas o título à direita da barra
                    title=dict(text="<b>Total </b>"),
                    x=0.8,
                    y=0.5,
                    len=0.75,
                    thickness=20,
                    # Rótulos
                    tickvals=np.linspace(0, valor_maximo, 5),
                    ticktext=[f"{int(v)}" for v in np.linspace(0, valor_maximo, 5)],
                    bgcolor="rgba(255,255,255,0.7)", 
                    borderwidth=0.1,
                    bordercolor="#000000"
                )
            )
        )
        
        map_html = fig.to_html(full_html = False, include_plotlyjs='cdn') 
        return map_html

    def index(self):
        """
        Busca dados do Model UMA VEZ, e passa esses dados para as
        funções de View (mapa e estatísticas).
        """
        conn_local = None 
        stats_html = "<h2>Erro ao carregar estatísticas.</h2>" 
        mapa_html = "<p>Erro ao gerar mapa.</p>" 
        
        try:
            print("Abrindo conexão com o banco para a requisição...")
            conn_local = database.connection_db() 

            query = "SELECT estado, COUNT(*) as quantidade FROM desaparecidos GROUP BY estado"
            df_dados_normalizados = database.get_dados_mapa(query, conn_local)

            stats_html = self._gerar_estatisticas_html(df_dados_normalizados)
            mapa_html = self._gerar_mapa_html(df_dados_normalizados)
            
        except sqlite3.Error as e:
                 print(f"Erro de Banco de Dados ao gerar a página: {e}")
        except FileNotFoundError as e:
                 print(f"Erro de Arquivo não encontrado: {e}")
                 mapa_html = f"<div style='padding: 20px; text-align: center;'><h1>Erro Crítico: Arquivo GeoJSON não encontrado.</h1></div>"
        except Exception as e:
             logging.exception("Erro inesperado ao gerar a página")
        finally:
                 if conn_local:
                         conn_local.close() 
                         print("Conexão com o banco fechada para a requisição.")

        #Renderiza o template com os dados
        return render_template('index.html', stats_html=stats_html, mapa_html=mapa_html)