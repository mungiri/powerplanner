"""파워플래너 페이지 URL/셀렉터 모음.

데이터 추출 셀렉터는 실제 페이지(메인화면.html)에서 확인한 확정값입니다.
로그인 폼 셀렉터만 후보로 시도합니다 (로그인 페이지 HTML 확보 시 정확히 고정 가능).
"""

# 로그인 페이지 (한전 통합 로그인)
LOGIN_URL = "https://pp.kepco.co.kr/intro.do"

# 로그인 후 스마트뷰 메인 (실시간/예상 요금이 표시됨)
SMARTVIEW_URL = "https://pp.kepco.co.kr/rm/rm0201.do?menu_id=O020101"

# --- 로그인 폼 (로그인화면.html 에서 확인한 확정값) ---
# 버튼 클릭 시 encript() 가 RSA 암호화 후 /login 으로 POST 한다 → 칸 채우고 버튼만 누르면 됨.
ID_SELECTORS = ["#RSA_USER_ID"]
PW_SELECTORS = ["#RSA_USER_PWD"]
LOGIN_BUTTON_SELECTORS = ["#intro_btn_indi"]

# --- 스마트뷰 메인의 요금/사용량 요소 (확정) ---
# JS(getRM0201.do 응답)가 채워넣으므로, 비어있지 않을 때까지 기다린 뒤 읽는다.
EL_TOTAL_CHARGE = "#TOTAL_CHARGE"                   # 실시간요금 (원)
EL_PREDICT_TOTAL_CHARGE = "#PREDICT_TOTAL_CHARGE"   # 예상요금 (원)
EL_USAGE = "#F_AP_QT"                               # 실시간 사용량 (kWh)
EL_PREDICT_USAGE = "#PREDICT_TOT"                   # 예상 사용량 (kWh)
EL_START_DT = "#START_DT"                           # 청구 시작일
EL_SELECT_DT = "#SELECT_DT"                         # 조회 기준일
EL_END_DT = "#END_DT"                               # 청구 종료일
