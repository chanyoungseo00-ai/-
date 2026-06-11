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
        
        players = working_df.to_dict('records')
        
        if match_type == "통합 (단체전 ➔ 개인전 이어서)":
            team_players = [p for p in players if '단체' in str(p.get('부문', ''))]
            indiv_players = [p for p in players if '단체' not in str(p.get('부문', ''))]
            
            num_team_teams = (len(team_players) + players_per_team - 1) // players_per_team if len(team_players) > 0 else 0
            teams = [[] for _ in range(num_team_teams)]
            
            def place_players(target_players, target_teams):
                females = [p for p in target_players if p['성별'] == '여']
                males = [p for p in target_players if p['성별'] == '남']
                r_counts = pd.Series([p['지역'] for p in target_players]).value_counts().to_dict()
                females.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
                males.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
                
                for p in females + males:
                    allowed = [t for t in target_teams if len(t) < players_per_team]
                    if not allowed: allowed = target_teams
                    best_team = min(allowed, key=lambda t: (
                        sum(1 for x in t if x['이름'] == p['이름']),
                        sum(1 for x in t if x['지역'] == p['지역']),
                        sum(1 for x in t if x['성별'] == p['성별']),
                        len(t)
                    ))
                    best_team.append(p)
            
            place_players(team_players, teams)
            
            total_players = len(players)
            total_teams_needed = (total_players + players_per_team - 1) // players_per_team
            while len(teams) < total_teams_needed:
                teams.append([])
                
            place_players(indiv_players, teams)
            num_teams = total_teams_needed
            
        else:
            num_teams = (len(players) + players_per_team - 1) // players_per_team
            teams = [[] for _ in range(num_teams)]
            
            females = [p for p in players if p['성별'] == '여']
            males = [p for p in players if p['성별'] == '남']
            
            r_counts = pd.Series([p['지역'] for p in players]).value_counts().to_dict()
            females.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
            males.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
            
            for p in females + males:
                allowed = [t for t in teams if len(t) < players_per_team]
                if not allowed: allowed = teams
                
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
            
            r_name = f"{round_id}부"
                
            for p in team:
                final_roster.append({
                    '경기': r_name,
                    '구장': field_name, 
                    '홀': hole, 
                    '팀': f"{idx+1}조", 
                    '타순': p['타순'], 
                    '대진표': f"{field_name} {hole} {p['타순']}",
                    '부문': p.get('부문', match_type),
                    '지역': p['지역'], 
                    '이름': p['이름'], 
                    '성별': p['성별'],
                    '_r': round_id, 
                    '_f': f_idx, 
                    '_h': hole
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
            
            rounds = sorted(df['경기'].unique())
            for r_name in rounds:
                r_df = df[df['경기'] == r_name]
                
                for f_name in ['청', '백', '홍', '황']:
                    f_df = r_df[r_df['구장'] == f_name]
                    if f_df.empty: continue
                    
                    sheet_name = f"{r_name}_{f_name}구장"
                    worksheet = workbook.add_worksheet(sheet_name)
                    worksheet.set_column('A:O', 11)
                    
                    title_text = f"제18회 대한체육회장배 {match_type} 대진표 ({r_name} {f_name}구장)"
                    worksheet.write(0, 0, title_text, workbook.add_format({'bold': True, 'font_size': 14}))
                    
                    row = 3
                    for h in range(1, holes_cnt + 1, 2):
                        h1_data = f_df[f_df['홀'] == h]
                        h2_data = f_df[f_df['홀'] == h+1]
                        
                        heads = ['홀', '타순', '부문', '지역', '이름', '성별', '심판']
                        for c, text in enumerate(heads):
                            worksheet.write(row, c, text, header_fmt)
                            worksheet.write(row, c+8, text, header_fmt)
                        row += 1
                        
                        max_len = max(len(h1_data), len(h2_data), 6)
                        for i in range(max_len):
                            if i < len(h1_data):
                                p = h1_data.iloc[i]
                                val_h = h if i == 0 else ""
                                worksheet.write(row+i, 0, val_h, cell_fmt)
                                worksheet.write(row+i, 1, p['타순'], cell_fmt)
                                worksheet.write(row+i, 2, p['부문'], cell_fmt)
                                worksheet.write(row+i, 3, p['지역'], cell_fmt)
                                worksheet.write(row+i, 4, p['이름'], cell_fmt)
                                worksheet.write(row+i, 5, p['성별'], cell_fmt)
                                worksheet.write(row+i, 6, "", cell_fmt)
                            if i < len(h2_data):
                                p = h2_data.iloc[i]
                                val_h2 = h+1 if i == 0 else ""
                                worksheet.write(row+i, 8, val_h2, cell_fmt)
                                worksheet.write(row+i, 9, p['타순'], cell_fmt)
                                worksheet.write(row+i, 10, p['부문'], cell_fmt)
                                worksheet.write(row+i, 11, p['지역'], cell_fmt)
                                worksheet.write(row+i, 12, p['이름'], cell_fmt)
                                worksheet.write(row+i, 13, p['성별'], cell_fmt)
                                worksheet.write(row+i, 14, "", cell_fmt)
                        row += max_len + 1
        return output.getvalue()

    # ==========================================
    # [메인 화면 UI]
    # ==========================================
    st.title("⛳ 그라운드골프 대진표 편성 시스템")
    
    st.sidebar.title("⚙️ 편성 설정")
    m_type = st.sidebar.radio("편성 부문", ["개인전", "단체전", "통합 (단체전 ➔ 개인전 이어서)"])
    h_cnt = st.sidebar.radio("출발홀 수", [6, 7, 8], index=2)
    p_cnt = st.sidebar.radio("조당 인원", [6, 7, 8], index=0)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 데이터 입력 방식")
    data_source = st.sidebar.radio("명단을 어디서 가져올까요?", ["엑셀 파일 업로드", "구글 시트 링크 연결"])
    
    df_raw = None
    
    if data_source == "엑셀 파일 업로드":
        up_file = st.file_uploader("선수 명단 엑셀 업로드", type=["xlsx"])
        if up_file:
            try:
                xls = pd.ExcelFile(up_file)
                sheet_names = xls.sheet_names
                selected_sheet = st.selectbox("📂 명단이 들어있는 엑셀 시트를 정확히 선택하세요", sheet_names)
                df_raw = pd.read_excel(up_file, sheet_name=selected_sheet, header=None)
            except Exception as e:
                st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
                
    elif data_source == "구글 시트 링크 연결":
        st.info("💡 **안내:** 구글 시트 우측 상단의 [공유] 버튼을 누르고 **'링크가 있는 모든 사용자가 볼 수 있음'**으로 변경한 후 주소를 복사하세요.")
        gsheet_url = st.text_input("🔗 구글 시트 링크 (URL) 붙여넣기")
        
        if gsheet_url:
            try:
                if "/d/" in gsheet_url:
                    doc_id = gsheet_url.split("/d/")[1].split("/")[0]
                    gid = "0"
                    if "gid=" in gsheet_url:
                        gid = gsheet_url.split("gid=")[1].split("&")[0]
                    
                    csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
                    df_raw = pd.read_csv(csv_url, header=None)
                    st.success("✅ 구글 시트 데이터를 성공적으로 불러왔습니다!")
                else:
                    st.error("❌ 올바른 구글 시트 주소가 아닙니다. 링크를 다시 확인해 주세요.")
            except Exception as e:
                st.error(f"❌ 구글 시트를 불러오지 못했습니다. 공유 설정이 제대로 열려 있는지 확인해 주세요. (오류: {e})")

    if df_raw is not None:
        try:
            header_idx = -1
            for i, row in df_raw.iterrows():
                row_str = row.astype(str).str.replace(" ", "").str.replace("\n", "").tolist()
                if '이름' in row_str or '성명' in row_str or '선수명' in row_str:
                    header_idx = i
                    break
            
            if header_idx == -1:
                st.error("❌ 데이터를 불러왔으나 [이름] 또는 [성명] 항목을 찾을 수 없습니다.")
            else:
                raw_cols = df_raw.iloc[header_idx].astype(str).str.replace(" ", "").str.replace("\n", "")
                df_raw.columns = raw_cols
                df_raw = df_raw.iloc[header_idx+1:].reset_index(drop=True)
                
                df_raw = df_raw.loc[:, ~df_raw.columns.duplicated()]
                
                if '성명' in df_raw.columns: df_raw = df_raw.rename(columns={'성명': '이름'})
                if '선수명' in df_raw.columns: df_raw = df_raw.rename(columns={'선수명': '이름'})
                if '소속' in df_raw.columns: df_raw = df_raw.rename(columns={'소속': '지역'})
                if '시군구' in df_raw.columns: df_raw = df_raw.rename(columns={'시군구': '지역'})
                if '클럽' in df_raw.columns: df_raw = df_raw.rename(columns={'클럽': '지역'})
                if '남여' in df_raw.columns: df_raw = df_raw.rename(columns={'남여': '성별'})
                if '구분' in df_raw.columns: df_raw = df_raw.rename(columns={'구분': '부문'})
                if '종목' in df_raw.columns: df_raw = df_raw.rename(columns={'종목': '부문'})
                if '참가부문' in df_raw.columns: df_raw = df_raw.rename(columns={'참가부문': '부문'})
                
                if '이름' not in df_raw.columns or '지역' not in df_raw.columns:
                    st.error("❌ 명단에 [이름] 열과 [지역(소속)] 열이 모두 있어야 합니다.")
                else:
                    df_raw['지역'] = df_raw['지역'].astype(str).str.strip()
                    df_raw['지역'] = df_raw['지역'].replace(r'^\s*$', np.nan, regex=True)
                    df_raw['지역'] = df_raw['지역'].replace(['nan', 'None', 'NaN'], np.nan)
                    
                    df_raw['이름'] = df_raw['이름'].astype(str).str.strip()
                    df_raw['이름'] = df_raw['이름'].replace(r'^\s*$', np.nan, regex=True)
                    df_raw['이름'] = df_raw['이름'].replace(['nan', 'None', 'NaN'], np.nan)
                        
                    cols_to_keep = ['지역', '이름', '성별']
                    if '부문' in df_raw.columns: cols_to_keep.append('부문')
                    
                    df_clean = df_raw.dropna(subset=['지역', '이름'])[cols_to_keep].copy()
                    
                    if '성별' not in df_clean.columns: df_clean['성별'] = '남'
                    df_clean['성별'] = df_clean['성별'].fillna('남')
                    
                    if m_type == "통합 (단체전 ➔ 개인전 이어서)":
                        if '부문' not in df_clean.columns:
                            df_clean['부문'] = df_clean.groupby('지역').cumcount().apply(lambda x: '단체' if x < 6 else '개인')
                        else:
                            df_clean['부문'] = df_clean['부문'].fillna('개인')
                    else:
                        df_clean['부문'] = m_type
                    
                    df_clean = df_clean[['지역', '이름', '성별', '부문']]
                    
                    dup_names = df_clean.duplicated(subset=['이름'], keep=False)
                    if dup_names.any():
                        df_clean.loc[dup_names, '이름'] = df_clean.loc[dup_names, '이름'] + "(" + df_clean.loc[dup_names, '지역'] + ")"
                        
                    st.info(f"✨ 총 **{len(df_clean)}명** 스캔 완료! (동명이인 자동 분리 완료)")
                    
                    with st.expander("👉 전체 명단 꼼꼼히 확인하기 (클릭)"):
                        # 💡 [핵심] 0번이 아닌 1번부터 순번(Index) 시작!
                        df_show = df_clean.reset_index(drop=True)
                        df_show.index = df_show.index + 1
                        st.dataframe(df_show, use_container_width=True)
                    
                    st.markdown("---")
                    
                    if st.button(f"🚀 {m_type} 대진표 생성 실행", use_container_width=True):
                        res, t_cnt, order_stats = assign_teams_and_orders(df_clean, h_cnt, p_cnt, m_type)
                        
                        res['성별'] = ""
                        
                        st.subheader(f"✅ {m_type} 편성 완료 (총 {t_cnt}개 조)")
                        
                        display_cols = ['대진표', '경기', '팀', '구장', '홀', '타순', '부문', '지역', '이름']
                        
                        # 💡 [핵심] 결과 창의 순번(Index)도 1번부터 시작!
                        res_show = res[display_cols].copy()
                        res_show.index = res_show.index + 1
                        st.dataframe(res_show, use_container_width=True)
                        
                        st.markdown("---")
                        st.write("#### 💾 결과물 다운로드")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            print_excel = create_print_excel(res, m_type, h_cnt)
                            st.download_button(
                                label="🖨️ 인쇄용 공식 대진표 다운로드 (격자형)", 
                                data=print_excel, 
                                file_name=f"{m_type}_최종_대진표.xlsx",
                                use_container_width=True
                            )
                        
                        with col2:
                            summary_excel = io.BytesIO()
                            res[display_cols].to_excel(summary_excel, index=False, sheet_name="검증용_명단")
                            st.download_button(
                                label="📋 검증용 명단 다운로드 (엑셀 원본 형태)", 
                                data=summary_excel.getvalue(), 
                                file_name=f"{m_type}_명단_검증표.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                        
        except Exception as e:
            st.error(f"명단을 처리하는 도중 문제가 발생했습니다: {e}")

except Exception as e:
    st.error(f"🚨 프로그램 구동 중 치명적인 에러가 발생했습니다: {e}")
    st.code(traceback.format_exc())