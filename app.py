import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="그라운드골프 단체전 채점 시스템", layout="wide")

st.title("🤝 단체전 전용 자동 채점 시스템")
st.markdown("단일 엑셀 파일을 업로드하면 **[단체전 채점표]** 시트의 데이터를 바탕으로 팀별 합산 및 순위를 자동 계산합니다.")

st.info("""
**💡 단체전 순위 결정 규정**
1. **팀 총타수**가 가장 적은 팀
2. 동타일 경우, **팀 2타수** 합계가 많은 팀
3. 2타수도 같을 경우, **팀 홀인원** 합계가 많은 팀
""")

uploaded_file = st.file_uploader("단체전 채점표가 포함된 엑셀 파일을 업로드해주세요 (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # 엑셀 컬럼 설정 (왼쪽 1~14열 선수 개별 데이터)
    col_names = [
        '일시', '조', '타순', '소속', '성명', 
        '1일차_총타수', '1일차_2타수', '1일차_홀인원', 
        '2일차_총타수', '2일차_2타수', '2일차_홀인원', 
        '최종_총타수', '최종_2타수', '최종_홀인원'
    ]

    try:
        with st.spinner("단체전 순위를 집계 중입니다..."):
            # 1. 단체전 채점표 데이터 읽기
            df_raw = pd.read_excel(uploaded_file, sheet_name='단체전 채점표', skiprows=2, usecols=range(14), names=col_names)
            
            # 소속과 성명이 있는 데이터만 유효한 것으로 판단
            df_raw = df_raw.dropna(subset=['성명', '소속'])
            
            # 숫자 데이터 변환 및 결측치 처리
            score_cols = ['최종_총타수', '최종_2타수', '최종_홀인원']
            for col in score_cols:
                df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0).astype(int)
                
            # 합계 데이터 보정 (최종 칸이 비어있을 경우 1, 2일차 합산)
            df_raw['최종_총타수'] = np.where(df_raw['최종_총타수'] == 0, 
                                        pd.to_numeric(df_raw['1일차_총타수'], errors='coerce').fillna(0) + 
                                        pd.to_numeric(df_raw['2일차_총타수'], errors='coerce').fillna(0), 
                                        df_raw['최종_총타수'])
            df_raw['최종_2타수'] = np.where(df_raw['최종_총타수'] > 0, 
                                        pd.to_numeric(df_raw['1일차_2타수'], errors='coerce').fillna(0) + 
                                        pd.to_numeric(df_raw['2일차_2타수'], errors='coerce').fillna(0), 
                                        df_raw['최종_2타수'])
            df_raw['최종_홀인원'] = np.where(df_raw['최종_총타수'] > 0, 
                                        pd.to_numeric(df_raw['1일차_홀인원'], errors='coerce').fillna(0) + 
                                        pd.to_numeric(df_raw['2일차_홀인원'], errors='coerce').fillna(0), 
                                        df_raw['최종_홀인원'])

            # 기권 등을 제외하고 실제 점수가 있는 데이터만 사용
            df_raw = df_raw[df_raw['최종_총타수'] > 0].copy()

            # 2. 팀별 합산 (소속 기준 그룹화)
            df_team = df_raw.groupby('소속', as_index=False)[['최종_총타수', '최종_2타수', '최종_홀인원']].sum()

            # 3. 순위 산정 (총타수 소 ➔ 2타수 대 ➔ 홀인원 대)
            df_team = df_team.sort_values(by=['최종_총타수', '최종_2타수', '최종_홀인원'], ascending=[True, False, False]).reset_index(drop=True)
            
            # 동점자 처리 포함 순위 부여
            df_team['순위'] = df_team[['최종_총타수', '최종_2타수', '최종_홀인원']].apply(
                lambda x: (-x['최종_총타수'], x['최종_2타수'], x['최종_홀인원']), axis=1
            ).rank(method='min', ascending=False).astype(int)

            # 결과 데이터 정리
            team_ranking = df_team[['순위', '소속', '최종_총타수', '최종_2타수', '최종_홀인원']].copy()
            team_ranking.columns = ['순위', '소속', '총타수(합계)', '2타수(합계)', '홀인원(합계)']

            # 4. 단체전 시상 명단 (1~5위 및 장려상 5팀)
            award_titles = ['1위', '2위', '3위', '4위', '5위'] + ['장려상'] * 5
            awards_data = []
            for i, title in enumerate(award_titles):
                if i < len(team_ranking):
                    t = team_ranking.iloc[i]
                    awards_data.append([title, t['소속'], t['총타수(합계)'], t['2타수(합계)'], t['홀인원(합계)']])
                else:
                    awards_data.append([title, '', '', '', ''])
            team_awards = pd.DataFrame(awards_data, columns=['구분', '소속(팀명)', '총타수', '2타수', '홀인원'])

            # 화면 출력
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("🤝 단체전 시상팀 명단")
                st.dataframe(team_awards, use_container_width=True, hide_index=True)
            with col2:
                st.subheader("📊 단체전 전체 순위표")
                st.dataframe(team_ranking, use_container_width=True, hide_index=True)

            # 5. 엑셀 다운로드 생성
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                team_ranking.to_excel(writer, index=False, sheet_name='단체전 순위표')
                team_awards.to_excel(writer, index=False, sheet_name='단체전 시상(출력물)')
                
            processed_data = output.getvalue()
            
            st.success("🎉 단체전 채점이 완료되었습니다!")
            st.download_button(
                label="📥 단체전 결과 엑셀 다운로드",
                data=processed_data,
                file_name="제18회_대한체육회장배_단체전_결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    except Exception as e:
        st.error(f"오류가 발생했습니다. 시트 이름이 '단체전 채점표'인지 확인해주세요: {e}")