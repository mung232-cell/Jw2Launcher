import os
import json
import subprocess
import time
import ctypes
import sys
import webbrowser
import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
import psutil
import math
import shutil
import multiprocessing  # [신규 추가] 관전 모니터를 독립된 프로세스로 실행하기 위함

# -------------------------------------------------------------------------
# 라이브러리 의존성 체크 및 초기화 구간
# -------------------------------------------------------------------------
try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("라이브러리 누락", "최신 UI를 위해 customtkinter 라이브러리가 필요합니다.\n터미널에 'pip install customtkinter'을 입력하십시오.")
    exit()

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pystray
    from pystray import MenuItem as item
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

CONFIG_FILE = "config.json"

# ── 자동 업데이트(GitHub 릴리스, 반자동) ──
APP_VERSION = "1.1.3"           # ★릴리스마다 이 값 + build_nuitka.py의 NAME 같이 올리기
GITHUB_REPO = "mung232-cell/Jw2Launcher"   # github.com/mung232-cell/Jw2Launcher (릴리스 태그와 비교)


def _res_dir():
    """번들된 읽기전용 자산 폴더(아이콘·BGM trc 등). PyInstaller=sys._MEIPASS, Nuitka/개발=이 스크립트 위치.
    (Nuitka는 sys._MEIPASS/sys.frozen 미설정 → dirname(__file__)이 임시추출폴더=번들자산 위치)."""
    return getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))


DDRAW_TEMPLATE = """[ddraw]
windowed={windowed}
fullscreen={fullscreen}
toggle_borderless={toggle_borderless}
{extra_res}boxing=false
fix_window_style=true
resizing=true
maintas=false
handlemouse=true
adjmouse=true
maxfps=-1
accuratetimers=false
singlecpu=true
renderer=opengl
vsync=false
shader=Bicubic
devmode=false
savesettings=1
keytogglefullscreen=0x0D
keytogglemaximize=0x22
keyunlockcursor1=0x09
keyunlockcursor2=0xA3
keyscreenshot=0
toggle_upscaled=false
d3d9_filter=2
border=true
maxgameticks=0
noactivateapp=false
resolutions=0
minfps=0
nonexclusive=false"""

