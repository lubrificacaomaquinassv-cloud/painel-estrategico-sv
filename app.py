import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import unicodedata

PAINEL_BUILD = "2026-07-24-periodo-maijunjul-v7"
MES_INICIO_COLETA = "2026-05"  # início apontamento_campo
LIMITE_OUTLIER_CUSTO = 50000.0  # ex.: motor R$ 91k — fora dos gráficos rotineiros
# Operação linear — só apontamento_campo (tempo real); exclui uso esporádico
MIN_DIAS_APONT_MES = 8       # mín. dias com apontamento no mês
MIN_HORAS_MES = 32           # mín. horas no mês
MIN_DIAS_SEQ_LINEAR = 5      # mín. dias consecutivos sem OS
MIN_DIAS_APONT_PERIODO = 20  # mín. dias no bloco Mai–Jun–Jul
MIN_HORAS_PERIODO = 80
FROTA_USO_ESPORADICO = {"920", "920K", "9999"}
PERIODO_INICIAL_MESES = ["2026-05", "2026-06", "2026-07"]

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
div[data-testid="metric-container"] [data-testid="stMetricValue"]{
 color:#e8edd0!important;font-size:1.25rem!important;white-space:normal!important;overflow:visible!important;}
div[data-testid="metric-container"] [data-testid="stMetricDelta"]{color:#8aab80!important;font-size:11px!important;}
.kpi-card{background:#111c10;border:1px solid #1e2e1c;border-radius:10px;padding:12px 14px;margin-bottom:8px;}
.kpi-lab{font-family:'Barlow Condensed',sans-serif;font-size:11px;color:#8aab80;
 letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;}
.kpi-val{font-family:'Barlow Condensed',sans-serif;font-size:1.45rem;font-weight:700;color:#e8edd0;
 line-height:1.2;word-break:break-word;}
.kpi-sub{font-size:10px;color:#6fcf60;margin-top:4px;}
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


def fmtR_curto(n):
    """Valores grandes legíveis em cards estreitos."""
    if pd.isna(n):
        return "—"
    n = float(n)
    if n >= 1_000_000:
        return f"R$ {n/1_000_000:.2f}M".replace(".", ",")
    if n >= 10_000:
        return f"R$ {n/1_000:.1f}k".replace(".", ",")
    return fmtR(n)


def kpi_card(label, value, sub=""):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi-card"><div class="kpi-lab">{label}</div>'
        f'<div class="kpi-val">{value}</div>{sub_html}</div>'
    )


def kpi_grid(cards, cols=4):
    """cards: [(label, value, sub?), ...] — HTML em linhas."""
    if not cards:
        return
    for i in range(0, len(cards), cols):
        chunk = cards[i:i + cols]
        st_cols = st.columns(cols)
        for j, item in enumerate(chunk):
            lab, val = item[0], item[1]
            sub = item[2] if len(item) > 2 else ""
            with st_cols[j]:
                st.markdown(kpi_card(lab, val, sub), unsafe_allow_html=True)


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


def meses_com_coleta(df_apont, df_disp=None):
    """Somente meses com apontamento real (>= maio/2026)."""
    meses = set()
    if df_apont is not None and not df_apont.empty:
        ap = df_apont.copy()
        ap["_mk"] = pd.to_datetime(ap["data"], errors="coerce").dt.strftime("%Y-%m")
        for mk, g in ap.groupby("_mk"):
            if mk and mk >= MES_INICIO_COLETA and g["horas_trabalhadas"].sum() > 0:
                meses.add(mk)
    if df_disp is not None and not df_disp.empty and "mes_key" in df_disp.columns:
        g = df_disp.groupby("mes_key")["horas_trabalhadas"].sum()
        for mk, h in g.items():
            if str(mk) >= MES_INICIO_COLETA and h > 0:
                meses.add(str(mk))
    return sorted(meses)


def filtrar_meses_coleta(df, col="mes_key"):
    if df.empty or col not in df.columns:
        return df
    return df[df[col].astype(str) >= MES_INICIO_COLETA].copy()


def maior_sequencia_dias(datas):
    """Maior sequência de dias consecutivos."""
    if not datas:
        return []
    datas = sorted(set(datas))
    best, cur = [datas[0]], [datas[0]]
    for d in datas[1:]:
        if (d - cur[-1]).days == 1:
            cur.append(d)
        else:
            if len(cur) > len(best):
                best = cur
            cur = [d]
    if len(cur) > len(best):
        best = cur
    return best


def fmt_periodo_label(periodo_id):
    if periodo_id == "2026-maijunjul":
        return "Mai · Jun · Jul/2026"
    return str(periodo_id)


def periodos_resumo_disponiveis(meses_opts):
    """Períodos fixos de resumo. Trimestre civil entra quando o ano tiver coleta completa."""
    meses_set = set(meses_opts)
    out = []
    m_ini = [m for m in PERIODO_INICIAL_MESES if m in meses_set and m >= MES_INICIO_COLETA]
    if len(m_ini) >= 2:
        out.append({"id": "2026-maijunjul", "label": fmt_periodo_label("2026-maijunjul"), "meses": m_ini})
    return out


def meses_do_periodo(periodo_id, meses_validos=None):
    if periodo_id == "2026-maijunjul":
        todos = list(PERIODO_INICIAL_MESES)
    else:
        return []
    if meses_validos is not None:
        return [m for m in todos if m in meses_validos and m >= MES_INICIO_COLETA]
    return [m for m in todos if m >= MES_INICIO_COLETA]


def mapa_frota_painel(df_painel):
    if df_painel is None or df_painel.empty:
        return {}
    pm = df_painel.copy()
    pm["id_frota"] = norm_frota_id(pm["id_frota"])
    return pm.set_index("id_frota")[["modelo", "categoria_painel"]].to_dict("index")


def frota_uso_esporadico(frota, modelo="", categoria=""):
    fid = str(frota or "").strip().upper()
    if fid in FROTA_USO_ESPORADICO:
        return True, "Frota sazonal (colheita)"
    mod = str(modelo or "").upper()
    cat = str(categoria or "").upper()
    if "COLHEIT" in cat or "HARVEST" in mod or "COLHEIT" in mod or "COLHEDOR" in mod:
        return True, "Colheitadeira / uso esporádico"
    return False, ""


def calc_operacao_linear_apontamento(df_apont, df_os, meses, df_painel=None, somente_elegiveis=True):
    """
    Operação linear via apontamento_campo: maior sequência de dias consecutivos
    com apontamento e sem OS. Exclui colheitadeiras e frotas com poucos dias no mês.
    """
    if df_apont.empty or not meses:
        return pd.DataFrame()
    meses = list(meses)
    multi = len(meses) > 1
    pm = mapa_frota_painel(df_painel)

    ap = df_apont.copy()
    ap["frota"] = norm_frota_id(ap["frota"])
    ap["_mk"] = pd.to_datetime(ap["data"], errors="coerce").dt.strftime("%Y-%m")
    ap = ap[ap["_mk"].isin(meses) & (ap["horas_trabalhadas"] > 0)]
    if ap.empty:
        return pd.DataFrame()

    os_por_frota = {}
    if not df_os.empty:
        os = df_os[df_os["mes_key"].astype(str).isin(meses)].copy()
        if "data_os" not in os.columns and "created_at" in os.columns:
            os["data_os"] = parse_dt(os["created_at"]).dt.date
        os["id_frota"] = norm_frota_id(os["id_frota"])
        for fid, g in os.groupby("id_frota"):
            os_por_frota[str(fid)] = set(g["data_os"].dropna())

    rows = []
    for frota, grp in ap.groupby("frota"):
        fid = str(frota)
        info = pm.get(fid, {})
        modelo = info.get("modelo", "")
        categoria = info.get("categoria_painel", "")
        esporadico, motivo_esp = frota_uso_esporadico(fid, modelo, categoria)

        por_dia = grp.groupby("data")["horas_trabalhadas"].sum()
        dias_apont = len(por_dia)
        horas_total = float(por_dia.sum())
        os_dias = os_por_frota.get(fid, set())
        dias_limpos = sorted(d for d in por_dia.index if d not in os_dias)
        seq = maior_sequencia_dias(dias_limpos)
        dias_linear = len(seq)
        horas_linear = sum(por_dia[d] for d in seq) if seq else 0

        # Elegibilidade por mês (pior mês do período) ou totais no bloco
        if multi:
            ok_meses = []
            for mk in meses:
                gmk = grp[grp["_mk"] == mk]
                if gmk.empty:
                    ok_meses.append(False)
                    continue
                pd_mk = gmk.groupby("data")["horas_trabalhadas"].sum()
                ok_meses.append(
                    len(pd_mk) >= MIN_DIAS_APONT_MES and float(pd_mk.sum()) >= MIN_HORAS_MES
                )
            regular = sum(ok_meses) >= max(1, len(meses) - 1)  # regular em quase todos os meses
            regular = regular and dias_apont >= MIN_DIAS_APONT_PERIODO and horas_total >= MIN_HORAS_PERIODO
        else:
            regular = dias_apont >= MIN_DIAS_APONT_MES and horas_total >= MIN_HORAS_MES

        linear_ok = dias_linear >= MIN_DIAS_SEQ_LINEAR and horas_linear > 0
        elegivel = regular and linear_ok and not esporadico
        motivo = ""
        if esporadico:
            motivo = motivo_esp
        elif not regular:
            motivo = f"Poucos dias/horas ({dias_apont}d · {horas_total:.0f}h)"
        elif not linear_ok:
            motivo = f"Sequência curta ({dias_linear}d sem OS)"

        rows.append({
            "id_frota": fid,
            "modelo": modelo,
            "categoria_painel": categoria,
            "dias_apontamento": dias_apont,
            "horas_total": horas_total,
            "dias_linear": dias_linear,
            "horas_linear": horas_linear,
            "periodo": f"{seq[0].strftime('%d/%m')}–{seq[-1].strftime('%d/%m')}" if seq else "—",
            "elegivel": elegivel,
            "motivo_exclusao": motivo,
            "label_curto": label_curto({"id_frota": fid, "modelo": modelo}),
        })

    out = pd.DataFrame(rows).sort_values(["elegivel", "horas_linear"], ascending=[False, False])
    if somente_elegiveis:
        out = out[out["elegivel"]].copy()
    return out


def calc_operacao_linear_periodo(df_apont, df_os, meses, df_painel=None):
    return calc_operacao_linear_apontamento(df_apont, df_os, meses, df_painel, somente_elegiveis=True)


def label_curto(row, max_len=20):
    frota = str(row.get("id_frota") or row.get("frota") or "—")
    modelo = row.get("modelo")
    if pd.notna(modelo) and str(modelo).strip():
        palavras = str(modelo).strip().split()
        mod = palavras[-1] if palavras else str(modelo)[:10]
        txt = f"{mod} · {frota}"
    else:
        txt = frota
    return txt if len(txt) <= max_len else txt[: max_len - 1] + "…"


def abast_s500_periodo(df_det, meses):
    if df_det.empty or not meses:
        return pd.DataFrame(columns=["id_frota", "litros_s500"])
    d = filtrar_meses_coleta(df_det)
    d = d[d["mes_key"].astype(str).isin(meses)].copy()
    if "fuel_type" in d.columns:
        d = d[d["fuel_type"].str.contains(r"S.?500|ADITIVADO", na=False, regex=True)]
    if d.empty:
        return pd.DataFrame(columns=["id_frota", "litros_s500"])
    return (
        d.groupby("id_frota", as_index=False)["liters"]
        .sum()
        .rename(columns={"liters": "litros_s500"})
    )


def agg_frota_trimestre(df_disp, df_abast, df_abast_s500, meses):
    if df_disp.empty or not meses:
        return pd.DataFrame()
    d = filtrar_meses_coleta(df_disp)
    d = d[d["mes_key"].astype(str).isin(meses)]
    d = filtrar_cat(d)
    if d.empty:
        return pd.DataFrame()
    g = d.groupby("id_frota", as_index=False).agg(
        horas_trabalhadas=("horas_trabalhadas", "sum"),
        horas_parada=("horas_parada", "sum"),
        total_os=("total_os", "sum"),
        modelo=("modelo", "first"),
        categoria_painel=("categoria_painel", "first"),
    )
    denom = g["horas_trabalhadas"] + g["horas_parada"]
    g["disponibilidade_pct"] = (g["horas_trabalhadas"] / denom.replace(0, pd.NA) * 100).fillna(0)
    g["label"] = g.apply(label_trator, axis=1)
    g["label_curto"] = g.apply(label_curto, axis=1)
    if df_abast is not None and not df_abast.empty:
        ab = filtrar_cat(df_abast[df_abast["mes_key"].astype(str).isin(meses)])
        if not ab.empty:
            g = g.merge(
                ab.groupby("id_frota", as_index=False)["litros_total"].sum(),
                on="id_frota", how="left",
            )
        else:
            g["litros_total"] = 0.0
    else:
        g["litros_total"] = 0.0
    g["litros_total"] = pd.to_numeric(g.get("litros_total", 0), errors="coerce").fillna(0)
    if df_abast_s500 is not None and not df_abast_s500.empty:
        g = g.merge(df_abast_s500, on="id_frota", how="left")
    else:
        g["litros_s500"] = 0.0
    g["litros_s500"] = pd.to_numeric(g.get("litros_s500", 0), errors="coerce").fillna(0)
    lit_col = "litros_s500" if g["litros_s500"].sum() > 0 else "litros_total"
    g["litros_uso"] = g[lit_col]
    g["litros_h"] = g.apply(
        lambda r: r["litros_uso"] / r["horas_trabalhadas"] if r["horas_trabalhadas"] > 0 else 0,
        axis=1,
    )
    return g


def chart_top_n(df, col, titulo, cor, n=10, fmt_fn=None):
    if df.empty or col not in df.columns:
        st.info("Sem dados para este ranking.")
        return None
    top = df.nlargest(n, col).sort_values(col, ascending=True)
    txt = top[col].apply(fmt_fn) if fmt_fn else top[col].astype(str)
    labels = top["label_curto"] if "label_curto" in top.columns else top.get("label", top.index.astype(str))
    fig = go.Figure(go.Bar(
        y=labels, x=top[col], orientation="h",
        marker_color=cor,
        text=txt, textposition="outside",
        textfont=dict(color="#e8edd0", size=10),
        hovertemplate="%{y}<br>%{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        **PDARK, height=max(320, n * 28),
        title=dict(text=titulo, font=dict(size=13, color="#8aab80")),
        xaxis={**PLOT_AXIS}, yaxis={**PLOT_AXIS, "tickfont": dict(size=10)},
    )
    return fig


def chart_radar_mecanicos(df_parada, titulo="Produtividade · mecânicos"):
    if df_parada.empty or "mecanico" not in df_parada.columns:
        return None
    rm = df_parada[df_parada["_c_mec"] > 0].groupby("mecanico").agg(
        horas=("_h", "sum"), os=("numero_os", "nunique"), custo=("_c_mec", "sum"),
    ).reset_index().sort_values("horas", ascending=False).head(6)
    if rm.empty:
        return None
    eixos = ["Horas OS", "Qtd OS", "Custo R$"]
    fig = go.Figure()
    for i, row in rm.iterrows():
        vals = []
        for col in ["horas", "os", "custo"]:
            mx = rm[col].max()
            vals.append(float(row[col] / mx * 100) if mx > 0 else 0)
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=eixos + [eixos[0]],
            fill="toself",
            name=str(row["mecanico"])[:18],
            line=dict(color=CORES[i % len(CORES)], width=2),
            opacity=0.75,
        ))
    fig.update_layout(
        **PDARK, height=380,
        title=dict(text=titulo, font=dict(size=13, color="#8aab80")),
        polar=dict(
            bgcolor="#0d180c",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#1e2e1c", tickfont=dict(color="#4a6644", size=9)),
            angularaxis=dict(tickfont=dict(color="#e8edd0", size=11)),
        ),
        legend=dict(orientation="h", y=-0.12, font=dict(color="#e8edd0", size=10)),
    )
    return fig


def calc_operacao_linear(df_apont, df_os, mes_sel, df_painel=None):
    return calc_operacao_linear_apontamento(
        df_apont, df_os, [mes_sel], df_painel, somente_elegiveis=True,
    )


def montar_rank_tratores(df_disp_m, df_abast_m=None, df_abast_s500=None):
    if df_disp_m.empty:
        return pd.DataFrame()
    r = df_disp_m.copy()
    r["label"] = r.apply(label_trator, axis=1)
    r["label_curto"] = r.apply(label_curto, axis=1)
    if df_abast_m is not None and not df_abast_m.empty:
        r = r.merge(
            df_abast_m[["id_frota", "litros_total"]].rename(columns={"litros_total": "litros"}),
            on="id_frota", how="left",
        )
    else:
        r["litros"] = 0.0
    if df_abast_s500 is not None and not df_abast_s500.empty:
        r = r.merge(
            df_abast_s500[["id_frota", "litros_s500"]], on="id_frota", how="left",
        )
    else:
        r["litros_s500"] = 0.0
    r["litros"] = pd.to_numeric(r.get("litros", 0), errors="coerce").fillna(0)
    r["litros_s500"] = pd.to_numeric(r.get("litros_s500", 0), errors="coerce").fillna(0)
    if r["litros"].sum() == 0 and r["litros_s500"].sum() > 0:
        r["litros"] = r["litros_s500"]
    r["litros_h"] = r.apply(
        lambda x: x["litros"] / x["horas_trabalhadas"] if x["horas_trabalhadas"] > 0 else 0,
        axis=1,
    )
    return r


def chart_top5(df, col, titulo, cor, fmt_fn=None, orientation="h"):
    return chart_top_n(df, col, titulo, cor, n=5, fmt_fn=fmt_fn)


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


def _secret(key, default=None):
    try:
        return st.secrets[key]
    except (KeyError, TypeError):
        return default


def _db_cfg():
    db = _secret("db")
    if not db or not db.get("host"):
        return None
    return db


def _supabase_cfg():
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_KEY")
    if url and key:
        return url, key
    return None, None


def _setup_secrets():
    st.error("Secrets não configurados no Streamlit Cloud.")
    st.markdown(
        "**Settings → Secrets** — cole o bloco abaixo "
        "(mesma senha do Postgres usada nos outros painéis SV):"
    )
    st.code(
        """SUPABASE_URL = "https://azhpxhrwhegfysoeqmft.supabase.co"
SUPABASE_KEY = "sua_anon_key_aqui"

[db]
host = "aws-1-sa-east-1.pooler.supabase.com"
port = 6543
dbname = "postgres"
user = "postgres.azhpxhrwhegfysoeqmft"
password = "SUA_SENHA_DO_BANCO"
""",
        language="toml",
    )
    st.info(
        "O painel usa Postgres direto (`[db]`) ou Supabase REST (`SUPABASE_URL` + `SUPABASE_KEY`). "
        "Depois de salvar, clique **Reboot app** no menu do Streamlit Cloud."
    )
    st.stop()


_db = _db_cfg()
_sb_url, _sb_key = _supabase_cfg()
if _db:
    CACHE_KEY = str(_db["host"])
    DATA_MODE = "postgres"
elif _sb_url:
    from supabase import create_client
    _supabase = create_client(_sb_url, _sb_key)
    CACHE_KEY = _sb_url
    DATA_MODE = "supabase"
else:
    _setup_secrets()


def get_conn():
    db = _db_cfg()
    if not db:
        raise RuntimeError("Postgres indisponível neste modo")
    return psycopg2.connect(
        host=db["host"],
        port=db["port"],
        dbname=db["dbname"],
        user=db["user"],
        password=db["password"],
        sslmode="require",
    )


def sb(table, order_col=None, desc=True):
    if DATA_MODE == "postgres":
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

    all_data = []
    page_size = 1000
    offset = 0
    while True:
        try:
            q = _supabase.table(table).select("*")
            if order_col:
                q = q.order(order_col, desc=desc)
            r = q.range(offset, offset + page_size - 1).execute()
        except Exception:
            try:
                r = _supabase.table(table).select("*").range(offset, offset + page_size - 1).execute()
            except Exception:
                return pd.DataFrame()
        batch = r.data or []
        all_data.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return pd.DataFrame(all_data)


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


@st.cache_data(ttl=120, show_spinner=False)
def load_abast_detalhe(_c):
    df = sb("vw_painel_abastecimento", order_col="created_at", desc=True)
    if df.empty:
        df = sb("vw_abastecimento_consolidado", order_col="created_at", desc=True)
    if df.empty:
        return df
    df = df.copy()
    df["mes_key"] = parse_mes_key(parse_dt(df["created_at"]))
    df["id_frota"] = norm_frota_id(df.get("vehicle", df.get("id_frota", "")))
    df["liters"] = pd.to_numeric(df.get("liters", 0), errors="coerce").fillna(0)
    if "fuel_type" in df.columns:
        df["fuel_type"] = df["fuel_type"].astype(str).str.upper()
    return df


def abast_s500_mes(df_det, mes_sel):
    if df_det.empty:
        return pd.DataFrame(columns=["id_frota", "litros_s500"])
    d = filtrar_meses_coleta(df_det)
    d = d[d["mes_key"].astype(str) == mes_sel].copy()
    if "fuel_type" in d.columns:
        d = d[d["fuel_type"].str.contains(r"S.?500|ADITIVADO", na=False, regex=True)]
    if d.empty:
        return pd.DataFrame(columns=["id_frota", "litros_s500"])
    return (
        d.groupby("id_frota", as_index=False)["liters"]
        .sum()
        .rename(columns={"liters": "litros_s500"})
    )


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


def separar_custos_outliers(df_lanc_m, df_pecas_m, limite=LIMITE_OUTLIER_CUSTO):
    """Separa lançamentos/OS extraordinários (ex.: motor R$ 91k) dos rotineiros."""
    extra_rows = []
    lanc_rot = df_lanc_m.copy() if not df_lanc_m.empty else pd.DataFrame()
    pecas_rot = df_pecas_m.copy() if not df_pecas_m.empty else pd.DataFrame()

    if not df_lanc_m.empty:
        vcol = "valor_total" if "valor_total" in df_lanc_m.columns else "valor"
        df_l = df_lanc_m.copy()
        df_l["_v"] = pd.to_numeric(df_l.get(vcol, 0), errors="coerce").fillna(0)
        mask = df_l["_v"] >= limite
        if mask.any():
            for _, r in df_l[mask].iterrows():
                extra_rows.append({
                    "tipo": "NF-e / Lançamento",
                    "referencia": str(r.get("descricao", r.get("fornecedor", r.get("id", "—"))))[:60],
                    "frota": str(r.get("id_frota", "—")),
                    "valor": r["_v"],
                })
            lanc_rot = df_l[~mask].drop(columns=["_v"], errors="ignore")

    if not df_pecas_m.empty:
        df_p = df_pecas_m.copy()
        df_p["_v"] = pd.to_numeric(df_p.get("custo_pecas", 0), errors="coerce").fillna(0)
        df_p["_tot"] = df_p["_v"] + pd.to_numeric(df_p.get("custo_mo", 0), errors="coerce").fillna(0)
        mask = df_p["_tot"] >= limite
        if mask.any():
            for _, r in df_p[mask].iterrows():
                extra_rows.append({
                    "tipo": "OS / Peças",
                    "referencia": f"OS {r.get('numero_os', '—')}",
                    "frota": str(r.get("id_frota", "—")),
                    "valor": r["_tot"],
                })
            pecas_rot = df_p[~mask].drop(columns=["_v", "_tot"], errors="ignore")

    return pd.DataFrame(extra_rows), lanc_rot, pecas_rot


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

df_resumo = load_resumo_mes(CACHE_KEY)
df_disp = load_disp_mes(CACHE_KEY)
df_os = load_os(CACHE_KEY)
df_pecas = load_pecas(CACHE_KEY)
df_lanc = load_lancamentos(CACHE_KEY)
df_abast = load_abast(CACHE_KEY)
df_abast_det = load_abast_detalhe(CACHE_KEY)
df_colab = load_colab(CACHE_KEY)
df_apont = load_apont(CACHE_KEY)
df_painel = load_frota_painel(CACHE_KEY)

# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filtros")
    meses_coleta = meses_com_coleta(df_apont, df_disp)
    meses_opts = [m for m in meses_coleta if m >= MES_INICIO_COLETA]
    if not meses_opts:
        meses_opts = meses_disponiveis(
            df_disp["mes_key"] if not df_disp.empty else pd.Series([mes_atual_str]),
            mes_atual_str,
            n=6,
        )
        meses_opts = [m for m in meses_opts if m >= MES_INICIO_COLETA] or [mes_atual_str]
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
    st.caption(
        f"Coleta desde {fmt_mes_label(MES_INICIO_COLETA)} · "
        f"Fonte: {DATA_MODE} · apontamento_campo + ordem_servico"
    )
    trimestres_opts = periodos_resumo_disponiveis(meses_opts)
    if not trimestres_opts:
        trimestres_opts = [{"id": "2026-maijunjul", "label": fmt_periodo_label("2026-maijunjul"), "meses": meses_opts[:3]}]
    periodo_sel = st.selectbox(
        "Período (resumo)",
        options=[p["id"] for p in trimestres_opts],
        index=0,
        format_func=lambda pid: next(p["label"] for p in trimestres_opts if p["id"] == pid),
        key="periodo_sel",
    )
    preco_s500 = st.number_input(
        "Preço médio S-500 (R$/L)",
        min_value=0.0, value=0.0, step=0.05, format="%.2f",
        help="Opcional: estima custo de compra do diesel aditivado no período.",
        key="preco_s500",
    )

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
df_abast_s500_m = abast_s500_mes(df_abast_det, mes_sel)
df_extra_custos, df_lanc_rot, df_pecas_rot = separar_custos_outliers(df_lanc_m, df_pecas_m)
custo_lanc_rot = (
    pd.to_numeric(
        df_lanc_rot.get("valor_total", df_lanc_rot.get("valor", 0)),
        errors="coerce",
    ).fillna(0).sum()
    if not df_lanc_rot.empty else 0
)
custo_pecas_rot = df_pecas_rot["custo_pecas"].sum() if not df_pecas_rot.empty else 0
custo_extra = df_extra_custos["valor"].sum() if not df_extra_custos.empty else 0
df_rank = montar_rank_tratores(df_disp_m, df_abast_m, df_abast_s500_m)
df_linear = calc_operacao_linear(df_apont, df_os, mes_sel, df_painel)
if not df_linear.empty and not df_rank.empty:
    df_rank = df_rank.merge(
        df_linear[["id_frota", "dias_linear", "horas_linear", "periodo"]],
        on="id_frota", how="left",
    )
    df_rank["horas_linear"] = pd.to_numeric(df_rank["horas_linear"], errors="coerce").fillna(0)
    df_rank["dias_linear"] = pd.to_numeric(df_rank["dias_linear"], errors="coerce").fillna(0).astype(int)

meses_tri = meses_do_periodo(periodo_sel, set(meses_opts))
df_abast_s500_tri = abast_s500_periodo(df_abast_det, meses_tri)
df_frota_tri = agg_frota_trimestre(df_disp, df_abast, df_abast_s500_tri, meses_tri)
df_os_tri = (
    filtrar_cat(df_os[df_os["mes_key"].astype(str).isin(meses_tri)].copy())
    if not df_os.empty else pd.DataFrame()
)
df_pecas_tri = (
    filtrar_cat(df_pecas[df_pecas["mes_key"].astype(str).isin(meses_tri)])
    if not df_pecas.empty else pd.DataFrame()
)
df_parada_tri = calc_parada_os(df_os_tri, df_colab, df_apont) if not df_os_tri.empty else pd.DataFrame()
df_linear_tri = calc_operacao_linear_periodo(df_apont, df_os, meses_tri, df_painel)
df_linear_mes = calc_operacao_linear_apontamento(df_apont, df_os, [mes_sel], df_painel, somente_elegiveis=False)
if not df_linear_tri.empty and not df_frota_tri.empty:
    df_frota_tri = df_frota_tri.merge(
        df_linear_tri[["id_frota", "dias_linear", "horas_linear", "periodo"]],
        on="id_frota", how="left",
    )
ht_tri = df_frota_tri["horas_trabalhadas"].sum() if not df_frota_tri.empty else 0
hp_tri = df_frota_tri["horas_parada"].sum() if not df_frota_tri.empty else 0
litros_tri = df_frota_tri["litros_uso"].sum() if not df_frota_tri.empty else 0
litros_s500_tri = df_frota_tri["litros_s500"].sum() if not df_frota_tri.empty else 0
lh_tri = litros_tri / ht_tri if ht_tri > 0 else 0
custo_mec_tri = df_parada_tri["_c_mec"].sum() if not df_parada_tri.empty else 0
custo_op_tri = df_parada_tri["_c_op"].sum() if not df_parada_tri.empty else 0
custo_pecas_tri = df_pecas_tri["custo_pecas"].sum() if not df_pecas_tri.empty else 0
custo_mo_tri = df_pecas_tri["custo_mo"].sum() if not df_pecas_tri.empty else 0
custo_parada_tri = custo_mec_tri + custo_op_tri
custo_manut_tri = custo_parada_tri + custo_pecas_tri + custo_mo_tri
custo_s500_tri = litros_s500_tri * preco_s500 if preco_s500 > 0 and litros_s500_tri > 0 else 0

tab1, tab_tri, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 Visão Executiva",
    "📅 Mai–Jun–Jul",
    "⚙️ Horas & Disponibilidade",
    "💸 Custos & Peças",
    "🏆 Ranking Tratores",
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

    st.caption(
        f"Base operacional desde {fmt_mes_label(MES_INICIO_COLETA)} — "
        "custos extraordinários (ex.: motor) ficam na aba Financeiro, fora desta visão."
    )

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
        st.markdown('<div class="sec">Top 5 · horas operando no mês</div>', unsafe_allow_html=True)
        if not df_rank.empty:
            fig_top_op = chart_top5(
                df_rank, "horas_trabalhadas", "",
                "#4a9e3f", lambda v: f"{v:.0f}h",
            )
            if fig_top_op:
                st.plotly_chart(fig_top_op, use_container_width=True, key="k_top5_op")
        else:
            st.info("Sem ranking — verifique apontamento_campo no mês.")

    st.markdown('<div class="sec">Evolução operacional · meses com coleta</div>', unsafe_allow_html=True)
    if not df_resumo.empty:
        trend = filtrar_meses_coleta(df_resumo)
        trend = trend[trend["horas_trabalhadas"] > 0].sort_values("mes_key").tail(n_meses_trend)
        if trend.empty:
            st.info(f"Sem histórico operacional antes de {fmt_mes_label(MES_INICIO_COLETA)}.")
        else:
            trend["mes_label"] = trend["mes_key"].map(fmt_mes_label)
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=trend["mes_label"], y=trend["disp_media_pct"],
                name="Disponib. %", mode="lines+markers",
                line=dict(color="#4a9e3f", width=3), marker=dict(size=8),
            ))
            fig_trend.add_trace(go.Scatter(
                x=trend["mes_label"], y=trend["horas_trabalhadas"],
                name="H. operando", mode="lines+markers",
                line=dict(color="#2980b9", width=2), marker=dict(size=7),
                yaxis="y2",
            ))
            fig_trend.add_trace(go.Scatter(
                x=trend["mes_label"], y=trend["horas_parada"],
                name="H. parada (OS)", mode="lines+markers",
                line=dict(color="#c0392b", width=2, dash="dot"), marker=dict(size=6),
                yaxis="y2",
            ))
            fig_trend.update_layout(
                **PDARK, height=320,
                xaxis={**PLOT_AXIS},
                yaxis={**PLOT_AXIS, "title": "Disponib. %", "range": [0, 100]},
                yaxis2={**PLOT_AXIS, "title": "Horas", "overlaying": "y", "side": "right"},
                legend=dict(orientation="h", y=1.12, font=dict(color="#e8edd0")),
            )
            st.plotly_chart(fig_trend, use_container_width=True, key="k_trend")
    else:
        st.info("Sem resumo mensal — rode as views SQL no Supabase.")

    if not df_rank.empty:
        st.markdown(f'<div class="sec">Resumo Top 5 · {fmt_mes_label(mes_sel)}</div>', unsafe_allow_html=True)
        cols_rank = st.columns(4)
        for i, (titulo, col, fn) in enumerate([
            ("⚙️ Operando", "horas_trabalhadas", lambda v: f"{v:.0f}h"),
            ("🔴 Paradas", "horas_parada", lambda v: f"{v:.0f}h"),
            ("⛽ Litros", "litros", lambda v: f"{v:,.0f} L"),
            ("📈 L/h", "litros_h", lambda v: f"{v:.1f}"),
        ]):
            top1 = df_rank.nlargest(1, col)
            with cols_rank[i]:
                if not top1.empty:
                    lc = top1.iloc[0].get("label_curto") or label_curto(top1.iloc[0])
                    st.metric(titulo, fn(top1.iloc[0][col]), lc)

