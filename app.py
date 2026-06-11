import streamlit as st
import pandas as pd
import numpy as np
import io
import random
import traceback

st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

# ==========================================
# [모듈 1] 데이터 스캔 및 정제 엔진
# ==========================================
def process_raw_data(df_raw, default_category):
    if df_raw is None or df_raw.empty: return None, "데이터가 비어있습니다."
    
    header_idx = next((i for i, r in df_raw.iterrows() if any(x in ''.join(map(str, r)) for x in ['이름', '성명', '선수명'])), -1)
    if header_idx == -1: return None, "❌ 명단에서 [이름] 또는 [성명] 항목을 찾을 수 없습니다."
    
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

# ==========================================
# [모듈 2] 대진표 편성 엔진
# ==========================================
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
        
        distribute_players(team_players, team_teams, p_cnt_team)
        distribute_players(indiv_players, indiv_teams, p_cnt_indiv)
        assign_orders(team_teams, p_cnt_team)
        assign_orders(indiv_teams, p_cnt_indiv)
        
        teams = team_teams + indiv_teams
    else:
        current_p_cnt = p_cnt_team if match_type == "단체전" else p_cnt_indiv
        teams = [[] for _ in range((len(players) + current_p_cnt - 1) // current_p_cnt)]
        distribute_players(players, teams, current_p_cnt)
        assign_orders(teams, current_p_cnt)

    fields = ['청', '백', '홍', '황']
    final_roster = []
    
    for idx, team in enumerate(teams):
        field_name = fields[idx % 4]
        hole = (idx // 4) % holes_per_field + 1
        round_id = (idx // (4 * holes_per_field)) + 1
        for p in team:
            final_roster.append({
                '경기': f"{round_id}부", '구장': field_name, '홀': hole, '팀': f"{idx+1}조", 
                '타순': p['타순'], '대진표': f"{field_name} {hole} {p['타순']}",
                '부문': p.get('부문', match_type), '지역': p['지역'], '이름': p['이름'], '성별': p['성별'],
                '_r': round_id, '_f': idx % 4, '_h': hole
            })
            
    res_df = pd.DataFrame(final_roster).sort_values(by=['_r', '_f', '_h', '타순']).reset_index(drop=True)
    return res_df.drop(columns=['_r', '_f', '_h']), len(teams)

# ==========================================
# [모듈 3] 인쇄용 엑셀 출력 엔진
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
# [모듈 4] UI 파일 입력 도우미
# ==========================================
def load_data_ui(label, source_type):
    df_raw = None
    if source_type == "엑셀 파일 업로드":
        up_file = st.file_uploader(f"📂 [{label}] 명단 엑셀 업로드", type=["xlsx"], key=f"file_{label}")
        if up_file:
            try:
                xls = pd.ExcelFile(up_file)
                sheet = st.selectbox(f"📋 [{label}] 시트 선택", xls.sheet_names, key=f"sheet_{label}")
                df_raw = pd.read_excel(up_file, sheet_name=sheet, header=None)
            except Exception as e:
                st.error(f"엑셀 파일 읽기 오류: {e}")
                
    elif source_type == "구글 시트 링크 연결":
        url = st.text_input(f"🔗 [{label}] 구글 시트 링크", key=f"url_{label}")
        if url and "/d/" in url:
            try:
                doc_id = url.split("/d/")[1].split("/")[0]
                gid = url.split("gid=")[1].split("&")[0] if "gid=" in url else "0"
                df_raw = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}", header=None)
                st.success(f"✅ [{label}] 구글 시트 로드 성공!")
            except Exception as e:
                st.error(f"❌ 구글 시트 로드 실패: {e}")
    return df_raw

# ==========================================
# [메인 화면 실행부]
# ==========================================
try:
    # 로고 적용
    _, logo_col, _ = st.columns([1, 1.5, 1])
    with logo_col:
        try: st.image("Gemini_Generated_Image_yeu46iyeu46iyeu4.png", width=350)
        except: pass

    st.title("그라운드골프 대진표 편성 시스템")
    
    st.sidebar.title("⚙️ 편성 설정")
    m_type = st.sidebar.radio("편성 부문", ["개인전", "단체전", "통합 (단체전 ➔ 개인전 이어서)"])
    h_cnt = st.sidebar.radio("출발홀 수", [6, 7, 8], index=2)
    p_cnt_team = st.sidebar.radio("단체전 조당 인원", [6, 7, 8], index=0)
    p_cnt_indiv = st.sidebar.radio("개인전 조당 인원", [6, 7, 8], index=0)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 데이터 입력 방식")
    # 💡 CSV 옵션을 완전히 제거하고 "엑셀 파일 업로드"로 되돌림
    data_source = st.sidebar.radio("명단 가져오기 방식", ["엑셀 파일 업로드", "구글 시트 링크 연결"])
    
    df_clean = None
    
    if m_type == "통합 (단체전 ➔ 개인전 이어서)":
        st.info("💡 통합 편성: **단체전 명단**과 **개인전 명단**을 각각 입력해 주세요.")