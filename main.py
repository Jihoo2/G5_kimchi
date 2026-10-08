"""
[실행 진입점] 조각김치 이물검출 라벨링 도구

실행 방법 (이 파일이 있는 폴더에서):
    source .venv/bin/activate
    pip install -r requirements.txt      # 처음 한 번
    python3 main.py

이 파일은 '실행'만 담당한다. 기능별 코드 위치는 docs/의사코드.md 참고.
    root 창 생성 → 폰트·스타일 적용 → 로그인 화면 표시 → 이벤트 루프 시작
"""
import tkinter as tk

from src.auth.login import show_login
from src.ui.theme import setup_theme


def main() -> None:
    root = tk.Tk()          # 프로그램 전체에서 쓰는 단 하나의 창
    setup_theme(root)       # 한글 폰트, 버튼·표 스타일
    show_login(root)        # 로그인 화면 → 로그인하면 메인 화면으로 전환
    root.mainloop()         # 창이 닫힐 때까지 이벤트 처리


if __name__ == "__main__":
    main()
