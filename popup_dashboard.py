import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

st.set_page_config(page_title="식품 팝업스토어 기획 대시보드", page_icon="🏪",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; color: #4E342E; font-size: 18px; }
    .stApp { background-color: #FAF7F2 !important; }
    .block-container { background-color: #FAF7F2 !important; }
    .dashboard-header {
        background: linear-gradient(135deg, #C8845A 0%, #A0522D 60%, #7B3F1E 100%);
        padding: 1.8rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem;
        border: none; position: relative; overflow: hidden;
        box-shadow: 0 4px 16px rgba(160,82,45,0.18);
    }
    .dashboard-header::after {
        content: '🏪'; position: absolute; right: 2.5rem; top: 50%;
        transform: translateY(-50%); font-size: 4rem; opacity: 1.0;
    }
    .dashboard-title  { font-size: 2.2rem; font-weight: 900; color: white; margin: 0; letter-spacing: -0.03rem; }
    .dashboard-subtitle { font-size: 1.0rem; color: rgba(255,255,255,0.8); margin-top: 0.5rem; font-weight: 400; }
    .metric-card {
        background: #FFFFFF; border: 1px solid #E8DDD0;
        border-radius: 12px; padding: 1.1rem 1.3rem; text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .metric-value { font-size: 2.0rem; font-weight: 800; line-height: 1.2; color: #3E2723; }
    .metric-label { font-size: 1.0rem; color: #6D4C41; margin-top: 0.2rem; font-weight: 700; }
    .section-title {
        font-size: 1.6rem; font-weight: 800; color: #3E2723;
        margin-top: 2rem; margin-bottom: 1.2rem; padding-left: 1rem; border-left: 7px solid #8D6E63;
    }
    .breadcrumb { font-size: 0.82rem; color: #999; margin-bottom: 0.8rem; }
    .breadcrumb span { color: #C8845A; font-weight: 700; }
    section[data-testid="stSidebar"] { background-color: #F2EDE6 !important; }
    section[data-testid="stSidebar"] * { color: #3D2B1F !important; }
    /* 사이드바 라디오 버튼 커스텀 (메뉴처럼 보이게) */
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label > div:first-child {
        display: none;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label {
        padding: 0.6rem 1rem; border-radius: 8px; margin-bottom: 0.3rem;
        transition: all 0.2s; border: 1px solid transparent;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:hover {
        background-color: rgba(255,255,255,0.6); cursor: pointer;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label[aria-checked="true"] {
        background-color: #FFFFFF; border: 1px solid #C8845A;
        box-shadow: 0 2px 6px rgba(200,132,90,0.1); font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# ── 데이터 로드 ───────────────────────────────────────────────
@st.cache_data
def load_csv(path):
    df = pd.read_csv(path)
    df['시작일'] = pd.to_datetime(df['시작일'])
    df['종료일'] = pd.to_datetime(df['종료일'])
    return df

csv_path = '식품_팝업_스토어_진짜 최종 데이터.csv'
df = load_csv(csv_path)

# ── 파생 변수 ─────────────────────────────────────────────────
cost_cols = ['대관료(원)','인테리어비(원)','마케팅비(원)','운영인건비(원)','물류기타비(원)']
df['총_지출_비용(원)'] = df[cost_cols].sum(axis=1)
df['일당_지출(원)']   = df['총_지출_비용(원)'] / df['운영_기간(일)']

if '사전예약율' not in df.columns:
    df['사전예약율'] = df['방문객_수(명)'] / df['방문객_수(명)'].max() * 40 + 10
df['분기'] = df['시작일'].dt.to_period('Q').astype(str)

SIDO_MAP = {
    '서울 성수동':'서울','서울 여의도':'서울',
    '서울 강남/압구정':'서울','서울 홍대/연남':'서울',
    '부산 해운대/서면':'부산','대구 동성로':'대구','제주/서귀포':'제주',
}
df['시도'] = df['상권구분'].map(SIDO_MAP)

FOOD_COLORS = ['#E57373','#64B5F6','#FFD54F','#81C784','#BA68C8','#4DB6AC']
AREA_COLORS = ['#E57373','#64B5F6','#FFD54F','#81C784','#BA68C8','#4DB6AC','#FF8A65']
AGE_COLS    = ['10대_방문객_수','20대_방문객_수','30대_방문객_수','40대_방문객_수','50대_방문객_수','60대이상_방문객_수']
AGE_LABELS  = ['10대','20대','30대','40대','50대','60대+']
AGE_CLRS    = ['#FF8A65', '#9575CD', '#4FC3F7', '#4DB6AC', '#FFD54F', '#A1887F']

def L(h=300, margin=None, **kw):
    # 기본 여백을 넉넉하게 늘려서 글자 잘림 방지 (t:위, b:아래, l:왼쪽, r:오른쪽)
    m = margin or dict(t=60,b=40,l=40,r=40)
    d = dict(paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF',
             font_color='#3D2B1F', height=h, margin=m,
             legend=dict(bgcolor='#FFFFFF', font_size=12, bordercolor='#E8DDD0', borderwidth=1))
    d.update(kw)
    return d

def ax():
    return dict(gridcolor='#F0EAE0', linecolor='#E8DDD0', zerolinecolor='#E8DDD0', automargin=True)

def fmt_money(x):
    if x == 0: return "0"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 100000000:
        eok = int(x // 100000000)
        man = int((x % 100000000) // 10000)
        return f"{sign}{eok}억 {man}만" if man > 0 else f"{sign}{eok}억"
    elif x >= 10000:
        return f"{sign}{int(x // 10000)}만"
    else:
        return f"{sign}{int(x)}"

def fmt_money_hover(x):
    if x == 0: return "0원"
    sign = "-" if x < 0 else ""
    x = abs(int(x))
    parts = []
    if x >= 100000000:
        parts.append(f"{x // 100000000}억")
        x %= 100000000
    if x >= 10000:
        parts.append(f"{x // 10000}만")
        x %= 10000
    if x > 0:
        parts.append(f"{x}")
    return sign + " ".join(parts) + "원"

def mc(col, val, label, color, help_text=None):
    help_attr = f' title="{help_text}"' if help_text else ''
    col.markdown(f'<div class="metric-card"{help_attr}><div class="metric-value" style="color:{color}">{val}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

def show_action_plan(text):
    st.markdown(f"""
    <div style="background-color: #EFEBE9; border-left: 5px solid #8D6E63; padding: 1.2rem; border-radius: 8px; margin-top: 0.5rem; margin-bottom: 2rem; color: #4E342E; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
        <strong style="font-size: 1.1rem; color: #3E2723;">🚀 Action Plan</strong><br>
        <span style="font-size: 1.0rem; line-height: 1.6;">{text}</span>
    </div>
    """, unsafe_allow_html=True)

# ── 세션 상태 ─────────────────────────────────────────────────
for k in ['map_sido','map_area','map_addr']:
    if k not in st.session_state: st.session_state[k] = None

# ── 사이드바 ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h1 style='font-size: 1.5rem; font-weight: 800; color: #3D2B1F; margin-bottom: 1rem;'>🏪 팝업스토어 기획 대시보드</h1>", unsafe_allow_html=True)
    pages = ["📊 개요","📍 상권 및 위치 분석","🍜 식품 분류 분석",
             "💰 비용/수익 분석","👥 연령대 분석","📣 마케팅 분석"]
    page = st.radio("페이지 선택", pages, label_visibility="collapsed")
    
    st.markdown("---")
    st.markdown("### ️ 공통 필터")
    sel_area = st.selectbox("상권", ['전체']+sorted(df['상권구분'].unique()))
    sel_food = st.selectbox("식품 분류", ['전체']+sorted(df['식품_세부분류'].unique()))
    sel_year = st.selectbox("연도", ['전체']+sorted(df['연도'].unique().tolist()))

    # 팝업 기획 도우미 (개요 페이지 전용)
    if page == "📊 개요":
        st.markdown("---")
        st.markdown("### 🕵️ 팝업 기획 도우미")
        user_budget = st.number_input("가용 예산 (원)", min_value=0, value=50000000, step=1000000, format="%d")
        user_area_plan = st.selectbox("희망 지역", ['전체'] + sorted(df['상권구분'].unique()))
        
        # 예산 & 지역 기반 추천 로직
        valid_pops = df[df['총_지출_비용(원)'] <= user_budget]
        if user_area_plan != '전체':
            valid_pops = valid_pops[valid_pops['상권구분'] == user_area_plan]

        if not valid_pops.empty:
            # 월별 평균 매출이 가장 높은 달 추천
            best_month = valid_pops.groupby(valid_pops['시작일'].dt.month)['총_매출액(원)'].mean().idxmax()

            if user_area_plan == '전체':
                grp = valid_pops.groupby(['상권구분', '식품_세부분류'])[['순수익(원)', '총_매출액(원)', '방문객_수(명)']].mean()
                best_combo = grp['순수익(원)'].idxmax()
                best_rev = grp.loc[best_combo, '총_매출액(원)']
                best_prof = grp.loc[best_combo, '순수익(원)']
                best_vis = grp.loc[best_combo, '방문객_수(명)']
                
                st.success(f"""
                **💡 추천 전략**
                📍 **{best_combo[0]}**
                🍜 **{best_combo[1]}**
                📅 **{best_month}월** 오픈
                
                **📊 예상 평균 성과**
                💰 매출: {fmt_money(best_rev)}원
                💎 순수익: {fmt_money(best_prof)}원
                👥 방문객: {best_vis:,.0f}명
                """)
            else:
                grp = valid_pops.groupby('식품_세부분류')[['순수익(원)', '총_매출액(원)', '방문객_수(명)']].mean()
                best_food = grp['순수익(원)'].idxmax()
                best_rev = grp.loc[best_food, '총_매출액(원)']
                best_prof = grp.loc[best_food, '순수익(원)']
                best_vis = grp.loc[best_food, '방문객_수(명)']
                
                st.success(f"""
                **💡 {user_area_plan} 추천 전략**
                🍜 **{best_food}**
                📅 **{best_month}월** 오픈
                
                **📊 예상 평균 성과**
                💰 매출: {fmt_money(best_rev)}원
                💎 순수익: {fmt_money(best_prof)}원
                👥 방문객: {best_vis:,.0f}명
                """)
        else:
            st.warning("조건에 맞는 데이터가 부족해요. 예산을 조금 더 늘려보세요!")

    # 지도 페이지 전용 필터 변수 초기화 (오류 방지)
    min_cost, max_cost = 0, 300000000  # 3억원
    sel_cost = (min_cost, max_cost)
    min_dur, max_dur = int(df['운영_기간(일)'].min()), int(df['운영_기간(일)'].max())
    sel_dur = (min_dur, max_dur)

    st.markdown("---")
    st.markdown(f"<div style='font-size:0.75rem;color:#888;line-height:1.5'>", unsafe_allow_html=True)

fdf = df.copy()
if sel_area != '전체': fdf = fdf[fdf['상권구분']==sel_area]
if sel_food != '전체': fdf = fdf[fdf['식품_세부분류']==sel_food]
if sel_year != '전체': fdf = fdf[fdf['연도']==int(sel_year)]

if fdf.empty:
    st.warning("조건에 맞는 데이터가 없어요.")
    st.stop()

# ── 헤더 subtitle 동적 생성 ───────────────────────────────────
parts = []
if sel_area != '전체': parts.append(sel_area)
if sel_food != '전체': parts.append(sel_food)
if sel_year != '전체': parts.append(f"{sel_year}년")
filter_str = " · ".join(parts) if parts else "전체"

PAGE_DESC = {
    "📊 개요":"전체 팝업스토어 현황 요약",
    "📍 상권 및 위치 분석":"상권별 성과 분석 및 상세 위치 확인",
    "🍜 식품 분류 분석":"식품 카테고리별 방문객·매출·전환율",
    "💰 비용/수익 분석":"비용 구조 및 수익성 분석",
    "👥 연령대 분석":"연령대별 방문객 패턴 분석",
    "📣 마케팅 분석":"기사 노출·UGC·설문 응답률 분석",
}
st.markdown(f"""
<div class="dashboard-header">
    <p class="dashboard-title">{page}</p>
    <p class="dashboard-subtitle">{PAGE_DESC[page]} · {filter_str}</p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# 📊 개요
# ════════════════════════════════════════════════════════════
if page == "📊 개요":
    show_action_plan("시장 규모와 트렌드를 바탕으로 <b>현실적인 목표 KPI</b>를 설정하고, 성장세에 있는 분기를 공략하여 <b>오픈 시기</b>를 확정하세요.")

    # 1. 핵심 KPI 카드 (총량 중심)
    cols = st.columns(6)
    
    # 데이터 계산
    total_cnt = len(fdf)
    total_visit = fdf['방문객_수(명)'].sum()
    total_sales = fdf['총_매출액(원)'].sum()
    avg_atv = fdf['객단가(원)'].mean()
    avg_conv = fdf['구매_전환율(%)'].mean()
    avg_profit = fdf['순수익(원)'].mean()

    kpi_data = [
        (cols[0], f"{total_cnt:,}건", "총 팝업 운영 수", "#C8845A", f"{total_cnt:,}건"),
        (cols[1], f"{total_visit:,.0f}명", "총 방문객 수", "#3498DB", f"{total_visit:,.0f}명"),
        (cols[2], f"{fmt_money(total_sales)}원", "총 매출 합계", "#2ECC71", f"{total_sales:,.0f}원"),
        (cols[3], f"{avg_atv:,.0f}원", "평균 객단가", "#1ABC9C", f"{avg_atv:,.0f}원"),
        (cols[4], f"{avg_conv:.1f}%", "평균 구매 전환율", "#F39C12", f"{avg_conv:.1f}%"),
        (cols[5], f"{fmt_money(avg_profit)}원", "평균 순수익", "#9B59B6", f"{avg_profit:,.0f}원"),
    ]
    
    for c, v, l, clr, h in kpi_data:
        mc(c, v, l, clr, h)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. 연도별 월별 매출 트렌드 비교 (Line Chart)
    st.markdown('<p class="section-title">연도별 월별 평균 매출 트렌드 비교</p>', unsafe_allow_html=True)
    
    # 연도 필터 무시하고 상권/식품 필터만 적용한 데이터 준비 (비교를 위해)
    trend_df = df.copy()
    if sel_area != '전체': trend_df = trend_df[trend_df['상권구분']==sel_area]
    if sel_food != '전체': trend_df = trend_df[trend_df['식품_세부분류']==sel_food]
    
    trend_df['월'] = trend_df['시작일'].dt.month
    trend_df['연도_str'] = trend_df['연도'].astype(str)
    
    monthly_sales = trend_df.groupby(['연도_str', '월'])['총_매출액(원)'].mean().reset_index()
    
    fig = go.Figure()
    years = sorted(monthly_sales['연도_str'].unique())
    colors = ['#FFB300', '#3498DB', '#2ECC71', '#9B59B6', '#E74C3C', '#95A5A6']
    
    for i, year in enumerate(years):
        sub = monthly_sales[monthly_sales['연도_str'] == year]
        hover_txt = [fmt_money_hover(v) for v in sub['총_매출액(원)']]
        fig.add_trace(go.Scatter(x=sub['월'], y=sub['총_매출액(원)'], mode='lines+markers', name=year,
            line=dict(width=3, color=colors[i % len(colors)]), marker=dict(size=8),
            text=hover_txt, hovertemplate='%{text}<extra></extra>'))
    fig.update_layout(**L(350, margin=dict(t=50,b=40,l=40,r=40)), xaxis=dict(**ax(), title='월', tickmode='linear', tick0=1, dtick=1), yaxis=dict(**ax(), title='평균 매출액 (원)'))
    st.plotly_chart(fig, use_container_width=True)

    # 3. 분기별 운영 추이 & 상권별 매출 상위 분류
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-title">분기별 팝업 운영 수 추이</p>', unsafe_allow_html=True)
        qt_counts = fdf['분기'].value_counts().sort_index()
        
        fig = go.Figure(go.Bar(x=qt_counts.index, y=qt_counts.values,
            marker_color='#C8845A', opacity=0.85,
            text=[f"{v}건" for v in qt_counts.values], textposition='outside', textfont=dict(size=12),
            hovertemplate='%{y}건<extra></extra>'))
        fig.update_layout(**L(300), xaxis=dict(**ax(), title='분기'), yaxis=dict(**ax(), title='운영 수 (건)', range=[0, qt_counts.values.max()*1.2]))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown('<p class="section-title">상권별 매출 상위 분류</p>', unsafe_allow_html=True)
        top_cat = fdf.groupby(['상권구분', '식품_세부분류'])['총_매출액(원)'].mean().reset_index()
        top_cat = top_cat.sort_values(['상권구분', '총_매출액(원)'], ascending=[True, False]).groupby('상권구분').head(1)
        
        top_cat['총_매출액(원)'] = top_cat['총_매출액(원)'].apply(lambda x: f"{fmt_money(x)}원")
        top_cat.columns = ['상권', '카테고리', '평균 매출']
        
        st.dataframe(top_cat, use_container_width=True, hide_index=True, height=300)

    # 4. 운영 기간별 매출 & TOP 5
    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<p class="section-title">운영 기간(일수)별 평균 매출 추이</p>', unsafe_allow_html=True)
        dur_rev = fdf.groupby('운영_기간(일)')['총_매출액(원)'].mean().sort_index()
        
        # 텍스트 위치 동적 계산 (V자 곡선에서 겹침 방지)
        text_pos = []
        vals = dur_rev.values
        for i in range(len(vals)):
            prev_v = vals[i-1] if i > 0 else vals[i]
            next_v = vals[i+1] if i < len(vals)-1 else vals[i]
            # 양옆보다 낮거나 같으면(Local Min) 아래로, 아니면 위로
            if vals[i] <= prev_v and vals[i] <= next_v: text_pos.append('bottom center')
            else: text_pos.append('top center')
            
        fig = go.Figure(go.Scatter(x=dur_rev.index, y=dur_rev.values,
            mode='lines+markers+text', marker=dict(color='#5F27CD', size=8),
            line=dict(color='#5F27CD', width=3),
            text=[f"{fmt_money(v)}원" for v in dur_rev.values], textposition=text_pos, textfont=dict(size=12, weight='bold', color='#3D2B1F')))
        fig.update_layout(**L(300, margin=dict(t=80,b=40,l=40,r=40)), xaxis=dict(**ax(), title='운영 기간 (일)'), yaxis=dict(**ax(), title='평균 매출 (원)', range=[0, dur_rev.values.max()*1.2]))
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        st.markdown('<p class="section-title">🏆 매출 기준 TOP 5 팝업스토어</p>', unsafe_allow_html=True)
        top5 = fdf.sort_values('총_매출액(원)', ascending=False).head(5)[
            ['상권구분','식품_세부분류','상세_주소','총_매출액(원)','방문객_수(명)','순수익(원)','시작일','종료일','운영_기간(일)']
        ].copy()
        top5['시작일'] = top5['시작일'].dt.strftime('%Y-%m-%d')
        top5['종료일'] = top5['종료일'].dt.strftime('%Y-%m-%d')
        top5['운영_기간(일)'] = top5['운영_기간(일)'].apply(lambda x: f"{int(x)}일")
        top5['총_매출액(원)'] = top5['총_매출액(원)'].apply(lambda x: f"{fmt_money(x)}원")
        top5['순수익(원)'] = top5['순수익(원)'].apply(lambda x: f"{fmt_money(x)}원")
        top5['방문객_수(명)'] = top5['방문객_수(명)'].apply(lambda x: f"{x:,.0f}명")
        top5.columns = ['상권','카테고리','팝업명(주소)','매출','방문객','순수익','시작일','종료일','운영기간']
        st.dataframe(top5, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════
# 📍 상권 및 위치 분석 (통합)
# ════════════════════════════════════════════════════════════
elif page == "📍 상권 및 위치 분석":
    if 'drill_area' not in st.session_state:
        st.session_state['drill_area'] = None
    if 'prev_clicked' not in st.session_state:
        st.session_state['prev_clicked'] = None

    show_action_plan("관심 상권 내 경쟁 팝업들의 성과를 비교하여, <b>예상 매출 대비 대관료 효율</b>이 가장 좋은 구체적인 입지 후보군을 2~3곳 선정하세요.")

    # ── 상단 레이아웃 구성 (지도 | 필터+요약) ────────────────
    map_col, summary_col = st.columns([1.8, 1.2])

    # 1. 필터 (우측 상단 배치)
    with summary_col:
        st.markdown('<p class="section-title" style="margin-top: 0;">필터 설정</p>', unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        with f1:
            sel_cost = st.slider("예산 범위 (총 지출)", 0, max_cost, (0, max_cost), step=100000, format="%d원")
        with f2:
            sel_dur = st.slider("운영 기간 (일)", min_dur, max_dur, (min_dur, max_dur))
        st.markdown("---")

    # 지도 전용 필터 적용
    fdf = fdf[(fdf['총_지출_비용(원)'] >= sel_cost[0]) & (fdf['총_지출_비용(원)'] <= sel_cost[1])]
    fdf = fdf[(fdf['운영_기간(일)'] >= sel_dur[0]) & (fdf['운영_기간(일)'] <= sel_dur[1])]
    fdf = fdf.reset_index(drop=True)

    if fdf.empty:
        st.warning("선택하신 조건에 맞는 팝업스토어가 없습니다. 우측 필터 조건을 조정해주세요.")
        st.stop()

    with map_col:
        c_search, c_reset = st.columns([3, 1])
        with c_search:
            # 검색 가능한 Selectbox로 변경 (자동완성 효과)
            search_options = sorted(fdf['상권구분'].unique().tolist())
            
            # 외부(지도 클릭 등)에서 drill_area가 변경되었을 때 selectbox에 반영
            if st.session_state['drill_area'] in search_options:
                st.session_state['area_search_select'] = st.session_state['drill_area']
            else:
                st.session_state['area_search_select'] = None

            def on_search_change():
                st.session_state['drill_area'] = st.session_state['area_search_select']
                st.session_state['prev_clicked'] = None

            st.selectbox(
                "상권 검색",
                options=search_options,
                index=None,
                placeholder="지역명 검색 (예: 성수, 홍대)",
                label_visibility="collapsed",
                key="area_search_select",
                on_change=on_search_change
            )
        with c_reset:
            def reset_callback():
                st.session_state['drill_area'] = None
                st.session_state['prev_clicked'] = None
                st.session_state['area_search_select'] = None
            
            st.button("🔄 초기화", use_container_width=True, on_click=reset_callback)

        # 현재 위치 표시
        if st.session_state['drill_area']:
            cur_loc = f"📍 현재 위치: {st.session_state['drill_area']}"
        else:
            cur_loc = "📍 전체 상권 (지도를 클릭하거나 검색하세요)"
        st.markdown(f"<div style='font-size:0.95rem; font-weight:600; color:#3D2B1F; margin-bottom:10px;'>{cur_loc}</div>", unsafe_allow_html=True)

        # 지도 중심 설정
        if st.session_state['drill_area']:
            center_df = fdf[fdf['상권구분'] == st.session_state['drill_area']]
            map_center = [center_df['위도'].mean(), center_df['경도'].mean()] \
                if not center_df.empty else [35.8, 128.0]
            map_zoom = 13
        else:
            map_center = [35.8, 128.0]  # 한국 전체 중심 (제주 포함)
            map_zoom = 7

        map_key = f"map_{st.session_state['drill_area']}"
        m = folium.Map(location=map_center, zoom_start=map_zoom)

        # 클러스터 추가 (줌아웃 시 개수 표시)
        marker_cluster = MarkerCluster().add_to(m)

        # CircleMarker로 교체 (클릭 감지 안정적)
        for idx, row in fdf.iterrows():
            is_selected = (st.session_state['drill_area'] == row['상권구분'])
            color = '#C8845A' if is_selected else '#3498DB'
            radius = 10 if is_selected else 7

            popup_html = f"""
            <div style="font-family: sans-serif; font-size: 13px;">
            <b>{row['상세_주소']}</b><hr style="margin:5px 0;">
            <b>카테고리:</b> {row['식품_세부분류']}<br>
            <b>운영기간:</b> {row['운영_기간(일)']}일<br>
            <b>방문객:</b> {row['방문객_수(명)']:,.0f}명<br>
            <b>총 지출:</b> {row['총_지출_비용(원)']:,.0f}원<br>
            <b>총 매출:</b> {row['총_매출액(원)']:,.0f}원<br>
            <b>순수익:</b> <span style="color:{'red' if row['순수익(원)'] < 0 else 'blue'};">
            {row['순수익(원)']:,.0f}원</span>
            </div>
            """
            folium.CircleMarker(
                location=[row['위도'], row['경도']],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                popup=folium.Popup(
                    folium.IFrame(popup_html, width=240, height=170), max_width=240
                ),
                tooltip=f"{row['상세_주소']} ({row['식품_세부분류']})"
            ).add_to(marker_cluster)

        map_data = st_folium(m, use_container_width=True, height=500, key=map_key,
                             returned_objects=["last_object_clicked", "bounds"])

        # ── 클릭 감지 ──────────────────────────────────────
        if map_data and map_data.get('last_object_clicked'):
            lat = map_data['last_object_clicked'].get('lat')
            lng = map_data['last_object_clicked'].get('lng')

            if lat and lng:
                matched = fdf[
                    (fdf['위도'].sub(lat).abs() < 0.0001) &
                    (fdf['경도'].sub(lng).abs() < 0.0001)
                ]
                if not matched.empty:
                    new_area = matched.iloc[0]['상권구분']
                    clicked_key = f"{round(lat,4)}_{round(lng,4)}"
                    if st.session_state['prev_clicked'] != clicked_key:
                        st.session_state['prev_clicked'] = clicked_key
                        st.session_state['drill_area'] = new_area
                        st.rerun()

        # ── bounds 기반 view_df 결정 ───────────────────────
        # 수정: 지도의 줌/이동(bounds)에 따라 데이터가 동적으로 변하도록 순서 변경
        if map_data and map_data.get('bounds'):
            bounds = map_data['bounds']
            lat_min = bounds['_southWest']['lat']
            lat_max = bounds['_northEast']['lat']
            lng_min = bounds['_southWest']['lng']
            lng_max = bounds['_northEast']['lng']
            view_df = fdf[
                (fdf['위도'] >= lat_min) & (fdf['위도'] <= lat_max) &
                (fdf['경도'] >= lng_min) & (fdf['경도'] <= lng_max)
            ].copy()
            
            # 화면 내 상권이 하나뿐이면 카테고리별 분석으로 자동 전환
            if view_df['상권구분'].nunique() == 1:
                grp_col = '식품_세부분류'
                area_name = view_df['상권구분'].iloc[0]
                level_name = f"📌 {area_name} 상권 ({len(view_df)}개 팝업)"
            else:
                grp_col = '상권구분'
                level_name = f"🗺️ 현재 지도 화면 범위 ({len(view_df)}개 팝업)"
        elif st.session_state['drill_area']:
            # 지도 로딩 직후라 bounds가 아직 안 넘어왔을 때 fallback
            view_df = fdf[fdf['상권구분'] == st.session_state['drill_area']].copy()
            grp_col = '식품_세부분류'
            level_name = f"📌 {st.session_state['drill_area']} 상권"
        else:
            view_df = fdf.copy()
            grp_col = '상권구분'
            level_name = "전체 상권"

    with summary_col:
        st.markdown('<p class="section-title">상권별 핵심 지표 요약</p>', unsafe_allow_html=True)
        summary_df = view_df.groupby('상권구분').agg(
            평균대관료=('대관료(원)', 'mean'),
            평균총지출=('총_지출_비용(원)', 'mean'),
            평균순수익=('순수익(원)', 'mean'),
            평균방문객=('방문객_수(명)', 'mean')
        ).reset_index()
        for c in ['평균대관료', '평균총지출', '평균순수익']:
            summary_df[c] = summary_df[c].apply(lambda x: f"{fmt_money(x)}원")
        summary_df['평균방문객'] = summary_df['평균방문객'].apply(lambda x: f"{x:,.0f}명")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── 하단: 연동 그래프 ──────────────────────────────────
    if view_df.empty:
        st.info("현재 지도 화면 범위에 데이터가 없습니다. 지도를 이동하거나 줌아웃해보세요.")
        st.stop()

    st.markdown(f'<p class="section-title">{level_name} — 핵심 지표 비교</p>', unsafe_allow_html=True)

    area_agg = view_df.groupby(grp_col).agg(
        방문객=('방문객_수(명)','mean'),
        매출=('총_매출액(원)','mean'),
        전환율=('구매_전환율(%)','mean'),
        순수익=('순수익(원)', 'mean')
    )
    
    c1, c2, c3, c4 = st.columns(4)
    for col_obj, key, label, color in [
        (c1, '방문객', '평균 방문객 (명)', '#3498DB'),
        (c2, '매출', '평균 매출 (원)', '#2ECC71'),
        (c3, '전환율', '평균 전환율 (%)', '#F39C12'),
        (c4, '순수익', '평균 순수익 (원)', '#9B59B6'),
    ]:
        with col_obj:
            df_sorted = area_agg.sort_values(key, ascending=True)
            if key == '전환율':
                text_fmt = [f"{v:.1f}%" for v in df_sorted[key]]
            elif key in ['매출', '순수익']:
                text_fmt = [f"{fmt_money(v)}원" for v in df_sorted[key]]
            else:
                text_fmt = [f"{v:,.0f}명" for v in df_sorted[key]]
            
            if key == '전환율': ht = '%{x:.1f}%<extra></extra>'
            elif key == '방문객': ht = '%{x:,.0f}명<extra></extra>'
            else: ht = '%{x:,.0f}원<extra></extra>'

            fig = go.Figure(go.Bar(
                x=df_sorted[key],
                y=df_sorted.index,
                orientation='h',
                marker_color=color,
                text=text_fmt,
                textposition='outside',
                hovertemplate=ht
            ))
            fig.update_layout(
                **L(300, margin=dict(t=50, b=20, l=10, r=40)),
                title=label,
                xaxis=dict(**ax(), range=[0, df_sorted[key].max() * 1.35]),
                yaxis=dict(**ax())
            )
            st.plotly_chart(fig, use_container_width=True, key=f"area_kpi_{key}_{st.session_state['drill_area']}")

    # 운영기간 분포 + 상세 목록
    c5, c6 = st.columns([1, 1.2])
    with c5:
        st.markdown(f'<p class="section-title">{level_name} — 평균 운영 기간 비교</p>', unsafe_allow_html=True)
        dur_agg = view_df.groupby(grp_col)['운영_기간(일)'].mean().sort_values(ascending=False)
        fig = go.Figure(go.Scatter(x=dur_agg.index, y=dur_agg.values, mode='lines+markers+text',
            line=dict(color='#9B59B6', width=3), marker=dict(size=8),
            text=[f"{v:.1f}일" for v in dur_agg.values], textposition='top center',
            textfont=dict(size=12, weight='bold', color='#3D2B1F'),
            hovertemplate='%{y:.1f}일<extra></extra>'))
        
        # 차이를 극적으로 보여주기 위해 Y축 범위 조정 (최소값의 50%부터 시작)
        y_min = dur_agg.min() * 0.5
        y_max = dur_agg.max() * 1.15
        
        fig.update_layout(
            **L(320, margin=dict(t=80, b=40, l=40, r=40)),
            xaxis=dict(**ax(), type='category'),
            yaxis=dict(**ax(), title='평균 운영 기간 (일)', range=[y_min, y_max])
        )
        st.plotly_chart(fig, use_container_width=True, key="area_dur_bar")

    with c6:
        st.markdown(f'<p class="section-title">{level_name} — 상세 목록 (매출순)</p>', unsafe_allow_html=True)
        show_cols = ['식품_세부분류', '상세_주소', '총_매출액(원)', '방문객_수(명)', '순수익(원)']
        show_df = view_df[show_cols].sort_values('총_매출액(원)', ascending=False).copy()
        show_df['총_매출액(원)'] = show_df['총_매출액(원)'].apply(lambda x: f"{fmt_money(x)}원")
        show_df['방문객_수(명)'] = show_df['방문객_수(명)'].apply(lambda x: f"{x:,.0f}명")
        show_df['순수익(원)'] = show_df['순수익(원)'].apply(lambda x: f"{fmt_money(x)}원")
        st.dataframe(show_df, use_container_width=True, hide_index=True, height=320)

# ════════════════════════════════════════════════════════════
# 🍜 식품 분류 분석
# ════════════════════════════════════════════════════════════
elif page == "🍜 식품 분류 분석":
    show_action_plan("선정된 카테고리의 <b>성공 사례(Top 10)</b>를 벤치마킹하여 메뉴 구성과 가격 정책을 다듬고, <b>최적의 운영 기간</b>을 설정하세요.")

    # 1. 핵심 지표 비교 (매출 / 방문객 / 객단가)
    st.markdown('<p class="section-title">카테고리별 핵심 지표 비교 (매출 / 방문객 / 객단가)</p>', unsafe_allow_html=True)
    
    food_agg = fdf.groupby('식품_세부분류').agg(
        매출=('총_매출액(원)','mean'),
        방문객=('방문객_수(명)','mean'),
        객단가=('객단가(원)','mean'),
        전환율=('구매_전환율(%)','mean'),
        운영기간=('운영_기간(일)','mean'),
        건수=('방문객_수(명)','count')
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        df_r = food_agg.sort_values('매출', ascending=False)
        fig = go.Figure(go.Bar(x=df_r.index, y=df_r['매출'], marker_color='#2ECC71',
            text=[f"{fmt_money(v)}원" for v in df_r['매출']], textposition='outside',
            hovertemplate='%{y:,.0f}원<extra></extra>'))
        fig.update_layout(**L(320, margin=dict(t=80,b=40,l=40,r=40)), title="평균 매출 (원)", xaxis=dict(**ax()), yaxis=dict(**ax(), range=[0, df_r['매출'].max()*1.15]))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        df_v = food_agg.sort_values('방문객', ascending=False)
        fig = go.Figure(go.Bar(x=df_v.index, y=df_v['방문객'], marker_color='#3498DB',
            text=[f"{v:,.0f}명" for v in df_v['방문객']], textposition='outside',
            hovertemplate='%{y:,.0f}명<extra></extra>'))
        fig.update_layout(**L(320, margin=dict(t=80,b=40,l=40,r=40)), title="평균 방문객 (명)", xaxis=dict(**ax()), yaxis=dict(**ax(), range=[0, df_v['방문객'].max()*1.15]))
        st.plotly_chart(fig, use_container_width=True)
    with c3:
        df_p = food_agg.sort_values('객단가', ascending=False)
        fig = go.Figure(go.Bar(x=df_p.index, y=df_p['객단가'], marker_color='#9B59B6',
            text=[f"{v:,.0f}원" for v in df_p['객단가']], textposition='outside',
            hovertemplate='%{y:,.0f}원<extra></extra>'))
        fig.update_layout(**L(320, margin=dict(t=80,b=40,l=40,r=40)), title="평균 객단가 (원)", xaxis=dict(**ax()), yaxis=dict(**ax(), range=[0, df_p['객단가'].max()*1.15]))
        st.plotly_chart(fig, use_container_width=True)

    # 2. 구매 전환율 랭킹 & 상권별 카테고리 성과 (히트맵)
    c4, c5 = st.columns(2)
    with c4:
        st.markdown('<p class="section-title">카테고리별 평균 구매 전환율 랭킹</p>', unsafe_allow_html=True)
        df_c = food_agg[['전환율']].sort_values('전환율', ascending=False).reset_index()
        df_c['순위'] = df_c.index + 1
        df_c['전환율'] = df_c['전환율'].apply(lambda x: f"{x:.1f}%")
        df_c = df_c[['순위', '식품_세부분류', '전환율']]
        st.dataframe(df_c, use_container_width=True, hide_index=True, height=350)
    with c5:
        st.markdown('<p class="section-title">상권별 카테고리 매출</p>', unsafe_allow_html=True)
        # 히트맵 -> Grouped Bar (X=상권, Y=매출, Color=카테고리)
        grp = fdf.groupby(['상권구분', '식품_세부분류'])['총_매출액(원)'].mean().unstack()
        fig = go.Figure()
        for col in grp.columns:
            fig.add_trace(go.Bar(name=col, x=grp.index, y=grp[col],
                hovertemplate='%{y:,.0f}원<extra></extra>'))
        fig.update_layout(**L(350), barmode='group', xaxis=dict(**ax(), title='상권'), yaxis=dict(**ax(), title='평균 매출 (원)'))
        st.plotly_chart(fig, use_container_width=True)

    # 3. 운영 기간 vs 매출 상관관계 (카테고리별)
    st.markdown('<p class="section-title">카테고리별 평균 운영 기간 vs 평균 매출 상관관계</p>', unsafe_allow_html=True)
    fig = go.Figure()
    cats = sorted(food_agg.index)
    for i, cat in enumerate(cats):
        row = food_agg.loc[cat]
        fig.add_trace(go.Scatter(
            x=[row['운영기간']], y=[row['매출']],
            mode='markers+text',
            marker=dict(size=15, color=FOOD_COLORS[i % len(FOOD_COLORS)], opacity=0.8, line=dict(width=1, color='white')),
            text=cat, textposition='top center', textfont=dict(size=12),
            hovertemplate=f"<b>{cat}</b><br>평균 운영: {row['운영기간']:.1f}일<br>평균 매출: {row['매출']:,.0f}원<br>건수: {row['건수']}건<extra></extra>"
        ))
    fig.add_vline(x=food_agg['운영기간'].mean(), line_width=1, line_dash="dash", line_color="gray")
    fig.add_hline(y=food_agg['매출'].mean(), line_width=1, line_dash="dash", line_color="gray")
    fig.update_layout(**L(400, margin=dict(t=80, b=40, l=40, r=40)), 
        xaxis=dict(**ax(), title='평균 운영 기간 (일)'),
        yaxis=dict(**ax(), title='평균 매출 (원)'),
        showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════
# 💰 비용/수익 분석
# ════════════════════════════════════════════════════════════
elif page == "💰 비용/수익 분석":
    show_action_plan("매출 상위 그룹의 <b>지출 패턴</b>을 참고하여 예산을 배분하고, 손익분기점을 넘기기 위한 <b>일일 최소 목표 매출액</b>을 산출하세요.")

    # ── 예산 입력 및 필터링 ──────────────────────────────────
    user_budget_analysis = st.number_input("나의 가용 예산 (원)", min_value=0, value=0, step=5000000, format="%d")

    if user_budget_analysis > 0:
        # 예산 수준 분석 (백분위 및 예상 매출)
        costs = fdf['총_지출_비용(원)']
        if not costs.empty:
            pct_rank = (costs < user_budget_analysis).mean() * 100
            top_pct = 100 - pct_rank
            
            if pct_rank >= 66:
                tier = "상위 33%"
                t_color = "#E74C3C"
            elif pct_rank >= 33:
                tier = "중위 33%"
                t_color = "#F39C12"
            else:
                tier = "하위 33%"
                t_color = "#2ECC71"
            
            # 유사 예산 구간(±20%)의 평균 ROI로 예상 매출 산출
            similar_df = fdf[(costs >= user_budget_analysis * 0.8) & (costs <= user_budget_analysis * 1.2)]
            roi = similar_df['총_매출액(원)'].sum() / similar_df['총_지출_비용(원)'].sum() if not similar_df.empty else fdf['총_매출액(원)'].sum() / fdf['총_지출_비용(원)'].sum()
            exp_sales = user_budget_analysis * roi
            
            st.markdown(f"""
            <div style="background-color: #FFF8E1; border: 1px solid #FFE082; border-radius: 10px; padding: 15px; margin-top: 10px; margin-bottom: 20px;">
                <div style="color: #F57F17; font-weight: 700; font-size: 1.1rem; margin-bottom: 5px;">💡 예산 분석 리포트</div>
                <div style="color: #4E342E; font-size: 1.0rem; line-height: 1.6;">
                    입력하신 <b>{fmt_money(user_budget_analysis)}원</b>은 전체 팝업 중 <span style="color:{t_color}; font-weight:800;">{tier} (상위 {top_pct:.1f}%)</span> 수준입니다.<br>
                    동일 규모 운영 시, 예상되는 총 매출액은 약 <b>{fmt_money(exp_sales)}원</b>입니다.
                </div>
            </div>
            """, unsafe_allow_html=True)

    cost_labels = ['대관료','인테리어','마케팅','운영인건비','물류기타']
    cost_clrs   = ['#FFB300','#3498DB','#F39C12','#2ECC71','#9B59B6']
    cost_descs  = [
        "공간 임대비, 임차 보증금, 단기 렌탈비",
        "도색비, 소품/집기 구매, 간판 제작, 조명 설치, 공간 연출비",
        "SNS 광고비, 인플루언서 협찬, 현수막/배너 제작, 기사 배포비",
        "스태프 일당, 알바비, 매니저 급여",
        "제품 운송비, 포장재, 재고 보관비, 기타 잡비"
    ]

    # 1. 평균 비용 구성
    st.markdown('<p class="section-title">평균 비용 구성</p>', unsafe_allow_html=True)
    
    sec1_df = pd.DataFrame()
    if user_budget_analysis > 0:
        sec1_df = fdf[fdf['총_지출_비용(원)'] <= user_budget_analysis].copy()
        if sec1_df.empty:
            st.warning(f"설정하신 예산 ({fmt_money(user_budget_analysis)}원) 이하로 운영된 팝업스토어 데이터가 없습니다.")
    else:
        st.info("예산을 입력하면 해당 예산 범위 내의 평균 비용 구성을 분석합니다.")

    c_pie, c_desc = st.columns([1.6, 1])
    with c_pie:
        if not sec1_df.empty:
            avg_costs = [sec1_df[c].mean() for c in cost_cols]
            fig = go.Figure(go.Pie(labels=cost_labels, values=avg_costs,
                marker_colors=cost_clrs, hole=0.42, textinfo='percent+label', textposition='outside', textfont_size=13))
            fig.update_layout(**L(400, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)), showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
    with c_desc:
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        for label, color, desc in zip(cost_labels, cost_clrs, cost_descs):
            st.markdown(f"""
            <div style="background-color: #f9f9f9; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid {color}; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-weight: 700; color: #333; font-size: 0.9rem;">{label}</div>
                <div style="color: #666; font-size: 0.8rem; margin-top: 3px; line-height: 1.4;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # 2. 매출 구간별 비용 구조 (파이 차트 3개)
    st.markdown('<p class="section-title">매출 구간별 비용 구조</p>', unsafe_allow_html=True)
    st.info(f"💡 전체 **{len(fdf):,}개** 팝업스토어를 **총 매출액 기준**으로 **하위 33% / 중위 33% / 상위 33%**로 구분하여, 성과 그룹별 비용 지출 패턴을 분석합니다.")
    
    try:
        fdf['매출구간'] = pd.qcut(fdf['총_매출액(원)'], q=3, labels=['하위 33%','중위 33%','상위 33%'])
    except:
        fdf['매출구간'] = '전체'

    c_charts, c_desc = st.columns([3, 1])

    with c_charts:
        c1, c2, c3 = st.columns(3)
        tiers = ['하위 33%', '중위 33%', '상위 33%']
        cols = [c1, c2, c3]
        for i, tier in enumerate(tiers):
            with cols[i]:
                tier_df = fdf[fdf['매출구간'] == tier]
                if not tier_df.empty:
                    st.markdown(f"<h6 style='text-align: center;'>{tier} 그룹</h6>", unsafe_allow_html=True)
                    tier_costs = [tier_df[c].mean() for c in cost_cols]
                    fig = go.Figure(go.Pie(labels=cost_labels, values=tier_costs,
                        marker_colors=cost_clrs, hole=0.4, textinfo='percent+label', textposition='inside', textfont_size=11))
                    fig.update_layout(**L(300, margin=dict(t=20,b=20,l=20,r=20)), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True, key=f"cost_tier_{i}")
    
    with c_desc:
        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
        for label, color in zip(cost_labels, cost_clrs):
            st.markdown(f"""
            <div style="background-color: #f9f9f9; padding: 8px 12px; border-radius: 6px; margin-bottom: 8px; border-left: 5px solid {color}; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                <div style="font-weight: 600; color: #333; font-size: 0.85rem;">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<hr>", unsafe_allow_html=True)

    # 3. 손익분기점 & 마케팅비 효율
    c4,c5 = st.columns(2)
    with c4:
        st.markdown('<p class="section-title">총 비용 구간별 평균 매출</p>', unsafe_allow_html=True)
        fdf['비용구간'] = pd.cut(fdf['총_지출_비용(원)'], bins=5)
        cost_grp = fdf.groupby('비용구간', observed=True)['총_매출액(원)'].mean()
        x_labels = [f"{fmt_money(i.left)}~{fmt_money(i.right)}" for i in cost_grp.index]
        fig = go.Figure(go.Bar(x=x_labels, y=cost_grp.values, marker_color='#2ECC71', 
            text=[f"{fmt_money(v)}원" for v in cost_grp.values], textposition='outside',
            hovertemplate='%{y:,.0f}원<extra></extra>'))
        fig.update_layout(**L(350, margin=dict(t=80,b=40,l=40,r=40)), xaxis=dict(**ax(), title='총 비용 구간 (만원)'), yaxis=dict(**ax(), title='평균 매출 (원)', range=[0, cost_grp.values.max()*1.2]))
        st.plotly_chart(fig, use_container_width=True)
    with c5:
        st.markdown('<p class="section-title">마케팅비 구간별 평균 구매 전환율</p>', unsafe_allow_html=True)
        # 마케팅비를 5개 구간으로 나눔
        fdf['마케팅비구간'] = pd.qcut(fdf['마케팅비(원)'], q=5, duplicates='drop')
        m_grp = fdf.groupby('마케팅비구간', observed=True)['구매_전환율(%)'].mean()
        
        # x축 라벨을 구간의 평균값이나 범위로 표시
        x_labels = [f"{fmt_money(i.left)}~{fmt_money(i.right)}" for i in m_grp.index]
        
        fig = go.Figure(go.Scatter(x=x_labels, y=m_grp.values, mode='lines+markers+text', line=dict(color='#9B59B6', width=3), 
            text=[f"{v:.1f}%" for v in m_grp.values], textposition='top center', textfont=dict(size=12, weight='bold', color='#3D2B1F')))
        fig.update_layout(**L(350, margin=dict(t=80,b=40,l=40,r=40)), xaxis=dict(**ax(), title='마케팅비 구간 (만원)'), yaxis=dict(**ax(), title='평균 구매 전환율 (%)', range=[0, m_grp.values.max()*1.2]))
        st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════
# 👥 연령대 분석
# ════════════════════════════════════════════════════════════
elif page == "👥 연령대 분석":
    # 가장 비중이 높은 연령대 계산 (Action Plan용)
    top_age_col = fdf[AGE_COLS].sum().idxmax()
    top_age_label = AGE_LABELS[AGE_COLS.index(top_age_col)]
    
    show_action_plan(f"주력 타겟인 <b>{top_age_label}</b>의 취향을 저격하는 <b>공간 컨셉</b>을 기획하고, 이들이 주로 활동하는 채널에 마케팅 리소스를 집중하세요.")

    # 주력 연령대 계산 (각 팝업에서 가장 방문객이 많은 연령대)
    def get_dom_age(r):
        vals = r[AGE_COLS].values
        return AGE_LABELS[np.argmax(vals)]
    fdf['주력_연령대'] = fdf.apply(get_dom_age, axis=1)

    # 1. 전체 비율 (도넛) & 카테고리별 선호도 (Stacked Bar)
    c1, c2 = st.columns([1.2, 1.8])
    with c1:
        st.markdown('<p class="section-title">전체 연령대 방문객 비율</p>', unsafe_allow_html=True)
        total_age = [fdf[c].sum() for c in AGE_COLS]
        fig = go.Figure(go.Pie(labels=AGE_LABELS, values=total_age,
            marker_colors=AGE_CLRS, hole=0.4, textinfo='percent+label', textposition='outside', textfont_size=13))
        fig.update_layout(**L(320), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown('<p class="section-title">전년 대비 연령대별 방문 증감률</p>', unsafe_allow_html=True)
        
        # YoY 계산을 위해 연도 필터 무시한 데이터셋 생성 (상권/식품 필터는 유지)
        yoy_df = df.copy()
        if sel_area != '전체': yoy_df = yoy_df[yoy_df['상권구분']==sel_area]
        if sel_food != '전체': yoy_df = yoy_df[yoy_df['식품_세부분류']==sel_food]
        
        yoy_df['분기_p'] = yoy_df['시작일'].dt.to_period('Q')
        qa_base = yoy_df.groupby('분기_p')[AGE_COLS].sum()
        
        # 현재 필터링된 기간(fdf)에 해당하는 분기 식별
        valid_qs = fdf['분기'].unique()
        current_periods = [pd.Period(q, freq='Q') for q in valid_qs]
        prev_periods = [p - 4 for p in current_periods] # 1년 전 (4분기 전)
        
        # 현재 기간 합계 & 전년 동기 합계 계산
        curr_sum = qa_base.loc[qa_base.index.isin(current_periods)].sum()
        prev_sum = qa_base.loc[qa_base.index.isin(prev_periods)].sum()
        
        # KPI 카드 그리드 (3열 x 2행)
        kpi_cols = st.columns(3)
        for i, (col_name, label) in enumerate(zip(AGE_COLS, AGE_LABELS)):
            c_val = curr_sum.get(col_name, 0)
            p_val = prev_sum.get(col_name, 0)
            
            if p_val > 0:
                rate = ((c_val - p_val) / p_val) * 100
                symbol = "▲" if rate > 0 else "▼" if rate < 0 else "-"
                color = "#2ECC71" if rate > 0 else "#E74C3C" if rate < 0 else "#7F8C8D"
                val_text = f"{symbol} {abs(rate):.1f}%"
            else:
                val_text = "-"
                color = "#999"
            
            with kpi_cols[i % 3]:
                st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color:{color}">{val_text}</div>
                <div class="metric-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)

    # 2. 상권별 분포 & 분기별 추이
    c3,c4 = st.columns(2)
    with c3:
        st.markdown('<p class="section-title">연령대별 상권 방문 분포</p>', unsafe_allow_html=True)
        # X=연령대, Color=상권
        aa = fdf.groupby('상권구분')[AGE_COLS].mean().T # Index=Age, Cols=Area
        aa.index = AGE_LABELS
        fig = go.Figure()
        for i, area in enumerate(aa.columns):
            fig.add_trace(go.Bar(name=area, x=aa.index, y=aa[area], marker_color=AREA_COLORS[i%len(AREA_COLORS)],
                hovertemplate='%{y:,.0f}명<extra></extra>'))
        fig.update_layout(**L(320), barmode='group', xaxis=dict(**ax(), title='연령대'), yaxis=dict(**ax(), title='평균 방문객'))
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        st.markdown('<p class="section-title">연령대별 선호 카테고리</p>', unsafe_allow_html=True)
        # X=연령대, Color=카테고리
        fa = fdf.groupby('식품_세부분류')[AGE_COLS].mean().T # Index=Age, Cols=Category
        fa.index = AGE_LABELS
        fig = go.Figure()
        for i, cat in enumerate(fa.columns):
            fig.add_trace(go.Bar(name=cat, x=fa.index, y=fa[cat], marker_color=FOOD_COLORS[i%len(FOOD_COLORS)],
                hovertemplate='%{y:,.0f}명<extra></extra>'))
        fig.update_layout(**L(320), barmode='group', xaxis=dict(**ax(), title='연령대'), yaxis=dict(**ax(), title='평균 방문객'))
        st.plotly_chart(fig, use_container_width=True)

    # 3. 랭킹 테이블
    st.markdown('<p class="section-title">연령대별 상위 팝업 랭킹</p>', unsafe_allow_html=True)
    target_age_label = st.selectbox("타겟 연령대 선택", AGE_LABELS, key='age_rank_sel')
    target_col = AGE_COLS[AGE_LABELS.index(target_age_label)]
    
    # 비율 계산
    fdf_rank = fdf[fdf['방문객_수(명)'] > 0].copy()
    fdf_rank['비율'] = (fdf_rank[target_col] / fdf_rank['방문객_수(명)']) * 100
    
    top10 = fdf_rank.sort_values('비율', ascending=False).head(10)
    top10_disp = top10[['상권구분','식품_세부분류','상세_주소','방문객_수(명)', target_col, '비율']].copy()
    top10_disp.columns = ['상권','카테고리','팝업명(주소)','총 방문객', f'{target_age_label} 방문객', f'{target_age_label} 비율']
    top10_disp[f'{target_age_label} 비율'] = top10_disp[f'{target_age_label} 비율'].apply(lambda x: f"{x:.1f}%")
    top10_disp['총 방문객'] = top10_disp['총 방문객'].apply(lambda x: f"{x:,.0f}명")
    top10_disp[f'{target_age_label} 방문객'] = top10_disp[f'{target_age_label} 방문객'].apply(lambda x: f"{x:,.0f}명")
    
    st.dataframe(top10_disp, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════
# 📣 마케팅 분석
# ════════════════════════════════════════════════════════════
elif page == "📣 마케팅 분석":
    show_action_plan("초기 모객을 위한 <b>사전 예약 프로모션</b>을 기획하고, 방문객이 자발적으로 콘텐츠를 생산(UGC)하도록 유도하는 <b>현장 이벤트</b>를 준비하세요.")

    # 1. 마케팅 4대 핵심 지표 KPI 카드
    st.markdown('<p class="section-title">마케팅 4대 핵심 지표 (평균)</p>', unsafe_allow_html=True)
    cols = st.columns(4)
    metrics = [
        ('UGC_리뷰_참여율(%)', 'UGC 참여율', '#C8845A'),
        ('브랜드_신뢰도(5점)', '브랜드 신뢰도', '#9B59B6'),
        ('구매_전환율(%)', '구매 전환율', '#3498DB'),
        ('사전예약율', '사전 예약률', '#F39C12')
    ]
    for col, (col_name, label, color) in zip(cols, metrics):
        val = fdf[col_name].mean()
        fmt = f"{val:.2f}점" if '점' in col_name else f"{val:.1f}%"
        mc(col, fmt, label, color, fmt)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. 전년 동분기 대비 마케팅 지표 (YoY)
    st.markdown('<p class="section-title">전년 동분기 대비 마케팅 지표</p>', unsafe_allow_html=True)
    
    # YoY 계산을 위해 연도 필터 무시한 데이터셋 생성
    yoy_mk_df = df.copy()
    if sel_area != '전체': yoy_mk_df = yoy_mk_df[yoy_mk_df['상권구분']==sel_area]
    if sel_food != '전체': yoy_mk_df = yoy_mk_df[yoy_mk_df['식품_세부분류']==sel_food]
    
    yoy_mk_df['분기_p'] = yoy_mk_df['시작일'].dt.to_period('Q')
    
    valid_qs = fdf['분기'].unique()
    current_periods = [pd.Period(q, freq='Q') for q in valid_qs]
    prev_periods = [p - 4 for p in current_periods]
    
    curr_df = yoy_mk_df[yoy_mk_df['분기_p'].isin(current_periods)]
    prev_df = yoy_mk_df[yoy_mk_df['분기_p'].isin(prev_periods)]
    
    mk_metrics = [('UGC_리뷰_참여율(%)', 'UGC 참여율'), ('사전예약율', '사전 예약률'), ('설문_응답률(%)', '설문 응답률')]
    
    # KPI 카드 (3열)
    kpi_cols = st.columns(3)
    for i, (col_name, label) in enumerate(mk_metrics):
        c_val = curr_df[col_name].mean()
        p_val = prev_df[col_name].mean()
        
        if pd.notna(p_val) and p_val > 0:
            rate = ((c_val - p_val) / p_val) * 100
            symbol = "▲" if rate > 0 else "▼" if rate < 0 else "-"
            color = "#2ECC71" if rate > 0 else "#E74C3C" if rate < 0 else "#7F8C8D"
            val_text = f"{symbol} {abs(rate):.1f}%"
        else:
            val_text = "-"
            color = "#999"
            
        with kpi_cols[i]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color:{color}">{val_text}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. 상권별 마케팅 지표 테이블
    st.markdown('<p class="section-title">상권별 마케팅 지표 비교</p>', unsafe_allow_html=True)
    area_mk = fdf.groupby('상권구분')[['마케팅비(원)', '관련_기사_노출_수(건)', 'UGC_리뷰_참여율(%)', '설문_응답률(%)', '사전예약율']].mean().reset_index()
    # Formatting
    area_mk['마케팅비(원)'] = area_mk['마케팅비(원)'].apply(lambda x: f"{fmt_money(x)}원")
    area_mk['관련_기사_노출_수(건)'] = area_mk['관련_기사_노출_수(건)'].apply(lambda x: f"{x:.1f}건")
    for c in ['UGC_리뷰_참여율(%)', '설문_응답률(%)', '사전예약율']:
        area_mk[c] = area_mk[c].apply(lambda x: f"{x:.1f}%")
    st.dataframe(area_mk, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. 효율성 분석 (마케팅비 vs 방문자, UGC vs 전환율, 방문객 vs 전환율)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<p class="section-title">마케팅비 구간별 평균 방문객 수</p>', unsafe_allow_html=True)
        fdf['마케팅비구간'] = pd.cut(fdf['마케팅비(원)'], bins=5)
        mk_vis_grp = fdf.groupby('마케팅비구간', observed=True)['방문객_수(명)'].mean()
        x_labels = [f"{fmt_money(i.left)}~{fmt_money(i.right)}" for i in mk_vis_grp.index]
        fig = go.Figure(go.Scatter(x=x_labels, y=mk_vis_grp.values, mode='lines+markers+text', line=dict(color='#2ECC71', width=3), text=[f"{v:,.0f}명" for v in mk_vis_grp.values], textposition='top center'))
        fig.update_layout(**L(350, margin=dict(t=80,b=40,l=40,r=40)), xaxis=dict(**ax(), title='마케팅비 구간 (만원)'), yaxis=dict(**ax(), title='평균 방문객 (명)', range=[0, mk_vis_grp.max()*1.25]))
        st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        st.markdown('<p class="section-title">UGC 참여율 구간별 평균 구매 전환율</p>', unsafe_allow_html=True)
        fdf['UGC구간'] = pd.cut(fdf['UGC_리뷰_참여율(%)'], bins=5)
        ugc_conv_grp = fdf.groupby('UGC구간', observed=True)['구매_전환율(%)'].mean()
        x_labels = [f"{i.left:.1f}~{i.right:.1f}%" for i in ugc_conv_grp.index]
        fig = go.Figure(go.Scatter(x=x_labels, y=ugc_conv_grp.values, mode='lines+markers+text', line=dict(color='#C8845A', width=3), 
            text=[f"{v:.1f}%" for v in ugc_conv_grp.values], textposition='top center', textfont=dict(size=12, weight='bold', color='#3D2B1F')))
        fig.update_layout(**L(350, margin=dict(t=80,b=40,l=40,r=40)), xaxis=dict(**ax(), title='UGC 참여율 구간'), yaxis=dict(**ax(), title='평균 전환율 (%)', range=[0, ugc_conv_grp.max()*1.25]))
        st.plotly_chart(fig, use_container_width=True)

    with c3:
        st.markdown('<p class="section-title">방문객 수 구간별 평균 구매 전환율</p>', unsafe_allow_html=True)
        fdf['방문객구간'] = pd.cut(fdf['방문객_수(명)'], bins=5)
        vis_conv_grp = fdf.groupby('방문객구간', observed=True)['구매_전환율(%)'].mean()
        x_labels = [f"{int(i.left):,}~{int(i.right):,}명" for i in vis_conv_grp.index]
        fig = go.Figure(go.Scatter(x=x_labels, y=vis_conv_grp.values, mode='lines+markers+text', line=dict(color='#1ABC9C', width=3), 
            text=[f"{v:.1f}%" for v in vis_conv_grp.values], textposition='top center', textfont=dict(size=12, weight='bold', color='#3D2B1F')))
        fig.update_layout(**L(350, margin=dict(t=80,b=40,l=40,r=40)), xaxis=dict(**ax(), title='방문객 수 구간'), yaxis=dict(**ax(), title='평균 전환율 (%)', range=[0, vis_conv_grp.max()*1.25]))
        
        # 클릭 이벤트 활성화
        selected_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", key="vis_conv_chart")

    # 선택된 구간 상세 목록 표시
    if selected_event and selected_event['selection']['points']:
        point_idx = selected_event['selection']['points'][0]['point_index']
        target_interval = vis_conv_grp.index[point_idx]
        
        st.markdown(f"<div style='padding:12px; background-color:#EFEBE9; border-radius:8px; margin-top:15px; font-weight:700; color:#4E342E; border-left:5px solid #1ABC9C;'>📋 방문객 {int(target_interval.left):,}~{int(target_interval.right):,}명 구간 팝업 목록 (전환율순)</div>", unsafe_allow_html=True)
        
        detail_df = fdf[fdf['방문객구간'] == target_interval][['상권구분','식품_세부분류','상세_주소','방문객_수(명)','구매_전환율(%)','총_매출액(원)']].copy()
        detail_df = detail_df.sort_values('구매_전환율(%)', ascending=False)
        
        detail_df['방문객_수(명)'] = detail_df['방문객_수(명)'].apply(lambda x: f"{x:,.0f}명")
        detail_df['구매_전환율(%)'] = detail_df['구매_전환율(%)'].apply(lambda x: f"{x:.1f}%")
        detail_df['총_매출액(원)'] = detail_df['총_매출액(원)'].apply(lambda x: f"{fmt_money(x)}원")
        
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

    # 5. 브랜드 신뢰도
    st.markdown('<p class="section-title">카테고리별 브랜드 신뢰도 순위</p>', unsafe_allow_html=True)
    cat_rel = fdf.groupby('식품_세부분류')['브랜드_신뢰도(5점)'].mean().sort_values(ascending=False).reset_index()
    cat_rel['브랜드_신뢰도(5점)'] = cat_rel['브랜드_신뢰도(5점)'].apply(lambda x: f"{x:.2f}점")
    cat_rel.columns = ['카테고리', '평균 신뢰도']
    st.dataframe(cat_rel, use_container_width=True, hide_index=True)
