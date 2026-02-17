import streamlit as st
import pandas as pd
import plotly.express as px

# --- Configuração da Página ---
st.set_page_config(page_title="Dashboard de Performance", layout="wide", page_icon="🎯")

# NOVO ID da Planilha e URL de Exportação
SHEET_ID = "1ggF1WwNrdXBcWX6tPHyQ72zrB-0ItyjBImw3h2xVC5U"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

# --- Funções de Conversão ---
def converter_tempo(val):
    """Converte HH:MM:SS (ou time) para segundos inteiros."""
    try:
        if pd.isna(val) or val == "-" or str(val).strip() == "":
            return 0
        if hasattr(val, 'hour'):
            return val.hour * 3600 + val.minute * 60 + val.second
        partes = str(val).split(':')
        if len(partes) == 3:
            return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
        return 0
    except:
        return 0

def formatar_tempo(segundos):
    if segundos == 0:
        return "-"
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def limpar_porcentagem(val):
    """Converte '50%' ou '0,5' ou 0.5 -> float 0-1."""
    try:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            v = val.replace('%', '').replace(',', '.').strip()
            if v == "":
                return 0.0
            f = float(v)
            return f / 100 if f > 1 else f
        return 0.0
    except:
        return 0.0

def to_num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)

def col_exists(df, name):
    return name in df.columns

def get_id_cols(df):
    """
    Ajuste aqui se suas colunas de identificação mudaram.
    Tenta por nome (preferível), senão cai nos índices antigos:
    Nome: 0, Equipe: 3, Horario: 4
    """
    # normaliza
    cols = list(df.columns)

    def pick_by_candidates(cands, fallback_idx, default_val):
        for c in cands:
            if c in cols:
                return df[c]
        if len(cols) > fallback_idx:
            return df.iloc[:, fallback_idx]
        return pd.Series([default_val] * len(df))

    nome = pick_by_candidates(["nome", "colaborador", "atendente"], 0, "N/A")
    equipe = pick_by_candidates(["equipe", "time", "squad"], 3, "Geral")
    horario = pick_by_candidates(["horario", "turno", "escala"], 4, "-")
    return nome, equipe, horario

