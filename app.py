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
    
    /* CSS para o Tooltip Customizado (Caixa Compacta) */
    .tooltip-header { 
        position: relative; 
        cursor: help; 
        border-bottom: 1px dotted #ffffff; 
    }
    .tooltip-header:hover::after {
        content: attr(data-title);
        position: absolute;
        bottom: 140%; 
        left: 50%; 
        transform: translateX(-50%);
        background-color: #1a1a1a; 
        color: #00d26a; 
        padding: 8px 12px; 
        border-radius: 6px; 
        font-size: 13px; 
        font-weight: normal;
        white-space: normal; 
        width: max-content; 
        max-width: 250px; 
        z-index: 999; 
        border: 1px solid #333; 
        text-align: left;
        line-height: 1.3;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.5);
    }
    .tooltip-header:hover::before {
        content: ""; 
        position: absolute; 
        bottom: 100%; 
        left: 50%; 
        transform: translateX(-50%);
        border-width: 5px; 
        border-style: solid; 
        border-color: #1a1a1a transparent transparent transparent;
    }
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
                
                # --- DICIONÁRIOS OMITIDOS AQUI PARA BREVIDADE NA RESPOSTA, MAS MANTENHA OS SEUS TRADUTORES NO CÓDIGO REAL ---
                tradutor_ligas = {"Argentinian Primera Division": "ARGENTINA 1", "Argentinian Primera B Nacional": "ARGENTINA 2", "Brazilian Serie A": "BRAZIL 1", "US MLS": "USA 1"} # Exemplo curto, mantenha sua lista inteira
                tradutor_times = {"Vasco Da Gama": "Vasco", "LA Galaxy": "Los Angeles Galaxy"} # Exemplo curto, mantenha sua lista inteira
                
                if not df_alvo.empty and 'League' in df_alvo.columns:
                    # df_alvo['League'] = df_alvo['League'].replace(tradutor_ligas) # Descomente na versão final
                    df_alvo = df_alvo[df_alvo['League'].isin(ligas_autorizadas)].copy()
                    # df_alvo['Home'] = df_alvo['Home'].replace(tradutor_times) # Descomente na versão final
                    # df_alvo['Away'] = df_alvo['Away'].replace(tradutor_times) # Descomente na versão final
                
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
                    # 1. CÁLCULO DAS MÉTRICAS BASE
                    # ========================================================
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

                    # ========================================================
                    # 2. EXPECTATIVA DE GOLS (Pseudo-xG)
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
                    # 3. NORMALIZAÇÃO E CÁLCULO DO "SCORE" (0 a 100)
                    # ========================================================
                    # XG (Peso 30): Proporção do xG Casa sobre o Total (Quanto maior, melhor)
                    xg_total = df_completo['XG_Casa'] + df_completo['XG_Fora']
                    score_xg = np.where(xg_total > 0, (df_completo['XG_Casa'] / xg_total) * 30.0, 15.0)

                    # Pontos (Peso 10 cada): Casa direto, Fora Invertido
                    score_pts_casa = (soma_pts_casa.fillna(0) / 15.0) * 10.0
                    score_pts_fora = ((15.0 - soma_pts_fora.fillna(0)) / 15.0) * 10.0

                    # Frequências (FTS Peso 15, CS Peso 5): Escala direta (0 a 1)
                    score_fts = soma_fts_fora.fillna(0) * 15.0
                    score_cs = soma_cs_casa.fillna(0) * 5.0

                    # Desvios Padrões (Peso 10 cada): Inversos (Teto 2.0 = nota 0)
                    score_dp_gm = (np.maximum(0, 2.0 - dp_gm_fora.fillna(1.0)) / 2.0) * 10.0
                    score_dp_gs = (np.maximum(0, 2.0 - dp_gs_casa.fillna(1.0)) / 2.0) * 10.0

                    # Vazamento (Peso 10): Direto (Visitante vazar é bom pro Lay, Teto 3.0)
                    score_vaz = (np.minimum(3.0, vaz_def_fora.fillna(0)) / 3.0) * 10.0

                    # SOMA FINAL DO SCORE
                    df_completo['Score'] = score_xg + score_pts_casa + score_pts_fora + score_fts + score_cs + score_dp_gm + score_dp_gs + score_vaz
                    df_completo['Score'] = df_completo['Score'].fillna(0).round(0).astype(int)

                    # Geração do Alerta Visual
                    def definir_alerta(score):
                        if score > 75: return '🟢'
                        elif score > 50: return '🟡'
                        else: return '🔴'
                    df_completo['Alerta'] = df_completo['Score'].apply(definir_alerta)

                    # Formatação de Exibição das Colunas Base
                    df_completo['Pontos Casa'] = np.where(qtd_jogos_casa > 0, soma_pts_casa.fillna(0).astype(int).astype(str), "-")
                    df_completo['Pontos Fora'] = np.where(qtd_jogos_fora > 0, soma_pts_fora.fillna(0).astype(int).astype(str), "-")
                    df_completo['CS Casa'] = np.where(qtd_jogos_casa > 0, soma_cs_casa.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['FTS Fora'] = np.where(qtd_jogos_fora > 0, soma_fts_fora.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['DP GS Casa'] = np.where(qtd_jogos_casa > 1, dp_gs_casa.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['DP GM Fora'] = np.where(qtd_jogos_fora > 1, dp_gm_fora.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    df_completo['Vaz Def Fora'] = np.where(qtd_jogos_fora > 0, vaz_def_fora.apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-"), "-")
                    
                    # ========================================================
                    # MÉTRICAS EXTRAS DO MODELO
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
        
        col_esq, col_central, col_dir = st.columns([0.05, 4.9, 0.05])
        with col_central:
            
            # FILTROS VISUAIS OCULTADOS DO CÓDIGO (COMENTADOS)
            odd_selecionada = 2.50
            edge_selecionado = 0.0
            
            df_filtrado_odd = df_bruto[df_bruto["Odd_A_Lay"] >= odd_selecionada].copy()
            edge_decimal = edge_selecionado / 100.0
            df_final_filtrado = df_filtrado_odd[df_filtrado_odd["Edge"] >= edge_decimal].copy()
            
            texto_resultado = f"""
            <div style='text-align: left; font-size: 18px; margin-top: 20px; margin-bottom: 10px; white-space: nowrap;'>
                Oportunidades Encontradas: <span style='color: #00d26a; background-color: rgba(0, 210, 106, 0.1); padding: 4px 12px; border-radius: 6px; font-weight: bold;'>{len(df_final_filtrado)} jogo(s)</span>
            </div>
            """
            st.markdown(texto_resultado, unsafe_allow_html=True)

            # Nova ordem das colunas, incluindo Score e Alerta
            tabela = df_final_filtrado[['Date', 'Time', 'League', 'Home', 'Away', 'Odd_A_Lay', 'Pontos Casa', 'Pontos Fora', 'FTS Fora', 'DP GM Fora', 'DP GS Casa', 'Vaz Def Fora', 'CS Casa', 'XG_Casa', 'XG_Fora', 'Score', 'Alerta', 'Edge']].copy()
            
            if not tabela.empty:
                tabela['Date'] = pd.to_datetime(tabela['Date'])
                tabela = tabela.sort_values(by=['Score', 'Date', 'Time'], ascending=[False, True, True]).reset_index(drop=True)
                tabela['Date'] = tabela['Date'].dt.strftime('%d/%m/%Y')

                # Tabela Original para Exportação Excel
                tabela_excel = tabela.rename(columns={
                    'Date': 'Data', 'Time': 'Horário', 'League': 'Liga', 'Home': 'Time Casa', 'Away': 'Time Fora',
                    'Odd_A_Lay': 'Odd Lay', 'Pontos Casa': 'Pts Casa', 'Pontos Fora': 'Pts Fora',
                    'XG_Casa': 'xG Casa', 'XG_Fora': 'xG Fora', 'Edge': 'Vantagem'
                })

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    tabela_excel.to_excel(writer, index=False, sheet_name='Lay_Away')
                
                with espaco_download:
                    st.download_button("📥 Baixar Jogos", data=buffer.getvalue(), file_name="Jogos_LayAway.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                
                # Tabela de Exibição Web (Removendo "Vantagem" da visualização)
                tabela_web = tabela_excel.drop(columns=['Vantagem'])

                # ========================================================
                # LÓGICA DE ESTILIZAÇÃO LIMPA (SEM CORES NO TEXTO)
                # ========================================================
                def estilizar_linhas_limpas(row):
                    cor_fundo = '#4a4a4a' if row.name % 2 == 0 else '#333333'
                    # Mantém o texto sempre branco, mudando apenas a cor de fundo da linha
                    return [f'background-color: {cor_fundo}; color: white; text-align: center !important; font-size: 16px;'] * len(row)

                tabela_estilizada = tabela_web.style.apply(estilizar_linhas_limpas, axis=1) \
                    .format({'Odd Lay': '{:.2f}', 'xG Casa': '{:.2f}', 'xG Fora': '{:.2f}'}, na_rep="-") \
                    .hide(axis="index") \
                    .set_table_attributes('style="width: 100%; margin: 0 auto; border-collapse: collapse;"') \
                    .set_table_styles([
                        {'selector': 'th', 'props': [
                            ('background-color', '#696969'), ('color', 'black'), 
                            ('text-align', 'center !important'), ('font-weight', 'bold'),
                            ('font-size', '19px'), ('padding', '6px')
                        ]},
                        {'selector': 'td', 'props': [('text-align', 'center !important'), ('padding', '10px')]}
                    ])
                    
                # Substituição das Strings HTML pelas Tooltips Customizadas
                html_final = tabela_estilizada.to_html()
                tooltips_dicionario = {
                    '>xG Casa</th>': '><span class="tooltip-header" data-title="A Verdade Atual: O diferencial entre o xG do Mandante e do Visitante dita o favoritismo real de hoje. É o motor do modelo.">xG Casa</span></th>',
                    '>xG Fora</th>': '><span class="tooltip-header" data-title="A Verdade Atual: O diferencial entre o xG do Mandante e do Visitante dita o favoritismo real de hoje. É o motor do modelo.">xG Fora</span></th>',
                    '>Pts Casa</th>': '><span class="tooltip-header" data-title="Embalo (Casa): Garante que estamos confiando o nosso dinheiro em um time que está acostumado a vencer no seu estádio.">Pts Casa</span></th>',
                    '>Pts Fora</th>': '><span class="tooltip-header" data-title="Crise (Fora): Confirma a má fase do visitante, mostrando que ele tem o hábito de tropeçar.">Pts Fora</span></th>',
                    '>FTS Fora</th>': '><span class="tooltip-header" data-title="Inofensividade: Penaliza fortemente o visitante se ele tem o costume de passar jogos sem marcar nenhum gol.">FTS Fora</span></th>',
                    '>DP GM Fora</th>': '><span class="tooltip-header" data-title="Filtro Anti-Zebra: Queremos um número baixo. Evita que a gente aposte contra um time que do nada mete 3 gols num jogo só.">DP GM Fora</span></th>',
                    '>DP GS Casa</th>': '><span class="tooltip-header" data-title="Muralha Estável: Queremos um número baixo. Confirma que a zaga do mandante não é de lua (um dia boa, outro dia péssima).">DP GS Casa</span></th>',
                    '>Vaz Def Fora</th>': '><span class="tooltip-header" data-title="Caminho Livre: Média de gols sofridos pelo visitante. Se eles sempre tomam gol, a nossa aposta fica muito mais tranquila.">Vaz Def Fora</span></th>',
                    '>CS Casa</th>': '><span class="tooltip-header" data-title="Seguro 0x0: Bônus para mandantes que saem de campo sem tomar gols, garantindo o nosso empate protetor.">CS Casa</span></th>',
                    '>Score</th>': '><span class="tooltip-header" data-title="Nota de 0 a 100 gerada pela normalização de todos os pesos. Serve como um guia de risco consolidado.">Score</span></th>',
                    '>Alerta</th>': '><span class="tooltip-header" data-title="Visualização Rápida de Risco. Verde > 75. Amarelo 51 a 75. Vermelho <= 50.">Alerta</span></th>'
                }

                for string_velha, string_nova in tooltips_dicionario.items():
                    html_final = html_final.replace(string_velha, string_nova)

                st.markdown(html_final, unsafe_allow_html=True)
            else:
                st.info(f"Nenhum jogo atende aos critérios (Mín Odd Lay: {odd_selecionada:.2f} e Edge: {edge_selecionado:.1f}%).")
                with espaco_download: st.empty()
