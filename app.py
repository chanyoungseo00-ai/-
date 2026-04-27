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

    # ==========================================
    # [1] 개인전 로직 
    # ==========================================
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

    # ==========================================
    # [2] 단체전 로직
    # ==========================================
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

    # ==========================================
    # [3] ★ 수정됨: 구장별(청->백->홍->황) 묶음 정렬 
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
        
        # 그룹 명칭을 구장 중심으로 변경
        if len(teams) > holes_per_field * 4:
            set_name = f"{round_id}그룹 {field}구장"
        else:
            set_name = f"{field}구장"
            
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
    
    # ★ 정렬 기준: 그룹