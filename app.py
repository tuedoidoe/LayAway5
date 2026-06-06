import streamlit as st
import pandas as pd
import numpy as np
import joblib
import warnings
import json
from datetime import datetime, timedelta
import pytz
import requests
import io
from rapidfuzz import process, fuzz
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

def drop_reset_index(df):
    return df.reset_index(drop=True)

# ==========================================
# CARREGAMENTO DOS DICIONÁRIOS JSON
# ==========================================
@st.cache_data # Desativar, fazer as modificações no arquivo mapeamentos.json, rodar, ativar novamente e depois ativar.
def carregar_mapeamentos():
    try:
        with open("mapeamentos.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo mapeamentos.json: {e}")
        return {"mapeamento_torneios": {}, "tradutor_times": {}}

dicionarios_globais = carregar_mapeamentos()
mapeamento_torneios = dicionarios_globais.get("mapeamento_torneios", {})
tradutor_times = dicionarios_globais.get("tradutor_times", {})

def identificar_torneio(nome_sujo):
    for raiz, codigo in mapeamento_torneios.items():
        if str(nome_sujo).startswith(raiz):
            return codigo
    return nome_sujo

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E LOGIN
# ==========================================
st.set_page_config(page_title="Scanner Lay Away", layout="wide", initial_sidebar_state="collapsed")

if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = 'scanner'

