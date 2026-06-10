import streamlit as st
import pandas as pd
import numpy as np
import io
import random
import traceback

st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

try:
    # ==========================================
    # [기능 1] 대진표 자동 편성 로직
    # ==========================================
    def assign_teams_and_orders(df, holes_per_field=8, players_per_team=6, match_type="개인전"):
        working_df = df.copy()
        
        working_df['성별'] = working_df['성별'].astype(str).str.strip().str[0] 
        working_df['성별'] = working_df['성별'].apply(lambda x: '여' if x == '여' else '남')
        working_df['지역'] = working_df['지역'].astype(str).str.strip()
        
        num_teams = (len(working_df) + players_per_team - 1) // players_per_team
        if num_teams == 0: 
            return pd.DataFrame(), 0, {}
        
        teams = [[] for _ in range(num_teams)]
        fields = ['청', '백', '홍', '황']
        
        players = working_df.to_dict('records')
        females = [p for p in players if p['성별'] == '여']
        males = [p for p in players if p['성별'] == '남']
        
        r_counts = working_df['지역'].value_counts().to_dict()
        females.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
        males.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for p in females + males:
            allowed = [t for t in teams if len(t) < players_per_team]
            if not allowed: allowed = teams
            
            # 💡 [핵심] 1순위: 동명이인 피하기 / 2순위: 지역 분산 / 3순위: 성별 섞기
            best_team = min(allowed, key=lambda t: (
                sum(1 for x in t if x['이름'] == p['이름']),
                sum(1 for x in t if x['지역'] == p['지역']),
                sum(1 for x in t if x['성별'] == p['성별']),
                len(t)
            ))
            best_team.append(p)

        region_order_count = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in working_df['지역'].unique()}
        for team in teams:
            avail_orders = list(range(1, players_per_team + 1))
            best_perm = None
            best_score = float('inf')
            perms = [random.sample(avail_orders, len(team)) for _ in range(2000)]
            for perm in perms:
                score = 0
                for i, p in enumerate(team):
                    score += region_order_count[p['지역']].get(perm[i], 0) ** 2
                if score < best_score:
                    best_score = score
                    best_perm = perm
                    if score == 0: break
            for i, p in enumerate(team):
                p['타순'] = best_perm[i]
                region_order_count[p['지역']][best_perm[i]] += 1

        final_roster = []
        for idx, team in enumerate(teams):
            f_idx = idx % 4
            field_name = fields[f_idx]
            hole = (idx // 4) % holes_per_field + 1
            round_id = (idx // (4 * holes_per_field)) + 1
            
            s_hole = f"{field_name}구장 {hole}홀"
            set_name = f"{round_id}그룹 {field_name}구장" if len(teams) > holes_per_field * 4 else f"{field_name}구장"
                
            for p in team:
                final_roster.append({
                    '진행 그룹': set_name, '팀': f"{match_type} {idx+1}조", 
                    '구장': field_name, '홀': hole, '타순': p['타순'], 
                    '지역': p['지역'], '이름': p['이름'], '성별': p['성별'],
                    '_r': round_id, '_f': f_idx, '_h': hole
                })
                
        res_df = pd.DataFrame(final_roster).sort_values(by=['_r', '_f', '_h', '타순']).reset_index(drop=True)
        return res_df.drop(columns=['_r', '_f', '_h']), num_teams, region_order_count

    # ==========================================
    # [기능 2] 인쇄용 대진표 엑셀 출력 양식
    # ==========================================
    def create_print_excel(df, match_type, holes_cnt):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'})
            cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
            
            for f_name in ['청', '백', '홍', '황']:
                f_df = df[df['구장'] == f_name]
                if f_df.empty: continue
                
                worksheet = workbook.add_worksheet(f"{f_name}구장 대진표")
                worksheet.set_column('A:N', 10)
                worksheet.write(0, 0, f"제18회 대한체육회장배 {match_type} 대진표 ({f_name}구장)", workbook.add_format({'bold': True, 'font_size': 14}))
                
                row = 3
                for h in range(1, holes_cnt + 1, 2):
                    h1_data = f_df[f_df['홀'] == h]
                    h2_data = f_df[f_df['홀'] == h+1]
                    
                    heads = ['홀', '타순', '지역', '이름', '성별', '심판']
                    for c, text in enumerate(heads):
                        worksheet.write(row, c, text, header_fmt)
                        worksheet.write(row, c+7, text, header_fmt)
                    row += 1
                    
                    max_len = max(len(h1_data), len(h2_data), 6)
                    for i in range(max_len):
                        if i < len(h1_data):
                            p = h1_data.iloc[i]
                            val_h = h if i == 0 else ""
                            worksheet.write(row+i, 0, val_h, cell_fmt)
                            worksheet.write(row+i, 1, p['타순'], cell_fmt)
                            worksheet.write(row+i, 2, p['지역'], cell_fmt)
                            worksheet.write(row+i, 3, p['이름'], cell_fmt)
                            worksheet.write(row+i, 4, p['성별'], cell_fmt)
                            worksheet.write(row+i, 5, "", cell_fmt)
                        if i < len(h2_data):
                            p = h2_data.iloc[i]
                            val_h2 = h+1 if i == 0 else ""
                            worksheet.write(row+i, 7, val_h2, cell_fmt)
                            worksheet.write(row+i, 8, p['타순'], cell_fmt)
                            worksheet.write(row+i, 9, p['지역'], cell_fmt)
                            worksheet.write(row+i, 10, p['이름'], cell_fmt)
                            worksheet.write(row+i, 11, p['성별'], cell_fmt)
                            worksheet.write(row+i, 12, "", cell_fmt)
                    row += max_len + 1
        return output.getvalue()

    # ==========================================
    # [메인 화면 UI]
    # ==========================================
    st.title("⛳ 그라운드골프 대진표 편성 시스템")
    
    st.sidebar.title("⚙️ 편성 설정")
    m_type = st.sidebar.radio("편성 부문", ["개인전", "단체전"])
    h_cnt = st.sidebar.