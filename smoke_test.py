"""자격증명 없이 Playwright + 로그인 페이지 셀렉터만 점검하는 스모크 테스트."""
from playwright.sync_api import sync_playwright
import pp_selectors as S

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    print(f"접속: {S.LOGIN_URL}")
    page.goto(S.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)
    print("페이지 타이틀:", page.title())

    for label, sel in [
        ("아이디칸", S.ID_SELECTORS[0]),
        ("비번칸", S.PW_SELECTORS[0]),
        ("로그인버튼", S.LOGIN_BUTTON_SELECTORS[0]),
        ("RSA지수(hidden)", "#RSAExponent"),
    ]:
        loc = page.locator(sel).first
        cnt = loc.count()
        print(f"  {label:12s} {sel:18s} -> {'찾음' if cnt else '없음!!'}")

    browser.close()
    print("스모크 테스트 완료")
