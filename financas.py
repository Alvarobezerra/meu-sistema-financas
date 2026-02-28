import streamlit as st
import pandas as pd
from datetime import datetime
from google import genai 

# 1. IMPORTAÇÃO DA BIBLIOTECA DE PLANILHA NA NUVEM
from streamlit_gsheets import GSheetsConnection

# Configuração da página
st.set_page_config(page_title="Controle Financeiro", layout="wide")

# ==========================================
# INJEÇÃO DE CSS: ALINHAMENTO, FONTES E BOTÕES
# ==========================================
st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] {
        margin-bottom: -22px !important; 
        align-items: flex-start !important; 
    }
    .stCheckbox {
        min-height: 0px !important;
        margin-bottom: 0px !important;
        padding-top: 4px !important; 
    }
    .stCheckbox label {
        min-height: 0px !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
    }
    button[data-testid="baseButton-secondary"] {
        min-height: 22px !important;
        height: 26px !important;
        padding: 0px 6px !important;
        margin-top: 2px !important;
        border-radius: 4px !important;
    }
    button[data-testid="baseButton-secondary"] p {
        font-size: 12px !important; 
    }
    button[data-testid="baseButton-primary"], 
    button[data-testid="baseButton-formSubmit"] {
        min-height: 40px !important;
        height: auto !important;
        padding: 6px 16px !important;
    }
    button[data-testid="baseButton-primary"] p, 
    button[data-testid="baseButton-formSubmit"] p {
        font-size: 16px !important;
    }
    hr {
        margin: 10px 0px 8px 0px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        margin-bottom: 30px !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# SISTEMA DE LOGIN / AUTENTICAÇÃO
# ==========================================
USUARIO_CORRETO = "Silvia"      # <--- MUDE O SEU USUÁRIO AQUI
SENHA_CORRETA = "Mae041820"     # <--- MUDE A SUA SENHA AQUI

if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>🔒 Acesso Restrito</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário")
                senha_input = st.text_input("Senha", type="password")
                submit_login = st.form_submit_button("Entrar", type="primary", use_container_width=True)
                
                if submit_login:
                    if usuario_input == USUARIO_CORRETO and senha_input == SENHA_CORRETA:
                        st.session_state['autenticado'] = True
                        st.rerun() # Recarrega a página liberando o sistema
                    else:
                        st.error("❌ Usuário ou senha incorretos!")
    
    # O comando abaixo impede que o resto do código seja lido se não estiver logado
    st.stop() 


# ==========================================
# O SISTEMA REAL COMEÇA AQUI (SÓ APARECE APÓS LOGIN)
# ==========================================
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# ==========================================
# NOVAS FUNÇÕES PARA GOOGLE SHEETS
# ==========================================
def carregar_dados():
    try:
        # Conecta no Google Sheets usando os Secrets
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0) # ttl=0 garante leitura em tempo real
        
        if df.empty or "Tipo" not in df.columns:
            return pd.DataFrame(columns=[
                "Tipo", "Categoria", "Descrição", "Valor", "Recorrência", 
                "Mes_Inicio", "Ano_Inicio", "Mes_Fim", "Ano_Fim", "Meses_Pagos"
            ])
            
        df["Categoria"] = df["Categoria"].fillna("Geral")
        df["Meses_Pagos"] = df["Meses_Pagos"].fillna("")
        
        # Garante que as colunas de Ano sejam lidas como números inteiros
        df['Ano_Inicio'] = pd.to_numeric(df['Ano_Inicio'], errors='coerce').fillna(datetime.now().year).astype(int)
        df['Ano_Fim'] = pd.to_numeric(df['Ano_Fim'], errors='coerce').fillna(datetime.now().year).astype(int)
        
        return df
    except Exception as e:
        st.error("Banco de Dados Vazio ou Conexão Pendente.")
        return pd.DataFrame(columns=[
            "Tipo", "Categoria", "Descrição", "Valor", "Recorrência", 
            "Mes_Inicio", "Ano_Inicio", "Mes_Fim", "Ano_Fim", "Meses_Pagos"
        ])

def salvar_dados(df):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(data=df)
    except Exception as e:
        st.error(f"Erro ao salvar na nuvem: {e}")

if 'df' not in st.session_state:
    st.session_state.df = carregar_dados()

def lancamento_ativo(row, mes_alvo, ano_alvo):
    idx_inicio = row['Ano_Inicio'] * 12 + MESES.index(row['Mes_Inicio'])
    idx_fim = row['Ano_Fim'] * 12 + MESES.index(row['Mes_Fim'])
    idx_alvo = ano_alvo * 12 + MESES.index(mes_alvo)
    return idx_inicio <= idx_alvo <= idx_fim

