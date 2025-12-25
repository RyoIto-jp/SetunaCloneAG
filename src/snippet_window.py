import tkinter as tk
from tkinter import filedialog, ttk
from PIL import ImageTk, Image, ImageDraw
import io
import win32clipboard
import win32gui
import win32con

class SnippetManager:
    """
    アクティブな付箋とグループウィンドウのコレクションを管理します。
    付箋の作成、削除、結合を処理します。
    """
    def __init__(self, root):
        self.root = root
        self.snippets = []

    def create_snippet(self, image, x=None, y=None):
        window = SnippetWindow(self.root, image, self.on_snippet_close, self, x=x, y=y)
        self.snippets.append(window)
        
    def on_snippet_close(self, snippet):
        if snippet in self.snippets:
            self.snippets.remove(snippet)

    def merge_all_snippets(self):
        if len(self.snippets) < 2:
            return # 結合するものがない

        # グループウィンドウを作成
        # 実際の付箋のみをフィルタリング（既存のグループウィンドウはオプションだが、今は単純化のためスキップ）
        # 単純な結合として、すべてのアクティブな付箋画像を取得
        
        images_to_merge = []
        windows_to_close = []
        
        for s in list(self.snippets):
            if isinstance(s, SnippetWindow):
                images_to_merge.append(s.original_image)
                windows_to_close.append(s)
            elif isinstance(s, GroupWindow):
                # 既存のグループを結合したい場合は、画像を取り出す必要がある
                pass # 複雑さを避けるため今はスキップ
        
        if len(images_to_merge) < 2:
            return

        for s in windows_to_close:
            s.close()
            
        group_window = GroupWindow(self.root, images_to_merge, self.on_snippet_close, self)
        self.snippets.append(group_window)


class SnippetLogicMixin:
    """SnippetWindowとGroupWindowで共有されるメソッド"""
    
    def generate_framed_image(self, img, scale=1.0):
        """
        白い枠線（左/上）と影/暗い枠線（右/下）を追加します。
        これはSetunaの視覚スタイルを模倣しています。
        
        Args:
            img: PIL Imageオブジェクト。
            scale: 現在の倍率（例: 1.0, 0.5, 2.0）。
            
        Returns:
            枠線と影が適用された新しいPIL Image。
        """
        # 必要に応じてリサイズ
        w, h = img.size
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        if scale != 1.0:
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            resized = img.copy() 
            
        border_width = 1 
        shadow_width = 2 
        
        # 枠線に基づいて新しいフレームサイズを計算
        frame_w = new_w + border_width + shadow_width
        frame_h = new_h + border_width + shadow_width
        
        # 影の色（濃い灰色）でベース画像を作成
        frame = Image.new('RGB', (frame_w, frame_h), (50, 50, 50)) 
        draw = ImageDraw.Draw(frame)
        
        # 左上の枠線分のオフセットを考慮してリサイズ画像を貼り付け
        frame.paste(resized, (border_width, border_width))
        
        # 上と左に白い枠線を描画
        draw.line([(0, 0), (frame_w - 1, 0)], fill=(255, 255, 255), width=border_width)
        draw.line([(0, 0), (0, frame_h - 1)], fill=(255, 255, 255), width=border_width)
        
        return frame

    def copy_image_to_clipboard(self, image):
        """
        指定されたPIL画像をDIB形式でWindowsクリップボードにコピーします。
        """
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:] # DIBデータを取得するためにBMPヘッダーを削除
        output.close()
        
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            print("Copied to clipboard")
        except Exception as e:
            print(f"Failed to copy: {e}")

    def save_image_to_file(self, image):
        """
        画像をファイルに保存するようユーザーに促します。
        """
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
        )
        if filename:
            image.save(filename)

    def hide_from_taskbar(self):
        """
        ウィンドウにWS_EX_TOOLWINDOWスタイルを適用してタスクバーから隠します。
        """
        try:
            self.window.update_idletasks()
            hwnd = win32gui.GetParent(self.window.winfo_id())
            # winfo_id()はラッパーのIDを返すことがあるためGetParentで実際のHWND取得を試みるが、
            # TkinterのToplevelではwinfo_id()自体がHWNDであることも多い。
            # ここでは確実性を高めるため、winfo_id() をそのまま使う。
            # GetParentを使うとデスクトップウィンドウなどが返ってくるリスクがある。
            hwnd = self.window.winfo_id()
            
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            style = style | win32con.WS_EX_TOOLWINDOW
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
        except Exception as e:
            print(f"Failed to hide from taskbar: {e}")


