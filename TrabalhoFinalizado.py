import streamlit as st
import pandas as pd
import plotly.express as px
import re
import unicodedata

# ---------------- CONFIGURAÇÃO INICIAL ----------------
st.set_page_config(page_title="Busca de Medicamentos", page_icon="💊", layout="wide")
st.title("💊 Sistema de Busca de Medicamentos")

# ---------------- FUNÇÃO AUXILIAR ----------------
def remover_acentos(texto: str) -> str:
    if not isinstance(texto, str):
        return texto
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')

def limpar_numero_preco(valor):
    if pd.isna(valor):
        return pd.NA
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    s = re.sub(r'[Rr]\$|\$', '', s)  # remove R$
    s = s.replace(' ', '')
    s = re.sub(r'[^\d\-,\.]', '', s)

    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    else:
        if ',' in s:
            s = s.replace(',', '.')

    try:
        return float(s)
    except:
        return pd.NA

# ---------------- FUNÇÃO PARA CARREGAR E AJUSTAR OS DADOS ----------------
@st.cache_data
def carregar_dados():
    try:
        df_raw = pd.read_excel("LISTA DE MEDICAMENTOS11.xlsx", header=None)

        linha_cabecalho = None
        for i, row in df_raw.iterrows():
            combined = ' '.join(row.astype(str).fillna('').tolist())
            combined_norm = remover_acentos(combined).lower()
            if "remedio" in combined_norm:
                linha_cabecalho = i
                break

        if linha_cabecalho is None:
            st.error("❌ Nenhuma linha com 'Remédio' encontrada.")
            return pd.DataFrame(), {}

        df = pd.read_excel("LISTA DE MEDICAMENTOS11.xlsx", header=linha_cabecalho)
        df.columns = [str(c).strip() for c in df.columns]
        df.dropna(how="all", inplace=True)

        colunas_originais = df.columns.tolist()
        colunas_norm = [remover_acentos(str(c)).lower() for c in colunas_originais]
        mapping = dict(zip(colunas_originais, colunas_norm))

        return df, mapping

    except Exception as e:
        st.error(f"Erro ao carregar arquivo: {e}")
        return pd.DataFrame(), {}

# ---------------- CARREGAR OS DADOS ----------------
df, col_map = carregar_dados()

if df.empty:
    st.stop()

st.success("✅ Dados carregados com sucesso!")
st.dataframe(df.head(), use_container_width=True)

# ---------------- FILTROS ----------------
st.sidebar.header("🔍 Filtros de busca")

categorias_escolhidas = st.sidebar.multiselect(
    "Escolha colunas para filtrar:",
    df.columns
)

filtros = {}
for categoria in categorias_escolhidas:
    valor = st.sidebar.text_input(f"Buscar por '{categoria}':")
    if valor:
        filtros[categoria] = valor

colunas_numericas = df.select_dtypes(include="number").columns.tolist()
coluna_ordem = st.sidebar.selectbox("Ordenar por:", ["Nenhum"] + colunas_numericas)
ordem_crescente = st.sidebar.radio("Ordem:", ["Crescente", "Decrescente"]) == "Crescente"

df_filtrado = df.copy()

for coluna, valor in filtros.items():
    df_filtrado = df_filtrado[df_filtrado[coluna].astype(str).str.contains(valor, case=False, na=False)]

if coluna_ordem != "Nenhum":
    df_filtrado = df_filtrado.sort_values(by=coluna_ordem, ascending=ordem_crescente)

st.write(f"### Resultados ({len(df_filtrado)} encontrados)")
st.dataframe(df_filtrado, use_container_width=True)

# ---------------- DETECTA COLUNAS DE LAB E PREÇO ----------------
coluna_lab = None
coluna_preco = None

for orig_col, norm_col in col_map.items():
    if any(k in norm_col for k in ["lab", "laboratorio", "fabricante"]):
        coluna_lab = orig_col
    if any(k in norm_col for k in ["preco", "preço", "valor", "price"]):
        coluna_preco = orig_col

if coluna_preco:
    df_filtrado["_PRECO_NUM"] = df_filtrado[coluna_preco].apply(limpar_numero_preco)
    df_filtrado["_PRECO_NUM"] = pd.to_numeric(df_filtrado["_PRECO_NUM"], errors="coerce")

# ---------------- GRÁFICOS (SÓ APARECEM SE O USUÁRIO SELECIONAR LABORATÓRIOS) ----------------
if coluna_lab and coluna_preco and not df_filtrado.empty:

    st.sidebar.subheader("📊 Comparar Laboratórios")
    laboratorios_unicos = sorted(df_filtrado[coluna_lab].dropna().unique().tolist())

    labs_selecionados = st.sidebar.multiselect(
        "Selecione os laboratórios:",
        laboratorios_unicos
    )

    if labs_selecionados:
        df_comp = df_filtrado[df_filtrado[coluna_lab].isin(labs_selecionados)].copy()

        df_comp["_PRECO_NUM"] = pd.to_numeric(
            df_comp["_PRECO_NUM"],
            errors="coerce"
        )

        # --- GRÁFICO 1: MÉDIA DE PREÇOS ---
        st.subheader("📊 Média de Preços - Laboratórios Selecionados")

        agrup = (
            df_comp.dropna(subset=[coluna_lab, "_PRECO_NUM"])
            .groupby(coluna_lab, as_index=False)["_PRECO_NUM"]
            .mean()
            .rename(columns={"_PRECO_NUM": "Preco_Medio"})
        )

        if not agrup.empty:
            fig = px.bar(
                agrup,
                x=coluna_lab,
                y="Preco_Medio",
                title="Média de Preços por Laboratório",
                labels={coluna_lab: "Laboratório", "Preco_Medio": "Preço Médio (R$)"},
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados suficientes para calcular média.")

        # --- GRÁFICO 2: QUANTIDADE ---
        st.subheader("📈 Quantidade de Produtos - Laboratórios Selecionados")

        contagem = (
            df_comp[coluna_lab]
            .value_counts()
            .reset_index()
        )
        contagem.columns = ["Laboratorio", "Quantidade"]

        fig2 = px.bar(
            contagem,
            x="Laboratorio",
            y="Quantidade",
            title="Quantidade de Produtos por Laboratório",
            height=400
        )
        st.plotly_chart(fig2, use_container_width=True)

    else:
        st.info("Selecione ao menos um laboratório na barra lateral para exibir os gráficos.")

# ---------------- DOWNLOAD ----------------
if not df_filtrado.empty:
    if "_PRECO_NUM" in df_filtrado.columns:
        df_export = df_filtrado.drop(columns=["_PRECO_NUM"])
    else:
        df_export = df_filtrado

    csv = df_export.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Baixar CSV",
        data=csv,
        file_name="resultado_medicamentos.csv",
        mime="text/csv"
    )