def get_local_ip():
    """IP 주소 추출 (라드민 VPN의 26.x.x 대역을 최우선으로 탐색)"""
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        for ip in ips:
            if ip.startswith("26."):
                return ip
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_icon_path():
    """실행 파일 위치를 기반으로 icon.ico 파일의 절대 경로 탐색"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    icon_path = os.path.join(base_dir, "icon.ico")
    if os.path.exists(icon_path):
        return icon_path
        
    try:
        temp_path = os.path.join(_res_dir(), "icon.ico")
        if os.path.exists(temp_path):
            return temp_path
    except:
        pass
        
    return "icon.ico"

# -------------------------------------------------------------------------
# Custom UI 컴포넌트
# -------------------------------------------------------------------------
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        
    def enter(self, event=None):
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background="#1e212b", fg="#ffffff", relief='solid', borderwidth=1,
                         font=("Malgun Gothic", 10))
        label.pack(ipadx=5, ipady=3)
        
    def leave(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None

class CustomFontPicker(ctk.CTkFrame):
    """폰트 리스트를 실제 폰트 모양으로 보여주는 커스텀 스크롤 드롭다운"""
    def __init__(self, master, variable, values, command=None, width=140, height=28, **kwargs):
        super().__init__(master, width=width, height=height, fg_color="transparent", **kwargs)
        self.variable = variable
        self.values = values
        self.command = command
        
        self.btn = ctk.CTkButton(self, textvariable=self.variable, width=width, height=height,
                                 fg_color="#0f1115", hover_color="#3a71f0", border_color="#252833", 
                                 border_width=1, corner_radius=6, command=self.toggle)
        self.btn.pack(expand=True, fill="both")
        self.toplevel = None

    def toggle(self):
        if self.toplevel:
            self.close()
        else:
            self.open()

    def open(self):
        self.toplevel = tk.Toplevel(self.winfo_toplevel())
        self.toplevel.overrideredirect(True)
        self.toplevel.attributes('-topmost', True)
        
        x = self.btn.winfo_rootx()
        y = self.btn.winfo_rooty() + self.btn.winfo_height()
        w = max(self.btn.winfo_width(), 170)
        h = min(len(self.values)*32 + 10, 280)
        
        self.toplevel.geometry(f"{w}x{h}+{x}+{y}")
        
        container = ctk.CTkScrollableFrame(self.toplevel, bg_color="#1e212b", fg_color="#1e212b", corner_radius=0)
        container.pack(expand=True, fill="both")
        
        for f_name in self.values:
            lbl = tk.Label(container, text=f_name, font=(f_name, 11), bg="#1e212b", fg="#ffffff", pady=4, anchor="w", padx=10)
            lbl.pack(fill="x")
            lbl.bind("<Enter>", lambda e, l=lbl: l.configure(bg="#3a71f0"))
            lbl.bind("<Leave>", lambda e, l=lbl: l.configure(bg="#1e212b"))
            lbl.bind("<Button-1>", lambda e, val=f_name: self.select(val))
            
        self.toplevel.bind("<FocusOut>", lambda e: self.close())
        self.toplevel.focus_set()

    def select(self, val):
        self.variable.set(val)
        if self.command:
            self.command(val)
        self.close()

    def close(self):
        if self.toplevel:
            self.toplevel.destroy()
            self.toplevel = None

# -------------------------------------------------------------------------
# 통합 게임 오버레이 클래스 (모드별 독립 좌표 관리 적용)
# -------------------------------------------------------------------------
class JurassicLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Jurassic War2: The Ranker Launcer")
        self.root.geometry("560x660")  # [수정됨] 체크박스가 잘리지 않도록 세로 길이를 660으로 소폭 확장
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.icon_path = get_icon_path()
        if os.path.exists(self.icon_path):
            try:
                self.root.iconbitmap(self.icon_path)
            except:
                pass
        
        self.COLOR_BG = "#0b0c10"
        self.COLOR_PANEL = "#15171e"
        self.COLOR_BORDER = "#252833"
        self.COLOR_TEXT_MAIN = "#ffffff"
        self.COLOR_TEXT_SUB = "#8b92a5"
        self.COLOR_BTN_PRIMARY = "#3a71f0"
        self.COLOR_BTN_PRIMARY_HOVER = "#2d5bc4"
        self.COLOR_BTN_DARK = "#20232e"
        self.COLOR_BTN_DARK_HOVER = "#2a2d3b"
        self.COLOR_INPUT = "#0f1115"
        
        self.root.configure(fg_color=self.COLOR_BG)
        self.settings_win = None
        self.options_win = None
        self.help_win = None
        self.tray_icon = None
        self.spectator_proc = None

        # 완전히 독립된 모드별 좌표 변수로 교체
        self.config = {
            "path_hd": "", "path_vanilla": "", "path_editor": "", "path_replay": "",
            "ui_transparency": 1.0, "minimize_to_tray_on_launch": False, "close_on_launch": False, "always_minimize_to_tray": False,
            "window_resolution": "1600x900(추천)", "display_mode": "borderless",
            "bgm_mode": "TheRanker 확장판",
            "game_pos_x": 0, "game_pos_y": 30,
            # ★오버레이(관전) 설정 — 타이머/APM 제거, 관전 오버레이 설정으로 대체
            "spectator_overlay_auto": True,   # 관전 오버레이 자동 활성화(해제=관전·리플레이도 바닐라)
            "replay_hide_gauge": True,        # 리플레이 관전 시 게임 진행바(네이티브 게이지) 숨김
            # ★플레이어 색 커스텀(로컬 인메모리, 나만 적용) — me/enemy는 항상 hex
            "color_play_custom": False, "color_play_me": "#ff1414", "color_play_enemy": "#2038dc",
            "color_spec_custom": False, "color_spec_mode": "rb",
            "color_spec_p1": "#ff1414", "color_spec_p2": "#2038dc",
        }
        self.load_config()
        self.auto_detect_paths()
        self.root.attributes("-alpha", float(self.config.get("ui_transparency", 1.0)))
        self.build_ui()
        # ★런처 실행시 관전 오버레이 자동 실행(런처 종속). UI가 완전히 뜬 뒤 스폰.
        self.root.after(1000, self._autostart_spectator)
        self.root.after(2500, self._check_update)   # ★GitHub 새 버전 확인(반자동 업데이트)

    def _get_popup_geometry(self, width, height, offset=40):
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            return f"{width}x{height}+{x + offset}+{y + offset}"
        except:
            return f"{width}x{height}"

    def auto_detect_paths(self):
        # ★exe 실제폴더 탐지: PyInstaller(sys.frozen) + Nuitka(__compiled__) 모두 dirname(sys.executable).
        #   Nuitka는 sys.frozen 미설정 → 예전엔 __file__=임시추출폴더가 돼, 게임폴더에 exe를 둬도 자동감지 실패했음.
        if getattr(sys, 'frozen', False) or '__compiled__' in globals():
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        sub_dir = os.path.join(base_dir, "RankerOCPV_Win")
        search_dirs = [base_dir, sub_dir]
        
        defaults = {
            "path_hd": ["Rank1024.exe"],
            "path_vanilla": ["Ranker800.exe", "Ranker800"],
            "path_editor": ["MapEditor_개발자용.exe", "MapEditor_개발자용"],
            "path_replay": ["Replays"]
        }

        # ★이미 지정된 경로(사용자 직접지정 or 이전 자동감지)의 폴더도 검색 대상에 추가:
        #   높은해상도만 지정돼 있어도 같은 게임폴더의 나머지(기본해상도·맵에디터·리플레이)를 자동으로 잡음
        #   (exe/소스를 게임폴더 밖에서 실행하는 경우 대비).
        for _k in defaults:
            _v = self.config.get(_k, "")
            if _v and os.path.exists(_v):
                _d = _v if os.path.isdir(_v) else os.path.dirname(_v)
                if _d and _d not in search_dirs:
                    search_dirs.append(_d)

        updated = False
        for key, filenames in defaults.items():
            current_path = self.config.get(key, "")
            if not current_path or not os.path.exists(current_path):
                for d in search_dirs:
                    found = False
                    for fname in filenames:
                        candidate = os.path.join(d, fname)
                        if os.path.exists(candidate):
                            self.config[key] = candidate
                            updated = True
                            found = True
                            break
                    if found:
                        break
                        
        if updated:
            self.save_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except: 
                pass

    def save_config(self):
        try:
            self.config["display_mode"] = self.display_var.get()
            if hasattr(self, 'bgm_var'):
                self.config["bgm_mode"] = self.bgm_var.get()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except:
            pass

    # ══ 자동 업데이트(반자동): GitHub 릴리스 확인 → 새 exe 다운로드 → 폴더 열고 "실행하세요" ══
    #   ★exe가 스스로를 교체하지 않음(백신 오탐 최소). 유저가 받은 새 exe를 직접 실행하면 적용.
    def _exe_base_dir(self):
        """현재 exe(또는 소스)가 있는 폴더 — 새 exe를 여기에 받음."""
        if getattr(sys, 'frozen', False) or '__compiled__' in globals():
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def _ver_newer(a, b):
        """버전 a가 b보다 최신인지 (숫자 비교라 1.1.10 > 1.1.9 정상)."""
        import re
        pa = [int(x) for x in re.findall(r'\d+', a or '')]
        pb = [int(x) for x in re.findall(r'\d+', b or '')]
        return pa > pb

    def _check_update(self):
        """GitHub 최신 릴리스와 버전 비교 → 새 버전이면 안내(백그라운드 스레드, UI 안 막음)."""
        if not GITHUB_REPO or "OWNER/REPO" in GITHUB_REPO:   # 저장소 미설정 → 조용히 스킵
            return
        def _work():
            try:
                import urllib.request, json as _json
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={'User-Agent': 'Jw2Launcher'})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = _json.load(resp)
                latest = (data.get('tag_name') or '').lstrip('vV').strip()
                if not latest or not self._ver_newer(latest, APP_VERSION):
                    return
                dl = fname = None
                for a in data.get('assets', []):                 # .exe 자산 찾기
                    if (a.get('name') or '').lower().endswith('.exe'):
                        dl = a.get('browser_download_url'); fname = a.get('name'); break
                if dl:
                    self.root.after(0, lambda: self._prompt_update(latest, dl, fname))
            except Exception:
                pass                                              # 네트워크 실패 등 조용히 무시(런처는 정상 작동)
        threading.Thread(target=_work, daemon=True).start()

    def _prompt_update(self, ver, url, fname):
        """새 버전 안내 팝업 → [받기]로 다운로드 시작."""
        try:
            win = ctk.CTkToplevel(self.root)
            win.title("업데이트")
            win.geometry(self._get_popup_geometry(420, 220))
            win.configure(fg_color=self.COLOR_BG)
            win.attributes("-topmost", True); win.grab_set()
            win.bind("<Escape>", lambda e: win.destroy())
            ctk.CTkLabel(win, text=f"새 버전 v{ver} 이(가) 있습니다.", font=("Malgun Gothic", 15, "bold"),
                         text_color=self.COLOR_TEXT_MAIN).pack(pady=(24, 4))
            ctk.CTkLabel(win, text=f"현재 v{APP_VERSION}  ·  받은 뒤 새 파일을 실행하면 적용됩니다.",
                         font=("Malgun Gothic", 11), text_color=self.COLOR_TEXT_SUB).pack(pady=(0, 14))
            bar = ctk.CTkProgressBar(win, width=340); bar.set(0)
            lbl = ctk.CTkLabel(win, text="", font=("Malgun Gothic", 10), text_color=self.COLOR_TEXT_SUB)
            bf = ctk.CTkFrame(win, fg_color="transparent"); bf.pack(pady=8)
            def start_dl():
                for w in bf.winfo_children(): w.destroy()
                bar.pack(pady=(6, 2)); lbl.pack()
                lbl.configure(text="받는 중... 0%")
                threading.Thread(target=lambda: self._do_download(url, fname, win, bar, lbl), daemon=True).start()
            ctk.CTkButton(bf, text="받기", command=start_dl, fg_color=self.COLOR_BTN_PRIMARY,
                          hover_color=self.COLOR_BTN_DARK_HOVER, width=120).grid(row=0, column=0, padx=8)
            ctk.CTkButton(bf, text="나중에", command=win.destroy, fg_color=self.COLOR_BTN_DARK,
                          hover_color=self.COLOR_BTN_DARK_HOVER, width=120).grid(row=0, column=1, padx=8)
        except Exception:
            pass

    def _do_download(self, url, fname, win, bar, lbl):
        """새 exe 다운로드(진행률 표시) → 완료 시 폴더 열고 안내. 실행 중 exe는 안 건드림."""
        import urllib.request
        dst = os.path.join(self._exe_base_dir(), fname)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Jw2Launcher'})
            with urllib.request.urlopen(req, timeout=30) as r:
                total = int(r.headers.get('Content-Length', 0) or 0)
                got = 0
                with open(dst + ".part", 'wb') as f:
                    while True:
                        chunk = r.read(1 << 20)                  # 1MB씩
                        if not chunk:
                            break
                        f.write(chunk); got += len(chunk)
                        if total:
                            fr = got / total
                            self.root.after(0, lambda v=fr: (bar.set(v), lbl.configure(text=f"받는 중... {int(v*100)}%")))
            os.replace(dst + ".part", dst)                       # 완성본만 최종 파일명으로
            def done():
                try: win.destroy()
                except Exception: pass
                try: os.startfile(self._exe_base_dir())          # 받은 폴더 열기
                except Exception: pass
                messagebox.showinfo("업데이트 받음",
                                    f"새 버전을 받았습니다:\n{fname}\n\n"
                                    f"열린 폴더에서 이 파일을 실행하면 업데이트 완료입니다.\n"
                                    f"(지금 이 런처는 닫으셔도 됩니다)")
            self.root.after(0, done)
        except Exception as e:
            try: os.remove(dst + ".part")
            except Exception: pass
            self.root.after(0, lambda: messagebox.showerror("업데이트 실패", f"다운로드 중 오류가 발생했습니다:\n{e}"))

    def on_closing(self):
        if not PYSTRAY_AVAILABLE:
            self.close_spectator_monitor()   # ★런처 종료시 모니터 함께 종료
            self.root.destroy()
            return
            
        if self.config.get("always_minimize_to_tray", False):
            self.minimize_to_tray()
        else:
            self.show_exit_dialog()

    def show_exit_dialog(self):
        warn_win = ctk.CTkToplevel(self.root)
        warn_win.title("종료 확인")
        warn_win.geometry(self._get_popup_geometry(400, 180))
        warn_win.configure(fg_color=self.COLOR_BG)
        warn_win.attributes("-topmost", True)
        warn_win.grab_set()
        warn_win.bind("<Escape>", lambda e: warn_win.destroy())

        ctk.CTkLabel(warn_win, text="프로그램을 종료하시겠습니까?\n아니면 트레이로 최소화하시겠습니까?", font=("Malgun Gothic", 14, "bold"), text_color=self.COLOR_TEXT_MAIN).pack(pady=(20, 15))

        chk_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(warn_win, text="항상 트레이로 최소화 (다시 묻지 않기)", variable=chk_var, font=("Malgun Gothic", 12), text_color=self.COLOR_TEXT_SUB, fg_color=self.COLOR_BTN_PRIMARY).pack(pady=(0, 15))

        btn_frame = ctk.CTkFrame(warn_win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)
        btn_frame.columnconfigure((0, 1), weight=1)

        def on_exit():
            warn_win.destroy()
            self.close_spectator_monitor()   # ★런처 종료시 관전 모니터+오버레이 함께 종료
            self.root.destroy()
            os._exit(0)

        def on_minimize():
            if chk_var.get():
                self.config["always_minimize_to_tray"] = True
                self.save_config()
            warn_win.destroy()
            self.minimize_to_tray()

        ctk.CTkButton(btn_frame, text="프로그램 종료", command=on_exit, fg_color=self.COLOR_BTN_DARK, hover_color=self.COLOR_BTN_DARK_HOVER).grid(row=0, column=0, padx=5, sticky="ew")
        ctk.CTkButton(btn_frame, text="닫기(트레이로 최소화)", command=on_minimize, fg_color=self.COLOR_BTN_PRIMARY, hover_color=self.COLOR_BTN_PRIMARY_HOVER).grid(row=0, column=1, padx=5, sticky="ew")

    def minimize_to_tray(self):
        self.root.withdraw()
        
        if PIL_AVAILABLE and os.path.exists(self.icon_path):
            image = Image.open(self.icon_path)
        else:
            image = Image.new('RGB', (64, 64), color=(58, 113, 240))
        
        menu = (
            item('열기', self.restore_from_tray, default=True),
            item('종료', self.quit_from_tray)
        )
        self.tray_icon = pystray.Icon("Jw2Launcher", image, "Jw2Launcher", menu)
        self.tray_icon.run_detached(setup=self.setup_tray)

    def setup_tray(self, icon):
        icon.visible = True

    def restore_from_tray(self, icon, item):
        self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)

    def quit_from_tray(self, icon, item):
        self.tray_icon.stop()
        self.close_spectator_monitor()   # ★트레이 종료시 모니터 함께 종료
        self.root.quit()
        os._exit(0)

    def on_mode_change(self, choice):
        if choice == "맵 에디터":
            self.rb_exclusive.configure(state="disabled")
            self.rb_borderless.configure(state="disabled")
            self.rb_windowed.configure(state="disabled")
        else:
            self.rb_exclusive.configure(state="normal")
            self.rb_borderless.configure(state="normal")
            self.rb_windowed.configure(state="normal")
            

    def _autostart_spectator(self):
        """★런처 실행시 관전 오버레이(모니터) 자동 실행 (런처 종속)."""
        self.launch_spectator_monitor()

    def launch_spectator_monitor(self):
        """관전 모니터를 독립 프로세스로 실행 (이미 실행 중이면 재시작)"""
        self.close_spectator_monitor()
        try:
            import JW2_Ranker_Monitor
            # ★런처 종속: 런처 PID를 넘겨 모니터가 런처 종료를 감지·자동종료 + 독립실행 차단
            p = multiprocessing.Process(target=JW2_Ranker_Monitor.main, args=(os.getpid(),))
            p.daemon = False
            p.start()
            self.spectator_proc = p
        except ImportError:
            messagebox.showerror("모듈 누락", "jw2_live_monitor 모듈을 찾을 수 없습니다.\n같은 경로에 jw2_live_monitor.py 파일이 있는지 확인해주세요.")
        except Exception as e:
            messagebox.showerror("실행 오류", f"관전 모니터를 실행하는 중 오류가 발생했습니다.\n{e}")

    def close_spectator_monitor(self):
        """실행 중인 관전 모니터 프로세스 종료"""
        if self.spectator_proc is not None:
            try:
                if self.spectator_proc.is_alive():
                    self.spectator_proc.terminate()
                    self.spectator_proc.join(timeout=2)
            except Exception:
                pass
            self.spectator_proc = None

    def open_overlay_options(self):
        """★오버레이(관전) 설정 창: 자동 활성화 / 진행바 숨김 + 단축키 안내.
        설정은 config.json에 저장 → 관전 모니터가 폴링해 즉시 반영."""
        if getattr(self, 'overlay_win', None) is not None and self.overlay_win.winfo_exists():
            self.overlay_win.lift(); self.overlay_win.focus_force(); return
        self.overlay_win = ctk.CTkToplevel(self.root)
        self.overlay_win.title("오버레이 설정")
        self.overlay_win.geometry(self._get_popup_geometry(460, 320))
        self.overlay_win.configure(fg_color=self.COLOR_BG)
        self.overlay_win.wm_transient(self.root)
        self.overlay_win.lift(); self.overlay_win.focus_force()
        self.overlay_win.bind("<Escape>", lambda e: self.overlay_win.destroy())

        FONT_HEADER = ("Segoe UI", 16, "bold")
        FONT_BODY = ("Malgun Gothic", 14, "bold")
        FONT_SUB = ("Malgun Gothic", 11)

        panel = ctk.CTkFrame(self.overlay_win, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        panel.pack(fill="both", expand=True, padx=14, pady=(14, 8))
        ctk.CTkLabel(panel, text="관전 오버레이", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(14, 8))

        auto_var = tk.BooleanVar(value=self.config.get("spectator_overlay_auto", True))
        gauge_var = tk.BooleanVar(value=self.config.get("replay_hide_gauge", True))

        def save_overlay_cfg():
            self.config["spectator_overlay_auto"] = auto_var.get()
            self.config["replay_hide_gauge"] = gauge_var.get()
            self.save_config()

        ctk.CTkCheckBox(panel, text="관전 오버레이 자동 활성화", variable=auto_var,
                        font=FONT_BODY, text_color=self.COLOR_TEXT_MAIN, fg_color=self.COLOR_BTN_PRIMARY,
                        hover_color=self.COLOR_BTN_PRIMARY_HOVER, command=save_overlay_cfg).pack(anchor="w", padx=18, pady=(4, 0))
        ctk.CTkLabel(panel, text="체크 시 관전·리플레이에서 오버레이 자동 표시, 해제 시 바닐라 (직접 플레이는 항상 바닐라)",
                     font=FONT_SUB, text_color=self.COLOR_TEXT_SUB, justify="left").pack(anchor="w", padx=44, pady=(0, 10))

        ctk.CTkCheckBox(panel, text="리플레이 관전 시 게임 진행바 숨기기", variable=gauge_var,
                        font=FONT_BODY, text_color=self.COLOR_TEXT_MAIN, fg_color=self.COLOR_BTN_PRIMARY,
                        hover_color=self.COLOR_BTN_PRIMARY_HOVER, command=save_overlay_cfg).pack(anchor="w", padx=18, pady=(4, 0))
        ctk.CTkLabel(panel, text="리플레이 하단 재생 진행 게이지바를 숨김 (재생 버튼은 유지)",
                     font=FONT_SUB, text_color=self.COLOR_TEXT_SUB, justify="left").pack(anchor="w", padx=44, pady=(0, 12))

        ctk.CTkButton(panel, text="⌨  단축키 안내", height=38, font=FONT_BODY,
                      fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1,
                      hover_color=self.COLOR_BTN_DARK_HOVER, command=self.show_shortcut_guide).pack(anchor="w", padx=18, pady=(2, 14))

        btn_frame = ctk.CTkFrame(self.overlay_win, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=(0, 12), padx=20)
        ctk.CTkButton(btn_frame, text="닫기", command=self.overlay_win.destroy, fg_color=self.COLOR_BTN_DARK,
                      border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER).pack(side="right", expand=True, fill="x", padx=5)

    def open_color_options(self):
        """★플레이어 색 커스텀 설정(로컬 인메모리 오버라이드, 나만 적용). 관전 모니터가 config 폴링해 반영.
        [플레이 시] 내 색/적 색(기본값 or 색상지정) · [관전 시] 빨강파랑 or 임의색(플레이어1/2)."""
        from tkinter import colorchooser
        if getattr(self, 'color_win', None) is not None and self.color_win.winfo_exists():
            self.color_win.lift(); self.color_win.focus_force(); return
        win = ctk.CTkToplevel(self.root); self.color_win = win
        win.title("플레이어 색상 설정")
        win.geometry(self._get_popup_geometry(500, 560))
        win.configure(fg_color=self.COLOR_BG)
        try: win.wm_transient(self.overlay_win if getattr(self, 'overlay_win', None) and self.overlay_win.winfo_exists() else self.root)
        except Exception: pass
        win.lift(); win.focus_force(); win.after(80, lambda: (win.winfo_exists() and win.lift()))
        win.bind("<Escape>", lambda e: win.destroy())
        FH = ("Segoe UI", 15, "bold"); FB = ("Malgun Gothic", 13, "bold"); FS = ("Malgun Gothic", 11)
        c = self.config

        # 상태 변수 (★기본값 제거 — 항상 색상지정. me/enemy는 항상 hex 저장)
        def _hx(v, d):
            v = c.get(v, d)
            return v if isinstance(v, str) and v.startswith("#") else d
        play_custom = tk.BooleanVar(value=c.get("color_play_custom", False))
        me_col   = [_hx("color_play_me", "#ff1414")]
        en_col   = [_hx("color_play_enemy", "#2038dc")]
        spec_custom = tk.BooleanVar(value=c.get("color_spec_custom", False))
        spec_mode = tk.StringVar(value=c.get("color_spec_mode", "rb"))
        p1_col = [_hx("color_spec_p1", "#ff1414")]; p2_col = [_hx("color_spec_p2", "#2038dc")]

        def save():
            c["color_play_custom"] = play_custom.get()
            c["color_play_me"]    = me_col[0]
            c["color_play_enemy"] = en_col[0]
            c["color_spec_custom"] = spec_custom.get()
            c["color_spec_mode"]  = spec_mode.get()
            c["color_spec_p1"] = p1_col[0]; c["color_spec_p2"] = p2_col[0]
            self.save_config()

        # ★색상 팔레트: 슬롯 기본색 8종 + 초록·검정·흰색 추가
        SLOT_COLORS = ["#FF1414", "#2038DC", "#E13DFF", "#FF9010", "#C86E28",
                       "#FFE800", "#D8AC66", "#12E6C8", "#9A9A9A",
                       "#00C800", "#000000", "#FFFFFF"]
        def mkswatch(parent, colref, onpick):
            st = {'en': True}
            sw = tk.Label(parent, bg=colref[0], width=4, relief="solid", bd=1, cursor="hand2")
            def choose(hx):
                colref[0] = hx; sw.config(bg=hx); onpick()
            def pick(_e=None):
                if not st['en']:
                    return
                pop = tk.Toplevel(win); pop.title("색상 선택"); pop.configure(bg="#1a1a2e")
                pop.transient(win); pop.resizable(False, False)
                try: pop.grab_set()
                except Exception: pass
                tk.Label(pop, text="색상 선택", bg="#1a1a2e", fg="#e2e8f4",
                         font=("Malgun Gothic", 11, "bold")).grid(row=0, column=0, columnspan=5, pady=(8, 4))
                for i, hc in enumerate(SLOT_COLORS):
                    tk.Button(pop, bg=hc, width=3, height=1, relief="raised", bd=2, cursor="hand2",
                              activebackground=hc,
                              command=lambda h=hc: (choose(h), pop.destroy())).grid(row=1 + i // 5, column=i % 5, padx=3, pady=3)
                def more():
                    try: pop.grab_release()
                    except Exception: pass
                    rgb, hx = colorchooser.askcolor(color=colref[0], parent=pop)
                    if hx: choose(hx)
                    pop.destroy()
                tk.Button(pop, text="더 많은 색상 보기…", bg="#2a2a3e", fg="#e2e8f4", relief="flat",
                          cursor="hand2", command=more).grid(row=3 + len(SLOT_COLORS)//5, column=0, columnspan=5, sticky="ew", padx=8, pady=(6, 8))
                # ★색 설정창 중앙 위에 띄움(좌상단 고정 방지)
                try:
                    pop.update_idletasks()
                    pw = pop.winfo_reqwidth(); ph = pop.winfo_reqheight()
                    wx = win.winfo_rootx(); wy = win.winfo_rooty()
                    ww = win.winfo_width(); wh = win.winfo_height()
                    pop.geometry(f"+{max(0, wx + (ww - pw) // 2)}+{max(0, wy + (wh - ph) // 2)}")
                except Exception:
                    pass
            sw.bind("<Button-1>", pick)
            def set_en(on):
                st['en'] = on
                sw.config(cursor=("hand2" if on else "arrow"), relief=("solid" if on else "flat"),
                          bg=(colref[0] if on else "#3a3a44"))
            sw._set_en = set_en
            return sw

        _cmd = {'fn': (lambda: None)}   # 체크박스/라디오 명령 지연참조(위젯 생성 후 on_change 연결)

        # ── [플레이 시] ──
        p1f = ctk.CTkFrame(win, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        p1f.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(p1f, text="플레이 시", font=FH, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkCheckBox(p1f, text="커스텀 색상 사용", variable=play_custom, font=FB,
                        text_color=self.COLOR_TEXT_MAIN, fg_color=self.COLOR_BTN_PRIMARY,
                        hover_color=self.COLOR_BTN_PRIMARY_HOVER,
                        command=lambda: _cmd['fn']()).pack(anchor="w", padx=16, pady=(2, 6))
        _play_sws = []
        for lab, colref in (("내 색상", me_col), ("적 색상", en_col)):
            row = tk.Frame(p1f, bg=self.COLOR_PANEL); row.pack(fill="x", padx=30, pady=2)
            tk.Label(row, text=lab, bg=self.COLOR_PANEL, fg="#e2e8f4", font=FB, width=7, anchor="w").pack(side="left")
            _sw = mkswatch(row, colref, save); _sw.pack(side="left"); _play_sws.append(_sw)

        # ── [관전 시] ──
        p2f = ctk.CTkFrame(win, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        p2f.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(p2f, text="관전 시", font=FH, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkCheckBox(p2f, text="커스텀 색상 사용", variable=spec_custom, font=FB,
                        text_color=self.COLOR_TEXT_MAIN, fg_color=self.COLOR_BTN_PRIMARY,
                        hover_color=self.COLOR_BTN_PRIMARY_HOVER,
                        command=lambda: _cmd['fn']()).pack(anchor="w", padx=16, pady=(2, 6))
        rrow = tk.Frame(p2f, bg=self.COLOR_PANEL); rrow.pack(anchor="w", padx=30, pady=2)
        _rb1 = tk.Radiobutton(rrow, text="빨강 · 파랑 쓰기", variable=spec_mode, value="rb", bg=self.COLOR_PANEL, fg="#cfd8e8",
                              selectcolor="#232734", font=FB, command=lambda: _cmd['fn']())
        _rb1.pack(anchor="w")
        crow = tk.Frame(p2f, bg=self.COLOR_PANEL); crow.pack(anchor="w", padx=30, pady=2)
        _rb2 = tk.Radiobutton(crow, text="임의의 색 쓰기", variable=spec_mode, value="custom", bg=self.COLOR_PANEL, fg="#cfd8e8",
                              selectcolor="#232734", font=FB, command=lambda: _cmd['fn']())
        _rb2.pack(side="left")
        prow = tk.Frame(p2f, bg=self.COLOR_PANEL); prow.pack(anchor="w", padx=52, pady=(2, 10))
        tk.Label(prow, text="플레이어1", bg=self.COLOR_PANEL, fg="#e2e8f4", font=FS).pack(side="left", padx=(0, 4))
        _p1sw = mkswatch(prow, p1_col, save); _p1sw.pack(side="left", padx=(0, 16))
        tk.Label(prow, text="플레이어2", bg=self.COLOR_PANEL, fg="#e2e8f4", font=FS).pack(side="left", padx=(0, 4))
        _p2sw = mkswatch(prow, p2_col, save); _p2sw.pack(side="left")

        # ★활성/비활성: 커스텀 체크 해제 시 하위 컨트롤 비활성화
        def upd_enable():
            pon = play_custom.get()
            for w in _play_sws: w._set_en(pon)
            son = spec_custom.get()
            _rb1.config(state=("normal" if son else "disabled"))
            _rb2.config(state=("normal" if son else "disabled"))
            _custom = son and spec_mode.get() == "custom"
            _p1sw._set_en(_custom); _p2sw._set_en(_custom)
        def on_change():
            upd_enable(); save()
        _cmd['fn'] = on_change
        upd_enable()   # 초기 상태 반영

        ctk.CTkLabel(win, text="※ 내 게임 화면에만 적용됩니다(다른 플레이어는 각자 설정 색으로 봄).",
                     font=FS, text_color=self.COLOR_TEXT_SUB).pack(anchor="w", padx=18, pady=(2, 4))
        ctk.CTkButton(win, text="닫기", command=win.destroy, fg_color=self.COLOR_BTN_DARK,
                      border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER).pack(side="bottom", fill="x", padx=20, pady=(4, 12))

    def show_shortcut_guide(self):
        """★관전 UI 단축키 안내 — 큰 키보드 그림, 각 단축키 안에 기능 설명을 직접 표기."""
        if getattr(self, 'shortcut_win', None) is not None and self.shortcut_win.winfo_exists():
            self.shortcut_win.lift(); self.shortcut_win.focus_force(); return
        win = ctk.CTkToplevel(self.root)
        self.shortcut_win = win
        win.title("관전 UI 단축키 안내")
        win.configure(fg_color=self.COLOR_BG)
        win.geometry(self._get_popup_geometry(970, 540))
        # ★'오버레이 설정' 창 앞으로 (부모 transient + 지연 lift)
        _parent = self.overlay_win if (getattr(self, 'overlay_win', None) is not None
                                       and self.overlay_win.winfo_exists()) else self.root
        try: win.wm_transient(_parent)
        except Exception: pass
        def _raise():
            try:
                if win.winfo_exists():
                    win.lift(); win.focus_force()
            except Exception: pass
        _raise(); win.after(60, _raise); win.after(200, _raise)
        win.bind("<Escape>", lambda e: win.destroy())

        TXT = "#e2e8f4"; DEF = "#232734"; EDGE = "#4a5066"
        BLUE = "#4a86ff"; ORANGE = "#f0912f"; GREEN = "#37c98a"; PURPLE = "#a06bff"
        cv = tk.Canvas(win, width=950, height=500, bg="#0b0c10", highlightthickness=0)
        cv.pack(padx=8, pady=6)
        cv.create_text(475, 30, text="관전 UI 단축키", fill="#ffffff", font=("Malgun Gothic", 20, "bold"))

        KW, KH, PITCH, ROW = 74, 62, 82, 76
        NUM = {'1': '현재 유닛', '2': '전투 유닛', '3': '레벨업 유닛', '4': '자원·일꾼',
               '5': '자원 현황', '6': '총 업글', '7': '현재 건물', '8': '잃은 유닛',
               '9': '잃은 건물', '0': '슬라이드쇼'}
        QW = {'Q': '생산 중', 'W': '현재 유닛', 'E': '완료 업글',
              'R': '일꾼 현황', 'T': '게임 통계'}
        AS = {'A': '확장 맵', 'S': '게임 액션'}

        def key(x, y, ch, color, func=None, kw=KW):
            cv.create_rectangle(x, y, x+kw, y+KH, fill=(color or DEF), outline=EDGE, width=1)
            cv.create_line(x+2, y+KH, x+kw-2, y+KH, fill="#12141c", width=3)   # 키캡 하단 음영
            if func:
                cv.create_text(x+kw/2, y+20, text=ch, fill="#ffffff", font=("Malgun Gothic", 17, "bold"))
                cv.create_text(x+kw/2, y+44, text=func, fill="#eef2fb", font=("Malgun Gothic", 10))
            else:
                cv.create_text(x+kw/2, y+KH/2, text=ch, fill=("#ffffff" if color else "#6f7789"),
                               font=("Malgun Gothic", 16, "bold"))

        kx = 45; yN = 88; yQ = yN+ROW; yA = yQ+ROW
        for i, ch in enumerate("1234567890"):
            key(kx+i*PITCH, yN, ch, GREEN if ch in NUM else None, NUM.get(ch))
        for i, ch in enumerate("QWERTYUIOP"):
            key(kx+i*PITCH+20, yQ, ch, BLUE if ch in QW else None, QW.get(ch))
        for i, ch in enumerate("ASDFGHJKL"):
            key(kx+i*PITCH+34, yA, ch, ORANGE if ch in AS else None, AS.get(ch))

        # ── 넘버패드(별도 키) ──
        ny = yA + KH + 30
        cv.create_text(kx+10, ny+2, text="넘버패드", fill=TXT, font=("Malgun Gothic", 12, "bold"), anchor="w")
        key(kx+100, ny-16, "0", PURPLE, "관전UI 켜기/새로시작", kw=178)
        key(kx+100+205, ny-16, "1", PURPLE, "좌우 반전")   # ★일반 단축키 폭(KW)으로 맞춤

        # ── 해상도 최적화 안내(별도) ──
        ly = ny + 82
        cv.create_text(475, ly+10, text="오버레이는 1920 × 1080 해상도에 최적화되어 있습니다.",
                       fill="#9aa6b4", font=("Malgun Gothic", 13), anchor="center")

    def build_ui(self):
        FONT_HEADER = ("Segoe UI", 16, "bold")
        FONT_BODY = ("Malgun Gothic", 14, "bold")
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=False, padx=20, pady=(15, 10))
        
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        # [수정됨] 버튼 개수를 4개에서 5개로 변경
        header_frame.columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="header_btns")

        ctk.CTkButton(header_frame, text="경로 설정", height=36, font=FONT_HEADER, fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER, command=self.open_settings_window).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ctk.CTkButton(header_frame, text="옵션", height=36, font=FONT_HEADER, fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER, command=self.open_options_window).grid(row=0, column=1, sticky="ew", padx=3)
        # ★오버레이 버튼(구 관전옵션 대체) — 관전 오버레이 설정 창
        ctk.CTkButton(header_frame, text="오버레이", height=36, font=FONT_HEADER, fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER, command=self.open_overlay_options).grid(row=0, column=2, sticky="ew", padx=3)
        ctk.CTkButton(header_frame, text="리플레이", height=36, font=FONT_HEADER, fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER, command=self.open_replay_folder).grid(row=0, column=3, sticky="ew", padx=3)
        ctk.CTkButton(header_frame, text="도움말", height=36, font=FONT_HEADER, fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER, command=self.show_help).grid(row=0, column=4, sticky="ew", padx=(3, 0))

        mode_panel = ctk.CTkFrame(main_frame, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        mode_panel.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(mode_panel, text="실행 파일 선택", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(10, 4))
        self.game_mode_var = ctk.StringVar(value="넓은 시야 (1024x768)")
        
        dropdown_style = {
            "font": FONT_BODY,
            "dropdown_font": FONT_BODY,
            "fg_color": self.COLOR_INPUT,
            "button_color": self.COLOR_BTN_DARK,
            "button_hover_color": self.COLOR_BTN_DARK_HOVER,
            "dropdown_fg_color": "#1e212b",
            "dropdown_hover_color": self.COLOR_BTN_PRIMARY,
            "dropdown_text_color": self.COLOR_TEXT_MAIN,
            "text_color": self.COLOR_TEXT_MAIN,
            "corner_radius": 6,
            "state": "readonly"
        }
        
        mode_combobox = ctk.CTkComboBox(mode_panel, variable=self.game_mode_var, values=["넓은 시야 (1024x768)", "기본 시야 (640x480)", "맵 에디터"], height=40, command=self.on_mode_change, **dropdown_style)
        mode_combobox.pack(fill="x", padx=16, pady=(0, 12))
        mode_combobox.set("넓은 시야 (1024x768)")

        bgm_panel = ctk.CTkFrame(main_frame, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        bgm_panel.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(bgm_panel, text="배경음악 선택", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(10, 4))
        
        self.bgm_var = ctk.StringVar(value=self.config.get("bgm_mode", "TheRanker 확장판"))
        bgm_combobox = ctk.CTkComboBox(bgm_panel, variable=self.bgm_var, values=["TheRanker 확장판", "오리지널"], height=40, command=lambda e: self.save_config(), **dropdown_style)
        bgm_combobox.pack(fill="x", padx=16, pady=(0, 12))

        display_panel = ctk.CTkFrame(main_frame, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        display_panel.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(display_panel, text="디스플레이 모드 설정", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(10, 4))
        
        radio_frame = ctk.CTkFrame(display_panel, fg_color="transparent")
        radio_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.display_var = tk.StringVar(value=self.config.get("display_mode", "borderless"))
        
        self.rb_borderless = ctk.CTkRadioButton(radio_frame, text="전체화면(테두리 없는 창모드)", variable=self.display_var, value="borderless", 
                           font=("Malgun Gothic", 12, "bold"), text_color=self.COLOR_TEXT_MAIN, fg_color=self.COLOR_BTN_PRIMARY, hover_color=self.COLOR_BTN_PRIMARY_HOVER, width=0)
        self.rb_borderless.pack(side="left", padx=(0, 15))
        
        self.rb_windowed = ctk.CTkRadioButton(radio_frame, text="창모드", variable=self.display_var, value="windowed", 
                           font=("Malgun Gothic", 12, "bold"), text_color=self.COLOR_TEXT_MAIN, fg_color=self.COLOR_BTN_PRIMARY, hover_color=self.COLOR_BTN_PRIMARY_HOVER, width=0)
        self.rb_windowed.pack(side="left", padx=15)

        self.rb_exclusive = ctk.CTkRadioButton(radio_frame, text="전체화면", variable=self.display_var, value="exclusive", 
                           font=("Malgun Gothic", 12, "bold"), text_color=self.COLOR_TEXT_MAIN, fg_color=self.COLOR_BTN_PRIMARY, hover_color=self.COLOR_BTN_PRIMARY_HOVER, width=0)
        self.rb_exclusive.pack(side="left", padx=(15, 0))

        self.on_mode_change(self.game_mode_var.get())

        # ★관전UI 체크박스 제거: 관전 모니터는 이제 런처 실행시 자동 실행(런처 종속).
        #   오버레이는 관전자/리플레이에서 자동 표시(직접 플레이 중엔 안 뜸). 별도 토글 없음.

        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 10)) 
        
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.rowconfigure(0, minsize=50)

        ctk.CTkButton(btn_frame, text="게임 시작 (PLAY)", height=50, font=("Segoe UI", 18, "bold"), 
                      fg_color=self.COLOR_BTN_PRIMARY, hover_color=self.COLOR_BTN_PRIMARY_HOVER, 
                      command=self.launch_selected_game).grid(row=0, column=0, sticky="nsew", padx=0)

        info_panel = ctk.CTkFrame(main_frame, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        info_panel.pack(fill="x", pady=(0, 8))
        info_panel.columnconfigure(0, weight=1)

        ip_frame = ctk.CTkFrame(info_panel, fg_color="transparent")
        ip_frame.grid(row=0, column=0, sticky="e", padx=16, pady=12)
        
        ctk.CTkLabel(ip_frame, text="내 IP 주소:", font=("Malgun Gothic", 12, "bold"), text_color=self.COLOR_TEXT_SUB).pack(side="left", padx=(0, 5))
        
        self.ip_visible = True
        self.real_ip = get_local_ip()
        
        def mask_ip(ip_str):
            parts = ip_str.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.---.---.--"
            return "---.---.---.---"
            
        self.masked_ip = mask_ip(self.real_ip)
        
        ip_entry = ctk.CTkEntry(ip_frame, width=110, height=28, font=("Consolas", 12, "bold"), fg_color=self.COLOR_INPUT, text_color=self.COLOR_TEXT_MAIN, border_width=1, border_color=self.COLOR_BORDER)
        ip_entry.insert(0, self.real_ip)
        ip_entry.configure(state="readonly")
        ip_entry.pack(side="left", padx=(0, 5))
        
        def toggle_ip_visibility():
            self.ip_visible = not self.ip_visible
            ip_entry.configure(state="normal")
            ip_entry.delete(0, tk.END)
            if self.ip_visible:
                ip_entry.insert(0, self.real_ip)
                toggle_btn.configure(text="🔓")
            else:
                ip_entry.insert(0, self.masked_ip)
                toggle_btn.configure(text="🔒")
            ip_entry.configure(state="readonly")

        toggle_btn = ctk.CTkButton(ip_frame, text="🔓", width=30, height=28, font=("Segoe UI Emoji", 14), fg_color=self.COLOR_BTN_DARK, hover_color=self.COLOR_BTN_DARK_HOVER, command=toggle_ip_visibility)
        toggle_btn.pack(side="left", padx=(0, 5))
        
        copy_btn = ctk.CTkButton(ip_frame, text="복사", width=45, height=28, font=("Malgun Gothic", 12, "bold"), fg_color=self.COLOR_BTN_DARK, hover_color=self.COLOR_BTN_DARK_HOVER)
        
        def copy_ip():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.real_ip)
            copy_btn.configure(text="✔", fg_color="#28a745", hover_color="#28a745", text_color="#ffffff")
            self.root.after(1500, lambda: copy_btn.configure(text="복사", fg_color=self.COLOR_BTN_DARK, hover_color=self.COLOR_BTN_DARK_HOVER))
            
        copy_btn.configure(command=copy_ip)
        copy_btn.pack(side="left")

        link_panel = ctk.CTkFrame(main_frame, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        link_panel.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(link_panel, text="관련 링크", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(10, 4))
        
        link_inner = ctk.CTkFrame(link_panel, fg_color="transparent")
        link_inner.pack(fill="x", padx=12, pady=(0, 10))
        link_inner.columnconfigure((0,1,2,3,4), weight=1, uniform="links")

        def open_url(url):
            webbrowser.open(url)                
        
        def make_btn_kwargs(icon_name):
            kwargs = {}
            base_dir = _res_dir()

            icon_full_path = os.path.join(base_dir, icon_name)

            if PIL_AVAILABLE and os.path.exists(icon_full_path):
                try:
                    img = Image.open(icon_full_path)
                    kwargs["image"] = ctk.CTkImage(light_image=img, dark_image=img, size=(17, 17))   # ★5버튼 한줄: 아이콘 축소(22→17)
                    kwargs["compound"] = "left"
                except:
                    pass
            return kwargs

        button_style = {
            "height": 36,
            "fg_color": self.COLOR_BTN_DARK,
            "hover_color": self.COLOR_BTN_DARK_HOVER,
            "text_color": self.COLOR_TEXT_MAIN,
            "font": ("Malgun Gothic", 11, "bold"),   # ★5버튼 한줄: 폰트 축소(글자 잘림 방지)
            "border_color": self.COLOR_BORDER,
            "border_width": 1
        }

        ctk.CTkButton(link_inner, text="카카오톡", command=lambda: open_url("https://open.kakao.com/o/g6BJ6Yv"), **make_btn_kwargs("kakaotalk.ico"), **button_style).grid(row=0, column=0, sticky="ew", padx=3)
        ctk.CTkButton(link_inner, text="공식카페", command=lambda: open_url("https://cafe.naver.com/jtr"), **make_btn_kwargs("naver.ico"), **button_style).grid(row=0, column=1, sticky="ew", padx=3)
        ctk.CTkButton(link_inner, text="디스코드", command=lambda: open_url("https://discord.gg/TE27ZGcuMu"), **make_btn_kwargs("discord.ico"), **button_style).grid(row=0, column=2, sticky="ew", padx=3)
        ctk.CTkButton(link_inner, text="Radmin", command=lambda: open_url("https://www.radmin-vpn.com/"), **make_btn_kwargs("radmin.ico"), **button_style).grid(row=0, column=3, sticky="ew", padx=3)
        # ★JW2 전적 사이트(자동 전적기록 연동) — 전투유닛 아이콘, 같은 행 5번째
        ctk.CTkButton(link_inner, text="전적사이트", command=lambda: open_url("http://jw2-arena.com/all"), **make_btn_kwargs(os.path.join("ico", "전투유닛.png")), **button_style).grid(row=0, column=4, sticky="ew", padx=3)

        version_label = ctk.CTkLabel(main_frame, text=f"Game: v2021. 9. 18. | Jw2Launcher: v{APP_VERSION}", font=("Malgun Gothic", 11, "bold"), text_color=self.COLOR_TEXT_SUB, anchor="e")
        version_label.pack(fill="x", pady=(10, 0))

    def open_replay_folder(self):
        replay_path = self.config.get("path_replay", "")
        if not replay_path or not os.path.exists(replay_path):
            messagebox.showwarning("알림", "리플레이 폴더가 지정되지 않았거나 존재하지 않습니다.\n'경로 설정' 메뉴에서 폴더를 먼저 지정해주세요.")
            return
        
        try:
            os.startfile(replay_path)
        except AttributeError:
            subprocess.Popen(['explorer', os.path.normpath(replay_path)])
        except Exception as e:
            messagebox.showerror("오류", f"폴더를 여는 중 오류가 발생했습니다.\n{e}")

    def show_help(self):
        if self.help_win is not None and self.help_win.winfo_exists():
            self.help_win.lift()
            self.help_win.focus_force()
            return

        self.help_win = ctk.CTkToplevel(self.root)
        self.help_win.title("도움말")
        self.help_win.geometry(self._get_popup_geometry(400, 440))
        self.help_win.configure(fg_color=self.COLOR_BG)
        self.help_win.wm_transient(self.root)
        self.help_win.lift()
        self.help_win.focus_force()
        self.help_win.bind("<Escape>", lambda e: self.help_win.destroy())
        
        FONT_HEADER = ("Segoe UI", 16, "bold")
        FONT_BODY = ("Malgun Gothic", 13, "bold")

        help_panel = ctk.CTkFrame(self.help_win, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        help_panel.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(help_panel, text="단축키 안내", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(16, 8))
        
        keys_text = (
            "• Alt + Enter : 전체화면 및 창모드 전환\n"
            "• 왼쪽Ctrl + Tab : 창모드 시 마우스 잠금 on/off"
        )
        ctk.CTkLabel(help_panel, text=keys_text, font=FONT_BODY, text_color=self.COLOR_TEXT_SUB, justify="left").pack(anchor="w", padx=16, pady=(0, 16))

        ctk.CTkLabel(help_panel, text="게임 내 단축키 (Alt + 해당키)", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(10, 8))

        lobby_text = (
            "• Alt + O : 확인\n"
            "• Alt + C : 취소\n"
            "• Alt + H : 게임 개설\n"
            "• Alt + J : 게임 참가\n"
            "• Alt + G : 게임 시작"
        )
        ctk.CTkLabel(help_panel, text=lobby_text, font=FONT_BODY, text_color=self.COLOR_TEXT_SUB, justify="left").pack(anchor="w", padx=16, pady=(0, 16))

        ctk.CTkLabel(help_panel, text="커뮤니 안내", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(10, 8))
        ctk.CTkLabel(help_panel, text="• 카카오톡 오픈채팅방 입장 비밀번호: 1234", font=FONT_BODY, text_color=self.COLOR_TEXT_SUB, justify="left").pack(anchor="w", padx=16, pady=(0, 16))

        ctk.CTkButton(help_panel, text="닫기", command=self.help_win.destroy, fg_color=self.COLOR_BTN_DARK, hover_color=self.COLOR_BTN_DARK_HOVER, width=100).pack(pady=10)

    def _find_game_pids(self):
        exes = {"rank1024.exe", "ranker800.exe", "ranker800"}
        pids = set()
        try:
            for p in psutil.process_iter(['name']):
                try:
                    if (p.info.get('name') or '').lower() in exes:
                        pids.add(p.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return pids

    def _get_game_hwnd(self):
        """실행 중인 게임 최상위 창 hwnd 반환(없으면 None)."""
        pids = self._find_game_pids()
        if not pids:
            return None
        import ctypes.wintypes as wt
        u = ctypes.windll.user32
        found = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(hwnd, lparam):
            try:
                if u.IsWindowVisible(hwnd) and u.GetWindow(hwnd, 4) == 0:   # GW_OWNER=4 → 최상위
                    pid = wt.DWORD()
                    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in pids and u.GetWindowTextLengthW(hwnd) > 0:
                        found.append(hwnd)
            except Exception:
                pass
            return True
        u.EnumWindows(WNDENUMPROC(cb), 0)
        return found[0] if found else None

    def center_game_window(self):
        """★실행 중인 게임창의 '실제 현재 크기'를 그 창이 놓인 모니터 중앙으로 이동.
           - 설정 해상도가 아니라 GetWindowRect로 읽은 진짜 창 크기 기준.
           - 테두리없는 창모드에서 창이 모니터를 꽉 채우면(창 크기=모니터 해상도) 중앙정렬 의미없음 → 작동 안 함."""
        def _feedback(msg, revert=True):
            try:
                if hasattr(self, '_center_btn') and self._center_btn.winfo_exists():
                    self._center_btn.configure(text=msg)
                    if revert:
                        self.root.after(1800, lambda: self._center_btn.winfo_exists()
                                        and self._center_btn.configure(text="⊹  게임창 중앙 정렬"))
            except Exception:
                pass
        hwnd = self._get_game_hwnd()
        if not hwnd:
            _feedback("게임이 실행 중이 아닙니다")
            return
        import ctypes.wintypes as wt
        u = ctypes.windll.user32
        # 실제 창 사각형(테두리없는 창모드=클라이언트와 동일)
        r = wt.RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(r)):
            _feedback("창 위치를 읽지 못했습니다")
            return
        w = r.right - r.left; h = r.bottom - r.top
        # 창이 놓인 모니터(멀티모니터 대응)
        class _MI(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                        ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]
        hmon = u.MonitorFromWindow(hwnd, 2)   # MONITOR_DEFAULTTONEAREST
        mi = _MI(); mi.cbSize = ctypes.sizeof(_MI)
        if not u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            _feedback("모니터 정보를 읽지 못했습니다")
            return
        mon_l = mi.rcMonitor.left; mon_t = mi.rcMonitor.top
        mon_w = mi.rcMonitor.right - mi.rcMonitor.left
        mon_h = mi.rcMonitor.bottom - mi.rcMonitor.top
        # ★창이 이미 모니터 전체를 채움(=출력해상도가 모니터 해상도와 동일) → 중앙정렬 불필요, 작동 안 함
        if w >= mon_w and h >= mon_h:
            _feedback("이미 전체화면 — 정렬 불필요")
            return
        cx = mon_l + max(0, (mon_w - w) // 2)
        cy = mon_t + max(0, (mon_h - h) // 2)
        SWP = 0x0001 | 0x0004 | 0x0010   # NOSIZE|NOZORDER|NOACTIVATE
        moved = bool(u.SetWindowPos(hwnd, 0, cx, cy, 0, 0, SWP))
        if moved:
            # 다음 실행에도 같은 위치로(실제 크기가 곧 설정 해상도라 재현됨)
            self.config["game_pos_x"] = int(cx)
            self.config["game_pos_y"] = int(cy)
            self.save_config()
        _feedback("✓ 중앙 정렬됨" if moved else "이동 실패")

    def open_options_window(self):
        if self.options_win is not None and self.options_win.winfo_exists():
            self.options_win.lift()
            self.options_win.focus_force()
            return
        
        self.options_win = ctk.CTkToplevel(self.root)
        self.options_win.title("옵션 설정")
        self.options_win.geometry(self._get_popup_geometry(480, 680))
        self.options_win.configure(fg_color=self.COLOR_BG)
        self.options_win.wm_transient(self.root)
        self.options_win.lift()
        self.options_win.focus_force()
        self.options_win.bind("<Escape>", lambda e: self.options_win.destroy())

        FONT_HEADER = ("Segoe UI", 16, "bold")
        FONT_BODY = ("Malgun Gothic", 14, "bold")

        dropdown_style = {
            "font": FONT_BODY,
            "dropdown_font": FONT_BODY,
            "fg_color": self.COLOR_INPUT,
            "button_color": self.COLOR_BTN_DARK,
            "button_hover_color": self.COLOR_BTN_DARK_HOVER,
            "dropdown_fg_color": "#1e212b",
            "dropdown_hover_color": self.COLOR_BTN_PRIMARY,
            "dropdown_text_color": self.COLOR_TEXT_MAIN,
            "text_color": self.COLOR_TEXT_MAIN,
            "corner_radius": 6,
            "state": "readonly"
        }

        scroll_frame = ctk.CTkScrollableFrame(self.options_win, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=(5, 0))

        gen_panel = ctk.CTkFrame(scroll_frame, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        gen_panel.pack(fill="x", padx=10, pady=(5, 5))
        
        ctk.CTkLabel(gen_panel, text="일반 옵션", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(12, 8))
        
        trans_frame = ctk.CTkFrame(gen_panel, fg_color="transparent")
        trans_frame.pack(fill="x", padx=16, pady=5)
        ctk.CTkLabel(trans_frame, text="UI 투명도", width=120, anchor="w", font=FONT_BODY, text_color=self.COLOR_TEXT_SUB).pack(side="left")
        
        trans_var = tk.DoubleVar(value=self.config.get("ui_transparency", 1.0))
        def update_transparency(val):
            self.root.attributes("-alpha", float(val))
            self.config["ui_transparency"] = float(val)
            self.save_config()
            
        ctk.CTkSlider(trans_frame, from_=0.3, to=1.0, variable=trans_var, command=update_transparency).pack(side="left", fill="x", expand=True, padx=10)
        
        min_frame = ctk.CTkFrame(gen_panel, fg_color="transparent")
        min_frame.pack(fill="x", padx=16, pady=(10, 5))
        
        min_var = tk.BooleanVar(value=self.config.get("minimize_to_tray_on_launch", False))
        close_var = tk.BooleanVar(value=self.config.get("close_on_launch", False))
        
        def update_min():
            if min_var.get():
                close_var.set(False)
            self.config["minimize_to_tray_on_launch"] = min_var.get()
            self.config["close_on_launch"] = close_var.get()
            self.save_config()
            
        def update_close():
            if close_var.get():
                min_var.set(False)
            self.config["minimize_to_tray_on_launch"] = min_var.get()
            self.config["close_on_launch"] = close_var.get()
            self.save_config()
            
        ctk.CTkCheckBox(min_frame, text="게임 실행 시 트레이로 최소화", variable=min_var, font=FONT_BODY, text_color=self.COLOR_TEXT_MAIN, command=update_min).pack(anchor="w", pady=(0, 10))
        ctk.CTkCheckBox(min_frame, text="게임 실행 시 런처 종료", variable=close_var, font=FONT_BODY, text_color=self.COLOR_TEXT_MAIN, command=update_close).pack(anchor="w")

        res_frame = ctk.CTkFrame(gen_panel, fg_color="transparent")
        res_frame.pack(fill="x", padx=16, pady=(10, 16))
        ctk.CTkLabel(res_frame, text="창모드 해상도", width=120, anchor="w", font=FONT_BODY, text_color=self.COLOR_TEXT_SUB).pack(side="left")

        res_var = tk.StringVar(value=self.config.get("window_resolution", "1600x900(추천)"))
        res_options = ["640x480(순정해상도)", "800x600", "1024x768", "1280x720(추천)", "1280x960", "1600x900(추천)", "1920x1080", "2048x1152", "2560x1440"]
        
        self.prev_resolution = res_var.get()

        def check_resolution(val):
            try:
                clean_val = val.split('(')[0].strip()
                sel_w, sel_h = map(int, clean_val.split('x'))
                mon_w = ctypes.windll.user32.GetSystemMetrics(0)
                mon_h = ctypes.windll.user32.GetSystemMetrics(1)
                
                if sel_w > mon_w or sel_h > mon_h:
                    messagebox.showwarning("경고", "해당 설정은 모니터 해상도를 초과합니다.")
                    res_var.set(self.prev_resolution)
                    return
            except:
                pass
                
            self.prev_resolution = val
            self.config["window_resolution"] = val
            self.save_config()

        ctk.CTkComboBox(res_frame, variable=res_var, values=res_options, command=check_resolution, **dropdown_style).pack(side="left", fill="x", expand=True, padx=10)

        # ★게임창 중앙 정렬(창모드 해상도 하단) — 체크박스/라디오 아님, 클릭하면 X/Y 중앙값으로 게임창 이동
        center_frame = ctk.CTkFrame(gen_panel, fg_color="transparent")
        center_frame.pack(fill="x", padx=16, pady=(0, 14))
        self._center_btn = ctk.CTkButton(center_frame, text="⊹  게임창 중앙 정렬", height=36, font=FONT_BODY,
                                          fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1,
                                          hover_color=self.COLOR_BTN_DARK_HOVER, command=self.center_game_window)
        self._center_btn.pack(fill="x")

        # ★플레이어 색상(플레이/관전/리플레이 공통 — 오버레이설정에서 옵션으로 이동)
        color_panel = ctk.CTkFrame(scroll_frame, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        color_panel.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(color_panel, text="플레이어 색상", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(color_panel, text="내 화면에만 적용 (플레이/관전/리플레이 모두 실시간). 다른 사람은 영향 없음.",
                     font=("Malgun Gothic", 11), text_color=self.COLOR_TEXT_SUB, justify="left").pack(anchor="w", padx=16, pady=(0, 6))
        ctk.CTkButton(color_panel, text="🎨  플레이어 색상 설정", height=38, font=FONT_BODY,
                      fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1,
                      hover_color=self.COLOR_BTN_DARK_HOVER, command=self.open_color_options).pack(anchor="w", padx=16, pady=(0, 14))

        btn_frame = ctk.CTkFrame(self.options_win, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=(0, 10), padx=20)
        ctk.CTkButton(btn_frame, text="닫기", command=self.options_win.destroy, fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER).pack(side="right", expand=True, fill="x", padx=5)

    def open_settings_window(self):
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.lift()
            self.settings_win.focus_force()
            return

        self.settings_win = ctk.CTkToplevel(self.root)
        self.settings_win.title("실행 경로 설정")
        self.settings_win.geometry(self._get_popup_geometry(560, 400))
        self.settings_win.resizable(False, False)
        self.settings_win.configure(fg_color=self.COLOR_BG)
        self.settings_win.wm_transient(self.root)
        self.settings_win.lift()
        self.settings_win.focus_force()
        self.settings_win.bind("<Escape>", lambda e: self.settings_win.destroy())
        
        FONT_HEADER = ("Segoe UI", 16, "bold")
        FONT_BODY = ("Malgun Gothic", 14, "bold")

        path_panel = ctk.CTkFrame(self.settings_win, fg_color=self.COLOR_PANEL, border_color=self.COLOR_BORDER, border_width=1, corner_radius=8)
        path_panel.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(path_panel, text="실행파일 및 리플레이폴더 경로 지정", font=FONT_HEADER, text_color=self.COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(12, 8))

        path_inner = ctk.CTkFrame(path_panel, fg_color="transparent")
        path_inner.pack(fill="x", padx=16, pady=(0, 16))
        path_inner.columnconfigure(1, weight=1)

        def create_path_row_toplevel(row_idx, label_text, config_key, is_dir=False):
            ctk.CTkLabel(path_inner, text=label_text, width=80, anchor="w", font=FONT_BODY, text_color=self.COLOR_TEXT_SUB).grid(row=row_idx, column=0, pady=6, sticky="w")
            
            display_path = self.config[config_key] if self.config[config_key] else "지정되지 않음"
            entry_var = tk.StringVar(value=display_path)
            
            entry = ctk.CTkEntry(path_inner, textvariable=entry_var, height=34, fg_color=self.COLOR_INPUT, 
                                 border_color=self.COLOR_BORDER, text_color=self.COLOR_TEXT_MAIN, font=FONT_BODY, state="readonly")
            entry.grid(row=row_idx, column=1, padx=(8, 8), pady=6, sticky="ew")
            
            def make_cmd(k, v, d):
                return lambda: self.browse_directory(k, v) if d else self.browse_file(k, v)
            
            btn = ctk.CTkButton(path_inner, text="찾기", width=55, height=34, font=FONT_BODY, 
                                fg_color=self.COLOR_BTN_DARK, hover_color=self.COLOR_BTN_DARK_HOVER, text_color=self.COLOR_TEXT_MAIN,
                                command=make_cmd(config_key, entry_var, is_dir))
            btn.grid(row=row_idx, column=2, pady=6)

        create_path_row_toplevel(0, "높은 해상도", "path_hd")
        create_path_row_toplevel(1, "기본 해상도", "path_vanilla")
        create_path_row_toplevel(2, "맵 에디터", "path_editor")
        create_path_row_toplevel(3, "리플레이 폴더", "path_replay", is_dir=True)

        btn_frame = ctk.CTkFrame(self.settings_win, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=20, padx=20)
        ctk.CTkButton(btn_frame, text="닫기", width=100, command=self.settings_win.destroy, fg_color=self.COLOR_BTN_DARK, border_color=self.COLOR_BORDER, border_width=1, hover_color=self.COLOR_BTN_DARK_HOVER).pack(side="right")

    def browse_file(self, config_key, string_var):
        filepath = filedialog.askopenfilename(
            title="실행 파일 선택",
            filetypes=[("실행 파일", "*.exe"), ("모든 파일", "*.*")]
        )
        if filepath:
            self.config[config_key] = filepath
            self.save_config()
            string_var.set(filepath)
            
    def browse_directory(self, config_key, string_var):
        dirpath = filedialog.askdirectory(title="폴더 선택")
        if dirpath:
            self.config[config_key] = dirpath
            self.save_config()
            string_var.set(dirpath)

    def inject_ddraw_ini(self, target_dir):
        ini_path = os.path.join(target_dir, "ddraw.ini")
        mode = self.display_var.get()
        res_str = self.config.get("window_resolution", "1600x900(추천)")
        
        try:
            clean_res = res_str.split('(')[0].strip()
            sel_w, sel_h = clean_res.split('x')
        except:
            sel_w, sel_h = "1024", "768"

        # 1. Exclusive 모드: 고정 텍스트 사용
        if mode == "exclusive":
            ini_content = """[ddraw]
