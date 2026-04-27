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
        return pd.DataFrame(), 0

    teams = [[] for _ in range(num_teams)]

    # ==========================================
    # [1] 개인전 로직 (지역 중복 방지 최우선)
    # ==========================================
    if match_type == "개인전":
        players = working_df.to_dict('records')
        region_counts = working_df['지역'].value_counts().to_dict()
        players.sort(key=lambda x: (region_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for p in players:
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
                
        for team in teams:
            random.shuffle(team)
            for i, p in enumerate(team):
                p['타순'] = i + 1

    # ==========================================
    # [2] 단체전 로직 (여성 포함 + 타순 평탄화)
    # ==========================================
    else:
        females = working_df[working_df['성별'] == '여'].to_dict('records')
        males = working_df[working_df['성별'] == '남'].to_dict('records')
        
        f_region_counts = pd.Series([p['지역'] for p in females]).value_counts().to_dict()
        females.sort(key=lambda x: (f_region_counts.get(x['지역'], 0), x['지역']), reverse=True)
        
        for team in teams:
            for _ in range(2):
                best_idx = -1
                for i, p in enumerate(females):
                    if p['지역'] not in [x['지역'] for x in team]:
                        best_idx = i; break
                if best_idx != -1: team.append(females.pop(best_idx))
                elif females: team.append(females.pop(0))
                    
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
                        best_score = score; best_team = t
            if best_team is not None: best_team.append(p)

        # 타순 평탄화 알고리즘
        for team in teams:
            available = list(range(1, players_per_team + 1))
            random.shuffle(available)
            for i, p in enumerate(team): p['타순'] = available[i]

        for _ in range(500):
            region_usage = {}
            for team in teams:
                for p in team:
                    r, o = p['지역'], p['타순']
                    if r not in region_usage: region_usage[r] = {i: 0 for i in range(1, players_per_team + 1)}
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
            random.shuffle(teams_with_over)
            for team in teams_with_over:
                try:
                    p1 = next(p for p in team if p['지역'] == worst_region and p['타순'] == worst_over)
                    p2 = next((p for p in team if p['타순'] == worst_under), None)
                    if p2 is None: p1['타순'] = worst_under; break
                    else:
                        r2 = p2['지역']
                        if region_usage[r2][worst_over] <= region_usage[r2][worst_under]:
                            p1['타순'], p2['타순'] = p2['타순'], p1['타순']; break
                except StopIteration: continue

    # ==========================================
    # [3] 정렬 및 결과 생성
    # ==========================================
    final_roster = []
    fields = ['청', '백', '홍', '황']
    for team_idx, team in enumerate(teams):
        team_id = team_idx + 1
        field_val = team_idx % 4
        field, hole = fields[field_val], (team_idx // 4) % holes_per_field + 1
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

# --- UI 레이아웃 ---
st.title("⛳ 전국그라운드골프대회 대진표 자동 편성 시스템")

with st.sidebar:
    st.header("⚙️ 대회 규정 설정")
    match_type = st.radio("🏆 편성 부문 선택", ("개인전", "단체전"), index=0)
    holes = st.radio("출발홀 수 선택", (6, 7, 8), index=2)
    players = st.radio("1조당 최대 인원", (6, 7, 8), index=0)

uploaded_file = st.file_uploader(f"[{match_type}] 참가선수명단 엑셀 파일(.xlsx)을 올려주세요.", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()
        if not {'지역', '이름', '성별'}.issubset(df.columns):
            st.error("❌ 엑셀 파일에 '지역', '이름', '성별' 열이 모두 포함되어 있는지 확인해 주세요.")
        else:
            df = df.dropna(subset=['지역', '이름', '성별']).copy()
            st.success(f"✅ 총 {len(df)}명의 선수 명단을 불러왔습니다.")
            
            if st.button(f"🚀 {match_type} 자동 조 편성 실행", type="primary"):
                final_df, total_teams = assign_teams_and_orders(df, holes, players, match_type)
                st.subheader(f"🎉 {match_type} 대진표 편성 완료")
                st.dataframe(final_df, use_container_width=True)
                
                # --- 검증 리포트 영역 ---
                st.markdown("---")
                st.subheader("📊 무결성 검증 리포트")
                
                # [1] 지역 중복 검증
                validation_team = pd.crosstab(final_df['지역'], final_df['팀'])
                team_errors = []
                for r_idx in validation_team.index:
                    for t_col in validation_team.columns:
                        if validation_team.loc[r_idx, t_col] > 1:
                            team_errors.append({'조': t_col, '지역': r_idx, '인원': f"{validation_team.loc[r_idx, t_col]}명"})
                
                st.markdown("**■ 한 조 동일 지역 선수 중복 여부**")
                if not team_errors: st.success("✅ 오류 없음 (지역 분산 완료)")
                else: st.error("⚠️ 중복 발생"); st.dataframe(pd.DataFrame(team_errors), use_container_width=True)

                # [2] 타순 분포 검증 (추가된 부분)
                st.markdown("<br>**■ 지역별 타순 분포 현황 (순환 배치 검증)**", unsafe_allow_html=True)
                validation_order = pd.crosstab(final_df['지역'], final_df['타순'])
                order_errors = []
                for r_idx in validation_order.index:
                    r_total = df[df['지역'] == r_idx].shape[0]
                    zeros = validation_order.columns[validation_order.loc[r_idx] == 0].tolist()
                    if r_total >= players and zeros:
                        order_errors.append({'지역': r_idx, '누락 타순': ", ".join(map(lambda x: f"{x}번", zeros))})
                
                if not order_errors: st.success("✅ 모든 지역이 모든 타순에 1회 이상 배정되었습니다.")
                else: st.warning("⚠️ 일부 타순 누락 발생 (아래 분포표 참조)"); st.write(pd.DataFrame(order_errors))
                
                st.dataframe(validation_order, use_container_width=True)

                # 다운로드
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='대진표')
                    validation_order.to_excel(writer, sheet_name='타순분포')
                st.download_button("📥 최종 결과 엑셀 다운로드", output.getvalue(), file_name=f"{match_type}_대진표_최종.xlsx")
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")