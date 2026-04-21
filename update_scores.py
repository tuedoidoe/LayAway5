import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Pega as senhas do Telegram injetadas pelo GitHub Actions
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
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Erro ao enviar mensagem pro Telegram: {e}")

def atualizar_banco_de_dados():
    print("Iniciando rotina de atualização diária (com Hora e Anti-Duplicidade)...")
    
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
                            # CAPTURA DA HORA: Extrai do campo Esd (Event Start Date)
                            esd = str(jogo.get('Esd', ''))
                            if len(esd) >= 12:
                                horario_jogo = f"{esd[8:10]}:{esd[10:12]}"
                            else:
                                horario_jogo = "00:00"

                            novos_jogos.append({
                                'Data': data_legivel,
                                'Hora': horario_jogo,
                                'Liga': liga_completa,
                                'HomeTeam': jogo['T1'][0]['Nm'],
                                'AwayTeam': jogo['T2'][0]['Nm'],
                                'FTHG': int(jogo.get('Tr1', 0)),
                                'FTAG': int(jogo.get('Tr2', 0))
                            })
                        except (KeyError, IndexError, ValueError):
                            pass
        else:
            enviar_mensagem_telegram(f"❌ Erro na API: {response.status_code}")
            return
            
    except Exception as e:
        enviar_mensagem_telegram(f"❌ Erro de conexão: {e}")
        return

    if novos_jogos:
        df_novos = pd.DataFrame(novos_jogos)
        nome_arquivo = 'base_livescore_api_2025_hoje.csv'
        
        try:
            if os.path.exists(nome_arquivo):
                df_existente = pd.read_csv(nome_arquivo)
                
                # Garante que as colunas estejam na mesma ordem
                df_completo = pd.concat([df_existente, df_novos], ignore_index=True)
                
                # Remove duplicatas usando a Hora como critério também
                df_completo.drop_duplicates(subset=['Data', 'Hora', 'HomeTeam', 'AwayTeam'], keep='last', inplace=True)
                
                # ORGANIZAÇÃO CRÍTICA: Reordena as colunas para evitar o erro de FTAG na coluna errada
                colunas_corretas = ['Data', 'Hora', 'Liga', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']
                df_completo = df_completo[colunas_corretas]
                
                df_completo.to_csv(nome_arquivo, index=False)
                enviar_mensagem_telegram(f"✅ <b>Base Atualizada!</b>\n📊 Total agora: {len(df_completo)} jogos.")
            else:
                df_novos.to_csv(nome_arquivo, index=False)
                enviar_mensagem_telegram(f"✅ Arquivo criado com {len(df_novos)} jogos.")
                
        except Exception as e:
            enviar_mensagem_telegram(f"❌ Erro ao salvar CSV: {e}")

atualizar_banco_de_dados()
