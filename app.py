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
            
            if best_team is not None:
                best_team.append(p)
            else:
                available_teams = [t for t in teams if len(t) < players_per_team]
                if available_teams:
                    best_team = min(available_teams, key=len)
                    best_team.append(p)
                else:
                    teams[-1].append(p)
                
        for _ in range(100):
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
                                        t1.remove(p1)
                                        t2.remove(p2)
                                        t1.append(p2)
                                        t2.append(p1)
                                        swapped = True
                                        break
                            if swapped: break
                        if swapped: break
                if violation: break
            if not violation: break
            
        final_roster = []
        for team_idx, team in enumerate(teams):
            team_name = f"개인전 {team_idx + 1}조"
            fields = ['청', '백', '홍', '황']
            field = fields[team_idx % 4]
            hole = (team_idx // 4) % holes_per_field + 1
            start_hole = f"{field}구장 {hole}홀"
            
            random.shuffle(team)
            for i, player in enumerate(team):
                final_roster.append({
                    '팀': team_name, '출발홀': start_hole, '타순': i + 1,
                    '지역': player['지역'], '이름': player['이름'], '성별': player['성별']
                })

    else:
        females = working_df[working_df['성별'] == '여'].to_dict('records')
        males = working_df[working_df['성별'] == '남'].to_dict('records')
        teams = [[] for _ in range(num_teams)]
        
        for team in teams:
            assigned_regions = set()
            for _ in range(2):
                for i, p in enumerate(females):
                    if p['지역'] not in assigned_regions:
                        team.append(p)
                        assigned_regions.add(p['지역'])
                        females.pop(i)
                        break
                        
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
                        
        for _ in range(100):
            violation = False
            for team in teams:
                regions_in_team = [p['지역'] for p in team]
                for p in team:
                    if regions_in_team.count(p['지역']) > 1:
                        violation = True
                        swapped = False
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
                                        swapped = True
                                        break
                            if swapped: break
                        if swapped: break
                if violation: break
            if not violation: break
                
        for team in teams:
            available = list(range(1, players_per_team + 1))
            random.shuffle(available)
            for i, p in enumerate(team):
                p['타순'] = available[i]

        for _ in range(1000):
            region_usage = {}
            for team in teams:
                for p in team:
                    r = p['지역']
                    o = p['타순']
                    if r not in region_usage:
                        region_usage[r] = {i: 0 for i in range(1, players_per_team + 1)}
                    region_usage[r][o] += 1
                    
            worst_region = None
            worst_skew = -1
            worst_over = -1
            worst_under = -1
            
            for r, usage in region_usage.items():
                counts = usage.values()
                skew = max(counts) - min(counts)
                if skew > worst_skew:
                    worst_skew = skew
                    worst_region = r
                    worst_over = max(usage, key=usage.get)
                    worst_under = min(usage, key=usage.get)
                    
            if worst_skew <= 1: break 
                
            teams_with_over = [t for t in teams if any(p['지역'] == worst_region and p['타순'] == worst_over for p in t)]
            swapped = False
            random.shuffle(teams_with_over)
            
            for team in teams_with_over:
                try:
                    p1 = next(p for p in team if p['지역'] == worst_region and p['타순'] == worst_over)
                    p2 = next((p for p in team if p['타순'] == worst_under), None)
                    
                    if p2 is None:
                        p1['타순'] = worst_under
                        swapped = True
                        break
                    else:
                        r2 = p2['지역']
                        if region_usage[r2][worst_over] <= region_usage[r2][worst_under]:
                            p1['타순'], p2['타순'] = p2['타순'], p1['타순']
                            swapped = True
                            break
                except StopIteration:
                    continue
                        
            if not swapped and teams_with_over:
                team = teams_with_over[0]
                try:
                    p1 = next(p for p in team if p['지역'] == worst_region and p['타순'] == worst_over)
                    p2 = next((p for p in team if p['타순'] == worst_under), None)
                    if p2 is None: p1['타순'] = worst_under
                    else: p1['타순'], p2['타순'] = p2['타순'], p1['타순']
                except StopIteration:
                    pass

        final_roster = []
        for team_idx, team in enumerate(teams):
            team_name = f"단체전 {team_idx + 1}조"
            fields = ['청', '백', '홍', '황']
            field = fields[team_idx % 4]
            hole = (team_idx // 4) % holes_per_field + 1
            start_hole = f"{field}구장 {hole}홀"
            
            for player in team:
                final_roster.append({
                    '팀': team_name, '출발홀': start_hole, '타순': player['타순'],
                    '지역': player['지역'], '이름': player['이름'], '성별': player['성별']
                })
                
    final_df = pd.DataFrame(final_roster)
    if final_df.empty: return final_df
    
    final_df['구장_순서'] = final_df['출발홀'].str[0].map({'청': 1, '백': 2, '홍': 3, '황': 4}).fillna(99)
    final_df['홀_번호'] = final_df['출발홀'].str.extract(r'(\d+)', expand=False).fillna(0).astype(int)
    final_df['조_번호'] = final_df['팀'].str.extract(r'(\d+)', expand=False).fillna(0).astype(int)
    
    final_df = final_df.sort_values(by=['구장_순서', '홀_번호', '조_번호', '타순']).reset_index(drop=True)
    final_df = final_df.drop(columns=['구장_순서', '홀_번호', '조_번호'])
    
    return final_df

st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

st.title("⛳ 전국그라운드골프대회 대진표 자동 편성 시스템")
st.markdown("엑셀 명단을 업로드하면 설정된 부문(개인전/단체전)의 맞춤형 규칙을 적용하여 대진표를 작성합니다.")

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
                with st.spinner("명단 분석 및 최적의 배치를 계산 중입니다..."):
                    
                    final_df = assign_teams_and_orders(df, holes_per_field=holes, players_per_team=players, match_type=match_type)
                    
                    st.subheader(f"🎉 {match_type} 대진표 편성 완료")
                    st.dataframe(final_df, use_container_width=True)
                    
                    st.markdown("---")
                    st.subheader("📊 배치 검증 리포트")
                    
                    temp_df = final_df.copy()
                    validation_team = pd.crosstab(temp_df['지역'], temp_df['팀'])   
                    
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
                                
                    st.markdown("**■ 한 조에 동일 지역 선수 중복 배치 검증**")
                    if not team_errors:
                        st.success("✅ 오류 없음 (모든 조에 동일 지역 선수가 겹치지 않고 안전하게 1명씩 분리 배치되었습니다.)")
                    else:
                        st.error("⚠️ 동일 조 중복 배치 오류 (남은 인원 구조상 불가피하게 겹친 내역입니다.)")
                        st.dataframe(pd.DataFrame(team_errors), use_container_width=True, hide_index=True)

                    validation_order = None
                    if match_type == "단체전":
                        validation_order = pd.crosstab(temp_df['지역'], temp_df['타순']) 
                        order_errors = []
                        short_players_regions = []
                        
                        for region in validation_order.index:
                            region_total = validation_order.loc[region].sum()
                            zeros = validation_order.columns[validation_order.loc[region] == 0].tolist()
                            if region_total >= players:
                                if zeros: 
                                    order_errors.append({'지역': region, '총 인원수': f"{region_total}명", '누락된 타순': ", ".join(map(lambda x: f"{x}번", zeros))})
                            else:
                                used_orders = (validation_order.loc[region] > 0).sum()
                                if used_orders < region_total:
                                    duplicates = validation_order.columns[validation_order.loc[region] > 1].tolist()
                                    order_errors.append({'지역': region, '총 인원수': f"{region_total}명", '중복 쏠림 타순': ", ".join(map(lambda x: f"{x}번", duplicates))})
                                else:
                                    short_players_regions.append(f"{region}({region_total}명)")
                                    
                        st.markdown("<br>**■ [단체전 전용] 지역별 타순 평탄화 검증**", unsafe_allow_html=True)
                        if not order_errors:
                            st.success("✅ 오류 없음 (모든 지역 선수가 특정 번호에 쏠림 없이 완벽히 평탄화되어 배치되었습니다.)")
                        else:
                            st.error("⚠️ 타순 배정 오류 (아래 지역의 타순 쏠림 내역을 확인하세요.)")
                            st.dataframe(pd.DataFrame(order_errors), use_container_width=True, hide_index=True)

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        final_df.to_excel(writer, index=False, sheet_name=f'{match_type}_대진표')
                        if match_type == "단체전" and validation_order is not None:
                            validation_order.to_excel(writer, sheet_name='지역별_타순검증')
                        validation_team.to_excel(writer, sheet_name='지역별_조검증')
                    processed_data = output.getvalue()
                    
                    st.markdown("---")
                    st.download_button(
                        label=f"📥 {match_type} 대진표 엑셀 다운로드",
                        data=processed_data,
                        file_name=f"제18회_대한체육회장배_{match_type}_대진표_최종.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    except Exception as e:
        st.error(f"오류가 발생했습니다. 원본 엑셀 파일을 다시 확인해 주세요: {e}")