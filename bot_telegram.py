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
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TOKEN_FUT = "b9f385cc07be27e7b04fe3a68c15120dd633d109"
headers = {"Authorization": f"Token {TOKEN_FUT}"}

# Arquivo de memória para não enviar jogos repetidos no mesmo dia
ARQUIVO_MEMORIA = "jogos_enviados.json"

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
                    return dados.get("enviados", [])
    except Exception as e:
        print(f"Erro ao ler memória: {e}")
    return []

def salvar_memoria(lista_enviados):
    hoje = datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%Y-%m-%d')
    with open(ARQUIVO_MEMORIA, 'w') as f:
        json.dump({"data": hoje, "enviados": lista_enviados}, f)

# --- FUNÇÕES DE DADOS (Mesmas do app.py, mas sem st.cache) ---
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
# MOTOR PRINCIPAL (Adaptado para rodar silencioso)
# ==========================================
def rodar_bot():
    print("Iniciando varredura...")
    fuso_br = pytz.timezone('America/Sao_Paulo')
    hoje = datetime.now(fuso_br)
    data_str = hoje.strftime('%Y-%m-%d')

    # Carrega dados
    try:
        dados_modelo = joblib.load('Modelo_LayAway_6.pkl')
    except Exception as e:
        print("Erro ao carregar modelo:", e)
        return

    model = dados_modelo['modelo']
    taxas_ligas = dados_modelo['liga_rates']
    media_global_treino = dados_modelo['media_global']
    X_cols_treino = dados_modelo['features']

    # Puxa jogos de hoje
    df_alvo = baixar_jogos_do_dia(data_str)
    if df_alvo.empty:
        print("Nenhum jogo no radar hoje.")
        return

    df_hist = baixar_base_dados()
    
    # Simula os tradutores do seu código original (coloque aqui os dicionários completos do seu app.py)
    tradutor_ligas = {"Argentinian Primera Division": "ARGENTINA 1", "Argentinian Primera B Nacional": "ARGENTINA 2", "Australian A-League Men": "AUSTRALIA 1", 
                      "Austrian Bundesliga": "AUSTRIA 1", "Austrian Erste Liga": "AUSTRIA 2", "Belgian First Division A": "BELGIUM 1", "Brazilian Serie A": "BRAZIL 1", 
                      "Chilean Primera Division": "CHILE 1", "Chinese Super League": "CHINA 1", "Czech 1 Liga": "CZECH 1", "Danish Superliga": "DENMARK 1", 
                      "Ecuadorian Serie A": "ECUADOR 1", "English Premier League": "ENGLAND 1", "English Championship": "ENGLAND 2", "English League 2": "ENGLAND 4", 
                      "UEFA Europa Conference League": "EUROPA CONFERENCE LEAGUE", "UEFA Europa League": "EUROPA LEAGUE", "French National": "FRANCE 3", "German Bundesliga": "GERMANY 1",
                      "German 3 Liga": "GERMANY 3", "Icelandic Urvalsdeild": "ICELAND 1", "Irish Premier Division": "IRELAND 1", "Irish Division 1": "IRELAND 2", "Italian Serie B": "ITALY 2", 
                      "Italian Serie C": "ITALY 3", "Japanese J League": "JAPAN 1", "Mexican Liga MX": "MEXICO 1", "Norwegian Eliteserien": "NORWAY 1", "Paraguayan Primera Division": "PARAGUAY 1", 
                      "Portuguese Segunda Liga": "PORTUGAL 2", "Romanian Liga I": "ROMANIA 1", "Saudi Professional League": "SAUDI ARABIA 1", "South Korean K League 2": "SOUTH KOREA 2", 
                      "Spanish La Liga": "SPAIN 1", "Spanish Segunda Division": "SPAIN 2", "Swiss Super League": "SWITZERLAND 1", "Turkish Super League": "TURKEY 1", "Turkiye - 1st Lig": "TURKEY 2",
                      "US MLS": "USA 1"}
    
    tradutor_times = {"KSV 1919": "Kapfenberg", "Al-Jndal": "Al Jandal", "Jeddah Club": "Jeddah", "Deportivo": "Dep. La Coruna", "Nacional (Par)": "Nacional Asuncion", 
                      "Rapid Bucharest": "FC Rapid 1923", "NEOM Sports Club": "Neom SC", "Al-Wahda (KSA)": "Al Wehda", "Erzgebirge": "Aue", "Zhejiang Greentown": "Zhejiang Professional", 
                      "Al-Raed (KSA)": "Al Raed", "ASD Alcione": "Alcione Milano", "Al-Fateh (KSA)": "Al Fateh", "Deportivo Riestra": "Dep. Riestra", "Nottm Forest": "Nottingham", "Al-Hazm (KSA)": 
                      "Al Hazem", "Deportes Concepcion": "D. Concepcion", "Dhamk": "Damac", "Al-Taawoun Buraidah": "Al Taawon", "RZ Pellets WAC": "Wolfsberger AC", "Gimnasia La Plata": "Gimnasia L.P.", 
                      "Al-Akhdoud": "Al Okhdood", "Athlone Town": "Athlone", "Kerry FC": "Kerry", "OB": "Odense", "Lask Linz": "LASK", "WSG Wattens": "WSG Tirol", "Al-Quadisiya (KSA)": "Al Qadsiah", 
                      "Qingdao Youth Island": "Qingdao West Coast", "Farense": "SC Farense", "Sporting Lisbon B": "Sporting CP B", 
                      "Western Sydney Wanderers": "WS Wanderers", "Leverkusen": "Bayer Leverkusen", "Botosani": "FC Botosani", "Andorra CF": "Andorra", "Independiente Rivadavia": "Ind. Rivadavia", 
                      "Talleres": "Talleres Cordoba", "SV Austria Salzburg": "A. Salzburg", "Le Puy": "Le Puy-en-Velay", "Bray Wanderers": "Bray", "Colorado": "Colorado Rapids", "Deportes Limache": "Limache", 
                      "New England": "New England Revolution", "Vasco Da Gama": "Vasco", "Vasco da Gama": "Vasco", "LA Galaxy": "Los Angeles Galaxy", "Wehen Wiesbaden": "Wehen", "Universitatea Cluj": "U. Cluj", 
                      "EC Vitoria Salvador": "Vitoria", "Club Sportivo Ameliano": "Ameliano", "Red Bull Bragantino": "Bragantino", "Guarani (Par)": "Guarani", "Libertad": "Libertad Asuncion", 
                      "Rapid Vienna (Am)": "SK Rapid II", "S.S.D. Casarano Calcio": "Casarano", "ACS Petrolul 52": "Petrolul", "Csikszereda": "Csikszereda M. Ciuc", "1860 Munich": "Munich 1860", 
                      "SSV Ulm": "Ulm", "Cavese 1919": "Cavese", "Villefranche Beaujolais": "Villefranche", "Leonesa": "Cultural Leonesa", "Al-Shabab (KSA)": "Al Shabab", "Al-Kholood Club": "Al Kholood", 
                      "Man Utd": "Manchester Utd", "Sporting Gijon": "Gijon", "AD Ceuta FC": "Ceuta", "FC Guidonia Montecelio 1937": "Guidonia", "Lusitania Futebol Clube": "Lusitania FC", 
                      "US Latina Calcio": "Latina", "Mgladbach": "B. Monchengladbach", "ASD Pineto Calcio": "Pineto", "AZ Picerno ASD": "Picerno", "Waldhof Mannheim": "Mannheim", "Otelul Galati": "Otelul", 
                      "Club 2 de Mayo de Pedro Juan Cab": "2 de Mayo", "Club 2 de Mayo de Pedro Jua": "2 de Mayo", "Club 2 de Mayo": "2 de Mayo", 
                      "Calcio Avellino SSD": "Avellino", "Olimpia": "Olimpia Asuncion", "Team Altamura": "Altamura", "Slovan Liberec": "Liberec", "FC Basel": "Basel", "Cadiz": "Cadiz CF", 
                      "Rot-Weiss Essen": "RW Essen", "Everton De Vina": "Everton", "Galway Utd": "Galway United FC", "Sportivo San Lorenzo": "San Lorenzo", 
                      "Deportivo Recoleta": "Recoleta", "Sportivo Luqueno": "Luqueno", "Banik Ostrava": "Ostrava", "SSD Bari": "Bari", 
                      "Coquimbo Unido": "Coquimbo", "Rapid Vienna": "SK Rapid", "Arzignanochiampo": "Arzignano", "Nuovo Campobasso": "Campobasso", "Pesaro": "Vis Pesaro", "Bohemians 1905": "Bohemians", 
                      "SV Ried": "Ried", "Grasshoppers Zurich": "Grasshoppers", "LASK Linz": "LASK", "First Vienna Fc 1894": "First Vienna", "First Vienna FC 1894": "First Vienna", 
                      "Versailles 78 FC": "Versailles", "MFK Chrudim": "Chrudim", "MFK Karvina": "Karvina", "FC Blau Weiss Linz": "BW Linz", "Sassari Torres": "Torres", 
                      "Al-Khaleej Saihat": "Al Khaleej", "Inter Milan (Res)": "Inter U23", "Wexford F.C": "Wexford FC", "Vejle": "Vejle Boldklub", "Brondby": "Broendby IF", "Clermont": "Clermont Foot 63", 
                      "Alaves": "Deportivo Alaves", "Longford": "Longford Town", "Estoril Praia": "Estoril", "St Patricks": "St. Patrick's Athletic", "Western Sydney Wanderers": "Western Sydney Wanderers FC", 
                      "Ayr": "Ayr United", "Betis": "Real Betis", "Rapid Vienna": "Rapid Wien", "Paris St-G": "Paris Saint-Germain", "IBV": "IBV Vestmannaeyjar", "Dortmund": "Borussia Dortmund", 
                      "CD Nacional Funchal": "Nacional", "Kasimpasa": "Kasımpaşa", "Odds BK": "Odds Ballklubb", "Stabaek": "Stabaek", "Nurnberg": "1. FC Nuremberg", "Bochum": "VfL Bochum", "St Mirren": "St. Mirren",
                      "Athletic Bilbao": "Athletic Club", "Guimaraes": "Vitoria de Guimaraes", "ACS Petrolul 52": "Petrolul Ploiesti", "Roma": "AS Roma", "Leeds": "Leeds United", "Fleury Merogis": "FC Fleury 91",
                      "FK Javor Ivanjica": "Javor", "Man City": "Manchester City", "Porto": "FC Porto", "Sporting Lisbon": "Sporting CP", "Everton De Vina": "Everton CD", 
                      "Cracovia Krakow": "Cracovia", "Deportes Limache": "Club Deportes Limache", "OHiggins": "O'Higgins", "Club Football Estrela": "CF Estrela da Amadora", "Entella": "Virtus Entella",
                      "Dunfermline": "Dunfermline Athletic", "Las Palmas": "Las Palmas", "CD Castellon": "Castellon", "Univ de Concepcion": "Universidad de Concepcion", "Roda JC": "Roda JC Kerkrade",
                      "Bohemians": "Bohemian FC", "Nieciecza": "Termalica Nieciecza", "Braunschweig": "Eintracht Braunschweig", "Obolon-Brovar Kiev": "FC Obolon Kyiv", "Rukh Vynnyky": "Rukh Lviv",
                      "FK Spartak": "FK Spartak Subotica", "Padova": "Calcio Padova", "Jong PSV Eindhoven": "Jong PSV", "Raith": "Raith Rovers", "Pescara": "Pescara Calcio", "Ross Co": "Ross County", 
                      "Sociedad B": "Real Sociedad B", "SC Telstar": "Telstar", "Philadelphia": "Philadelphia Union", "FK Backa Topola": "TSC Backa Topola", "Hartberg": "TSV Hartberg", "FK Napredak": "Napredak",
                      "Casa Pia": "Casa Pia AC", "FK IMT Novi Beograd": "FK IMT Beograd", "Brisbane Roar": "Brisbane Roar FC", "Partick": "Partick Thistle", "Univ Catolica (Chile)": "Universidad Catolica", 
                      "Oviedo": "Real Oviedo", "Fenerbahce": "Fenerbahçe", "Midtjylland": "FC Midtjylland", "Braga": "SC Braga", "76 Igdir Belediyespor": "Igdir FK", "Pyramids": "Pyramids FC", "Al Ahly Cairo": "Al Ahly",
                      "Melbourne City": "Melbourne City FC", "Cesena": "Cesena FC", "Morton": "Greenock Morton", "Dobrudzha": "Dobrudzha Dobrich", "Lokomotiv Sofia": "PFC Lokomotiv Sofia 1929", "PSV": "PSV Eindhoven",
                      "Fatih Karagumruk Istanbul": "Fatih Karagumruk", "Falkenbergs": "Falkenbergs FF", "Norrkoping": "IFK Norrkoeping", "Arda": "Arda Kardzhali", "Ranheim IL": "Ranheim", "Monaco": "AS Monaco",
                      "Septemvri": "Septemvri Sofia", "Avai": "Avai FC", "Fortaleza EC": "Fortaleza", "Randers": "Randers FC", "Hafnarfjordur": "FH Hafnarfjordur"
                     }

    df_alvo['id_jogo'] = range(1, len(df_alvo) + 1)
    if 'League' in df_alvo.columns:
        df_alvo['League'] = df_alvo['League'].replace(tradutor_ligas)
        df_alvo['Home'] = df_alvo['Home'].replace(tradutor_times)
        df_alvo['Away'] = df_alvo['Away'].replace(tradutor_times)

    def safe_prob(column): return (1 / pd.to_numeric(column, errors='coerce').replace(0, np.nan)).fillna(0)
    data_limite = df_alvo['Date'].min()

    # Cria df_completo (simplificado para o script)
    if not df_hist.empty:
        df_hist_passado = df_hist[df_hist['Date'] < data_limite].copy()
        df_completo = pd.concat([df_hist_passado, df_alvo], ignore_index=True)
    else:
        df_completo = df_alvo.copy()

    df_completo = df_completo.reset_index(drop=True).sort_values(["Date", "Home"])
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

    # Pegar só os jogos de hoje
    df_hoje = df_completo[df_completo['id_jogo'].notnull()].copy()
    df_hoje = df_hoje[df_hoje['Date'].dt.date == hoje.date()].copy()

    # Filtros base
    df_hoje = df_hoje[(df_hoje['Odd_A_Lay'] <= 3.50) & (df_hoje['Odd_H_Back'] < df_hoje['Odd_A_Back'])].copy()

    colunas_vitais = list(X_cols_treino) + ['Odd_A_Lay', 'Home', 'Away', 'League', 'Time']
    colunas_vitais = [col for col in colunas_vitais if col in df_hoje.columns]
    df_hoje = df_hoje.dropna(subset=colunas_vitais)

    if len(df_hoje) == 0:
        print("Nenhum jogo passou nos filtros base.")
        return

    # Previsão
    df_hoje["Previsao"] = model.predict_proba(df_hoje[X_cols_treino])[:, 1]
    df_hoje["Edge"] = df_hoje["Previsao"] - (1 - (1 / df_hoje["Odd_A_Lay"]))
    
    # FILTRO FINAL: Apenas Edge positivo e Score aceitável (Ajuste conforme quiser)
    df_bruto = df_hoje[df_hoje["Edge"] >= 0.0].copy()

    if df_bruto.empty:
        print("Nenhum jogo com Edge+ encontrado agora.")
        return

    # Processar envios
    jogos_ja_enviados = carregar_memoria()
    novos_envios = False

    for index, row in df_bruto.iterrows():
        id_jogo_str = f"{row['Home']} x {row['Away']}"
        
        if id_jogo_str not in jogos_ja_enviados:
            edge_pct = row['Edge'] * 100
            odd = row['Odd_A_Lay']
            horario = row['Time']
            liga = row['League']

            # Monta a mensagem no estilo Telegram
            msg = f"🚨 <b>NOVO ALERTA LAY AWAY</b> 🚨\n\n"
            msg += f"⚽ <b>Jogo:</b> {id_jogo_str}\n"
            msg += f"🏆 <b>Liga:</b> {liga}\n"
            msg += f"⏰ <b>Horário:</b> {horario}\n"
            msg += f"📉 <b>Odd Lay Fora:</b> {odd:.2f}\n"
            msg += f"💎 <b>Edge (EV+):</b> {edge_pct:.2f}%\n\n"
            msg += f"👉 <i>Opere com responsabilidade.</i>"

            enviar_mensagem_telegram(msg)
            print(f"Enviado: {id_jogo_str}")
            
            jogos_ja_enviados.append(id_jogo_str)
            novos_envios = True

    if novos_envios:
        salvar_memoria(jogos_ja_enviados)
    else:
        print("Jogos encontrados já haviam sido enviados hoje.")

if __name__ == "__main__":
    rodar_bot()
