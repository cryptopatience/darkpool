import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
import time

warnings.filterwarnings('ignore')

# ==================== 페이지 설정 ====================
st.set_page_config(
    page_title="MAG 7+2 Dark Pool 분석",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)



# ==================== 로그인 시스템 ====================
def check_password():
    """비밀번호 확인 및 로그인 상태 관리"""
    if st.session_state.get('password_correct', False):
        return True
    
    st.title("🔒 MAG 7+2 퀀트 대시보드 로그인")
    st.markdown("### Magnificent Seven + Bitcoin Exposure 종합 분석")
    
    with st.form("credentials"):
        username = st.text_input("아이디 (ID)", key="username")
        password = st.text_input("비밀번호 (Password)", type="password", key="password")
        submit_btn = st.form_submit_button("로그인", type="primary")
    
    if submit_btn:
        if username in st.secrets["passwords"] and password == st.secrets["passwords"][username]:
            st.session_state['password_correct'] = True
            st.rerun()
        else:
            st.error("😕 아이디 또는 비밀번호가 올바르지 않습니다.")
    
    return False

if not check_password():
    st.stop()

# ==================== 로그아웃 버튼 ====================
with st.sidebar:
    st.success(f"✅ 로그인 성공!")
    if st.button("🚪 로그아웃"):
        st.session_state['password_correct'] = False
        st.rerun()


# ==================== 설정 및 종목 리스트 ====================
MAG7_STOCKS = {
    'AAPL': 'Apple', 'MSFT': 'Microsoft', 'GOOGL': 'Alphabet',
    'AMZN': 'Amazon', 'NVDA': 'NVIDIA', 'META': 'Meta',
    'TSLA': 'Tesla', 'COIN': 'Coinbase', 'IBIT': 'Bitcoin ETF'
}

# ==================== 데이터 수집 함수 ====================

@st.cache_data(ttl=3600)  # 1시간 캐시
def get_market_volume(ticker, days_back=65):
    """Yahoo Finance에서 전체 시장 거래량 가져오기"""
    try:
        stock = yf.Ticker(ticker)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back + 10)
        df = stock.history(start=start_date, end=end_date)
        return df['Volume']
    except:
        return None

@st.cache_data(ttl=3600)  # 1시간 캐시
def get_finra_data_full(ticker, days_back=60):
    """
    FINRA 데이터 수집 및 핵심 지표 3가지 계산 (60일 history 포함)
    """
    try:
        today = datetime.now()
        data_list = []

        # Yahoo 전체 거래량 (분모용)
        market_volumes = get_market_volume(ticker, days_back)
        if market_volumes is None or market_volumes.empty: 
            return None

        # FINRA 데이터 루프 (최근 N일)
        for days in range(days_back + 5):  # 휴일 고려 여유분
            check_date = today - timedelta(days=days)
            if check_date.weekday() >= 5: 
                continue

            date_str = check_date.strftime('%Y%m%d')
            date_key = check_date.strftime('%Y-%m-%d')

            url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date_str}.txt"

            try:
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    df = pd.read_csv(StringIO(response.text), sep='|')
                    if 'Symbol' in df.columns: 
                        df.rename(columns={'Symbol': 'symbol'}, inplace=True)
                    if 'ShortVolume' in df.columns: 
                        df.rename(columns={'ShortVolume': 'shortVolume'}, inplace=True)
                    if 'TotalVolume' in df.columns: 
                        df.rename(columns={'TotalVolume': 'totalVolume'}, inplace=True)

                    row = df[df['symbol'] == ticker.upper()]

                    if not row.empty:
                        finra_total = int(row.iloc[0]['totalVolume'])
                        finra_short = int(row.iloc[0]['shortVolume'])

                        # Yahoo Volume 매칭
                        market_vol = 0
                        if date_key in market_volumes.index:
                            market_vol = market_volumes.loc[date_key]
                        else:
                            for idx in market_volumes.index:
                                if idx.strftime('%Y-%m-%d') == date_key:
                                    market_vol = market_volumes[idx]
                                    break

                        if market_vol > 0:
                            # 지표 계산
                            dp_ratio = (finra_total / market_vol) * 100
                            dp_short_ratio = (finra_short / finra_total) * 100
                            total_short_ratio = (finra_short / market_vol) * 100

                            # 보정 (데이터 오차)
                            if dp_ratio > 100: 
                                dp_ratio = 100

                            data_list.append({
                                'date': date_key,
                                'dp_ratio': round(dp_ratio, 2),
                                'dp_short_ratio': round(dp_short_ratio, 2),
                                'total_short_ratio': round(total_short_ratio, 2),
                                'market_vol': market_vol
                            })

                if len(data_list) >= days_back: 
                    break
            except:
                continue

        if not data_list: 
            return None

        df_hist = pd.DataFrame(data_list).sort_values('date')

        # 10일 평균 및 변화율 계산
        df_hist['dp_short_ratio_10d_avg'] = df_hist['dp_short_ratio'].rolling(window=10, min_periods=1).mean()
        latest = df_hist.iloc[-1]

        recent_10d_avg = df_hist.iloc[-10:]['dp_short_ratio'].mean()
        dp_short_change = latest['dp_short_ratio'] - recent_10d_avg

        return {
            'ticker': ticker,
            'name': MAG7_STOCKS[ticker],
            'latest_date': latest['date'],
            'dp_ratio': latest['dp_ratio'],
            'dp_short_ratio': latest['dp_short_ratio'],
            'total_short_ratio': latest['total_short_ratio'],
            'dp_short_10d_avg': latest['dp_short_ratio_10d_avg'],
            'dp_short_change_pct': dp_short_change,
            'history': df_hist
        }

    except Exception as e:
        return None

