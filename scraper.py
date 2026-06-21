"""Playwright 로 파워플래너에 로그인하고 실시간/예상 요금을 읽어온다."""
import os
import re
import pathlib
from datetime import datetime

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

import pp_selectors as S

CAPTURE_DIR = pathlib.Path(__file__).parent / "capture"


def _try_fill(page: Page, candidates, value: str) -> bool:
    for sel in candidates:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                el.fill(value, timeout=3000)
                return True
        except Exception:
            continue
    return False


def _try_click(page: Page, candidates) -> bool:
    for sel in candidates:
        try:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_visible():
                el.click(timeout=3000)
                return True
        except Exception:
            continue
    return False


def _num(text):
    """'7,970 원' / '45.948kWh' → 숫자. 정수는 int, 소수는 float."""
    if text is None:
        return None
    m = re.search(r"[\d,]+(?:\.\d+)?", text)
    if not m:
        return None
    val = m.group(0).replace(",", "")
    return float(val) if "." in val else int(val)


def _read_text(page: Page, selector: str, timeout: int = 25000):
    """요소 텍스트가 '값이 채워질 때까지' 기다린 뒤 반환."""
    try:
        # JS가 숫자를 채워넣을 때까지 대기 (초기엔 비어있음)
        page.wait_for_function(
            "(sel) => { const e = document.querySelector(sel);"
            " return e && /\\d/.test(e.textContent); }",
            arg=selector,
            timeout=timeout,
        )
    except PWTimeout:
        pass
    try:
        el = page.locator(selector).first
        if el.count() > 0:
            return el.inner_text(timeout=3000).strip()
    except Exception:
        pass
    return None


def login_and_fetch(headless: bool = True, capture: bool = False):
    """로그인 후 요금 정보를 dict 로 반환.

    반환 예:
        {
          "total_charge": 7970, "predict_charge": 19757,
          "usage": 45.948, "predict_usage": 124.428,
          "period": "2026.06.11 ~ 2026.07.10", "as_of": "2026.06.21",
        }
    실패 시 RuntimeError.
    """
    kepco_id = os.getenv("KEPCO_ID")
    kepco_pw = os.getenv("KEPCO_PW")
    if not kepco_id or not kepco_pw:
        raise RuntimeError("KEPCO_ID / KEPCO_PW 가 .env 에 설정되어 있지 않습니다.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        )
        page = ctx.new_page()

        try:
            # 1) 로그인
            page.goto(S.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)

            if not _try_fill(page, S.ID_SELECTORS, kepco_id):
                _save_capture(page, "login_id_fail")
                raise RuntimeError(
                    "아이디 입력칸을 못 찾았습니다. capture/ 의 화면을 보고 "
                    "pp_selectors.py 의 ID_SELECTORS 를 수정하세요."
                )
            if not _try_fill(page, S.PW_SELECTORS, kepco_pw):
                _save_capture(page, "login_pw_fail")
                raise RuntimeError(
                    "비밀번호 입력칸을 못 찾았습니다. pp_selectors.py 의 PW_SELECTORS 를 수정하세요."
                )

            _try_click(page, S.LOGIN_BUTTON_SELECTORS)
            page.wait_for_timeout(3000)

            # 2) 스마트뷰 메인으로 이동
            page.goto(S.SMARTVIEW_URL, wait_until="domcontentloaded", timeout=30000)

            if capture:
                page.wait_for_timeout(4000)
                _save_capture(page, "after_login")

            # 3) JS 가 채운 요금 값 읽기
            total_txt = _read_text(page, S.EL_TOTAL_CHARGE)
            predict_txt = _read_text(page, S.EL_PREDICT_TOTAL_CHARGE)
            usage_txt = _read_text(page, S.EL_USAGE)
            predict_usage_txt = _read_text(page, S.EL_PREDICT_USAGE)
            start_dt = _read_text(page, S.EL_START_DT, timeout=5000)
            select_dt = _read_text(page, S.EL_SELECT_DT, timeout=5000)
            end_dt = _read_text(page, S.EL_END_DT, timeout=5000)

            total_charge = _num(total_txt)
            if total_charge is None:
                _save_capture(page, "charge_not_found")
                raise RuntimeError(
                    "요금(#TOTAL_CHARGE)을 읽지 못했습니다. 로그인이 실패했거나 "
                    "화면 구조가 바뀌었을 수 있습니다. capture/ 를 확인하세요."
                )

            return {
                "total_charge": total_charge,
                "predict_charge": _num(predict_txt),
                "usage": _num(usage_txt),
                "predict_usage": _num(predict_usage_txt),
                "period": f"{start_dt} ~ {end_dt}" if start_dt and end_dt else None,
                "as_of": select_dt,
            }
        finally:
            browser.close()


def _save_capture(page: Page, tag: str) -> None:
    CAPTURE_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = CAPTURE_DIR / f"{tag}_{ts}"
    try:
        page.screenshot(path=str(base) + ".png", full_page=True)
    except Exception:
        pass
    try:
        (pathlib.Path(str(base) + ".html")).write_text(page.content(), encoding="utf-8")
    except Exception:
        pass
    print(f"[capture] 저장됨: {base}.png / .html")