@st.cache_data(ttl=60)
def load_data():
    try:
        xls = pd.read_excel(URL, sheet_name=None)

        def processar_aba(df, nome_aba):
            # Limpeza básica
            df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)
            df.columns = [str(c).lower().strip() for c in df.columns]

            data = pd.DataFrame()

            # Identificação
            nome, equipe, horario = get_id_cols(df)
            data["Nome"] = nome.astype(str)
            data["Equipe"] = equipe.astype(str)
            data["Horario"] = horario.astype(str)

            # --- CHAT (novas colunas padronizadas) ---
            # Mantemos "Chat" como o total (qtde_chat_total)
            if col_exists(df, "qtde_chat_total"):
                data["Chat"] = to_num(df["qtde_chat_total"])
            else:
                # fallback: soma de filas se existir
                chat_cols = [c for c in df.columns if c.startswith("qtde_chat_") and c != "qtde_chat_total"]
                data["Chat"] = to_num(df[chat_cols].sum(axis=1)) if chat_cols else 0

            # Nota e % nota do chat
            data["Chat (nota)"] = to_num(df["nota_chat"]) if col_exists(df, "nota_chat") else 0
            # Normaliza (se vier 0-10, converte para 0-5)
            data["Chat (nota)"] = data["Chat (nota)"].apply(lambda x: x / 10 if x > 5 else x)

            if col_exists(df, "%_nota_chat"):
                data["Nota (%)"] = df["%_nota_chat"].apply(limpar_porcentagem)
            else:
                data["Nota (%)"] = 0.0

            # TME chat (em segundos)
            if col_exists(df, "tme_chat"):
                data["Chat (TME) [s]"] = df["tme_chat"].apply(converter_tempo)
            else:
                # fallback: média dos tme_chat_* se existir
                tme_cols = [c for c in df.columns if c.startswith("tme_chat_") and c != "tme_chat"]
                if tme_cols:
                    tmp = df[tme_cols].applymap(converter_tempo)
                    data["Chat (TME) [s]"] = tmp.mean(axis=1)
                else:
                    data["Chat (TME) [s]"] = 0

            # --- PBX / Telefone (novas colunas padronizadas) ---
            data["Total (PBX)"] = to_num(df["total_pbx"]) if col_exists(df, "total_pbx") else 0

            data["PBX (nota)"] = to_num(df["nota_pbx"]) if col_exists(df, "nota_pbx") else 0
            data["PBX (nota)"] = data["PBX (nota)"].apply(lambda x: x / 10 if x > 5 else x)

            if col_exists(df, "tme_pbx"):
                data["PBX (TME) [s]"] = df["tme_pbx"].apply(converter_tempo)
            else:
                data["PBX (TME) [s]"] = 0

            # (Opcional) guardar % nota PBX para uso futuro (não exibimos por padrão)
            if col_exists(df, "%_nota_pbx"):
                data["PBX Nota (%)"] = df["%_nota_pbx"].apply(limpar_porcentagem)
            else:
                data["PBX Nota (%)"] = 0.0

            # (Opcional) manter as filas detalhadas para evoluções futuras do dashboard
            # Chat por fila (se existirem)
            for c in [
                "qtde_chat_suporte", "qtde_chat_incidentes", "qtde_chat_visitas", "qtde_migracao_br",
                "qtde_chat_relacionamento", "qtde_chat_bloqueios"
            ]:
                if col_exists(df, c):
                    data[c] = to_num(df[c])

            # TME por fila (se existirem)
            for c in [
                "tme_chat_suporte", "tme_chat_incidentes", "tme_chat_visitas", "tme_chat_migracao_br",
                "tme_chat_relacionamento", "tme_chat_bloqueios"
            ]:
                if col_exists(df, c):
                    data[c + " [s]"] = df[c].apply(converter_tempo)

            # PBX recebidas/efetuadas (se existirem)
            for c in ["qtde_pbx_r", "qtde_pbx_e"]:
                if col_exists(df, c):
                    data[c] = to_num(df[c])

            return data

        if "Suporte" not in xls or "SAC" not in xls:
            raise Exception("As abas 'Suporte' e/ou 'SAC' não foram encontradas na planilha.")

        return processar_aba(xls["Suporte"], "Suporte"), processar_aba(xls["SAC"], "SAC")

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None, None

