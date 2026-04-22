import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import csv

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
    novos_jogos = []
    headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'https://www.livescore.com'}
    
    # Pega dados de Ontem e Hoje
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
                        if jogo.get('Eps', '') == 'FT':
                            esd = str(jogo.get('Esd', ''))
                            hora = f"{esd[8:10]}:{esd[10:12]}" if len(esd) >= 12 else "00:00"
                            
                            novos_jogos.append({
                                'Data': data_legivel, 'Hora': hora, 'Liga': liga_nm,
                                'HomeTeam': jogo['T1'][0]['Nm'], 'AwayTeam': jogo['T2'][0]['Nm'],
                                'FTHG': jogo.get('Tr1'), 'FTAG': jogo.get('Tr2')
                            })
        except Exception as e:
            print(f"Erro ao extrair dia {data_legivel}: {e}")
            continue

    if novos_jogos:
        df_novos = pd.DataFrame(novos_jogos)
        nome_arquivo = 'base_livescore_api_2025_hoje.csv'
        colunas_padrao = ['Data', 'Hora', 'Liga', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']
        
        # BLINDAGEM 1: Tipagem dos dados NOVOS imediatamente
        for col in ['FTHG', 'FTAG']:
            df_novos[col] = pd.to_numeric(df_novos[col], errors='coerce').fillna(0).astype(int)
        
        if os.path.exists(nome_arquivo):
            try:
                # BLINDAGEM 2: sep=None faz o Pandas identificar sozinho se é vírgula ou ponto-e-vírgula
                df_existente = pd.read_csv(nome_arquivo, sep=None, engine='python', encoding='utf-8', quoting=csv.QUOTE_NONE, on_bad_lines='skip')
                
                # BLINDAGEM 3: Força os nomes exatos removendo espaços invisíveis
                df_existente.columns = df_existente.columns.str.strip()
                
                # Se as colunas sumiram no passado por arquivo corrompido, recria elas antes que o código quebre
                for col in colunas_padrao:
                    if col not in df_existente.columns:
                        df_existente[col] = 0 if col in ['FTHG', 'FTAG'] else ""

                # BLINDAGEM 4: Força os tipos nos dados ANTIGOS ANTES do concat
                for col in ['FTHG', 'FTAG']:
                    df_existente[col] = pd.to_numeric(df_existente[col], errors='coerce').fillna(0).astype(int)
                
                tamanho_antes = len(df_existente)
                
                # BLINDAGEM 5: Concatena passando apenas as colunas mapeadas (evita colunas fantasmas)
                df_completo = pd.concat([df_existente[colunas_padrao], df_novos[colunas_padrao]], ignore_index=True)
                
                # Remove duplicatas
                df_completo.drop_duplicates(subset=['Data', 'Hora', 'HomeTeam', 'AwayTeam'], keep='last', inplace=True)
                
                # BLINDAGEM 6: Salva forçando explicitamente a vírgula e removendo a formatação estranha
                df_completo.to_csv(nome_arquivo, index=False, sep=',', encoding='utf-8')
                
                jogos_add = len(df_completo) - tamanho_antes
                msg = f"✅ <b>Base Atualizada!</b>\n⚽ +{max(0, jogos_add)} jogos adicionados.\n📊 Total: {len(df_completo)} jogos"
                enviar_mensagem_telegram(msg if jogos_add > 0 else "⚠️ Sem novos jogos para adicionar.")
                
            except Exception as e:
                msg_erro = f"❌ Erro crítico ao mesclar os dados: {e}"
                print(msg_erro)
                enviar_mensagem_telegram(msg_erro)
        else:
            # Primeiro salvamento
            df_novos = df_novos[colunas_padrao]
            df_novos.to_csv(nome_arquivo, index=False, sep=',', encoding='utf-8')
            enviar_mensagem_telegram("✅ Arquivo base criado com sucesso!")

atualizar_banco_de_dados()
