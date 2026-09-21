"""پویش همهٔ ترکیب‌های پوسته × زبان × صفحه، برای یافتن خطای ترسیم."""
import os,sys,traceback
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
qt=QApplication([])
from app.application import Application
from localization import Translator
from ui.themes import ThemeManager
from ui.windows import MainWindow
from ui.controllers import MainController
fails=[]
for lang in ('fa','en'):
    tr=Translator(lang); tr.load()
    for theme in ThemeManager.available():
        try:
            app=Application(); th=ThemeManager(); th.apply(qt,theme.key)
            w=MainWindow(tr,th); c=MainController(app,w,tr,th,qt)
            w.apply_direction(); w.retranslate(); w.apply_theme_tokens()
            for i in range(len(w.PAGES)):
                w.go_to_page(i); qt.processEvents()
            sp=c.settings_page
            for t in range(sp.tabs.count()):
                sp.tabs.setCurrentIndex(t); qt.processEvents()
            c._refresh_search_suggestions()
            # چند ردیف بازار با و بدون تاریخچه
            c.markets.set_rows([
                {'symbol':'BTC/USDT','price':1.0,'change_percent':2.0,'history':[1,2,3]},
                {'symbol':'ETH/USDT','price':1.0,'change_percent':-2.0},
            ])
            c.chat.add_message('سلام', is_user=True)
            c.chat.add_message('درود', is_user=False)
            c.chat.apply_theme(th.tokens)
            qt.processEvents()
            w.deleteLater()
        except Exception as e:
            fails.append(f"{lang}/{theme.key}: {e}")
            traceback.print_exc()
print("FAILURES:",len(fails))
for f in fails: print(" -",f)