class SnippetWindow(SnippetLogicMixin):
    """
    単一のフローティング付箋ウィンドウ。
    移動、リサイズ、描画、トリミング、ホットキーをサポートします。
    """
    def __init__(self, master, image, close_callback, manager=None, x=None, y=None):
        """
        新しいSnippetWindowを初期化します。

        Args:
            master (tk.Tk or tk.Toplevel): 親のTkinterウィンドウ。
            image (PIL.Image.Image): 付箋に表示する初期画像。
            close_callback (callable): 付箋ウィンドウが閉じられたときに呼び出す関数。
            manager (SnippetManager, optional): この付箋を管理するマネージャー。デフォルトはNone。
            x (int, optional): 初期表示X座標。
            y (int, optional): 初期表示Y座標。
        """
        self.manager = manager
        self.original_image = image
        self.scale = 1.0
        self.is_minimized = False # 階調化（シェーディング）モード用
        self.opacity = 1.0
        self.close_callback = close_callback
        
        # 状態フラグ
        self.drawing_mode = False
        self.last_draw_x = None
        self.last_draw_y = None
        
        # 表示用の視覚効果を適用
        self.current_display_image = self.generate_framed_image(self.original_image, self.scale)
        self.tk_image = ImageTk.PhotoImage(self.current_display_image)
        
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True) # フレームレスウィンドウ
        self.hide_from_taskbar()
        self.window.attributes('-topmost', True) # 常に最前面
        
        w, h = self.current_display_image.size
        
        if x is not None and y is not None:
             self.window.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
        else:
            # 初期位置を中央に
            screen_width = master.winfo_screenwidth()
            screen_height = master.winfo_screenheight()
            pos_x = (screen_width - w) // 2
            pos_y = (screen_height - h) // 2
            self.window.geometry(f"{w}x{h}+{int(pos_x)}+{int(pos_y)}")

        self.label = tk.Label(self.window, image=self.tk_image, bd=0)
        self.label.pack(fill=tk.BOTH, expand=True)

        # イベントバインド
        self.label.bind("<ButtonPress-1>", self.start_move)
        self.label.bind("<ButtonRelease-1>", self.stop_move)
        self.label.bind("<B1-Motion>", self.do_move)
        self.label.bind("<Button-3>", self.show_context_menu)
        self.label.bind("<Double-Button-1>", self.toggle_shading)
        self.label.bind("<MouseWheel>", self.on_mouse_wheel)
        self.label.bind("<Enter>", self.on_enter)
        self.label.bind("<Leave>", self.on_leave)
        
        # ホットキー
        self.window.bind("<q>", lambda e: self.close())
        self.window.bind("<Control-c>", lambda e: self.copy_image_to_clipboard(self.original_image))
        self.window.bind("<Control-x>", self.cut_image)
        self.window.bind("<t>", self.toggle_trim_mode)
        self.window.bind("<Control-z>", self.undo)
        self.window.bind("<e>", lambda event: self.toggle_drawing_mode())
        
        # 描画状態
        self.drawing_mode = False
        self.last_draw_x = None
        self.last_draw_y = None
        
        # トリミング状態
        self.trim_mode = False
        self.trim_start_x = None
        self.trim_start_y = None
        self.trim_rect_id = None
        
        self.is_hovering = False
        self.hover_opacity = 0.6 # ホバー時の透明度 (0.0 - 1.0)
        
        self.history = [] # アンドゥ用スタック
        self.x = None
        self.y = None
        
        self.create_context_menu()

    def undo(self, event=None):
        if not self.history:
            return
        
        # 最後の状態を復元
        last_state = self.history.pop()
        self.original_image = last_state
        self.update_display()
        print("Undo performed not trim or anything")

    def save_state(self):
        # メモリ問題を避けるため履歴サイズを制限 (例: 20)
        if len(self.history) > 20:
            self.history.pop(0)
        self.history.append(self.original_image.copy())

    def on_enter(self, event):
        self.is_hovering = True
        # キーイベントを受け取るためにフォーカスを設定
        self.window.focus_force()

    def on_leave(self, event):
        self.is_hovering = False

    def update_opacity(self):
        # 目標の透明度を決定
        # 移動中（ドラッグ中）の場合、透明度を適用
        is_moving = (self.x is not None)
        
        if is_moving:
             # 移動中/クリック中は背景が見えるように半透明にする
            self.window.attributes('-alpha', 0.5)
        else:
            self.window.attributes('-alpha', self.opacity)

    def cut_image(self, event=None):
        self.copy_image_to_clipboard(self.original_image)
        self.close()

    def start_move(self, event):
        if self.drawing_mode:
            self.start_draw(event)
        elif self.trim_mode:
            self.start_trim(event)
        else:
            self.x = event.x
            self.y = event.y
            self.update_opacity()

    def stop_move(self, event):
        if self.drawing_mode:
            self.stop_draw(event)
        elif self.trim_mode:
            self.stop_trim(event)
        else:
            self.x = None
            self.y = None
            self.update_opacity()

    def do_move(self, event):
        """ドラッグ、描画、またはトリミングのマウス移動を処理します。"""
        if self.drawing_mode:
            self.do_draw(event)
        elif self.trim_mode:
            self.do_trim(event)
        else:
            if self.x is None or self.y is None: return
            # 差分を計算してウィンドウを移動
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.window.winfo_x() + deltax
            y = self.window.winfo_y() + deltay
            self.window.geometry(f"+{x}+{y}")
            
    # 描画メソッド
    def start_draw(self, event):
        self.save_state() # ストローク前に保存
        # ストローク座標を画像の縮尺に合わせて変換
        self.last_draw_x = (event.x - 1) / self.scale
        self.last_draw_y = (event.y - 1) / self.scale

    def do_draw(self, event):
        if self.last_draw_x is None: return
        
        curr_x = (event.x - 1) / self.scale
        curr_y = (event.y - 1) / self.scale
        
        # 元画像に描画（永続的）
        draw = ImageDraw.Draw(self.original_image)
        # 縮尺に基づいて線の太さを調整 -> 縮小表示時に見やすくするため太くする
        width = int(3/self.scale) if self.scale < 1 else 3
        draw.line([self.last_draw_x, self.last_draw_y, curr_x, curr_y], fill='red', width=width)
        
        self.last_draw_x = curr_x
        self.last_draw_y = curr_y
        self.update_display()

    def stop_draw(self, event):
        self.last_draw_x = None
        self.last_draw_y = None
        
    # トリミングメソッド
    def toggle_trim_mode(self, event=None):
        self.trim_mode = not self.trim_mode
        self.drawing_mode = False # 排他制御
        if self.trim_mode:
            self.label.config(cursor="cross")
            print("Trim mode ON")
        else:
            self.label.config(cursor="arrow")
            # 一時的な描画をクリア
            self.update_display()
            print("Trim mode OFF")

    def start_trim(self, event):
        self.trim_start_x = event.x
        self.trim_start_y = event.y

    def do_trim(self, event):
        if self.trim_start_x is None: return
        # 視覚的フィードバック: 現在の表示画像のコピーに赤い矩形を描画
        img_copy = self.current_display_image.copy()
        draw = ImageDraw.Draw(img_copy)
        # 終了座標が開始座標より小さい場合の座標修正
        x1 = min(self.trim_start_x, event.x)
        y1 = min(self.trim_start_y, event.y)
        x2 = max(self.trim_start_x, event.x)
        y2 = max(self.trim_start_y, event.y)
        
        draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
        
        self.tk_image = ImageTk.PhotoImage(img_copy)
        self.label.config(image=self.tk_image)

    def stop_trim(self, event):
        """マウスリリース時に切り取り操作を実行します。"""
        if self.trim_start_x is None: return
        
        end_x = event.x
        end_y = event.y
        
        # 表示座標での境界ボックスを計算
        x1 = min(self.trim_start_x, end_x)
        y1 = min(self.trim_start_y, end_y)
        x2 = max(self.trim_start_x, end_x)
        y2 = max(self.trim_start_y, end_y)
        
        # 非常に小さい選択（誤クリック）を無視
        if x2 - x1 < 5 or y2 - y1 < 5:
            self.update_display() 
            return
            
        # 表示座標を元画像の座標に変換するロジック:
        # 1. 枠線のオフセット(1px)を削除
        # 2. 倍率で割る
        
        orig_x1 = int((x1 - 1) / self.scale)
        orig_y1 = int((y1 - 1) / self.scale)
        orig_x2 = int((x2 - 1) / self.scale)
        orig_y2 = int((y2 - 1) / self.scale)
        
        # 画像の範囲内に座標を収める
        w, h = self.original_image.size
        orig_x1 = max(0, min(orig_x1, w))
        orig_y1 = max(0, min(orig_y1, h))
        orig_x2 = max(0, min(orig_x2, w))
        orig_y2 = max(0, min(orig_y2, h))
        
        # 有効な領域が存在することを確認
        if orig_x2 - orig_x1 > 0 and orig_y2 - orig_y1 > 0:
            # 切り取り実行
            self.save_state() # トリミング前に保存
            self.original_image = self.original_image.crop((orig_x1, orig_y1, orig_x2, orig_y2))
            
            # 新しい切り取り画像で表示を更新
            self.update_display()
            # 新しい画像サイズに合わせてウィンドウをリサイズ
            new_w, new_h = self.current_display_image.size
            self.window.geometry(f"{new_w}x{new_h}")
            
        self.trim_start_x = None
        self.toggle_trim_mode() # トリミングモードを自動終了

    def update_display(self):
        self.current_display_image = self.generate_framed_image(self.original_image, self.scale)
        self.tk_image = ImageTk.PhotoImage(self.current_display_image)
        self.label.config(image=self.tk_image)

    def on_mouse_wheel(self, event):
        if event.delta > 0:
            new_scale = self.scale + 0.1
        else:
            new_scale = self.scale - 0.1
        if new_scale < 0.1: new_scale = 0.1
        if new_scale > 3.0: new_scale = 3.0
        self.set_scale(new_scale)

    def create_context_menu(self):
        self.menu = tk.Menu(self.window, tearoff=0)
        self.menu.add_command(label="Toggle Pen Mode (E)", command=self.toggle_drawing_mode)
        self.menu.add_command(label="Trim Mode (T)", command=self.toggle_trim_mode)
        # 管理機能で結合が可能かチェック
        if self.manager and len([s for s in self.manager.snippets if isinstance(s, SnippetWindow)]) > 1:
            self.menu.add_command(label="Merge All Snippets", command=self.manager.merge_all_snippets)
            
        self.menu.add_separator()
        self.menu.add_command(label="Copy (Ctrl+C)", command=lambda: self.copy_image_to_clipboard(self.original_image))
        self.menu.add_command(label="Save As...", command=lambda: self.save_image_to_file(self.original_image))
        
        opacity_menu = tk.Menu(self.menu, tearoff=0)
        for op in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]:
            opacity_menu.add_command(label=f"{int(op*100)}%", command=lambda o=op: self.set_opacity(o))
        self.menu.add_cascade(label="Opacity", menu=opacity_menu)
        
        scale_menu = tk.Menu(self.menu, tearoff=0)
        for sc in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
             scale_menu.add_command(label=f"{int(sc*100)}%", command=lambda s=sc: self.set_scale(s))
        self.menu.add_cascade(label="Scale", menu=scale_menu)
        
        self.menu.add_separator()
        self.menu.add_command(label="Close (Q)", command=self.close)

    def toggle_drawing_mode(self):
        self.drawing_mode = not self.drawing_mode
        self.trim_mode = False
        if self.drawing_mode:
            self.label.config(cursor="cross")
        else:
            self.label.config(cursor="arrow")

    def show_context_menu(self, event):
        # 結合状態を動的にチェックするためにメニューを再生成
        self.create_context_menu()
        self.menu.post(event.x_root, event.y_root)

    def toggle_shading(self, event=None):
        if self.is_minimized:
            self.label.config(anchor='center')
            self.set_scale(self.prev_scale if hasattr(self, 'prev_scale') else 1.0)
            self.is_minimized = False
        else:
            self.prev_scale = self.scale
            self.is_minimized = True
            curr_w = self.window.winfo_width()
            curr_x = self.window.winfo_x()
            curr_y = self.window.winfo_y()
            self.window.geometry(f"{curr_w}x30+{curr_x}+{curr_y}") 
            self.label.config(anchor='n') 
            
    def set_opacity(self, alpha):
        self.opacity = alpha
        self.update_opacity()

    def set_scale(self, scale):
        self.scale = scale
        self.update_display()
        new_w, new_h = self.current_display_image.size
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.geometry(f"{new_w}x{new_h}+{x}+{y}")

    def close(self):
        self.window.destroy()
        if self.close_callback:
            self.close_callback(self)


