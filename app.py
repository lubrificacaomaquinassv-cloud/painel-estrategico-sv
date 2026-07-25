import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import unicodedata

PAINEL_BUILD = "2026-07-24-apontamento-campo-v2"

st.set_page_config(
    page_title="Painel Estratégico — Mecanização SV",
    layout="wide",
    page_icon="📊",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700&display=swap');
[data-testid="stAppViewContainer"]{background:#0a1409;}
[data-testid="stSidebar"]{background:#111c10;border-right:1px solid #1e2e1c;}
[data-testid="stHeader"]{background:#0a1409;}
h1,h2,h3,p,span,label{color:#e8edd0;}
.stCaption,[data-testid="stCaptionContainer"] p{color:#8aab80!important;}
.stMarkdown p,.stMarkdown li{color:#c8d8c0;}
.stAlert p{color:#e8edd0!important;}
.sec{font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:700;
     letter-spacing:2px;text-transform:uppercase;color:#8aab80;
     border-left:4px solid #4a9e3f;padding-left:10px;margin:18px 0 10px;}
.stTabs [data-baseweb="tab-list"]{background:#111c10;border-bottom:2px solid #1e2e1c;gap:0;}
.stTabs [data-baseweb="tab"]{color:#4a6644;font-family:'Barlow Condensed',sans-serif;
     font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
     padding:10px 20px;border-bottom:3px solid transparent;}
.stTabs [aria-selected="true"]{color:#6fcf60!important;border-bottom:3px solid #4a9e3f!important;}
div[data-testid="metric-container"]{background:#111c10;border:1px solid #1e2e1c;border-radius:10px;padding:14px;}
div[data-testid="metric-container"] label{color:#8aab80!important;font-size:11px!important;}
div[data-testid="metric-container"] [data-testid="stMetricValue"]{color:#e8edd0!important;}
div[data-testid="metric-container"] [data-testid="stMetricDelta"]{color:#8aab80!important;}
div[data-testid="stSelectbox"] label,div[data-testid="stMultiSelect"] label{color:#8aab80!important;}
div[data-testid="stSelectbox"] > div,div[data-testid="stMultiSelect"] > div{
 background:#111c10!important;border:1px solid #1e2e1c!important;color:#e8edd0!important;}
.stButton button{background:#4a9e3f!important;color:#ffffff!important;border:1px solid #6fcf60!important;
 font-family:'Barlow Condensed',sans-serif;font-weight:700;letter-spacing:1px;text-transform:uppercase;border-radius:8px;}
.stButton button:hover{background:#3d8534!important;border-color:#9fe790!important;}
.stButton button p{color:#ffffff!important;font-weight:700;}
</style>
""", unsafe_allow_html=True)

PDARK = dict(
    paper_bgcolor="#111c10", plot_bgcolor="#0d180c",
    font=dict(color="#e8edd0", family="Barlow Condensed"),
    margin=dict(l=10, r=10, t=40, b=10),
)
PLOT_AXIS = dict(gridcolor="#1e2e1c", tickfont=dict(color="#e8edd0"))
CORES = ["#4a9e3f", "#2980b9", "#d4a017", "#c0392b", "#8e44ad", "#16a085", "#e67e22"]


def dark_table(df, height=300):
    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return
    rows = "".join(
        "<tr>" + "".join(
            f'<td style="padding:6px 10px;border-bottom:1px solid #1e2e1c;color:#e8edd0;font-size:12px;">{v}</td>'
            for v in row) + "</tr>"
        for _, row in df.iterrows())
    headers = "".join(
        f'<th style="padding:7px 10px;background:#111c10;color:#8aab80;font-size:10px;'
        f'font-weight:700;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #1e2e1c;">{c}</th>'
        for c in df.columns)
    st.markdown(
        f'<div style="max-height:{height}px;overflow-y:auto;overflow-x:auto;border:1px solid #1e2e1c;border-radius:10px;">'
        f'<table style="width:100%;border-collapse:collapse;background:#0d180c;font-family:Barlow Condensed,sans-serif;">'
        f'<thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table></div>',
        unsafe_allow_html=True)


def fmt(n, dec=0):
    if pd.isna(n):
        return "—"
    return f"{n:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmtR(n):
    if pd.isna(n):
        return "—"
    return f"R$ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sem_acento(s):
    def _norm(x):
        x = "" if x is None else str(x)
        x = unicodedata.normalize("NFKD", x)
        x = x.encode("ascii", "ignore").decode("ascii")
        return x.strip().upper()
    return s.map(_norm)


def norm_frota_id(s):
    return s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def parse_dt(series):
    raw = series.astype(str).str.strip()
    has_tz = raw.str.contains(r"[+-]\d{2}:\d{2}|Z$", regex=True, na=False)
    dt = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if has_tz.any():
        dt.loc[has_tz] = (
            pd.to_datetime(raw[has_tz], errors="coerce", utc=True)
            .dt.tz_convert("America/Sao_Paulo")
            .dt.tz_localize(None)
        )
    if (~has_tz).any():
        dt.loc[~has_tz] = pd.to_datetime(raw[~has_tz], errors="coerce")
    return dt


def parse_mes_key(series):
    if series is None or len(series) == 0:
        return pd.Series(dtype=str)
    raw = series.astype(str).str.strip()
    ym = raw.str.extract(r"(\d{4})[-/](\d{1,2})", expand=True)
    out = pd.Series(index=series.index, dtype="object")
    ok = ym[0].notna() & ym[1].notna()
    out.loc[ok] = ym.loc[ok, 0] + "-" + ym.loc[ok, 1].str.zfill(2)
    miss = ~ok
    if miss.any():
        dt = parse_dt(series[miss])
        out.loc[miss] = dt.dt.strftime("%Y-%m")
    return out


def fmt_mes_label(mes_key):
    try:
        return pd.Period(str(mes_key), freq="M").strftime("%b/%Y")
    except Exception:
        return str(mes_key)


def meses_disponiveis(series, mes_atual_str, n=12):
    meses = sorted(
        {str(m) for m in series.dropna().unique() if str(m) not in ("", "NaT", "None")},
        reverse=True,
    )
    mes_atual = pd.Period(mes_atual_str, freq="M")
    for m in [str(mes_atual), str(mes_atual - 1)]:
        if m not in meses:
            meses.insert(0, m)
    return sorted(set(meses), reverse=True)[:n]


def label_trator(row):
    frota = row.get("id_frota") or row.get("frota") or "—"
    modelo = row.get("modelo")
    if pd.notna(modelo) and str(modelo).strip():
        return f"{modelo} · {frota}"
    return str(frota)


import psycopg2

DB_HOST = st.secrets["db"]["host"]


def get_conn():
    return psycopg2.connect(
        host=st.secrets["db"]["host"],
        port=st.secrets["db"]["port"],
        dbname=st.secrets["db"]["dbname"],
        user=st.secrets["db"]["user"],
        password=st.secrets["db"]["password"],
        sslmode="require",
    )


def sb(table, order_col=None, desc=True):
    conn = get_conn()
    try:
        q = f"SELECT * FROM {table}"
        if order_col:
            direction = "DESC" if desc else "ASC"
            q += f' ORDER BY "{order_col}" {direction}'
        return pd.read_sql_query(q, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


def calc_disp_from_apontamento(df_apont, df_os, df_painel=None):
    """Fallback: horas operando de apontamento_campo + parada de ordem_servico."""
    if df_apont is None or df_apont.empty:
        return pd.DataFrame()
    ap = df_apont.copy()
    ap["mes_key"] = pd.to_datetime(ap["data"], errors="coerce").dt.strftime("%Y-%m")
    ap["id_frota"] = norm_frota_id(ap["frota"])
    ap["horas_trabalhadas"] = pd.to_numeric(ap["horas_trabalhadas"], errors="coerce").fillna(0)
    g_ap = (
        ap[ap["horas_trabalhadas"] > 0]
        .groupby(["mes_key", "id_frota"], as_index=False)
        .agg(
            dias_com_apontamento=("data", "nunique"),
            horas_trabalhadas=("horas_trabalhadas", "sum"),
        )
    )
    g_os = pd.DataFrame(columns=["mes_key", "id_frota", "horas_parada", "total_os"])
    if df_os is not None and not df_os.empty:
        os = df_os.copy()
        if "mes_key" not in os.columns:
            os["mes_key"] = parse_mes_key(parse_dt(os["created_at"]))
        os["id_frota"] = norm_frota_id(os["id_frota"])
        os["tempo_min"] = pd.to_numeric(os["tempo_min"], errors="coerce").fillna(0)
        g_os = (
            os[os["tempo_min"] > 0]
            .groupby(["mes_key", "id_frota"], as_index=False)
            .agg(
                horas_parada=("tempo_min", lambda x: x.sum() / 60.0),
                total_os=("numero_os", "count"),
            )
        )
    out = g_ap.merge(g_os, on=["mes_key", "id_frota"], how="left")
    out["horas_parada"] = pd.to_numeric(out["horas_parada"], errors="coerce").fillna(0)
    out["total_os"] = pd.to_numeric(out["total_os"], errors="coerce").fillna(0)
    denom = out["horas_trabalhadas"] + out["horas_parada"]
    out["disponibilidade_pct"] = (out["horas_trabalhadas"] / denom.replace(0, pd.NA) * 100).fillna(0)
    if df_painel is not None and not df_painel.empty:
        pm = df_painel.set_index("id_frota")
        out["modelo"] = out["id_frota"].map(lambda f: pm.loc[f, "modelo"] if f in pm.index else "")
        out["categoria_painel"] = out["id_frota"].map(
            lambda f: pm.loc[f, "categoria_painel"] if f in pm.index else "OUTRO"
        )
    else:
        out["modelo"] = ""
        out["categoria_painel"] = "OUTRO"
    return out


@st.cache_data(ttl=120, show_spinner=False)
def load_resumo_mes(_c):
    df = sb("vw_painel_estrategico_resumo_mes", order_col="mes_key", desc=True)
    if df.empty:
        return df
    df = df.copy()
    for col in df.columns:
        if col != "mes_key":
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=120, show_spinner=False)
def load_disp_mes(_c):
    df = sb("vw_painel_estrategico_disp_mes", order_col="mes_key", desc=True)
    if df.empty:
        df_ap = load_apont(_c)
        df_os_raw = sb("ordem_servico", order_col="created_at", desc=True)
        df_p = load_frota_painel(_c)
        df = calc_disp_from_apontamento(df_ap, df_os_raw, df_p)
    if df.empty:
        return df
    df = df.copy()
    if "mes_key" not in df.columns:
        col_mes = next((c for c in ("mes", "mes_referencia") if c in df.columns), None)
        if col_mes:
            df["mes_key"] = parse_mes_key(df[col_mes])
    for col in ["horas_trabalhadas", "horas_parada", "disponibilidade_pct", "total_os", "dias_com_apontamento"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=120, show_spinner=False)
def load_os(_c):
    df = sb("vw_painel_estrategico_os", order_col="created_at", desc=True)
    if df.empty:
        df = sb("vw_painel_os", order_col="created_at", desc=True)
    if df.empty:
        df = sb("ordem_servico", order_col="created_at", desc=True)
    if df.empty:
        return df
    df = df.copy()
    if "created_at" in df.columns:
        df["dt"] = parse_dt(df["created_at"])
        df["data_os"] = df["dt"].dt.date
        df["mes_key"] = parse_mes_key(df["dt"])
    elif "mes_key" in df.columns:
        df["mes_key"] = parse_mes_key(df["mes_key"])
    df["tempo_min"] = pd.to_numeric(df.get("tempo_min", 0), errors="coerce").fillna(0)
    if "horas_parada_os" not in df.columns:
        df["horas_parada_os"] = df["tempo_min"] / 60.0
    return df


@st.cache_data(ttl=120, show_spinner=False)
def load_pecas(_c):
    df = sb("vw_painel_estrategico_pecas", order_col="mes_key", desc=True)
    if df.empty:
        df = sb("financeiro_os", order_col="criado_em", desc=True)
        if not df.empty:
            df = df.copy()
            df["mes_key"] = parse_mes_key(parse_dt(df["criado_em"]))
            if "valor_total_pecas" in df.columns:
                df["custo_pecas"] = pd.to_numeric(df["valor_total_pecas"], errors="coerce").fillna(0)
            elif "peca_valor" in df.columns:
                df["custo_pecas"] = (
                    pd.to_numeric(df["peca_valor"], errors="coerce").fillna(0)
                    * pd.to_numeric(df.get("quantidade", 1), errors="coerce").fillna(1)
                )
            else:
                df["custo_pecas"] = 0
            df["custo_mo"] = pd.to_numeric(df.get("custo_mo", 0), errors="coerce").fillna(0)
    if df.empty:
        return df
    df = df.copy()
    for col in ["custo_pecas", "custo_mo", "custo_total_os"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=120, show_spinner=False)
def load_lancamentos(_c):
    df = sb("vw_painel_estrategico_lancamentos", order_col="mes_key", desc=True)
    if df.empty:
        df = sb("financeiro_lancamento", order_col="data", desc=True)
        if not df.empty:
            df = df.copy()
            df["data"] = pd.to_datetime(df["data"], errors="coerce")
            df["mes_key"] = df["data"].dt.strftime("%Y-%m")
            df["valor_total"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    if df.empty:
        return df
    df = df.copy()
    df["valor_total"] = pd.to_numeric(df.get("valor_total", df.get("valor", 0)), errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=120, show_spinner=False)
def load_abast(_c):
    df = sb("vw_painel_estrategico_abast_mes", order_col="mes_key", desc=True)
    if df.empty:
        df = sb("vw_painel_abastecimento", order_col="created_at", desc=True)
        if df.empty:
            df = sb("vw_abastecimento_consolidado", order_col="created_at", desc=True)
        if not df.empty:
            df = df.copy()
            df["mes_key"] = parse_mes_key(parse_dt(df["created_at"]))
            df["id_frota"] = norm_frota_id(df.get("vehicle", df.get("id_frota", "")))
            df["litros_total"] = pd.to_numeric(df["liters"], errors="coerce").fillna(0)
            df = df.groupby(["mes_key", "id_frota"], as_index=False).agg(
                litros_total=("litros_total", "sum"), eventos=("liters", "count")
            )
    if df.empty:
        return df
    df = df.copy()
    df["litros_total"] = pd.to_numeric(df["litros_total"], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_colab(_c):
    df = sb("vw_painel_estrategico_colaboradores")
    if df.empty:
        df = sb("dim_colaborador")
    if df.empty:
        return df
    df = df.copy()
    df["_nome"] = sem_acento(df["nome"])
    df["custo_hora"] = pd.to_numeric(df["custo_hora"], errors="coerce").fillna(0)
    return df[df["custo_hora"] > 0].drop_duplicates(subset=["_nome"], keep="first")


@st.cache_data(ttl=300, show_spinner=False)
def load_apont(_c):
    df = sb("apontamento_campo")
    if df.empty:
        return df
    df = df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    df["frota"] = norm_frota_id(df["frota"])
    df["operador"] = sem_acento(df["operador"])
    df["horas_trabalhadas"] = pd.to_numeric(df.get("horas_trabalhadas", 0), errors="coerce").fillna(0)
    return df.dropna(subset=["data"]).sort_values("data")


@st.cache_data(ttl=300, show_spinner=False)
def load_frota_painel(_c):
    df = sb("dim_frota_painel")
    if df.empty:
        return df
    df = df.copy()
    df["id_frota"] = norm_frota_id(df["id_frota"])
    return df


def mapa_busca_custo_hora(df_colab):
    if df_colab is None or df_colab.empty:
        return lambda _n: 0.0
    _ch = df_colab.set_index("_nome")["custo_hora"]
    _ch_fl = {}
    for _n, _v in _ch.items():
        _ts = str(_n).split()
        if len(_ts) >= 2:
            _k = (_ts[0], _ts[-1])
            _ch_fl[_k] = None if _k in _ch_fl else float(_v)

    def busca_ch(nome):
        nome = str(nome or "").strip()
        if not nome:
            return 0.0
        if nome in _ch.index:
            return float(_ch[nome])
        _ts = nome.split()
        if len(_ts) >= 2:
            _v = _ch_fl.get((_ts[0], _ts[-1]))
            if _v is not None:
                return _v
        return 0.0

    return busca_ch


def operador_apontamento(frota, data_os, df_apont):
    if df_apont is None or df_apont.empty:
        return ""
    fid = norm_frota_id(pd.Series([frota])).iloc[0]
    cand = df_apont[df_apont["frota"] == fid].sort_values("data")
    if cand.empty:
        return ""
    if pd.notna(data_os):
        ate = cand[cand["data"] <= data_os]
        return str(ate.iloc[-1]["operador"]) if not ate.empty else ""
    return str(cand.iloc[-1]["operador"])


def calc_parada_os(df_os, df_colab, df_apont):
    if df_os.empty:
        return df_os
    busca_ch = mapa_busca_custo_hora(df_colab)
    out = df_os.copy()
    out["_h"] = pd.to_numeric(out["tempo_min"], errors="coerce").fillna(0) / 60.0
    out["_mec"] = sem_acento(out["mecanico"]) if "mecanico" in out.columns else ""
    out["_c_mec"] = out["_h"] * out["_mec"].map(busca_ch)
    out["_oper"] = ""
    if "operador" in out.columns:
        out["_oper"] = sem_acento(out["operador"])
        out.loc[out["_oper"].isin(["NAN", "NONE", "<NA>", "NULL", "N/A", "-"]), "_oper"] = ""
    if "eh_implemento" in out.columns:
        out.loc[out["eh_implemento"] == True, "_oper"] = ""  # noqa: E712
    if df_apont is not None and not df_apont.empty and out["_oper"].eq("").any():
        if "data_os" not in out.columns and "created_at" in out.columns:
            out["data_os"] = parse_dt(out["created_at"]).dt.date
        for _i in out.index[out["_oper"].eq("")]:
            if out.at[_i, "eh_implemento"] if "eh_implemento" in out.columns else False:
                continue
            _op = operador_apontamento(out.at[_i, "id_frota"], out.at[_i, "data_os"], df_apont)
            if _op:
                out.at[_i, "_oper"] = _op
    out["_c_op"] = out["_h"] * out["_oper"].map(busca_ch)
    out["_c_tot"] = out["_c_mec"] + out["_c_op"]
    return out


def gauge_disponibilidade(valor, titulo, nf, ht, hp):
    cor = "#c0392b" if valor < 70 else "#d4a017" if valor < 85 else "#4a9e3f"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=round(valor, 1),
        number={"suffix": "%", "font": {"color": "#e8edd0", "size": 36}},
        title={
            "text": (
                f"<span style='color:#e8edd0'>{titulo}</span><br>"
                f"<span style='color:#8aab80;font-size:12px'>"
                f"{nf} equipamentos · {fmt(ht)}h operando · {fmt(hp)}h paradas</span>"
            ),
            "font": {"color": "#e8edd0", "size": 14},
        },
        gauge={
            "axis": {"range": [0, 100], "ticksuffix": "%", "tickcolor": "#4a6644"},
            "bar": {"color": cor, "thickness": 0.3},
            "bgcolor": "#0d180c", "bordercolor": "#1e2e1c",
            "steps": [
                {"range": [0, 70], "color": "#2a1010"},
                {"range": [70, 85], "color": "#2a2200"},
                {"range": [85, 100], "color": "#1a3318"},
            ],
            "threshold": {"line": {"color": "#d4a017", "width": 2}, "thickness": 0.8, "value": 85},
        },
    ))
    fig.update_layout(
        paper_bgcolor="#111c10", plot_bgcolor="#111c10",
        font=dict(color="#e8edd0", family="Barlow Condensed"),
        height=280, margin=dict(l=30, r=30, t=80, b=10),
    )
    return fig


# ── HEADER ────────────────────────────────────────────────────
h1, h2, h3 = st.columns([1, 8, 2])
with h1:
    st.image(
        "https://raw.githubusercontent.com/lubrificacaomaquinassv-cloud/painel-frota-sv/main/icons/logo_sv.png",
        width=92,
    )
with h2:
    st.markdown(
        '<div style="font-family:Barlow Condensed,sans-serif;">'
        '<div style="font-size:22px;font-weight:700;color:#e8edd0;letter-spacing:1px;">'
        'PAINEL ESTRATÉGICO — MECANIZAÇÃO</div>'
        '<div style="font-size:11px;color:#8aab80;letter-spacing:2px;margin-top:2px;">'
        'Horas · Paradas · Custos · Peças · Abastecimento · Santa Vergínia</div></div>',
        unsafe_allow_html=True,
    )
with h3:
    if st.button("🔄 Atualizar", key="refresh"):
        st.cache_data.clear()
        st.rerun()
    agora_br = datetime.utcnow() - timedelta(hours=3)
    st.caption(agora_br.strftime("%d/%m/%Y %H:%M") + " (Brasília)")
    st.caption(f"Build {PAINEL_BUILD}")

st.divider()

hoje = (datetime.utcnow() - timedelta(hours=3)).date()
mes_atual_str = pd.Period(hoje, freq="M").strftime("%Y-%m")

df_resumo = load_resumo_mes(DB_HOST)
df_disp = load_disp_mes(DB_HOST)
df_os = load_os(DB_HOST)
df_pecas = load_pecas(DB_HOST)
df_lanc = load_lancamentos(DB_HOST)
df_abast = load_abast(DB_HOST)
df_colab = load_colab(DB_HOST)
df_apont = load_apont(DB_HOST)
df_painel = load_frota_painel(DB_HOST)

# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filtros")
    meses_opts = meses_disponiveis(
        df_resumo["mes_key"] if not df_resumo.empty else pd.Series([mes_atual_str]),
        mes_atual_str,
        n=12,
    )
    if not meses_opts:
        meses_opts = [mes_atual_str]
    mes_sel = st.selectbox(
        "Mês de referência",
        options=meses_opts,
        index=0,
        format_func=fmt_mes_label,
        key="mes_sel",
    )
    n_meses_trend = st.slider("Meses no gráfico de tendência", 3, 12, 6, key="n_trend")
    categorias = sorted(
        {str(c) for c in df_disp["categoria_painel"].dropna().unique()}
        if not df_disp.empty and "categoria_painel" in df_disp.columns
        else ["EQUIPAMENTO", "MAQUINA"]
    )
    cat_sel = st.multiselect(
        "Categorias de frota",
        options=categorias,
        default=[c for c in categorias if c in ("EQUIPAMENTO", "MAQUINA", "OUTRO")][:3] or categorias[:2],
        key="cat_sel",
    )
    st.caption("Horas operando: apontamento_campo · Parada: ordem_servico")

# Filtrar por categoria
def filtrar_cat(df, col="categoria_painel"):
    if df.empty or col not in df.columns or not cat_sel:
        return df
    return df[df[col].astype(str).isin(cat_sel)]

df_disp_m = filtrar_cat(df_disp[df_disp["mes_key"] == mes_sel]) if not df_disp.empty else pd.DataFrame()
df_os_m = df_os[df_os["mes_key"] == mes_sel].copy() if not df_os.empty else pd.DataFrame()
df_os_m = filtrar_cat(df_os_m)
df_pecas_m = filtrar_cat(df_pecas[df_pecas["mes_key"] == mes_sel]) if not df_pecas.empty else pd.DataFrame()
df_lanc_m = filtrar_cat(df_lanc[df_lanc["mes_key"] == mes_sel]) if not df_lanc.empty else pd.DataFrame()
df_abast_m = filtrar_cat(df_abast[df_abast["mes_key"] == mes_sel]) if not df_abast.empty else pd.DataFrame()

# Calcular custos de parada do mês
df_parada = calc_parada_os(df_os_m, df_colab, df_apont) if not df_os_m.empty else pd.DataFrame()

# KPIs do mês
disp_media = df_disp_m["disponibilidade_pct"].mean() if not df_disp_m.empty else 0
ht = df_disp_m["horas_trabalhadas"].sum() if not df_disp_m.empty else 0
hp = df_disp_m["horas_parada"].sum() if not df_disp_m.empty else 0
custo_pecas = df_pecas_m["custo_pecas"].sum() if not df_pecas_m.empty else 0
custo_mo = df_pecas_m["custo_mo"].sum() if not df_pecas_m.empty else 0
custo_lanc = df_lanc_m["valor_total"].sum() if not df_lanc_m.empty else 0
custo_parada_mec = df_parada["_c_mec"].sum() if not df_parada.empty else 0
custo_parada_op = df_parada["_c_op"].sum() if not df_parada.empty else 0
custo_parada_tot = df_parada["_c_tot"].sum() if not df_parada.empty else 0
litros = df_abast_m["litros_total"].sum() if not df_abast_m.empty else 0

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 Visão Executiva",
    "⚙️ Horas & Disponibilidade",
    "💸 Custos & Peças",
    "👷 Por Pessoa",
    "⛽ Abastecimento × Produtividade",
])

# ══════════════════════════════════════════════════════════════
# TAB 1 — VISÃO EXECUTIVA
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown(f'<div class="sec">Indicadores estratégicos · {fmt_mes_label(mes_sel)}</div>', unsafe_allow_html=True)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("📊 Disponibilidade", f"{disp_media:.1f}%")
    k2.metric("⚙️ H. Operando", f"{fmt(ht)}h")
    k3.metric("🔴 H. Paradas", f"{fmt(hp)}h")
    k4.metric("🔧 OS no Mês", len(df_os_m))
    k5.metric("💸 Custo Parada", fmtR(custo_parada_tot))
    k6.metric("🔩 Peças (OS)", fmtR(custo_pecas))

    ce1, ce2 = st.columns([1, 1.2])

    with ce1:
        if disp_media > 0 or not df_disp_m.empty:
            st.plotly_chart(
                gauge_disponibilidade(
                    disp_media,
                    f"Disponibilidade · {fmt_mes_label(mes_sel)}",
                    df_disp_m["id_frota"].nunique() if not df_disp_m.empty else 0,
                    ht, hp,
                ),
                use_container_width=True, key="k_gauge_exec",
            )
        else:
            st.info("Sem dados de disponibilidade para este mês.")

    with ce2:
        st.markdown('<div class="sec">Composição de custos · Waterfall</div>', unsafe_allow_html=True)
        wf_vals = [
            custo_pecas, custo_mo, custo_parada_mec, custo_parada_op, custo_lanc,
        ]
        wf_labels = ["Peças OS", "MO OS", "Parada Mec.", "Parada Oper.", "NF-e Lanç."]
        wf_measures = ["relative"] * 5 + ["total"]
        wf_x = wf_labels + ["Total"]
        wf_y = wf_vals + [sum(wf_vals)]
        fig_wf = go.Figure(go.Waterfall(
            name="Custos",
            orientation="v",
            x=wf_x, y=wf_y,
            measure=wf_measures,
            connector={"line": {"color": "#1e2e1c"}},
            increasing={"marker": {"color": "#4a9e3f"}},
            decreasing={"marker": {"color": "#c0392b"}},
            totals={"marker": {"color": "#2980b9"}},
            text=[fmtR(v) for v in wf_y],
            textposition="outside",
            textfont=dict(color="#e8edd0", size=11),
        ))
        fig_wf.update_layout(**PDARK, height=280, showlegend=False, yaxis={**PLOT_AXIS, "title": "R$"})
        st.plotly_chart(fig_wf, use_container_width=True, key="k_waterfall")

    st.markdown('<div class="sec">Tendência · últimos meses</div>', unsafe_allow_html=True)
    if not df_resumo.empty:
        trend = df_resumo.sort_values("mes_key").tail(n_meses_trend).copy()
        trend["mes_label"] = trend["mes_key"].map(fmt_mes_label)
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=trend["mes_label"], y=trend["disp_media_pct"],
            name="Disponib. %", mode="lines+markers",
            line=dict(color="#4a9e3f", width=3), marker=dict(size=8),
            yaxis="y",
        ))
        fig_trend.add_trace(go.Scatter(
            x=trend["mes_label"], y=trend["horas_parada"],
            name="H. Paradas", mode="lines+markers",
            line=dict(color="#c0392b", width=2, dash="dot"), marker=dict(size=6),
            yaxis="y2",
        ))
        fig_trend.add_trace(go.Bar(
            x=trend["mes_label"], y=trend["custo_pecas"] + trend["custo_lancamentos"],
            name="Custos R$", marker_color="rgba(41,128,185,0.5)",
            yaxis="y3",
        ))
        fig_trend.update_layout(
            **PDARK, height=320,
            xaxis={**PLOT_AXIS},
            yaxis={**PLOT_AXIS, "title": "Disponib. %", "side": "left", "range": [0, 100]},
            yaxis2={**PLOT_AXIS, "title": "Horas paradas", "overlaying": "y", "side": "right"},
            yaxis3={**PLOT_AXIS, "title": "R$ custos", "overlaying": "y", "anchor": "free", "position": 0.95, "showgrid": False},
            legend=dict(orientation="h", y=1.12, font=dict(color="#e8edd0")),
        )
        st.plotly_chart(fig_trend, use_container_width=True, key="k_trend")
    else:
        st.info("Rode as views SQL (vw_painel_estrategico_resumo_mes) no Supabase para ver a tendência.")

    if not df_pecas_m.empty or not df_lanc_m.empty:
        st.markdown('<div class="sec">Distribuição de custos · Sunburst</div>', unsafe_allow_html=True)
        sb_rows = []
        if not df_pecas_m.empty:
            for cat, r in df_pecas_m.groupby("categoria_painel")["custo_pecas"].sum().items():
                sb_rows.append({"cat": str(cat), "tipo": "Peças OS", "valor": r})
        if not df_lanc_m.empty:
            for tipo, r in df_lanc_m.groupby("tipo_manutencao")["valor_total"].sum().items():
                sb_rows.append({"cat": "Lançamentos", "tipo": str(tipo), "valor": r})
        if custo_parada_tot > 0:
            sb_rows.append({"cat": "Parada", "tipo": "Mecânico", "valor": custo_parada_mec})
            sb_rows.append({"cat": "Parada", "tipo": "Operador", "valor": custo_parada_op})
        if sb_rows:
            df_sb = pd.DataFrame(sb_rows)
            fig_sb = px.sunburst(
                df_sb, path=["cat", "tipo"], values="valor",
                color="cat", color_discrete_sequence=CORES,
            )
            fig_sb.update_layout(**PDARK, height=340)
            fig_sb.update_traces(textinfo="label+percent entry", insidetextorientation="radial")
            st.plotly_chart(fig_sb, use_container_width=True, key="k_sunburst")

# ══════════════════════════════════════════════════════════════
# TAB 2 — HORAS & DISPONIBILIDADE
# ══════════════════════════════════════════════════════════════
with tab2:
    if df_disp_m.empty:
        st.warning("Sem dados de disponibilidade para o mês/categorias selecionados.")
    else:
        st.markdown(f'<div class="sec">Parado × Operando · {fmt_mes_label(mes_sel)}</div>', unsafe_allow_html=True)
        df_disp_m = df_disp_m.copy()
        df_disp_m["label"] = df_disp_m.apply(label_trator, axis=1)

        h1, h2 = st.columns(2)
        with h1:
            dd = df_disp_m.sort_values("horas_trabalhadas", ascending=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="✅ Operando", y=dd["label"], x=dd["horas_trabalhadas"],
                orientation="h", marker_color="#4a9e3f",
                text=dd["horas_trabalhadas"].apply(lambda v: f"{v:.0f}h"),
                textposition="inside", textfont=dict(color="#e8edd0"),
            ))
            fig.add_trace(go.Bar(
                name="🔴 Paradas", y=dd["label"], x=dd["horas_parada"],
                orientation="h", marker_color="#c0392b",
                text=dd["horas_parada"].apply(lambda v: f"{v:.0f}h" if v > 0 else ""),
                textposition="inside", textfont=dict(color="#e8edd0"),
            ))
            fig.update_layout(
                **PDARK, barmode="stack", height=max(320, len(dd) * 28),
                legend=dict(orientation="h", y=1.05, font=dict(color="#e8edd0")),
                xaxis={**PLOT_AXIS, "title": "Horas no mês"},
                yaxis={**PLOT_AXIS},
            )
            st.plotly_chart(fig, use_container_width=True, key="k_stack_h")

        with h2:
            dd2 = df_disp_m.sort_values("disponibilidade_pct", ascending=True)
            cores = dd2["disponibilidade_pct"].apply(
                lambda v: "#c0392b" if v < 70 else "#d4a017" if v < 85 else "#4a9e3f"
            )
            fig2 = go.Figure(go.Bar(
                y=dd2["label"], x=dd2["disponibilidade_pct"],
                orientation="h", marker_color=cores.tolist(),
                text=dd2["disponibilidade_pct"].apply(lambda v: f"{v:.1f}%"),
                textposition="outside", textfont=dict(color="#e8edd0"),
            ))
            fig2.add_vline(x=85, line_color="#4a9e3f", line_dash="dot")
            fig2.add_vline(x=70, line_color="#c0392b", line_dash="dash")
            fig2.update_layout(
                **PDARK, height=max(320, len(dd2) * 28),
                xaxis_range=[0, 115], xaxis={**PLOT_AXIS}, yaxis={**PLOT_AXIS},
            )
            st.plotly_chart(fig2, use_container_width=True, key="k_disp_bar")

        # Heatmap frota x mes
        if not df_disp.empty:
            st.markdown('<div class="sec">Heatmap · Disponibilidade % (frota × mês)</div>', unsafe_allow_html=True)
            df_hm = filtrar_cat(df_disp.copy())
            meses_hm = sorted(df_hm["mes_key"].unique())[-n_meses_trend:]
            df_hm = df_hm[df_hm["mes_key"].isin(meses_hm)]
            if not df_hm.empty:
                pivot = df_hm.pivot_table(
                    index="id_frota", columns="mes_key", values="disponibilidade_pct", aggfunc="mean"
                )
                pivot = pivot.loc[pivot.mean(axis=1).sort_values().index]
                fig_hm = go.Figure(go.Heatmap(
                    z=pivot.values,
                    x=[fmt_mes_label(c) for c in pivot.columns],
                    y=pivot.index.astype(str),
                    colorscale=[[0, "#2a1010"], [0.7, "#2a2200"], [0.85, "#1a3318"], [1, "#4a9e3f"]],
                    zmin=0, zmax=100,
                    text=pivot.values.round(1),
                    texttemplate="%{text}%",
                    textfont=dict(size=10, color="#e8edd0"),
                    hovertemplate="Frota %{y}<br>%{x}: %{z:.1f}%<extra></extra>",
                ))
                fig_hm.update_layout(
                    **PDARK, height=max(280, len(pivot) * 22),
                    xaxis={**PLOT_AXIS}, yaxis={**PLOT_AXIS, "tickfont": dict(size=10)},
                )
                st.plotly_chart(fig_hm, use_container_width=True, key="k_heatmap")

# ══════════════════════════════════════════════════════════════
# TAB 3 — CUSTOS & PEÇAS
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown(f'<div class="sec">Custos de manutenção · {fmt_mes_label(mes_sel)}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🔩 Peças (financeiro_os)", fmtR(custo_pecas))
    c2.metric("🔧 MO registrada", fmtR(custo_mo))
    c3.metric("📄 NF-e (lançamentos)", fmtR(custo_lanc))
    c4.metric("⏱ Custo parada total", fmtR(custo_parada_tot))
    c5.metric("💰 Total estimado", fmtR(custo_pecas + custo_mo + custo_lanc + custo_parada_tot))

    ct1, ct2 = st.columns(2)
    with ct1:
        st.markdown('<div class="sec">Top frotas · Treemap de custos</div>', unsafe_allow_html=True)
        tm_rows = []
        if not df_pecas_m.empty:
            for fid, v in df_pecas_m.groupby("id_frota")["custo_pecas"].sum().items():
                tm_rows.append({"frota": str(fid), "tipo": "Peças", "valor": v})
        if not df_parada.empty:
            for fid, v in df_parada.groupby("id_frota")["_c_tot"].sum().items():
                if v > 0:
                    tm_rows.append({"frota": str(fid), "tipo": "Parada", "valor": v})
        if tm_rows:
            df_tm = pd.DataFrame(tm_rows)
            fig_tm = px.treemap(
                df_tm, path=["frota", "tipo"], values="valor",
                color="valor", color_continuous_scale=["#1a3318", "#4a9e3f", "#d4a017", "#c0392b"],
            )
            fig_tm.update_layout(**PDARK, height=320)
            st.plotly_chart(fig_tm, use_container_width=True, key="k_treemap")

    with ct2:
        st.markdown('<div class="sec">Peças por sistema (OS)</div>', unsafe_allow_html=True)
        if not df_os_m.empty and not df_pecas_m.empty:
            merged = df_pecas_m.merge(
                df_os_m[["numero_os", "sistema"]].drop_duplicates(),
                on="numero_os", how="left",
            )
            rs = merged.groupby("sistema")["custo_pecas"].sum().reset_index().sort_values("custo_pecas", ascending=True).tail(10)
            fig_p = go.Figure(go.Bar(
                y=rs["sistema"], x=rs["custo_pecas"], orientation="h",
                marker_color="#2980b9",
                text=rs["custo_pecas"].apply(fmtR), textposition="outside",
                textfont=dict(color="#e8edd0"),
            ))
            fig_p.update_layout(**PDARK, height=320, xaxis={**PLOT_AXIS}, yaxis={**PLOT_AXIS})
            st.plotly_chart(fig_p, use_container_width=True, key="k_pecas_sis")
        else:
            st.info("Sem cruzamento OS × peças neste mês.")

    if not df_pecas_m.empty:
        st.markdown('<div class="sec">Detalhe peças por OS</div>', unsafe_allow_html=True)
        det = df_pecas_m.sort_values("custo_pecas", ascending=False).head(25).copy()
        det_show = pd.DataFrame({
            "OS": det["numero_os"],
            "Frota": det["id_frota"],
            "Peças": det["custo_pecas"].apply(fmtR),
            "MO": det["custo_mo"].apply(fmtR),
            "Total OS": (det["custo_pecas"] + det["custo_mo"]).apply(fmtR),
        })
        dark_table(det_show, height=380)

# ══════════════════════════════════════════════════════════════
# TAB 4 — POR PESSOA
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown(f'<div class="sec">Custo por mecânico e operador · {fmt_mes_label(mes_sel)}</div>', unsafe_allow_html=True)

    if df_parada.empty:
        st.info("Sem OS no mês para calcular custos por pessoa.")
    elif df_colab.empty:
        st.warning("Cadastre custo_hora em dim_colaborador para calcular os custos.")
    else:
        pm1, pm2, pm3 = st.columns(3)
        pm1.metric("🔧 Custo mecânicos", fmtR(custo_parada_mec))
        pm2.metric("👨‍🌾 Custo operadores", fmtR(custo_parada_op))
        pm3.metric("⏱ Horas parada OS", f"{fmt(df_parada['_h'].sum(), 1)}h")

        pp1, pp2 = st.columns(2)
        with pp1:
            st.markdown('<div class="sec">Top mecânicos · horas × custo/h</div>', unsafe_allow_html=True)
            mec = df_parada[df_parada["_c_mec"] > 0].copy()
            if not mec.empty:
                rm = mec.groupby("mecanico").agg(
                    horas=("_h", "sum"), custo=("_c_mec", "sum"), os=("numero_os", "count")
                ).reset_index().sort_values("custo", ascending=True).tail(10)
                fig_m = go.Figure()
                fig_m.add_trace(go.Bar(
                    y=rm["mecanico"], x=rm["horas"], name="Horas",
                    orientation="h", marker_color="#4a9e3f",
                    text=rm["horas"].apply(lambda v: f"{v:.1f}h"), textposition="inside",
                ))
                fig_m.add_trace(go.Scatter(
                    y=rm["mecanico"], x=rm["custo"], name="R$ Custo",
                    mode="markers+text",
                    marker=dict(size=rm["custo"] / rm["custo"].max() * 30 + 8, color="#d4a017"),
                    text=rm["custo"].apply(fmtR), textposition="middle right",
                    textfont=dict(color="#e8edd0", size=10),
                    xaxis="x2",
                ))
                fig_m.update_layout(
                    **PDARK, height=320,
                    xaxis={**PLOT_AXIS, "title": "Horas parada"},
                    xaxis2={**PLOT_AXIS, "title": "R$", "overlaying": "x", "side": "top", "showgrid": False},
                    yaxis={**PLOT_AXIS},
                    legend=dict(orientation="h", y=1.08, font=dict(color="#e8edd0")),
                )
                st.plotly_chart(fig_m, use_container_width=True, key="k_mec")
            else:
                st.info("Sem custo de mecânico registrado.")

        with pp2:
            st.markdown('<div class="sec">Top operadores · máquina parada</div>', unsafe_allow_html=True)
            op = df_parada[(df_parada["_c_op"] > 0) & (df_parada["_oper"] != "")].copy()
            if not op.empty:
                ro = op.groupby("_oper").agg(
                    horas=("_h", "sum"), custo=("_c_op", "sum"), os=("numero_os", "count")
                ).reset_index().sort_values("custo", ascending=True).tail(10)
                ro["operador"] = ro["_oper"]
                fig_o = go.Figure(go.Bar(
                    y=ro["operador"], x=ro["custo"], orientation="h",
                    marker_color="#2980b9",
                    text=ro.apply(lambda r: f"{fmtR(r['custo'])} · {r['horas']:.1f}h", axis=1),
                    textposition="outside", textfont=dict(color="#e8edd0", size=11),
                ))
                fig_o.update_layout(**PDARK, height=320, xaxis={**PLOT_AXIS}, yaxis={**PLOT_AXIS})
                st.plotly_chart(fig_o, use_container_width=True, key="k_oper")
            else:
                st.info("Sem custo de operador (implementos não têm operador próprio).")

        st.markdown('<div class="sec">Radar · produtividade mecânicos (horas OS)</div>', unsafe_allow_html=True)
        mec_radar = df_parada[df_parada["_c_mec"] > 0].copy()
        if not mec_radar.empty:
            rm_r = mec_radar.groupby("mecanico")["_h"].sum().reset_index().sort_values("_h", ascending=False).head(8)
            fig_r = go.Figure(go.Scatterpolar(
                r=rm_r["_h"].tolist(),
                theta=rm_r["mecanico"].tolist(),
                fill="toself",
                fillcolor="rgba(74,158,63,0.3)",
                line=dict(color="#4a9e3f", width=2),
            ))
            fig_r.update_layout(
                **PDARK, height=340,
                polar=dict(
                    bgcolor="#0d180c",
                    radialaxis=dict(visible=True, gridcolor="#1e2e1c", tickfont=dict(color="#8aab80")),
                    angularaxis=dict(tickfont=dict(color="#e8edd0", size=11)),
                ),
            )
            st.plotly_chart(fig_r, use_container_width=True, key="k_radar")

# ══════════════════════════════════════════════════════════════
# TAB 5 — ABASTECIMENTO × PRODUTIVIDADE
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown(f'<div class="sec">Combustível vs horas operando · {fmt_mes_label(mes_sel)}</div>', unsafe_allow_html=True)

    ab1, ab2, ab3 = st.columns(3)
    ab1.metric("⛽ Litros abastecidos", f"{fmt(litros)} L")
    ab2.metric("⚙️ Horas operando", f"{fmt(ht)}h")
    ab3.metric("📈 L/h produtividade", f"{litros/ht:.1f} L/h" if ht > 0 else "—")

    if not df_abast_m.empty and not df_disp_m.empty:
        cruz = df_abast_m.merge(
            df_disp_m[["id_frota", "horas_trabalhadas", "horas_parada", "disponibilidade_pct"]],
            on="id_frota", how="inner",
        )
        cruz["litros_h"] = cruz.apply(
            lambda r: r["litros_total"] / r["horas_trabalhadas"] if r["horas_trabalhadas"] > 0 else 0,
            axis=1,
        )
        cruz["label"] = cruz.apply(
            lambda r: label_trator({"id_frota": r["id_frota"], "modelo": r.get("modelo", "")}),
            axis=1,
        )

        ax1, ax2 = st.columns(2)
        with ax1:
            st.markdown('<div class="sec">Scatter · Litros × Horas operando</div>', unsafe_allow_html=True)
            fig_sc = px.scatter(
                cruz, x="horas_trabalhadas", y="litros_total",
                size="disponibilidade_pct", color="disponibilidade_pct",
                hover_name="label",
                labels={"horas_trabalhadas": "Horas operando", "litros_total": "Litros"},
                color_continuous_scale=["#c0392b", "#d4a017", "#4a9e3f"],
            )
            fig_sc.update_layout(**PDARK, height=340, coloraxis_colorbar=dict(tickfont=dict(color="#e8edd0")))
            st.plotly_chart(fig_sc, use_container_width=True, key="k_scatter")

        with ax2:
            st.markdown('<div class="sec">Consumo específico · L/h por frota</div>', unsafe_allow_html=True)
            cr = cruz[cruz["litros_h"] > 0].sort_values("litros_h", ascending=True).tail(12)
            fig_lh = go.Figure(go.Bar(
                y=cr["label"], x=cr["litros_h"], orientation="h",
                marker_color=cr["disponibilidade_pct"].apply(
                    lambda v: "#c0392b" if v < 70 else "#d4a017" if v < 85 else "#4a9e3f"
                ),
                text=cr["litros_h"].apply(lambda v: f"{v:.1f} L/h"),
                textposition="outside", textfont=dict(color="#e8edd0"),
            ))
            fig_lh.update_layout(**PDARK, height=340, xaxis={**PLOT_AXIS, "title": "Litros / hora"}, yaxis={**PLOT_AXIS})
            st.plotly_chart(fig_lh, use_container_width=True, key="k_lh")

        st.markdown('<div class="sec">Tabela cruzada · frota</div>', unsafe_allow_html=True)
        t_cruz = cruz.sort_values("litros_total", ascending=False).head(20).copy()
        t_show = pd.DataFrame({
            "Frota": t_cruz["label"],
            "Litros": t_cruz["litros_total"].apply(lambda v: f"{v:,.0f} L"),
            "H. Operando": t_cruz["horas_trabalhadas"].apply(lambda v: f"{v:.0f}h"),
            "H. Paradas": t_cruz["horas_parada"].apply(lambda v: f"{v:.0f}h"),
            "Disp. %": t_cruz["disponibilidade_pct"].apply(lambda v: f"{v:.1f}%"),
            "L/h": t_cruz["litros_h"].apply(lambda v: f"{v:.1f}"),
        })
        dark_table(t_show, height=360)
    else:
        st.info(
            "Para este cruzamento, é necessário abastecimento (vw_painel_abastecimento) "
            "e disponibilidade (vw_disponibilidade_equipamentos) no mesmo mês."
        )

st.divider()
st.markdown(
    '<div style="text-align:center;color:#4a6644;font-size:11px;font-family:Barlow Condensed,sans-serif;'
    'letter-spacing:1px;padding:8px 0;">'
    'Santa Vergínia Agropecuária e Florestal · Controladoria · Painel Estratégico Mecanização</div>',
    unsafe_allow_html=True,
)
