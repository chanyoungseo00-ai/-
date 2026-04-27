import streamlit as st
import pandas as pd
import numpy as np
import io
import itertools

def assign_teams_and_orders(df, holes_per_field=8, players_per_team=6, match_type="개인전"):
    working_df = df.copy()
    total_players = len(working_df)
    team_size = players_per_team
    num_teams = (total_players + team_size - 1) // team_size
    
    females = working_df[working_df['성별'] == '여'].to_dict('records')
    males = working_df[working_df['성별'] == '남'].to_dict('records')
    
    teams = [[] for _ in range(num_teams)]
    
    # 1. 여자 2명 우선 배치
    for team in teams:
        assigned_regions = set()
        for _ in range(2):
            for i, p in enumerate(females):
                if p['지역'] not in assigned_regions:
                    team.append(p)
                    assigned_regions.add(p['지역'])
                    females.pop(i)
                    break
                    
    # 2. 남은 인원 배치
    remaining_players = females + males
    remaining_players.sort(key=lambda x: str(x['지역'])) 
    
    for team in teams:
        assigned_regions = {p['지역'] for p in team}
        while len(team) < team_size and remaining_players:
            for i, p in enumerate(remaining_players):
                if p['지역'] not in assigned_regions:
                    team.append(p)
                    assigned_regions.add(p['지역'])
                    remaining_players.pop(i)
                    break
            else:
                if remaining_players:
                    player = remaining_players.pop(0)
                    team.append(player)
                
    # 3. ★ 타순 완벽 분산 (순열 탐색 알고리즘) 및 구장 배정 ★
    region_batting_counts = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in working_df['지역'].unique()}
    final_roster = []
    
    for team_idx, team in enumerate(teams):
        team_name = f"{match_type} {team_idx + 1}조"
        fields = ['청', '백', '홍', '황']
        field = fields[team_idx % 4]
        hole = (team_idx // 4) % holes_per_field + 1
        start_hole = f"{field}구장 {hole}홀"
        
        available_orders = list(range(1, len(team) + 1))
        best_perm = None
        best_score = float('inf')
        
        # 현재 조 선수들의 지역 목록
        team_regions = [p['지역'] for p in team]
        
        # 해당 조 안에서 가능한 모든 타순 조합(경우의 수)을 시뮬레이션
        for perm in itertools.permutations(available_orders):
            score = 0
            for i, r in enumerate(team_regions):
                # 지역별 특정 타순 배정 횟수의 제곱을 더하여, 쏠림이 발생할수록 페널티를 무겁게 부여
                score += region_batting_counts[r].get(perm[i], 0) ** 2
            
            if score < best_score:
                best_score = score
                best_perm = perm
                if score == 0: # 완벽하게 안 쓴 타순들로만 배정 가능하면 즉시 확정
                    break
                    
        # 최적의 타순 조합을 실제 선수들에게 적용
        for i, player in enumerate(team):
            best_order = best_perm[i]
            if player['지역'] not in region_batting_counts:
                region_batting_counts[player['지역']] = {k: 0 for k in range(1, players_per_team + 1)}
            region_batting_counts[player['지역']][best_order] += 1
            
            final_roster.append({
                '팀': team_name, '출발홀': start_hole, '타순': best_order,
                '지역': player['지역'], '이름': player['이름'], '성별': player['성별']
            })
            
    final_df = pd.DataFrame(final_roster)
    if final_df.empty: return final_df
    
    # 4. 정렬 로직
    final_df['구장_순서'] = final_df['출발홀'].str[0].map({'청': 1, '백': 2, '홍': 3, '황': 4}).fillna(99)
    final_df['홀_번호'] = final_df['출발홀'].str.extract(r'(\d+)', expand=False).fillna(0).astype(int)
    final_df['조_번호'] = final_df['팀'].str.extract(r'(\d+)', expand=False).fillna(0).astype(int)
    
    final_df = final_df.sort_values(by=['구장_순서', '홀_번호', '조_번호', '타순']).reset_index(drop=True)
    final_df = final_df.drop(columns=['구장_순서', '홀_번호', '조_번호'])
    
    return final_df

# --- 웹사이트 화면 구성 ---
st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

st.title("⛳ 전국그라운드골프대회 대진표 자동 편성 시스템")
st.markdown("엑셀 명단을 업로드하면 조편성 규칙을 적용하여 대진표를 작성합니다. **(타순 완벽 분산 및 자동 오류 검증)**")

with st.sidebar:
    st.header("⚙️ 대회 규정 설정")
    match_type = st.radio("🏆 편성 부문 선택", ("개인전", "단체전"), index=0)
    holes = st.radio("출발홀 수 선택", (6, 7, 8), index=2)
    players = st.radio("1조당 최대 인원", (6, 7, 8), index=0)
    st.info("💡 엑셀 파일은 1행에 '지역', '이름', '성별' 열이 있어야 합니다.")

uploaded_file = st.file_uploader(f"[{match_type}] 참가선수명단 엑셀 파일(.xlsx)을 올려주세요.", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()
        
        if not {'지역', '이름', '성별'}.issubset(df.columns):
            st.error("❌ 엑셀 파일에 '지역', '이름', '성별' 열이 모두 포함되어 있는지 확인해 주세요.")
        else:
            df = df.dropna(subset=['지역', '이름', '성별']).copy()
            st.success(f"✅ 총 {len(df)}명의 선수 명단을 성공적으로 불러왔습니다!")
            
            if st.button(f"🚀 {match_type} 자동 조 편성 실행", type="primary"):
                with st.spinner("최적의 배치를 계산 중입니다... (수천 가지 타순 조합 분석 중)"):
                    
                    final_df = assign_teams_and_orders(df, holes_per_field=holes, players_per_team=players, match_type=match_type)
                    
                    st.subheader(f"🎉 {match_type} 대진표 편성 완료")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # ---------------------------------------------------------
                    # ★ 자동 오류 검증 리포트 (오류가 있을 때만 표 출력) ★
                    # ---------------------------------------------------------
                    st.markdown("---")
                    st.subheader("📊 자동 배치 검증 리포트")
                    
                    temp_df = final_df.copy()
                    validation_order = pd.crosstab(temp_df['지역'], temp_df['타순']) 
                    validation_team = pd.crosstab(temp_df['지역'], temp_df['팀'])   
                    
                    # [검증 1] 타순 누락 오류 색출
                    order_errors = []
                    short_players_regions = []
                    
                    for region in validation_order.index:
                        region_total = validation_order.loc[region].sum()
                        if region_total >= players:
                            # 인원이 충분한데 배정 횟수가 0인 타순이 있는지 검사
                            zeros = validation_order.columns[validation_order.loc[region] == 0].tolist()
                            if zeros:
                                order_errors.append({
                                    '지역': region, 
                                    '총 인원수': f"{region_total}명", 
                                    '누락된 타순(배정 0회)': ", ".join(map(lambda x: f"{x}번", zeros))
                                })
                        else:
                            short_players_regions.append(f"{region}({region_total}명)")
                            
                    st.markdown("**1. 지역별 타순 누락 검증 (쏠림 현상 확인)**")
                    if not order_errors:
                        st.success("✅ 오류 없음 (모든 지역이 1번부터 마지막 타순까지 완벽하게 분산 배치되었습니다.)")
                    else:
                        st.error("⚠️ 타순 배정 오류 발생 (일부 타순 쏠림 내역이 존재합니다.)")
                        st.dataframe(pd.DataFrame(order_errors), use_container_width=True, hide_index=True)
                        
                    if short_players_regions:
                        st.caption(f"💡 (참고) 전체 참가 인원 자체가 너무 적어 구조적으로 모든 타순 경험이 불가능한 지역: {', '.join(short_players_regions)}")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # [검증 2] 한 조 동일 지역 중복 오류 색출
                    team_errors = []
                    for team_col in validation_team.columns:
                        for region_idx in validation_team.index:
                            count = validation_team.loc[region_idx, team_col]
                            if count > 1:
                                team_errors.append({
                                    '문제 발생 조': team_col, 
                                    '중복된 지역': region_idx, 
                                    '배치된 인원수': f"{count}명"
                                })
                                
                    st.markdown("**2. 한 조에 동일 지역 중복 배치 검증**")
                    if not team_errors:
                        st.success("✅ 오류 없음 (모든 조에 동일 지역 선수가 겹치지 않고 1명씩 안전하게 배치되었습니다.)")
                    else:
                        st.error("⚠️ 동일 조 중복 배치 오류 (남은 인원 배정상 불가피한 중복 내역입니다.)")
                        st.dataframe(pd.DataFrame(team_errors), use_container_width=True, hide_index=True)

                    # ---------------------------------------------------------
                    # 엑셀 파일 다운로드 생성
                    # ---------------------------------------------------------
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        final_df.to_excel(writer, index=False, sheet_name=f'{match_type}_대진표')
                    processed_data = output.getvalue()
                    
                    st.markdown("---")
                    st.download_button(
                        label=f"📥 {match_type} 대진표 엑셀 다운로드",
                        data=processed_data,
                        file_name=f"제18회_대한체육회장배_{match_type}_대진표_최종결과.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    except Exception as e:
        st.error(f"오류가 발생했습니다. 원본 엑셀 파일을 다시 확인해 주세요: {e}")