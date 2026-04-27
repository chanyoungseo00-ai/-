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
    # [3] ★ 수정됨: 구장 배정 및 [홀 단위] 세트별 정렬 
    # ==========================================
    final_roster = []
    fields = ['청', '백', '홍', '황']
    
    for team_idx, team in enumerate(teams):
        team_id = team_idx + 1
        
        # 구장, 홀, 그룹(오전/오후반) 계산
        field_val = team_idx % 4
        field = fields[field_val]
        hole = (team_idx // 4) % holes_per_field + 1
        round_id = (team_idx // (4 * holes_per_field)) + 1 
        
        start_hole = f"{field}구장 {hole}홀"
        
        # 참가 인원이 많아 동일 구장을 2바퀴 이상 돌아야 할 경우 그룹 명시
        if len(teams) > holes_per_field * 4:
            set_name = f"{round_id}그룹 {hole}홀 세트"
        else:
            set_name = f"{hole}홀 세트"
            
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
                '_hole_val': hole,
                '_field_val': field_val
            })
            
    final_df = pd.DataFrame(final_roster)
    
    # ★ 정렬 기준: 그룹(바퀴수) ➔ 홀 번호 ➔ 구장(청백홍황) ➔ 타순
    final_df = final_df.sort_values(by=['_round_val', '_hole_val', '_field_val', '타순']).reset_index(drop=True)
    
    # 계산용 임시 컬럼 삭제
    final_df = final_df.drop(columns=['_round_val', '_hole_val', '_field_val'])
    
    return final_df

# --- 웹사이트 화면 구성 ---
st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")
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
                with st.spinner("명단 분석 및 최적의 배치를 초고속으로 계산 중입니다..."):
                    
                    final_df = assign_teams_and_orders(df, holes_per_field=holes, players_per_team=players, match_type=match_type)
                    
                    st.subheader(f"🎉 {match_type} 대진표 편성 완료")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # --- 검증 리포트 영역 ---
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