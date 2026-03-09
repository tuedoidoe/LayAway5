import streamlit as st
import pandas as pd
import numpy as np
import joblib
import urllib.request
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E LOGIN
# ==========================================
st.set_page_config(page_title="Lay Away", page_icon="🎯", layout="wide")

# CSS customizado para forçar alinhamento e botões mais bonitos
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: #0068c9;
        color: white;
        border-radius: 5px;
        width: 100%;
        font-weight: bold;
    }
    div.stButton > button:first-child:hover {
        background-color: #0052a3;
        border-color: #0052a3;
    }
    </style>
""", unsafe_allow_html=True)

def check_password():
    # 1. Se já estiver logado, retorna True imediatamente e NÃO desenha a imagem!
    if st.session_state.get("password_correct", False):
        return True

    # 2. Se NÃO estiver logado, desenha a tela de login com a imagem
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
# FUNÇÃO DE CARREGAMENTO (COM CACHE)
# ==========================================
@st.cache_data(ttl=900)
def carregar_dados():
    url_base_mae = "https://github.com/futpythontrader/Bases_de_Dados/raw/refs/heads/main/Base_de_Dados_BetfairExchange.csv"
    df = pd.read_csv(url_base_mae)
    df['Date'] = pd.to_datetime(df['Date'])
    return df

# ==========================================
# CÓDIGO DO SCANNER
# ==========================================
if check_password():
    
    # Mantemos a proporção [1.5, 1, 1.5] para deixar tudo estreito e alinhado
    col_t1, col_t2, col_t3 = st.columns([1.5, 1, 1.5])
    
    with col_t2:
        
        st.markdown("<h2 style='text-align: center;'>🎯 Scanner Lay Away</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Busca automatizada de oportunidades de valor.</p>", unsafe_allow_html=True)
        
        # Seletor de Data e Botão alinhados na mesma largura
        data_consulta = st.date_input("📅 Escolha a data para consulta:", datetime.now())
        dia_consulta = data_consulta.strftime("%Y-%m-%d")
        btn_procurar = st.button("🚀 Iniciar Varredura")
        
    st.divider() # Linha de separação visual

    if btn_procurar:
        with st.spinner('Baixando inteligência e processando o mercado...'):
            try:
                # 1. Carrega Modelo
                url_modelo = 'https://github.com/tuedoidoe/LayAway5/raw/refs/heads/main/Modelo_LayAway_5.pkl'
                caminho_local = 'Modelo_LayAway_5.pkl'
                urllib.request.urlretrieve(url_modelo, caminho_local)
                dados_modelo = joblib.load(caminho_local)
                
                model = dados_modelo['modelo']
                taxas_ligas = dados_modelo['liga_rates']
                media_global_treino = dados_modelo['media_global']
                X_cols_treino = dados_modelo['features']
                ligas_autorizadas = dados_modelo.get('ligas_autorizadas', [])
                
                # 2. Carrega Base com Cache
                df_hist = carregar_dados()
                
                # 3. Lógica de Consulta
                df_alvo = df_hist[df_hist['Date'] == dia_consulta].copy()
                
                tradutor_ligas = {
                    "English Championship": "ENGLAND 2", "Belgian First Division A": "BELGIUM 1",
                    "French Ligue 1": "FRANCE 1", "Italian Serie B": "ITALY 2",
                    "Spanish Segunda Division": "SPAIN 2", "Dutch Eredivisie": "NETHERLANDS 1",
                    "Swiss Super League": "SWITZERLAND 1", "Chilean Primera Division": "CHILE 1",
                    "Chinese Super League": "CHINA 1", "South Korean K League 2": "SOUTH KOREA 2",
                    "Scottish Championship": "SCOTLAND 2", "Danish Superliga": "DENMARK 1",
                    "English League 2": "ENGLAND 4", "Slovakian Super League": "SLOVAKIA 1",
                    "Irish Premier Division": "IRELAND 1"
                }
                df_alvo['League'] = df_alvo['League'].replace(tradutor_ligas)
                df_alvo = df_alvo[df_alvo['League'].isin(ligas_autorizadas)].copy()
                
                if len(df_alvo) == 0:
                    st.info(f"O modelo não identificou jogos lucrativos para {dia_consulta}.")
                else:
                    def safe_prob(column):
                        return (1 / pd.to_numeric(column, errors='coerce').replace(0, np.nan)).fillna(0)
                        
                    data_limite = df_alvo['Date'].min()
                    df_hist_passado = df_hist[df_hist['Date'] < data_limite].copy()
                    df_completo = pd.concat([df_hist_passado, df_alvo], ignore_index=True)
                    df_completo = df_completo.sort_values(["Date", "Home"]).reset_index(drop=True)
                    
                    # Feature Engineering
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
                    
                    df_hoje = df_completo[df_completo['Date'] == dia_consulta].copy()
                    df_hoje = df_hoje[(df_hoje['Odd_A_Lay'] <= 4.00) & (df_hoje['Odd_H_Back'] < df_hoje['Odd_A_Back']) & (abs(df_hoje['Odd_A_Back'] - df_hoje['Odd_A_Lay']) <= 1.00) & (abs(df_hoje['Odd_H_Back'] - df_hoje['Odd_H_Lay']) <= 1.00)].copy()
                    
                    if len(df_hoje) == 0:
                        st.info("Nenhum jogo passou nos filtros iniciais de Odd (Máx 4.00).")
                    else:
                        df_hoje = df_hoje.dropna().reset_index(drop=True)
                        df_hoje["Previsao"] = model.predict_proba(df_hoje[X_cols_treino])[:, 1]
                        df_hoje["Edge"] = df_hoje["Previsao"] - (1 - (1 / df_hoje["Odd_A_Lay"]))
                        
                        df_final = df_hoje[df_hoje["Edge"] > 0.09].copy()
                        
                        if len(df_final) == 0:
                            st.warning(f"O modelo filtrou o mercado, mas não encontrou Edge suficiente (>0.09) para operar em {dia_consulta}.")
                        else:
                            # --- MODO DE EXIBIÇÃO VISUAL ---
                            col_met1, col_met2, col_met3 = st.columns([1, 2, 1])
                            with col_met2:
                                # 1. Removido o delta verde (Edge > 0.09)
                                st.metric(label="Oportunidades Encontradas", value=f"{len(df_final)} Jogos")
                            
                            st.markdown("<br>", unsafe_allow_html=True) # Espaçamento
                            
                            # 2. Preparação da Tabela
                            tabela = df_final[['Date', 'Time', 'League', 'Home', 'Away', 'Odd_A_Lay']].copy()
                            tabela = tabela.rename(columns={
                                'Date': 'Data',
                                'Time': 'Horário',
                                'League': 'Liga',
                                'Home': 'Time Casa',
                                'Away': 'Time Fora',
                                'Odd_A_Lay': 'Odd Lay'
                            })
                            
                            tabela['Data'] = pd.to_datetime(tabela['Data']).dt.strftime('%d/%m/%Y')
                            tabela = tabela.sort_values(by='Horário', ascending=True).reset_index(drop=True)
                            
                            # 3. Função para as linhas alternadas com centralização FORÇADA (!important)
                            def cores_alternadas(row):
                                cor_fundo = '#4a4a4a' if row.name % 2 == 0 else '#333333'
                                return [f'background-color: {cor_fundo}; color: white; text-align: center !important; font-size: 18px;' for _ in row]

                            # 4. Aplicando o Estilo Final
                            tabela_estilizada = tabela.style.apply(cores_alternadas, axis=1) \
                                .format({'Odd Lay': '{:.2f}'}) \
                                .hide(axis="index") \
                                .set_table_styles([
                                    # Estilo do Cabeçalho (Primeira Linha)
                                    {'selector': 'th', 'props': [
                                        ('background-color', '#696969'), 
                                        ('color', 'black'), 
                                        ('text-align', 'center !important'), 
                                        ('font-weight', 'bold'),
                                        ('font-size', '22px'), # FONTE AUMENTADA AQUI
                                        ('padding', '12px')
                                    ]},
                                    # Reforço de centralização para todas as células de dados
                                    {'selector': 'td', 'props': [
                                        ('text-align', 'center !important')
                                    ]}
                                ])
                            
                            # 5. Exibição da Tabela (usando HTML para garantir a remoção do Índice)
                            col_esq, col_central, col_dir = st.columns([0.1, 5, 0.1])
                            with col_central:
                                # Renderiza a tabela em HTML puro. O índice '0' desaparece de vez!
                                st.markdown(tabela_estilizada.to_html(), unsafe_allow_html=True)
                                
            except Exception as e:
                st.error(f"Erro inesperado durante o processamento: {e}")
