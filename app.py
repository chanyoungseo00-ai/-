import streamlit as st
import pandas as pd
import numpy as np
import io

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
                player = remaining_players.pop(0)
                team.append(player)
                
    # 3. 타순 및 구장 배정
    regions = working_df['지역'].unique()
    region_batting_counts = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in regions}
    final_roster = []
    
    for team_idx, team in enumerate(teams):
        team_name = f"{match_type} {team_idx + 1}조"
        fields = ['청', '백', '홍', '황']
        field = fields[team_idx % 4]
        hole = (team_idx // 4) % holes_per_field + 1
        start_hole = f"{field}구장 {hole}홀"
        
        available_orders = list(range(1, len(team) + 1))
        for player in team:
            best_order = min(available_orders, key=lambda o: region_batting_counts[player['지역']].get(o, 0))
            available_orders.remove(best_order)
            if best_order in region_batting_counts[player['지역']]:
                region_batting_counts[player['지역']][best_order] += 1
            
            final_roster.append({
                '팀': team_name, '출발홀': start_hole, '타순': best_order,
                '지역': player['지역'], '이름': player['이름'], '성별': player['성별']
            })
            
    final_df = pd.DataFrame(final_roster)
    
    # 4. 정렬 로직 (타순 섞임 방지)
    final_df['구장_순서'] = final_df['출발홀'].str[0].map({'청': 1, '백': 2, '홍': 3, '황': 4})
    final_df['홀_번호'] = final_df['출발홀'].str.extract(r'(\d+)')[0].astype(int)
    final_df['조_번호'] = final_df['팀'].str.extract(r'(\d+)')[0].astype(int)
    
    final_df = final_df.sort_values(by=['구장_순서', '홀_번호', '조_번호', '타순']).reset_index(drop=True)
    final_df = final_df.drop(columns=['구장_순서', '홀_번호', '조_번호'])
    
    return final_df

# --- 웹사이트 화면 구성 ---
st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

st.title("⛳ 전국그라운드골프대회 대진표 자동 편성 시스템")
st.markdown("엑셀 명단을 업로드하면 조편성 규칙을 적용하여 자동으로 대진표를 작성합니다. **(지역별 배치 검증표 포함)**")

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
            st.success(f"✅ 총 {len(df)}명의 선수 명단을 성공적으로 불러왔습니다!")
            
            if st.button(f"🚀 {match_type} 자동 조 편성 실행", type="primary"):
                with st.spinner("최적의 배치를 계산 중입니다..."):
                    
                    # 1. 대진표 생성
                    final_df = assign_teams_and_orders(df, holes_per_field=holes, players_per_team=players, match_type=match_type)
                    
                    st.subheader(f"🎉 {match_type} 대진표 편성 완료")
                    st.dataframe(final_df, use_container_width=True)
                    
                    # ---------------------------------------------------------
                    # ★ 추가된 로직: 지역별 구장 및 조 배치 검증표 생성 ★
                    # ---------------------------------------------------------
                    st.markdown("---")
                    st.subheader("📊 지역별 배치 검증 리포트")
                    st.markdown("프로그램이 대회 규정을 완벽하게 준수하여 조를 편성했는지 확인하는 검증표입니다.")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    # 구장 컬럼 임시 생성 (청구장, 백구장 등)
                    temp_df = final_df.copy()
                    temp_df['구장'] = temp_df['출발홀'].str[0] + '구장'
                    
                    # 검증표 1: 지역 vs 구장
                    validation_field = pd.crosstab(temp_df['지역'], temp_df['구장'])
                    # 검증표 2: 지역 vs 조
                    validation_team = pd.crosstab(temp_df['지역'], temp_df['팀'])
                    
                    with col1:
                        st.markdown("**1. 지역별 구장(청·백·홍·황) 분산 현황**")
                        st.caption("각 지역 선수들이 특정 구장에 쏠리지 않고 고르게 분배되었는지 확인합니다.")
                        st.dataframe(validation_field, use_container_width=True)
                        
                    with col2:
                        st.markdown("**2. 한 조에 동일 지역 중복 배치 여부 (1 초과 시 에러)**")
                        # 겹친 지역이 있는지 최대값으로 확인
                        max_overlap = validation_team.max().max()
                        if max_overlap > 1:
                            st.error(f"⚠️ 주의: 남은 인원 배정 문제로 동일 조에 같은 지역 선수가 {max_overlap}명 중복 배치된 곳이 있습니다.")
                        else:
                            st.success("✅ 완벽합니다! 모든 조에 동일 지역 선수가 겹치지 않고 1명씩 분산 배치되었습니다.")
                        st.dataframe(validation_team, use_container_width=True)

                    # ---------------------------------------------------------
                    # 엑셀 파일 저장 (검증표 시트 추가)
                    # ---------------------------------------------------------
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        # 1번째 시트: 대진표
                        final_df.to_excel(writer, index=False, sheet_name=f'{match_type}_대진표')
                        # 2번째 시트: 구장별 분산 검증표
                        validation_field.to_excel(writer, sheet_name='지역별_구장검증')
                        # 3번째 시트: 조별 중복 검증표
                        validation_team.to_excel(writer, sheet_name='지역별_조검증')
                        
                    processed_data = output.getvalue()
                    
                    st.markdown("---")
                    st.download_button(
                        label=f"📥 {match_type} 대진표 및 검증표 엑셀 다운로드",
                        data=processed_data,
                        file_name=f"제18회_대한체육회장배_{match_type}_대진표_결과.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")