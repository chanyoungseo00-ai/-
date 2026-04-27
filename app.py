import streamlit as st
import pandas as pd
import numpy as np
import io
import random
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
                    
    # 2-5. [신규 로직] 강제 배치로 인한 동일 지역 중복 발생 시, 다른 조와 맞교환(Swap)하여 완벽 차단
    max_swaps = 100
    swaps = 0
    while swaps < max_swaps:
        violation_found = False
        for team in teams:
            regions_in_team = [p['지역'] for p in team]
            for p in team:
                if regions_in_team.count(p['지역']) > 1:
                    violation_found = True
                    swap_done = False
                    for other_team in teams:
                        if other_team is team: continue
                        if p['지역'] not in [x['지역'] for x in other_team]:
                            for other_p in other_team:
                                team_regions_without_p = [x['지역'] for x in team if x is not p]
                                if other_p['지역'] not in team_regions_without_p:
                                    team.remove(p)
                                    other_team.remove(other_p)
                                    team.append(other_p)
                                    other_team.append(p)
                                    swap_done = True
                                    swaps += 1
                                    break
                        if swap_done: break
                    if swap_done: break
            if violation_found: break
        if not violation_found:
            break
                
    # 3. ★ 타순 완벽 분산 알고리즘 (가중치 채점 방식) ★
    regions = working_df['지역'].unique()
    region_batting_counts = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in regions}
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
        
        all_perms = list(itertools.permutations(available_orders))
        random.shuffle(all_perms)
        
        team_regions = [p['지역'] for p in team]
        
        # 가능한 모든 타순 조합(수천 가지)을 시뮬레이션하여 최적의 분산 도출
        for perm in all_perms:
            score = 0
            for i, r in enumerate(team_regions):
                count = region_batting_counts[r].get(perm[i], 0)
                if count == 0:
                    # 해당 타순에 처음 배치되는 경우: 압도적인 혜택(마이너스 점수) 부여 -> 우선 배치
                    score -= 10000 
                else:
                    # 이미 배치된 적이 있는 경우: 남은 인원 균등 분산을 위해 누적 횟수만큼 페널티 부여
                    score += count 
            
            if score < best_score:
                best_score = score
                best_perm = perm
                
            # 가장 완벽한 조합(모두가 새로운 타순)을 찾으면 조기 종료
            if score == -10000 * len(team):
                break
                
        # 최적의 타순을 확정하고 카운트 증가
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
                with st.spinner("최적의 배치를 계산 중입니다... (교차 검증 및 무결성 확인 중)"):
                    
                    final_df = assign_teams_and_orders(df, holes_per_field=holes, players_per_team=players, match_type=match_type)
                    
                    st.subheader(f"🎉 {match_type} 대진표 편성 완료")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # ---------------------------------------------------------
                    # ★ 깔끔하게 개편된 자동 오류 검증 리포트 ★
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
                        zeros = validation_order.columns[validation_order.loc[region] == 0].tolist()
                        
                        if region_total >= players:
                            if zeros: # 인원이 충분한데 타순 배정을 0회 받은 곳이 있다면 오류
                                order_errors.append({
                                    '지역': region, 
                                    '총 인원수': f"{region_total}명", 
                                    '누락된 타순(배정 0회)': ", ".join(map(lambda x: f"{x}번", zeros))
                                })
                        else:
                            # 인원이 적은 경우, 인원수만큼 타순을 다양하게 받았는지 검사
                            used_orders = (validation_order.loc[region] > 0).sum()
                            if used_orders < region_total:
                                duplicates = validation_order.columns[validation_order.loc[region] > 1].tolist()
                                order_errors.append({
                                    '지역': region, 
                                    '총 인원수': f"{region_total}명", 
                                    '중복 배정된 타순': ", ".join(map(lambda x: f"{x}번", duplicates)),
                                    '사유': f"인원이 적음에도 불구하고 동일 타순 중복 배정됨"
                                })
                            else:
                                short_players_regions.append(f"{region}({region_total}명)")
                                
                    st.markdown("**1. 지역별 모든 타순(1번~마지막) 최소 1회 배정 검증**")
                    if not order_errors:
                        st.success("✅ 오류 없음 (모든 지역이 규정에 맞게 모든 타순에 우선적으로 완벽히 배치되었습니다.)")
                    else:
                        st.error("⚠️ 타순 배정 오류 발생 (아래 지역의 타순 쏠림 내역을 확인하세요.)")
                        st.dataframe(pd.DataFrame(order_errors), use_container_width=True, hide_index=True)
                        
                    if short_players_regions:
                        st.caption(f"💡 (정상) 지역 총 인원이 1조 정원({players}명)보다 적어 모든 타순 배정이 불가능한 지역: {', '.join(short_players_regions)}")
                    
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
                                
                    st.markdown("**2. 한 조에 동일 지역 선수 중복 배치 검증**")
                    if not team_errors:
                        st.success("✅ 오류 없음 (모든 조에 동일 지역 선수가 겹치지 않고 1명씩 안전하게 배치되었습니다.)")
                    else:
                        st.error("⚠️ 동일 조 중복 배치 오류 (남은 인원 구조상 불가피하게 겹친 내역입니다.)")
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