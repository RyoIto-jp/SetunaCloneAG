import tkinter as tk
import threading
from pynput import keyboard
from capture_tool import CaptureTool
from snippet_window import SnippetManager
import pystray
from PIL import Image, ImageDraw

class TrayIcon:
    """
    pystrayを使用してシステムトレイアイコンを管理します。
    Tkinterのメインループをブロックしないよう、別スレッドで実行されます。
    """
    def __init__(self, app):
        """
        Args:
            app: メインのSetunaCloneAppインスタンス。
        """
        self.app = app
        self.icon = None
        self.thread = None

    def create_image(self):
        """アイコン画像を生成または読み込みます。"""
        try:
             # assets/favicon.icoを読み込む
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            favicon_path = os.path.join(base_dir, "assets", "favicon.ico")
            return Image.open(favicon_path)
        except Exception as e:
            print(f"Failed to load favicon.ico: {e}. Using default icon.")
            # シンプルなアイコンを作成（例：青い四角に白い窓）
            width = 64
            height = 64
            color1 = (0, 0, 255)
            color2 = (255, 255, 255)
            image = Image.new('RGB', (width, height), color1)
            dc = ImageDraw.Draw(image)
            dc.rectangle((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=color2)
            return image

    def run(self):
        """トレイアイコンのループを実行します。"""
        image = self.create_image()
        menu = pystray.Menu(
            pystray.MenuItem("Capture", self.on_capture),
            pystray.MenuItem("Exit", self.on_exit)
        )
        self.icon = pystray.Icon("SetunaClone", image, "Setuna Clone", menu)
        self.icon.run()

    def start_thread(self):
        """トレイアイコンをバックグラウンドスレッドで開始します。"""
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def on_capture(self, icon, item):
        """「Capture」メニュー項目のコールバック。"""
        self.app.on_activate_capture()

    def on_exit(self, icon, item):
        """「Exit」メニュー項目のコールバック。"""
        # すべてを停止する必要があります
        icon.stop()
        self.app.quit()

class SetunaCloneApp:
    """
    メインアプリケーションクラス。
    グローバルホットキー、付箋管理、Tkinterルートウィンドウを処理します。
    """
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw() # メインウィンドウを隠す
        self.snippet_manager = SnippetManager(self.root)
        
        # ホットキーリスナー
        self.listener = keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+z': self.on_activate_capture
        })
        self.listener.start()
        
        # トレイアイコン
        self.tray = TrayIcon(self)
        self.tray.start_thread()

        print("SETUNA2 Clone started. Press Ctrl+Shift+Z to capture.")

    def on_activate_capture(self):
        """ホットキーまたはトレイからキャプチャがアクティブ化されたときに呼び出されます。"""
        print("Capture triggered!")
        # GUI更新をメインスレッドで実行するために after を使用
        self.root.after(0, self.start_capture)

    def start_capture(self):
        """キャプチャツールを開始します。"""
        CaptureTool(self.root, self.on_capture_complete)

    def on_capture_complete(self, image, x=None, y=None):
        """キャプチャ完了時のコールバック。"""
        if image:
            self.snippet_manager.create_snippet(image, x, y)

    def quit(self):
        """アプリケーションをクリーンアップして終了します。"""
        self.root.quit()
        # 必要であればリスナーを停止（デーモンスレッドなら通常は終了するが明示的に）
        self.listener.stop()

    def run(self):
        """メインイベントループを開始します。"""
        self.root.mainloop()

if __name__ == "__main__":
    app = SetunaCloneApp()
    app.run()
