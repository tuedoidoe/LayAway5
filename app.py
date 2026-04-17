import streamlit as st
import pandas as pd
import numpy as np
import joblib
import warnings
from datetime import datetime
import pytz
import requests
import io
from rapidfuzz import process, fuzz

warnings.filterwarnings("ignore")

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E LOGIN
# ==========================================
st.set_page_config(page_title="Scanner Lay Away", layout="wide", initial_sidebar_state="collapsed")

# CSS PREMIUM (Dark Mode, Título Ouro/Prata e Alinhamentos)
st.markdown("""
    <style>
    /* Fundo escuro moderno */
    .stApp {
        background-color: #0e1117;
        font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Estilização do Título Impactante (Dourado e Prateado) */
    .titulo-premium {
        font-family: 'Arial Black', Impact, sans-serif;
        font-size: 60px !important;
        font-weight: 900;
        letter-spacing: -2px;
        background: linear-gradient(135deg, #d4af37 0%, #fff2cd 25%, #c0c0c0 50%, #e5e4e2 75%, #b5952f 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        padding-bottom: 0px;
        line-height: 1.1;
        text-transform: uppercase;
        display: inline-block;
    }
    
    /* Data da última atualização */
    .data-atualizacao {
        color: #888888;
        font-size: 15px;
        font-weight: 600;
        margin-top: 5px;
        margin-bottom: 20px;
    }

    /* Ajustes dos controles (Horizontalidade) */
    div[data-testid="stRadio"] { display: flex !important; justify-content: flex-start !important; align-items: center !important; height: 100%;}
    div[data-testid="stRadio"] > div[role="radiogroup"] { display: flex !important; flex-direction: row !important; gap: 20px; }
    
    /* Estilo dos Títulos (Labels) dos Filtros e Selects */
    div[data-testid="stNumberInput"] label p, div[data-testid="stSelectbox"] label p {
        font-size: 15px !important; 
        font-weight: bold !important;
        color: #e0e0e0 !important;
    }

    /* Estilo dos Inputs Numéricos (Filtros) */
    div[data-testid="stNumberInputContainer"] {
        background-color: #1e1e1e !important;
        border: 1px solid #333 !important;
        border-radius: 6px !important;
    }
    div[data-testid="stNumberInputContainer"] input {
        color: #00d26a !important;
        font-weight: bold !important;
    }
    
    /* Ajuste da altura e alinhamento do botão principal */
    div[data-testid="stButton"] > button { 
        background-color: #00d26a !important; 
        color: #121212 !important; 
        font-weight: 900 !important; 
        border-radius: 6px !important; 
        border: none !important;
        font-size: 16px !important;
        height: 40px !important;
        margin-top: 24px !important; 
        transition: all 0.3s ease;
    }
    div[data-testid="stButton"] > button:hover { 
        background-color: #00b55b !important; 
        transform: translateY(-2px);
    }

    /* Botão de Download EXATAMENTE alinhado à direita */
    div[data-testid="stDownloadButton"] {
        display: flex;
        justify-content: flex-end !important;
        width: 100% !important;
        margin-bottom: 5px;
        padding-right: 0px !important; 
    }
    div[data-testid="stDownloadButton"] > button { 
        background-color: #262730 !important; 
        color: white !important; 
        border-radius: 6px !important; 
        border: 1px solid #444 !important;
        width: max-content !important; 
        padding: 6px 20px !important;
    }
    div[data-testid="stDownloadButton"] > button:hover { background-color: #333 !important; border-color: #666 !important; }

    /* CSS para o Tooltip Customizado */
    .tooltip-header { 
        position: relative; 
        cursor: help; 
        border-bottom: 1px dotted #888; 
    }
    .tooltip-header:hover::after {
        content: attr(data-title);
        position: absolute;
        bottom: 140%; 
        left: 50%; 
        transform: translateX(-50%);
        background-color: #1a1a1a; 
        color: #00d26a; 
        padding: 10px 14px; 
        border-radius: 8px; 
        font-size: 13px; 
        font-weight: normal;
        white-space: normal; 
        width: max-content; 
        max-width: 250px; 
        z-index: 999; 
        border: 1px solid #333; 
        text-align: left;
        line-height: 1.4;
        box-shadow: 0px 8px 16px rgba(0,0,0,0.7);
    }
    .tooltip-header:hover::before {
        content: ""; 
        position: absolute; 
        bottom: 100%; 
        left: 50%; 
        transform: translateX(-50%);
        border-width: 6px; 
        border-style: solid; 
        border-color: #1a1a1a transparent transparent transparent;
    }
    </style>
""", unsafe_allow_html=True)

