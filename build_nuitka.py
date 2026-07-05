# -*- coding: utf-8 -*-
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
NAME = "Jw2Launcher_v1.1.3"

DATA_FILES = [
    ("icon.ico", "icon.ico"), ("kakaotalk.ico", "kakaotalk.ico"), ("naver.ico", "naver.ico"),
    ("discord.ico", "discord.ico"), ("radmin.ico", "radmin.ico"),
    ("Jw2_15(old).trc", "Jw2_15(old).trc"), ("Jw2_15(new).trc", "Jw2_15(new).trc"),
    ("개발 참조 내용/마법_사용조건.json", "마법_사용조건.json"),   # 루트로(코드 폴백 검색)
]
DATA_DIRS = [("ico", "ico"), ("newico", "newico"), ("skillico", "skillico"), ("fonts", "fonts")]

args = [
    sys.executable, "-m", "nuitka", "launcher.py",
    "--onefile",
    "--windows-console-mode=disable",          # noconsole
    "--enable-plugin=tk-inter",                # tkinter
    "--windows-icon-from-ico=icon.ico",
    "--output-dir=dist_nuitka",
    f"--output-filename={NAME}.exe",
    "--include-module=JW2_Ranker_Monitor",     # 관전 모니터(런처가 import)
    "--include-module=jwar2_replay_result",    # 리플 승패판정
    "--nofollow-import-to=jw2inject",          # 제거된 기능 제외
    "--include-package=customtkinter",         # 런처 UI
    "--include-package-data=customtkinter",    # 테마 json
    "--assume-yes-for-downloads",              # MinGW C컴파일러 자동 다운로드 확인
    "--remove-output",                         # 중간 빌드파일 정리
]
for s, d in DATA_FILES:
    if os.path.exists(s):
        args.append(f"--include-data-files={s}={d}")
    else:
        print("!! 자산 없음(건너뜀):", s)
for s, d in DATA_DIRS:
    if os.path.exists(s):
        args.append(f"--include-data-dir={s}={d}")

print("Nuitka 명령:\n", " ".join(a if " " not in a else f'"{a}"' for a in args), "\n")
r = subprocess.run(args)
print("\n=== Nuitka 종료코드:", r.returncode, "===")
if r.returncode == 0:
    print("빌드 완료 → dist_nuitka/%s.exe" % NAME)