def calcular_saldo_anterior(mes_alvo, ano_alvo, df):
    idx_alvo = ano_alvo * 12 + MESES.index(mes_alvo)
    saldo_total = 0.0
    for _, row in df.iterrows():
        idx_inicio = row['Ano_Inicio'] * 12 + MESES.index(row['Mes_Inicio'])
        idx_fim = row['Ano_Fim'] * 12 + MESES.index(row['Mes_Fim'])
        start_count = idx_inicio
        end_count = min(idx_fim, idx_alvo - 1)
        if start_count <= end_count:
            str_pagos = str(row.get('Meses_Pagos', ''))
            pagos_list = [p.strip() for p in str_pagos.split(',') if p.strip()]
            meses_ativos_nao_pagos = 0
            for curr_idx in range(start_count, end_count + 1):
                curr_m = MESES[curr_idx % 12]
                curr_a = curr_idx // 12
                if f"{curr_m}/{curr_a}" not in pagos_list:
                    meses_ativos_nao_pagos += 1
            if row['Tipo'] == 'Receita':
                saldo_total += row['Valor'] * meses_ativos_nao_pagos
            else:
                saldo_total -= row['Valor'] * meses_ativos_nao_pagos
    return saldo_total

def obter_meses_exibicao(ano_selecionado, mostrar_passados=False):
    if mostrar_passados:
        return MESES
    hoje = datetime.now()
    ano_atual = hoje.year
    mes_atual_idx = hoje.month - 1
    if ano_selecionado < ano_atual: return [] 
    elif ano_selecionado == ano_atual: return MESES[mes_atual_idx:] 
    else: return MESES 

def formata_moeda(valor):
    if valor is None or pd.isna(valor): return ""
    if valor == 0: return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def altera_pagamento(idx_db, mes_ano_str):
    str_pagos = str(st.session_state.df.loc[idx_db, 'Meses_Pagos'])
    pagos_list = [p.strip() for p in str_pagos.split(',') if p.strip()]
    if mes_ano_str in pagos_list:
        pagos_list.remove(mes_ano_str)
    else:
        pagos_list.append(mes_ano_str)
    st.session_state.df.loc[idx_db, 'Meses_Pagos'] = ','.join(pagos_list)
    salvar_dados(st.session_state.df)

# ==========================================
# FUNÇÕES MODAIS
# ==========================================
@st.dialog("✏️ Editar Lançamento")
def modal_editar(idx):
    row = st.session_state.df.loc[idx]
    tipo_idx = 0 if row["Tipo"] == "Despesa" else 1
    tipo = st.selectbox("Tipo", ["Despesa", "Receita"], index=tipo_idx, key="edit_tipo")
    
    categoria = "Geral"
    if tipo == "Despesa":
        cat_idx = 0 if row["Categoria"] == "Geral" else 1
        categoria = st.selectbox("Categoria da Despesa", ["Geral", "Crianças"], index=cat_idx, key="edit_cat")
        
    descricao = st.text_input("Item", value=row["Descrição"], key="edit_desc")
    valor = st.number_input("Valor (R$)", min_value=0.01, value=float(row["Valor"]), format="%0.2f", key="edit_valor")
    
    opcoes_rec = ["Apenas em um mês", "Faixa de meses", "Todos os meses"]
    rec_idx = opcoes_rec.index(row["Recorrência"]) if row["Recorrência"] in opcoes_rec else 0
    recorrencia = st.selectbox("Vigência", opcoes_rec, index=rec_idx, key="edit_rec")
    
    if recorrencia == "Apenas em um mês":
        col_m, col_a = st.columns(2)
        with col_m: mes_unico = st.selectbox("Mês", MESES, index=MESES.index(row["Mes_Inicio"]), key="edit_m1")
        with col_a: ano_unico = st.number_input("Ano", min_value=2020, max_value=2100, value=int(row["Ano_Inicio"]), key="edit_a1")
        mes_inicio, mes_fim, ano_inicio, ano_fim = mes_unico, mes_unico, ano_unico, ano_unico
    elif recorrencia == "Faixa de meses":
        c1, c2 = st.columns(2)
        with c1: mes_inicio = st.selectbox("Mês Início", MESES, index=MESES.index(row["Mes_Inicio"]), key="edit_m2")
        with c2: ano_inicio = st.number_input("Ano Início", min_value=2020, max_value=2100, value=int(row["Ano_Inicio"]), key="edit_a2")
        c3, c4 = st.columns(2)
        with c3: mes_fim = st.selectbox("Mês Fim", MESES, index=MESES.index(row["Mes_Fim"]), key="edit_m3")
        with c4: ano_fim = st.number_input("Ano Fim", min_value=2020, max_value=2100, value=int(row["Ano_Fim"]), key="edit_a3")
    else:
        c1, c2 = st.columns(2)
        with c1: ano_inicio = st.number_input("Ano Início", min_value=2020, max_value=2100, value=int(row["Ano_Inicio"]), key="edit_a4")
        with c2: ano_fim = st.number_input("Ano Fim", min_value=2020, max_value=2100, value=int(row["Ano_Fim"]), key="edit_a5")
        mes_inicio, mes_fim = "Janeiro", "Dezembro"
        
    if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
        if not descricao: st.error("Por favor, preencha o nome do Item.")
        elif (ano_fim * 12 + MESES.index(mes_fim)) < (ano_inicio * 12 + MESES.index(mes_inicio)): st.error("Erro: Data de término anterior a início!")
        else:
            st.session_state.df.loc[idx, "Tipo"] = tipo
            st.session_state.df.loc[idx, "Categoria"] = categoria
            st.session_state.df.loc[idx, "Descrição"] = descricao
            st.session_state.df.loc[idx, "Valor"] = valor
            st.session_state.df.loc[idx, "Recorrência"] = recorrencia
            st.session_state.df.loc[idx, "Mes_Inicio"] = mes_inicio
            st.session_state.df.loc[idx, "Ano_Inicio"] = ano_inicio
            st.session_state.df.loc[idx, "Mes_Fim"] = mes_fim
            st.session_state.df.loc[idx, "Ano_Fim"] = ano_fim
            st.session_state.df.loc[idx, "Meses_Pagos"] = row.get("Meses_Pagos", "")
            salvar_dados(st.session_state.df)
            st.success("Alteração salva!")
            st.rerun()