# ══════════════════════════════════════════════════════════════
# TAB PERÍODO MAI–JUN–JUL
# ══════════════════════════════════════════════════════════════
with tab_tri:
    st.markdown(
        f'<div class="sec">Resumo · {fmt_periodo_label(periodo_sel)}</div>',
        unsafe_allow_html=True,
    )
    meses_label = " · ".join(fmt_mes_label(m) for m in meses_tri) if meses_tri else "—"
    st.caption(
        f"Meses: {meses_label} — bloco fixo de coleta inicial (não usa trimestre civil). "
        f"Operação linear: apontamento_campo em tempo real · mín. {MIN_DIAS_APONT_MES}d/mês · "
        f"exclui colheitadeiras e frotas esporádicas."
    )

    if not meses_tri:
        st.warning(f"Sem meses com coleta (base desde {fmt_mes_label(MES_INICIO_COLETA)}).")
    elif df_frota_tri.empty:
        st.warning("Sem apontamento no período para as categorias selecionadas.")
    else:
        s500_sub = fmtR(custo_s500_tri) if custo_s500_tri > 0 else f"{fmt(litros_s500_tri)} L"
        kpi_grid([
            ("⚙️ H. operando", f"{fmt(ht_tri)}h", f"{len(meses_tri)} meses"),
            ("⛽ Litros", f"{fmt(litros_tri)} L", f"L/h {lh_tri:.1f}" if ht_tri > 0 else ""),
            ("🔧 Custo parada", fmtR_curto(custo_parada_tri), "mec + operador"),
            ("🔩 Peças + MO", fmtR_curto(custo_pecas_tri + custo_mo_tri), "financeiro_os"),
            ("💰 Manutenção", fmtR_curto(custo_manut_tri), "parada + peças + MO"),
            ("⛽ S-500 adit.", f"{fmt(litros_s500_tri)} L" if litros_s500_tri > 0 else "—", s500_sub if litros_s500_tri > 0 else ""),
        ], cols=3)
        kpi_grid([
            ("📊 Disp. média", f"{df_frota_tri['disponibilidade_pct'].mean():.1f}%", "média frota"),
            ("🔧 OS", f"{int(df_frota_tri['total_os'].sum())}", "no período"),
            ("🏆 Lineares", f"{len(df_linear_tri)}", f"≥{MIN_DIAS_SEQ_LINEAR}d sem OS"),
        ], cols=3)

        if preco_s500 > 0 and litros_s500_tri > 0:
            st.caption(
                f"Custo S-500 estimado: {fmtR(custo_s500_tri)} "
                f"({fmt(litros_s500_tri)} L × R$ {preco_s500:.2f}/L)"
            )

        tr1, tr2 = st.columns([1.3, 1])
        with tr1:
            st.markdown('<div class="sec">Top 10 · horas operando</div>', unsafe_allow_html=True)
            fig_t10 = chart_top_n(
                df_frota_tri, "horas_trabalhadas",
                "", "#4a9e3f", n=10, fmt_fn=lambda v: f"{v:.0f}h",
            )
            if fig_t10:
                st.plotly_chart(fig_t10, use_container_width=True, key="k_tri_top10")

        with tr2:
            st.markdown('<div class="sec">Destaques do período</div>', unsafe_allow_html=True)
            for titulo, col, fn in [
                ("⚙️ Operando", "horas_trabalhadas", lambda v: f"{v:.0f}h"),
                ("🔴 Paradas", "horas_parada", lambda v: f"{v:.0f}h"),
                ("⛽ Consumo", "litros_uso", lambda v: f"{v:,.0f} L".replace(",", ".")),
                ("📈 L/h", "litros_h", lambda v: f"{v:.1f}"),
            ]:
                top1 = df_frota_tri.nlargest(1, col)
                if not top1.empty and top1.iloc[0][col] > 0:
                    st.markdown(
                        kpi_card(titulo, fn(top1.iloc[0][col]), top1.iloc[0]["label_curto"]),
                        unsafe_allow_html=True,
                    )

        tr3, tr4 = st.columns(2)
        with tr3:
            st.markdown('<div class="sec">Top 10 · consumo (L/h)</div>', unsafe_allow_html=True)
            df_lh = df_frota_tri[df_frota_tri["litros_h"] > 0]
            fig_lh_tri = chart_top_n(
                df_lh, "litros_h", "", "#2980b9", n=10,
                fmt_fn=lambda v: f"{v:.1f} L/h",
            )
            if fig_lh_tri:
                st.plotly_chart(fig_lh_tri, use_container_width=True, key="k_tri_lh")

        with tr4:
            st.markdown('<div class="sec">Treemap · custos de manutenção</div>', unsafe_allow_html=True)
            tm_c = []
            if custo_mec_tri > 0:
                tm_c.append({"tipo": "Mecânico (salário×h)", "valor": custo_mec_tri})
            if custo_op_tri > 0:
                tm_c.append({"tipo": "Operador (salário×h)", "valor": custo_op_tri})
            if custo_pecas_tri > 0:
                tm_c.append({"tipo": "Peças OS", "valor": custo_pecas_tri})
            if custo_mo_tri > 0:
                tm_c.append({"tipo": "MO registrada", "valor": custo_mo_tri})
            if tm_c:
                df_tm_c = pd.DataFrame(tm_c)
                fig_tm_c = px.treemap(
                    df_tm_c, path=["tipo"], values="valor",
                    color="valor", color_continuous_scale=["#1a3318", "#4a9e3f", "#d4a017", "#c0392b"],
                )
                fig_tm_c.update_layout(**PDARK, height=340)
                st.plotly_chart(fig_tm_c, use_container_width=True, key="k_tri_treemap")
            else:
                st.info("Sem custos registrados no período.")

        st.markdown('<div class="sec">Evolução · Mai · Jun · Jul</div>', unsafe_allow_html=True)
        if not df_resumo.empty:
            trend_tri = filtrar_meses_coleta(df_resumo)
            trend_tri = trend_tri[trend_tri["mes_key"].astype(str).isin(meses_tri)].sort_values("mes_key")
            if not trend_tri.empty:
                trend_tri["mes_label"] = trend_tri["mes_key"].map(fmt_mes_label)
                fig_mtri = go.Figure()
                fig_mtri.add_trace(go.Bar(
                    x=trend_tri["mes_label"], y=trend_tri["horas_trabalhadas"],
                    name="H. operando", marker_color="#4a9e3f",
                    text=trend_tri["horas_trabalhadas"].apply(lambda v: f"{v:.0f}h"),
                    textposition="outside", textfont=dict(color="#e8edd0", size=10),
                ))
                fig_mtri.add_trace(go.Scatter(
                    x=trend_tri["mes_label"], y=trend_tri["horas_parada"],
                    name="H. parada", mode="lines+markers",
                    line=dict(color="#c0392b", width=2), marker=dict(size=8),
                    yaxis="y2",
                ))
                fig_mtri.update_layout(
                    **PDARK, height=300, barmode="group",
                    xaxis={**PLOT_AXIS},
                    yaxis={**PLOT_AXIS, "title": "Horas operando"},
                    yaxis2={**PLOT_AXIS, "title": "Horas parada", "overlaying": "y", "side": "right"},
                    legend=dict(orientation="h", y=1.1, font=dict(color="#e8edd0")),
                )
                st.plotly_chart(fig_mtri, use_container_width=True, key="k_tri_trend")

        tr5, tr6 = st.columns([1.2, 1])
        with tr5:
            st.markdown(
                f'<div class="sec">Operação linear · apontamento_campo · {fmt_mes_label(mes_sel)}</div>',
                unsafe_allow_html=True,
            )
            df_lin_mes = df_linear_mes[df_linear_mes["elegivel"]].copy() if not df_linear_mes.empty else pd.DataFrame()
            if not df_lin_mes.empty:
                lin_m_show = pd.DataFrame({
                    "Trator": df_lin_mes["label_curto"],
                    "Dias apont.": df_lin_mes["dias_apontamento"],
                    "Dias s/ OS": df_lin_mes["dias_linear"],
                    "H. lineares": df_lin_mes["horas_linear"].apply(lambda v: f"{v:.0f}h"),
                    "Período": df_lin_mes["periodo"],
                })
                dark_table(lin_m_show, height=280)
            else:
                st.info(
                    f"Nenhum equipamento elegível em {fmt_mes_label(mes_sel)} "
                    f"(mín. {MIN_DIAS_APONT_MES} dias apontados, {MIN_DIAS_SEQ_LINEAR}d seguidos sem OS)."
                )

            st.markdown(
                f'<div class="sec">Operação linear · bloco {fmt_periodo_label(periodo_sel)}</div>',
                unsafe_allow_html=True,
            )
            if not df_linear_tri.empty:
                lin_show = pd.DataFrame({
                    "Trator": df_linear_tri["label_curto"],
                    "Dias apont.": df_linear_tri["dias_apontamento"],
                    "Dias s/ OS": df_linear_tri["dias_linear"],
                    "H. lineares": df_linear_tri["horas_linear"].apply(lambda v: f"{v:.0f}h"),
                    "Período": df_linear_tri["periodo"],
                })
                dark_table(lin_show, height=260)
            else:
                st.info("Nenhum equipamento com operação linear confiável no bloco Mai–Jun–Jul.")

            excl = df_linear_mes[~df_linear_mes["elegivel"]] if not df_linear_mes.empty else pd.DataFrame()
            if not excl.empty:
                with st.expander(f"Excluídos do linear em {fmt_mes_label(mes_sel)} ({len(excl)})"):
                    excl_show = excl[["label_curto", "dias_apontamento", "horas_total", "motivo_exclusao"]].rename(
                        columns={"label_curto": "Frota", "dias_apontamento": "Dias", "horas_total": "Horas", "motivo_exclusao": "Motivo"},
                    )
                    dark_table(excl_show, height=200)

        with tr6:
            st.markdown('<div class="sec">Radar · produtividade mecânicos</div>', unsafe_allow_html=True)
            fig_rad = chart_radar_mecanicos(
                df_parada_tri,
                "Horas OS · quantidade · custo (normalizado)",
            )
            if fig_rad:
                st.plotly_chart(fig_rad, use_container_width=True, key="k_tri_radar")
            else:
                st.info("Sem horas de mecânico no período.")

        st.markdown('<div class="sec">Tabela consolidada · frota no período</div>', unsafe_allow_html=True)
        tbl_tri = df_frota_tri.sort_values("horas_trabalhadas", ascending=False).head(25).copy()
        if not df_linear_tri.empty:
            tbl_tri = tbl_tri.merge(
                df_linear_tri[["id_frota", "dias_linear", "horas_linear", "periodo"]],
                on="id_frota", how="left", suffixes=("_x", ""),
            )
        tbl_tri_show = pd.DataFrame({
            "Trator": tbl_tri["label_curto"],
            "H. Operando": tbl_tri["horas_trabalhadas"].apply(lambda v: f"{v:.0f}h"),
            "H. Paradas": tbl_tri["horas_parada"].apply(lambda v: f"{v:.0f}h"),
            "Disp. %": tbl_tri["disponibilidade_pct"].apply(lambda v: f"{v:.1f}%"),
            "Litros": tbl_tri["litros_uso"].apply(lambda v: f"{v:,.0f} L".replace(",", ".")),
            "L/h": tbl_tri["litros_h"].apply(lambda v: f"{v:.1f}" if v > 0 else "—"),
            "Dias s/ OS": tbl_tri.get("dias_linear", pd.Series(0, index=tbl_tri.index)).apply(
                lambda v: f"{int(v)}" if pd.notna(v) and v else "—"
            ),
            "Período linear": tbl_tri.get("periodo", pd.Series("—", index=tbl_tri.index)),
        })
        dark_table(tbl_tri_show, height=400)

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
            st.caption(f"Apenas meses com coleta desde {fmt_mes_label(MES_INICIO_COLETA)}")
            df_hm = filtrar_cat(filtrar_meses_coleta(df_disp.copy()))
            meses_hm = [m for m in meses_com_coleta(df_apont, df_disp) if m >= MES_INICIO_COLETA][-n_meses_trend:]
            df_hm = df_hm[df_hm["mes_key"].astype(str).isin(meses_hm)]
            if not df_hm.empty:
                pivot = df_hm.pivot_table(
                    index="id_frota", columns="mes_key", values="disponibilidade_pct", aggfunc="mean",
                )
                # Top 12 frotas por horas no período (legível na reunião)
                horas_idx = df_hm.groupby("id_frota")["horas_trabalhadas"].sum()
                top_f = horas_idx.nlargest(12).index
                pivot = pivot.reindex(top_f).dropna(how="all")
                pivot = pivot.reindex(columns=sorted(pivot.columns))
                z = pivot.values.astype(float)
                txt = [[f"{v:.0f}%" if pd.notna(v) else "" for v in row] for row in z]
                fig_hm = go.Figure(go.Heatmap(
                    z=z,
                    x=[fmt_mes_label(c) for c in pivot.columns],
                    y=[label_trator({"id_frota": f, "modelo": df_hm.loc[df_hm["id_frota"] == f, "modelo"].iloc[0] if f in df_hm["id_frota"].values and "modelo" in df_hm.columns else ""}) for f in pivot.index],
                    colorscale=[[0, "#2a1010"], [0.7, "#2a2200"], [0.85, "#1a3318"], [1, "#4a9e3f"]],
                    zmin=0, zmax=100,
                    text=txt,
                    texttemplate="%{text}",
                    textfont=dict(size=11, color="#e8edd0"),
                    hovertemplate="%{y}<br>%{x}: %{z:.1f}%<extra></extra>",
                ))
                fig_hm.update_layout(
                    **PDARK, height=max(300, len(pivot) * 26),
                    xaxis={**PLOT_AXIS}, yaxis={**PLOT_AXIS, "tickfont": dict(size=10)},
                )
                st.plotly_chart(fig_hm, use_container_width=True, key="k_heatmap")

