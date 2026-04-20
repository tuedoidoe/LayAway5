import requests
import pandas as pd
from datetime import datetime, timedelta
import sys

# Pega as senhas diretamente da linha de comando do GitHub
try:
    TELEGRAM_TOKEN = sys.argv[1]
    TELEGRAM_CHAT_ID = sys.argv[2]
except IndexError:
    TELEGRAM_TOKEN = None
    TELEGRAM_CHAT_ID = None

def enviar_mensagem_telegram(mensagem):
    """Função para enviar mensagem para o seu Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Aviso: Credenciais do Telegram não configuradas ou vazias.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    
    try:
        resposta = requests.post(url, json=payload)
        if resposta.status_code != 200:
            print(f"Aviso do Telegram: {resposta.text}")
    except Exception as e:
        print(f"Erro ao enviar mensagem pro Telegram: {e}")

def atualizar_banco_de_dados():
    print("Iniciando rotina de atualização diária...")
    
    ontem = datetime.now() - timedelta(days=1)
    data_str = ontem.strftime('%Y%m%d')
    data_legivel = ontem.strftime('%Y-%m-%d')
    
    url_api = f"https://prod-public-api.livescore.com/v1/api/app/date/soccer/{data_str}/-3"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': '*/*',
        'Origin': 'https://www.livescore.com',
        'Referer': 'https://www.livescore.com/'
    }
    
    novos_jogos = []
    
    try:
        response = requests.get(url_api, headers=headers, timeout=15)
        if response.status_code == 200:
            dados_json = response.json()
            
            for liga in dados_json.get('Stages', []):
                liga_completa = f"{liga.get('Cnm', '')} - {liga.get('Snm', '')}"
                
                for jogo in liga.get('Events', []):
                    if jogo.get('Eps', '') == 'FT':
                        try:
                            novos_jogos.append({
                                'Data': data_legivel,
                                'Liga': liga_completa,
                                'HomeTeam': jogo['T1'][0]['Nm'],
                                'AwayTeam': jogo['T2'][0]['Nm'],
                                'FTHG': int(jogo.get('Tr1', 0)),
                                'FTAG': int(jogo.get('Tr2', 0))
                            })
                        except (KeyError, IndexError, ValueError):
                            pass
        else:
            erro_msg = f"❌ <b>LayAway5:</b> Erro na API do LiveScore. Status: {response.status_code}"
            print(erro_msg)
            enviar_mensagem_telegram(erro_msg)
            return
            
    except Exception as e:
        erro_msg = f"❌ <b>LayAway5:</b> Erro de conexão: {e}"
        print(erro_msg)
        enviar_mensagem_telegram(erro_msg)
        return

    # Adicionar os dados novos ao arquivo existente
    if novos_jogos:
        df_novos = pd.DataFrame(novos_jogos)
        nome_arquivo = 'base_livescore_api_2025_hoje.csv'
        
        try:
            df_novos.to_csv(nome_arquivo, mode='a', header=False, index=False)
            sucesso_msg = f"✅ <b>LayAway5:</b> Base atualizada com sucesso!\n⚽ <b>{len(novos_jogos)}</b> jogos do dia {data_legivel} foram adicionados."
            print(sucesso_msg)
            enviar_mensagem_telegram(sucesso_msg)
        except Exception as e:
            erro_csv = f"❌ <b>LayAway5:</b> Erro ao salvar o CSV: {e}"
            print(erro_csv)
            enviar_mensagem_telegram(erro_csv)
    else:
        aviso_msg = f"⚠️ <b>LayAway5:</b> Automação rodou, mas nenhum jogo finalizado no dia {data_legivel}."
        print(aviso_msg)
        enviar_mensagem_telegram(aviso_msg)

# Executa a função
atualizar_banco_de_dados()
