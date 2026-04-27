import streamlit as st
import pandas as pd
import numpy as np
import io
import random

st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

def assign_teams_and_orders(df, holes_per_field=8, players_per_team=6, match_type="개인전"):
    working_df = df.copy()
    total_players = len(working_df)
    team_size = players_per_team
    num_teams = (total_players + team_size - 1) // team_size
    
    if num_teams == 0:
        return pd.DataFrame()

    teams = [[] for _ in range(num_teams)]

    # ==========================================
    # [1] 개인전 로직 (빈도수 기반 스마트 분산)
    # ==========================================
    if match_type == "개인전":
        players = working_df.to_dict('records')
        # 1. 인원수가 많은 지역부터 먼저 배치하기 위해 정렬
        region_counts = working_df['지역'].value_counts().to_dict()
        players.sort(key=lambda x: (region_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        # 2. 각 선수별로 최적의 조 탐색
        for p in players:
            best_team = None
            best_score = (float('inf'), float('inf')) # (동일 지역 수, 현재 조 인원수)
            
            for t in teams:
                if len(t) < players_per_team:
                    r_count = sum(1 for x in t if x['지역'] == p['지역'])
                    score = (r_count, len(t))
                    # 동일 지역 인원이 가장 적은 조 ➔ 인원수가 가장 적은 조 순으로 우선순위
                    if score < best_score:
                        best_score = score
                        best_team = t
                        
            if best_team is not None:
                best_team.append(p)
                
        # 3. 타순 무작위 배정
        for team in teams:
            available = list(range(1, players_per_team + 1))
            random.shuffle(available)
            for i, p in enumerate(team):
                p['타순'] = available[i]

    # ==========================================
    # [2] 단체전 로직 (여성 필수 포함 + 빈도수 분산)
    # ==========================================
    else:
        females = working_df[working_df['성별'] == '여'].to_dict('records')
        males = working_df[working_df['성별'] == '남'].to_dict('records')
        
        # 1. 여성 선수 먼저 인원수가 많은 지역 순으로 정렬하여 2명씩 배치
        f_region_counts = pd.Series([p['지역'] for p in females]).value_counts().to_dict()
        females.sort(key=lambda x: (f_region_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for team in teams:
            for _ in range(2):
                best_idx = -1
                for i, p in enumerate(females):
                    if p['지역'] not in [x['지역'] for x in team]:
                        best_idx = i
                        break
                if best_idx != -1:
                    team.append(females.pop(best_idx))
                elif females:
                    team.append(females.pop(0)) # 중복 감수하고 강제 배치
                    
        # 2. 남은 인원 역시 지역 인원수 순으로 정렬하여 최적 분산
        remaining_players = females + males
        all_region_counts = pd.Series([p['지역'] for p in remaining_players]).value_counts().to_dict()
        remaining_players.sort(key=lambda x: (all_region_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for p in remaining_players:
            best_team = None
            best_score = (float('inf'), float('inf'))
            for t in teams:
                if len(t) < players_per_team:
                    r_count = sum(1 for x in t if x['지역'] == p['지역'])
                    score = (r_count, len(t))
                    if score < best_score:
                        best_score = score
                        best_team = t
            if best_team is not None:
                best_team.append(p)

        # 3. 단체전 전용 타순 평탄화 (기존 문제없던 타순 로직 유지)
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
                    
            worst_region = None; worst_skew = -1; worst_over = -1; worst_under = -1
            
            for r, usage in region_usage.items():
                counts = usage.values()
                skew = max(counts) - min(counts)
                if skew > worst_skew:
                    worst_skew = skew; worst_region = r
                    worst_over = max(usage, key=usage.get); worst_under = min(usage, key=usage.get)
                    
            if worst_skew <= 1: break 
                
            teams_with_over = [t for t in teams if any(p['지역'] == worst_region and p['타순'] == worst_over for p in t)]
            swapped = False
            random.shuffle(teams_with_over)
            
            for team in teams_with_over:
                try:
                    p1 = next(p for p in team if p['지역'] == worst_region and p['타순'] == worst_over)
                    p2 = next((p for p in team if p['타순'] == worst_under), None)
                    if p2 is None:
                        p1['타순'] = worst_under; swapped = True; break
                    else:
                        r2 = p2['지역']
                        if region_usage[r2][worst_over] <= region_usage[r2][worst_under]:
                            p1['타순'], p2['타순'] = p2['타순'], p1['타순']
                            swapped = True; break
                except StopIteration: continue
                        
            if not swapped and teams_with_over:
                team = teams_with_over[0]
                try:
                    p1 = next(p for p in team if p['지역'] == worst_region and p['타순'] == worst_over)
                    p2 = next((p for p in team if p['타순'] == worst_under), None)
                    if p2 is None: p1['타순'] = worst_under
                    else: p1['타순'], p2['타순'] = p2['타순'], p1['타순']
                except StopIteration: pass

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
                '진행 그룹': set_name, '팀': f"{match_type} {team_id}조", '출발홀': start_hole, 
                '타순': p['타순'], '지역': p['지역'], '이름': p['이름'], '성별': p['성별'],
                '_round_val': round_id, '_field_val': field_val, '_hole_val': hole
            })
            
    final_df = pd.DataFrame(final_roster)
    final_df = final_df.sort_values(by=['_round_val', '_field_val', '_hole_val', '타순']).reset_index(drop=True)
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
                    
                    final_df, total_teams = assign_teams_and_orders(df, holes_per_field=holes, players_per_team=players, match_type=match_type)
                    
                    st.subheader(f"🎉 {match_type} 대진표 편성 완료 (총 {total_teams}개 조)")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # --- 검증 리포트 영역 ---
                    st.markdown("---")
                    st.subheader("📊 배치 검증 리포트")
                    
                    temp_df = final_df.copy()
                    validation_team = pd.crosstab(temp_df['지역'], temp_df['팀'])   
                    
                    team_errors = []
                    unavoidable_errors = False
                    
                    for region_idx in validation_team.index:
                        region_total_players = df[df['지역'] == region_idx].shape[0]
                        # 해당 지역의 인원이 전체 조 개수보다 많으면 중복은 '수학적으로 불가피함'
                        is_unavoidable = region_total_players > total_teams
                        
                        for team_col in validation_team.columns:
                            count = validation_team.loc[region_idx, team_col]
                            if count > 1:
                                team_errors.append({
                                    '구분': '불가피한 중복' if is_unavoidable else '일반 중복',
                                    '문제 발생 조': team_col, 
                                    '중복된 지역': region_idx, 
                                    '배치된 인원수': f"{count}명"
                                })
                                if is_unavoidable: unavoidable_errors = True
                                
                    st.markdown("**■ 한 조에 동일 지역 선수 중복 배치 검증**")
                    if not team_errors:
                        st.success("✅ 오류 없음 (모든 조에 동일 지역 선수가 겹치지 않고 안전하게 분리 배치되었습니다.)")
                    else:
                        if unavoidable_errors:
                            st.warning(f"⚠️ 일부 지역 인원이 전체 조 개수({total_teams}개)보다 많아 수학적으로 불가피하게 발생한 중복 내역입니다.")
                        else:
                            st.error("⚠️ 남은 인원 구조상 불가피하게 겹친 내역입니다.")
                        st.dataframe(pd.DataFrame(team_errors), use_container_width=True, hide_index=True)

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        final_df.to_excel(writer, index=False, sheet_name=f'{match_type}_대진표')
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