# ══════════════════════════════════════════════════════════════
# TAB 3 — CUSTOS & PEÇAS
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown(f'<div class="sec">Custos de manutenção · {fmt_mes_label(mes_sel)}</div>', unsafe_allow_html=True)
    st.caption(
        f"Gráficos rotineiros excluem eventos ≥ {fmtR(LIMITE_OUTLIER_CUSTO)} "
        "(ex.: revisão de motor). Eventos extraordinários aparecem na tabela abaixo."
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("🔩 Peças rotineiras", fmtR(custo_pecas_rot))
    c2.metric("🔧 MO registrada", fmtR(custo_mo))
    c3.metric("📄 NF-e rotineiras", fmtR(custo_lanc_rot))
    c4.metric("⏱ Custo parada", fmtR(custo_parada_tot))
    c5.metric("⚠️ Extraordinários", fmtR(custo_extra))
    c6.metric("💰 Total mês", fmtR(custo_pecas + custo_mo + custo_lanc + custo_parada_tot))

    if not df_extra_custos.empty:
        st.markdown('<div class="sec">Eventos extraordinários do mês</div>', unsafe_allow_html=True)
        extra_show = df_extra_custos.sort_values("valor", ascending=False).copy()
        extra_show["Valor"] = extra_show["valor"].apply(fmtR)
        dark_table(extra_show[["tipo", "referencia", "frota", "Valor"]].rename(columns={
            "tipo": "Tipo", "referencia": "Referência", "frota": "Frota",
        }), height=160)

    ct1, ct2 = st.columns(2)
    with ct1:
        st.markdown('<div class="sec">Top frotas · custos rotineiros</div>', unsafe_allow_html=True)
        tm_rows = []
        if not df_pecas_rot.empty:
            for fid, v in df_pecas_rot.groupby("id_frota")["custo_pecas"].sum().items():
                if v > 0:
                    tm_rows.append({"frota": str(fid), "tipo": "Peças", "valor": v})
        if not df_parada.empty:
            for fid, v in df_parada.groupby("id_frota")["_c_tot"].sum().items():
                if 0 < v < LIMITE_OUTLIER_CUSTO:
                    tm_rows.append({"frota": str(fid), "tipo": "Parada", "valor": v})
        if tm_rows:
            df_tm = pd.DataFrame(tm_rows)
            fig_tm = px.treemap(
                df_tm, path=["frota", "tipo"], values="valor",
                color="valor", color_continuous_scale=["#1a3318", "#4a9e3f", "#d4a017", "#c0392b"],
            )
            fig_tm.update_layout(**PDARK, height=320)
            st.plotly_chart(fig_tm, use_container_width=True, key="k_treemap")
        else:
            st.info("Sem custos rotineiros para treemap neste mês.")

    with ct2:
        st.markdown('<div class="sec">Peças por sistema (OS rotineiras)</div>', unsafe_allow_html=True)
        if not df_os_m.empty and not df_pecas_rot.empty:
            merged = df_pecas_rot.merge(
                df_os_m[["numero_os", "sistema"]].drop_duplicates(),
                on="numero_os", how="left",
            )
            rs = merged.groupby("sistema")["custo_pecas"].sum().reset_index().sort_values("custo_pecas", ascending=True).tail(10)
            if not rs.empty and rs["custo_pecas"].sum() > 0:
                fig_p = go.Figure(go.Bar(
                    y=rs["sistema"], x=rs["custo_pecas"], orientation="h",
                    marker_color="#2980b9",
                    text=rs["custo_pecas"].apply(fmtR), textposition="outside",
                    textfont=dict(color="#e8edd0"),
                ))
                fig_p.update_layout(**PDARK, height=320, xaxis={**PLOT_AXIS}, yaxis={**PLOT_AXIS})
                st.plotly_chart(fig_p, use_container_width=True, key="k_pecas_sis")
            else:
                st.info("Sem peças rotineiras por sistema.")
        else:
            st.info("Sem cruzamento OS × peças neste mês.")

    if not df_pecas_rot.empty:
        st.markdown('<div class="sec">Detalhe peças rotineiras por OS</div>', unsafe_allow_html=True)
        det = df_pecas_rot.sort_values("custo_pecas", ascending=False).head(25).copy()
        det_show = pd.DataFrame({
            "OS": det["numero_os"],
            "Frota": det["id_frota"],
            "Peças": det["custo_pecas"].apply(fmtR),
            "MO": det["custo_mo"].apply(fmtR),
            "Total OS": (det["custo_pecas"] + det["custo_mo"]).apply(fmtR),
        })
        dark_table(det_show, height=380)

# ══════════════════════════════════════════════════════════════
# TAB 4 — RANKING TRATORES
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown(f'<div class="sec">Ranking operacional · {fmt_mes_label(mes_sel)}</div>', unsafe_allow_html=True)
    st.caption(
        "Fonte operacional: apontamento_campo. Operação linear exige "
        f"≥{MIN_DIAS_APONT_MES} dias apontados/mês, ≥{MIN_DIAS_SEQ_LINEAR} dias seguidos sem OS — "
        "colheitadeiras e uso esporádico ficam de fora."
    )

    if df_rank.empty:
        st.warning("Sem apontamento no mês — verifique apontamento_campo.")
    else:
        tem_s500 = df_rank["litros_s500"].sum() > 0
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            fig_r1 = chart_top5(
                df_rank, "horas_trabalhadas",
                "Top 5 · horas operando", "#4a9e3f",
                lambda v: f"{v:.0f}h",
            )
            if fig_r1:
                st.plotly_chart(fig_r1, use_container_width=True, key="k_rank_op")
        with r1c2:
            fig_r2 = chart_top5(
                df_rank[df_rank["horas_parada"] > 0],
                "horas_parada",
                "Top 5 · horas paradas (OS)", "#c0392b",
                lambda v: f"{v:.0f}h",
            )
            if fig_r2:
                st.plotly_chart(fig_r2, use_container_width=True, key="k_rank_par")

        r2c1, r2c2 = st.columns(2)
        with r2c1:
            col_litros = "litros_s500" if tem_s500 else "litros"
            titulo_lit = "Top 5 · Diesel S-500 aditivado" if tem_s500 else "Top 5 · litros abastecidos"
            df_lit = df_rank[df_rank[col_litros] > 0]
            fig_r3 = chart_top5(
                df_lit, col_litros, titulo_lit, "#2980b9",
                lambda v: f"{v:,.0f} L".replace(",", "."),
            )
            if fig_r3:
                st.plotly_chart(fig_r3, use_container_width=True, key="k_rank_lit")
            elif not tem_s500:
                st.info("Sem detalhe S-500 — usando total de abastecimento na aba Combustível.")
        with r2c2:
            if not df_linear.empty:
                fig_r4 = chart_top_n(
                    df_linear, "horas_linear",
                    "Top 5 · operação linear", "#d4a017", n=5,
                    fmt_fn=lambda v: f"{v:.0f}h",
                )
                if fig_r4:
                    st.plotly_chart(fig_r4, use_container_width=True, key="k_rank_lin")
            else:
                st.info(
                    f"Nenhum equipamento elegível em {fmt_mes_label(mes_sel)} "
                    "(harvester/colheitadeira ou poucos dias apontados)."
                )

        st.markdown('<div class="sec">Tabela consolidada · frota</div>', unsafe_allow_html=True)
        tbl = df_rank.sort_values("horas_trabalhadas", ascending=False).head(20).copy()
        tbl_show = pd.DataFrame({
            "Trator": tbl["label"],
            "H. Operando": tbl["horas_trabalhadas"].apply(lambda v: f"{v:.0f}h"),
            "H. Paradas": tbl["horas_parada"].apply(lambda v: f"{v:.0f}h"),
            "Disp. %": tbl["disponibilidade_pct"].apply(lambda v: f"{v:.1f}%"),
            "Litros": tbl["litros"].apply(lambda v: f"{v:,.0f} L".replace(",", ".")),
            "S-500": tbl["litros_s500"].apply(lambda v: f"{v:,.0f} L".replace(",", ".") if v > 0 else "—"),
            "L/h": tbl["litros_h"].apply(lambda v: f"{v:.1f}" if v > 0 else "—"),
            "Dias s/ OS": tbl.get("dias_linear", pd.Series(0, index=tbl.index)).apply(lambda v: f"{int(v)}" if v else "—"),
            "Período linear": tbl.get("periodo", pd.Series("—", index=tbl.index)),
        })
        dark_table(tbl_show, height=420)

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
