import streamlit as st
import pandas as pd
import numpy as np
import joblib
import warnings
from datetime import datetime
import requests
import io
from rapidfuzz import process, fuzz

warnings.filterwarnings("ignore")

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E LOGIN
# ==========================================
st.set_page_config(page_title="Lay Away", page_icon="🎯", layout="wide")

st.markdown("""
    <style>
    div[data-testid="stRadio"] { display: flex !important; justify-content: center !important; align-items: center !important; width: 100% !important; }
    div[data-testid="stRadio"] > div[role="radiogroup"] { display: flex !important; justify-content: center !important; margin: 0 auto !important; width: max-content !important; }
    div[data-testid="stDateInput"] input { text-align: center !important; }
    div[data-testid="stNumberInputContainer"] { display: flex !important; flex-direction: row !important; align-items: center !important; justify-content: space-between !important; height: 32px !important; min-height: 32px !important; }
    div[data-testid="stNumberInputStepDown"] { order: 1 !important; }
    div[data-testid="stNumberInputContainer"] input { order: 2 !important; text-align: center !important; }
    div[data-testid="stNumberInputStepUp"] { order: 3 !important; }
    
    div[data-testid="stButton"] > button { background-color: #0068c9 !important; color: white !important; font-weight: bold !important; border-radius: 5px !important; }
    div[data-testid="stButton"] > button:hover { background-color: #0052a3 !important; border-color: #0052a3 !important; color: white !important; }
    div[data-testid="stDownloadButton"] > button { background-color: #FF00FF !important; border-radius: 5px !important; width: 100% !important; margin-top: 5px !important; }
    div[data-testid="stDownloadButton"] > button p { color: black !important; font-weight: 900 !important; font-size: 16px !important; margin: 0 !important; }
    div[data-testid="stDownloadButton"] > button:hover { background-color: #CC00CC !important; border-color: #CC00CC !important; }
    
    /* CSS para o Tooltip Customizado na Tabela HTML */
    .tooltip-header { cursor: help; border-bottom: 1px dotted #ffffff; }
    </style>
""", unsafe_allow_html=True)

def check_password():
    if st.session_state.get("password_correct", False): return True
    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    with col2:
        st.image("logo.png", use_container_width=True)
        def password_entered():
            if st.session_state["password"] == st.secrets["senha_secreta"]:
                st.session_state["password_correct"] = True
                del st.session_state["password"]
            else: st.session_state["password_correct"] = False

        if "password_correct" not in st.session_state:
            st.text_input("🔑 Digite a senha para acessar:", type="password", on_change=password_entered, key="password")
            return False
        elif not st.session_state["password_correct"]:
            st.text_input("🔑 Digite a senha para acessar:", type="password", on_change=password_entered, key="password")
            st.error("❌ Senha incorreta.")
            return False
    return True

# ==========================================
# FUNÇÕES DE CARREGAMENTO (COM CACHE)
# ==========================================
TOKEN = "b9f385cc07be27e7b04fe3a68c15120dd633d109"
headers = {"Authorization": f"Token {TOKEN}"}

@st.cache_data(ttl=1800)
def baixar_base_dados():
    try:
        response = requests.get("https://api.futpythontrader.com/api/dados/betfair/download/", headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(io.BytesIO(response.content))
            if not df.empty and 'Date' in df.columns: df['Date'] = pd.to_datetime(df['Date'])
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300) 
def baixar_jogos_do_dia(data):
    try:
        url = f"https://api.futpythontrader.com/api/dados/jogos-do-dia/betfair/{data}/download/"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            df_api = pd.read_csv(io.BytesIO(response.content))
            if not df_api.empty and 'Date' in df_api.columns: df_api['Date'] = pd.to_datetime(df_api['Date'])
            return df_api
        return pd.DataFrame()
    except: return pd.DataFrame()

