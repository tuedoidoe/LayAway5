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
        resposta = requests.post(url, json=payload)
        if resposta.status_code != 200:
            print(f"Aviso do Telegram: {resposta.text}")
    except Exception as e:
        print(f"Erro ao enviar mensagem pro Telegram: {e}")

def atualizar_banco_de_dados():
    print("Iniciando rotina de atualização diária (com verificação de duplicatas)...")
    
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

    # Processamento e Lógica Anti-Duplicidade
    if novos_jogos:
        df_novos = pd.DataFrame(novos_jogos)
        nome_arquivo = 'base_livescore_api_2025_hoje.csv'
        
        try:
            if os.path.exists(nome_arquivo):
                # 1. Lê a base existente
                df_existente = pd.read_csv(nome_arquivo)
                tamanho_antes = len(df_existente)
                
                # 2. Junta a base antiga com a nova
                df_completo = pd.concat([df_existente, df_novos], ignore_index=True)
                
                # 3. Remove as duplicatas (Chave de verificação: Data, Mandante e Visitante)
                # keep='last' garante que se houver uma atualização de placar, ele mantém a mais recente.
                df_completo.drop_duplicates(subset=['Data', 'HomeTeam', 'AwayTeam'], keep='last', inplace=True)
                
                tamanho_depois = len(df_completo)
                jogos_reais_adicionados = tamanho_depois - tamanho_antes
                
                # 4. Salva sobrescrevendo o arquivo (agora limpo)
                df_completo.to_csv(nome_arquivo, index=False)
                
                # Prepara a mensagem pro Telegram baseada no que realmente foi adicionado
                if jogos_reais_adicionados > 0:
                    sucesso_msg = f"✅ <b>LayAway5:</b> Base atualizada!\n⚽ <b>{jogos_reais_adicionados}</b> novos jogos adicionados.\n🛡️ Duplicatas removidas.\n📊 Total na base: {tamanho_depois}"
                else:
                    sucesso_msg = f"⚠️ <b>LayAway5:</b> Automação rodou, mas os {len(df_novos)} jogos rastreados hoje já estavam na base. Nenhuma duplicata foi gerada!"
                
                print(sucesso_msg)
                enviar_mensagem_telegram(sucesso_msg)
                
            else:
                # Se o arquivo não existir (primeira vez rodando), apenas salva
                df_novos.to_csv(nome_arquivo, index=False)
                msg_primeira_vez = f"✅ <b>LayAway5:</b> Arquivo criado!\n⚽ <b>{len(df_novos)}</b> jogos adicionados."
                print(msg_primeira_vez)
                enviar_mensagem_telegram(msg_primeira_vez)
                
        except Exception as e:
            erro_csv = f"❌ <b>LayAway5:</b> Erro ao processar o CSV: {e}"
            print(erro_csv)
            enviar_mensagem_telegram(erro_csv)
    else:
        aviso_msg = f"⚠️ <b>LayAway5:</b> Automação rodou, mas nenhum jogo finalizado no dia {data_legivel}."
        print(aviso_msg)
        enviar_mensagem_telegram(aviso_msg)

# Executa a função
atualizar_banco_de_dados()
