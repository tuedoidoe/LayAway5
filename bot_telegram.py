import pandas as pd
import numpy as np
import joblib
import warnings
from datetime import datetime
import pytz
import requests
import io
import os
import json
from rapidfuzz import process, fuzz

warnings.filterwarnings("ignore")

# Configurações do Telegram pegas do GitHub Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN_SCANNER_LAY_AWAY")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_SCANNER_LAY_AWAY")

TOKEN_FUT = "b9f385cc07be27e7b04fe3a68c15120dd633d109"
headers = {"Authorization": f"Token {TOKEN_FUT}"}

ARQUIVO_MEMORIA = "jogos_enviados.json"

# ==========================================
# CARREGAMENTO DOS DICIONÁRIOS JSON
# ==========================================
def carregar_mapeamentos():
    try:
        with open("mapeamentos.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar o arquivo mapeamentos.json: {e}")
        return {"mapeamento_torneios": {}, "tradutor_times": {}}

dicionarios_globais = carregar_mapeamentos()
mapeamento_torneios = dicionarios_globais.get("mapeamento_torneios", {})
tradutor_times = dicionarios_globais.get("tradutor_times", {})

def identificar_torneio(nome_sujo):
    for raiz, codigo in mapeamento_torneios.items():
        if str(nome_sujo).startswith(raiz): return codigo
    return nome_sujo

def drop_reset_index(df):
    return df.reset_index(drop=True)

def enviar_mensagem_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Erro: Credenciais do Telegram não configuradas.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def carregar_memoria():
    hoje = datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%Y-%m-%d')
    try:
        if os.path.exists(ARQUIVO_MEMORIA):
            with open(ARQUIVO_MEMORIA, 'r') as f:
                dados = json.load(f)
                if dados.get("data") == hoje:
                    enviados = dados.get("enviados", {})
                    # Trava para converter arquivo antigo (lista) para o novo formato (dicionário)
                    if isinstance(enviados, list):
                        return {jogo: "ativo" for jogo in enviados}
                    return enviados
    except Exception as e:
        print(f"Erro ao ler memória: {e}")
    return {}

def salvar_memoria(dict_enviados):
    hoje = datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%Y-%m-%d')
    with open(ARQUIVO_MEMORIA, 'w') as f:
        json.dump({"data": hoje, "enviados": dict_enviados}, f)

