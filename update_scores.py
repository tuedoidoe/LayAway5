import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Puxa as senhas enviadas pelo GitHub Actions
try:
    token = sys.argv[1]
    chat_id = sys.argv[2]
except:
    token = chat_id = None

def enviar_telegram(msg):
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
        except:
            print("Erro ao conectar com Telegram")

def atualizar():
    print("Iniciando atualização...")
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
        else:
            enviar_telegram(f"❌ Erro API: {res.status_code}")
            return
    except Exception as e:
        enviar_telegram(f"❌ Erro de conexão: {e}")
        return

    file = 'base_livescore_api_2025_hoje.csv'
    if novos:
        df_n = pd.DataFrame(novos)
        if os.path.exists(file):
            df_e = pd.read_csv(file)
            
            # Força a conversão para evitar o problema do ".0" e desaparecimento
            df_e['FTHG'] = pd.to_numeric(df_e['FTHG'], errors='coerce').fillna(0).astype(int)
            df_e['FTAG'] = pd.to_numeric(df_e['FTAG'], errors='coerce').fillna(0).astype(int)

            df_c = pd.concat([df_e, df_n], ignore_index=True)
            df_c.drop_duplicates(subset=['Data', 'Hora', 'HomeTeam', 'AwayTeam'], keep='last', inplace=True)
            
            # TRAVA AS COLUNAS NA ORDEM EXATA
            df_c = df_c[['Data', 'Hora', 'Liga', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]
            
            df_c.to_csv(file, index=False, encoding='utf-8-sig')
            enviar_telegram(f"✅ <b>LayAway5:</b> Atualizado!\n⚽ {len(df_n)} jogos processados.\n📊 Total: {len(df_c)}")
        else:
            df_n.to_csv(file, index=False, encoding='utf-8-sig')
            enviar_telegram("✅ Arquivo novo criado!")
    else:
        enviar_telegram(f"⚠️ Nenhum jogo finalizado em {data_legivel}")

atualizar()