def check_password():
    if st.session_state.get("password_correct", False): return True
    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.image("logo.png", use_container_width=True)
        
        def password_entered():
            if st.session_state["password"] == st.secrets["senha_secreta"]:
                st.session_state["password_correct"] = True
                del st.session_state["password"]
            else: st.session_state["password_correct"] = False

        if "password_correct" not in st.session_state:
            st.text_input("🔑 Senha:", type="password", on_change=password_entered, key="password")
            return False
        elif not st.session_state["password_correct"]:
            st.text_input("🔑 Senha:", type="password", on_change=password_entered, key="password")
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
# CÓDIGO DO SCANNER (CABEÇALHO)
# ==========================================
if check_password():
    
    col_esquerda, col_direita = st.columns([1.3, 1])
    
    with col_esquerda:
        st.markdown("<p class='titulo-premium'>SCANNER LAY AWAY</p>", unsafe_allow_html=True)
        # Horário de Brasília Fixo
        fuso_br = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(fuso_br).strftime("%d/%m/%Y às %H:%M:%S")
        st.markdown(f"<p class='data-atualizacao'>Última atualização: {agora}</p>", unsafe_allow_html=True)

    with col_direita:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        hoje = datetime.now(fuso_br).date()
        
        c1, c2, c3 = st.columns([1.2, 1, 1])
        with c1:
            st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
            tipo_filtro = st.radio("Período", ["Data Única", "Intervalo"], horizontal=True, label_visibility="collapsed")
        with c2:
            st.markdown("<div style='font-size: 14px; font-weight: bold; margin-bottom: 2px;'>Data da Pesquisa</div>", unsafe_allow_html=True)
            if tipo_filtro == "Data Única":
                data_selecionada = st.date_input("Data", value=hoje, format="DD/MM/YYYY", label_visibility="collapsed")
            else:
                data_selecionada = st.date_input("Data", value=(hoje, hoje), format="DD/MM/YYYY", label_visibility="collapsed")
        with c3:
            btn_procurar = st.button("🚀 Iniciar Varredura", use_container_width=True)
        
    st.markdown("<hr style='margin-top: 0px; margin-bottom: 25px; border: 1px solid #333;'>", unsafe_allow_html=True)

    if btn_procurar:
        st.session_state['mostrar_tabela'] = False 
        
        with st.spinner('Analisando o mercado global...'):
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
                    
                    df_completo['Goals_H_FT'] = pd.to_numeric(df_completo['Goals_H_FT'], errors='coerce')
                    df_completo['Goals_A_FT'] = pd.to_numeric(df_completo['Goals_A_FT'], errors='coerce')

                    df_completo['Pts_H'] = np.where(df_completo['Goals_H_FT'] > df_completo['Goals_A_FT'], 3, np.where(df_completo['Goals_H_FT'] == df_completo['Goals_A_FT'], 1, 0))
                    df_completo['Pts_A'] = np.where(df_completo['Goals_A_FT'] > df_completo['Goals_H_FT'], 3, np.where(df_completo['Goals_A_FT'] == df_completo['Goals_H_FT'], 1, 0))
                    
                    soma_pts_casa = df_completo.groupby('Home')['Pts_H'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
                    soma_pts_fora = df_completo.groupby('Away')['Pts_A'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
                    qtd_jogos_casa = df_completo.groupby('Home')['Pts_H'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).count())
                    qtd_jogos_fora = df_completo.groupby('Away')['Pts_A'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).count())
                    
                    df_completo['Is_CS_Casa'] = (df_completo['Goals_A_FT'] == 0).astype(int)
                    df_completo['Is_FTS_Fora'] = (df_completo['Goals_A_FT'] == 0).astype(int)
                    
                    soma_cs_casa = df_completo.groupby('Home')['Is_CS_Casa'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
                    soma_fts_fora = df_completo.groupby('Away')['Is_FTS_Fora'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
                    
                    dp_gs_casa = df_completo.groupby('Home')['Goals_A_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=2).std())
                    dp_gm_fora = df_completo.groupby('Away')['Goals_A_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=2).std())
                    vaz_def_fora = df_completo.groupby('Away')['Goals_H_FT'].transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())

                    prob_h = safe_prob(df_completo['Odd_H_Back'])
                    prob_a = safe_prob(df_completo['Odd_A_Back'])
                    prob_o25 = safe_prob(df_completo['Odd_Over25_FT_Back'])
                    
                    prob_d = np.clip(1.0 - prob_h - prob_a, 0.1, 1.0)
                    exp_tg = np.where(prob_o25 > 0, 1.25 + (prob_o25 * 2.5), 2.5) 
                    soma_probs = prob_h + prob_a + prob_d
                    
                    df_completo['XG_Casa'] = np.where(prob_h > 0, (exp_tg * (prob_h + 0.5 * prob_d) / soma_probs), np.nan)
                    df_completo['XG_Fora'] = np.where(prob_a > 0, (exp_tg * (prob_a + 0.5 * prob_d) / soma_probs), np.nan)

                    xg_total = df_completo['XG_Casa'] + df_completo['XG_Fora']
                    score_xg = np.where(xg_total > 0, (df_completo['XG_Casa'] / xg_total) * 30.0, 15.0)

                    score_pts_casa = (soma_pts_casa.fillna(0) / 15.0) * 10.0
                    score_pts_fora = ((15.0 - soma_pts_fora.fillna(0)) / 15.0) * 10.0

                    score_fts = soma_fts_fora.fillna(0) * 15.0
                    score_cs = soma_cs_casa.fillna(0) * 5.0

                    score_dp_gm = (np.maximum(0, 2.0 - dp_gm_fora.fillna(1.0)) / 2.0) * 10.0
                    score_dp_gs = (np.maximum(0, 2.0 - dp_gs_casa.fillna(1.0)) / 2.0) * 10.0

                    score_vaz = (np.minimum(3.0, vaz_def_fora.fillna(0)) / 3.0) * 10.0

                    df_completo['Score'] = score_xg + score_pts_casa + score_pts_fora + score_fts + score_cs + score_dp_gm + score_dp_gs + score_vaz
                    df_completo['Score'] = df_completo['Score'].fillna(0).round(0).astype(int)

                    def definir_alerta(score):
                        if score >= 55: return '🟢'
                        elif score >= 48: return '🟡'
                        else: return '🔴'
                    df_completo['Alerta'] = df_completo['Score'].apply(definir_alerta)

                    df_completo['Pontos Casa'] = np.where(qtd_jogos_casa > 0, soma_pts_casa.fillna(0).astype(int).astype(str), "-")
                    df_completo['Pontos Fora'] = np.where(qtd_jogos_fora > 0, soma_pts_fora.fillna(0).astype(int).astype(str), "-")
                    df_completo['CS Casa'] = np.where(qtd_jogos_casa > 0, soma_cs_casa.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['FTS Fora'] = np.where(qtd_jogos_fora > 0, soma_fts_fora.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['DP GS Casa'] = np.where(qtd_jogos_casa > 1, dp_gs_casa.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['DP GM Fora'] = np.where(qtd_jogos_fora > 1, dp_gm_fora.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['Vaz Def Fora'] = np.where(qtd_jogos_fora > 0, vaz_def_fora.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    
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
                            st.warning(f"Foram encontrados jogos para {texto_data}, mas eles foram descartados pois não possuem histórico estatístico suficiente.")
                        else:
                            df_hoje["Previsao"] = model.predict_proba(df_hoje[X_cols_treino])[:, 1]
                            df_hoje["Edge"] = df_hoje["Previsao"] - (1 - (1 / df_hoje["Odd_A_Lay"]))
                            
                            df_bruto = df_hoje[df_hoje["Edge"] >= 0.0].copy()
                            
                            if len(df_bruto) == 0:
                                st.warning(f"O modelo não encontrou Edge suficiente (>0.0%) em {texto_data}.")
                            else:
                                st.session_state['mostrar_tabela'] = True
                                st.session_state['df_bruto'] = df_bruto

            except Exception as e:
                st.error(f"Erro inesperado durante o processamento: {e}")

    # ==========================================
    # EXIBIÇÃO VISUAL E TABELA PREMIUM
    # ==========================================
    if st.session_state.get('mostrar_tabela', False):
        df_bruto = st.session_state['df_bruto']
        
        # Grid para alinhar Resultados, Filtros, Ordenação e Botão de Exportar
        col_res1, col_sort, col_ordem, col_odd, col_edge, col_btn = st.columns([3.2, 0.7, 0.6, 0.5, 0.5, 0.8])
        
        with col_sort:
            coluna_ordem = st.selectbox("Ordenar por", ["Horário", "EV+", "Score"])
            
        with col_ordem:
            direcao_ordem = st.selectbox("Ordem", ["Crescente", "Decrescente"])

        with col_odd:
            odd_selecionada = st.number_input("Odd Lay", min_value=2.50, max_value=5.0, value=2.50, step=0.10, format="%.2f")
            
        with col_edge:
            edge_selecionado = st.number_input("EV+ (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, format="%.1f")
        
        # Aplicação dos Filtros Ativos
        df_filtrado_odd = df_bruto[df_bruto["Odd_A_Lay"] >= odd_selecionada].copy()
        edge_decimal = edge_selecionado / 100.0
        df_final_filtrado = df_filtrado_odd[df_filtrado_odd["Edge"] >= edge_decimal].copy()
        
        with col_res1:
            texto_resultado = f"""
            <div style='text-align: left; font-size: 18px; margin-top: 34px; margin-bottom: 20px;'>
                <span style='color: #888;'>Oportunidades Encontradas:</span> <span style='color: #00d26a; font-weight: 900;'>{len(df_final_filtrado)} jogo(s)</span>
            </div>
            """
            st.markdown(texto_resultado, unsafe_allow_html=True)

        tabela = df_final_filtrado[['Date', 'Time', 'League', 'Home', 'Away', 'Odd_A_Lay', 'Pontos Casa', 'Pontos Fora', 'FTS Fora', 'DP GM Fora', 'DP GS Casa', 'Vaz Def Fora', 'CS Casa', 'XG_Casa', 'XG_Fora', 'Edge', 'Score', 'Alerta']].copy()
        
        if not tabela.empty:
            tabela['Date'] = pd.to_datetime(tabela['Date'])
            
            # --- LÓGICA DE ORDENAÇÃO APLICADA AQUI ---
            is_ascending = (direcao_ordem == "Crescente")
            
            if coluna_ordem == "Horário":
                tabela = tabela.sort_values(by=['Date', 'Time'], ascending=[is_ascending, is_ascending]).reset_index(drop=True)
            elif coluna_ordem == "EV+":
                tabela = tabela.sort_values(by=['Edge'], ascending=is_ascending).reset_index(drop=True)
            elif coluna_ordem == "Score":
                tabela = tabela.sort_values(by=['Score'], ascending=is_ascending).reset_index(drop=True)

            tabela['Date'] = tabela['Date'].dt.strftime('%d/%m/%Y')

            tabela_excel = tabela.rename(columns={
                'Date': 'Data', 'Time': 'Horário', 'League': 'Liga', 'Home': 'Time Casa', 'Away': 'Time Fora',
                'Odd_A_Lay': 'Odd Lay', 'Pontos Casa': 'Pts Casa', 'Pontos Fora': 'Pts Fora',
                'XG_Casa': 'xG Casa', 'XG_Fora': 'xG Fora', 'Edge': 'EV+'
            })

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                tabela_excel.to_excel(writer, index=False, sheet_name='Lay_Away')
            
            with col_btn:
                # O margin-top de 28px compensa o espaço do título das caixas para que o botão fique perfeitamente alinhado com o input
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                st.download_button("📥 Exportar Excel", data=buffer.getvalue(), file_name="Jogos_LayAway.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=False)
            
            tabela_web = tabela_excel.copy() 

            def estilizar_linhas_premium(row):
                cor_fundo = '#1e1e1e' if row.name % 2 == 0 else '#121212'
                return [f'background-color: {cor_fundo}; color: #e0e0e0; text-align: center !important; font-size: 15px; border-bottom: 1px solid #333;'] * len(row)

            tabela_estilizada = tabela_web.style.apply(estilizar_linhas_premium, axis=1) \
                .format({'Odd Lay': '{:.2f}', 'xG Casa': '{:.2f}', 'xG Fora': '{:.2f}', 'EV+': '{:.1%}'}, na_rep="-") \
                .hide(axis="index") \
                .set_table_attributes('style="width: 100%; border-collapse: collapse; margin-top: 5px; border: 1px solid #333;"') \
                .set_table_styles([
                    {'selector': 'th', 'props': [
                        ('background-color', '#262730'), ('color', '#ffffff'), 
                        ('text-align', 'center !important'), ('font-weight', 'bold'),
                        ('font-size', '16px'), ('padding', '12px 8px'), ('border-bottom', '2px solid #00d26a')
                    ]},
                    {'selector': 'td', 'props': [('text-align', 'center !important'), ('padding', '12px 8px')]}
                ])
                
            html_final = tabela_estilizada.to_html()
            
            tooltips_dicionario = {
                '>xG Casa</th>': '><span class="tooltip-header" data-title="A Verdade Atual: O diferencial entre o xG do Mandante e do Visitante dita o favoritismo real de hoje. É o motor do modelo. | Quanto MAIOR, melhor. (Ideal: > 1.50)">xG Casa</span></th>',
                '>xG Fora</th>': '><span class="tooltip-header" data-title="A Verdade Atual: O diferencial entre o xG do Mandante e do Visitante dita o favoritismo real de hoje. É o motor do modelo. | Quanto MENOR, melhor. (Ideal: < 1.00)">xG Fora</span></th>',
                '>Pts Casa</th>': '><span class="tooltip-header" data-title="Embalo (Casa): Garante que estamos confiando o nosso dinheiro em um time que está acostumado a vencer no seu estádio. | Quanto MAIOR, melhor. (Ideal: >= 10 pts)">Pts Casa</span></th>',
                '>Pts Fora</th>': '><span class="tooltip-header" data-title="Crise (Fora): Confirma a má fase do visitante, mostrando que ele tem o hábito de tropeçar. | Quanto MENOR, melhor. (Ideal: <= 5 pts)">Pts Fora</span></th>',
                '>FTS Fora</th>': '><span class="tooltip-header" data-title="Inofensividade: Penaliza fortemente o visitante se ele tem o costume de passar jogos sem marcar nenhum gol. | Quanto MAIOR, melhor. (Ideal: >= 0.60)">FTS Fora</span></th>',
                '>DP GM Fora</th>': '><span class="tooltip-header" data-title="Filtro Anti-Zebra: Evita que a gente aposte contra um time que do nada mete 3 gols num jogo só. | Quanto MENOR, melhor. (Ideal: < 1.00)">DP GM Fora</span></th>',
                '>DP GS Casa</th>': '><span class="tooltip-header" data-title="Muralha Estável: Confirma que a zaga do mandante não é de lua (um dia boa, outro dia péssima). | Quanto MENOR, melhor. (Ideal: < 1.00)">DP GS Casa</span></th>',
                '>Vaz Def Fora</th>': '><span class="tooltip-header" data-title="Caminho Livre: Média de gols sofridos pelo visitante. Se eles sempre tomam gol, a nossa aposta fica muito mais tranquila. | Quanto MAIOR, melhor. (Ideal: >= 1.50)">Vaz Def Fora</span></th>',
                '>CS Casa</th>': '><span class="tooltip-header" data-title="Seguro 0x0: Bônus para mandantes que saem de campo sem tomar gols, garantindo o nosso empate protetor. | Quanto MAIOR, melhor. (Ideal: >= 0.40)">CS Casa</span></th>',
                '>EV+</th>': '><span class="tooltip-header" data-title="Vantagem (Edge): Margem de valor real encontrada pelo modelo em relação à cotação da casa de apostas. | Quanto MAIOR, melhor.">EV+</span></th>',
                '>Score</th>': '><span class="tooltip-header" data-title="Nota de 0 a 100 gerada pela normalização de todos os pesos. Serve como um guia de risco consolidado. | Quanto MAIOR, melhor. (Ideal: >= 55)">Score</span></th>',
                '>Alerta</th>': '><span class="tooltip-header" data-title="Visualização Rápida de Risco. Verde >= 55. Amarelo 48 a 54. Vermelho < 48. | O ideal é focar nos Verdes e Amarelos.">Alerta</span></th>'
            }

            for string_velha, string_nova in tooltips_dicionario.items():
                html_final = html_final.replace(string_velha, string_nova)

            st.markdown(html_final, unsafe_allow_html=True)
            st.markdown("<br><br>", unsafe_allow_html=True)
        else:
            st.info("Nenhum jogo atende aos critérios do modelo para a data selecionada.")