# --- Renderização ---
def render_tab(df, titulo, meta_nota, meta_tme_chat_seg, meta_tme_pbx_seg, meta_perc):

    # 1. Filtros
    c1, c2 = st.columns(2)
    equipes = sorted(list(df["Equipe"].dropna().unique()))
    sel_equipe = c1.multiselect(f"Equipe ({titulo})", equipes, default=equipes, key=f"eq_{titulo}")

    horarios = sorted(list(df["Horario"].astype(str).dropna().unique()))
    sel_horario = c2.multiselect(f"Horário ({titulo})", horarios, default=horarios, key=f"hr_{titulo}")

    # Filtragem
    dff = df[df["Equipe"].isin(sel_equipe) & df["Horario"].astype(str).isin(sel_horario)].copy()
    if dff.empty:
        st.warning("Sem dados para os filtros selecionados.")
        return

    # 2. Cálculo das Médias (Metas Dinâmicas)
    media_vol_chat = dff["Chat"].mean()
    media_vol_pbx = dff["Total (PBX)"].mean()

    # 3. KPIs
    st.markdown("### 🎯 Visão Geral")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total de Atendimentos (chat)", f"{dff['Chat'].sum():,.0f}")
    k2.metric("Nota Média (chat)", f"{dff[dff['Chat'] > 0]['Chat (nota)'].mean():.2f}")
    k3.metric("Total de Atendimentos (PBX)", f"{dff['Total (PBX)'].sum():,.0f}")
    k4.metric("Nota Média (PBX)", f"{dff[dff['Total (PBX)'] > 0]['PBX (nota)'].mean():.2f}")
    st.markdown("---")

    # 4. Gráficos (Rankings)
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**⭐ Top 10 Notas (chat)**")
        top_n = dff[dff["Chat"] > 0].nlargest(10, "Chat (nota)")
        if not top_n.empty:
            st.plotly_chart(
                px.bar(
                    top_n.sort_values("Chat (nota)"),
                    x="Chat (nota)",
                    y="Nome",
                    orientation="h",
                    text_auto=".2f",
                    color_discrete_sequence=["#2ecc71"],
                ),
                use_container_width=True,
                key=f"gnc_{titulo}",
            )

    with g2:
        st.markdown("**⭐ Top 10 Notas (PBX)**")
        top_np = dff[dff["Total (PBX)"] > 0].nlargest(10, "PBX (nota)")
        if not top_np.empty:
            st.plotly_chart(
                px.bar(
                    top_np.sort_values("PBX (nota)"),
                    x="PBX (nota)",
                    y="Nome",
                    orientation="h",
                    text_auto=".2f",
                    color_discrete_sequence=["#9b59b6"],
                ),
                use_container_width=True,
                key=f"gnp_{titulo}",
            )

    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**🏆 Top 10 Volume (chat)**")
        st.plotly_chart(
            px.bar(
                dff.nlargest(10, "Chat").sort_values("Chat"),
                x="Chat",
                y="Nome",
                orientation="h",
                text="Chat",
                color_discrete_sequence=["#3498db"],
            ),
            use_container_width=True,
            key=f"gvc_{titulo}",
        )
    with r2:
        st.markdown("**📞 Top 10 Volume (PBX)**")
        st.plotly_chart(
            px.bar(
                dff.nlargest(10, "Total (PBX)").sort_values("Total (PBX)"),
                x="Total (PBX)",
                y="Nome",
                orientation="h",
                text="Total (PBX)",
                color_discrete_sequence=["#e67e22"],
            ),
            use_container_width=True,
            key=f"gvp_{titulo}",
        )

    st.markdown("---")

    # 5. TABELA DE METAS E RESULTADOS
    st.subheader(f"✅ Acompanhamento de Metas Individual - {titulo}")

    st.info(
        f"""
**Regras Ativas:**
- Volume Chat/Tel: Acima da Média da Equipe (Média Chat: {media_vol_chat:.0f} | Média Tel: {media_vol_pbx:.0f})
- Nota Chat: >= {meta_nota}
- % Avaliação (Chat): >= {meta_perc*100:.0f}%
- TME Chat: <= {formatar_tempo(meta_tme_chat_seg)} | TME Tel: <= {formatar_tempo(meta_tme_pbx_seg)}
"""
    )

    # Preparar DF para exibição
    resumo = dff[
        ["Nome", "Equipe", "Horario", "Chat", "Chat (nota)", "Nota (%)", "Chat (TME) [s]", "Total (PBX)", "PBX (TME) [s]"]
    ].copy()

    resumo["Chat (TME)"] = resumo["Chat (TME) [s]"].apply(formatar_tempo)
    resumo["PBX (TME)"] = resumo["PBX (TME) [s]"].apply(formatar_tempo)

    colunas_visiveis = ["Nome", "Equipe", "Horario", "Chat", "Chat (nota)", "Nota (%)", "Chat (TME)", "Total (PBX)", "PBX (TME)"]
    colunas_calculo = ["Chat (TME) [s]", "PBX (TME) [s]"]
    resumo = resumo[colunas_visiveis + colunas_calculo]

    # Função de Estilo
    def highlight_metas(row):
        styles = [""] * len(row)

        # Index: 0 Nome, 1 Equipe, 2 Horario, 3 Chat, 4 Chat(nota), 5 Nota(%), 6 Chat(TME), 7 Total(PBX), 8 PBX(TME), 9 Chat(TME)[s], 10 PBX(TME)[s]

        # Meta Volume Chat (Index 3)
        if row["Chat"] >= media_vol_chat:
            styles[3] = "background-color: #d4edda; color: green"
        else:
            styles[3] = "background-color: #f8d7da; color: red"

        # Meta Nota Chat (Index 4)
        if row["Chat (nota)"] >= meta_nota:
            styles[4] = "background-color: #d4edda; color: green"
        else:
            styles[4] = "background-color: #f8d7da; color: red"

        # Meta % Avaliação Chat (Index 5)
        if row["Nota (%)"] >= meta_perc:
            styles[5] = "background-color: #d4edda; color: green"
        else:
            styles[5] = "background-color: #f8d7da; color: red"

        # Meta TME Chat (visual Index 6, lógica Index 9)
        val_tme_chat = row["Chat (TME) [s]"]
        if val_tme_chat > 0 and val_tme_chat <= meta_tme_chat_seg:
            styles[6] = "background-color: #d4edda; color: green"
        elif val_tme_chat == 0:
            styles[6] = ""
        else:
            styles[6] = "background-color: #f8d7da; color: red"

        # Meta Volume PBX (Index 7)
        if row["Total (PBX)"] >= media_vol_pbx:
            styles[7] = "background-color: #d4edda; color: green"
        else:
            styles[7] = "background-color: #f8d7da; color: red"

        # Meta TME PBX (visual Index 8, lógica Index 10)
        val_tme_pbx = row["PBX (TME) [s]"]
        if val_tme_pbx > 0 and val_tme_pbx <= meta_tme_pbx_seg:
            styles[8] = "background-color: #d4edda; color: green"
        elif val_tme_pbx == 0:
            styles[8] = ""
        else:
            styles[8] = "background-color: #f8d7da; color: red"

        return styles

    st_df = (
        resumo.style.apply(highlight_metas, axis=1)
        .format(
            {
                "Chat": "{:.0f}",
                "Chat (nota)": "{:.2f}",
                "Nota (%)": "{:.1%}",
                "Total (PBX)": "{:.0f}",
            }
        )
    )

    st.dataframe(
        st_df,
        column_order=colunas_visiveis,
        hide_index=True,
        use_container_width=True,
        height=500,
    )

