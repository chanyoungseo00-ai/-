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
    
    if num_teams == 0: return pd.DataFrame()

    # [1] 개인전 로직 (지역 중복 방지 중심)
    if match_type == "개인전":
        players = working_df.to_dict('records')
        region_counts = working_df['지역'].value_counts().to_dict()
        players.sort(key=lambda x: (region_counts.get(x['지역'], 0), x['지역']), reverse=True)
        teams = [[] for _ in range(num_teams)]
        for p in players:
            best_team = None
            min_len = float('inf')
            for t in teams:
                if len(t) < players_per_team and p['지역'] not in [x['지역'] for x in t]:
                    if len(t) < min_len:
                        min_len = len(t)
                        best_team = t
            if best_team is not None: best_team.append(p)
            else:
                available_teams = [t for t in teams if len(t) < players_per_team]
                if available_teams: best_team = min(available_teams, key=len); best_team.append(p)
                else: teams[-1].append(p)
        for _ in range(50):
            violation = False
            for t1 in teams:
                regions1 = [x['지역'] for x in t1]
                for p1 in t1:
                    if regions1.count(p1['지역']) > 1:
                        violation = True
                        swapped = False
                        for t2 in teams:
                            if t1 is t2: continue
                            if p1['지역'] not in [x['지역'] for x in t2]:
                                for p2 in t2:
                                    t1_regions_without_p1 = [x['지역'] for x in t1 if x is not p1]
                                    if p2['지역'] not in t1_regions_without_p1:
                                        t1.remove(p1); t2.remove(p2); t1.append(p2); t2.append(p1)
                                        swapped = True; break
                            if swapped: break
                        if swapped: break
                if violation: break
            if not violation: break
        for team in teams:
            random.shuffle(team)
            for i, p in enumerate(team): p['타순'] = i + 1

    # [2] 단체전 로직 (성별 우선, 타순 평탄화 중심)
    else:
        females = working_df[working_df['성별'] == '여'].to_dict('records')
        males = working_df[working_df['성별'] == '남'].to_dict('records')
        teams = [[] for _ in range(num_teams)]
        for team in teams:
            assigned_regions = set()
            for _ in range(2):
                for i, p in enumerate(females):
                    if p['지역'] not in assigned_regions:
                        team.append(p); assigned_regions.add(p['지역']); females.pop(i); break
        remaining_players = females + males
        remaining_players.sort(key=lambda x: str(x['지역'])) 
        for team in teams:
            assigned_regions = {p['지역'] for p in team}
            while len(team) < team_size and remaining_players:
                for i, p in enumerate(remaining_players):
                    if p['지역'] not in assigned_regions:
                        team.append(p); assigned_regions.add(p['지역']); remaining_players.pop(i); break
                else:
                    if remaining_players: player = remaining_players.pop(0); team.append(player)
        for team in teams:
            available = list(range(1, players_per_team + 1))
            random.shuffle(available)
            for i, p in enumerate(team): p['타순'] = available[i]

    # [3] 공통: 구장 배정 및 세트별 정렬
    final_roster = []
    fields = ['청', '백', '홍', '황']
    for team_idx, team in enumerate(teams):
        team_id = team_idx + 1
        set_id = (team_idx // 4) + 1  # 4개 조가 한 세트
        field = fields[team_idx % 4]
        hole = (team_idx // 4) % holes_per_field + 1
        start_hole = f"{field}구장 {hole}홀"
        for p in team:
            final_roster.append({
                '세트': f"{set_id}세트", '팀': f"{match_type} {team_id}조", '출발홀': start_hole, 
                '타순': p['타순'], '지역': p['지역'], '이름': p['이름'], '성별': p['성별'],
                '_field_val': team_idx % 4, '_set_val': set_id # 정렬용 임시값
            })
            
    final_df = pd.DataFrame(final_roster)
    # 정렬: 세트 ➔ 구장(청백홍황) ➔ 타순
    final_df = final_df.sort_values(by=['_set_val', '_field_val', '타순']).reset_index(drop=True)
    final_df = final_df.drop(columns=['_field_val', '_set_val'])
    
    return final_df

# --- 화면 구성 생략 (기존과 동일) ---
st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")
st.title("⛳ 전국그라운드골프대회 대진표 시스템")
with st.sidebar:
    st.header("⚙️ 설정")
    match_type = st.radio("🏆 부문", ("개인전", "단체전"))
    holes = st.radio("출발홀", (6, 7, 8), index=2)
    players = st.radio("조당 인원", (6, 7, 8), index=0)

uploaded_file = st.file_uploader("엑셀 업로드", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()
    if st.button("🚀 조 편성 실행"):
        final_df = assign_teams_and_orders(df, holes, players, match_type)
        st.subheader("🎉 편성 완료 (세트별 묶음)")
        st.dataframe(final_df, use_container_width=True)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='대진표')
        st.download_button("📥 엑셀 다운로드", output.getvalue(), file_name=f"{match_type}_대진표.xlsx")