import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

try:
    TELEGRAM_TOKEN = sys.argv[1]
    TELEGRAM_CHAT_ID = sys.argv[2]
except:
    TELEGRAM_TOKEN = TELEGRAM_CHAT_ID = None

def atualizar():
    ontem = datetime.now() - timedelta(days=1)
    data_str = ontem.strftime('%Y%m%d')
    data_legivel = ontem.strftime('%Y-%m-%d')
    
    url = f"https://prod-public-api.livescore.com/v1/api/app/date/soccer/{data_str}/-3"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    novos = []
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            for liga in res.json().get('Stages', []):
                liga_n = f"{liga.get('Cnm')} - {liga.get('Snm')}"
                for j in liga.get('Events', []):
                    if j.get('Eps') == 'FT':
                        esd = str(j.get('Esd', ''))
                        novos.append({
                            'Data': data_legivel,
                            'Hora': f"{esd[8:10]}:{esd[10:12]}" if len(esd) >= 12 else "00:00",
                            'Liga': liga_n,
                            'HomeTeam': j['T1'][0]['Nm'],
                            'AwayTeam': j['T2'][0]['Nm'],
                            'FTHG': int(j.get('Tr1', 0)),
                            'FTAG': int(j.get('Tr2', 0))
                        })
    except: return

    if novos:
        df_n = pd.DataFrame(novos)
        file = 'base_livescore_api_2025_hoje.csv'
        if os.path.exists(file):
            df_e = pd.read_csv(file)
            df_c = pd.concat([df_e, df_n], ignore_index=True)
            df_c.drop_duplicates(subset=['Data', 'Hora', 'HomeTeam', 'AwayTeam'], keep='last', inplace=True)
            # TRAVA AS COLUNAS AQUI TAMBÉM
            df_c = df_c[['Data', 'Hora', 'Liga', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]
            df_c.to_csv(file, index=False, encoding='utf-8-sig')
            print("Base Atualizada!")

atualizar()
