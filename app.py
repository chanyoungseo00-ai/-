import streamlit as st
import pandas as pd
import numpy as np
import io
import random
import itertools

st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

def assign_teams_and_orders(df, holes_per_field=8, players_per_team=6, match_type="개인전"):
    working_df = df.copy()
    total_players = len(working_df)
    team_size = players_per_team
    num_teams = (total_players + team_size - 1) // team_size
    
    if num_teams == 0:
        return pd.DataFrame(), 0

    teams = [[] for _ in range(num_teams)]

    # ==========================================
    # [1] 조 편성 로직 (지역 중복 완벽 방지)
    # ==========================================
    if match_type == "개인전":
        players = working_df.to_dict('records')
        # 인원수가 많은 지역부터 먼저 배치하여 빈자리 선점
        region_counts = working_df['지역'].value_counts().to_dict()
        players.sort(key=lambda x: (region_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for p in players:
            # 현재 가장 안 겹치는 조 ➔ 인원이 가장 적은 조 순으로 탐색
            best_team = min(
                teams, 
                key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t))
            )
            best_team.append(p)
            
    else: # 단체전 (여성 우선 배치 후 남은 인원 분산)
        females = working_df[working_df['성별'] == '여'].to_dict('records')
        males = working_df[working_df['성별'] == '남'].to_dict('records')
        
        f_counts = pd.Series([p['지역'] for p in females]).value_counts().to_dict()
        females.sort(key=lambda x: (f_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        # 각 조에 여자 선수 2명씩, 지역 안 겹치게 우선 배정
        for team in teams:
            for _ in range(2):
                if not females: 
                    break
                min_overlap = min(sum(1 for x in team if x['지역'] == f['지역']) for f in females)
                for i, f in enumerate(females):
                    if sum(1 for x in team if x['지역'] == f['지역']) == min_overlap:
                        team.append(females.pop(i))
                        break
                        
        # 남은 인원 배치
        remaining = females + males
        rem_counts = pd.Series([p['지역'] for p in remaining]).value_counts().to_dict()
        remaining.sort(key=lambda x: (rem_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for p in remaining:
            best_team = min(
                teams, 
                key=lambda t: (sum(1 for x in t if x['지역'] == p['지역']), len(t))
            )
            best_team.append(p)

    # ==========================================
    # [2] 타순 편성 로직 (타순 쏠림 완벽 평탄화)
    # ==========================================
    region_order_count = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in working_df['지역'].unique()}
    
    # 1차 배정: 각 조 안에서 경우의 수를 돌려 최적의 타순 조합 찾기
    for team in teams:
        available_orders = list(range(1, players_per_team + 1))
        best_perm = None
        best_score = float('inf')
        
        # 6명 이하일 경우 모든 경우의 수 확인, 그 이상은 무작위 2000번 섞어서 확인
        if len(available_orders) <= 6:
            perms = list(itertools.permutations(available_orders, len(team)))
        else:
            perms = [random.sample(available_orders, len(team)) for _ in range(2000)]
            
        for perm in perms:
            score = 0
            for i, p in enumerate(team):
                count = region_order_count[p['지역']].get(perm[i], 0)
                score += count ** 2 # 쏠림에 강력한 페널티 부여
            if score < best_score:
                best_score = score
                best_perm = perm
                if score == 0: 
                    break # 완벽한 조합이면 즉시 확정
                
        for i, p in enumerate(team):
            p['타순'] = best_perm[i]
            region_order_count[p['지역']][best_perm[i]] += 1

    # 2차 배정: 전체 조를 돌며 미세한 쏠림까지 서로 맞교환하여 완벽 평탄화
    for _ in range(3000):
        usage = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in working_df['지역'].unique()}
        for team in teams:
            for p in team: 
                usage[p['지역']][p['타순']] += 1
                
        worst_region, worst_skew, worst_over, worst_under = None, -1, -1, -1
        for r, u in usage.items():
            skew = max(u.values()) - min(u.values())
            if skew > worst_skew:
                worst_skew = skew
                worst_region = r
                worst_over = max(u, key=u.get)
                worst_under = min(u, key=u.get)
                
        if worst_skew <= 1: 
            break # 모든 지역의 타순 오차가 1 이하라면 완벽한 상태
        
        teams_with_over = [t for t in teams if any(p['지역'] == worst_region and p['타순'] == worst_over for p in t)]
        swapped = False
        random.shuffle(teams_with_over)
        
        for team in teams_with_over:
            p1 = next((p for p in team if p['지역'] == worst_region and p['타순'] == worst_over), None)
            p2 = next((p for p in team if p['타순'] == worst_under), None)
            if p1 and p2:
                r2 = p2['지역']
                if usage[r2][worst_over] <= usage[r2][worst_under]: # 남에게 피해를 안 줄 때만 교환
                    p1['타순'], p2['타순'] = p2['타순'], p1['타순']
                    swapped = True
                    break
            elif p1 and not p2:
                p1['타순'] = worst_under
                swapped = True
                break
                
        if not swapped and teams_with_over:
            team = teams_with_over[0]
            p1 = next((p for p in team if p['지역'] == worst_region and p['타순'] == worst_over), None)
            p2 = next((p for p in team if p['타순'] == worst_under), None)
            if p1 and p2: 
                p1['타순'], p2['타순'] = p2['타순'], p1['타순']
            elif p1: 
                p1['타순'] = worst_under

    # ==========================================
    # [3] 구장별 정렬 로직 (청 ➔ 백 ➔ 홍 ➔ 황 순서)
    # ==========================================
    final_roster = []
    fields = ['청', '백', '홍', '황']
    
    for team_idx, team in enumerate(teams):
        team_id = team_idx + 1
        field_val = team_idx % 4
        field = fields[field_val]
        hole = (team_idx // 4) % holes_per_field + 1
        round_id = (team_idx // (4 * holes_per_field)) + 1 
        start_hole = f"{field}구장 {hole}홀"
        
        set_name = f"{round_id}그룹 {field}구장" if len(teams) > holes_per_field * 4 else f"{field}구장"
            
        for p in team:
            final_roster.append({
                '진행 그룹': set_name, 
                '팀': f"{match_type} {team_id}조", 
                '출발홀': start_hole, 
                '타순': p['타순'], 
                '지역': p['지역'], 
                '이름': p['이름'], 
                '성별': p['성별'],
                '_round_val': round_id, 
                '_field_val': field_val, 
                '_hole_val': hole
            })
            
    final_df = pd.DataFrame(final_roster)
    final_df = final_df.sort_values(
        by=['_round_val', '_field_val', '_hole_val', '타순']
    ).reset_index(drop=True)
    
    final_df = final_df.drop(columns=['_round_val', '_field_val', '_hole_val'])
    
    return final_df, num_teams

# --- 웹사이트 화면 구성 ---
st.title("⛳ 전국그라운드골프대회 대진표 자동 편성 시스템")

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
                with st.spinner("구장별 최적의 배치를 계산 중입니다..."):
                    
                    final_df, total_teams = assign_teams_and_orders(
                        df, holes_per_field=holes, players_per_team=players, match_type=match_type
                    )
                    
                    st.subheader(f"🎉 {match_type} 대진표 편성 완료 (총 {total_teams}개 조)")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # --- 검증 리포트 영역 ---
                    st.markdown("---")
                    st.subheader("📊 무결성 검증 리포트")
                    
                    # [1] 지역 중복 검증
                    validation_team = pd.crosstab(final_df['지역'], final_df['팀'])   
                    team_errors = []
                    unavoidable_errors = False
                    
                    for region_idx in validation_team.index:
                        region_total_players = df[df['지역'] == region_idx].shape[0]
                        # 지역 인원이 총 조 개수보다 많은 경우 불가피한 중복으로 판단
                        is_unavoidable = region_total_players > total_teams 
                        
                        for team_col in validation_team.columns:
                            count = validation_team.loc[region_idx, team_col]
                            if count > 1: