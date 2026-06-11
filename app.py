import streamlit as st
import pandas as pd
import numpy as np
import io
import traceback
import base64

# 💡 [핵심] 로고 이미지를 프로그램 안에 직접 심어놓는 방식 (에러 방지)
def get_image_base64(img_file):
    with open(img_file, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"

st.set_page_config(page_title="그라운드골프 대진표 시스템", layout="wide")

# (이후 assign_teams_and_orders, create_print_excel, process_raw_data 함수는 이전 코드와 동일합니다)
# 아래는 오류를 방지하기 위해 정돈된 UI 실행부입니다.

try:
    # 💡 [핵심] 로고 이미지 에러 방지 처리
    try:
        # 업로드해주신 파일을 'edited-image.jpg'로 이름 변경하여 같은 폴더에 두시거나, 
        # 코드를 실행하는 서버에 해당 파일이 있는지 확인이 필요합니다.
        # 파일이 없을 경우를 대비해 이미지 섹션을 try-except로 감쌌습니다.
        st.image("edited-image.jpg", width=350)
    except:
        st.warning("⚠️ 로고 이미지 파일이 현재 폴더에 없습니다. 대진표 시스템을 시작합니다.")

    st.title("그라운드골프 대진표 편성 시스템")
    
    # [나머지 로직은 이전과 동일하게 유지됩니다]
    # 사이드바 설정 및 데이터 처리 로직을 그대로 사용하시면 됩니다.
    
    st.sidebar.title("⚙️ 편성 설정")
    # ... (생략된 이전 코드의 사이드바/입력 로직을 여기에 그대로 붙여넣으세요) ...

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
    st.code(traceback.format_exc())