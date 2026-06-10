"""
Дашборд аналитика Botamin.
Запуск:  .venv/bin/streamlit run app.py
"""
import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from data_pipeline import (
    load_and_process,
    STEP_NAMES,
    parse_turns,
    meeting_booked as calc_meeting_booked,
    preconsent_bot_reason as calc_preconsent_bot_reason,
    canonicalize_subcategory,
)

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "Calls Week Anon.csv")
PIPELINE_CACHE_VERSION = "2026-06-10-subcategory-dedup-v9"

st.set_page_config(page_title="Botamin · Дашборд аналитика", layout="wide",
                   initial_sidebar_state="expanded")

# ---------- стили ----------
st.markdown("""
<style>
.block-container {padding-top: 2rem; padding-bottom: 2rem;}
div[data-testid="stMetric"] {background:#f6f7fb; border:1px solid #e7e9f2;
    border-radius:14px; padding:14px 18px;}
div[data-testid="stMetric"] * {color:#1b1f3b !important;}
div[data-testid="stMetricValue"] {font-size:1.7rem; color:#1b1f3b !important;}
div[data-testid="stMetricLabel"] p {color:#475067 !important; font-weight:600;}
div[data-testid="stMetricDelta"] {color:#2e7d32 !important;}
.bubble-bot {background:#eef1ff;border-radius:12px;padding:8px 12px;margin:4px 0;}
.bubble-user {background:#f1f3f5;border-radius:12px;padding:8px 12px;margin:4px 0 4px 40px;}
.small {color:#6b7280;font-size:0.85rem;}
h1,h2,h3 {color:#1b1f3b;}
.frow {display:flex; gap:10px; flex-wrap:nowrap; overflow-x:auto;}
.fcard {flex:1; min-width:130px; background:#f6f7fb; border:1px solid #e7e9f2;
    border-radius:14px; padding:12px 14px;}
.fcard .nm {color:#475067; font-size:0.82rem; font-weight:600; margin-bottom:2px;}
.fcard .vl {color:#1b1f3b; font-size:1.5rem; font-weight:700; line-height:1.1;}
.badge {display:inline-block; border-radius:8px; padding:2px 8px; font-size:0.74rem;
    margin-top:6px; margin-right:4px;}
.b-through {background:#e6e9fb; color:#3a45b0;}
.b-prev {background:#e3f2e4; color:#2e7d32;}
.farrow {align-self:center; color:#b0b4c4; font-size:1.4rem;}
.stage {margin:10px 0 4px 0;}
.stage-h {font-size:0.95rem; font-weight:700; color:#1b1f3b; margin-bottom:4px;}
.stage-h .base {color:#6b7280; font-weight:500; font-size:0.82rem;}
.pbar {display:flex; width:100%; height:42px; border-radius:10px; overflow:hidden;
    border:1px solid #e7e9f2;}
.seg {display:flex; align-items:center; justify-content:center; color:#fff;
    font-size:0.82rem; font-weight:600; text-align:center; padding:0 6px;
    white-space:nowrap; overflow:hidden;}
.callout {font-size:0.82rem; color:#9a6b00; background:#fff7e6; border-radius:8px;
    padding:5px 10px; margin-top:5px; display:inline-block;}
.stage-arrow {color:#c2c6da; font-size:1.1rem; margin:2px 0 2px 6px;}
.legend {display:flex; flex-wrap:wrap; gap:6px 14px; margin-top:5px;
    font-size:0.8rem; color:#475067;}
.legend .dot {display:inline-block; width:10px; height:10px; border-radius:3px;
    margin-right:5px; vertical-align:middle;}
.catdescs {margin-top:6px;}
.catdesc {font-size:0.82rem; color:#5a5f73; margin:2px 0; line-height:1.35;}
.catdesc b {color:#1b1f3b;}
.summary {background:#f0f3ff; border:1px solid #d7dcfb; border-left:4px solid #4b57c9;
    border-radius:10px; padding:14px 18px; margin-bottom:14px; color:#1b1f3b;
    font-size:0.95rem; line-height:1.5;}
/* таблица проблем (ровно 5 колонок): «Размер» и «Массовость» шире, без переноса */
[data-testid="stTable"] table:has(thead th:nth-child(5)):not(:has(thead th:nth-child(6))) th:nth-child(3),
[data-testid="stTable"] table:has(thead th:nth-child(5)):not(:has(thead th:nth-child(6))) td:nth-child(3),
[data-testid="stTable"] table:has(thead th:nth-child(5)):not(:has(thead th:nth-child(6))) th:nth-child(4),
[data-testid="stTable"] table:has(thead th:nth-child(5)):not(:has(thead th:nth-child(6))) td:nth-child(4) {
    white-space:nowrap; text-align:center;}
[data-testid="stTable"] table:has(thead th:nth-child(5)):not(:has(thead th:nth-child(6))) th:nth-child(3),
[data-testid="stTable"] table:has(thead th:nth-child(5)):not(:has(thead th:nth-child(6))) td:nth-child(3) {min-width:130px;}
[data-testid="stTable"] table:has(thead th:nth-child(5)):not(:has(thead th:nth-child(6))) th:nth-child(4),
[data-testid="stTable"] table:has(thead th:nth-child(5)):not(:has(thead th:nth-child(6))) td:nth-child(4) {min-width:115px;}
/* таблица A/B-идей (ровно 4 колонки): фикс-ширины + буллеты метрик с новой строки */
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) {
    table-layout:fixed; width:100%;}
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) td,
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) th {
    white-space:pre-line; vertical-align:top; word-break:break-word;}
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) th:nth-child(1),
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) td:nth-child(1) {width:28%;}
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) th:nth-child(2),
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) td:nth-child(2) {width:20%;}
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) th:nth-child(3),
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) td:nth-child(3) {width:26%;}
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) th:nth-child(4),
[data-testid="stTable"] table:has(thead th:nth-child(4)):not(:has(thead th:nth-child(5))) td:nth-child(4) {width:26%;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Загружаю и размечаю звонки…")
def get_data(_cache_version: str):
    return load_and_process(DATA_PATH)


df_all = get_data(PIPELINE_CACHE_VERSION)

# Поддержка старого кэша Streamlit: если в кэше лежит датафрейм без новых
# колонок, достраиваем их на месте, чтобы дэш не падал при обновлении логики.
if "meeting_booked" not in df_all.columns:
    df_all["meeting_booked"] = df_all.apply(
        lambda r: calc_meeting_booked(r["dialog"], r["reached_step"]), axis=1)
if "preconsent_bot_reason" not in df_all.columns:
    prebot = df_all["dialog"].apply(calc_preconsent_bot_reason)
    df_all["preconsent_bot_reason"] = prebot.where(
        (df_all["reached_step"] < 2) & (df_all["reason"] == "bot_hangup") & ~df_all["is_ao"],
        other=None)
else:
    df_all.loc[df_all["is_ao"], "preconsent_bot_reason"] = None

for col in ["objection", "nobook_reason", "preconsent_bot_reason", "offer_refuse_reason"]:
    if col in df_all.columns:
        df_all[col] = df_all[col].map(canonicalize_subcategory)

# ======================= SIDEBAR / ФИЛЬТРЫ =======================
st.sidebar.title("Фильтры")

dmin, dmax = df_all["dt"].min(), df_all["dt"].max()
date_range = st.sidebar.date_input("Период", (dmin.date(), dmax.date()),
                                   min_value=dmin.date(), max_value=dmax.date())
wd_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
wd_ru = {"Monday": "Пн", "Tuesday": "Вт", "Wednesday": "Ср", "Thursday": "Чт",
         "Friday": "Пт", "Saturday": "Сб", "Sunday": "Вс"}
present_wd = [w for w in wd_order if w in df_all["weekday_name"].unique()]
sel_wd = st.sidebar.multiselect("День недели", present_wd,
                                default=present_wd, format_func=lambda w: wd_ru[w])
hr = st.sidebar.slider("Часы звонка", 0, 23, (int(df_all["hour"].min()), int(df_all["hour"].max())))
reasons = sorted(df_all["reason"].unique())
sel_reason = st.sidebar.multiselect("Причина завершения", reasons, default=reasons)
max_ci = int(df_all["call_index"].max())
ORD = {1: "1-й (первый)", 2: "2-й (перезвон)", 3: "3-й", 4: "4-й", 5: "5-й", 6: "6-й", 7: "7-й"}
call_nums = st.sidebar.multiselect(
    "Какой по счёту звонок контакту", options=list(range(1, max_ci + 1)), default=[],
    format_func=lambda i: ORD.get(i, f"{i}-й"),
    help="Каждому номеру звонят несколько раз. Здесь выбираете, какие по счёту звонки "
         "показывать. Пусто = все. Например «1-й» — только первые звонки, без перезвонов.")

st.sidebar.divider()
st.sidebar.caption("**Срез знаменателя**")
unit = st.sidebar.radio("Считать по", ["Звонкам", "Контактам (уник. номер)"],
                        label_visibility="collapsed")

st.sidebar.divider()
st.sidebar.caption("**Верх воронки** (нет в выгрузке — из телефонии/CRM)")
n_contacts = int(df_all["phone"].nunique())
base_size = st.sidebar.number_input("Размер базы (контактов)", min_value=n_contacts,
                                    value=n_contacts, step=500,
                                    help="В файле только соединившиеся звонки. ""Размер всей базы задаётся вручную — ""иначе % обзвона не посчитать.")
rate = st.sidebar.number_input("Стоимость минуты (наша), ₽", min_value=0.0,
                               value=10.0, step=1.0,
                               help="Фактическая поминутная стоимость обзвона (что платим мы).")
revenue = st.sidebar.number_input("Выручка с минуты (платит клиент), ₽", min_value=0.0,
                                  value=20.0, step=1.0,
                                  help="Сколько клиент платит нам за минуту. Маржа = выручка − стоимость.")

# применяем фильтры
m = (
    (df_all["dt"].dt.date >= date_range[0]) &
    (df_all["dt"].dt.date <= (date_range[1] if len(date_range) > 1 else date_range[0])) &
    (df_all["weekday_name"].isin(sel_wd)) &
    (df_all["hour"].between(hr[0], hr[1])) &
    (df_all["reason"].isin(sel_reason))
)
df = df_all[m].copy()
if call_nums:
    df = df[df["call_index"].isin(call_nums)]
unit_is_contacts = unit.startswith("Контакт")
if unit.startswith("Контакт"):
    # По контакту берём «лучший» звонок: максимальный шаг, а при равенстве самый поздний.
    df = (df.sort_values(["phone", "reached_step", "dt"])
            .groupby("phone", as_index=False)
            .last())

# ======================= ШАПКА =======================
st.title("Дашборд аналитика проекта")
st.caption(f"Период данных: {dmin:%d.%m.%Y} – {dmax:%d.%m.%Y} · "f"в выборке после фильтров: **{len(df):,}** записей".replace(",", " "))

# ---------- расчёт воронки (звонки, для секций ниже) ----------
N = len(df)
has_dlg = int(df["has_dialog"].sum())
s2 = int((df["reached_step"] >= 2).sum())
s3 = int((df["reached_step"] >= 3).sum())
s4 = int((df["reached_step"] >= 4).sum())


def pct(a, b):
    return f"{a / b * 100:.1f}%" if b else "—"


def fnum(x):
    return f"{int(x):,}".replace(",", " ")


def audio_link(r):
    a = r.get("audio")
    return f" · <a href='{a}' target='_blank'>аудиозапись</a>" if isinstance(a, str) and a else ""


def show_examples(sub, n=2):
    """Отрендерить n примеров диалогов с транскриптом."""
    for _, r in sub.head(n).iterrows():
        st.markdown(f"<span class='small'>{r['dt']:%d.%m %H:%M} · {r['dur_raw']} · "
                    f"{r['reason']} · тел {r['phone']}{audio_link(r)}</span>",
                    unsafe_allow_html=True)
        for spk, utt in parse_turns(r["dialog"]):
            cls = "bubble-bot" if spk == "bot" else "bubble-user"
            who = "bot" if spk == "bot" else "клиент"
            st.markdown(f"<div class='{cls}'><b>{who}:</b> {utt or '—'}</div>",
                        unsafe_allow_html=True)
        st.markdown("<hr style='margin:6px 0'>", unsafe_allow_html=True)


# ---------- расчёт воронки по выбранной единице анализа ----------
fsrc = df.copy()
unit_note = ("показаны только " + ", ".join(ORD.get(i, f"{i}-й") for i in sorted(call_nums))
             + " звонки контакту" if call_nums else "по звонкам (с учётом перезвонов)")
unit_noun = "контактов" if unit_is_contacts else "звонков"
n_calls = len(fsrc)
dialed = int(fsrc["phone"].nunique())             # обзвонено контактов (для % базы)
fsrc["live_human_answer"] = (~fsrc["no_pickup"] & ~fsrc["is_ao"]).astype(int)
repeats = fsrc[fsrc["call_index"] >= 2]
wrong_person_all = fsrc[fsrc["gave_contact"] & ~fsrc["is_ao"]]
nwp_all = len(wrong_person_all)

vz = fsrc[~fsrc["no_pickup"]]                     # взяли трубку
n_vz = len(vz)
ao = vz[vz["is_ao"]]                              # автоответчик / автоматика
n_ao = len(ao)
human = vz[~vz["is_ao"]]                          # точно пошли в ветку «человек»
n_human = len(human)

# Служебный индикатор для АМД-ошибки оставляем отдельно, но он больше не задаёт ветку воронки.
amd_mask = (vz["reason"] == "bot_hangup") & (vz["dur_sec"] <= 10)
amd_err = int(amd_mask.sum())
amd_live = int((vz[amd_mask]["n_user_real"] >= 1).sum())

# Человек -> короткий отказ / дослушали первый заход
human_short_mask = ((human["reason"] == "client_hangup")
                    & human["dur_sec"].between(1, 10))
human_short = int(human_short_mask.sum())
cont1 = human[~human_short_mask]                  # дослушали первый заход
n_cont1 = len(cont1)

# Дослушали первый заход -> отказ / прошли 1 этап
consent = cont1[cont1["reached_step"] >= 2]       # прошли 1 этап
n_consent = len(consent)
no_consent_bot_mask = ((cont1["reached_step"] < 2) & (cont1["reason"] == "bot_hangup"))
no_consent_bot_df = cont1[no_consent_bot_mask]
no_consent_bot = int(no_consent_bot_mask.sum())
bot_drop_consent = int((no_consent_bot_mask & cont1["said_consent"] & ~cont1["refused"]).sum())
n_short_refuse = n_cont1 - n_consent - no_consent_bot   # человек не дал согласие на разговор

# Прошли 1 этап -> отказ / вышли на шаг встречи
to_meeting_step = consent[consent["reached_step"] >= 3]
n_to_meeting_step = len(to_meeting_step)
at_offer = consent[consent["reached_step"] == 2]    # отказ на 2 этапе
stage2_refuse = len(at_offer)
nc_mask = at_offer["gave_contact"]
new_contacts = int(nc_mask.sum())
rest_offer = at_offer[~nc_mask]
# бот скинул на оффере = бот завершил, но клиент НЕ отказывался (иначе это отказ клиента)
offer_bot_drop = int(((rest_offer["reason"] == "bot_hangup") & ~rest_offer["refused"]).sum())
offer_refuse = len(rest_offer) - offer_bot_drop                      # отказ клиента на оффере

# Шаг встречи -> реально назначили / не назначили
booked = to_meeting_step[to_meeting_step["meeting_booked"]]
n_booked = len(booked)
meeting_not_booked = to_meeting_step[~to_meeting_step["meeting_booked"]]
n_meeting_not_booked = len(meeting_not_booked)

# Назначили встречу -> дали квалификацию / без квалификации
to_qual = booked[booked["reached_step"] >= 4]
n_to_qual = len(to_qual)
n_booked_noqual = n_booked - n_to_qual

# ---------- сводные показатели по всем звонкам ----------
total_min = fsrc["dur_sec"].sum() / 60
spend = total_min * rate
margin_min = revenue - rate
margin_total = total_min * margin_min
econ_state = "в плюс" if margin_min >= 0 else "в убыток"
econ_color = "#2e7d32" if margin_min >= 0 else "#d9534f"
botbot = int(fsrc["is_botbot"].sum())
ao_calls = int(fsrc["is_ao"].sum())
neg = int(fsrc["negative"].sum())
dropped = int(fsrc["bot_dropped_willing"].sum())
good = n_booked                                    # успешные = встреча действительно назначена
quality_loops = int(fsrc["bot_loop"].sum())
quality_silent = int(fsrc["bot_silent"].sum())
quality_industry_bug = int(fsrc["industry_bug"].sum())

call_counts_per_contact = fsrc.groupby("phone").size()
avg_calls_per_contact = call_counts_per_contact.mean() if len(call_counts_per_contact) else 0
median_calls_per_contact = call_counts_per_contact.median() if len(call_counts_per_contact) else 0
share_repeat_contacts = ((call_counts_per_contact >= 2).mean() if len(call_counts_per_contact) else 0)
repeat_dist = (call_counts_per_contact.value_counts()
               .sort_index()
               .rename_axis("calls_per_contact")
               .reset_index(name="contacts"))
call_index_dist = (fsrc["call_index"].value_counts()
                   .sort_index()
                   .rename_axis("call_index")
                   .reset_index(name="calls"))

stage_losses = [
    ("Не дозвонились", nopickup_n := n_calls - n_vz, n_calls),
    ("АО / автоматика", n_ao, n_vz),
    ("Короткий отказ", human_short, n_human),
    ("Не дал согласие на разговор", n_short_refuse + no_consent_bot, n_cont1),
    ("Отказ на 2 этапе", stage2_refuse, n_consent),
    ("Встреча не назначена", n_meeting_not_booked, n_to_meeting_step),
]
top_loss_name, top_loss_value, top_loss_base = max(stage_losses, key=lambda x: x[1]) if stage_losses else ("—", 0, 0)

if top_loss_name == "Не дал согласие на разговор":
    top_loss_detail = (
        f"Из них {fnum(n_short_refuse)} {unit_noun} завершил клиент и "
        f"{fnum(no_consent_bot)} {unit_noun} прервал бот."
    )
elif top_loss_name == "Отказ на 2 этапе":
    stage2_parts = [
        ("нецелевой / редирект", new_contacts),
        ("бот сам завершил", offer_bot_drop),
        ("клиент отказался", offer_refuse),
    ]
    stage2_top_name, stage2_top_value = max(stage2_parts, key=lambda x: x[1])
    top_loss_detail = f"Крупнейшая причина внутри этапа: {stage2_top_name} — {fnum(stage2_top_value)}."
elif top_loss_name == "Встреча не назначена":
    top_loss_detail = "Бот вышел на шаг встречи, но явной фиксации времени/даты в диалоге не было."
else:
    top_loss_detail = ""

# ======================= САММАРИ =======================
report_dt = datetime.now().strftime("%d.%m.%Y %H:%M")
summary = (
    f"<div class='summary'>"
    f"<b>Саммари.</b> В текущем срезе {fnum(n_calls)} {unit_noun} ({fnum(dialed)} уник. контактов): "
    f"дозвонились до {fnum(n_vz)}, автоответчики/автоматика — {fnum(n_ao)}, "
    f"назначили встречу — <b>{fnum(good)}</b>, до квалификации дошли — <b>{fnum(n_to_qual)}</b>. "
    f"<span class='prio'><b>Главный обрыв сейчас:</b> {top_loss_name} — "
    f"{fnum(top_loss_value)} {unit_noun} ({pct(top_loss_value, top_loss_base)} от своей базы). "
    f"{top_loss_detail}</span> "
    f"Где бот сам теряет диалог: {fnum(dropped)} потерянных разговоров, "
    f"{fnum(no_consent_bot)} обрывов до 2 этапа и {fnum(offer_bot_drop)} обрывов на 2 этапе. "
    f"По юнит-экономике работаем "
    f"<span style='color:{econ_color};font-weight:700'>{econ_state}</span>: "
    f"{margin_min:+.0f} ₽ с минуты разговора, суммарно {margin_total:+,.0f} ₽ за выбранный период."
    f"</div>")
summary = summary.replace(",", " ")

GREEN, RED, AMBER = "#4b9f5e", "#d9534f", "#e8a33d"
undialed_contacts = max(int(base_size) - dialed, 0)


def render_stage(title, segments, last=False):
    total = sum(c for _, c, _, _ in segments)
    bars, legend, descs = "", "", ""
    for label, cnt, color, desc in segments:
        if cnt <= 0:
            continue
        w = cnt / total * 100 if total else 0
        inner = f"{label}<br>{fnum(cnt)} · {w:.0f}%" if w >= 14 else f"{fnum(cnt)}"
        bars += (f"<div class='seg' style='width:{w:.2f}%;background:{color}' "
                 f"title='{label}: {fnum(cnt)} ({w:.1f}%)'>{inner}</div>")
        legend += (f"<span><span class='dot' style='background:{color}'></span>"
                   f"{label} — {fnum(cnt)} ({w:.0f}%)</span>")
        if desc:
            descs += (f"<div class='catdesc'><span class='dot' style='background:{color}'></span>"
                      f"<b>{label}:</b> {desc}</div>")
    arrow = "" if last else "<div class='stage-arrow'>↓</div>"
    st.markdown(f"<div class='stage'><div class='stage-h'>{title} "
                f"<span class='base'>· всего {fnum(total)}</span></div>"
                f"<div class='pbar'>{bars}</div>"
                f"<div class='legend'>{legend}</div>"
                f"<div class='catdescs'>{descs}</div></div>{arrow}",
                unsafe_allow_html=True)

dashboard_tabs = st.tabs([
    "Саммари",
    "Воронка",
    "Рекомендации",
    "Повторные звонки",
    "База и время",
    "Качество робота",
    "Диалоги",
    "Поиск по номеру",
])

with dashboard_tabs[0]:
    st.markdown(summary, unsafe_allow_html=True)

# ======================= ГЛАВНЫЕ МЕТРИКИ =======================
    st.subheader("Главные метрики")
    st.caption(f"Отчёт обновлён: {report_dt}. Период и фильтры — в панели слева.")

    # ряд 1: верхние KPI
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Обзвон базы", pct(dialed, base_size),
              help=f"Уникальных номеров в выборке ({fnum(dialed)}) ÷ размер базы ({fnum(base_size)}).")
    m2.metric("Назначили встречу", pct(good, n_calls),
              help="В диалоге есть явная фиксация времени/даты встречи или бот уже дошёл до квалификации.")
    m3.metric("Потерянные разговоры", pct(dropped, n_calls),
              help="Бот завершил разговор после реплики живого клиента, хотя тот не отказывался.")
    m4.metric("Доля АО", pct(ao_calls, n_calls),
              help="Все «не живой человек»: быстрый AMD 1–4 сек без ответа + молчаливая автоматика + бот-бот + автоматика по тексту.")
    m5.metric("Негатив", pct(neg, n_calls),
              help="Явный отказ/грубость в репликах клиента.")

    # ряд 2: экономика
    k1, k2 = st.columns(2)
    k1.metric("Стоимость минуты", f"{rate:.0f} ₽", help=f"Расход за период: {fnum(spend)} ₽.")
    k2.metric("Маржа с минуты", f"{margin_min:.0f} ₽",
              help=f"Выручка с минуты − стоимость минуты = {revenue:.0f} − {rate:.0f} = {margin_min:.0f} ₽.")

with dashboard_tabs[2]:
    # ---- данные для таблицы «Текущие проблемы» ----
    flagged_ao = int((df["reason"] == "answering_machine").sum())
    analytic_ao = int(df["is_ao"].sum())
    extra_ao = max(analytic_ao - flagged_ao, 0)
    repeat_ao_share = (repeats["is_ao"].mean() * 100) if len(repeats) else 0
    secretary_cases = int((df["machine_type"] == "Виртуальный секретарь").sum())
    conf_cases = int((df["preconsent_bot_reason"] == "Связь / не понял бота").sum()) + int((df["nobook_reason"] == "Связь / не понял бота").sum())
    script_break = int((df["bot_error_type"] == "Не по скрипту").sum())
    ao_note = (f"Робот/телефония пометили только {fnum(flagged_ao)}, аналитика нашла "
               f"ещё {fnum(extra_ao)} сверху. Особенно много АО на перезвонах — "
               f"в автоматику уходит {repeat_ao_share:.1f}% повторных звонков")
    redirect_note = "Часть базы ведёт не к нужному ЛПР"
    # (размер в звонках, название, как читается) — сортируем по размеру, приоритет = ранг
    problems_raw = [
        (analytic_ao, "АО не распознаются роботом как АО", ao_note),
        (quality_industry_bug, "В базе не хватает индустрии",
         "Пустая подстановка ломает оффер и делает скрипт нерелевантным"),
        (conf_cases, "Проблемы связи / бот не понятен клиенту",
         "Явные срывы диалога из-за шума, связи, ветра или непонятной речи бота (минимум по явным кейсам)"),
        (quality_silent, "Молчание бота / dead air",
         "Отдельный технический дефект, не сводящийся к зацикливанию"),
        (dropped, "Потерянные разговоры",
         "Человек не отказывался, но бот всё равно завершил диалог"),
        (quality_loops, "Бот зацикливается",
         "Нужна правка логики, чтобы бот не повторялся и не зависал в одном сценарии"),
        (nwp_all, "Не тот человек / редирект", redirect_note),
        (secretary_cases, "Общий номер компании принимается за человека",
         "Бот говорил не с ЛПР, а с общей линией / секретарём (подтв. виртуальные секретари)"),
        (script_break, "Бот не соблюдает скрипт",
         "Вместо штатного опенера звучит off-script заход про «хочу к вам в продажи»"),
    ]
    problems_raw.sort(key=lambda r: r[0], reverse=True)
    robot_problems = pd.DataFrame([
        {
            "Приоритет": i + 1,
            "Проблема": name,
            "Размер": f"{fnum(n)} звонков",
            "Массовость": pct(n, len(df)),
            "Как читается": note,
        }
        for i, (n, name, note) in enumerate(problems_raw)
    ])

    # ---- A/B-тесты (одна гипотеза = одно изменение) ----
    lost_offers = max(n_cont1 - n_consent, 0)

    def bullets(items):
        return "\n".join(f"• {x}" for x in items)

    st.subheader("Идеи A/B-тестов")
    st.caption("Каждая гипотеза проверяет ровно одно изменение в скрипте бота.")
    ab_tests = pd.DataFrame([
        {
            "Проблема": (f"Клиенты отваливаются в начале — из {fnum(n_cont1)} дослушавших начало "
                         f"до оффера доходят {fnum(n_consent)}, теряем {fnum(lost_offers)} офферов "
                         f"({pct(lost_offers, n_cont1)})"),
            "Гипотеза": "Убрать ранний запрос согласия («секунду уделите?») из начала разговора, "
                        "не меняя остальной скрипт.",
            "Метрики": bullets([
                "Доля прошедших 1 этап среди дослушавших начало",
                "Доля дошедших до оффера",
            ]),
            "Гард-метрики": bullets([
                "Доля ранних отказов",
                "Доля «не понял бота / связь»",
                "Конверсия из оффера во встречу",
            ]),
        },
        {
            "Проблема": (f"Бот сам бросает вовлечённых клиентов при паузе, шуме или неуверенном ответе — "
                         f"{fnum(dropped)} потерянных разговоров, {fnum(bot_drop_consent)} обрывов после "
                         f"согласия и {fnum(offer_bot_drop)} после оффера, хотя клиент не отказывался"),
            "Гипотеза": "При первой паузе или шуме бот один раз переспрашивает вместо завершения звонка.",
            "Метрики": bullets([
                "Доля потерянных разговоров",
                "Доля встреч среди услышавших оффер",
            ]),
            "Гард-метрики": bullets([
                "Средняя длительность звонка",
                "Доля негатива",
                "Доля зацикливаний",
            ]),
        },
        {
            "Проблема": (f"После оффера мало кто соглашается на встречу — из {fnum(n_consent)} услышавших "
                         f"оффер встречу назначили {fnum(n_booked)} ({pct(n_booked, n_consent)})"),
            "Гипотеза": "Вместо общего предложения созвониться предлагать готовое время на выбор "
                        "(«вторник в 15:00 или среда в 11:00?»).",
            "Метрики": bullets([
                "Доля назначивших встречу среди услышавших оффер",
                "Число встреч",
            ]),
            "Гард-метрики": bullets([
                "Доля отказов после оффера",
                "Доля нецелевых / редиректов",
            ]),
        },
    ])
    ab_cols = ["Гипотеза", "Метрики", "Гард-метрики"]
    st.table(ab_tests.set_index("Проблема")[ab_cols])

    st.divider()

    st.markdown("**Текущие проблемы**")
    st.table(robot_problems.set_index("Приоритет"))

with dashboard_tabs[1]:
    st.subheader("Воронка по этапам бота")
    st.caption(f"Срез: {unit_note}.")

    render_stage("База (контакты)", [
        ("База", dialed, GREEN, "контакты из базы, которые обзвонили"),
        ("Ещё не обзвонено", undialed_contacts, "#c2c6da",
         "контакты из базы, до которых ещё не дозванивались"),
    ])
    render_stage("Из базы → обзвон", [
        ("Дозвонились", n_vz, GREEN, "кто-то взял трубку"),
        ("Не дозвонились", nopickup_n, RED, "нет соединения"),
    ])
    render_stage("Из дозвонившихся", [
        ("АО / автоматика", n_ao, RED, "на линии автоматика или не-живой сценарий"),
        ("Человек", n_human, GREEN, "живой разговор"),
    ])
    render_stage("Из ветки «человек»", [
        ("Короткий отказ", human_short, AMBER, "сброс в первые 10 секунд"),
        ("Дослушали первый заход", n_cont1, GREEN, "клиент остался на линии"),
    ])
    render_stage("Из тех, кто дослушал первый заход", [
        ("Человек не дал согласие на разговор", n_short_refuse, RED, "услышал старт, но не пошёл дальше"),
        ("Бот прервал до 2 этапа", no_consent_bot, "#c97b3d", "бот завершил разговор до оффера"),
        ("Прошли 1 этап", n_consent, GREEN, "бот дошёл до оффера"),
    ])
    render_stage("Из прошедших 1 этап", [
        ("Нецелевой / редирект", new_contacts, AMBER, "вышли не на того человека"),
        ("Бот сам завершил разговор", offer_bot_drop, "#c97b3d", "оффер прозвучал, но разговор завершил бот"),
        ("Клиент отказался на 2 этапе", offer_refuse, RED, "клиент услышал оффер и не пошёл дальше"),
        ("Вышли на шаг встречи", n_to_meeting_step, GREEN, "разговор дошёл до обсуждения встречи"),
    ])
    render_stage("Из вышедших на шаг встречи", [
        ("Встреча не назначена", n_meeting_not_booked, RED, "в диалоге нет явной фиксации времени"),
        ("Назначили встречу", n_booked, GREEN, "есть время/дата или бот дошёл до квалификации"),
    ])
    render_stage("Из назначивших встречу", [
        ("Без квалификации", n_booked_noqual, GREEN, "встречу зафиксировали, но не дошли до квалификации"),
        ("Дали квалификацию", n_to_qual, "#2f855a", "самый глубокий успешный проход"),
    ], last=True)

    st.markdown("**Примеры по проблемным категориям:**")
    ex_cats = [
        (f"Потерянные разговоры — {fnum(dropped)}", fsrc[fsrc["bot_dropped_willing"]], 3),
        (f"Бот прервал до 2 этапа — {fnum(no_consent_bot)}", no_consent_bot_df, 2),
        (f"Бот сам завершил разговор — {fnum(offer_bot_drop)}", rest_offer[(rest_offer["reason"] == "bot_hangup") & ~rest_offer["refused"]], 2),
        (f"Встреча не назначена — {fnum(n_meeting_not_booked)}", meeting_not_booked, 2),
    ]
    for cap, pop, nex in ex_cats:
        with st.expander(cap):
            show_examples(pop, n=nex) if len(pop) else st.caption("Нет звонков в этой категории за выбранный период.")

    st.divider()
    st.subheader("Почему после оффера не переходят к назначению встречи")
    st.caption("Только звонки, где оффер уже прозвучал, но разговор не дошёл до назначенной встречи.")
    nb = at_offer["nobook_reason"].value_counts()
    if len(nb):
        OUR_FAULT = {
            "Связь / не понял бота",
            "Молчание бота / dead air",
            "Зацикливание / ошибка логики",
            "Клиент замолчал, бот завершил",
            "Бот сам завершил без явной причины",
        }
        bar_colors = ["#d9534f" if r in OUR_FAULT else "#6f7ad6" for r in nb.index]
        fignb = go.Figure(go.Bar(
            y=nb.index[::-1], x=nb.values[::-1], orientation="h",
            marker_color=bar_colors[::-1], text=nb.values[::-1], textposition="auto"))
        fignb.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title="звонков", font=dict(color="#1b1f3b"))
        st.plotly_chart(fignb)
        our = int(sum(v for r, v in nb.items() if r in OUR_FAULT))
        st.caption(
            f"Красное — потери, где проблема похожа на ошибку бота или качество диалога: "
            f"{fnum(our)} из {fnum(int(nb.sum()))} ({pct(our, int(nb.sum()))}). "
            f"Синие — клиентский отказ или редирект."
        )
        conn_confused = at_offer[at_offer["nobook_reason"] == "Связь / не понял бота"]
        with st.expander(f"Примеры: Связь / не понял бота — {fnum(len(conn_confused))}"):
            if len(conn_confused):
                show_examples(conn_confused, n=4)
            else:
                st.caption("Нет звонков в этой категории за выбранный период.")
        bot_no_reason = at_offer[at_offer["nobook_reason"] == "Бот сам завершил без явной причины"]
        with st.expander(f"Примеры: Бот сам завершил без явной причины — {fnum(len(bot_no_reason))}"):
            if len(bot_no_reason):
                show_examples(bot_no_reason, n=4)
            else:
                st.caption("Нет звонков в этой категории за выбранный период.")
        bot_silent_reason = at_offer[at_offer["nobook_reason"] == "Молчание бота / dead air"]
        with st.expander(f"Примеры: Молчание бота / dead air — {fnum(len(bot_silent_reason))}"):
            if len(bot_silent_reason):
                show_examples(bot_silent_reason, n=4)
            else:
                st.caption("Нет звонков в этой категории за выбранный период.")

    st.divider()
    st.subheader("Причины клиентского отказа на 2 этапе")
    offer_refuse_full = at_offer[~at_offer["gave_contact"]
                                 & ((at_offer["reason"] == "client_hangup") | at_offer["refused"])]
    orr = offer_refuse_full["offer_refuse_reason"].value_counts()
    if len(orr):
        colors_or = ["#9e9e9e" if r == "Молча бросил трубку" else "#d9534f" for r in orr.index]
        figor = go.Figure(go.Bar(
            y=orr.index[::-1], x=orr.values[::-1], orientation="h",
            marker_color=colors_or[::-1], text=orr.values[::-1], textposition="auto"))
        figor.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title="звонков", font=dict(color="#1b1f3b"))
        st.plotly_chart(figor)
        red_refuse_reasons = [r for r in orr.index if r != "Молча бросил трубку"]
        for reason_name in red_refuse_reasons:
            reason_examples = offer_refuse_full[offer_refuse_full["offer_refuse_reason"] == reason_name]
            with st.expander(f"Примеры: {reason_name} — {fnum(len(reason_examples))}"):
                if len(reason_examples):
                    show_examples(reason_examples, n=4)
                else:
                    st.caption("Нет звонков в этой категории за выбранный период.")

    st.divider()
    st.subheader("Автоответчики и машины (АО)")
    st.caption("Показываем отдельно, сколько звонков вообще не были разговором с живым человеком.")
    mc = int(df["is_machine"].sum())
    amd = int(df["amd_suspect"].sum())
    struct = int(df["bot_bot_struct"].sum())
    ao_all = int(df["is_ao"].sum())
    flagged_ao = int((df["reason"] == "answering_machine").sum())
    analytic_extra_ao = max(ao_all - flagged_ao, 0)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("АО, помеченные роботом / телефонией", fnum(flagged_ao),
              help="То, что уже пришло в логе как `answering_machine`.")
    m2.metric("АО, найденные аналитически", fnum(ao_all),
              help="Все АО и автоматики после нашей аналитической досборки: текстовые маркеры, короткие AMD-сценарии, молчаливая автоматика и длинный робот-робот.")
    m3.metric("Добавили аналитикой сверх флага робота", fnum(analytic_extra_ao),
              help="Сколько АО не были явно помечены роботом/телефонией, но были найдены аналитически.")
    m4.metric("Мгновенные автоответчики без ответа клиента", fnum(amd),
              help="Очень короткие звонки 1–4 секунды, где бот сам завершил разговор и клиент не сказал ни одной реальной реплики.")
    st.caption(
        f"Сравнение: робот/телефония пометили как АО **{fnum(flagged_ao)}** звонков, "
        f"аналитически АО и автоматики насчитывается **{fnum(ao_all)}**, "
        f"то есть сверху было найдено ещё **{fnum(analytic_extra_ao)}** случаев."
    )
    a1, a2 = st.columns(2)
    a1.metric("Автоматика по явным фразам в диалоге", fnum(mc))
    a2.metric("Долгие разговоры с роботом вместо человека", fnum(struct))
    if mc:
        mt = df[df["is_machine"]]["machine_type"].value_counts()
        figm = px.bar(mt, orientation="h", text=mt.values,
                      color=mt.values, color_continuous_scale="Purples")
        figm.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10),
                           coloraxis_showscale=False, showlegend=False,
                           yaxis_title="", xaxis_title="звонков (подтв. по тексту)",
                           yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(figm)

with dashboard_tabs[3]:
    st.subheader("Повторные попытки")
    st.caption("Сколько раз звоним одному контакту и в каких сегментах чаще всего дожимаем перезвонами.")
    r1, r2, r3 = st.columns(3)
    r1.metric("Звонков на 1 контакт", f"{avg_calls_per_contact:.2f}",
              help=f"Медиана: {median_calls_per_contact:.0f}.")
    r2.metric("Контакты с 2+ звонками", pct((call_counts_per_contact >= 2).sum(), len(call_counts_per_contact)),
              help=f"{fnum((call_counts_per_contact >= 2).sum())} контактов получили повторный звонок.")
    r3.metric("Повторные звонки", pct(max(n_calls - dialed, 0), n_calls),
              help=f"{fnum(max(n_calls - dialed, 0))} из {fnum(n_calls)} {unit_noun}.")

    rr1, rr2 = st.columns(2)
    with rr1:
        fig_repeat = go.Figure(go.Bar(
            x=repeat_dist["calls_per_contact"].astype(str),
            y=repeat_dist["contacts"],
            marker_color="#6f7ad6",
            text=repeat_dist["contacts"],
            textposition="outside",
            cliponaxis=False,
        ))
        fig_repeat.update_layout(height=300, margin=dict(l=10, r=10, t=28, b=10),
                                 xaxis_title="Сколько звонков пришлось на контакт",
                                 yaxis_title="Контактов", yaxis=dict(rangemode="tozero"),
                                 font=dict(color="#1b1f3b"))
        st.plotly_chart(fig_repeat)
    with rr2:
        fig_call_index = go.Figure(go.Bar(
            x=call_index_dist["call_index"].astype(str),
            y=call_index_dist["calls"],
            marker_color="#c7cfeb",
            text=call_index_dist["calls"],
            textposition="outside",
            cliponaxis=False,
        ))
        fig_call_index.update_layout(height=300, margin=dict(l=10, r=10, t=28, b=10),
                                     xaxis_title="Какой по счёту звонок контакту",
                                     yaxis_title=f"{unit_noun.capitalize()}",
                                     yaxis=dict(rangemode="tozero"),
                                     font=dict(color="#1b1f3b"))
        st.plotly_chart(fig_call_index)

with dashboard_tabs[4]:
    st.subheader("Качество базы")
    wrong_person = fsrc[fsrc["gave_contact"] & ~fsrc["is_ao"]]
    wrong_comp = fsrc[fsrc["wrong_company"]]
    notprof = fsrc[fsrc["not_profile"]]
    nwp, nwc, nnp = len(wrong_person), len(wrong_comp), len(notprof)
    bad_mask = (fsrc["gave_contact"] & ~fsrc["is_ao"]) | fsrc["wrong_company"] | fsrc["not_profile"]
    bad_total = int(bad_mask.sum())
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Не тот человек", fnum(nwp), help=f"{pct(nwp, n_calls)} от всех {unit_noun}")
    b2.metric("Не работает в компании / ошиблись", fnum(nwc),
              help=f"{pct(nwc, n_calls)} от всех {unit_noun}")
    b3.metric("Не профиль / не наш бизнес", fnum(nnp),
              help=f"{pct(nnp, n_calls)} от всех {unit_noun}")
    b4.metric("Проблемных контактов всего", fnum(bad_total),
              help=f"{pct(bad_total, n_calls)} от всех {unit_noun}")
    st.caption(
        f"Доли по базе: не тот человек — {pct(nwp, n_calls)}, "
        f"ошиблись контактом — {pct(nwc, n_calls)}, "
        f"не профиль — {pct(nnp, n_calls)}, "
        f"всего проблемных — {pct(bad_total, n_calls)}."
    )

    st.divider()
    st.subheader("Когда чаще отвечает живой человек и назначают встречу")
    st.caption("Конверсия во встречу = `назначили встречу / все звонки в этот час`. Если в 14:00 было 100 звонков и 3 встречи, конверсия во встречу = 3%.")
    hourly = (
        fsrc.groupby("hour")
        .agg(
            calls=("phone", "size"),
            human_rate=("live_human_answer", "mean"),
            meeting_rate=("meeting_booked", "mean"),
            meetings=("meeting_booked", "sum"),
        )
        .reindex(range(24), fill_value=0)
        .reset_index()
    )
    hourly["human_pct"] = (hourly["human_rate"] * 100).round(1)
    hourly["meeting_pct"] = (hourly["meeting_rate"] * 100).round(1)
    hourly["hour_label"] = hourly["hour"].map(lambda h: f"{h:02d}:00")

    fig_time = go.Figure()
    fig_time.add_bar(x=hourly["hour_label"], y=hourly["calls"], name="Звонков",
                     marker_color="#d9deee", yaxis="y2",
                     hovertemplate="%{x}<br>звонков: %{y}<extra></extra>")
    fig_time.add_trace(go.Scatter(
        x=hourly["hour_label"], y=hourly["human_pct"], name="Ответил живой человек, %",
        mode="lines+markers", line=dict(color="#4b57c9", width=3),
        hovertemplate="%{x}<br>ответил живой человек: %{y}%<extra></extra>"))
    fig_time.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                           xaxis_title="Час звонка",
                           yaxis=dict(title="% звонков", rangemode="tozero"),
                           yaxis2=dict(title="Кол-во звонков", overlaying="y", side="right", rangemode="tozero"),
                           legend=dict(orientation="h", y=1.12, x=0),
                           font=dict(color="#1b1f3b"), barmode="overlay")
    st.plotly_chart(fig_time)

    meet_cols = st.columns([1, 2])
    meet_cols[0].metric("Назначили встречу", fnum(int(hourly["meetings"].sum())),
                        help=f"{pct(int(hourly['meetings'].sum()), n_calls)} от всех {unit_noun}.")
    best_hour_row = hourly.loc[hourly["meetings"].idxmax()] if len(hourly) else None
    meet_cols[1].metric(
        "Пиковый час по встречам",
        f"{best_hour_row['hour_label']}" if best_hour_row is not None else "—",
        (f"{fnum(int(best_hour_row['meetings']))} встреч · {best_hour_row['meeting_pct']:.1f}%"
         if best_hour_row is not None and best_hour_row["meetings"] > 0 else "встреч нет"),
    )

    fig_meetings = go.Figure()
    fig_meetings.add_bar(
        x=hourly["hour_label"], y=hourly["meetings"], name="Назначили встречу",
        marker_color="#7cc48b", text=hourly["meetings"], textposition="outside",
        cliponaxis=False, hovertemplate="%{x}<br>назначили встречу: %{y}<extra></extra>",
    )
    fig_meetings.add_trace(go.Scatter(
        x=hourly["hour_label"], y=hourly["meeting_pct"], name="Конверсия во встречу, %",
        mode="lines+markers", line=dict(color="#2f855a", width=3), yaxis="y2",
        hovertemplate="%{x}<br>конверсия во встречу: %{y}%<extra></extra>"))
    fig_meetings.update_layout(height=340, margin=dict(l=10, r=10, t=28, b=10),
                               xaxis_title="Час звонка",
                               yaxis=dict(title="Назначено встреч", rangemode="tozero"),
                               yaxis2=dict(title="Конверсия, %", overlaying="y", side="right", rangemode="tozero"),
                               legend=dict(orientation="h", y=1.12, x=0),
                               font=dict(color="#1b1f3b"))
    st.plotly_chart(fig_meetings)

with dashboard_tabs[5]:
    st.subheader("Качество робота")

    err = df[(df["has_bot_error"]) & (df["bot_error_type"] != "Не распознал автоответчик")]
    n_err = len(err)
    err_hangup = int((err["reason"] == "client_hangup").sum())
    st.markdown("**Полная структура ошибок бота**")
    e1, e2, e3 = st.columns(3)
    e1.metric("Ошибки бота, всего", pct(n_err, len(df)),
              help=f"{fnum(n_err)} звонков с хотя бы одной ошибкой бота.")
    e2.metric("Из них клиент сбросил сам", fnum(err_hangup),
              help=f"{pct(err_hangup, n_err)} от всех звонков с ошибками.")
    e3.metric("Молчание бота (dead air)", fnum(int(df["bot_silent"].sum())))

with dashboard_tabs[6]:
    st.subheader("Разбор диалогов")
    f1, f2, f3 = st.columns(3)
    with f1:
        pick_step = st.selectbox("Макс. шаг диалога",
                                 ["(любой)"] + [STEP_NAMES[s] for s in range(5)])
    with f2:
        outs = ["(любой)"] + list(df["step1_outcome"].value_counts().index)
        pick_out = st.selectbox("Исход шага 1", outs)
    with f3:
        obs = ["(любой)"] + list(df[df["engaged"]]["objection"].dropna().unique())
        pick_ob = st.selectbox("Реакция клиента", obs)

    extra1, extra2, extra3 = st.columns(3)
    only_bug = extra1.checkbox("только баг отрасли")
    only_loop = extra2.checkbox("только зацикливание бота")
    only_machine = extra3.checkbox("только автоответчики/машины")

    d = df.copy()
    if pick_step != "(любой)":
        d = d[d["reached_step_name"] == pick_step]
    if pick_out != "(любой)":
        d = d[d["step1_outcome"] == pick_out]
    if pick_ob != "(любой)":
        d = d[d["objection"] == pick_ob]
    if only_bug:
        d = d[d["industry_bug"]]
    if only_loop:
        d = d[d["bot_loop"]]
    if only_machine:
        d = d[d["is_ao"]]

    st.caption(f"Найдено диалогов: **{len(d):,}**".replace(",", " "))
    d = d[d["has_dialog"]].head(40)
    for _, row in d.iterrows():
        head = (f"{row['dt']:%d.%m %H:%M} · {row['reached_step_name']} · "
                f"{row['reason']} · {row['dur_raw']} · реплик: {row['n_turns']}")
        with st.expander(head):
            for spk, utt in parse_turns(row["dialog"]):
                cls = "bubble-bot" if spk == "bot" else "bubble-user"
                who = "bot" if spk == "bot" else "клиент"
                st.markdown(f"<div class='{cls}'><b>{who}:</b> {utt or '—'}</div>",
                            unsafe_allow_html=True)
    st.divider()
    st.subheader("Что считаем этапами")
    st.markdown(
        "- `Дослушали первый заход` — клиент не сбросил сразу в первые 10 секунд.\n"
        "- `Прошли 1 этап` — бот дошёл до оффера.\n"
        "- `Назначили встречу` — в диалоге есть явная фиксация времени / даты или бот уже дошёл до квалификации.\n"
        "- `Дали квалификацию` — бот дошёл до квалификационного вопроса (`reached_step >= 4`)."
    )

with dashboard_tabs[7]:
    st.subheader("Поиск по номеру")
    st.caption("Введите номер — покажем все его звонки (по всей базе, без учёта фильтров слева) "
               "с результатами и диалогами.")

    def norm_phone(s):
        return "".join(ch for ch in str(s) if ch.isdigit())

    raw = st.text_input("Номер телефона", placeholder="например, 79991234567 или +7 999 123-45-67")
    q = norm_phone(raw)
    if len(q) == 11 and q.startswith("8"):
        q = "7" + q[1:]
    elif len(q) == 10:
        q = "7" + q

    if not q:
        st.info("Введите номер в любом формате — лишние символы (плюс, пробелы, дефисы) уберём сами.")
    else:
        phone_norm = df_all["phone"].map(norm_phone)
        calls = df_all[phone_norm == q].sort_values("dt")
        if calls.empty:
            st.warning(f"По номеру {q} звонков не найдено.")
        else:
            booked = int(calls["meeting_booked"].sum())
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Всего звонков", fnum(len(calls)))
            s2.metric("Назначена встреча", "Да" if booked else "Нет",
                      help=f"Встреча зафиксирована в {fnum(booked)} из {fnum(len(calls))} звонков.")
            s3.metric("Первый звонок", f"{calls['dt'].min():%d.%m.%Y}")
            s4.metric("Последний звонок", f"{calls['dt'].max():%d.%m.%Y}")
            st.divider()

            for _, row in calls.iterrows():
                meet = "✅ встреча" if row["meeting_booked"] else "—"
                head = (f"#{row['call_index']} · {row['dt']:%d.%m.%Y %H:%M} · "
                        f"{row['reached_step_name']} · {row['reason']} · {row['dur_raw']} · {meet}")
                with st.expander(head):
                    facts = [
                        ("Дата и время", f"{row['dt']:%d.%m.%Y %H:%M:%S}"),
                        ("Длительность", row["dur_raw"]),
                        ("Статус", row["status"]),
                        ("Причина завершения", row["reason"]),
                        ("Этап диалога", row["reached_step_name"]),
                        ("Реплик в диалоге", fnum(int(row["n_turns"]))),
                        ("Встреча назначена", "Да" if row["meeting_booked"] else "Нет"),
                        ("Реакция клиента", row["objection"] or "—"),
                        ("Автоответчик / машина", "Да" if row["is_ao"] else "Нет"),
                        ("Ошибка бота", row["bot_error_type"] if row["has_bot_error"] else "—"),
                    ]
                    rows_html = "".join(
                        f"<tr><td style='color:#6b7280;padding:2px 14px 2px 0'>{k}</td>"
                        f"<td style='color:#1b1f3b'><b>{v}</b></td></tr>"
                        for k, v in facts)
                    st.markdown(f"<table style='font-size:0.88rem'>{rows_html}</table>",
                                unsafe_allow_html=True)

                    audio = row.get("audio")
                    if isinstance(audio, str) and audio.startswith("http"):
                        st.markdown(f"🎧 [Запись разговора]({audio})")

                    if row["has_dialog"]:
                        st.markdown("**Диалог:**")
                        for spk, utt in parse_turns(row["dialog"]):
                            cls = "bubble-bot" if spk == "bot" else "bubble-user"
                            who = "bot" if spk == "bot" else "клиент"
                            st.markdown(f"<div class='{cls}'><b>{who}:</b> {utt or '—'}</div>",
                                        unsafe_allow_html=True)
                    else:
                        st.caption("Диалога по этому звонку нет (нет соединения / молчание).")

st.stop()

with dashboard_tabs[1]:
    st.divider()

# ======================= ВОРОНКА ПО ЭТАПАМ =======================
    st.subheader("Воронка по этапам бота")

GREEN, RED, AMBER = "#4b9f5e", "#d9534f", "#e8a33d"
nopickup_n = n_calls - n_vz
undialed_contacts = max(int(base_size) - dialed, 0)


def render_stage(title, segments, last=False):
    # segments: (label, cnt, color, desc)
    total = sum(c for _, c, _, _ in segments)
    bars, legend, descs = "", "", ""
    for label, cnt, color, desc in segments:
        if cnt <= 0:
            continue
        w = cnt / total * 100 if total else 0
        inner = f"{label}<br>{fnum(cnt)} · {w:.0f}%" if w >= 14 else f"{fnum(cnt)}"
        bars += (f"<div class='seg' style='width:{w:.2f}%;background:{color}' "
                 f"title='{label}: {fnum(cnt)} ({w:.1f}%)'>{inner}</div>")
        legend += (f"<span><span class='dot' style='background:{color}'></span>"
                   f"{label} — {fnum(cnt)} ({w:.0f}%)</span>")
        if desc:
            descs += (f"<div class='catdesc'><span class='dot' style='background:{color}'></span>"
                      f"<b>{label}:</b> {desc}</div>")
    arrow = "" if last else "<div class='stage-arrow'>↓</div>"
    st.markdown(f"<div class='stage'><div class='stage-h'>{title} "
                f"<span class='base'>· всего {fnum(total)}</span></div>"
                f"<div class='pbar'>{bars}</div>"
                f"<div class='legend'>{legend}</div>"
                f"<div class='catdescs'>{descs}</div></div>{arrow}",
                unsafe_allow_html=True)


    st.caption(f"Срез: {unit_note}.")

render_stage("База (контакты)", [
    ("База", dialed, GREEN, "контакты из базы, которые обзвонили"),
    ("Ещё не обзвонено", undialed_contacts, "#c2c6da",
     "контакты из базы, до которых ещё не дозванивались (если задан размер базы больше обзвона)"),
])

render_stage("Из базы → обзвон", [
    ("Дозвонились", n_vz, GREEN, "кто-то взял трубку: дальше делим на автоответчики и живых людей"),
    ("Не дозвонились", nopickup_n, RED,
     "нет соединения: no_answer / queue_timeout / bad_number / network_error"),
])

render_stage("Из дозвонившихся", [
    ("АО / автоматика", n_ao, RED,
     "на линии был автоответчик, автоматика или другой не-живой сценарий"),
    ("Человек", n_human, GREEN,
     "из дозвонов убрали автоответчики и автоматику; остальное считаем разговором с человеком"),
])

render_stage("Из ветки «человек»", [
    ("Короткий отказ", human_short, AMBER,
     "живой человек сам бросил трубку за ≤10 сек, почти сразу после начала разговора"),
    ("Дослушали первый заход", n_cont1, GREEN,
     "клиент не сбросил сразу и дал боту закончить первый заход"),
])

render_stage("Из тех, кто дослушал первый заход", [
    ("Человек не дал согласие на разговор", n_short_refuse, RED,
     "услышал первое предложение, но не дал согласие идти дальше"),
    ("Бот прервал до 2 этапа", no_consent_bot, "#c97b3d",
     "бот завершил разговор до оффера, хотя клиент уже не сбросил сразу"),
    ("Прошли 1 этап", n_consent, GREEN,
     "клиент дал пройти шаг согласия, и бот дошёл до оффера"),
])

render_stage("Из прошедших 1 этап", [
    ("Нецелевой / редирект", new_contacts, AMBER,
     "клиент не ЛПР и переводит на другого человека"),
    ("Бот сам завершил разговор", offer_bot_drop, "#c97b3d",
     "оффер прозвучал, но разговор завершил бот"),
    ("Клиент отказался на 2 этапе", offer_refuse, RED,
     "клиент услышал оффер и сам не пошёл дальше"),
    ("Вышли на шаг встречи", n_to_meeting_step, GREEN,
     "после оффера разговор дошёл до обсуждения встречи / следующего созвона"),
])

render_stage("Из вышедших на шаг встречи", [
    ("Встреча не назначена", n_meeting_not_booked, RED,
     "бот вышел на шаг встречи, но в диалоге не видно явной фиксации времени/даты"),
    ("Назначили встречу", n_booked, GREEN,
     "в диалоге есть явное согласование времени/даты или бот дошёл до квалификации"),
])

render_stage("Из назначивших встречу", [
    ("Без квалификации", n_booked_noqual, GREEN,
     "встречу зафиксировали, но до квалификационного вопроса не дошли"),
    ("Дали квалификацию", n_to_qual, "#2f855a",
     "дошли до квалификационного этапа — самый глубокий успешный проход"),
], last=True)

# ---- примеры по проблемным категориям воронки ----
st.markdown("**Примеры по проблемным категориям:**")
botdrop_consent_pop = cont1[no_consent_bot_mask & cont1["said_consent"] & ~cont1["refused"]]
botdrop_before2_pop = no_consent_bot_df
offer_botdrop_pop = rest_offer[(rest_offer["reason"] == "bot_hangup") & ~rest_offer["refused"]]
ex_cats = [
    (f"Потерянные разговоры — {fnum(dropped)}", fsrc[fsrc["bot_dropped_willing"]], 5),
    (f"Бот прервал до 2 этапа — {fnum(no_consent_bot)}", botdrop_before2_pop, 2),
    (f"Бот скинул согласного — {fnum(bot_drop_consent)}", botdrop_consent_pop, 2),
    (f"Бот сам завершил разговор — {fnum(offer_bot_drop)}", offer_botdrop_pop, 2),
    (f"Встреча не назначена — {fnum(n_meeting_not_booked)}", meeting_not_booked, 2),
    (f"Дали квалификацию — {fnum(n_to_qual)}", to_qual, 2),
]
for cap, pop, nex in ex_cats:
    with st.expander(cap):
        if len(pop):
            show_examples(pop, n=nex)
        else:
            st.caption("Нет звонков в этой категории за выбранный период.")

with st.expander("По каким критериям звонок попадает в этап и категорию"):
    st.markdown(
        "**Шаг бота (reached_step)** — определяется по репликам бота:\n"
        "- 1 — приветствие («…добрый день! Звоню насчёт…»)\n"
        "- 2 — оффер («запускаем ИИ-продавца», «Это Лариса, батамИн»)\n"
        "- 3 — вопрос про встречу («созвониться с нашим экспертом», «удобно созвониться»)\n"
        "- 4 — квалификация («какая у вас обычно база в месяц на прозвон»)\n\n"
        "**Взяли трубку** — причина завершения НЕ из {no_answer, queue_timeout, bad_number, "
        "network_error}.\n\n"
        "**Обзвон:**\n"
        "- *Не дозвонились* — причина из {no_answer, queue_timeout, bad_number, network_error}.\n"
        "- *Дозвонились* — все остальные.\n\n"
        "**Дозвонились:**\n"
        "- *АО / автоматика* — текст-маркеры автоматики («абонент», «секретарь», «вне зоны») "
        "ИЛИ `bot_hangup` за 1–4 сек без единой реальной реплики клиента ИЛИ длинная «молчаливая автоматика» "
        "(клиент не дал ни одной реальной реплики, бот не дошёл до оффера и сам завершил звонок) ИЛИ «длинный робот-робот» "
        "(≥45 сек, но клиент сказал ≤1 реплики и до оффера не дошёл).\n"
        "- *Человек* — всё, что не попало в АО/автоматику.\n\n"
        "**Человек:**\n"
        "- *Короткий отказ* — `client_hangup` И длительность ≤ 10 сек.\n"
        "- *Дослушали первый заход* — живой человек не сбросил сразу.\n\n"
        "**Дослушали первый заход:**\n"
        "- *Человек не дал согласие на разговор* — reached_step < 2 И разговор завершил клиент.\n"
        "- *Бот прервал до 2 этапа* — reached_step < 2 И разговор завершил бот.\n"
        "- *Прошли 1 этап* — reached_step ≥ 2.\n\n"
        "**Прошли 1 этап:**\n"
        "- *Нецелевой / редирект* — reached_step == 2 И клиент дал контакт другого человека.\n"
        "- *Бот сам завершил разговор* — reached_step == 2 И разговор завершил бот.\n"
        "- *Клиент отказался на 2 этапе* — reached_step == 2 И разговор завершил клиент.\n"
        "- *Вышли на шаг встречи* — reached_step ≥ 3.\n\n"
        "**Из вышедших на шаг встречи:**\n"
        "- *Встреча не назначена* — бот обсуждал встречу, но в диалоге нет явной фиксации времени/даты.\n"
        "- *Назначили встречу* — в диалоге есть явное время/дата ИЛИ бот уже дошёл до квалификации.\n\n"
        "**Из назначивших встречу:**\n"
        "- *Без квалификации* — встречу зафиксировали, но до квалификационного вопроса не дошли.\n"
        "- *Дали квалификацию* — reached_step ≥ 4.\n\n"
        "Полная классификация живой/машина всё равно точнее с AMD-флагом или аудио.")

with st.expander("Как найти эти звонки в исходной таблице (фильтры по колонкам + примеры ячеек)"):
    SHEET = ("https://docs.google.com/spreadsheets/d/"
             "18lZSxc5G6lhj9hoDgVZKMtrYDYzr2tJ692txym3L7oI/edit#gid=1903196005&range=")
    st.markdown(
        "Колонки в прод-таблице: **A** телефон · **B** дата и время · **C** длительность · "
        "**D** статус · **E** запись аудио · **F** причина завершения · **G** история диалога.\n\n"
        f"- **АО / автоматика** — текстовые маркеры автоматики ИЛИ `F = bot_hangup` при `C 0:01–0:04` "
        f"без реальной реплики клиента. "
        f"Пример: [строка 11464]({SHEET}A11464:G11464).\n"
        f"- **Короткий отказ** — `F = client_hangup` И `C 0:01–0:10`. "
        f"Пример: [строка 11458]({SHEET}A11458:G11458).\n"
        f"- **Человек не дал согласие на разговор** — в `G` есть только приветствие "
        f"(«…Звоню насчёт искусственного интеллекта…»), нет фразы оффера «запускаем ИИ-продавца»; "
        f"`F = client_hangup`.\n"
        f"- **Бот прервал до 2 этапа** — `F = bot_hangup`, оффера «запускаем ИИ-продавца» в `G` нет. "
        f"Если в репликах `user:` уже было «да/слушаю/говорите», это частный случай "
        f"«бот скинул согласного». Пример: [строка 11431]({SHEET}A11431:G11431).\n"
        f"- **Клиент отказался на 2 этапе** — в `G` есть «запускаем ИИ-продавца», но нет вопроса про "
        f"встречу («созвониться с экспертом»); `F = client_hangup`. Пример: [строка 11484]({SHEET}A11484:G11484).\n"
        f"- **Бот сам завершил разговор** — то же, но `F = bot_hangup`. "
        f"Пример: [строка 11485]({SHEET}A11485:G11485).\n"
        f"- **Нецелевой / редирект** — в `user:` есть переадресация на другого человека / ЛПР.\n"
        f"- **Назначили встречу** — в `user:` после вопроса про встречу есть явное время / дата / слот.\n"
        f"- **Дали квалификацию** — в `G` есть вопрос «какая у вас обычно база в месяц». "
        f"Пример: [строка 11483]({SHEET}A11483:G11483).\n\n"
        "_Номера строк — для текущей выгрузки (порядок строк совпадает с файлом)._")

st.divider()

# ======================= ПОЧЕМУ БОТ ЗАВЕРШАЕТ ДО 2 ЭТАПА =======================
st.subheader("Почему бот завершает до 2 этапа")
st.caption("Отдельно разбираем случаи, где до оффера не дошли и разговор завершил сам бот.")

prebot = no_consent_bot_df["preconsent_bot_reason"].value_counts()
if len(prebot):
    PREBOT_FAULT = {
        "Связь / не понял бота",
        "Молчание бота / dead air",
        "Зацикливание / ошибка логики",
        "Бот завершил после согласия клиента",
        "Бот вежливо завершил после реакции клиента",
        "Бот сам завершил без явной причины",
    }
    colors_pre = ["#d9534f" if r in PREBOT_FAULT else "#6f7ad6" for r in prebot.index]
    figpre = go.Figure(go.Bar(
        y=prebot.index[::-1], x=prebot.values[::-1], orientation="h",
        marker_color=colors_pre[::-1], text=prebot.values[::-1], textposition="auto"))
    figpre.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                         xaxis_title=unit_noun, font=dict(color="#1b1f3b"))
    st.plotly_chart(figpre)
    pre_our = int(sum(v for r, v in prebot.items() if r in PREBOT_FAULT))
    st.caption(f"Красное — сценарии, где бот, вероятно, можно улучшить: "
               f"{fnum(pre_our)} из {fnum(int(prebot.sum()))} ({pct(pre_our, int(prebot.sum()))}).")

    st.markdown("**Примеры по причинам:**")
    for reason_name, cnt in prebot.items():
        with st.expander(f"{reason_name} — {fnum(int(cnt))}"):
            show_examples(no_consent_bot_df[no_consent_bot_df["preconsent_bot_reason"] == reason_name])

st.divider()

# ======================= ПОЧЕМУ ТЕРЯЕМ НА 2 ЭТАПЕ =======================
st.subheader("Почему теряем на 2 этапе")
st.caption("Среди тех, кто дошёл до оффера, но не вышел в назначенную встречу — что именно произошло.")
nb = at_offer["nobook_reason"].value_counts()
if len(nb):
    OUR_FAULT = {
        "Связь / не понял бота",
        "Молчание бота / dead air",
        "Зацикливание / ошибка логики",
        "Клиент замолчал, бот завершил",
        "Бот сам завершил без явной причины",
    }
    bar_colors = ["#d9534f" if r in OUR_FAULT else "#6f7ad6" for r in nb.index]
    fignb = go.Figure(go.Bar(
        y=nb.index[::-1], x=nb.values[::-1], orientation="h",
        marker_color=bar_colors[::-1], text=nb.values[::-1], textposition="auto"))
    fignb.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                        xaxis_title="звонков", font=dict(color="#1b1f3b"))
    st.plotly_chart(fignb)
    our = int(sum(v for r, v in nb.items() if r in OUR_FAULT))
    st.caption(f"Красное — потери, где проблема выглядит как ошибка бота или качества диалога: "
               f"{fnum(our)} из {fnum(int(nb.sum()))} ({pct(our, int(nb.sum()))}). "
               f"Синие категории — там, где клиент фактически отказался или перевёл на другого человека.")

    st.markdown("**Примеры звонков по каждой причине:**")
    nb_pop = at_offer
    for reason_name, cnt in nb.items():
        exs = nb_pop[nb_pop["nobook_reason"] == reason_name].head(2)
        with st.expander(f"{reason_name} — {fnum(int(cnt))} звонков"):
            for _, r in exs.iterrows():
                st.markdown(f"<span class='small'>{r['dt']:%d.%m %H:%M} · {r['dur_raw']} · "
                            f"{r['reason']} · тел {r['phone']}</span>", unsafe_allow_html=True)
                for spk, utt in parse_turns(r["dialog"]):
                    cls = "bubble-bot" if spk == "bot" else "bubble-user"
                    who = "bot" if spk == "bot" else "клиент"
                    st.markdown(f"<div class='{cls}'><b>{who}:</b> {utt or '—'}</div>",
                                unsafe_allow_html=True)
                st.markdown("<hr style='margin:6px 0'>", unsafe_allow_html=True)

st.divider()

# ======================= ПРИЧИНЫ КЛИЕНТСКОГО ОТКАЗА НА 2 ЭТАПЕ =======================
st.subheader("Причины клиентского отказа на 2 этапе")
st.caption("Только звонки, где оффер прозвучал, и дальше не пошёл именно клиент, а не бот и не редирект.")
offer_refuse_full = at_offer[~at_offer["gave_contact"]
                             & ((at_offer["reason"] == "client_hangup") | at_offer["refused"])]
orr = offer_refuse_full["offer_refuse_reason"].value_counts()
if len(orr):
    SILENT = "Молча бросил трубку"
    colors_or = ["#9e9e9e" if r == SILENT else "#d9534f" for r in orr.index]
    figor = go.Figure(go.Bar(y=orr.index[::-1], x=orr.values[::-1], orientation="h",
                             marker_color=colors_or[::-1], text=orr.values[::-1],
                             textposition="auto"))
    figor.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                        xaxis_title="звонков", font=dict(color="#1b1f3b"))
    st.plotly_chart(figor)
    sil = int(orr.get(SILENT, 0))
    st.caption(f"Серое — {fnum(sil)} из {fnum(int(orr.sum()))} ({pct(sil, int(orr.sum()))}) "
               f"бросают трубку молча, не назвав причину: оффер про ИИ не цепляет настолько, "
               f"чтобы хотя бы возразить. Среди назвавших — заметны «не профиль» (не та база) "
               f"и «скепсис к ИИ / это робот?».")

    st.markdown("**Примеры по причинам:**")
    for rname, cnt in orr.items():
        with st.expander(f"{rname} — {fnum(int(cnt))}"):
            show_examples(offer_refuse_full[offer_refuse_full["offer_refuse_reason"] == rname])

st.divider()

# ======================= ПОВТОРНЫЕ ПОПЫТКИ =======================
st.subheader("Повторные попытки")
st.caption("Сколько раз звоним одному контакту и в каких сегментах чаще всего дожимаем перезвонами.")

r1, r2, r3 = st.columns(3)
r1.metric("Звонков на 1 контакт", f"{avg_calls_per_contact:.2f}",
          help="Среднее и медианное число звонков на один уникальный номер в текущем срезе.")
r2.metric("Контакты с 2+ звонками", pct((call_counts_per_contact >= 2).sum(), len(call_counts_per_contact)),
          help="Сколько уникальных контактов получали повторный звонок хотя бы один раз.")
r3.metric("Повторные звонки", pct(max(n_calls - dialed, 0), n_calls),
          help="Все звонки сверх первого звонка по контакту в текущем срезе.")

rr1, rr2 = st.columns(2)
with rr1:
    fig_repeat = go.Figure(go.Bar(
        x=repeat_dist["calls_per_contact"].astype(str),
        y=repeat_dist["contacts"],
        marker_color="#6f7ad6",
        text=repeat_dist["contacts"],
        textposition="outside",
        cliponaxis=False,
    ))
    fig_repeat.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=28, b=10),
        xaxis_title="Сколько звонков пришлось на контакт",
        yaxis_title="Контактов",
        yaxis=dict(rangemode="tozero"),
        font=dict(color="#1b1f3b"),
    )
    st.plotly_chart(fig_repeat)

with rr2:
    fig_call_index = go.Figure(go.Bar(
        x=call_index_dist["call_index"].astype(str),
        y=call_index_dist["calls"],
        marker_color="#c7cfeb",
        text=call_index_dist["calls"],
        textposition="outside",
        cliponaxis=False,
    ))
    fig_call_index.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=28, b=10),
        xaxis_title="Какой по счёту звонок контакту",
        yaxis_title=f"{unit_noun.capitalize()}",
        yaxis=dict(rangemode="tozero"),
        font=dict(color="#1b1f3b"),
    )
    st.plotly_chart(fig_call_index)

segment_repeat = pd.DataFrame([
    ("Не дозвонились", nopickup_n, len(fsrc[fsrc["no_pickup"]]["phone"].unique())),
    ("АО / автоматика", n_ao, ao["phone"].nunique()),
    ("Короткий отказ", human_short, human[human_short_mask]["phone"].nunique()),
    ("Не дал согласие", n_short_refuse, cont1[(cont1["reached_step"] < 2) & (cont1["reason"] != "bot_hangup")]["phone"].nunique()),
    ("Бот прервал до 2 этапа", no_consent_bot, cont1[no_consent_bot_mask]["phone"].nunique()),
    ("Клиент отказался на 2 этапе", offer_refuse, at_offer[~at_offer["gave_contact"] & ~((at_offer["reason"] == "bot_hangup") & ~at_offer["refused"])]["phone"].nunique()),
    ("Встреча не назначена", n_meeting_not_booked, meeting_not_booked["phone"].nunique()),
    ("Назначили встречу", n_booked_noqual, booked[booked["reached_step"] == 3]["phone"].nunique()),
    ("Дали квалификацию", n_to_qual, to_qual["phone"].nunique()),
], columns=["segment", "calls", "contacts"])
segment_repeat = segment_repeat[segment_repeat["calls"] > 0].copy()
segment_repeat["avg_calls_per_contact"] = segment_repeat["calls"] / segment_repeat["contacts"].clip(lower=1)
segment_repeat = segment_repeat.sort_values("avg_calls_per_contact", ascending=False)

fig_seg_repeat = go.Figure(go.Bar(
    y=segment_repeat["segment"][::-1],
    x=segment_repeat["avg_calls_per_contact"][::-1],
    orientation="h",
    marker_color="#4b57c9",
    text=segment_repeat["avg_calls_per_contact"][::-1].round(2),
    textposition="auto",
    customdata=segment_repeat[["calls", "contacts"]][::-1].values,
    hovertemplate="%{y}<br>звонков на контакт: %{x:.2f}<br>звонков: %{customdata[0]}<br>контактов: %{customdata[1]}<extra></extra>",
))
fig_seg_repeat.update_layout(
    height=340,
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="Среднее звонков на контакт внутри сегмента",
    font=dict(color="#1b1f3b"),
)
st.plotly_chart(fig_seg_repeat)
st.caption("Чем выше столбец, тем чаще один и тот же контакт попадает в этот сегмент после нескольких попыток.")

st.divider()

# ======================= КАЧЕСТВО БАЗЫ =======================
st.subheader("Качество базы")
wrong_person = fsrc[fsrc["gave_contact"] & ~fsrc["is_ao"]]   # нужен другой человек (живой редирект)
wrong_comp = fsrc[fsrc["wrong_company"]]
notprof = fsrc[fsrc["not_profile"]]
nwp, nwc, nnp = len(wrong_person), len(wrong_comp), len(notprof)
bad_mask = (fsrc["gave_contact"] & ~fsrc["is_ao"]) | fsrc["wrong_company"] | fsrc["not_profile"]
bad_total = int(bad_mask.sum())
b1, b2, b3, b4 = st.columns(4)
b1.metric("Не тот человек (нужен другой ЛПР)", fnum(nwp),
          help="Клиент сказал, что вопрос не к нему, а к другому человеку "
               "(дал его номер или нет — неважно).")
b2.metric("Не работает в компании / ошиблись", fnum(nwc),
          help="«Я тут не работаю», «вы ошиблись номером», «не туда попали» — "
               "устаревший или неверный контакт.")
b3.metric("Не профиль / не наш бизнес", fnum(nnp),
          help="«У нас нет отдела продаж», «мы грузоперевозки», «не работаем с продажами» — "
               "звоним компании, которой оффер в принципе не подходит.")
b4.metric("Проблемных контактов всего", fnum(bad_total),
          help="Объединение трёх категорий — нижняя оценка «мусора» в базе.")
be1, be2, be3 = st.columns(3)
with be1:
    with st.expander(f"Не тот человек — примеры ({fnum(nwp)})"):
        show_examples(wrong_person, n=3) if nwp else st.caption("Нет за период.")
with be2:
    with st.expander(f"Не работает здесь — примеры ({fnum(nwc)})"):
        show_examples(wrong_comp, n=3) if nwc else st.caption("Нет за период.")
with be3:
    with st.expander(f"Не профиль — примеры ({fnum(nnp)})"):
        show_examples(notprof, n=3) if nnp else st.caption("Нет за период.")

st.divider()

# ======================= ВРЕМЯ ЗВОНКА =======================
st.subheader("Когда чаще берут трубку и назначают встречу")

hourly = (
    fsrc.groupby("hour")
    .agg(
        calls=("phone", "size"),
        human_rate=("live_human_answer", "mean"),
        meeting_rate=("meeting_booked", "mean"),
        meetings=("meeting_booked", "sum"),
    )
    .reindex(range(24), fill_value=0)
    .reset_index()
)
hourly["pickup_pct"] = (hourly["human_rate"] * 100).round(1)
hourly["meeting_pct"] = (hourly["meeting_rate"] * 100).round(1)
hourly["hour_label"] = hourly["hour"].map(lambda h: f"{h:02d}:00")

fig_time = go.Figure()
fig_time.add_bar(
    x=hourly["hour_label"], y=hourly["calls"], name="Звонков",
    marker_color="#d9deee", yaxis="y2",
    hovertemplate="%{x}<br>звонков: %{y}<extra></extra>")
fig_time.add_trace(go.Scatter(
    x=hourly["hour_label"], y=hourly["pickup_pct"], name="Ответил живой человек, %",
    mode="lines+markers", line=dict(color="#4b57c9", width=3),
    hovertemplate="%{x}<br>ответил живой человек: %{y}%<extra></extra>"))
fig_time.update_layout(
    height=360,
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="Час звонка",
    yaxis=dict(title="% звонков", rangemode="tozero"),
    yaxis2=dict(title="Кол-во звонков", overlaying="y", side="right", rangemode="tozero"),
    legend=dict(orientation="h", y=1.12, x=0),
    font=dict(color="#1b1f3b"),
    barmode="overlay",
)
st.plotly_chart(fig_time)

meet_cols = st.columns([1, 2])
meet_cols[0].metric(
    "Назначили встречу",
    fnum(int(hourly["meetings"].sum())),
    help="Сколько встреч зафиксировали в выбранном срезе."
)
best_hour_row = hourly.loc[hourly["meetings"].idxmax()] if len(hourly) else None
meet_cols[1].metric(
    "Пиковый час по встречам",
    f"{best_hour_row['hour_label']}" if best_hour_row is not None else "—",
    (f"{fnum(int(best_hour_row['meetings']))} встреч · {best_hour_row['meeting_pct']:.1f}%"
     if best_hour_row is not None and best_hour_row["meetings"] > 0 else "встреч нет"),
    help="Показываем час, в который назначили больше всего встреч."
)

fig_meetings = go.Figure()
fig_meetings.add_bar(
    x=hourly["hour_label"],
    y=hourly["meetings"],
    name="Назначили встречу",
    marker_color="#7cc48b",
    text=hourly["meetings"],
    textposition="outside",
    cliponaxis=False,
    hovertemplate="%{x}<br>назначили встречу: %{y}<extra></extra>",
)
fig_meetings.add_trace(go.Scatter(
    x=hourly["hour_label"],
    y=hourly["meeting_pct"],
    name="Конверсия во встречу, %",
    mode="lines+markers",
    line=dict(color="#2f855a", width=3),
    yaxis="y2",
    hovertemplate="%{x}<br>конверсия во встречу: %{y}%<extra></extra>",
))
fig_meetings.update_layout(
    height=340,
    margin=dict(l=10, r=10, t=28, b=10),
    xaxis_title="Час звонка",
    yaxis=dict(title="Назначено встреч", rangemode="tozero"),
    yaxis2=dict(title="Конверсия, %", overlaying="y", side="right", rangemode="tozero"),
    legend=dict(orientation="h", y=1.12, x=0),
    font=dict(color="#1b1f3b"),
)
st.plotly_chart(fig_meetings)

st.divider()

# ======================= ОШИБКИ КАЧЕСТВА РОБОТА =======================
st.subheader("Ошибки качества робота")
st.caption("Отдельный блок по дефектам сценария и логики: это не отказ клиента, а наши управляемые потери.")

q1, q2, q3 = st.columns(3)
q1.metric("Зацикливание / повтор", fnum(quality_loops),
          help="Бот повторяет реплику или списывает на «связь подвисает», хотя клиент отвечает.")
q2.metric("Пустая реплика бота", fnum(quality_silent),
          help="Dead air: бот отвечает пустотой `bot: ...`.")
q3.metric("Пустая отрасль в оффере", fnum(quality_industry_bug),
          help="Фраза вида «есть кейс по , хотела показать» — сломанная подстановка отрасли.")

loop_examples = df[df["bot_loop"]]
with st.expander(f"Примеры зацикливания — {fnum(len(loop_examples))}"):
    if len(loop_examples):
        show_examples(loop_examples, n=4)
    else:
        st.caption("Нет звонков в этой категории за выбранный период.")

st.divider()

st.subheader("Ошибки бота")
err = df[(df["has_bot_error"]) & (df["bot_error_type"] != "Не распознал автоответчик")]
n_err = len(err)
err_hangup = int((err["reason"] == "client_hangup").sum())
e1, e2, e3 = st.columns(3)
e1.metric("Ошибки бота, всего", pct(n_err, len(df)),
          help=f"Звонки хотя бы с одной ошибкой бота = {fnum(n_err)} ÷ {fnum(len(df))} всех.")
e2.metric("Из них клиент сбросил сам", fnum(err_hangup),
          help="Человек положил трубку — увидел, что разговор с ботом бессмысленный.")
e3.metric("Молчание бота (dead air)", fnum(int(df["bot_silent"].sum())),
          help="Бот выдал пустую реплику «bot: ...» — провал генерации/TTS.")

by_type = err["bot_error_type"].value_counts()
fige = go.Figure(go.Bar(y=by_type.index[::-1], x=by_type.values[::-1], orientation="h",
                        marker_color="#d9534f", text=by_type.values[::-1], textposition="auto"))
fige.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10),
                   xaxis_title="звонков", font=dict(color="#1b1f3b"))
st.plotly_chart(fige)

st.markdown("**Примеры по типам ошибок:**")
DESCR = {
    "Молчание бота (пустая реплика)": "бот ответил пустотой «...», клиент переспрашивает «чё-чё?» и бросает",
    "Зацикливание / повтор": "бот повторяет одну реплику или списывает на «связь» при говорящем клиенте",
    "Не по скрипту": "битый опенер «Хочу к вам в — в продажах поработать» вместо скрипта про ИИ",
    "Баг: пустая отрасль в оффере": "«…есть кейс по , хотела показать» — отрасль не подставилась",
}
for etype, cnt in by_type.items():
    with st.expander(f"{etype} — {fnum(int(cnt))}"):
        st.caption(DESCR.get(etype, ""))
        show_examples(df[df["bot_error_type"] == etype])

st.divider()

# ======================= АВТООТВЕТЧИКИ / МАШИНЫ =======================
st.subheader("Автоответчики и машины (АО)")
st.caption("«Машина» = бот попал не на живого человека: операторский сервис, ""виртуальный секретарь, «абонент недоступен», антиспам, длинный «робот-робот».")
mc = int(df["is_machine"].sum())
amd = int(df["amd_suspect"].sum())
struct = int(df["bot_bot_struct"].sum())
ao_all = int(df["is_ao"].sum())
m1, m2, m3, m4 = st.columns(4)
m1.metric("Все звонки в автоматику", fnum(ao_all),
          help="Общий объём звонков, где бот, вероятнее всего, попал не на живого человека.")
m2.metric("Автоматика по явным фразам в диалоге", fnum(mc),
          help="Случаи, где в репликах есть прямые маркеры автоматики: «абонент», «секретарь», «вне зоны», антиспам и похожие.")
m3.metric("Долгие разговоры с роботом вместо человека", fnum(struct),
          help="Длинные звонки от 45 секунд, где клиент почти не говорит и бот, скорее всего, общался с автоматикой, а не с человеком.")
m4.metric("Мгновенные автоответчики без ответа клиента", fnum(amd),
          help="Очень короткие звонки 1–4 секунды, где бот сам завершил разговор и клиент не сказал ни одной реальной реплики.")
if mc:
    mt = df[df["is_machine"]]["machine_type"].value_counts()
    figm = px.bar(mt, orientation="h", text=mt.values,
                  color=mt.values, color_continuous_scale="Purples")
    figm.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10),
                       coloraxis_showscale=False, showlegend=False,
                       yaxis_title="", xaxis_title="звонков (подтв. по тексту)",
                       yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(figm)
st.markdown("<span class='small'>АО определялись <b>по тексту диалогов</b> "
            "(маркеры автоматики + структура: длительность/число реплик + правило «1–4 сек без ответа» + длинная молчаливая автоматика).</span>",
            unsafe_allow_html=True)

# ======================= DRILL-DOWN =======================
st.subheader("Разбор диалогов")
st.caption("Выберите срез — и читайте реальные транскрипты обрывов. ""Так гипотеза рождается из сырья, а не из агрегатов.")

f1, f2, f3 = st.columns(3)
with f1:
    pick_step = st.selectbox("Макс. шаг диалога",
                             ["(любой)"] + [STEP_NAMES[s] for s in range(5)])
with f2:
    outs = ["(любой)"] + list(df["step1_outcome"].value_counts().index)
    pick_out = st.selectbox("Исход шага 1", outs)
with f3:
    obs = ["(любой)"] + list(df[df["engaged"]]["objection"].dropna().unique())
    pick_ob = st.selectbox("Реакция клиента", obs)

extra1, extra2, extra3 = st.columns(3)
only_bug = extra1.checkbox("только баг отрасли")
only_loop = extra2.checkbox("только зацикливание бота")
only_machine = extra3.checkbox("только автоответчики/машины")

d = df.copy()
if pick_step != "(любой)":
    d = d[d["reached_step_name"] == pick_step]
if pick_out != "(любой)":
    d = d[d["step1_outcome"] == pick_out]
if pick_ob != "(любой)":
    d = d[d["objection"] == pick_ob]
if only_bug:
    d = d[d["industry_bug"]]
if only_loop:
    d = d[d["bot_loop"]]
if only_machine:
    d = d[d["is_ao"]]

st.caption(f"Найдено диалогов: **{len(d):,}**".replace(",", " "))
d = d[d["has_dialog"]].head(40)

for _, row in d.iterrows():
    head = (f"{row['dt']:%d.%m %H:%M} · {row['reached_step_name']} · "f"{row['reason']} · {row['dur_raw']} · реплик: {row['n_turns']}")
    with st.expander(head):
        from data_pipeline import parse_turns
        for spk, utt in parse_turns(row["dialog"]):
            cls = "bubble-bot" if spk == "bot" else "bubble-user"
            who = "bot" if spk == "bot" else "клиент"
            st.markdown(f"<div class='{cls}'><b>{who}:</b> {utt or '—'}</div>",
                        unsafe_allow_html=True)
        if isinstance(row.get("audio"), str) and row["audio"]:
            st.markdown(f"<span class='small'><a href='{row['audio']}' target='_blank'>"
                        f"аудиозапись</a></span>", unsafe_allow_html=True)

st.divider()

st.subheader("Что считаем этапами")
st.caption("Короткая легенда для чтения воронки.")
st.markdown(
    "- `Дослушали первый заход` — клиент не сбросил сразу в первые 10 секунд.\n"
    "- `Прошли 1 этап` — бот дошёл до оффера, то есть клиент дал пройти шаг согласия на разговор.\n"
    "- `Назначили встречу` — в диалоге есть явная фиксация времени / даты или бот уже дошёл до квалификации.\n"
    "- `Дали квалификацию` — бот дошёл до квалификационного вопроса (`reached_step >= 4`)."
)
