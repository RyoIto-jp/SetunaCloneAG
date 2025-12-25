import tkinter as tk
from PIL import ImageGrab

class CaptureTool:
    """
    透明なオーバーレイを使用して画面領域をキャプチャするツール。
    ユーザーはマウスドラッグで矩形領域を選択できます。
    """
    def __init__(self, master, callback):
        """
        キャプチャツールを初期化します。
        
        Args:
            master: 親となるTkinterウィジェット。
            callback: キャプチャされた画像（キャンセル時はNone）を受け取るコールバック関数。
        """
        self.master = master
        self.callback = callback
        
        # 全画面オーバーレイを作成
        self.top = tk.Toplevel(master)
        self.top.attributes('-fullscreen', True)
        self.top.attributes('-alpha', 0.3)
        self.top.config(cursor="cross")
        
        # Escapeキーで閉じる
        self.top.bind("<Escape>", lambda e: self.close())
        
        self.canvas = tk.Canvas(self.top, highlightthickness=0, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 選択用の変数
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", lambda e: self.close()) # 右クリックでキャンセル

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, 
            outline='red', width=2, fill='white', stipple='gray25' 
        )

    def on_drag(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        end_x, end_y = (event.x, event.y)
        
        # 有効な座標を保証
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        # オーバーレイを即座に閉じる
        self.top.destroy()
        self.top.update() # キャプチャ前に確実に画面から消す
        
        if x2 - x1 > 5 and y2 - y1 > 5: # 最小サイズチェック
            # キャプチャロジック
            # 古いPILとの互換性を考慮
            try:
                image = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
            except TypeError:
                 # 古いPillow用のフォールバック
                image = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                
            self.callback(image, x1, y1)
        else:
            self.callback(None, None, None)

    def close(self):
        self.top.destroy()
        self.callback(None, None, None)