class GroupWindow(SnippetLogicMixin):
    """
    複数の画像をタブ（ttk.Notebook）に設定するウィンドウ。
    SnippetWindowと似ていますが、複数画像を扱います。
    """
    def __init__(self, master, images, close_callback, manager=None):
        self.master = master
        self.manager = manager
        self.images = images
        self.close_callback = close_callback
        self.scale = 1.0
        
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True) 
        self.hide_from_taskbar()
        self.window.attributes('-topmost', True)
        
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        self.tabs = []
        self.tk_images = [] # GCを防ぐために参照を保持
        
        for i, img in enumerate(images):
            frame = tk.Frame(self.notebook, bg='black')
            self.notebook.add(frame, text=f"Img {i+1}")
            
            # ラベル
            framed_img = self.generate_framed_image(img, self.scale)
            tk_img = ImageTk.PhotoImage(framed_img)
            self.tk_images.append(tk_img)
            
            label = tk.Label(frame, image=tk_img, bd=0)
            label.pack(fill=tk.BOTH, expand=True)
            
             # イベントバインド
            label.bind("<ButtonPress-1>", self.start_move)
            label.bind("<ButtonRelease-1>", self.stop_move)
            label.bind("<B1-Motion>", self.do_move)
            label.bind("<Button-3>", self.show_context_menu)
            
            self.tabs.append({
                'frame': frame,
                'label': label,
                'image': img
            })
            
        # 最初の画像に基づいて初期サイズを設定
        self.update_geometry()
        
    def on_tab_changed(self, event):
        """タブ切り替え時にウィンドウサイズを更新します。"""
        self.update_geometry()
        
    def update_geometry(self):
        """現在選択されている画像に合わせてウィンドウをリサイズします。"""
        # 現在のタブ画像に合わせてウィンドウをリサイズ
        try:
            current_tab = self.notebook.select()
            if not current_tab: return 
            idx = self.notebook.index(current_tab)
            original_img = self.tabs[idx]['image']
            
            framed = self.generate_framed_image(original_img, self.scale)
            tk_img = ImageTk.PhotoImage(framed)
            self.tk_images[idx] = tk_img # 参照を更新
            self.tabs[idx]['label'].configure(image=tk_img)
            
            w, h = framed.size
            h += 25 # タブバーの高さ（概算）
            
            curr_x = self.window.winfo_x()
            curr_y = self.window.winfo_y()
            
            self.window.geometry(f"{w}x{h}+{curr_x}+{curr_y}")
        except Exception as e:
            print(f"Error updating geometry: {e}")
        
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.window.winfo_x() + deltax
        y = self.window.winfo_y() + deltay
        self.window.geometry(f"+{x}+{y}")
        
    def create_context_menu(self):
        self.curr_menu = tk.Menu(self.window, tearoff=0)
        idx = self.notebook.index(self.notebook.select())
        img = self.tabs[idx]['image']
        
        self.curr_menu.add_command(label="Copy", command=lambda: self.copy_image_to_clipboard(img))
        self.curr_menu.add_command(label="Save", command=lambda: self.save_image_to_file(img))
        self.curr_menu.add_separator()
        self.curr_menu.add_command(label="Close Group", command=self.close)

    def show_context_menu(self, event):
        self.create_context_menu()
        self.curr_menu.post(event.x_root, event.y_root)

    def close(self):
        self.window.destroy()
        if self.close_callback:
            self.close_callback(self)
