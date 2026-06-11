import streamlit as st
import pandas as pd
import numpy as np
import io
import traceback

st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

try:
    # 1. 편성 로직 (동명이인 분리 + 통합 편성)
    def assign_teams_and_orders(df, holes_per_field=8, p_cnt_indiv=6, p_cnt_team=6, match_type="개인전"):
        players = df.to_dict('records')
        def distribute_players(target_players, target_teams, p_cnt):
            if not target_players: return
            r_counts = pd.Series([p['지역'] for p in target_players]).value_counts().to_dict()
            target_players.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
            for p in target_players:
                allowed = [t for t in target_teams if len(t) < p_cnt] or target_teams
                best_team = min(allowed, key=lambda t: (sum(1 for x in t if x['이름'] == p['이름']), sum(1 for x in t if x['지역'] == p['지역']), sum(1 for x in t if x['성별'] == p['성별']), len(t)))
                best_team.append(p)

        def assign_orders(target_teams, p_cnt):
            region_order_count = {r: {i: 0 for i in range(1, p_cnt + 1)} for r in df['지역'].unique()}
            for team in target_teams:
                avail_orders = list(range(1, p_cnt + 1))
                team.sort(key=lambda x: x['지역'])
                for p in team:
                    best_order = min(avail_orders, key=lambda o: region_order_count[p['지역']].get(o, 0))
                    p['타순'] = best_order
                    avail_orders.remove(best_order)
                    region_order_count[p['지역']][best_order] += 1
        
        if match_type == "통합 (단체전 ➔ 개인전 이어서)":
            team_players = [p for p in players if '단체' in p.get('부문', '')]
            indiv_players = [p for p in players if '단체' not in p.get('부문', '')]
            team_teams = [[] for _ in range((len(team_players) + p_cnt_team - 1) // p_cnt_team)] if team_players else []
            indiv_teams = [[] for _ in range((len(indiv_players) + p_cnt_indiv - 1) // p_cnt_indiv)] if indiv_players else []
            distribute_players(team_players, team_teams, p_cnt_team); distribute_players(indiv_players, indiv_teams, p_cnt_indiv)
            assign_orders(team_teams, p_cnt_team); assign_orders(indiv_teams, p_cnt_indiv)
            teams = team_teams + indiv_teams
        else:
            p_cnt = p_cnt_team if match_type == "단체전" else p_cnt_indiv
            teams = [[] for _ in range((len(players) + p_cnt - 1) // p_cnt)]
            distribute_players(players, teams, p_cnt); assign_orders(teams, p_cnt)

        fields = ['청', '백', '홍', '황']
        final_roster = []
        for idx, team in enumerate(teams):
            round_id = (idx // (4 * holes_per_field)) + 1
            for p in team:
                final_roster.append({'경기': f"{round_id}부", '구장': fields[idx % 4], '홀': (idx // 4) % holes_per_field + 1, '팀': f"{idx+1}조", '타순': p['타순'], '대진표': f"{fields[idx % 4]} {(idx // 4) % holes_per_field + 1} {p['타순']}", '부문': p.get('부문', match_type), '지역': p['지역'], '이름': p['이름'], '성별': p['성별'], '_r': round_id, '_f': idx % 4, '_h': (idx // 4) % holes_per_field + 1})
        return pd.DataFrame(final_roster).sort_values(by=['_r', '_f', '_h', '타순']).reset_index(drop=True).drop(columns=['_r', '_f', '_h']), len(teams)

    # 2. 엑셀 출력 및 데이터 처리 함수 생략(위와 동일)...
    
    # [UI 구성]
    try: st.image("edited-image.jpg", width=350)
    except: st.warning("로고 파일을 확인해 주세요.")
    
    st.title("그라운드골프 대진표 편성 시스템")
    # (위의 로직을 결합하여 실행)
    
except Exception as e:
    st.error(f"시스템 오류: {e}")