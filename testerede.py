import requests
def teste_proxy():
     
    # URL da API do CNPD
    API_URL = "https://cnpd.mj.gov.br/api/api/painel-publico/desaparecidos/filtrar?ordenacao=MAIS_RECENTE&pagina=0"

    # Use EXATAMENTE as mesmas credenciais de proxy do seu outro script
    PROXIES = {
        "http": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080',
        "https": 'http://atalaia:proj0Talaia992025@proxy.dpf.gov.br:8080'
    }

    # Tudo que é necessário para a API funcionar: 
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://cnpd.mj.gov.br',
        'Referer': 'https://cnpd.mj.gov.br/painel-publico',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }

    params = {
        'ordenacao': 'MAIS_RECENTE',
        'pagina': '0',
    }

    json_data = {
        'estado': 'DF',
    }

    response = requests.post(
        'https://cnpd.mj.gov.br/api/api/painel-publico/desaparecidos/filtrar',
        params=params,
        headers=headers,
        json=json_data,
    )


    # Payload para pedir a primeira página
    payload = {"pagina": 1, "quantidade": 10}

    print("Tentando conectar à API do CNPD através do proxy...")

    try:
        # Adicionamos os parâmetros `proxies` e `verify=False`
        # `verify=False` é frequentemente necessário em redes corporativas com proxy
        response = requests.post(
            API_URL, 
            headers=headers, 
            json=payload, 
            proxies=PROXIES, 
            verify=False, 
            timeout=30
        )
        
        # Verifica se a requisição foi bem-sucedida (código 200)
        response.raise_for_status()
        
        print("\n✅ SUCESSO! Conexão estabelecida.")
        data = response.json()
        print(f"Encontrados {len(data.get('pessoas', []))} registros na primeira página.")
        print("\nAmostra do primeiro registro:")
        print(data['pessoas'][0])

    except requests.exceptions.ProxyError as e:
        print("\n❌ ERRO DE PROXY: Não foi possível conectar através do proxy.")
        print("Verifique se o endereço do proxy e as credenciais estão corretas.")
        print(f"Detalhe: {e}")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERRO DE REQUISIÇÃO: Falha ao conectar à API.")
        print(f"Detalhe: {e}")
        