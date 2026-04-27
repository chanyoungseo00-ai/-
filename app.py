import streamlit as st
import pandas as pd
import numpy as np
import io
import random

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
                
    # 3. ★ 타순 완벽 분산 및 구장 배정 ★
    regions = working_df['지역'].unique()
    region_batting_counts = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in regions}
    final_roster = []
    
    for team_idx, team in enumerate(teams):
        team_name = f"{match_type} {team_idx + 1}조"
        fields = ['청', '백', '홍', '황']
        field = fields[team_idx % 4]
        hole = (team_idx // 4) % holes_per_field + 1
        start_hole = f"{field}구장 {hole}홀"
        
        # [핵심 로직] 아직 배정받지 못한 타순(0회)이 가장 많은 지역의 선수부터 타순 우선 선택권 부여
        team.sort(key=lambda p: sum(1 for v in region_batting_counts.get(p['지역'], {i:0 for i in range(1, players_per_team+1)}).values() if v == 0), reverse=True)
        
        available_orders = list(range(1, len(team) + 1))
        
        for player in team:
            if player['지역'] not in region_batting_counts:
                region_batting_counts[player['지역']] = {i: 0 for i in range(1, players_per_team + 1)}
                
            # 해당 선수의 지역이 가장 적게 배정받은 타순 후보들을 모두 추출
            min_usage = min(region_batting_counts[player['지역']][o] for o in available_orders)
            candidates = [o for o in available_orders if region_batting_counts[player['지역']][o] == min_usage]
            
            # 후보 중 무작위로 하나를 선택하여 특정 번호로 쏠리는 패턴 방지
            best_order = random.choice(candidates)
            
            available_orders.remove(best_order)
            region_batting_counts[player['지역']][best_order] += 1
            
            final_roster.append({
                '팀': team_name, '출발홀': start_hole, '타순': best_order,
                '지역': player['지역'], '이름': player['이름'], '성별': player['성별']
            })
            
    final_df = pd.DataFrame(final_roster)
    
    if final_df.empty:
        return final_df
    
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
st.markdown("엑셀 명단을 업로드하면 조편성 규칙을 적용하여 자동으로 대진표를 작성합니다. **(타순 밸런스 검증 기능 포함)**")

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
            st.error("❌