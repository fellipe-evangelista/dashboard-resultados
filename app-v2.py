import streamlit as st
import pandas as pd
import plotly.express as px

# --- Configuração da Página ---
st.set_page_config(page_title="Dashboard de Performance", layout="wide", page_icon="🎯")

SHEET_ID = "1ggF1WwNrdXBcWX6tPHyQ72zrB-0ItyjBImw3h2xVC5U"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"


# --- Funções utilitárias ---
def converter_tempo(val):
    try:
        if pd.isna(val) or val == "-" or str(val).strip() == "":
            return 0
        if hasattr(val, "hour"):
            return val.hour * 3600 + val.minute * 60 + val.second
        partes = str(val).split(":")
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
    try:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            v = val.replace("%", "").replace(",", ".").strip()
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


# --- Mapeamentos de filas (por aba) ---
FILAS_CHAT = {
    "Suporte": [
        ("Suporte", "qtde_chat_suporte", "tme_chat_suporte"),
        ("Incidentes", "qtde_chat_incidentes", "tme_chat_incidentes"),
        ("Visitas", "qtde_chat_visitas", "tme_chat_visitas"),
        ("Migração BR", "qtde_chat_migracao_br", "tme_chat_migracao_br"),
    ],
    "SAC": [
        ("Relacionamento", "qtde_chat_relacionamento", "tme_chat_relacionamento"),
        ("Bloqueios", "qtde_chat_bloqueios", "tme_chat_bloqueios"),
        ("Visitas", "qtde_chat_visitas", "tme_chat_visitas"),
        ("Migração BR", "qtde_chat_migracao_br", "tme_chat_migracao_br"),
    ],
}

COLS_PBX = [
    ("PBX Recebidas", "qtde_pbx_r"),
    ("PBX Efetuadas", "qtde_pbx_e"),
]


@st.cache_data(ttl=60)
def load_data():
    try:
        xls = pd.read_excel(URL, sheet_name=None)

        def processar_aba(df, nome_aba):
            df = df.dropna(how="all", axis=1).dropna(how="all", axis=0)
            df.columns = [str(c).lower().strip() for c in df.columns]

            data = pd.DataFrame()

            # Identificação
            nome, equipe, horario = get_id_cols(df)
            data["Nome"] = nome.astype(str)
            data["Equipe"] = equipe.astype(str)
            data["Horario"] = horario.astype(str)

            # Totais (base das metas)
            data["Chat"] = to_num(df["qtde_chat_total"]) if col_exists(df, "qtde_chat_total") else 0
            data["Total (PBX)"] = to_num(df["total_pbx"]) if col_exists(df, "total_pbx") else 0

            # Notas / % (chat) e nota PBX (mantido)
            data["Chat (nota)"] = to_num(df["nota_chat"]) if col_exists(df, "nota_chat") else 0
            data["Chat (nota)"] = data["Chat (nota)"].apply(lambda x: x / 10 if x > 5 else x)
            data["Nota (%)"] = df["%_nota_chat"].apply(limpar_porcentagem) if col_exists(df, "%_nota_chat") else 0.0

            data["PBX (nota)"] = to_num(df["nota_pbx"]) if col_exists(df, "nota_pbx") else 0
            data["PBX (nota)"] = data["PBX (nota)"].apply(lambda x: x / 10 if x > 5 else x)

            # TMEs totais (base das metas)
            data["Chat (TME) [s]"] = df["tme_chat"].apply(converter_tempo) if col_exists(df, "tme_chat") else 0
            data["PBX (TME) [s]"] = df["tme_pbx"].apply(converter_tempo) if col_exists(df, "tme_pbx") else 0

            # --- Nota / % PBX (para exibição no detalhamento) ---
            data["PBX (nota)"] = to_num(df["nota_pbx"]) if col_exists(df, "nota_pbx") else 0
            data["PBX (nota)"] = data["PBX (nota)"].apply(lambda x: x / 10 if x > 5 else x)

            data["PBX Nota (%)"] = df["%_nota_pbx"].apply(limpar_porcentagem) if col_exists(df, "%_nota_pbx") else 0.0

            # Detalhamento por fila (somente exibição)
            for label, col_qtd, col_tme in FILAS_CHAT.get(nome_aba, []):
                data[f"Chat - {label}"] = to_num(df[col_qtd]) if col_exists(df, col_qtd) else 0
                data[f"TME - {label} [s]"] = df[col_tme].apply(converter_tempo) if col_exists(df, col_tme) else 0

            for label, col_qtd in COLS_PBX:
                data[label] = to_num(df[col_qtd]) if col_exists(df, col_qtd) else 0

            return data

        if "Suporte" not in xls or "SAC" not in xls:
            raise Exception("As abas 'Suporte' e/ou 'SAC' não foram encontradas na planilha.")

        return processar_aba(xls["Suporte"], "Suporte"), processar_aba(xls["SAC"], "SAC")

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None, None


def render_tab(df, titulo, meta_nota, meta_tme_chat_seg, meta_tme_pbx_seg, meta_perc):
    # 1. Filtros
    c1, c2 = st.columns(2)
    equipes = sorted(list(df["Equipe"].dropna().unique()))
    sel_equipe = c1.multiselect(f"Equipe ({titulo})", equipes, default=equipes, key=f"eq_{titulo}")

    horarios = sorted(list(df["Horario"].astype(str).dropna().unique()))
    sel_horario = c2.multiselect(f"Horário ({titulo})", horarios, default=horarios, key=f"hr_{titulo}")

    dff = df[df["Equipe"].isin(sel_equipe) & df["Horario"].astype(str).isin(sel_horario)].copy()
    if dff.empty:
        st.warning("Sem dados para os filtros selecionados.")
        return

    # 2. Metas dinâmicas (continuam no total)
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

    # 4. Gráficos (Rankings - continuam no total)
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
        st.markdown("**🏆 Top 10 Volume (chat total)**")
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
        st.markdown("**📞 Top 10 Volume (PBX total)**")
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

    # 5. TABELA PRINCIPAL (metas)
    st.subheader(f"✅ Acompanhamento de Metas Individual - {titulo}")
    st.info(
        f"""
**Regras Ativas (baseadas nos totais):**
- Volume Chat/Tel: Acima da Média da Equipe (Média Chat: {media_vol_chat:.0f} | Média Tel: {media_vol_pbx:.0f})
- Nota Chat: >= {meta_nota}
- % Avaliação (Chat): >= {meta_perc*100:.0f}%
- TME Chat: <= {formatar_tempo(meta_tme_chat_seg)} | TME Tel: <= {formatar_tempo(meta_tme_pbx_seg)}
"""
    )

    # --- Tabela "principal" enxuta (só o necessário para metas + visão geral) ---
    base_cols = [
        "Nome", "Equipe", "Horario",
        "Chat", "Chat (nota)", "Nota (%)", "Chat (TME) [s]",
        "Total (PBX)", "PBX (TME) [s]",
    ]
    base_cols = [c for c in base_cols if c in dff.columns]
    resumo = dff[base_cols].copy()

    resumo["Chat (TME)"] = resumo["Chat (TME) [s]"].apply(formatar_tempo)
    resumo["PBX (TME)"] = resumo["PBX (TME) [s]"].apply(formatar_tempo)

    colunas_visiveis = ["Nome", "Equipe", "Horario", "Chat", "Chat (nota)", "Nota (%)", "Chat (TME)", "Total (PBX)", "PBX (TME)"]
    colunas_visiveis = [c for c in colunas_visiveis if c in resumo.columns]
    colunas_calculo = ["Chat (TME) [s]", "PBX (TME) [s]"]
    colunas_calculo = [c for c in colunas_calculo if c in resumo.columns]

    resumo = resumo[colunas_visiveis + colunas_calculo]

    def highlight_metas(row):
        styles = [""] * len(row)
        idx = {col: i for i, col in enumerate(row.index)}

        def paint(col, ok):
            if col not in idx:
                return
            styles[idx[col]] = "background-color: #d4edda; color: green" if ok else "background-color: #f8d7da; color: red"

        paint("Chat", row.get("Chat", 0) >= media_vol_chat)
        paint("Chat (nota)", row.get("Chat (nota)", 0) >= meta_nota)
        paint("Nota (%)", row.get("Nota (%)", 0) >= meta_perc)

        v_chat = row.get("Chat (TME) [s]", 0)
        if "Chat (TME)" in idx:
            if v_chat > 0 and v_chat <= meta_tme_chat_seg:
                styles[idx["Chat (TME)"]] = "background-color: #d4edda; color: green"
            elif v_chat == 0:
                styles[idx["Chat (TME)"]] = ""
            else:
                styles[idx["Chat (TME)"]] = "background-color: #f8d7da; color: red"

        paint("Total (PBX)", row.get("Total (PBX)", 0) >= media_vol_pbx)

        v_pbx = row.get("PBX (TME) [s]", 0)
        if "PBX (TME)" in idx:
            if v_pbx > 0 and v_pbx <= meta_tme_pbx_seg:
                styles[idx["PBX (TME)"]] = "background-color: #d4edda; color: green"
            elif v_pbx == 0:
                styles[idx["PBX (TME)"]] = ""
            else:
                styles[idx["PBX (TME)"]] = "background-color: #f8d7da; color: red"

        return styles

    st_df = (
        resumo.style.apply(highlight_metas, axis=1)
        .format({"Chat": "{:.0f}", "Chat (nota)": "{:.2f}", "Nota (%)": "{:.1%}", "Total (PBX)": "{:.0f}"})
    )

    st.dataframe(
        st_df,
        column_order=colunas_visiveis,
        hide_index=True,
        use_container_width=True,
        height=520,
    )

    # --- EXPANDER: detalhamento por fila (exibição) ---
    with st.expander("🔎 Ver detalhamento por fila (somente exibição)", expanded=False):
        # Define a ordem por aba
        ordem = {
            "Suporte": [
                "Chat - Suporte", "Chat - Incidentes", "Chat - Visitas", "Chat - Migração BR", "Chat - Total",
                "TME - Suporte", "TME - Incidentes", "TME - Visitas", "TME - Migração BR", "TME - Média",
                "PBX - Recebidas", "PBX - Efetuadas", "PBX - Total", "PBX - TME",
                "Chat - Nota", "Chat - % Nota", "PBX - Nota", "PBX - % Nota",
            ],
            "SAC": [
                "Chat - Relacionamento", "Chat - Bloqueios", "Chat - Visitas", "Chat - Migração BR", "Chat - Total",
                "TME - Relacionamento", "TME - Bloqueios", "TME - Visitas", "TME - Migração BR", "TME - Média",
                "PBX - Recebidas", "PBX - Efetuadas", "PBX - Total", "PBX - TME",
                "Chat - Nota", "Chat - % Nota", "PBX - Nota", "PBX - % Nota",
            ],
        }

        # Mapeia colunas do seu DF -> nomes de exibição no detalhamento
        filas = FILAS_CHAT.get(titulo, [])  # lista de tuplas: (label, col_qtd, col_tme)

        # Começa com "Nome/Equipe/Horario" (se você quiser ocultar, é só remover daqui)
        det = dff[["Nome", "Equipe", "Horario"]].copy()

        # CHAT por fila (volumes)
        for label, _, _ in filas:
            src = f"Chat - {label}"           # já existe no DF
            dst = f"Chat - {label}"           # nome de exibição
            if src in dff.columns:
                det[dst] = dff[src]
            else:
                det[dst] = 0

        # CHAT total
        det["Chat - Total"] = dff["Chat"] if "Chat" in dff.columns else 0

        # TME por fila (formatado)
        for label, _, _ in filas:
            src_s = f"TME - {label} [s]"      # já existe no DF
            dst = f"TME - {label}"            # exibição
            if src_s in dff.columns:
                det[dst] = dff[src_s].apply(formatar_tempo)
            else:
                det[dst] = "-"

        # TME média (tme_chat) -> do seu DF: "Chat (TME) [s]"
        if "Chat (TME) [s]" in dff.columns:
            det["TME - Média"] = dff["Chat (TME) [s]"].apply(formatar_tempo)
        else:
            det["TME - Média"] = "-"

        # PBX volumes
        det["PBX - Recebidas"] = dff["PBX Recebidas"] if "PBX Recebidas" in dff.columns else 0
        det["PBX - Efetuadas"] = dff["PBX Efetuadas"] if "PBX Efetuadas" in dff.columns else 0
        det["PBX - Total"] = dff["Total (PBX)"] if "Total (PBX)" in dff.columns else 0

        # PBX TME
        if "PBX (TME) [s]" in dff.columns:
            det["PBX - TME"] = dff["PBX (TME) [s]"].apply(formatar_tempo)
        else:
            det["PBX - TME"] = "-"

        # Notas e percentuais
        det["Chat - Nota"] = dff["Chat (nota)"] if "Chat (nota)" in dff.columns else 0
        det["Chat - % Nota"] = dff["Nota (%)"] if "Nota (%)" in dff.columns else 0.0
        det["PBX - Nota"] = dff["PBX (nota)"] if "PBX (nota)" in dff.columns else 0
        det["PBX - % Nota"] = dff["PBX Nota (%)"] if "PBX Nota (%)" in dff.columns else 0.0

        # Ordena colunas exatamente como solicitado (mantendo Nome/Equipe/Horario no começo)
        ordem_cols = ordem.get(titulo, [])
        colunas_visiveis = ["Nome", "Equipe", "Horario"] + ordem_cols

        # Garante que só vai exibir o que existe
        colunas_visiveis = [c for c in colunas_visiveis if c in det.columns]
        det = det[colunas_visiveis]

        # Formatação
        fmt = {}
        for c in det.columns:
            if c.startswith("Chat - ") and c not in ["Chat - % Nota", "Chat - Nota"]:
                fmt[c] = "{:.0f}"
            if c.startswith("PBX - ") and c not in ["PBX - TME", "PBX - % Nota", "PBX - Nota"]:
                fmt[c] = "{:.0f}"

        fmt.update({
            "Chat - Nota": "{:.2f}",
            "Chat - % Nota": "{:.1%}",
            "PBX - Nota": "{:.2f}",
            "PBX - % Nota": "{:.1%}",
        })

        st.dataframe(
            det.style.format(fmt),
            hide_index=True,
            use_container_width=True,
            height=420,
        )


# --- Execução ---
st.title("📊 Painel de Metas e Performance - Fevereiro/2026")

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