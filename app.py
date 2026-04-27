import streamlit as st
import pandas as pd
import numpy as np
import io

def assign_teams_and_orders(df, holes_per_field=8, players_per_team=6):
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
                
    # 3. 타순 및 구장 배정 (청, 백, 홍, 황)
    regions = working_df['지역'].unique()
    region_batting_counts = {r: {i: 0 for i in range(1, players_per_team + 1)} for r in regions}
    final_roster = []
    
    for team_idx, team in enumerate(teams):
        team_name = f"{team_idx + 1}조"
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
                '지역': player['지역'], '성명': player['성명'], '성별': player['성별']
            })
            
    final_df = pd.DataFrame(final_roster)
    
    # ★ 추가된 로직: 청, 백, 홍, 황 순서대로 정렬하기 ★
    # 1) 구장 순서를 1, 2, 3, 4로 매핑
    final_df['구장_순서'] = final_df['출발홀'].str[0].map({'청': 1, '백': 2, '홍': 3, '황': 4})
    # 2) 홀 번호를 추출해서 숫자로 변환
    final_df['홀_번호'] = final_df['출발홀'].str.extract(r'(\d+)홀').astype(int)
    
    # 3) 정렬: 구장 순서 -> 홀 번호 -> 타순 순으로 오름차순 정렬
    final_df = final_df.sort_values(by=['구장_순서', '홀_번호', '타순']).reset_index(drop=True)
    
    # 4) 사용이 끝난 임시 열(구장_순서, 홀_번호) 삭제
    final_df = final_df.drop(columns=['구장_순서', '홀_번호'])
    
    return final_df

# --- 웹사이트 화면 구성 ---
st.set_page_config(page_title="그라운드골프 조편성 프로그램", layout="wide")

st.title("⛳ 전국그라운드골프대회 자동 조편성 시스템")
st.markdown("엑셀 명단을 업로드하면 동일 지역 금지, 여성 필수 포함 등의 규칙을 적용하여 자동으로 조를 편성합니다. **(결과는 청·백·홍·황 구장 순서로 정렬되어 출력됩니다.)**")

with st.sidebar:
    st.header("⚙️ 대회 규정 설정")
    holes = st.radio("출발홀 수 선택", (6, 7, 8), index=2)
    players = st.radio("1조당 최대 인원", (6, 7, 8), index=0)
    st.info("💡 엑셀 파일은 1행에 '지역', '성명', '성별' 열이 있어야 합니다.")

uploaded_file = st.file_uploader("참가선수명단 엑셀 파일(.xlsx)을 올려주세요.", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()
        
        if not {'지역', '성명', '성별'}.issubset(df.columns):
            st.error("❌ 엑셀 파일에 '지역', '성명', '성별' 열이 모두 포함되어 있는지 확인해 주세요.")
        else:
            st.success(f"✅ 총 {len(df)}명의 선수 명단을 성공적으로 불러왔습니다!")
            
            if st.button("🚀 자동 조 편성 실행", type="primary"):
                with st.spinner("최적의 배치를 계산 중입니다..."):
                    
                    final_df = assign_teams_and_orders(df, holes_per_field=holes, players_per_team=players)
                    
                    st.subheader("🎉 편성 완료 (청 ➔ 백 ➔ 홍 ➔ 황 순서 정렬)")
                    st.dataframe(final_df, use_container_width=True)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        final_df.to_excel(writer, index=False, sheet_name='조편성결과')
                    processed_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 최종 조편성 엑셀 파일 다운로드",
                        data=processed_data,
                        file_name="제18회_대한체육회장기_배치결과_구장별정렬.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")