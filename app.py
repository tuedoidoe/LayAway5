import streamlit as st
import pandas as pd
import numpy as np
import joblib
import warnings
from datetime import datetime
import requests 
import io       

warnings.filterwarnings("ignore")

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E LOGIN
# ==========================================
st.set_page_config(page_title="Lay Away", page_icon="🎯", layout="wide")

st.markdown("""
    <style>
    div[data-testid="stRadio"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex !important;
        justify-content: center !important;
        margin: 0 auto !important;
        width: max-content !important;
    }
    div[data-testid="stDateInput"] input {
        text-align: center !important;
    }
    
    /* Cor do Botão Principal (Azul) */
    div[data-testid="stButton"] > button {
        background-color: #0068c9 !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 5px !important;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: #0052a3 !important;
        border-color: #0052a3 !important;
        color: white !important;
    }

    /* Cor do Botão de Download (Fúcsia) */
    div[data-testid="stDownloadButton"] > button {
        background-color: #FF00FF !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 5px !important;
        width: 100% !important;
        margin-top: 5px !important;
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #CC00CC !important;
        border-color: #CC00CC !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

def check_password():
    if st.session_state.get("password_correct", False):
        return True

    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    with col2:
        st.image("logo.png", use_container_width=True)
        
        def password_entered():
            if st.session_state["password"] == st.secrets["senha_secreta"]:
                st.session_state["password_correct"] = True
                del st.session_state["password"]
            else:
                st.session_state["password_correct"] = False

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
@st.cache_data(ttl=900)
def carregar_dados():
    url_base_mae = "https://github.com/futpythontrader/Bases_de_Dados/raw/refs/heads/main/Base_de_Dados_BetfairExchange.csv"
    df = pd.read_csv(url_base_mae)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

TOKEN = "b9f385cc07be27e7b04fe3a68c15120dd633d109"
headers = {"Authorization": f"Token {TOKEN}"}

@st.cache_data(ttl=300) 
def baixar_jogos_do_dia(data):
    url = f"https://api.futpythontrader.com/api/dados/jogos-do-dia/betfair/{data}/download/"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            df_api = pd.read_csv(io.BytesIO(response.content))
            if not df_api.empty and 'Date' in df_api.columns:
                df_api['Date'] = pd.to_datetime(df_api['Date'])
            return df_api
        else:
            return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# CÓDIGO DO SCANNER
# ==========================================
if check_password():
    
    col_t1, col_t2, col_t3 = st.columns([1.5, 1, 1.5])
    
    with col_t2:
        st.markdown("<h2 style='text-align: center;'>🎯 Scanner Lay Away</h2>", unsafe_allow_html=True)
                
        col_rad1, col_rad2, col_rad3 = st.columns([0.4, 2, 0.4])
        with col_rad2:
            tipo_filtro = st.radio("Formato de Pesquisa:", ["Data Única", "Intervalo de Datas"], horizontal=True, label_visibility="collapsed")
        
        hoje = datetime.now().date()
        st.markdown("<br>", unsafe_allow_html=True)
        
        if tipo_filtro == "Data Única":
            st.markdown("<p style='text-align: center; margin-bottom: 5px; font-weight: bold;'>📅 Escolha a data para consulta:</p>", unsafe_allow_html=True)
            data_selecionada = st.date_input("Data única", value=hoje, label_visibility="collapsed")
        else:
            st.markdown("<p style='text-align: center; margin-bottom: 5px; font-weight: bold;'>📅 Escolha o período para consulta:</p>", unsafe_allow_html=True)
            data_selecionada = st.date_input("Intervalo", value=(hoje, hoje), label_visibility="collapsed")
            
        st.markdown("<br>", unsafe_allow_html=True)
        btn_procurar = st.button("🚀 Iniciar Varredura", use_container_width=True)
        
    st.divider()

    # Se clicar em procurar, ele apaga a memória antiga
    if btn_procurar:
        st.session_state['mostrar_tabela'] = False 
        
        with st.spinner('Baixando inteligência e processando o mercado...'):
            try:
                # Carregamento LOCAL do modelo (Muito mais rápido e seguro)
                dados_modelo = joblib.load('Modelo_LayAway_5.pkl')
                
                model = dados_modelo['modelo']
                taxas_ligas = dados_modelo['liga_rates']
                media_global_treino = dados_modelo['media_global']
                X_cols_treino = dados_modelo['features']
                ligas_autorizadas = dados_modelo.get('ligas_autorizadas', [])
                
                df_hist = carregar_dados()
                df_alvo_lista = []
                
                if tipo_filtro == "Data Única":
                    texto_data = data_selecionada.strftime('%d/%m/%Y')
                    data_api = data_selecionada.strftime('%Y-%m-%d')
                    df_dia = baixar_jogos_do_dia(data_api)
                    if not df_dia.empty:
                        df_alvo_lista.append(df_dia)
                else:
                    if isinstance(data_selecionada, tuple) and len(data_selecionada) == 2:
                        d_inicio, d_fim = data_selecionada
                    else:
                        d_inicio = d_fim = data_selecionada[0]
                        
                    texto_data = f"de {d_inicio.strftime('%d/%m/%Y')} até {d_fim.strftime('%d/%m/%Y')}"
                    
                    datas_intervalo = pd.date_range(start=d_inicio, end=d_fim)
                    for data_atual in datas_intervalo:
                        data_api = data_atual.strftime('%Y-%m-%d')
                        df_dia = baixar_jogos_do_dia(data_api)
                        if not df_dia.empty:
                            df_alvo_lista.append(df_dia)
                
                if df_alvo_lista:
                    df_alvo = pd.concat(df_alvo_lista, ignore_index=True)
                else:
                    df_alvo = pd.DataFrame()
                
                tradutor_ligas = {
                    "Argentinian Primera Division": "ARGENTINA 1",
                    "Argentinian Primera B Nacional": "ARGENTINA 2",
                    "Australian A-League Men": "AUSTRALIA 1",
                    "Austrian Bundesliga": "AUSTRIA 1",
                    "Austrian Erste Liga": "AUSTRIA 2",
                    "Belgian First Division A": "BELGIUM 1",
                    "Brazilian Serie A": "BRAZIL 1",
                    "Chilean Primera Division": "CHILE 1",
                    "Chinese Super League": "CHINA 1",
                    "Czech 1 Liga": "CZECH 1",
                    "Danish Superliga": "DENMARK 1",
                    "Ecuadorian Serie A": "ECUADOR 1",
                    "English Premier League": "ENGLAND 1",
                    "English Championship": "ENGLAND 2",
                    "English League 2": "ENGLAND 4",
                    "UEFA Europa Conference League": "EUROPA CONFERENCE LEAGUE",
                    "UEFA Europa League": "EUROPA LEAGUE",
                    "French National": "FRANCE 3",
                    "German Bundesliga": "GERMANY 1",
                    "German 3 Liga": "GERMANY 3",
                    "Icelandic Urvalsdeild": "ICELAND 1",
                    "Irish Premier Division": "IRELAND 1",
                    "Irish Division 1": "IRELAND 2",
                    "Italian Serie B": "ITALY 2",
                    "Italian Serie C": "ITALY 3",
                    "Japanese J League": "JAPAN 1",
                    "Mexican Liga MX": "MEXICO 1",
                    "Norwegian Eliteserien": "NORWAY 1",
                    "Paraguayan Primera Division": "PARAGUAY 1",
                    "Portuguese Segunda Liga": "PORTUGAL 2",
                    "Romanian Liga I": "ROMANIA 1",
                    "Saudi Professional League": "SAUDI ARABIA 1",
                    "South Korean K League 2": "SOUTH KOREA 2",
                    "Spanish La Liga": "SPAIN 1",
                    "Spanish Segunda Division": "SPAIN 2",
                    "Swiss Super League": "SWITZERLAND 1",
                    "Turkish Super League": "TURKEY 1",
                    "US MLS": "USA 1"
                }
                
                if not df_alvo.empty and 'League' in df_alvo.columns:
                    df_alvo['League'] = df_alvo['League'].replace(tradutor_ligas)
                    df_alvo = df_alvo[df_alvo['League'].isin(ligas_autorizadas)].copy()
                
                if len(df_alvo) == 0:
                    st.info(f"A API não identificou jogos cadastrados e autorizados para {texto_data}.")
                else:
                    def safe_prob(column):
                        return (1 / pd.to_numeric(column, errors='coerce').replace(0, np.nan)).fillna(0)
                        
                    data_limite = df_alvo['Date'].min()
                    df_hist_passado = df_hist[df_hist['Date'] < data_limite].copy()
                    df_completo = pd.concat([df_hist_passado, df_alvo], ignore_index=True)
                    df_completo = df_completo.sort_values(["Date", "Home"]).reset_index(drop=True)
                    
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
                            
                            df_final = df_hoje[df_hoje["Edge"] > 0.05].copy()
                            
                            if len(df_final) == 0:
                                st.warning(f"O modelo filtrou o mercado, mas não encontrou Edge suficiente (>0.05) para operar em {texto_data}.")
                            else:
                                # SALVA OS RESULTADOS NA MEMÓRIA DO STREAMLIT
                                st.session_state['mostrar_tabela'] = True
                                st.session_state['df_final'] = df_final

            except Exception as e:
                st.error(f"Erro inesperado durante o processamento: {e}")

    # ==========================================
    # EXIBIÇÃO VISUAL E BOTÃO DE DOWNLOAD
    # (Fica fora do btn_procurar para não sumir)
    # ==========================================
    if st.session_state.get('mostrar_tabela', False):
        df_final = st.session_state['df_final']
        
        # Prepara os dados brutos e renomeia
        tabela = df_final[['Date', 'Time', 'League', 'Home', 'Away', 'Odd_A_Lay', 'Edge']].copy()
        tabela = tabela.rename(columns={
            'Date': 'Data', 'Time': 'Horário', 'League': 'Liga',
            'Home': 'Time Casa', 'Away': 'Time Fora',
            'Odd_A_Lay': 'Odd Lay', 'Edge': 'Vantagem (> 5.0%)'
        })
        tabela['Data'] = pd.to_datetime(tabela['Data']).dt.strftime('%d/%m/%Y')
        tabela = tabela.sort_values(by=['Data', 'Horário'], ascending=[True, True]).reset_index(drop=True)

        col_esq, col_central, col_dir = st.columns([1, 4, 1])
        
        with col_central:
            # Layout Superior: Texto na esquerda, Botão na direita
            col_texto, col_botao = st.columns([2.5, 1])
            
            with col_texto:
                texto_resultado = f"""
                <div style='text-align: left; font-size: 20px; margin-top: 15px; margin-bottom: 10px;'>
                    Oportunidades Encontradas: <span style='color: #00d26a; background-color: rgba(0, 210, 106, 0.1); padding: 4px 12px; border-radius: 6px; font-weight: bold;'>{len(tabela)} jogo(s)</span>
                </div>
                """
                st.markdown(texto_resultado, unsafe_allow_html=True)
                
            with col_botao:
                # Transforma para Excel em Memória
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    tabela.to_excel(writer, index=False, sheet_name='Lay_Away')
                
                st.download_button(
                    label="📥 Baixar Jogos",
                    data=buffer.getvalue(),
                    file_name="Jogos_LayAway.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            # Monta o visual da Tabela
            def cores_alternadas(row):
                cor_fundo = '#4a4a4a' if row.name % 2 == 0 else '#333333'
                return [f'background-color: {cor_fundo}; color: white; text-align: center !important; font-size: 16px;' for _ in row]

            tabela_estilizada = tabela.style.apply(cores_alternadas, axis=1) \
                .format({
                    'Odd Lay': '{:.2f}',
                    'Vantagem (> 5.0%)': '{:.1%}'
                }) \
                .hide(axis="index") \
                .set_table_attributes('style="width: 100%; margin: 0 auto; border-collapse: collapse;"') \
                .set_table_styles([
                    {'selector': 'th', 'props': [
                        ('background-color', '#696969'), 
                        ('color', 'black'), 
                        ('text-align', 'center !important'), 
                        ('font-weight', 'bold'),
                        ('font-size', '22px'), 
                        ('padding', '6px')
                    ]},
                    {'selector': 'td', 'props': [
                        ('text-align', 'center !important'),
                        ('padding', '10px')
                    ]}
                ])
                
            st.markdown(tabela_estilizada.to_html(), unsafe_allow_html=True)
