import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Configurações do Telegram via argumentos do GitHub Actions
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
    print("Iniciando atualização blindada (Formato JSON)...")
    novos_jogos = []
    headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://www.livescore.com'}
    
    # Busca dados de ontem e hoje para garantir a cobertura de fusos horários
    for d in [1, 0]: 
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
                        # Filtra apenas jogos encerrados (FT)
                        if jogo.get('Eps', '') == 'FT':
                            esd = str(jogo.get('Esd', ''))
                            hora = f"{esd[8:10]}:{esd[10:12]}" if len(esd) >= 12 else "00:00"
                            
                            novos_jogos.append({
                                'Data': data_legivel, 'Hora': hora, 'Liga': liga_nm,
                                'HomeTeam': jogo['T1'][0]['Nm'], 'AwayTeam': jogo['T2'][0]['Nm'],
                                'FTHG': jogo.get('Tr1', 0), 'FTAG': jogo.get('Tr2', 0)
                            })
        except Exception as e:
            print(f"Erro ao extrair dia {data_legivel}: {e}")
            continue

    if novos_jogos:
        df_novos = pd.DataFrame(novos_jogos)
        nome_arquivo = 'base_livescore_api.json'
        colunas_padrao = ['Data', 'Hora', 'Liga', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']
        
        # Converte gols para numérico para evitar erros de tipagem
        for col in ['FTHG', 'FTAG']:
            df_novos[col] = pd.to_numeric(df_novos[col], errors='coerce').fillna(0).astype(int)
        
        if os.path.exists(nome_arquivo):
            try:
                # Lendo a base existente em JSON
                df_existente = pd.read_json(nome_arquivo, orient='records')
                
                tamanho_antes = len(df_existente)
                # Junta novos jogos com os antigos
                df_completo = pd.concat([df_existente, df_novos[colunas_padrao]], ignore_index=True)
                
                # Remove duplicatas (mesmo jogo coletado em dias diferentes)
                df_completo.drop_duplicates(subset=['Data', 'Hora', 'HomeTeam', 'AwayTeam'], keep='last', inplace=True)
                
                # Salva no formato JSON (orientado por registros e com indentação para leitura fácil)
                df_completo.to_json(nome_arquivo, orient='records', indent=4, force_ascii=False)
                
                jogos_add = len(df_completo) - tamanho_antes
                msg = f"✅ <b>Base Atualizada!</b>\n⚽ +{max(0, jogos_add)} jogos adicionados.\n📊 Total: {len(df_completo)} jogos"
                enviar_mensagem_telegram(msg if jogos_add > 0 else "⚠️ Sem novos jogos para adicionar.")
                
            except Exception as e:
                msg_erro = f"❌ Erro crítico no JSON: {e}"
                print(msg_erro)
                enviar_mensagem_telegram(msg_erro)
        else:
            # Caso o arquivo ainda não exista, cria o primeiro
            df_novos = df_novos[colunas_padrao]
            df_novos.to_json(nome_arquivo, orient='records', indent=4, force_ascii=False)
            enviar_mensagem_telegram("✅ Arquivo JSON inicial criado com sucesso!")

atualizar_banco_de_dados()
