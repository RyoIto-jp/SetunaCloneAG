import tkinter as tk

"""
ウィンドウ管理および画面プロパティに関するユーティリティ関数。
"""

def get_screen_size(root: tk.Tk = None):
    """
    画面の幅と高さを取得します。
    """
    if root is None:
        root = tk.Tk()
        root.withdraw()
    
    return root.winfo_screenwidth(), root.winfo_screenheight()

def center_window(window, width, height):
    """
    Tkinterウィンドウを画面の中央に配置します。
    """
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    x = (screen_width / 2) - (width / 2)
    y = (screen_height / 2) - (height / 2)
    
    window.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
