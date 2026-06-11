import streamlit as st
import pandas as pd
import numpy as np
import io
import traceback

st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

try:
    # ==========================================
    # [기능 1] 대진표 초고속 편성 로직 (인원 개별 설정 적용)
    # ==========================================
    def assign_teams_and_orders(df, holes_per_field=8, p_cnt_indiv=6, p_cnt_team=6, match_type="개인전"):
        players = df.to_dict('records')
        
        def distribute_players(target_players, target_teams, p_cnt):
            if not target_players: return
            r_counts = pd.Series([p['지역'] for p in target_players]).value_counts().to_dict()
            target_players.sort(key=lambda x: (r_counts.get(x['지역'], 0), x['지역']), reverse=True)
            
            for p in target_players:
                allowed = [t for t in target_teams if len(t) < p_cnt] or target_teams
                best_team = min(allowed, key=lambda t: (
                    sum(1 for x in t if x['이름'] == p['이름']),
                    sum(1 for x in t if x['지역'] == p['지역']),
                    sum(1 for x in t if x['성별'] == p['성별']),
                    len(t)
                ))
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
            
            team_teams_cnt = (len(team_players) + p_cnt_team - 1) // p_cnt_team if team_players else 0
            indiv_teams_cnt = (len(indiv_players) + p_cnt_indiv - 1) // p_cnt_indiv if indiv_players else 0
            
            team_teams = [[] for _ in range(team_teams_cnt)]
            indiv_teams = [[] for _ in range(indiv_teams_cnt)]
            
            distribute_players(team_players, team_teams, p_cnt_team)
            distribute_players(indiv_players, indiv_teams, p_cnt_indiv)
            
            assign_orders(team_teams, p_cnt_team)
            assign_orders(indiv_teams, p_cnt_indiv)
            
            teams = team_teams + indiv_teams
            num_teams = len(teams)
        else:
            current_p_cnt = p_cnt_team if match_type == "단체전" else p_cnt_indiv
            num_teams = (len(players) + current_p_cnt - 1) // current_p_cnt
            teams = [[] for _ in range(num_teams)]
            
            distribute_players(players, teams, current_p_cnt)
            assign_orders(teams, current_p_cnt)

        fields = ['청', '백', '홍', '황']
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
                    '_r': round_id, '_f': f_idx, '_h': hole
                })
                
        res_df = pd.DataFrame(final_roster).sort_values(by=['_r', '_f', '_h', '타순']).reset_index(drop=True)
        return res_df.drop(columns=['_r', '_f', '_h']), num_teams

    # ==========================================
    # [기능 2] 인쇄용 대진표 엑셀 출력
    # ==========================================
    def create_print_excel(df, match_type, holes_cnt):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            wb = writer.book
            head_fmt = wb.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1, 'align': 'center'})
            cell_fmt = wb.add_format({'border': 1, 'align': 'center'})
            
            for r_name in sorted(df['경기'].unique()):
                r_df = df[df['경기'] == r_name]
                for f_name in ['청', '백', '홍', '황']:
                    f_df = r_df[r_df['구장'] == f_name]
                    if f_df.empty: continue
                    
                    ws = wb.add_worksheet(f"{r_name}_{f_name}구장")
                    ws.set_column('A:O', 11)
                    ws.write(0, 0, f"제18회 대한체육회장배 {match_type} 대진표 ({r_name} {f_name}구장)", wb.add_format({'bold': True, 'font_size': 14}))
                    
                    row = 3
                    for h in range(1, holes_cnt + 1, 2):
                        h1_data, h2_data = f_df[f_df['홀'] == h], f_df[f_df['홀'] == h+1]
                        heads = ['홀', '타순', '부문', '지역', '이름', '성별', '심판']
                        
                        for c, text in enumerate(heads):
                            ws.write(row, c, text, head_fmt)
                            ws.write(row, c+8, text, head_fmt)
                        row += 1
                        
                        for i in range(max(len(h1_data), len(h2_data), 6)):
                            if i < len(h1_data):
                                p = h1_data.iloc[i]
                                ws.write_row(row+i, 0, [h if i==0 else "", p['타순'], p['부문'], p['지역'], p['이름'], p['성별'], ""], cell_fmt)
                            if i < len(h2_data):
                                p = h2_data.iloc[i]
                                ws.write_row(row+i, 8, [h+1 if i==0 else "", p['타순'], p['부문'], p['지역'], p['이름'], p['성별'], ""], cell_fmt)
                        row += max(len(h1_data), len(h2_data), 6) + 1
        return output.getvalue()

    # ==========================================
    # [기능 3] 명단 데이터 스캔 및 정제 통합 함수
    # ==========================================
    def process_raw_data(df_raw, default_category):
        if df_raw is None or df_raw.empty: return None, "데이터가 비어있습니다."
        
        header_idx = next((i for i, r in df_raw.iterrows() if any(x in ''.join(map(str, r)) for x in ['이름', '성명', '선수명'])), -1)
        if header_idx == -1:
            return None, "❌ 명단에서 [이름] 또는 [성명] 항목을 찾을 수 없습니다."
        
        df_raw.columns = df_raw.iloc[header_idx].astype(str).str.replace(r"\s+", "", regex=True)
        df_raw = df_raw.iloc[header_idx+1:].loc[:, ~df_raw.columns.duplicated()].reset_index(drop=True)
        
        rename_map = {'성명':'이름', '선수명':'이름', '소속':'지역', '시군구':'지역', '클럽':'지역', '남여':'성별'}
        df_raw.rename(columns=rename_map, inplace=True)
        
        if '이름' not in df_raw.columns or '지역' not in df_raw.columns:
            return None, "❌ 명단에 [이름]과 [지역] 열이 모두 필요합니다."
        
        for col in ['지역', '이름']:
            df_raw[col] = df_raw[col].astype(str).str.strip().replace(r'^\s*$', np.nan, regex=True).replace(['nan', 'None', 'NaN'], np.nan)
        df_clean = df_raw.dropna(subset=['지역', '이름']).copy()
        
        df_clean['성별'] = df_clean.get('성별', '남').fillna('남').astype(str).str.strip().str[0].apply(lambda x: '여' if x == '여' else '남')
        df_clean['부문'] = default_category
        
        return df_clean[['지역', '이름', '성별', '부문']], ""

    def load_gsheet(url):
        if not url: return None
        if "/d/" in url:
            doc_id = url.split("/d/")[1].split("/")[0]
            gid = url.split("gid=")[1].split("&")[0] if "gid=" in url else "0"
            return pd.read_csv(f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}", header=None)
        return None

    # ==========================================
    # [메인 화면 UI]
    # ==========================================

    # 💡 [핵심] 위원장님이 올려주신 새 로고 파일 적용 완료!
    _, logo_col, _ = st.columns([1, 1.5, 1])
    with logo_col:
        try:
            st.image("edited-image.jpg", width=350)
        except FileNotFoundError:
            st.error("⚠️ 로고 이미지 파일('edited-image.jpg')을 코드가 있는 폴더 안에서 찾을 수 없습니다. 파일을 확인해 주세요.")

    st.title("그라운드골프 대진표 편성 시스템")
    
    # 💡 [핵심] 단체전 / 개인전 조당 인원을 개별적으로 설정하도록 분리!
    st.sidebar.title("⚙️ 편성 설정")
    m_type = st.sidebar.radio("편성 부문", ["개인전", "단체전", "통합 (단체전 ➔ 개인전 이어서)"])
    h_cnt = st.sidebar.radio("출발홀 수", [6, 7, 8], index=2)
    p_cnt_team = st.sidebar.radio("단체전 조당 인원", [6, 7, 8], index=0)
    p_cnt_indiv = st.sidebar.radio("개인전 조당 인원", [6, 7, 8], index=0)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 데이터 입력 방식")
    data_source = st.sidebar.radio("명단을 어디서 가져올까요?", ["엑셀 파일 업로드", "구글 시트 링크 연결"])
    
    df_clean = None
    
    if m_type == "통합 (단체전 ➔ 개인전 이어서)":
        st.info("💡 통합 편성입니다. **단체전 명단**과 **개인전 명단**을 각각 지정해 주세요.")
        
        df_raw_team, df_raw_indiv = None, None
        
        if data_source == "엑셀 파일 업로드":
            up_file = st.file_uploader("명단 엑셀 업로드", type=["xlsx"])
            if up_file:
                try:
                    xls = pd.ExcelFile(up_file)
                    t_idx = xls.sheet_names.index('단체전') if '단체전' in xls.sheet_names else 0
                    i_idx = xls.sheet_names.index('개인전') if '개인전' in xls.sheet_names else 0
                    
                    col1, col2 = st.columns(2)
                    with col1: sheet_team = st.selectbox("📂 [단체전] 명단 시트 선택", xls.sheet_names, index=t_idx)
                    with col2: sheet_indiv = st.selectbox("📂 [개인전] 명단 시트 선택", xls.sheet_names, index=i_idx)
                    
                    df_raw_team = pd.read_excel(up_file, sheet_name=sheet_team, header=None)
                    df_raw_indiv = pd.read_excel(up_file, sheet_name=sheet_indiv, header=None)
                except Exception as e:
                    st.error(f"엑셀 읽기 오류: {e}")
                    
        elif data_source == "구글 시트 링크 연결":
            col1, col2 = st.columns(2)
            with col1: url_team = st.text_input("🔗 [단체전] 구글 시트 링크")
            with col2: url_indiv = st.text_input("🔗 [개인전] 구글 시트 링크")
            
            if url_team and url_indiv:
                try:
                    df_raw_team = load_gsheet(url_team)
                    df_raw_indiv = load_gsheet(url_indiv)
                    if df_raw_team is not None and df_raw_indiv is not None:
                        st.success("✅ 단체전 및 개인전 시트 데이터 로드 성공!")
                except Exception as e:
                    st.error(f"❌ 구글 시트 로드 실패: {e}")
                    
        if df_raw_team is not None and df_raw_indiv is not None:
            clean_team, err_t = process_raw_data(df_raw_team, "단체전")
            clean_indiv, err_i = process_raw_data(df_raw_indiv, "개인전")
            
            if err_t: st.error(f"[단체전 명단 오류] {err_t}")
            elif err_i: st.error(f"[개인전 명단 오류] {err_i}")
            else:
                df_clean = pd.concat([clean_team, clean_indiv], ignore_index=True)
                
    else: 
        df_raw = None
        if data_source == "엑셀 파일 업로드":
            up_file = st.file_uploader("명단 엑셀 업로드", type=["xlsx"])
            if up_file:
                try:
                    xls = pd.ExcelFile(up_file)
                    selected_sheet = st.selectbox("📂 명단 시트 선택", xls.sheet_names)
                    df_raw = pd.read_excel(up_file, sheet_name=selected_sheet, header=None)
                except Exception as e:
                    st.error(f"엑셀 읽기 오류: {e}")
                    
        elif data_source == "구글 시트 링크 연결":
            gsheet_url = st.text_input("🔗 구글 시트 링크 (공유 권한 확인 필수)")
            if gsheet_url:
                try:
                    df_raw = load_gsheet(gsheet_url)
                    if df_raw is not None: st.success("✅ 구글 시트 데이터 로드 성공!")
                except Exception as e:
                    st.error(f"❌ 구글 시트 로드 실패: {e}")
                    
        if df_raw is not None:
            df_clean, err = process_raw_data(df_raw, m_type)
            if err: st.error(err)

    if df_clean is not None:
        try:
            dup_mask = df_clean.duplicated(subset=['이름'], keep=False)
            if dup_mask.any():
                df_clean.loc[dup_mask, '이름'] += "(" + df_clean.loc[dup_mask, '지역'] + ")"
                
            st.info(f"✨ 총 **{len(df_clean)}명** 데이터 스캔 완료! (동명이인 자동 분리 완료)")
            
            with st.expander("👉 정리된 전체 명단 확인 (클릭)"):
                df_show = df_clean[['지역', '이름', '성별', '부문']].reset_index(drop=True)
                df_show.index += 1
                st.dataframe(df_show, use_container_width=True)
            
            st.markdown("---")
            
            if st.button(f"🚀 {m_type} 생성 실행", use_container_width=True):
                # 💡 선택한 조당 인원(개인전, 단체전)을 각각 전달!
                res, t_cnt = assign_teams_and_orders(df_clean, h_cnt, p_cnt_indiv, p_cnt_team, m_type)
                
                st.subheader(f"✅ 편성 완료 (총 {t_cnt}조)")
                disp_cols = ['대진표', '경기', '팀', '구장', '홀', '타순', '부문', '지역', '이름']
                
                res_show = res[disp_cols].copy()
                res_show.index += 1
                st.dataframe(res_show, use_container_width=True)
                
                st.write("#### 💾 다운로드")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button("🖨️ 인쇄용 대진표 (격자형)", data=create_print_excel(res, m_type, h_cnt), file_name=f"{m_type}_대진표.xlsx", use_container_width=True)
                with col2:
                    buf = io.BytesIO()
                    res[disp_cols].to_excel(buf, index=False, sheet_name="검증용_명단")
                    st.download_button("📋 검증용 명단 (엑셀형)", data=buf.getvalue(), file_name=f"{m_type}_명단검증.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                
        except Exception as e:
            st.error(f"데이터 처리 오류: {e}")

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
    st.code(traceback.format_exc())