# ==========================================
# CÓDIGO DO SCANNER
# ==========================================
if check_password():
    col_t1, col_t2, col_t3 = st.columns([1.5, 1, 1.5])
    with col_t2:
        st.markdown("<h2 style='text-align: center;'>🎯 Scanner Lay Away</h2>", unsafe_allow_html=True)
        col_rad1, col_rad2, col_rad3 = st.columns([0.4, 2, 0.4])
        with col_rad2: tipo_filtro = st.radio("Formato de Pesquisa:", ["Data Única", "Intervalo de Datas"], horizontal=True, label_visibility="collapsed")
        
        hoje = datetime.now().date()
        st.markdown("<br>", unsafe_allow_html=True)
        
        if tipo_filtro == "Data Única":
            st.markdown("<p style='text-align: center; margin-bottom: 5px; font-weight: bold;'>📅 Escolha a data para consulta:</p>", unsafe_allow_html=True)
            data_selecionada = st.date_input("Data única", value=hoje, format="DD/MM/YYYY", label_visibility="collapsed")
        else:
            st.markdown("<p style='text-align: center; margin-bottom: 5px; font-weight: bold;'>📅 Escolha o período para consulta:</p>", unsafe_allow_html=True)
            data_selecionada = st.date_input("Intervalo", value=(hoje, hoje), format="DD/MM/YYYY", label_visibility="collapsed")
            
        st.markdown("<br>", unsafe_allow_html=True)
        btn_procurar = st.button("🚀 Iniciar Varredura", use_container_width=True)
        espaco_download = st.empty()
        
    st.divider()

    if btn_procurar:
        st.session_state['mostrar_tabela'] = False 
        
        with st.spinner('Baixando inteligência e processando o mercado...'):
            try:
                dados_modelo = joblib.load('Modelo_LayAway_5.pkl')
                model = dados_modelo['modelo']
                taxas_ligas = dados_modelo['liga_rates']
                media_global_treino = dados_modelo['media_global']
                X_cols_treino = dados_modelo['features']
                ligas_autorizadas = dados_modelo.get('ligas_autorizadas', [])
                
                df_hist = baixar_base_dados()
                df_alvo_lista = []
                
                if tipo_filtro == "Data Única":
                    texto_data = data_selecionada.strftime('%d/%m/%Y')
                    df_dia = baixar_jogos_do_dia(data_selecionada.strftime('%Y-%m-%d'))
                    if not df_dia.empty: df_alvo_lista.append(df_dia)
                else:
                    d_inicio, d_fim = data_selecionada if isinstance(data_selecionada, tuple) and len(data_selecionada) == 2 else (data_selecionada[0], data_selecionada[0])
                    texto_data = f"de {d_inicio.strftime('%d/%m/%Y')} até {d_fim.strftime('%d/%m/%Y')}"
                    for data_atual in pd.date_range(start=d_inicio, end=d_fim):
                        df_dia = baixar_jogos_do_dia(data_atual.strftime('%Y-%m-%d'))
                        if not df_dia.empty: df_alvo_lista.append(df_dia)
                
                df_alvo = pd.concat(df_alvo_lista, ignore_index=True) if df_alvo_lista else pd.DataFrame()
                
                tradutor_ligas = {"Argentinian Primera Division": "ARGENTINA 1", "Argentinian Primera B Nacional": "ARGENTINA 2", "Australian A-League Men": "AUSTRALIA 1", "Austrian Bundesliga": "AUSTRIA 1", "Austrian Erste Liga": "AUSTRIA 2", "Belgian First Division A": "BELGIUM 1", "Brazilian Serie A": "BRAZIL 1", "Chilean Primera Division": "CHILE 1", "Chinese Super League": "CHINA 1", "Czech 1 Liga": "CZECH 1", "Danish Superliga": "DENMARK 1", "Ecuadorian Serie A": "ECUADOR 1", "English Premier League": "ENGLAND 1", "English Championship": "ENGLAND 2", "English League 2": "ENGLAND 4", "UEFA Europa Conference League": "EUROPA CONFERENCE LEAGUE", "UEFA Europa League": "EUROPA LEAGUE", "French National": "FRANCE 3", "German Bundesliga": "GERMANY 1", "German 3 Liga": "GERMANY 3", "Icelandic Urvalsdeild": "ICELAND 1", "Irish Premier Division": "IRELAND 1", "Irish Division 1": "IRELAND 2", "Italian Serie B": "ITALY 2", "Italian Serie C": "ITALY 3", "Japanese J League": "JAPAN 1", "Mexican Liga MX": "MEXICO 1", "Norwegian Eliteserien": "NORWAY 1", "Paraguayan Primera Division": "PARAGUAY 1", "Portuguese Segunda Liga": "PORTUGAL 2", "Romanian Liga I": "ROMANIA 1", "Saudi Professional League": "SAUDI ARABIA 1", "South Korean K League 2": "SOUTH KOREA 2", "Spanish La Liga": "SPAIN 1", "Spanish Segunda Division": "SPAIN 2", "Swiss Super League": "SWITZERLAND 1", "Turkish Super League": "TURKEY 1", "US MLS": "USA 1"}
                tradutor_times = {"UCD": "UC Dublin", "KSV 1919": "Kapfenberg", "Al-Jndal": "Al Jandal", "Jeddah Club": "Jeddah", "Deportivo": "Dep. La Coruna", "Nacional (Par)": "Nacional Asuncion", "Rapid Bucharest": "FC Rapid Bucuresti", "NEOM Sports Club": "Neom SC", "Al-Wahda (KSA)": "Al Wehda", "Erzgebirge": "Aue", "Zhejiang Greentown": "Zhejiang Professional", "Al-Raed (KSA)": "Al Raed", "ASD Alcione": "Alcione Milano", "Al-Fateh (KSA)": "Al Fateh", "Deportivo Riestra": "Dep. Riestra", "Nottm Forest": "Nottingham", "Al-Hazm (KSA)": "Al Hazem", "Deportes Concepcion": "D. Concepcion", "Dhamk": "Damac", "Al-Taawoun Buraidah": "Al Taawon", "RZ Pellets WAC": "Wolfsberger AC", "Gimnasia La Plata": "Gimnasia L.P.", "Al-Akhdoud": "Al Okhdood", "Athlone Town": "Athlone", "Kerry FC": "Kerry", "OB": "Odense", "Lask Linz": "LASK", "WSG Wattens": "Tirol", "Al-Quadisiya (KSA)": "Al Qadsiah", "Shenzhen Peng City": "Shenzhen Xinpengcheng", "Qingdao Youth Island": "Qingdao West Coast", "Farense": "SC Farense", "Sporting Lisbon B": "Sporting CP B", "Western Sydney Wanderers": "WS Wanderers", "Leverkusen": "Bayer Leverkusen", "Botosani": "FC Botosani", "Andorra CF": "Andorra", "Independiente Rivadavia": "Ind. Rivadavia", "Talleres": "Talleres Cordoba", "SV Austria Salzburg": "A. Salzburg", "Le Puy": "Le Puy-en-Velay", "Bray Wanderers": "Bray", "Colorado": "Colorado Rapids", "Deportes Limache": "Limache", "New England": "New England Revolution", "Vasco Da Gama": "Vasco", "Vasco da Gama": "Vasco", "LA Galaxy": "Los Angeles Galaxy", "Wehen Wiesbaden": "Wehen", "Universitatea Cluj": "U. Cluj", "EC Vitoria Salvador": "Vitoria", "Club Sportivo Ameliano": "Ameliano", "Red Bull Bragantino": "Bragantino", "Guarani (Par)": "Guarani", "Libertad": "Libertad Asuncion", "Rapid Vienna (Am)": "SK Rapid II", "S.S.D. Casarano Calcio": "Casarano", "ACS Petrolul 52": "Petrolul", "Csikszereda": "Csikszereda M. Ciuc", "1860 Munich": "Munich 1860", "SSV Ulm": "Ulm", "Cavese 1919": "Cavese", "Villefranche Beaujolais": "Villefranche", "Leonesa": "Cultural Leonesa", "Al-Shabab (KSA)": "Al Shabab", "Al-Kholood Club": "Al Kholood", "Man Utd": "Manchester Utd", "Sporting Gijon": "Gijon", "AD Ceuta FC": "Ceuta", "FC Guidonia Montecelio 1937": "Guidonia", "Lusitania Futebol Clube": "Lusitania FC", "US Latina Calcio": "Latina", "Mgladbach": "B. Monchengladbach", "ASD Pineto Calcio": "Pineto", "AZ Picerno ASD": "Picerno", "Waldhof Mannheim": "Mannheim", "Otelul Galati": "Otelul", "Club 2 de Mayo de Pedro Juan Cab": "2 de Mayo", "Club 2 de Mayo de Pedro Jua": "2 de Mayo", "Club 2 de Mayo": "2 de Mayo", "Sportivo Luquen": "Sp. Luqueno", "Calcio Avellino SSD": "Avellino", "Olimpia": "Olimpia Asuncion", "Team Altamura": "Altamura", "Slovan Liberec": "Liberec", "FC Basel": "Basel", "Cadiz": "Cadiz CF", "Rot-Weiss Essen": "RW Essen", "Everton De Vina": "Everton", "U. De Concepcion": "D. Concepcion", "Galway Utd": "Galway", "Sportivo San Lorenzo": "San Lorenzo", "Deportivo Recoleta": "Recoleta", "Sportivo Luqueno": "Sp. Luqueno", "Fatih Karagumruk Istanbul": "Karagumruk", "Banik Ostrava": "Ostrava", "SSD Bari": "Bari", "Coquimbo Unido": "Coquimbo", "Rapid Vienna": "SK Rapid", "Arzignanochiampo": "Arzignano", "Nuovo Campobasso": "Campobasso", "Pesaro": "Vis Pesaro", "Bohemians 1905": "Bohemians", "SV Ried": "Ried", "Grasshoppers Zurich": "Grasshoppers", "LASK Linz": "LASK", "First Vienna Fc 1894": "First Vienna", "First Vienna FC 1894": "First Vienna", "Versailles 78 FC": "Versailles", "MFK Chrudim": "Chrudim", "MFK Karvina": "Karvina", "FC Blau Weiss Linz": "BW Linz", "Universidad de Chile": "U. De Chile", "Sassari Torres": "Torres", "Al-Khaleej Saihat": "Al Khaleej", "Inter Milan (Res)": "Inter U23", "Wexford F.C": "Wexford"}
                
                if not df_alvo.empty and 'League' in df_alvo.columns:
                    df_alvo['League'] = df_alvo['League'].replace(tradutor_ligas)
                    df_alvo = df_alvo[df_alvo['League'].isin(ligas_autorizadas)].copy()
                    df_alvo['Home'] = df_alvo['Home'].replace(tradutor_times)
                    df_alvo['Away'] = df_alvo['Away'].replace(tradutor_times)
                
                if len(df_alvo) == 0:
                    st.info(f"A API não identificou jogos cadastrados e autorizados para {texto_data}.")
                else:
                    def safe_prob(column): return (1 / pd.to_numeric(column, errors='coerce').replace(0, np.nan)).fillna(0)
                        
                    data_limite = df_alvo['Date'].min()
                    if not df_hist.empty:
                        df_hist_passado = df_hist[df_hist['Date'] < data_limite].copy()
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
                        
                        if dicionario_times_fuzzy:
                            df_alvo['Home'] = df_alvo.apply(lambda r: dicionario_times_fuzzy.get((r['League'], r['Home']), r['Home']), axis=1)
                            df_alvo['Away'] = df_alvo.apply(lambda r: dicionario_times_fuzzy.get((r['League'], r['Away']), r['Away']), axis=1)
                        df_completo = pd.concat([df_hist_passado, df_alvo], ignore_index=True)
                    else:
                        df_completo = df_alvo.copy()
                        
                    df_completo = df_completo.sort_values(["Date", "Home"]).reset_index(drop=True)
                    
                    # ========================================================
                    # NOVAS MÉTRICAS DE RISCO E ESTATÍSTICA (SEM SG)
                    # ========================================================
                    df_completo['Goals_H_FT'] = pd.to_numeric(df_completo['Goals_H_FT'], errors='coerce')
                    df_completo['Goals_A_FT'] = pd.to_numeric(df_completo['Goals_A_FT'], errors='coerce')

                    # 1. Pontos Básicos
                    df_completo['Pts_H'] = np.where(df_completo['Goals_H_FT'] > df_completo['Goals_A_FT'], 3, np.where(df_completo['Goals_H_FT'] == df_completo['Goals_A_FT'], 1, 0))
                    df_completo['Pts_A'] = np.where(df_completo['Goals_A_FT'] > df_completo['Goals_H_FT'], 3, np.where(df_completo['Goals_A_FT'] == df_completo['Goals_H_FT'], 1, 0))
                    
                    soma_pts_casa = df_completo.groupby('Home')['Pts_H'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
                    soma_pts_fora = df_completo.groupby('Away')['Pts_A'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
                    qtd_jogos_casa = df_completo.groupby('Home')['Pts_H'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).count())
                    qtd_jogos_fora = df_completo.groupby('Away')['Pts_A'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).count())
                    
                    # 2. Clean Sheet Casa e FTS Fora (Frequências)
                    df_completo['Is_CS_Casa'] = (df_completo['Goals_A_FT'] == 0).astype(int)
                    df_completo['Is_FTS_Fora'] = (df_completo['Goals_A_FT'] == 0).astype(int)
                    
                    soma_cs_casa = df_completo.groupby('Home')['Is_CS_Casa'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean()) * 100
                    soma_fts_fora = df_completo.groupby('Away')['Is_FTS_Fora'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean()) * 100
                    
                    # 3. Desvios Padrões (Volatilidade) e Vazamento
                    dp_gs_casa = df_completo.groupby('Home')['Goals_A_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=2).std())
                    dp_gm_fora = df_completo.groupby('Away')['Goals_A_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=2).std())
                    vaz_def_fora = df_completo.groupby('Away')['Goals_H_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())

                    # Aplicação ao DataFrame
                    df_completo['Pontos Casa'] = np.where(qtd_jogos_casa > 0, soma_pts_casa.fillna(0).astype(int).astype(str), "-")
                    df_completo['Pontos Fora'] = np.where(qtd_jogos_fora > 0, soma_pts_fora.fillna(0).astype(int).astype(str), "-")
                    
                    df_completo['CS Casa'] = np.where(qtd_jogos_casa > 0, soma_cs_casa.fillna(0).astype(int).astype(str) + "%", "-")
                    df_completo['FTS Fora'] = np.where(qtd_jogos_fora > 0, soma_fts_fora.fillna(0).astype(int).astype(str) + "%", "-")
                    
                    df_completo['DP GS Casa'] = np.where(qtd_jogos_casa > 1, dp_gs_casa.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['DP GM Fora'] = np.where(qtd_jogos_fora > 1, dp_gm_fora.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['Vaz Def Fora'] = np.where(qtd_jogos_fora > 0, vaz_def_fora.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    
                    # ========================================================
                    # EXPECTATIVA DE GOLS DO MERCADO (Pseudo-xG)
                    # ========================================================
                    prob_h = safe_prob(df_completo['Odd_H_Back'])
                    prob_a = safe_prob(df_completo['Odd_A_Back'])
                    prob_o25 = safe_prob(df_completo['Odd_Over25_FT_Back'])
                    
                    prob_d = np.clip(1.0 - prob_h - prob_a, 0.1, 1.0)
                    exp_tg = np.where(prob_o25 > 0, 1.25 + (prob_o25 * 2.5), 2.5) 
                    soma_probs = prob_h + prob_a + prob_d
                    
                    df_completo['XG_Casa'] = np.where(prob_h > 0, (exp_tg * (prob_h + 0.5 * prob_d) / soma_probs), np.nan)
                    df_completo['XG_Fora'] = np.where(prob_a > 0, (exp_tg * (prob_a + 0.5 * prob_d) / soma_probs), np.nan)
                    
                    # ========================================================
                    df_completo['Prob_1x2_A'] = safe_prob(df_completo['Odd_A_Back'])
                    df_completo['Prob_CS_Resistance'] = safe_prob(df_completo['Odd_CS_1x0_Lay']) + safe_prob(df_completo['Odd_CS_2x1_Lay'])
                    df_completo['Market_Asymmetry'] = (df_completo['Prob_CS_Resistance'] - df_completo['Prob_1x2_A'])
                    df_completo['Draw_Density'] = safe_prob(df_completo['Odd_CS_0x0_Lay']) + safe_prob(df_completo['Odd_CS_1x1_Lay'])
                    df_completo['Volatility_Risk'] = np.clip((df_completo['Odd_Over25_FT_Back'] / (df_completo['Odd_A_Back'].replace(0, np.nan))), 0, 50)
                    df_completo['Away_Odd_Trend'] = df_completo.groupby('Away')['Odd_A_Back'].transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean() - x.shift(1)).fillna(0)
                    df_completo['Home_HT_Def_Power'] = df_completo.groupby('Home')['Goals_A_HT'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean()).fillna(0)
                    df_completo['Home_Attack_Strength'] = df_completo.groupby('Home')['Goals_H_FT'].transform(lambda x: x.shift(1).rolling(8, min_periods=1).mean()).fillna(0)
                    df_completo['Away_Attack_Strength'] = df_completo.groupby('Away')['Goals_A_FT'].transform(lambda x: x.shift(1).rolling(8, min_periods=1).mean()).fillna(0)
                    df_completo['Power_Diff'] = df_completo['Home_Attack_Strength'] - df_completo['Away_Attack_Strength']
                    df_completo['League_Avg_Goals'] = df_completo.groupby('League')['Goals_H_FT'].transform(lambda x: x.shift(1).expanding().mean()).fillna(df_completo['Goals_H_FT'].mean())
                    df_completo["LIGA_RATE"] = df_completo["League"].map(taxas_ligas).fillna(media_global_treino)
                    
                    if tipo_filtro == "Data Única":
                        df_hoje = df_completo[df_completo['Date'].dt.date == data_selecionada].copy()
                    else:
                        df_hoje = df_completo[(df_completo['Date'].dt.date >= d_inicio) & (df_completo['Date'].dt.date <= d_fim)].copy()
                        
                    df_hoje = df_hoje[(df_hoje['Odd_A_Lay'] <= 5.00) & (df_hoje['Odd_H_Back'] < df_hoje['Odd_A_Back']) & (abs(df_hoje['Odd_A_Back'] - df_hoje['Odd_A_Lay']) <= 1.00) & (abs(df_hoje['Odd_H_Back'] - df_hoje['Odd_H_Lay']) <= 1.00)].copy()
                    
                    if len(df_hoje) == 0:
                        st.info("Nenhum jogo passou nos filtros iniciais de Odd (Máx 5.00).")
                    else:
                        colunas_vitais = list(X_cols_treino) + ['Odd_A_Lay', 'Home', 'Away', 'League', 'Date']
                        colunas_vitais = [col for col in colunas_vitais if col in df_hoje.columns]
                        
                        df_hoje = df_hoje.dropna(subset=colunas_vitais).reset_index(drop=True)
                        
                        if len(df_hoje) == 0:
                            st.warning(f"Foram encontrados jogos para {texto_data}, mas eles foram descartados pois não possuem histórico estatístico suficiente para o modelo analisar.")
                        else:
                            df_hoje["Previsao"] = model.predict_proba(df_hoje[X_cols_treino])[:, 1]
                            df_hoje["Edge"] = df_hoje["Previsao"] - (1 - (1 / df_hoje["Odd_A_Lay"]))
                            
                            df_bruto = df_hoje[df_hoje["Edge"] >= 0.0].copy()
                            
                            if len(df_bruto) == 0:
                                st.warning(f"O modelo filtrou o mercado, mas não encontrou Edge suficiente (>0.0%) para operar em {texto_data}.")
                            else:
                                st.session_state['mostrar_tabela'] = True
                                st.session_state['df_bruto'] = df_bruto

            except Exception as e:
                st.error(f"Erro inesperado durante o processamento: {e}")

    # ==========================================
    # EXIBIÇÃO VISUAL E BOTÃO DE DOWNLOAD
    # ==========================================
    if st.session_state.get('mostrar_tabela', False):
        df_bruto = st.session_state['df_bruto']
        
        col_esq, col_central, col_dir = st.columns([1, 4, 1])
        with col_central:
            col_texto, col_vazia, col_filtro_odd, col_filtro_edge = st.columns([4.0, 0.5, 1.25, 1.25])
            
            with col_filtro_odd:
                st.markdown("<div style='text-align: center; font-size: 16px; font-weight: bold; margin-bottom: 5px; margin-top: 25px;'>Mín Odd Lay</div>", unsafe_allow_html=True)
                odd_selecionada = st.number_input("Mín Odd Lay", min_value=2.50, max_value=5.0, value=2.50, step=0.10, format="%.2f", label_visibility="collapsed")

            with col_filtro_edge:
                st.markdown("<div style='text-align: center; font-size: 16px; font-weight: bold; margin-bottom: 5px; margin-top: 25px;'>Edge Mínimo (%)</div>", unsafe_allow_html=True)
                edge_selecionado = st.number_input("Edge Mínimo (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, format="%.1f", label_visibility="collapsed")
            
            df_filtrado_odd = df_bruto[df_bruto["Odd_A_Lay"] >= odd_selecionada].copy()
            edge_decimal = edge_selecionado / 100.0
            df_final_filtrado = df_filtrado_odd[df_filtrado_odd["Edge"] >= edge_decimal].copy()
            
            with col_texto:
                texto_resultado = f"""
                <div style='text-align: left; font-size: 18px; margin-top: 40px; margin-bottom: 10px; white-space: nowrap;'>
                    Oportunidades Encontradas: <span style='color: #00d26a; background-color: rgba(0, 210, 106, 0.1); padding: 4px 12px; border-radius: 6px; font-weight: bold;'>{len(df_final_filtrado)} jogo(s)</span>
                </div>
                """
                st.markdown(texto_resultado, unsafe_allow_html=True)

            # Separa as colunas atualizadas
            tabela = df_final_filtrado[['Date', 'Time', 'League', 'Home', 'Away', 'Pontos Casa', 'Pontos Fora', 'FTS Fora', 'DP GM Fora', 'DP GS Casa', 'Vaz Def Fora', 'CS Casa', 'XG_Casa', 'XG_Fora', 'Odd_A_Lay', 'Edge']].copy()
            
            # Formatação Básica
            if not tabela.empty:
                tabela['Date'] = pd.to_datetime(tabela['Date'])
                tabela = tabela.sort_values(by=['Date', 'Time'], ascending=[True, True]).reset_index(drop=True)
                tabela['Date'] = tabela['Date'].dt.strftime('%d/%m/%Y')

                # Tabela de Exportação Excel (Sem código HTML nos Títulos)
                tabela_excel = tabela.rename(columns={
                    'Date': 'Data', 'Time': 'Horário', 'League': 'Liga', 'Home': 'Time Casa', 'Away': 'Time Fora',
                    'Pontos Casa': 'Pts Casa', 'Pontos Fora': 'Pts Fora',
                    'XG_Casa': 'xG Casa', 'XG_Fora': 'xG Fora', 'Odd_A_Lay': 'Odd Lay', 'Edge': 'Vantagem'
                })

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    tabela_excel.to_excel(writer, index=False, sheet_name='Lay_Away')
                
                with espaco_download:
                    st.download_button("📥 Baixar Jogos", data=buffer.getvalue(), file_name="Jogos_LayAway.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                
                # Tabela de Exibição Web (Com Nomes Limpos para o Pandas processar)
                tabela_web = tabela.rename(columns={
                    'Date': 'Data', 'Time': 'Horário', 'League': 'Liga', 'Home': 'Time Casa', 'Away': 'Time Fora',
                    'Pontos Casa': 'Pts Casa', 'Pontos Fora': 'Pts Fora',
                    'XG_Casa': 'xG Casa', 'XG_Fora': 'xG Fora', 'Odd_A_Lay': 'Odd Lay', 'Edge': 'Vantagem'
                })

                # ========================================================
                # LÓGICA DE CORES
                # ========================================================
                def estilizar_linhas_e_destacar_pontos(row):
                    cor_fundo = '#4a4a4a' if row.name % 2 == 0 else '#333333'
                    estilos = [f'background-color: {cor_fundo}; color: white; text-align: center !important; font-size: 16px;'] * len(row)
                    try:
                        estilo_maior = f'background-color: {cor_fundo}; color: #00d26a; font-weight: 900; text-align: center !important; font-size: 18px;'
                        estilo_menor = f'background-color: {cor_fundo}; color: #ff4b4b; font-weight: 900; text-align: center !important; font-size: 18px;'
                        estilo_empate = f'background-color: {cor_fundo}; color: #ffd700; font-weight: 900; text-align: center !important; font-size: 18px;'
                        
                        # --- 1. Formatação dos Pontos ---
                        if 'Pts Casa' in row.index and 'Pts Fora' in row.index:
                            idx_casa = list(row.index).index('Pts Casa')
                            idx_fora = list(row.index).index('Pts Fora')
                            pts_casa = int(str(row['Pts Casa'])) if str(row['Pts Casa']).isdigit() else -1
                            pts_fora = int(str(row['Pts Fora'])) if str(row['Pts Fora']).isdigit() else -1
                            if pts_casa >= 0 and pts_fora >= 0: 
                                if pts_casa == pts_fora: estilos[idx_casa], estilos[idx_fora] = estilo_empate, estilo_empate
                                elif pts_casa > pts_fora: estilos[idx_casa], estilos[idx_fora] = estilo_maior, estilo_menor
                                else: estilos[idx_casa], estilos[idx_fora] = estilo_menor, estilo_maior
                                    
                        # --- 2. Formatação do Pseudo-xG ---
                        if 'xG Casa' in row.index:
                            idx_xg_casa = list(row.index).index('xG Casa')
                            if pd.notna(row['xG Casa']) and row['xG Casa'] != "-":
                                try:
                                    xg_casa = float(row['xG Casa'])
                                    if xg_casa >= 1.50: estilos[idx_xg_casa] = estilo_maior
                                    elif xg_casa < 1.30: estilos[idx_xg_casa] = estilo_menor
                                    else: estilos[idx_xg_casa] = estilo_empate
                                except ValueError: pass

                        if 'xG Fora' in row.index:
                            idx_xg_fora = list(row.index).index('xG Fora')
                            if pd.notna(row['xG Fora']) and row['xG Fora'] != "-":
                                try:
                                    xg_fora = float(row['xG Fora'])
                                    if xg_fora <= 1.00: estilos[idx_xg_fora] = estilo_maior
                                    elif xg_fora >= 1.25: estilos[idx_xg_fora] = estilo_menor
                                    else: estilos[idx_xg_fora] = estilo_empate
                                except ValueError: pass

                    except ValueError: pass
                    return estilos

                tabela_estilizada = tabela_web.style.apply(estilizar_linhas_e_destacar_pontos, axis=1) \
                    .format({'Odd Lay': '{:.2f}', 'Vantagem': '{:.1%}', 'xG Casa': '{:.2f}', 'xG Fora': '{:.2f}'}, na_rep="-") \
                    .hide(axis="index") \
                    .set_table_attributes('style="width: 100%; margin: 0 auto; border-collapse: collapse;"') \
                    .set_table_styles([
                        {'selector': 'th', 'props': [
                            ('background-color', '#696969'), ('color', 'black'), 
                            ('text-align', 'center !important'), ('font-weight', 'bold'),
                            ('font-size', '19px'), ('padding', '6px') # Tamanho da fonte levemente reduzido para caber as novas colunas
                        ]},
                        {'selector': 'td', 'props': [('text-align', 'center !important'), ('padding', '10px')]}
                    ])
                    
                # Substituição das Strings Nativas do Pandas pelos Tooltips HTML Dinâmicos
                html_final = tabela_estilizada.to_html()
                tooltips_dicionario = {
                    '>xG Casa</th>': '><span class="tooltip-header" title="A Verdade Atual: O diferencial entre o xG do Mandante e do Visitante dita o favoritismo real de hoje. É o motor do modelo.">xG Casa</span></th>',
                    '>xG Fora</th>': '><span class="tooltip-header" title="A Verdade Atual: O diferencial entre o xG do Mandante e do Visitante dita o favoritismo real de hoje. É o motor do modelo.">xG Fora</span></th>',
                    '>Pts Casa</th>': '><span class="tooltip-header" title="Embalo (Casa): Garante que estamos confiando o nosso dinheiro em um time que está acostumado a vencer no seu estádio.">Pts Casa</span></th>',
                    '>Pts Fora</th>': '><span class="tooltip-header" title="Crise (Fora): Confirma a má fase do visitante, mostrando que ele tem o hábito de tropeçar.">Pts Fora</span></th>',
                    '>FTS Fora</th>': '><span class="tooltip-header" title="Inofensividade: Penaliza fortemente o visitante se ele tem o costume de passar jogos sem marcar nenhum gol.">FTS Fora</span></th>',
                    '>DP GM Fora</th>': '><span class="tooltip-header" title="Filtro Anti-Zebra: Queremos um número baixo. Evita que a gente aposte contra um time que do nada mete 3 gols num jogo só.">DP GM Fora</span></th>',
                    '>DP GS Casa</th>': '><span class="tooltip-header" title="Muralha Estável: Queremos um número baixo. Confirma que a zaga do mandante não é de lua (um dia boa, outro dia péssima).">DP GS Casa</span></th>',
                    '>Vaz Def Fora</th>': '><span class="tooltip-header" title="Caminho Livre: Média de gols sofridos pelo visitante. Se eles sempre tomam gol, a nossa aposta fica muito mais tranquila.">Vaz Def Fora</span></th>',
                    '>CS Casa</th>': '><span class="tooltip-header" title="Seguro 0x0: Bônus para mandantes que saem de campo sem tomar gols, garantindo o nosso empate protetor.">CS Casa</span></th>'
                }

                for string_velha, string_nova in tooltips_dicionario.items():
                    html_final = html_final.replace(string_velha, string_nova)

                st.markdown(html_final, unsafe_allow_html=True)
            else:
                st.info(f"Nenhum jogo atende aos critérios (Mín Odd Lay: {odd_selecionada:.2f} e Edge: {edge_selecionado:.1f}%).")
                with espaco_download: st.empty()