@st.dialog("✏️ Inserir/Ajustar Saldo Atual")
def modal_saldo(mes, ano):
    mask = (st.session_state.df['Descrição'] == 'Saldo Atual') & \
           (st.session_state.df['Mes_Inicio'] == mes) & \
           (st.session_state.df['Ano_Inicio'] == ano) & \
           (st.session_state.df['Tipo'] == 'Receita')
    
    existente = st.session_state.df[mask]
    valor_atual = float(existente['Valor'].iloc[0]) if not existente.empty else 0.0
    
    st.write(f"Declare um Saldo Atual (Entrada de Receita Extra) para **{mes}/{ano}**:")
    novo_valor = st.number_input("Valor a Inserir (R$)", min_value=0.0, value=valor_atual, format="%0.2f")
    
    if st.button("💾 Salvar Saldo Atual", type="primary", use_container_width=True):
        if not existente.empty:
            idx = existente.index[0]
            if novo_valor > 0: st.session_state.df.loc[idx, 'Valor'] = novo_valor
            else: st.session_state.df = st.session_state.df.drop(idx).reset_index(drop=True)
        else:
            if novo_valor > 0:
                novo_dado = {
                    "Tipo": "Receita", "Categoria": "Geral", "Descrição": "Saldo Atual", 
                    "Valor": novo_valor, "Recorrência": "Apenas em um mês", 
                    "Mes_Inicio": mes, "Ano_Inicio": ano, "Mes_Fim": mes, "Ano_Fim": ano, "Meses_Pagos": ""
                }
                novo_df = pd.DataFrame([novo_dado])
                st.session_state.df = pd.concat([st.session_state.df, novo_df], ignore_index=True)
                
        salvar_dados(st.session_state.df)
        st.success("Saldo atualizado com sucesso!")
        st.rerun()

st.title("💰 Controle Financeiro Pessoal")

aba_cadastro, aba_resumo, aba_detalhada, aba_ia = st.tabs([
    "📝 Cadastrar Lançamento", 
    "📊 Resumo por Período", 
    "📋 Visão Planilha",
    "🤖 Consultor IA"
])

tem_dados = not st.session_state.df.empty
anos_cadastrados = set()
if tem_dados:
    for idx, row in st.session_state.df.iterrows():
        anos_cadastrados.update(range(int(row['Ano_Inicio']), int(row['Ano_Fim']) + 1))
anos_disponiveis = sorted(list(anos_cadastrados)) if anos_cadastrados else [datetime.now().year]