# --- Execução ---
st.title("📊 Painel de Metas e Performance")

st.sidebar.title("⚙️ Configuração de Metas")
st.sidebar.markdown("Defina os alvos para colorir a tabela.")

with st.sidebar.expander("💬 Metas de Chat", expanded=True):
    meta_nota_sup = st.number_input("Nota Suporte (Min)", value=4.45, step=0.05)
    meta_nota_sac = st.number_input("Nota SAC (Min)", value=4.55, step=0.05)
    meta_perc = st.slider("% Avaliação Mínima (Chat)", 0.0, 1.0, 0.50)
    tme_chat_str = st.text_input("TME Chat Máximo (HH:MM:SS)", "00:01:00")
    meta_tme_chat = converter_tempo(tme_chat_str)

with st.sidebar.expander("📞 Metas de Telefone", expanded=True):
    tme_pbx_str = st.text_input("TME Telefone Máximo (HH:MM:SS)", "00:00:10")
    meta_tme_pbx = converter_tempo(tme_pbx_str)

st.sidebar.info("As metas de VOLUME são calculadas automaticamente com base na média da equipe filtrada.")

if st.button("🔄 Atualizar Dados"):
    st.cache_data.clear()
    st.rerun()

df_sup, df_sac = load_data()

if df_sup is not None and df_sac is not None:
    tab1, tab2 = st.tabs(["Suporte", "SAC"])
    with tab1:
        render_tab(df_sup, "Suporte", meta_nota_sup, meta_tme_chat, meta_tme_pbx, meta_perc)
    with tab2:
        render_tab(df_sac, "SAC", meta_nota_sac, meta_tme_chat, meta_tme_pbx, meta_perc)