# --- FUNÇÕES DE DADOS ---
def baixar_base_dados():
    try:
        response = requests.get("https://api.futpythontrader.com/api/dados/betfair/download/", headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(io.BytesIO(response.content))
            if not df.empty and 'Date' in df.columns: df['Date'] = pd.to_datetime(df['Date'])
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

def baixar_jogos_do_dia(data_str):
    try:
        url = f"https://api.futpythontrader.com/api/dados/jogos-do-dia/betfair/{data_str}/download/"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(io.BytesIO(response.content))
            if not df.empty and 'Date' in df.columns: df['Date'] = pd.to_datetime(df['Date'])
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

def carregar_base_livescore():
    try:
        df = pd.read_json("base_livescore_api.json")
        if not df.empty and 'Data' in df.columns: df['Date'] = pd.to_datetime(df['Data'], errors='coerce')
        return df
    except: return pd.DataFrame()

# ==========================================
# MOTOR PRINCIPAL
# ==========================================
def rodar_bot():
    print("Iniciando varredura...")
    fuso_br = pytz.timezone('America/Sao_Paulo')
    hoje = datetime.now(fuso_br)
    data_str = hoje.strftime('%Y-%m-%d')

    try:
        dados_modelo = joblib.load('Modelo_LayAway_6.pkl')
    except Exception as e:
        print("Erro ao carregar modelo:", e)
        return

    model = dados_modelo['modelo']
    taxas_ligas = dados_modelo['liga_rates']
    media_global_treino = dados_modelo['media_global']
    X_cols_treino = dados_modelo['features']

    df_alvo = baixar_jogos_do_dia(data_str)
    if df_alvo.empty:
        print("Nenhum jogo no radar hoje.")
        return

    df_hist = baixar_base_dados()
    
    df_alvo['id_jogo'] = range(1, len(df_alvo) + 1)
    if 'League' in df_alvo.columns:
        df_alvo['League'] = df_alvo['League'].replace(mapeamento_torneios)
        df_alvo['Home'] = df_alvo['Home'].replace(tradutor_times)
        df_alvo['Away'] = df_alvo['Away'].replace(tradutor_times)

    def safe_prob(column): return (1 / pd.to_numeric(column, errors='coerce').replace(0, np.nan)).fillna(0)
    data_limite = df_alvo['Date'].min()

    if not df_hist.empty:
        df_hist_passado = df_hist[df_hist['Date'] < data_limite].copy()
        
        # Fuzzy matching Histórico
        df_hist_h = df_hist_passado[['League', 'Home']].rename(columns={'Home': 'Team'})
        df_hist_a = df_hist_passado[['League', 'Away']].rename(columns={'Away': 'Team'})
        df_hist_all_teams = pd.concat([df_hist_h, df_hist_a]).drop_duplicates()
        
        dicionario_times_fuzzy = {}
        for liga in df_alvo['League'].unique():
            times_hist_liga = df_hist_all_teams[df_hist_all_teams['League'] == liga]['Team'].tolist()
            if not times_hist_liga: continue
            times_hoje_liga = set(df_alvo[df_alvo['League'] == liga]['Home']).union(set(df_alvo[df_alvo['League'] == liga]['Away']))
            for time in times_hoje_liga:
                if time not in times_hist_liga:
                    match = process.extractOne(time, times_hist_liga, scorer=fuzz.ratio)
                    if match and match[1] >= 80: dicionario_times_fuzzy[(liga, time)] = match[0]
        
        df_alvo_odd = df_alvo.copy()
        if dicionario_times_fuzzy:
            df_alvo_odd['Home'] = df_alvo_odd.apply(lambda r: dicionario_times_fuzzy.get((r['League'], r['Home']), r['Home']), axis=1)
            df_alvo_odd['Away'] = df_alvo_odd.apply(lambda r: dicionario_times_fuzzy.get((r['League'], r['Away']), r['Away']), axis=1)
        df_completo = pd.concat([df_hist_passado, df_alvo_odd], ignore_index=True)
    else:
        df_completo = df_alvo.copy()

    df_completo = drop_reset_index(df_completo.sort_values(["Date", "Home"]))
    df_completo['Goals_H_FT'] = pd.to_numeric(df_completo['Goals_H_FT'], errors='coerce')
    df_completo['Goals_A_FT'] = pd.to_numeric(df_completo['Goals_A_FT'], errors='coerce')

    prob_h = safe_prob(df_completo['Odd_H_Back'])
    prob_a = safe_prob(df_completo['Odd_A_Back'])
    prob_o25 = safe_prob(df_completo['Odd_Over25_FT_Back'])
    prob_d = np.clip(1.0 - prob_h - prob_a, 0.1, 1.0)
    exp_tg = np.where(prob_o25 > 0, 1.25 + (prob_o25 * 2.5), 2.5) 
    soma_probs = prob_h + prob_a + prob_d

    df_completo['XG_Casa'] = np.where(prob_h > 0, (exp_tg * (prob_h + 0.5 * prob_d) / soma_probs), np.nan)
    df_completo['XG_Fora'] = np.where(prob_a > 0, (exp_tg * (prob_a + 0.5 * prob_d) / soma_probs), np.nan)
    df_completo['Prob_1x2_A'] = safe_prob(df_completo['Odd_A_Back'])
    df_completo['Prob_CS_Resistance'] = safe_prob(df_completo['Odd_CS_1x0_Lay']) + safe_prob(df_completo['Odd_CS_2x1_Lay'])
    df_completo['Market_Asymmetry'] = (df_completo['Prob_CS_Resistance'] - df_completo['Prob_1x2_A'])
    df_completo['Draw_Density'] = safe_prob(df_completo['Odd_CS_0x0_Lay']) + safe_prob(df_completo['Odd_CS_1x1_Lay'])
    df_completo['Volatility_Risk'] = np.clip((df_completo['Odd_Over25_FT_Back'] / (df_completo['Odd_A_Back'].replace(0, np.nan))), 0, 50)
    df_completo['Away_Odd_Trend'] = df_completo.groupby('Away')['Odd_A_Back'].transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean() - x.shift(1)).fillna(0)
    df_completo["LIGA_RATE"] = df_completo["League"].map(taxas_ligas).fillna(media_global_treino)

    # --- CAMADA ESTATÍSTICAS (Score) ---
    df_livescore = carregar_base_livescore()
    if not df_livescore.empty:
        df_livescore['League'] = df_livescore['Liga'].apply(identificar_torneio)
        df_livescore = df_livescore.rename(columns={'HomeTeam': 'Home', 'AwayTeam': 'Away', 'FTHG': 'Goals_H_FT', 'FTAG': 'Goals_A_FT'})
        df_livescore['Home'] = df_livescore['Home'].map(tradutor_times).fillna(df_livescore['Home'])
        df_livescore['Away'] = df_livescore['Away'].map(tradutor_times).fillna(df_livescore['Away'])
        
        df_ls_passado = df_livescore[df_livescore['Date'] < data_limite].copy()
        times_no_periodo = set(df_alvo['Home']).union(set(df_alvo['Away']))
        df_ls_passado = df_ls_passado[df_ls_passado['Home'].isin(times_no_periodo) | df_ls_passado['Away'].isin(times_no_periodo)]
        
        df_ls_h = df_ls_passado[['League', 'Home']].rename(columns={'Home': 'Team'})
        df_ls_a = df_ls_passado[['League', 'Away']].rename(columns={'Away': 'Team'})
        df_ls_teams = pd.concat([df_ls_h, df_ls_a]).drop_duplicates()
        
        dic_fuzzy_ls = {}
        for liga in df_alvo['League'].unique():
            hist_teams = df_ls_teams[df_ls_teams['League'] == liga]['Team'].tolist()
            if not hist_teams: continue
            hoje_teams = set(df_alvo[df_alvo['League'] == liga]['Home']).union(set(df_alvo[df_alvo['League'] == liga]['Away']))
            for time in hoje_teams:
                if time not in hist_teams:
                    match = process.extractOne(time, hist_teams, scorer=fuzz.ratio, score_cutoff=85)
                    if match: dic_fuzzy_ls[(liga, time)] = match[0]
        
        df_alvo_ls = df_alvo.copy()
        if dic_fuzzy_ls:
            df_alvo_ls['Home'] = df_alvo_ls.apply(lambda r: dic_fuzzy_ls.get((r['League'], r['Home']), r['Home']), axis=1)
            df_alvo_ls['Away'] = df_alvo_ls.apply(lambda r: dic_fuzzy_ls.get((r['League'], r['Away']), r['Away']), axis=1)
            
        df_stats = pd.concat([df_ls_passado, df_alvo_ls], ignore_index=True)
    else:
        df_stats = df_completo.copy()
        
    df_stats = drop_reset_index(df_stats.sort_values(["Date", "Home"]))
    df_stats['Goals_H_FT'] = pd.to_numeric(df_stats['Goals_H_FT'], errors='coerce')
    df_stats['Goals_A_FT'] = pd.to_numeric(df_stats['Goals_A_FT'], errors='coerce')

    df_stats['Pts_H'] = np.where(df_stats['Goals_H_FT'] > df_stats['Goals_A_FT'], 3, np.where(df_stats['Goals_H_FT'] == df_stats['Goals_A_FT'], 1, 0))
    df_stats['Pts_A'] = np.where(df_stats['Goals_A_FT'] > df_stats['Goals_H_FT'], 3, np.where(df_stats['Goals_A_FT'] == df_stats['Goals_H_FT'], 1, 0))
    df_stats['soma_pts_casa'] = df_stats.groupby(['League', 'Home'])['Pts_H'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
    df_stats['soma_pts_fora'] = df_stats.groupby(['League', 'Away'])['Pts_A'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
    df_stats['qtd_jogos_casa'] = df_stats.groupby(['League', 'Home'])['Pts_H'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).count())
    df_stats['qtd_jogos_fora'] = df_stats.groupby(['League', 'Away'])['Pts_A'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).count())
    df_stats['Is_CS_Casa'] = (df_stats['Goals_A_FT'] == 0).astype(int)
    df_stats['Is_FTS_Fora'] = (df_stats['Goals_A_FT'] == 0).astype(int)
    df_stats['soma_cs_casa'] = df_stats.groupby(['League', 'Home'])['Is_CS_Casa'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    df_stats['soma_fts_fora'] = df_stats.groupby(['League', 'Away'])['Is_FTS_Fora'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    df_stats['dp_gs_casa'] = df_stats.groupby(['League', 'Home'])['Goals_A_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=2).std())
    df_stats['dp_gm_fora'] = df_stats.groupby(['League', 'Away'])['Goals_A_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=2).std())
    df_stats['vaz_def_fora'] = df_stats.groupby(['League', 'Away'])['Goals_H_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())

    df_hoje = df_completo[df_completo['id_jogo'].notnull()].copy()
    df_hoje = df_hoje[df_hoje['Date'].dt.date == hoje.date()].copy()

    df_hoje_stats = df_stats.dropna(subset=['id_jogo'])
    df_hoje = df_hoje.merge(
        df_hoje_stats[['id_jogo', 'soma_pts_casa', 'soma_pts_fora', 'qtd_jogos_casa', 'qtd_jogos_fora', 
                       'soma_cs_casa', 'soma_fts_fora', 'dp_gs_casa', 'dp_gm_fora', 'vaz_def_fora']],
        on='id_jogo', how='left'
    )

    if len(df_hoje) > 0:
        xg_total = df_hoje['XG_Casa'] + df_hoje['XG_Fora']
        score_xg = np.where(xg_total > 0, (df_hoje['XG_Casa'] / xg_total) * 30.0, 15.0)
        score_pts_casa = (df_hoje['soma_pts_casa'].fillna(0) / 15.0) * 10.0
        score_pts_fora = ((15.0 - df_hoje['soma_pts_fora'].fillna(0)) / 15.0) * 10.0
        score_fts = df_hoje['soma_fts_fora'].fillna(0) * 15.0
        score_cs = df_hoje['soma_cs_casa'].fillna(0) * 5.0
        score_dp_gm = (np.maximum(0, 2.0 - df_hoje['dp_gm_fora'].fillna(1.0)) / 2.0) * 10.0
        score_dp_gs = (np.maximum(0, 2.0 - df_hoje['dp_gs_casa'].fillna(1.0)) / 2.0) * 10.0
        score_vaz = (np.minimum(3.0, df_hoje['vaz_def_fora'].fillna(0)) / 3.0) * 10.0

        df_hoje['Score'] = score_xg + score_pts_casa + score_pts_fora + score_fts + score_cs + score_dp_gm + score_dp_gs + score_vaz
        df_hoje['Score'] = df_hoje['Score'].fillna(0).round(0).astype(int)

    colunas_vitais = list(X_cols_treino) + ['Odd_A_Lay', 'Odd_H_Back', 'Odd_A_Back', 'Home', 'Away', 'League', 'Time', 'Date', 'Score']
    colunas_vitais = [col for col in colunas_vitais if col in df_hoje.columns]
    df_hoje = drop_reset_index(df_hoje.dropna(subset=colunas_vitais))

    if len(df_hoje) == 0:
        print("Nenhum jogo possui as métricas completas hoje.")
        return

    # Previsão p/ todos
    df_hoje["Previsao"] = model.predict_proba(df_hoje[X_cols_treino])[:, 1]
    df_hoje["Edge"] = df_hoje["Previsao"] - (1 - (1 / df_hoje["Odd_A_Lay"]))
    
    # Filtro de Operabilidade
    df_bruto = df_hoje[(df_hoje["Edge"] >= 0.0) & (df_hoje['Odd_A_Lay'] <= 3.50) & (df_hoje['Odd_H_Back'] < df_hoje['Odd_A_Back'])].copy()

    jogos_memoria = carregar_memoria()
    novos_envios = False
    jogos_operaveis_agora = []

    # 1. VERIFICA JOGOS NOVOS OU QUE RETORNARAM A FICAR OPERÁVEIS
    for index, row in df_bruto.iterrows():
        id_jogo_str = f"{row['Home']} x {row['Away']}"
        jogos_operaveis_agora.append(id_jogo_str)
        
        status_anterior = jogos_memoria.get(id_jogo_str)
        
        if status_anterior != "ativo":
            edge_pct = row['Edge'] * 100
            odd = row['Odd_A_Lay']
            horario = row['Time']
            liga = row['League']
            data_formatada = row['Date'].strftime('%d/%m/%Y')
            score = int(row['Score'])
            alerta = '🟢' if score >= 55 else '🟡' if score >= 48 else '🔴'

            titulo = "🚨 <b>NOVO ALERTA LAY AWAY</b> 🚨" if status_anterior is None else "🔄 <b>ATUALIZAÇÃO: VOLTOU A TER VALOR</b> 🔄"

            msg = f"{titulo}\n\n"
            msg += f"⚽ <b>Jogo:</b> {id_jogo_str}\n"
            msg += f"🏆 <b>Liga:</b> {liga}\n"
            msg += f"📅 <b>Data:</b> {data_formatada}\n"
            msg += f"⏰ <b>Horário:</b> {horario}\n"
            msg += f"📉 <b>Odd Lay Fora:</b> {odd:.2f}\n"
            msg += f"💎 <b>Edge (EV+):</b> {edge_pct:.2f}%\n"
            msg += f"📊 <b>Score:</b> {score} {alerta}\n\n"
            msg += f"✅ <b>Status: Jogo Operável</b>"

            enviar_mensagem_telegram(msg)
            print(f"Enviado Operável: {id_jogo_str}")
            
            jogos_memoria[id_jogo_str] = "ativo"
            novos_envios = True

    # 2. VERIFICA JOGOS QUE PERDERAM A OPERABILIDADE
    for jogo_memoria, status in jogos_memoria.items():
        if status == "ativo" and jogo_memoria not in jogos_operaveis_agora:
            
            home_team, away_team = jogo_memoria.split(" x ")
            jogo_dados = df_hoje[(df_hoje['Home'] == home_team) & (df_hoje['Away'] == away_team)]
            
            msg = f"⚠️ <b>ALERTA DE SAÍDA LAY AWAY</b> ⚠️\n\n"
            msg += f"⚽ <b>Jogo:</b> {jogo_memoria}\n"
            
            if not jogo_dados.empty:
                row = jogo_dados.iloc[-1]
                odd = row['Odd_A_Lay']
                edge_pct = row['Edge'] * 100
                msg += f"📉 <b>Odd Lay Fora Atual:</b> {odd:.2f}\n"
                msg += f"💎 <b>Edge Atual:</b> {edge_pct:.2f}%\n\n"
                msg += f"❌ <b>Status: Jogo Não Operável</b>\n"
                msg += f"<i>(A odd subiu, o Edge caiu ou o favoritismo virou.)</i>"
            else:
                msg += f"\n❌ <b>Status: Jogo Não Operável</b>\n"
                msg += f"<i>(Partida iniciada, odd suspensa ou mercado fechado.)</i>"

            enviar_mensagem_telegram(msg)
            print(f"Enviado Inoperável: {jogo_memoria}")
            
            jogos_memoria[jogo_memoria] = "inativo"
            novos_envios = True

    if novos_envios:
        salvar_memoria(jogos_memoria)
    else:
        print("Nenhuma mudança de status nos jogos encontrados hoje.")

if __name__ == "__main__":
    rodar_bot()