windowed=false
fullscreen=false
toggle_borderless=false
boxing=false
fix_window_style=false
resizing=false
maintas=false
handlemouse=true
adjmouse=true
maxfps=-1
accuratetimers=false
singlecpu=true
renderer=opengl
vsync=false
shader=Bicubic
devmode=false
savesettings=1
keytogglefullscreen=0x0D
keytogglemaximize=0x22
keyunlockcursor1=0x09
keyunlockcursor2=0xA3
keyscreenshot=0
toggle_upscaled=false
d3d9_filter=2
border=false
maxgameticks=0
noactivateapp=false
resolutions=0
minfps=0
posX=0
posY=0"""
        
        # 2. Borderless, Windowed 모드: 위치 로직 통합 및 분리 (강제보정 제거)
        else:
            try:
                pos_x = int(self.config.get("game_pos_x", 0))
            except ValueError:
                pos_x = 0
            
            try:
                pos_y = int(self.config.get("game_pos_y", 30))
            except ValueError:
                pos_y = 30
            
            # 여기서 mode와 상관없이 저장된 posX, posY 값을 무조건 삽입.
            extra_res_str = f"width={sel_w}\nheight={sel_h}\nposX={pos_x}\nposY={pos_y}\n"
            
            if mode == "borderless":
                ini_content = DDRAW_TEMPLATE.format(
                    windowed="true", fullscreen="true", toggle_borderless="true", 
                    extra_res=extra_res_str
                )
            elif mode == "windowed":
                ini_content = DDRAW_TEMPLATE.format(
                    windowed="true", fullscreen="false", toggle_borderless="true", 
                    extra_res=extra_res_str
                )
            else:
                return False
            
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write(ini_content)
        except Exception as e:
            messagebox.showerror("오류", f"ddraw.ini 파일 작성에 실패했습니다.\n{e}")
            return False
        return True

    def launch_game(self, config_key):
        target_path = self.config.get(config_key, "")
        if not target_path or not os.path.exists(target_path):
            messagebox.showerror("실행 오류", "해당 모드의 실행 파일 경로가 지정되지 않았거나 올바르지 않습니다.\n좌측 상단의 '경로 설정' 버튼을 눌러 경로 지정해주세요.")
            return

        proc_name = os.path.basename(target_path)
        target_dir = os.path.dirname(target_path)

        running_procs = []
        pid_file = "last_game_pid.txt"
        KNOWN_GAME_EXES = ["Rank1024.exe", "Ranker800.exe", "Ranker800", "MapEditor_개발자용.exe", "MapEditor_개발자용", "JurassicWar2.exe"]
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    last_pid = int(f.read().strip())
                if psutil.pid_exists(last_pid):
                    p = psutil.Process(last_pid)
                    if p.name() in KNOWN_GAME_EXES or p.name() == proc_name:
                        running_procs.append(p)
            except:
                pass

        if running_procs:
            if messagebox.askyesno("알림", "백그라운드에 실행된 The Ranker를 종료하고 시작하시겠습니까?"):
                for proc in running_procs:
                    try:
                        proc.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                try:
                    gone, alive = psutil.wait_procs(running_procs, timeout=3.0)
                    for proc in alive:
                        try:
                            proc.kill()
                        except:
                            pass
                except:
                    pass
                
                self.root.after(1500, lambda: self._execute_launch_process(config_key, target_path, target_dir, pid_file, KNOWN_GAME_EXES))
            else:
                return 
        else:
            self._execute_launch_process(config_key, target_path, target_dir, pid_file, KNOWN_GAME_EXES)

    def _execute_launch_process(self, config_key, target_path, target_dir, pid_file, KNOWN_GAME_EXES):
        if config_key in ["path_hd", "path_vanilla"]:
            if not self.inject_ddraw_ini(target_dir):
                return

        try:
            selected_bgm = getattr(self, 'bgm_var', None)
            if selected_bgm:
                bgm_val = selected_bgm.get()
                src_bgm_name = "Jw2_15(old).trc" if "오리지널" in bgm_val else "Jw2_15(new).trc"
                
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    
                src_path = os.path.join(base_dir, src_bgm_name)
                
                if not os.path.exists(src_path):
                    try:
                        temp_path = os.path.join(_res_dir(), src_bgm_name)
                        if os.path.exists(temp_path):
                            src_path = temp_path
                    except:
                        pass
                
                if os.path.exists(src_path):
                    target_bgm_path = os.path.join(target_dir, "Jw2_15.trc")
                    shutil.copy2(src_path, target_bgm_path)
        except Exception as e:
            pass

        try:
            proc = subprocess.Popen([target_path], cwd=target_dir)
            
            try:
                with open(pid_file, "w") as f:
                    f.write(str(proc.pid))
            except:
                pass

            def monitor_game_process():
                try:
                    proc.wait() 
                except:
                    pass
                time.sleep(0.5) 
                
                for p in psutil.process_iter(['name']):
                    try:
                        if p.info['name'] in KNOWN_GAME_EXES:
                            p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            if not self.config.get("close_on_launch", False):
                threading.Thread(target=monitor_game_process, daemon=True).start()
                # ★타이머/APM 스레드 제거됨(기능 삭제). 관전 오버레이는 런처 시작시 이미 자동실행됨(_autostart_spectator).
                if self.config.get("minimize_to_tray_on_launch", False):
                    self.minimize_to_tray()
            else:
                # ★런처 종속: 런처가 종료되면 관전 모니터도 함께 종료(옛 '독립 유지' 로직 제거)
                self.close_spectator_monitor()
                self.root.destroy()
                os._exit(0)

        except Exception as e:
            messagebox.showerror("실행 오류", f"프로세스 실행에 실패했습니다.\n{e}")

    def launch_selected_game(self):
        selected_mode = self.game_mode_var.get()
        
        if selected_mode == "넓은 시야 (1024x768)":
            config_key = "path_hd"
        elif selected_mode == "기본 시야 (640x480)":
            config_key = "path_vanilla"
        elif selected_mode == "맵 에디터":
            config_key = "path_editor"
        else:
            return

        self.launch_game(config_key)


if __name__ == "__main__":
    # [신규 추가] PyInstaller 컴파일 환경에서 독립된 프로세스를 안전하게 생성하기 위해 필요
    multiprocessing.freeze_support()
    
    mutex_name = "Jw2Launcher_SingleInstance_Mutex_v1"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183:
        tmp_root = tk.Tk()
        tmp_root.withdraw()
        messagebox.showwarning("실행 경고", "런처가 이미 실행 중입니다.")
        sys.exit(0)

    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    app = JurassicLauncher(root)
    root.mainloop()