import pandas as pd
import numpy as np
import plotly.express as px
import os
from flask import current_app
import json
import sqlite3
from app.models import database 
from flask import Flask, render_template

GEOJSON_URL = "scripts/brazil_geo.json"


class HomeController:
    def _gerar_estatisticas_html(self, cursor_local):
        #Cosulta os dados no banco de dados e retorna as estatísticas em HTML
        print("Gerando estatísticas html...")
        query = "SELECT estado, COUNT(*) FROM desaparecidos GROUP BY estado ORDER BY COUNT(*) DESC"
        cursor_local.execute(query)
        resultados = cursor_local.fetchall()
        #string HTML
        html_output = "<h2> Estatísticas por Estado 📈</h2>"
        if not resultados:
            html_output += "<p> Nenhum estado encontrado para gerar estatísticas.</p>"
        else:
            html_output += "<ul style = 'padding-left: 20px'>"
            for estado, quantidade in resultados:
                #Tratamento para casos do estado ser nulo ou vazio
                estado_nome = estado if estado else "Não especificado"
                html_output += f"<li style = 'margin-bottom: 5px;'> {estado_nome}: <strong>{quantidade}</strong></li>"
            html_output += "</ul>"
        #Adionando Total geral de desaparecidos:
        cursor_local.execute("SELECT COUNT (*) FROM desaparecidos")
        total_geral = cursor_local.fetchone()[0]
        html_output += f"<h3>Total de Registros: {total_geral}</h3>"

        return html_output
    
    def _gerar_mapa_html(self, conn_local):
        # Pega os dados do banco
        '''
        Função PRIVADA da View: Busca dados via conexão, gera o mapa Plotly 
        e retorna nos HTML.
        '''
        print("\n Gerando mapeamento...")
        query = "SELECT estado, COUNT(*) as quantidade FROM desaparecidos GROUP BY estado"
        df_dados = database.get_dados_mapa(query, conn_local)
        print(">>> df_dados.head():", df_dados.head().to_dict(orient='records'))
        print(">>> df_dados.dtypes:", df_dados.dtypes.to_dict())
        # Calcula o valor máximo para o range
        if not df_dados.empty:
            valor_maximo = df_dados['quantidade'].max()
        else:
            valor_maximo = 100 
        
        mapeamentos_estados = {
            'Acre': 'AC', 'Alagoas': 'AL', 'Amapá': 'AP', 'Amazonas': 'AM', 'Bahia': 'BA', 
            'Ceará': 'CE', 'Distrito Federal': 'DF', 'Espírito Santo': 'ES', 'Goiás': 'GO', 
            'Maranhão': 'MA', 'Mato Grosso': 'MT', 'Mato Grosso do Sul': 'MS', 'Minas Gerais': 'MG', 
            'Pará': 'PA', 'Paraíba': 'PB', 'Paraná': 'PR', 'Pernambuco': 'PE', 'Piauí': 'PI', 
            'Rio de Janeiro': 'RJ', 'Rio Grande do Norte': 'RN', 'Rio Grande do Sul': 'RS', 
            'Rondônia': 'RO', 'Roraima': 'RR', 'Santa Catarina': 'SC', 'São Paulo': 'SP', 
            'Sergipe': 'SE', 'Tocantins': 'TO'
        }
        df_dados['id'] = df_dados['estado'].map(mapeamentos_estados)

        # 3. Carrega o GeoJSON
        geojson_path = os.path.join(current_app.static_folder, 'scripts', 'brazil_geo.json')
        try:
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson = json.load(f)
        except FileNotFoundError:
            print(f"Arquivo {geojson_path} não encontrado. Verifique o caminho.")
            return
        
        # 4. Lógica para incluir todos os estados
        todos_os_estados = {
            feature['id']: feature['properties']['name'] 
            for feature in geojson['features']
        }
        df_completo = pd.DataFrame(list(todos_os_estados.items()), columns=['id', 'estado'])
        df_mapa = pd.merge(df_completo, df_dados[['id', 'quantidade']], on='id', how='left')
        df_mapa['quantidade'].fillna(0, inplace=True)

        fig = px.choropleth(
            df_mapa,
            geojson=geojson,
            locations='id',
            featureidkey="id",
            color='quantidade',
            hover_name='estado',
            color_continuous_scale="blues",
            title='<b>Mapeamento de desaparecidos no Brasil</b>',
            labels={'quantidade': 'Nº de Desaparecidos'}
        ) 
        fig.update_geos(
            fitbounds="locations",
            visible=False
        )
        #LAYOUT mapa
        #criando mapa cloroplético com os dados de database.py para ser exibido no dashboard

        fig.update_layout(
            title_x=0.5,
            margin={"r":0, "t":40, "l":0, "b":0},
            
            coloraxis=dict(
                cmin=0,
                cmax=valor_maximo,
                colorscale="blues",
                # Força as marcações (ticks) na barra de cores
                colorbar=dict(
                    title="<b>Total de Desaparecidos</b>",
                    x=0.8, 
                    y=0.5,
                    len=0.75,
                    thickness=20,
                    #--- Rótulos ---
                    tickvals=np.linspace(0, valor_maximo, 5),
                    ticktext=[f"{int(v)}" for v in np.linspace(0, valor_maximo, 5)],
                    #--- Estilo da borda e fundo ---
                    bgcolor="rgba(255,255,255,0.7)", #funco branco semi-transparente
                    borderwidth=0.1,
                    bordercolor="#000000"           
                )
            )
        )
        map_html = fig.to_html(full_html = False, include_plotlyjs='cdn') 
        return map_html
    # --- MÉTODO PÚBLICO CHAMADO PELA ROTA ---
    def index(self):
        """
        Busca dados do Model, chama métodos para gerar HTMLs parciais,
        e passa esses HTMLs para o template 'posts/index.html' renderizar.
        """
        conn_local = None 
        stats_html = "<h2>Erro ao carregar estatísticas.</h2>" # Valor padrão em caso de erro
        mapa_html = "<p>Erro ao gerar mapa.</p>"           # Valor padrão em caso de erro
        
        try:
            print("Abrindo conexão com o banco para a requisição...")
            conn_local = database.connection_db() 
            cursor_local = conn_local.cursor()
            
            # Chama as funções privadas para gerar os blocos de HTML
            stats_html = self._gerar_estatisticas_html(cursor_local)
            mapa_html = self._gerar_mapa_html(conn_local)
            
            
        except sqlite3.Error as e:
             print(f"Erro de Banco de Dados ao gerar a página: {e}")
        except FileNotFoundError as e:
             print(f"Erro de Arquivo não encontrado: {e}")
             mapa_html = f"<div style='padding: 20px; text-align: center;'><h1>Erro Crítico: Arquivo necessário ({e.filename}) não encontrado.</h1></div>"
        except Exception as e:
             print(f"Erro inesperado ao gerar a página: {e}")
        finally:
             if conn_local:
                  conn_local.close() 
                  print("Conexão com o banco fechada para a requisição.")

        return render_template('index.html', stats_html=stats_html, mapa_html=mapa_html)
        

