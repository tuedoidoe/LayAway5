import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

try:
    TELEGRAM_TOKEN = sys.argv[1]
    TELEGRAM_CHAT_ID = sys.argv[2]
except IndexError:
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = None, None

def enviar_mensagem_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
    try: requests.post(url, json=payload)
    except: pass

def atualizar_banco_de_dados():
    print("Iniciando atualização blindada...")
    # Pega dados de ontem e hoje para garantir que nada escape no fuso horário
    novos_jogos = []
    headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://www.livescore.com'}
    
    for d in [1, 0]: # Ontem e Hoje (para cobrir jogos que terminam de madrugada)
        data_obj = datetime.now() - timedelta(days=d)
        data_str = data_obj.strftime('%Y%m%d')
        data_legivel = data_obj.strftime('%Y-%m-%d')
        url = f"https://prod-public-api.livescore.com/v1/api/app/date/soccer/{data_str}/-3"
        
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                for liga in r.json().get('Stages', []):
                    liga_nm = f"{liga.get('Cnm', '')} - {liga.get('Snm', '')}"
                    for jogo in liga.get('Events', []):
                        if jogo.get('Eps', '') == 'FT':
                            esd = str(jogo.get('Esd', ''))
                            hora = f"{esd[8:10]}:{esd[10:12]}" if len(esd) >= 12 else "00:00"
                            novos_jogos.append({
                                'Data': data_legivel, 'Hora': hora, 'Liga': liga_nm,
                                'HomeTeam': jogo['T1'][0]['Nm'], 'AwayTeam': jogo['T2'][0]['Nm'],
                                'FTHG': jogo.get('Tr1'), 'FTAG': jogo.get('Tr2')
                            })
        except: continue

    if novos_jogos:
        df_novos = pd.DataFrame(novos_jogos)
        nome_arquivo = 'base_livescore_api_2025_hoje.csv'
        
        if os.path.exists(nome_arquivo):
            # LER COM CUIDADO: Forçamos tipos e limpamos nomes de colunas
            df_existente = pd.read_csv(nome_arquivo)
            df_existente.columns = df_existente.columns.str.strip()
            
            tamanho_antes = len(df_existente)
            df_completo = pd.concat([df_existente, df_novos], ignore_index=True)
            
            # Remove duplicatas baseado nas colunas chave
            df_completo.drop_duplicates(subset=['Data', 'Hora', 'HomeTeam', 'AwayTeam'], keep='last', inplace=True)
            
            # RE-PROCESSAMENTO DE TIPOS (Evita o erro do FTAG sumindo)
            for col in ['FTHG', 'FTAG']:
                df_completo[col] = pd.to_numeric(df_completo[col], errors='coerce').fillna(0).astype(int)
            
            df_completo = df_completo[['Data', 'Hora', 'Liga', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]
            df_completo.to_csv(nome_arquivo, index=False)
            
            jogos_add = len(df_completo) - tamanho_antes
            msg = f"✅ <b>Base Atualizada!</b>\n⚽ +{jogos_add} jogos.\n📊 Total: {len(df_completo)}"
            enviar_mensagem_telegram(msg if jogos_add > 0 else "⚠️ Sem novos jogos para adicionar.")
        else:
            # Caso o arquivo não exista no repositório por algum erro
            for col in ['FTHG', 'FTAG']:
                df_novos[col] = pd.to_numeric(df_novos[col], errors='coerce').fillna(0).astype(int)
            df_novos.to_csv(nome_arquivo, index=False)
            enviar_mensagem_telegram("✅ Arquivo base criado!")

atualizar_banco_de_dados()