def create_signal(row):
    """시그널 생성 함수"""
    if row['dp_short_change_pct'] < -5:
        return '🟢 급락 (청산 신호)'
    if row['dp_ratio'] > 50 and row['dp_short_ratio'] > 55:
        return '🔴 기관 강한 약세 포지션'
    if row['dp_ratio'] > 50 and row['dp_short_ratio'] < 45:
        return '💚 기관 매집 가능성'
    if row['dp_vs_total'] > 5:
        return '⚠️ DP에 공매도 집중'
    if row['dp_vs_total'] < -5:
        return '✅ 거래소에 공매도 집중'
    return '⚪ 관망/정상'

# ==================== 메인 앱 ====================

def main():
    # 타이틀
    st.title("🚀 MAG 7+2: Dark Pool & Short Interest 심층 분석")
    st.markdown("---")
    
    # 사이드바
    with st.sidebar:
        st.header("⚙️ 설정")
        days_back = st.slider("분석 기간 (일)", 30, 90, 60)
        auto_refresh = st.checkbox("자동 새로고침 (1시간)", value=False)
        
        st.markdown("---")
        st.markdown("### 📚 신호 해석 가이드")
        st.markdown("""
        - **🔴 기관 강한 약세**: DP Ratio >50% & DP Short >55%
        - **💚 기관 매집 가능성**: DP Ratio >50% & DP Short <45%
        - **🟢 급락 (청산)**: 10일 대비 -5%p 이상
        - **⚠️ DP 공매도 집중**: DP Short > Total Short +5%p
        - **✅ 거래소 공매도**: Total Short > DP Short +5%p
        """)
    
    # 데이터 로딩
    if st.button("🔄 데이터 새로고침") or auto_refresh:
        st.cache_data.clear()
    
    with st.spinner("데이터 수집 중..."):
        analysis_results = []
        progress_bar = st.progress(0)
        
        for idx, ticker in enumerate(MAG7_STOCKS.keys()):
            res = get_finra_data_full(ticker, days_back=days_back)
            if res:
                analysis_results.append(res)
            progress_bar.progress((idx + 1) / len(MAG7_STOCKS))
        
        progress_bar.empty()
    
    if not analysis_results:
        st.error("데이터를 가져올 수 없습니다. 잠시 후 다시 시도해주세요.")
        return
    
    # 메인 데이터프레임 생성
    df_main = pd.DataFrame([{k:v for k,v in r.items() if k != 'history'} for r in analysis_results])
    df_main['dp_vs_total'] = (df_main['dp_short_ratio'] - df_main['total_short_ratio']).round(2)
    df_main['Signal'] = df_main.apply(create_signal, axis=1)
    df_main = df_main.sort_values('dp_ratio', ascending=False)
    
    # ==================== 요약 통계 ====================
    st.header("📊 전체 시장 개요")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_dp = df_main['dp_ratio'].mean()
        st.metric("평균 Dark Pool Ratio", f"{avg_dp:.1f}%")
    
    with col2:
        avg_short = df_main['dp_short_ratio'].mean()
        st.metric("평균 DP Short Ratio", f"{avg_short:.1f}%")
    
    with col3:
        bullish_count = len(df_main[df_main['Signal'].str.contains('매집|청산')])
        st.metric("강세 신호 종목", f"{bullish_count}개")
    
    with col4:
        bearish_count = len(df_main[df_main['Signal'].str.contains('약세|집중')])
        st.metric("약세 신호 종목", f"{bearish_count}개")
    
    st.markdown("---")
    
    # ==================== 통합 테이블 ====================
    st.header("📋 통합 상세 비교 테이블")
    
    df_display = df_main.copy()
    df_display = df_display.rename(columns={
        'ticker': '티커',
        'name': '종목명',
        'dp_ratio': 'DP Ratio (%)',
        'dp_short_ratio': 'DP Short (%)',
        'dp_short_10d_avg': 'DP 10일 평균',
        'dp_short_change_pct': '1일 vs 10일',
        'total_short_ratio': 'Total Short (%)',
        'dp_vs_total': 'DP vs Total',
        'Signal': '신호'
    })
    
    # 컬럼 포맷팅
    display_cols = ['티커', '종목명', 'DP Ratio (%)', 'DP Short (%)', 
                    'DP 10일 평균', '1일 vs 10일', 'Total Short (%)', 
                    'DP vs Total', '신호']
    
    # 스타일링
    def highlight_signal(row):
        if '🔴' in str(row['신호']):
            return ['background-color: #ffcccc'] * len(row)
        elif '💚' in str(row['신호']) or '🟢' in str(row['신호']):
            return ['background-color: #ccffcc'] * len(row)
        elif '⚠️' in str(row['신호']):
            return ['background-color: #fff3cd'] * len(row)
        return [''] * len(row)
    
    st.dataframe(
        df_display[display_cols].style.apply(highlight_signal, axis=1).format({
            'DP Ratio (%)': '{:.2f}%',
            'DP Short (%)': '{:.2f}%',
            'DP 10일 평균': '{:.2f}%',
            '1일 vs 10일': '{:+.2f}%p',
            'Total Short (%)': '{:.2f}%',
            'DP vs Total': '{:+.2f}%p'
        }),
        use_container_width=True,
        height=400
    )
    
    st.markdown("---")
    
    # ==================== 차트 섹션 ====================
    st.header("📈 시각화 분석")
    
    # 탭으로 구성
    tab1, tab2, tab3, tab4 = st.tabs([
        "Dark Pool Ratio", 
        "Short 비교", 
        "4분면 분석", 
        "시계열 분석"
    ])
    
    # Tab 1: Dark Pool Ratio
    with tab1:
        st.subheader("Dark Pool Ratio (기관의 장외 거래 장악력)")
        
        colors_dp = ['green' if x < 40 else 'orange' if x < 50 else 'red' 
                     for x in df_main['dp_ratio']]
        
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=df_main['ticker'], 
            y=df_main['dp_ratio'],
            text=[f"{x:.1f}%" for x in df_main['dp_ratio']], 
            textposition='auto',
            marker_color=colors_dp, 
            name='Dark Pool %'
        ))
        
        fig1.add_hline(y=50, line_dash="dash", line_color="red", 
                      annotation_text="기관 과열 (50%)")
        fig1.add_hline(y=40, line_dash="dash", line_color="green", 
                      annotation_text="정상 범위 (40%)")
        
        fig1.update_layout(
            title='Dark Pool Ratio (FINRA Vol / Total Vol)', 
            height=500, 
            template='plotly_white',
            xaxis_title='종목',
            yaxis_title='Dark Pool Ratio (%)'
        )
        
        st.plotly_chart(fig1, use_container_width=True)
    
    # Tab 2: Short 비교
    with tab2:
        st.subheader("은밀한 공매도(장외) vs 공개된 공매도 비교")
        
        fig2 = go.Figure()
        
        fig2.add_trace(go.Bar(
            x=df_main['ticker'], 
            y=df_main['dp_short_ratio'],
            name='Dark Pool Short % (장외 내부)',
            marker_color='darkblue'
        ))
        
        fig2.add_trace(go.Bar(
            x=df_main['ticker'], 
            y=df_main['total_short_ratio'],
            name='Total Short % (전체 시장)',
            marker_color='gray'
        ))
        
        fig2.update_layout(
            title='Dark Pool Short Ratio vs Total Market Short Ratio',
            barmode='group', 
            height=500, 
            template='plotly_white',
            xaxis_title='종목',
            yaxis_title='Short Ratio (%)'
        )
        
        st.plotly_chart(fig2, use_container_width=True)
    
    # Tab 3: 4분면 분석
    with tab3:
        st.subheader("Market Sentiment Map (4분면 분석)")
        
        # 4분면 해석 가이드
        with st.expander("📚 4분면 해석 가이드 (클릭하여 보기)", expanded=False):
            st.markdown("""
            ### 📈 Dark Pool Sentiment Map 분석
            
            이 4분면 차트는 **Dark Pool Ratio (DP Ratio)**와 **Dark Pool Short Ratio (DP Short Ratio)** 
            두 가지 주요 지표를 사용하여 기관 투자자들의 현재 포지션과 심리를 시각화합니다.
            
            #### 📊 차트 축 및 분면 해석
            
            | 분면 | X축 (DP Ratio) | Y축 (DP Short Ratio) | 시장 심리 (해석) |
            |:---|:---|:---|:---|
            | **우상단 (Distribution)** | **높음** (기관 개입 강함) | **높음** (공매도 심리 강함) | **기관의 매도/공매도 집중** (가장 부정적 신호) |
            | **좌상단** | **낮음** (기관 개입 약함) | **높음** (공매도 심리 강함) | **개인 주도 공매도 또는 관망 속 공매도** |
            | **우하단 (Accumulation)** | **높음** (기관 개입 강함) | **낮음** (공매도 심리 약함) | **기관의 매집/매수 집중** (가장 긍정적 신호) |
            | **좌하단 (개인/관망)** | **낮음** (기관 개입 약함) | **낮음** (공매도 심리 약함) | **기관의 관심 부족** (개인 주도 거래) |
            
            #### 💡 투자 시사점
            
            - **우하단 (매집 영역)**: 기관들이 장외에서 적극적으로 매수 포지션 구축 → **긍정적 신호**
            - **우상단 (분배 영역)**: 기관들이 장외에서 강력한 공매도 포지션 구축 → **부정적 신호**
            - **좌하단 (관망 영역)**: 기관 활동이 과열되지 않고 안정적인 범위 → **중립적 신호**
            
            ⚠️ **주의**: 이 분석은 장외(Dark Pool) 거래에 국한된 기관의 움직임만을 나타내므로, 
            최종 투자 결정은 전체 거래소의 가격, 기술적 지표, 뉴스 등을 종합하여 판단해야 합니다.
            """)
        
        # 분면별 설명을 위한 호버 텍스트 생성
        def get_quadrant_info(dp_ratio, dp_short_ratio):
            """각 분면에 대한 상세 설명 반환"""
            if dp_ratio >= 45 and dp_short_ratio >= 50:
                return "🔴 Distribution (분배): 기관의 매도/공매도 집중 - 부정적 신호"
            elif dp_ratio >= 45 and dp_short_ratio < 50:
                return "💚 Accumulation (매집): 기관의 매수 집중 - 긍정적 신호"
            elif dp_ratio < 45 and dp_short_ratio >= 50:
                return "⚠️ 개인 주도 공매도: 기관 개입 약함, 공매도 심리 강함"
            else:
                return "⚪ 개인/관망: 기관 개입 약함, 정상 범위"
        
        # 각 종목에 대한 호버 텍스트 생성
        hover_texts = []
        for idx, row in df_main.iterrows():
            quadrant = get_quadrant_info(row['dp_ratio'], row['dp_short_ratio'])
            hover_text = (
                f"<b>{row['ticker']} ({row['name']})</b><br>"
                f"DP Ratio: {row['dp_ratio']:.2f}%<br>"
                f"DP Short Ratio: {row['dp_short_ratio']:.2f}%<br>"
                f"<br>{quadrant}"
            )
            hover_texts.append(hover_text)
        
        fig3 = go.Figure()
        
        fig3.add_trace(go.Scatter(
            x=df_main['dp_ratio'],
            y=df_main['dp_short_ratio'],
            mode='markers+text',
            text=df_main['ticker'],
            textposition='top center',
            marker=dict(
                size=df_main['dp_ratio'] * 0.8,
                color=df_main['dp_short_ratio'],
                colorscale='RdYlGn_r',
                showscale=True,
                colorbar=dict(title="Short Ratio")
            ),
            hovertext=hover_texts,
            hoverinfo='text'
        ))
        
        # 분면 구분선
        fig3.add_vline(x=45, line_dash="dot", line_color="gray", line_width=2)
        fig3.add_hline(y=50, line_dash="dot", line_color="gray", line_width=2)
        
        # 분면 라벨 (배경색 추가)
        fig3.add_annotation(
            x=55, y=70, 
            text="<b>매도/공매도</b><br>(Distribution)<br>🔴 부정적", 
            showarrow=False, 
            font=dict(color="darkred", size=12),
            bgcolor="rgba(255,200,200,0.3)",
            bordercolor="red",
            borderwidth=1,
            borderpad=4
        )
        fig3.add_annotation(
            x=55, y=30, 
            text="<b>매집</b><br>(Accumulation)<br>💚 긍정적", 
            showarrow=False, 
            font=dict(color="darkgreen", size=12),
            bgcolor="rgba(200,255,200,0.3)",
            bordercolor="green",
            borderwidth=1,
            borderpad=4
        )
        fig3.add_annotation(
            x=35, y=30, 
            text="<b>개인/관망</b><br>⚪ 중립", 
            showarrow=False, 
            font=dict(color="gray", size=12),
            bgcolor="rgba(220,220,220,0.3)",
            bordercolor="gray",
            borderwidth=1,
            borderpad=4
        )
        fig3.add_annotation(
            x=35, y=70, 
            text="<b>개인 공매도</b><br>⚠️ 주의", 
            showarrow=False, 
            font=dict(color="orange", size=12),
            bgcolor="rgba(255,240,200,0.3)",
            bordercolor="orange",
            borderwidth=1,
            borderpad=4
        )
        
        fig3.update_layout(
            title='X축: 기관 관심도 (DP Ratio) vs Y축: 공매도 심리 (DP Short Ratio)',
            xaxis_title='Dark Pool Ratio (%) - 높을수록 기관 개입 강함',
            yaxis_title='Dark Pool Short Ratio (%) - 높을수록 하락 베팅',
            height=600, 
            template='plotly_white',
            hovermode='closest'
        )
        
        st.plotly_chart(fig3, use_container_width=True)
        
        # 현재 포지션 요약
        st.markdown("### 📊 현재 포지션 요약")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            accumulation = df_main[(df_main['dp_ratio'] >= 45) & (df_main['dp_short_ratio'] < 50)]
            st.success(f"**💚 매집 (Accumulation)**\n\n{', '.join(accumulation['ticker'].tolist()) if not accumulation.empty else '없음'}")
        
        with col2:
            distribution = df_main[(df_main['dp_ratio'] >= 45) & (df_main['dp_short_ratio'] >= 50)]
            st.error(f"**🔴 분배 (Distribution)**\n\n{', '.join(distribution['ticker'].tolist()) if not distribution.empty else '없음'}")
        
        with col3:
            neutral = df_main[df_main['dp_ratio'] < 45]
            st.info(f"**⚪ 개인/관망**\n\n{', '.join(neutral['ticker'].tolist()) if not neutral.empty else '없음'}")
    
    # Tab 4: 시계열 분석
    with tab4:
        st.subheader("전체 종목 상세 시계열 분석")
        
        selected_ticker = st.selectbox(
            "종목 선택",
            options=[f"{r['ticker']} ({r['name']})" for r in analysis_results],
            index=0
        )
        
        ticker_code = selected_ticker.split()[0]
        item = next(r for r in analysis_results if r['ticker'] == ticker_code)
        
        df_hist = item['history']
        
        fig_ts = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True,
            subplot_titles=(
                f"{ticker_code} - Dark Pool Ratio Trend (기관 개입 강도)",
                f"{ticker_code} - Dark Pool Short Ratio Trend (공매도 심리)"
            ),
            vertical_spacing=0.15
        )
        
        # Dark Pool Ratio
        fig_ts.add_trace(go.Scatter(
            x=df_hist['date'], 
            y=df_hist['dp_ratio'],
            mode='lines+markers', 
            name='DP Ratio', 
            line=dict(color='blue', width=2),
            showlegend=True
        ), row=1, col=1)
        
        fig_ts.add_hline(y=50, line_dash="dot", line_color="red", 
                        annotation_text="과열 (50%)", row=1, col=1)
        fig_ts.add_hline(y=40, line_dash="dot", line_color="green", 
                        annotation_text="안정 (40%)", row=1, col=1)
        
        # Dark Pool Short Ratio
        fig_ts.add_trace(go.Scatter(
            x=df_hist['date'], 
            y=df_hist['dp_short_ratio'],
            mode='lines+markers', 
            name='DP Short Ratio', 
            line=dict(color='orange', width=2),
            showlegend=True
        ), row=2, col=1)
        
        # 10일 평균선
        fig_ts.add_trace(go.Scatter(
            x=df_hist['date'], 
            y=df_hist['dp_short_ratio_10d_avg'],
            mode='lines', 
            name='10일 평균', 
            line=dict(color='gray', dash='dot'),
            showlegend=True
        ), row=2, col=1)
        
        fig_ts.add_hline(y=50, line_dash="dot", line_color="gray", 
                        annotation_text="매수/매도 분기점", row=2, col=1)
        
        fig_ts.update_layout(
            height=700, 
            title_text=f"📊 {ticker_code} ({item['name']}) {days_back}일 상세 타임라인", 
            template='plotly_white'
        )
        
        fig_ts.update_xaxes(title_text="날짜", row=2, col=1)
        fig_ts.update_yaxes(title_text="DP Ratio (%)", row=1, col=1)
        fig_ts.update_yaxes(title_text="DP Short Ratio (%)", row=2, col=1)
        
        st.plotly_chart(fig_ts, use_container_width=True)
        
        # 상세 데이터 테이블
        with st.expander("📊 상세 데이터 보기"):
            st.dataframe(
                df_hist[['date', 'dp_ratio', 'dp_short_ratio', 
                        'dp_short_ratio_10d_avg', 'total_short_ratio']].sort_values('date', ascending=False),
                use_container_width=True
            )
    
    # 푸터
    st.markdown("---")
    st.markdown(f"**최종 업데이트**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption("데이터 출처: Yahoo Finance & FINRA | 1시간마다 캐시 갱신")

if __name__ == "__main__":
    main()