# ==========================================
# ABA 1: CADASTRO E GERENCIAMENTO OTIMIZADO
# ==========================================
with aba_cadastro:
    st.markdown("#### Configuração do Lançamento")
    c_tipo, c_rec = st.columns(2)
    
    with c_tipo: tipo = st.radio("Tipo:", ["Despesa", "Receita"], horizontal=True)
    with c_rec: recorrencia = st.radio("Vigência:", ["Apenas em um mês", "Faixa de meses", "Todos os meses"], horizontal=True)

    with st.form("form_cadastro", clear_on_submit=True):
        st.markdown("##### 1. Dados do Item")
        if tipo == "Despesa":
            col_cat, col_desc, col_val = st.columns([1, 2, 1])
            with col_cat: categoria = st.selectbox("Categoria", ["Geral", "Crianças"])
            with col_desc: descricao = st.text_input("Descrição (Ex: Mensalidade, Farmácia)")
            with col_val: valor = st.number_input("Valor (R$)", min_value=0.01, format="%0.2f")
        else:
            categoria = "Geral"
            col_desc, col_val = st.columns([3, 1])
            with col_desc: descricao = st.text_input("Descrição (Ex: Perícia, Consignado)")
            with col_val: valor = st.number_input("Valor (R$)", min_value=0.01, format="%0.2f")
                
        st.markdown("##### 2. Período de Aplicação")
        if recorrencia == "Apenas em um mês":
            col_m, col_a, _ = st.columns([1, 1, 2])
            with col_m: mes_unico = st.selectbox("Mês", MESES)
            with col_a: ano_unico = st.number_input("Ano", min_value=2020, max_value=2100, value=datetime.now().year)
            mes_inicio, mes_fim, ano_inicio, ano_fim = mes_unico, mes_unico, ano_unico, ano_unico
        elif recorrencia == "Faixa de meses":
            c1, c2, c3, c4 = st.columns(4)
            with c1: mes_inicio = st.selectbox("Mês Início", MESES, key="m_ini")
            with c2: ano_inicio = st.number_input("Ano Início", min_value=2020, max_value=2100, value=datetime.now().year, key="a_ini")
            with c3: mes_fim = st.selectbox("Mês Fim", MESES, index=11, key="m_fim")
            with c4: ano_fim = st.number_input("Ano Fim", min_value=2020, max_value=2100, value=datetime.now().year, key="a_fim")
        else: 
            c1, c2, _ = st.columns([1, 1, 2])
            with c1: ano_inicio = st.number_input("Ano de Início", min_value=2020, max_value=2100, value=datetime.now().year)
            with c2: ano_fim = st.number_input("Ano de Fim (Infinito? Coloque 2100)", min_value=2020, max_value=2100, value=datetime.now().year)
            mes_inicio, mes_fim = "Janeiro", "Dezembro"
            
        st.markdown("") 
        if st.form_submit_button("✅ Cadastrar Lançamento", type="primary", use_container_width=True):
            if not descricao: st.error("Por favor, preencha o nome do Item.")
            elif (ano_fim * 12 + MESES.index(mes_fim)) < (ano_inicio * 12 + MESES.index(mes_inicio)): st.error("Erro: Data de término anterior à data de início!")
            else:
                novo_dado = {
                    "Tipo": tipo, "Categoria": categoria, "Descrição": descricao, "Valor": valor,
                    "Recorrência": recorrencia, "Mes_Inicio": mes_inicio, "Ano_Inicio": ano_inicio,
                    "Mes_Fim": mes_fim, "Ano_Fim": ano_fim, "Meses_Pagos": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([novo_dado])], ignore_index=True)
                salvar_dados(st.session_state.df)
                st.success(f"✅ '{descricao}' cadastrado com sucesso!")

    st.divider()
    st.markdown("### 📋 Lançamentos Cadastrados")
    if st.session_state.df.empty: st.info("Nenhum lançamento cadastrado no banco de dados.")
    else:
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1: filtro_tipo = st.selectbox("Filtrar Tipo", ["Todos", "Despesa", "Receita"])
        with col_f2: filtro_categoria = st.selectbox("Filtrar Categoria", ["Todas", "Geral", "Crianças"])
        with col_f3: filtro_ano = st.selectbox("Filtrar Ano", ["Todos"] + anos_disponiveis)
        with col_f4: filtro_mes = st.selectbox("Filtrar Mês", ["Todos"] + MESES)

        df_filtrado = st.session_state.df.copy()
        if filtro_tipo != "Todos": df_filtrado = df_filtrado[df_filtrado["Tipo"] == filtro_tipo]
        if filtro_categoria != "Todas": df_filtrado = df_filtrado[df_filtrado["Categoria"] == filtro_categoria]
        if filtro_ano != "Todos" and filtro_mes != "Todos":
            mask = df_filtrado.apply(lambda row: lancamento_ativo(row, filtro_mes, int(filtro_ano)), axis=1)
            df_filtrado = df_filtrado[mask]
        elif filtro_ano != "Todos":
            df_filtrado = df_filtrado[(df_filtrado["Ano_Inicio"] <= int(filtro_ano)) & (df_filtrado["Ano_Fim"] >= int(filtro_ano))]

        if df_filtrado.empty: st.warning("Nenhum lançamento encontrado com estes filtros.")
        else:
            df_filtrado = df_filtrado.sort_values(by=['Tipo', 'Valor'], ascending=[True, False])
            for idx, row in df_filtrado.iterrows():
                with st.container(border=True):
                    col_info, col_valor, col_btn_edit, col_btn_del = st.columns([4, 2, 1, 1])
                    with col_info:
                        icone = "🟢" if row['Tipo'] == "Receita" else ("🧸" if row['Categoria'] == "Crianças" else "🔴")
                        st.markdown(f"**{icone} {row['Descrição']}** ({row['Tipo']})")
                        if row['Mes_Inicio'] == row['Mes_Fim'] and row['Ano_Inicio'] == row['Ano_Fim']: st.caption(f"📅 Apenas em {row['Mes_Inicio']}/{row['Ano_Inicio']}")
                        else: st.caption(f"📅 Vigência: {row['Mes_Inicio']}/{row['Ano_Inicio']} até {row['Mes_Fim']}/{row['Ano_Fim']}")
                    with col_valor: st.markdown(f"<h4 style='margin:0; padding:0; color:{'#28a745' if row['Tipo']=='Receita' else '#dc3545'};'>R$ {row['Valor']:,.2f}</h4>".replace(",", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)
                    with col_btn_edit:
                        if st.button("✏️ Editar", key=f"edit_{idx}"): modal_editar(idx)
                    with col_btn_del:
                        if st.button("🗑️ Excluir", key=f"del_{idx}"):
                            st.session_state.df = st.session_state.df.drop(idx).reset_index(drop=True)
                            salvar_dados(st.session_state.df)
                            st.rerun()

# ==========================================
# ABA 2: RESUMO POR PERÍODO
# ==========================================
with aba_resumo:
    st.markdown("### Acumulado do Período")
    if not tem_dados:
        st.info("Nenhum dado cadastrado.")
    else:
        col_m_ini, col_a_ini, col_m_fim, col_a_fim = st.columns(4)
        with col_m_ini: mes_ini_resumo = st.selectbox("Mês Inicial", MESES, key="res_m_ini")
        with col_a_ini: ano_ini_resumo = st.selectbox("Ano Inicial", anos_disponiveis, key="res_a_ini")
        with col_m_fim: mes_fim_resumo = st.selectbox("Mês Final", MESES, index=datetime.now().month - 1, key="res_m_fim")
        with col_a_fim: ano_fim_resumo = st.selectbox("Ano Final", anos_disponiveis, key="res_a_fim")
            
        idx_resumo_ini = ano_ini_resumo * 12 + MESES.index(mes_ini_resumo)
        idx_resumo_fim = ano_fim_resumo * 12 + MESES.index(mes_fim_resumo)
        
        st.write("") 
        if idx_resumo_fim < idx_resumo_ini: st.error("⚠️ O período final não pode ser anterior ao período inicial.")
        else:
            tot_rec, tot_desp, tot_criancas = 0.0, 0.0, 0.0
            
            for _, row in st.session_state.df.iterrows():
                item_ini = row['Ano_Inicio'] * 12 + MESES.index(row['Mes_Inicio'])
                item_fim = row['Ano_Fim'] * 12 + MESES.index(row['Mes_Fim'])
                
                overlap_ini = max(idx_resumo_ini, item_ini)
                overlap_fim = min(idx_resumo_fim, item_fim)
                
                if overlap_ini <= overlap_fim:
                    str_pagos = str(row.get('Meses_Pagos', ''))
                    pagos_list = [p.strip() for p in str_pagos.split(',') if p.strip()]
                    
                    meses_ativos_validos = 0
                    for curr_idx in range(overlap_ini, overlap_fim + 1):
                        curr_m = MESES[curr_idx % 12]
                        curr_a = curr_idx // 12
                        if f"{curr_m}/{curr_a}" not in pagos_list:
                            meses_ativos_validos += 1
                            
                    valor_total_item = row['Valor'] * meses_ativos_validos
                    if row['Tipo'] == 'Receita': tot_rec += valor_total_item
                    else:
                        tot_desp += valor_total_item
                        if row['Categoria'] == 'Crianças': tot_criancas += valor_total_item
                            
            saldo_periodo = tot_rec - tot_desp
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Projeção de Receitas", formata_moeda(tot_rec))
            c2.metric("Projeção de Despesas", formata_moeda(tot_desp))
            c3.metric("Projeção c/ Crianças", formata_moeda(tot_criancas))
            c4.metric("Balanço Pendente", formata_moeda(saldo_periodo), delta="Positivo" if saldo_periodo >= 0 else "Negativo", delta_color="normal" if saldo_periodo >= 0 else "inverse")
            st.caption("ℹ️ *Atenção: Itens que foram marcados como 'Pagos ✅' na planilha não entram nesta soma.*")
            st.divider()
            
            st.markdown("#### Detalhamento Mensal Pendente")
            dados_mensais = []
            
            for current_idx in range(idx_resumo_ini, idx_resumo_fim + 1):
                ano_m = current_idx // 12
                mes_m = MESES[current_idx % 12]
                mes_ano_str = f"{mes_m}/{ano_m}"
                
                mask_m = st.session_state.df.apply(lambda r: lancamento_ativo(r, mes_m, ano_m), axis=1)
                df_m = st.session_state.df[mask_m]
                
                if not df_m.empty:
                    mask_nao_pago = [mes_ano_str not in [p.strip() for p in str(row_pagos).split(',') if p.strip()] for row_pagos in df_m['Meses_Pagos']]
                    df_m = df_m[mask_nao_pago]
                    
                    r_val = df_m[df_m["Tipo"] == "Receita"]["Valor"].sum()
                    d_val = df_m[df_m["Tipo"] == "Despesa"]["Valor"].sum()
                    c_val = df_m[df_m["Categoria"] == "Crianças"]["Valor"].sum()
                    s_val = r_val - d_val
                else:
                    r_val, d_val, c_val, s_val = 0.0, 0.0, 0.0, 0.0
                
                dados_mensais.append({
                    "Período": f"{mes_m}/{ano_m}", "Receitas": r_val, "Despesas": d_val, "Crianças": c_val, "Saldo do Mês": s_val
                })
            
            if dados_mensais:
                df_mensal = pd.DataFrame(dados_mensais)
                def estilizar_tabela_resumo(row):
                    if row.name % 2 == 0: return ['background-color: rgba(128, 128, 128, 0.2);'] * len(row)
                    return [''] * len(row)
                    
                df_mensal_formatado = pd.DataFrame({
                    "Período": df_mensal["Período"],
                    "Receitas": [formata_moeda(v) for v in df_mensal["Receitas"]],
                    "Despesas": [formata_moeda(v) for v in df_mensal["Despesas"]],
                    "Gastos (Crianças)": [formata_moeda(v) for v in df_mensal["Crianças"]],
                    "Balanço": [formata_moeda(v) for v in df_mensal["Saldo do Mês"]]
                })
                
                st.dataframe(df_mensal_formatado.style.apply(estilizar_tabela_resumo, axis=1), hide_index=True, use_container_width=True)
                
                st.write("")
                st.markdown("#### 📈 Evolução Gráfica")
                df_grafico = df_mensal.set_index("Período")
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown("**Receitas vs Despesas (Pendentes)**")
                    st.bar_chart(df_grafico[["Receitas", "Despesas"]], color=["#28a745", "#dc3545"])
                with col_g2:
                    st.markdown("**Evolução do Saldo Mensal**")
                    st.line_chart(df_grafico[["Saldo do Mês"]], color=["#1f77b4"])


# ==========================================
# ABA 3: VISÃO PLANILHA MINIMALISTA 
# ==========================================
with aba_detalhada:
    st.markdown("### Visão Contínua e Baixa de Lançamentos")
    st.caption("✔️ **Marque a caixinha** para dar baixa. O valor deixará de ser contado nas pendências.")
    
    if not tem_dados:
        st.info("Cadastre lançamentos para gerar a visualização.")
    else:
        col_ano_ini, col_ano_fim, col_toggle_plan = st.columns([1, 1, 2])
        with col_ano_ini: ano_inicio_plan = st.selectbox("Ano Inicial", anos_disponiveis, index=0, key="ano_ini_plan")
        with col_ano_fim: ano_fim_plan = st.selectbox("Ano Final", anos_disponiveis, index=len(anos_disponiveis)-1, key="ano_fim_plan")
        with col_toggle_plan:
            st.write(""); st.write("")
            mostrar_passados_plan = st.toggle("👁️ Mostrar meses passados", value=False, key="t_planilha")
            
        st.write("") 
        
        if ano_fim_plan < ano_inicio_plan: st.warning("⚠️ O Ano Final não pode ser menor que o Ano Inicial.")
        else:
            periodos_exibicao = []
            for ano_iter in range(ano_inicio_plan, ano_fim_plan + 1):
                meses_ano = obter_meses_exibicao(ano_iter, mostrar_passados_plan)
                for m in meses_ano: periodos_exibicao.append((ano_iter, m))
            
            if not periodos_exibicao: st.info("Todos os meses do período selecionado já passaram.")
            else:
                for i in range(0, len(periodos_exibicao), 3):
                    cols = st.columns(3)
                    
                    for j in range(3):
                        if i + j < len(periodos_exibicao):
                            ano_card, mes_card = periodos_exibicao[i+j]
                            with cols[j]:
                                with st.container(border=True):
                                    
                                    # CABEÇALHO DO CARD (Limpo e centralizado)
                                    st.markdown(f"<h4 style='text-align: center; color: #1f77b4; margin-bottom: 5px;'>📅 {mes_card} {ano_card}</h4>", unsafe_allow_html=True)
                                    
                                    # SALDO ANTERIOR
                                    saldo_anterior = calcular_saldo_anterior(mes_card, ano_card, st.session_state.df)
                                    st.markdown(f"<div style='text-align: center; color: gray; font-size: 0.95em; margin-bottom: 5px;'>Saldo Anterior Caixa: <b>{formata_moeda(saldo_anterior)}</b></div>", unsafe_allow_html=True)
                                    st.markdown("<hr/>", unsafe_allow_html=True)
                                    
                                    # BUSCA TODOS OS ITENS ATIVOS DO MÊS
                                    mask_planilha = st.session_state.df.apply(lambda r: lancamento_ativo(r, mes_card, ano_card), axis=1)
                                    ativos = st.session_state.df[mask_planilha]
                                    
                                    # SEPARA O "SALDO ATUAL" PARA RENDERIZAR SÓ NO FINAL
                                    mask_saldo = ativos['Descrição'] == 'Saldo Atual'
                                    ativos_normais = ativos[~mask_saldo].copy()
                                    saldo_row = ativos[mask_saldo]
                                    valor_saldo = saldo_row['Valor'].iloc[0] if not saldo_row.empty else 0.0
                                    
                                    t_despesas_mes = 0.0
                                    t_receitas_mes = 0.0
                                    
                                    if ativos_normais.empty:
                                        st.markdown("<div style='text-align: center; font-size: 0.95em; color: gray; margin-bottom: 10px;'>Nenhum item pendente.</div>", unsafe_allow_html=True)
                                    else:
                                        # ORDENAÇÃO: Despesa vem primeiro (D < R), depois o Maior valor pro Menor
                                        ativos_normais = ativos_normais.sort_values(by=['Tipo', 'Valor'], ascending=[True, False])
                                        
                                        # LOOP DOS ITENS NORMAIS
                                        for idx_db, row_db in ativos_normais.iterrows():
                                            mes_ano_str = f"{mes_card}/{ano_card}"
                                            str_pagos = str(row_db.get('Meses_Pagos', ''))
                                            is_pago = mes_ano_str in [p.strip() for p in str_pagos.split(',') if p.strip()]
                                            
                                            if not is_pago:
                                                if row_db['Tipo'] == "Despesa": t_despesas_mes += row_db['Valor']
                                                else: t_receitas_mes += row_db['Valor']
                                            
                                            c_chk, c_desc, c_val = st.columns([1.2, 6, 4])
                                            with c_chk:
                                                st.checkbox("P", value=is_pago, key=f"chk_{idx_db}_{mes_card}_{ano_card}", on_change=altera_pagamento, args=(idx_db, mes_ano_str), label_visibility="collapsed")
                                            
                                            estilo_riscado = "text-decoration: line-through; color: gray;" if is_pago else ""
                                            cor_valor = "#dc3545" if row_db['Tipo'] == "Despesa" else "#28a745"
                                            sinal = "-" if row_db['Tipo'] == "Despesa" else "+"
                                            
                                            with c_desc:
                                                st.markdown(f"<div style='font-size: 0.95em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-top: 5px; {estilo_riscado}'>{row_db['Descrição']}</div>", unsafe_allow_html=True)
                                            with c_val:
                                                estilo_val = estilo_riscado if is_pago else f"color: {cor_valor}; font-weight: bold;"
                                                st.markdown(f"<div style='text-align: right; font-size: 0.95em; padding-top: 5px; {estilo_val}'>{sinal} {formata_moeda(row_db['Valor'])}</div>", unsafe_allow_html=True)

                                    # ---> LINHA DO "SALDO ATUAL" NO FINAL DAS RECEITAS COM O LÁPIS <---
                                    t_receitas_mes += valor_saldo 
                                    
                                    c_edit, c_desc_saldo, c_val_saldo = st.columns([1.2, 6, 4])
                                    with c_edit:
                                        if st.button("✏️", key=f"btn_saldo_{mes_card}_{ano_card}", help="Ajustar Saldo Atual Injetado"):
                                            modal_saldo(mes_card, ano_card)
                                    with c_desc_saldo:
                                        st.markdown(f"<div style='font-size: 0.95em; color: #1f77b4; font-weight: bold; padding-top: 4px;'>Saldo Atual</div>", unsafe_allow_html=True)
                                    with c_val_saldo:
                                        st.markdown(f"<div style='text-align: right; font-size: 0.95em; color: #1f77b4; font-weight: bold; padding-top: 4px;'>+ {formata_moeda(valor_saldo)}</div>", unsafe_allow_html=True)

                                    # RODAPÉ DO CARD (TOTAIS)
                                    t_saldo_mes = t_receitas_mes - t_despesas_mes
                                    saldo_acumulado = saldo_anterior + t_saldo_mes
                                    
                                    st.markdown("<hr/>", unsafe_allow_html=True)
                                    cor_mes = "#28a745" if t_saldo_mes >= 0 else "#dc3545"
                                    st.markdown(f"<div style='display: flex; justify-content: space-between; font-size: 0.95em;'><span>Balanço Pendente:</span> <strong style='color: {cor_mes};'>{formata_moeda(t_saldo_mes)}</strong></div>", unsafe_allow_html=True)
                                    
                                    cor_acumulado = "#28a745" if saldo_acumulado >= 0 else "#dc3545"
                                    st.markdown(f"<div style='display: flex; justify-content: space-between; font-size: 1.05em; margin-top: 2px;'><span><b>CAIXA FINAL:</b></span> <strong style='color: {cor_acumulado};'>{formata_moeda(saldo_acumulado)}</strong></div>", unsafe_allow_html=True)


# ==========================================
# ABA 4: CONSULTOR IA GEMINI 
# ==========================================
with aba_ia:
    st.markdown("### 🤖 Consultor Financeiro Inteligente (Gemini)")
    st.write("Converse com a IA para analisar seus gastos, criar cenários futuros e obter conselhos baseados na sua base de dados atual.")
    
    # ---------------------------------------------------------
    # 👇 COLE A SUA CHAVE DA IA AQUI (NÃO É A CHAVE DO GOOGLE SHEETS)
    api_key = "AIzaSyCh4AEXspkoUwbedaKbMdQKunjD9FIVWwA" 
    # ---------------------------------------------------------
    
    st.divider()
    
    if api_key and api_key != "AIzaSyCh4AEXspkoUwbedaKbMdQKunjD9FIVWwA":
        try:
            client = genai.Client(api_key=api_key)
            if "chat_messages" not in st.session_state: st.session_state.chat_messages = []
                
            chat_container = st.container(height=500, border=False)
            with chat_container:
                if len(st.session_state.chat_messages) == 0:
                    st.info("👋 Olá! Sou o seu Consultor Financeiro. Como posso ajudar a analisar suas finanças hoje?")
                for message in st.session_state.chat_messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
                        
            prompt = st.chat_input("Ex: Simule um cenário para o próximo ano com um corte de 10% nos gastos gerais...")
            
            if prompt:
                st.session_state.chat_messages.append({"role": "user", "content": prompt})
                with chat_container:
                    with st.chat_message("user"): st.markdown(prompt)
                        
                    dados_csv_string = st.session_state.df.to_csv(index=False)
                    historico_conversa = ""
                    for msg in st.session_state.chat_messages[-5:-1]: 
                        papel = "Usuário" if msg["role"] == "user" else "Consultor"
                        historico_conversa += f"{papel}: {msg['content']}\n"
                    
                    contexto_ia = f"""
                    Você é um consultor financeiro pessoal especialista e analítico.
                    DADOS FINANCEIROS ATUAIS DO USUÁRIO:
                    {dados_csv_string}
                    HISTÓRICO RECENTE DA CONVERSA:
                    {historico_conversa}
                    Baseando-se estritamente nestes dados e no histórico da conversa, responda de forma clara à nova pergunta:
                    PERGUNTA DO USUÁRIO: "{prompt}"
                    """
                    
                    with st.chat_message("assistant"):
                        with st.spinner("🧠 O Gemini está analisando seus dados e calculando cenários..."):
                            try:
                                resposta = client.models.generate_content(model='gemini-2.5-flash', contents=contexto_ia)
                                st.markdown(resposta.text)
                                st.session_state.chat_messages.append({"role": "assistant", "content": resposta.text})
                            except Exception as e: st.error(f"Ocorreu um erro ao processar com a API do Gemini: {e}")
                                
        except Exception as e: st.error(f"Erro na configuração da API Key. Detalhes: {e}")
    else:
        st.warning("⚠️ Lembre-se de colar a sua chave gerada pelo Google AI Studio diretamente na variável `api_key` no código fonte.")