def mudar_pagina(nome_pagina):
    st.session_state['pagina_atual'] = nome_pagina

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
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
    .data-atualizacao {
        color: #888888;
        font-size: 15px;
        font-weight: 600;
        margin-top: 5px;
        margin-bottom: 20px;
    }
    div[data-testid="stRadio"] { display: flex !important; justify-content: flex-start !important; align-items: center !important; height: 100%;}
    div[data-testid="stRadio"] > div[role="radiogroup"] { 
        display: flex !important; 
        flex-direction: row !important; 
        gap: 20px; 
        flex-wrap: nowrap !important;
        white-space: nowrap !important;
    }
    div[data-testid="stNumberInput"] label p, div[data-testid="stSelectbox"] label p {
        font-size: 15px !important; 
        font-weight: bold !important;
        color: #e0e0e0 !important;
    }
    div[data-testid="stNumberInputContainer"] {
        background-color: #1e1e1e !important;
        border: 1px solid #333 !important;
        border-radius: 6px !important;
    }
    div[data-testid="stNumberInputContainer"] input {
        color: #00d26a !important;
        font-weight: bold !important;
    }
    
    /* Configuração Geral de Botões (Primário Verde, Secundário Cinza) */
    div[data-testid="stButton"] > button {
        font-weight: 900 !important; 
        border-radius: 6px !important; 
        font-size: 16px !important;
        height: 40px !important;
        transition: all 0.3s ease;
        white-space: nowrap !important;
    }
    div[data-testid="stButton"] > button[kind="primary"] { 
        background-color: #00d26a !important; 
        color: #121212 !important; 
        border: none !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover { 
        background-color: #00b55b !important; 
        transform: translateY(-2px);
    }
    div[data-testid="stButton"] > button[kind="secondary"] { 
        background-color: #333333 !important; 
        color: #ffffff !important; 
        border: 1px solid #555555 !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover { 
        background-color: #444444 !important; 
        border-color: #777777 !important;
        transform: translateY(-2px);
    }

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
            senha_digitada = st.session_state.get("password", "")
            if senha_digitada == st.secrets["senha_secreta"]:
                st.session_state["password_correct"] = True
                if "password" in st.session_state:
                    del st.session_state["password"]
            else: 
                st.session_state["password_correct"] = False

        st.text_input("🔑 Senha:", type="password", on_change=password_entered, key="password")

        if st.button("Acessar", use_container_width=True, type="primary"):
            password_entered()
            st.rerun()

        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("❌ Senha incorreta.")
            
    return False

# ==========================================
# FUNÇÕES DE CARREGAMENTO (COM CACHE) E GRÁFICO
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

@st.cache_data(ttl=1800)
def carregar_base_livescore():
    try:
        df = pd.read_json("base_livescore_api.json")
        if not df.empty and 'Data' in df.columns:
            df['Date'] = pd.to_datetime(df['Data'], errors='coerce')
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300) 
def baixar_jogos_do_dia(data):
    try:
        url = f"https://api.futpythontrader.com/api/dados/jogos-do-dia/betfair/{data}/download/"
        # url = f"https://api.futpythontrader.com/api/dados/jogos-do-dia/betfair/{data}/"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            df_api = pd.read_csv(io.BytesIO(response.content))
            if not df_api.empty and 'Date' in df_api.columns: df_api['Date'] = pd.to_datetime(df_api['Date'])
            return df_api
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.dialog("📊 Raio-X do Confronto: Boca de Jacaré", width="large")
def abrir_popup_grafico(t_casa, t_fora, df_completo):
    df_historico = df_completo.dropna(subset=['Goals_H_FT', 'Goals_A_FT']).copy()
    
    hist_casa = df_historico[(df_historico['Home'] == t_casa)].tail(10).copy()
    hist_fora = df_historico[(df_historico['Away'] == t_fora)].tail(10).copy()
    
    if not hist_casa.empty:
        hist_casa['MM_Gols_Feitos'] = hist_casa['Goals_H_FT'].rolling(window=3, min_periods=1).mean()
    if not hist_fora.empty:
        hist_fora['MM_Gols_Sofridos'] = hist_fora['Goals_H_FT'].rolling(window=3, min_periods=1).mean()
    
    hist_casa = hist_casa.tail(6)
    hist_fora = hist_fora.tail(6)
    
    eixo_x = [f"Jogo {i+1}" for i in range(6)]
    fig = go.Figure()

    if not hist_casa.empty:
        fig.add_trace(go.Scatter(
            x=eixo_x[:len(hist_casa)], y=hist_casa['MM_Gols_Feitos'].values,
            mode='lines+markers', name=f"📈 Poder de Fogo ({t_casa})",
            line=dict(color='#00d26a', width=4, shape='spline'),
            marker=dict(size=10, color='#00d26a', symbol='circle'),
            fill='tozeroy', fillcolor='rgba(0, 210, 106, 0.05)'
        ))

    if not hist_fora.empty:
        fig.add_trace(go.Scatter(
            x=eixo_x[:len(hist_fora)], y=hist_fora['MM_Gols_Sofridos'].values, 
            mode='lines+markers', name=f"📉 Crise Defensiva ({t_fora})",
            line=dict(color='#ff4b4b', width=4, shape='spline', dash='dot'),
            marker=dict(size=10, color='#ff4b4b', symbol='diamond')
        ))

    max_casa = hist_casa['MM_Gols_Feitos'].max() if not hist_casa.empty else 0
    max_fora = hist_fora['MM_Gols_Sofridos'].max() if not hist_fora.empty else 0
    teto_grafico = max(max_casa, max_fora) + 0.5 if max(max_casa, max_fora) > 0 else 3.0

    fig.update_layout(
        plot_bgcolor='#121212', paper_bgcolor='#121212',
        font=dict(color='#888'),
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#333'),
        yaxis=dict(title='Média Móvel de Gols', showgrid=True, gridwidth=1, gridcolor='#333', range=[-0.5, teto_grafico]),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

    val_ataque = hist_casa['MM_Gols_Feitos'].iloc[-1] if not hist_casa.empty and 'MM_Gols_Feitos' in hist_casa.columns else 0.0
    momento_ataque_casa = float(val_ataque) if pd.notna(val_ataque) else 0.0
    
    val_defesa = hist_fora['MM_Gols_Sofridos'].iloc[-1] if not hist_fora.empty and 'MM_Gols_Sofridos' in hist_fora.columns else 0.0
    momento_defesa_fora = float(val_defesa) if pd.notna(val_defesa) else 0.0

    st.markdown("<hr style='margin-top: 10px; border: 1px solid #333;'>", unsafe_allow_html=True)
    col_msg1, col_msg2 = st.columns(2)
    
    with col_msg1:
        if momento_ataque_casa >= 1.5:
            st.success(f"🔥 **Ataque Feroz:** A tendência atual do {t_casa} é marcar {momento_ataque_casa:.1f} gols/jogo.")
        elif momento_ataque_casa >= 1.0:
            st.info(f"⚖️ **Ataque Regular:** A tendência atual do {t_casa} é marcar {momento_ataque_casa:.1f} gols/jogo.")
        else:
            st.error(f"⚠️ **Ataque Inofensivo:** O {t_casa} vem sofrendo para marcar (tendência de {momento_ataque_casa:.1f} gols/jogo).")
            
    with col_msg2:
        if momento_defesa_fora >= 1.5:
            st.success(f"🚨 **Defesa em Crise:** A zaga do {t_fora} está vazando! Sofrendo {momento_defesa_fora:.1f} gols/jogo.")
        elif momento_defesa_fora >= 1.0:
            st.info(f"⚖️ **Defesa Regular:** A tendência atual do {t_fora} é sofrer {momento_defesa_fora:.1f} gols/jogo.")
        else:
            st.error(f"🛡️ **Defesa Intransponível:** O {t_fora} ajustou a zaga e vem sofrendo apenas {momento_defesa_fora:.1f} gols/jogo.")

    if momento_ataque_casa >= 1.5 and momento_defesa_fora >= 1.5:
        veredito = "🐊 <b>BOCA DE JACARÉ DETECTADA:</b> Cenário PERFEITO para Lay Away! O ataque do mandante está crescendo na mesma proporção em que a defesa do visitante está afundando."
        cor_borda = "#00d26a"
    elif momento_ataque_casa < 1.0 and momento_defesa_fora < 1.0:
        veredito = "🧱 <b>CENÁRIO PERIGOSO:</b> Mandante com ataque inoperante contra uma defesa visitante ajustada. Risco alto de jogo truncado ou 0x0. Evite o Lay Away."
        cor_borda = "#ff4b4b"
    elif momento_ataque_casa >= 1.5 and momento_defesa_fora < 1.0:
        veredito = "⚔️ <b>JOGO DE PACIÊNCIA:</b> O mandante tem muito volume, mas o visitante sabe se defender. A linha de gols dependerá da quebra dessa retranca."
        cor_borda = "#fada5e"
    elif momento_ataque_casa < 1.0 and momento_defesa_fora >= 1.5:
        veredito = "🎲 <b>CENÁRIO IMPREVISÍVEL:</b> A defesa visitante é terrível, mas o ataque mandante não aproveita. Jogo com alta chance de zebras."
        cor_borda = "#fada5e"
    else:
        veredito = "⚖️ <b>CENÁRIO NEUTRO:</b> As médias móveis estão estáveis. Não há padrão claro de Boca de Jacaré neste momento."
        cor_borda = "#3b82f6"

    st.markdown(f"""
    <div style='border-left: 5px solid {cor_borda}; background-color: #1e1e1e; padding: 15px; border-radius: 5px; margin-top: 15px; color: #e0e0e0; font-size: 15px;'>
        {veredito}
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# ENGINE CENTRAL DE PROCESSAMENTO
# ==========================================
def rodar_engine_pesquisa(data_selecionada, tipo_filtro, st_context_msg="Analisando..."):
    with st.spinner(st_context_msg):
        try:
            dados_modelo = joblib.load('Modelo_LayAway_6.pkl')
            model = dados_modelo['modelo']
            taxas_ligas = dados_modelo['liga_rates']
            media_global_treino = dados_modelo['media_global']
            X_cols_treino = dados_modelo['features']
            
            df_hist = baixar_base_dados()
            df_alvo_lista = []
            
            if tipo_filtro == "Data Única":
                df_dia = baixar_jogos_do_dia(data_selecionada.strftime('%Y-%m-%d'))
                if not df_dia.empty: df_alvo_lista.append(df_dia)
                d_inicio = d_fim = data_selecionada
            else:
                d_inicio, d_fim = data_selecionada if isinstance(data_selecionada, tuple) and len(data_selecionada) == 2 else (data_selecionada[0], data_selecionada[0])
                for data_atual in pd.date_range(start=d_inicio, end=d_fim):
                    df_dia = baixar_jogos_do_dia(data_atual.strftime('%Y-%m-%d'))
                    if not df_dia.empty: df_alvo_lista.append(df_dia)
            
            df_alvo = pd.concat(df_alvo_lista, ignore_index=True) if df_alvo_lista else pd.DataFrame()
            
            if not df_alvo.empty:
                df_alvo['id_jogo'] = range(1, len(df_alvo) + 1)
                if 'League' in df_alvo.columns:
                    df_alvo['League'] = df_alvo['League'].replace(mapeamento_torneios)
                    df_alvo['Home'] = df_alvo['Home'].replace(tradutor_times)
                    df_alvo['Away'] = df_alvo['Away'].replace(tradutor_times)
            else:
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

            def safe_prob(column): return (1 / pd.to_numeric(column, errors='coerce').replace(0, np.nan)).fillna(0)
            data_limite = df_alvo['Date'].min()

            # --- CAMADA ODD ---
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

            # --- CAMADA ESTATÍSTICAS ---
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
                
                df_ls_names = df_alvo_ls[['id_jogo', 'Home', 'Away']].rename(columns={'Home': 'Home_LS', 'Away': 'Away_LS'})
            else:
                df_stats = df_completo.copy()
                df_ls_names = pd.DataFrame(columns=['id_jogo', 'Home_LS', 'Away_LS'])
                
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

            # --- MERGE ---
            df_hoje = df_completo[df_completo['id_jogo'].notnull()].copy()
            if tipo_filtro == "Data Única":
                df_hoje = df_hoje[df_hoje['Date'].dt.date == data_selecionada].copy()
            else:
                df_hoje = df_hoje[(df_hoje['Date'].dt.date >= d_inicio) & (df_hoje['Date'].dt.date <= d_fim)].copy()
                
            df_hoje_stats = df_stats.dropna(subset=['id_jogo'])
            df_hoje = df_hoje.merge(
                df_hoje_stats[['id_jogo', 'soma_pts_casa', 'soma_pts_fora', 'qtd_jogos_casa', 'qtd_jogos_fora', 
                               'soma_cs_casa', 'soma_fts_fora', 'dp_gs_casa', 'dp_gm_fora', 'vaz_def_fora']],
                on='id_jogo', how='left'
            )
            
            df_hoje = df_hoje.merge(df_ls_names, on='id_jogo', how='left')

            df_hoje = df_hoje[(df_hoje['Odd_A_Lay'] <= 3.50) & (df_hoje['Odd_H_Back'] < df_hoje['Odd_A_Back']) & (abs(df_hoje['Odd_A_Back'] - df_hoje['Odd_A_Lay']) <= 0.50) & (abs(df_hoje['Odd_H_Back'] - df_hoje['Odd_H_Lay']) <= 0.50)].copy()
            
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

                def definir_alerta(score):
                    if score >= 55: return '🟢'
                    elif score >= 48: return '🟡'
                    else: return '🔴'
                df_hoje['Alerta'] = df_hoje['Score'].apply(definir_alerta)

                df_hoje['Pontos Casa'] = np.where(df_hoje['qtd_jogos_casa'] > 0, df_hoje['soma_pts_casa'].fillna(0).astype(int).astype(str), "-")
                df_hoje['Pontos Fora'] = np.where(df_hoje['qtd_jogos_fora'] > 0, df_hoje['soma_pts_fora'].fillna(0).astype(int).astype(str), "-")
                df_hoje['CS Casa'] = np.where(df_hoje['qtd_jogos_casa'] > 0, df_hoje['soma_cs_casa'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                df_hoje['FTS Fora'] = np.where(df_hoje['qtd_jogos_fora'] > 0, df_hoje['soma_fts_fora'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                df_hoje['DP GS Casa'] = np.where(df_hoje['qtd_jogos_casa'] > 1, df_hoje['dp_gs_casa'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                df_hoje['DP GM Fora'] = np.where(df_hoje['qtd_jogos_fora'] > 1, df_hoje['dp_gm_fora'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                df_hoje['Vaz Def Fora'] = np.where(df_hoje['qtd_jogos_fora'] > 0, df_hoje['vaz_def_fora'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")

                colunas_vitais = list(X_cols_treino) + ['Odd_A_Lay', 'Home', 'Away', 'League', 'Date', 'Home_LS', 'Away_LS']
                colunas_vitais = [col for col in colunas_vitais if col in df_hoje.columns]
                df_hoje = drop_reset_index(df_hoje.dropna(subset=colunas_vitais))
                
                if len(df_hoje) > 0:
                    df_hoje["Previsao"] = model.predict_proba(df_hoje[X_cols_treino])[:, 1]
                    df_hoje["Edge"] = df_hoje["Previsao"] - (1 - (1 / df_hoje["Odd_A_Lay"]))
                    df_bruto = df_hoje[df_hoje["Edge"] > 0.0].copy()
                    return df_bruto, df_completo, df_livescore 
            
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        except Exception as e:
            st.error(f"Erro inesperado durante o processamento: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# ==========================================
# PÁGINA 1: SCANNER
# ==========================================
def pagina_scanner():
    st.markdown("<p class='titulo-premium'>SCANNER LAY AWAY</p>", unsafe_allow_html=True)
    fuso_br = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_br).strftime("%d/%m/%Y às %H:%M:%S")
    st.markdown(f"<p class='data-atualizacao'>Última atualização: {agora}</p>", unsafe_allow_html=True)
    
    col_nav, espaco, col_rad, col_dat, col_btn_pesq = st.columns([1.2, 1.5, 1.4, 1.2, 1.2])

    with col_nav:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("📊 Ver Resultados Passados", key="btn_nav_res", use_container_width=True, type="secondary"):
            mudar_pagina('resultados')
            st.rerun()

    with col_rad:
        st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
        tipo_filtro = st.radio("Período", ["Data Única", "Intervalo"], horizontal=True, label_visibility="collapsed", key="scan_rad")

    with col_dat:
        st.markdown("<div style='font-size: 14px; font-weight: bold; margin-bottom: 2px;'>Data da Pesquisa</div>", unsafe_allow_html=True)
        hoje = datetime.now(fuso_br).date()
        if tipo_filtro == "Data Única":
            data_selecionada = st.date_input("Data", value=hoje, format="DD/MM/YYYY", label_visibility="collapsed", key="scan_dt1")
        else:
            data_selecionada = st.date_input("Data", value=(hoje, hoje), format="DD/MM/YYYY", label_visibility="collapsed", key="scan_dt2")

    with col_btn_pesq:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        btn_procurar = st.button("🚀 Iniciar Varredura", use_container_width=True, key="scan_btn", type="primary")
        
    st.markdown("<hr style='margin-top: 0px; margin-bottom: 25px; border: 1px solid #333;'>", unsafe_allow_html=True)

    if btn_procurar:
        st.session_state['mostrar_tabela_scanner'] = False 
        df_bruto, df_completo, _ = rodar_engine_pesquisa(data_selecionada, tipo_filtro, "Analisando o mercado global...")
        
        if df_bruto.empty:
            texto_data = data_selecionada.strftime('%d/%m/%Y') if tipo_filtro == "Data Única" else "no período selecionado"
            st.warning(f"O modelo não encontrou Edge suficiente (>0.0%) ou não há jogos qualificados para {texto_data}.")
        else:
            st.session_state['mostrar_tabela_scanner'] = True
            st.session_state['df_bruto_scanner'] = df_bruto
            st.session_state['df_completo_scanner'] = df_completo

    if st.session_state.get('mostrar_tabela_scanner', False):
        df_bruto = st.session_state['df_bruto_scanner']
        df_completo = st.session_state['df_completo_scanner']
        
        col_res1, col_sort, col_ordem, col_odd, col_edge, col_score, col_btn = st.columns([3.0, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8])
        with col_sort: coluna_ordem = st.selectbox("Ordenar por", ["Horário", "EV+", "Score"], key="scan_ord1")
        with col_ordem: direcao_ordem = st.selectbox("Ordem", ["Crescente", "Decrescente"], key="scan_ord2")
        with col_odd: odd_selecionada = st.number_input("Odd Lay", min_value=2.30, max_value=3.50, value=2.30, step=0.10, format="%.2f", key="scan_odd")
        with col_edge: edge_selecionado = st.number_input("EV+ (%)", min_value=0.0, max_value=50.0, value=0.0, step=0.50, format="%.1f", key="scan_edge")
        with col_score: score_selecionado = st.number_input("Score", min_value=0, max_value=100, value=0, step=1, key="scan_score")
        
        df_final_filtrado = df_bruto[(df_bruto["Odd_A_Lay"] >= odd_selecionada) & (df_bruto["Edge"] >= (edge_selecionado/100.0)) & (df_bruto["Score"] >= score_selecionado)].copy()
        
        with col_res1:
            st.markdown(f"<div style='text-align: left; font-size: 18px; margin-top: 34px; margin-bottom: 20px;'><span style='color: #888;'>Oportunidades Encontradas:</span> <span style='color: #00d26a; font-weight: 900;'>{len(df_final_filtrado)} jogo(s)</span></div>", unsafe_allow_html=True)

        tabela = df_final_filtrado[['Date', 'Time', 'League', 'Home', 'Away', 'Odd_A_Lay', 'Pontos Casa', 'Pontos Fora', 'FTS Fora', 'DP GM Fora', 'DP GS Casa', 'Vaz Def Fora', 'CS Casa', 'XG_Casa', 'XG_Fora', 'Edge', 'Score', 'Alerta']].copy()
        
        if not tabela.empty:
            tabela['Date'] = pd.to_datetime(tabela['Date'])
            is_ascending = (direcao_ordem == "Crescente")
            if coluna_ordem == "Horário": tabela = drop_reset_index(tabela.sort_values(by=['Date', 'Time'], ascending=[is_ascending, is_ascending]))
            elif coluna_ordem == "EV+": tabela = drop_reset_index(tabela.sort_values(by=['Edge'], ascending=is_ascending))
            elif coluna_ordem == "Score": tabela = drop_reset_index(tabela.sort_values(by=['Score'], ascending=is_ascending))

            tabela['Date'] = tabela['Date'].dt.strftime('%d/%m/%Y')
            tabela_excel = tabela.rename(columns={'Date': 'Data', 'Time': 'Horário', 'League': 'Liga', 'Home': 'Time Casa', 'Away': 'Time Fora', 'Odd_A_Lay': 'Odd Lay', 'Pontos Casa': 'Pts Casa', 'Pontos Fora': 'Pts Fora', 'XG_Casa': 'xG Casa', 'XG_Fora': 'xG Fora', 'Edge': 'EV+'})

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: tabela_excel.to_excel(writer, index=False, sheet_name='Lay_Away')
            
            with col_btn:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                st.download_button("📥 Exportar Excel", data=buffer.getvalue(), file_name="Jogos_LayAway.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=False)
            
            def estilizar_linhas_premium(row):
                cor_fundo = '#1e1e1e' if row.name % 2 == 0 else '#121212'
                return [f'background-color: {cor_fundo}; color: #e0e0e0; text-align: center !important; font-size: 15px; border-bottom: 1px solid #333;'] * len(row)

            tabela_estilizada = tabela_excel.style.apply(estilizar_linhas_premium, axis=1).format({'Odd Lay': '{:.2f}', 'xG Casa': '{:.2f}', 'xG Fora': '{:.2f}', 'EV+': '{:.1%}'}, na_rep="-").hide(axis="index").set_table_attributes('style="width: 100%; border-collapse: collapse; margin-top: 5px; border: 1px solid #333;"').set_table_styles([{'selector': 'th', 'props': [('background-color', '#262730'), ('color', '#ffffff'), ('text-align', 'center !important'), ('font-weight', 'bold'), ('font-size', '16px'), ('padding', '12px 8px'), ('border-bottom', '2px solid #00d26a')]}, {'selector': 'td', 'props': [('text-align', 'center !important'), ('padding', '12px 8px')]}])
                
            html_final = tabela_estilizada.to_html()
            
            tooltips_dicionario = {
                '>xG Casa</th>': '><span class="tooltip-header" data-title="A Verdade Atual: O diferencial entre o xG do Mandante e do Visitante dita o favoritismo real de hoje. É o motor do modelo. | Quanto MAIOR, melhor. (Ideal: > 1.50)">xG Casa</span></th>',
                '>xG Fora</th>': '><span class="tooltip-header" data-title="A Verdade Atual: O diferencial entre o xG do Mandante e do Visitante dita o favoritismo real de hoje. É o motor do modelo. | Quanto MENOR, melhor. (Ideal: < 1.00)">xG Fora</span></th>',
                '>Pts Casa</th>': '><span class="tooltip-header" data-title="Soma os pontos do time jogando em casa nos últimos 5 jogos. | Quanto MAIOR, melhor. (Ideal: >= 10 pts)">Pts Casa</span></th>',
                '>Pts Fora</th>': '><span class="tooltip-header" data-title="Soma os pontos do time jogando fora de casa nos últimos 5 jogos. | Quanto MENOR, melhor. (Ideal: <= 5 pts)">Pts Fora</span></th>',
                '>FTS Fora</th>': '><span class="tooltip-header" data-title="Quantas vezes o time visitante não marcou nenhum gol nos seus últimos 5 jogos fora de casa e tira a média. | Quanto MAIOR, melhor. (Ideal: >= 0.60)">FTS Fora</span></th>',
                '>DP GM Fora</th>': '><span class="tooltip-header" data-title="(Desvio Padrão Gols Marcados) Calcula a oscilação de gols marcados pelo visitante nos últimos 5 jogos. | Quanto MENOR, melhor. (Ideal: < 1.00)">DP GM Fora</span></th>',
                '>DP GS Casa</th>': '><span class="tooltip-header" data-title="(Desvio Padrão Gols Sofridos) A mesma lógica do desvio padrão, mas aplicada aos gols que o mandante sofreu nos últimos 5 jogos em casa, para medir a estabilidade da zaga. | Quanto MENOR, melhor. (Ideal: < 1.00)">DP GS Casa</span></th>',
                '>Vaz Def Fora</th>': '><span class="tooltip-header" data-title="Pega a média de gols sofridos pelo time visitante nos últimos 5 jogos fora de casa. | Quanto MAIOR, melhor. (Ideal: >= 1.50)">Vaz Def Fora</span></th>',
                '>CS Casa</th>': '><span class="tooltip-header" data-title="Verifica quantas vezes o time da casa não sofreu gols nos seus últimos 5 jogos em casa e tira a média. | Quanto MAIOR, melhor. (Ideal: >= 0.40)">CS Casa</span></th>',
                '>EV+</th>': '><span class="tooltip-header" data-title="Vantagem (Edge): Margem de valor real encontrada pelo modelo em relação à cotação da casa de apostas. | Quanto MAIOR, melhor.">EV+</span></th>',
                '>Score</th>': '><span class="tooltip-header" data-title="Nota de 0 a 100 gerada pela normalização de todos os pesos. Serve como um guia de risco consolidado. | Quanto MAIOR, melhor. (Ideal: >= 55)">Score</span></th>',
                '>Alerta</th>': '><span class="tooltip-header" data-title="Visualização Rápida de Risco. Verde >= 55. Amarelo 48 a 54. Vermelho < 48. | O ideal é focar nos Verdes e Amarelos.">Alerta</span></th>'
            }
            for string_velha, string_nova in tooltips_dicionario.items(): html_final = html_final.replace(string_velha, string_nova)

            st.markdown(html_final, unsafe_allow_html=True)
            st.markdown("<br><br>", unsafe_allow_html=True)
            
            st.markdown("<hr style='margin-top: 10px; margin-bottom: 20px; border: 1px solid #333;'>", unsafe_allow_html=True)
            st.markdown("<p style='font-size: 16px; color: #e0e0e0; font-weight: bold; margin-bottom: 5px;'>📊 Abrir Gráfico de Tendência (Pop-up)</p>", unsafe_allow_html=True)
            col_sel, col_btn_graf, col_vazia = st.columns([0.8, 0.6, 3])
            with col_sel:
                st.markdown("<div style='margin-top: 0px;'></div>", unsafe_allow_html=True)
                jogo_alvo = st.selectbox("Selecione o Jogo:", tabela['Home'] + " x " + tabela['Away'], label_visibility="collapsed", key="scan_graf")
            with col_btn_graf:
                st.markdown("<div style='margin-top: -14px;'></div>", unsafe_allow_html=True)
                if st.button("📈 Ver Gráfico na Janela", use_container_width=True, key="scan_btn_graf", type="secondary"):
                    if jogo_alvo:
                        t_casa, t_fora = jogo_alvo.split(" x ")
                        abrir_popup_grafico(t_casa, t_fora, df_completo)
        else:
            st.info("Nenhum jogo atende aos critérios do modelo para a data selecionada.")

# ==========================================
# PÁGINA 2: RESULTADOS PASSADOS
# ==========================================
def pagina_resultados():
    st.markdown("<p class='titulo-premium'>RESULTADOS LAY AWAY</p>", unsafe_allow_html=True)
    fuso_br = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_br).strftime("%d/%m/%Y às %H:%M:%S")
    st.markdown(f"<p class='data-atualizacao'>Última atualização: {agora}</p>", unsafe_allow_html=True)
    
    col_nav, espaco, col_rad, col_dat, col_resp, col_btn_pesq = st.columns([1.2, 1.5, 1.4, 1.2, 0.9, 1.2])

    with col_nav:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔙 Voltar para o Scanner", key="btn_nav_scan", use_container_width=True, type="secondary"):
            mudar_pagina('scanner')
            st.rerun()

    with col_rad:
        st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
        tipo_filtro = st.radio("Período", ["Data Única", "Intervalo"], horizontal=True, label_visibility="collapsed", key="res_rad")

    with col_dat:
        st.markdown("<div style='font-size: 14px; font-weight: bold; margin-bottom: 2px;'>Data da Pesquisa</div>", unsafe_allow_html=True)
        ontem = datetime.now(fuso_br).date() - timedelta(days=1)
        if tipo_filtro == "Data Única":
            data_selecionada = st.date_input("Data", value=ontem, max_value=ontem, format="DD/MM/YYYY", label_visibility="collapsed", key="res_dt1")
        else:
            data_selecionada = st.date_input("Data", value=(ontem, ontem), max_value=ontem, format="DD/MM/YYYY", label_visibility="collapsed", key="res_dt2")

    with col_resp:
        st.markdown("<div style='font-size: 14px; font-weight: bold; margin-bottom: 2px;'>Responsabilidade</div>", unsafe_allow_html=True)
        resp_input = st.number_input("Responsabilidade", min_value=1.0, value=30.0, step=5.0, format="%.2f", label_visibility="collapsed", key="res_resp")
        
    with col_btn_pesq:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        btn_procurar = st.button("🚀 Iniciar Pesquisa", use_container_width=True, key="res_btn", type="primary")
        
    st.markdown("<hr style='margin-top: 0px; margin-bottom: 25px; border: 1px solid #333;'>", unsafe_allow_html=True)

    if btn_procurar:
        st.session_state['mostrar_tabela_resultados'] = False 
        df_bruto, _, df_livescore = rodar_engine_pesquisa(data_selecionada, tipo_filtro, "Calculando resultados históricos...")
        
        if df_bruto.empty:
            st.warning("Não foram encontrados alertas do Scanner no período selecionado.")
        else:
            df_resultados = df_bruto[['Date', 'Time', 'League', 'Home', 'Away', 'Home_LS', 'Away_LS', 'Odd_A_Lay', 'Edge', 'Score']].copy()
            
            df_resultados['Date_Match'] = pd.to_datetime(df_resultados['Date']).dt.strftime('%Y-%m-%d')
            df_livescore['Date_Match'] = pd.to_datetime(df_livescore['Date']).dt.strftime('%Y-%m-%d')
            
            df_livescore['Goals_H_FT'] = pd.to_numeric(df_livescore['Goals_H_FT'], errors='coerce')
            df_livescore['Goals_A_FT'] = pd.to_numeric(df_livescore['Goals_A_FT'], errors='coerce')
            
            df_final = pd.merge(
                df_resultados, 
                df_livescore[['Date_Match', 'Home', 'Away', 'Goals_H_FT', 'Goals_A_FT']].drop_duplicates(subset=['Date_Match', 'Home', 'Away']), 
                left_on=['Date_Match', 'Home_LS', 'Away_LS'], 
                right_on=['Date_Match', 'Home', 'Away'],
                how='inner',
                suffixes=('', '_drop')
            )
            
            df_final = df_final.dropna(subset=['Goals_H_FT', 'Goals_A_FT']).copy()
            
            if df_final.empty:
                st.info("Os jogos alertados pelo scanner nesta data ainda não possuem placar finalizado no banco de dados.")
            else:
                st.session_state['mostrar_tabela_resultados'] = True
                st.session_state['df_resultados'] = df_final
                st.session_state['valor_responsabilidade'] = resp_input

    if st.session_state.get('mostrar_tabela_resultados', False):
        df_final = st.session_state['df_resultados'].copy()
        resp_atual = st.session_state['valor_responsabilidade']
        
        col_res1, col_espaco, col_btn = st.columns([7.0, 1.0, 2.0])
        
        df_view = df_final.copy()
        
        if df_view.empty:
            st.warning("Nenhum resultado atende aos filtros atuais.")
        else:
            df_view = df_view.sort_values(by=['Date', 'Time'], ascending=[True, True])
            df_view = drop_reset_index(df_view)

            def calc_profit(row):
                gc, gf, odd_lay = row['Goals_H_FT'], row['Goals_A_FT'], row['Odd_A_Lay']
                if gc >= gf: return (resp_atual / (odd_lay - 1)) * 0.9550 
                else: return -resp_atual 

            df_view['Profit'] = df_view.apply(calc_profit, axis=1)
            df_view['Profit Acumulado'] = df_view['Profit'].cumsum()
            
            def html_resultado(row):
                cor = "#00d26a" if row['Goals_H_FT'] >= row['Goals_A_FT'] else "#ff4b4b"
                return f"<div style='width: 20px; height: 20px; background-color: {cor}; border-radius: 4px; margin: auto;'></div>"
            df_view['Resultado'] = df_view.apply(html_resultado, axis=1)

            # --- NOVOS CÁLCULOS DE GREEN E RED ---
            qtd_green = len(df_view[df_view['Goals_H_FT'] >= df_view['Goals_A_FT']])
            qtd_red = len(df_view[df_view['Goals_H_FT'] < df_view['Goals_A_FT']])

            lucro_total = df_view['Profit'].sum()
            odd_media = df_view['Odd_A_Lay'].mean()
            cor_lucro = "#00d26a" if lucro_total >= 0 else "#ff4b4b"
            
            with col_res1:
                st.markdown(f"""
                <div style='text-align: left; font-size: 18px; margin-top: 34px; margin-bottom: 20px;'>
                    <span style='color: #888;'>Operações Finalizadas:</span> <span style='color: #00d26a; font-weight: 900;'>{len(df_view)}</span> | 
                    <span style='color: #888;'>Resultado Período:</span> <span style='color: {cor_lucro}; font-weight: 900;'>R$ {lucro_total:.2f}</span> | 
                    <span style='color: #888;'>Odd Média Período:</span> <span style='color: #e0e0e0; font-weight: bold;'>{odd_media:.2f}</span> | 
                    <span style='color: #888;'>Green:</span> <span style='color: #00d26a; font-weight: 900;'>{qtd_green}</span> | 
                    <span style='color: #888;'>RED:</span> <span style='color: #ff4b4b; font-weight: 900;'>{qtd_red}</span>
                </div>
                """, unsafe_allow_html=True)

            tabela_final = df_view[['Date', 'Time', 'League', 'Home', 'Away', 'Odd_A_Lay', 'Goals_H_FT', 'Goals_A_FT', 'Resultado', 'Profit', 'Profit Acumulado']].copy()
            tabela_final['Date'] = pd.to_datetime(tabela_final['Date']).dt.strftime('%d/%m/%Y')
            
            tabela_final['Goals_H_FT'] = tabela_final['Goals_H_FT'].astype(int)
            tabela_final['Goals_A_FT'] = tabela_final['Goals_A_FT'].astype(int)

            tabela_excel = tabela_final.rename(columns={'Date': 'Data', 'Time': 'Hora', 'League': 'Liga', 'Home': 'Time Casa', 'Away': 'Time Fora', 'Odd_A_Lay': 'Odd Lay', 'Goals_H_FT': 'Gols Casa', 'Goals_A_FT': 'Gols Fora'})
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: tabela_excel.drop(columns=['Resultado']).to_excel(writer, index=False, sheet_name='Resultados')
            
            with col_btn:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                st.download_button("📥 Exportar Resultados Excel", data=buffer.getvalue(), file_name="Resultados Jogos Lay Away.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="res_export")

            def estilizar_linhas_resultados(row):
                cor_fundo = '#1e1e1e' if row.name % 2 == 0 else '#121212'
                return [f'background-color: {cor_fundo}; color: #e0e0e0; text-align: center !important; font-size: 15px; border-bottom: 1px solid #333;'] * len(row)

            def formatar_moeda(val):
                return f"R$ {val:.2f}"

            tabela_estilizada = tabela_excel.style.apply(estilizar_linhas_resultados, axis=1)\
                .format({'Odd Lay': '{:.2f}', 'Profit': formatar_moeda, 'Profit Acumulado': formatar_moeda})\
                .hide(axis="index")\
                .set_table_attributes('style="width: 100%; border-collapse: collapse; margin-top: 5px; border: 1px solid #333;"')\
                .set_table_styles([
                    {'selector': 'th', 'props': [('background-color', '#262730'), ('color', '#ffffff'), ('text-align', 'center !important'), ('font-weight', 'bold'), ('font-size', '16px'), ('padding', '12px 8px'), ('border-bottom', '2px solid #00d26a')]},
                    {'selector': 'td', 'props': [('text-align', 'center !important'), ('padding', '12px 8px'), ('vertical-align', 'middle')]}
                ])
                
            st.markdown(tabela_estilizada.to_html(escape=False), unsafe_allow_html=True)
            st.markdown("<br><br>", unsafe_allow_html=True)

# ==========================================
# ROTEADOR DE PÁGINAS
# ==========================================
if check_password():
    if st.session_state['pagina_atual'] == 'scanner':
        pagina_scanner()
    elif st.session_state['pagina_atual'] == 'resultados':
        pagina_resultados()
