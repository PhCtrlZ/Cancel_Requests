# -*- coding: utf-8 -*-
# Facebook Friend Request Canceller (GUI by QtDesigner)
# Created by PhCtrlZ

import sys, time, re
from datetime import datetime
from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 👉 import giao diện từ QtDesigner
from QtGui import Ui_Dialog


# =========================================================
# ===============  THREAD CHÍNH  ===========================
# =========================================================
class CancelWorker(QThread):
    status_update = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, cookie_str, delay_sec=1.0):
        super().__init__()
        self.cookie_str = cookie_str
        self.delay_sec = delay_sec
        self.is_running = True
        self.is_paused = False
        self.cancelled = 0

    def stop(self):
        self.is_running = False
        self.status_update.emit("🛑 Dừng tiến trình...")

    def pause(self):
        self.is_paused = True
        self.status_update.emit("⏸ Tạm dừng...")

    def resume(self):
        self.is_paused = False
        self.status_update.emit("▶ Tiếp tục...")

    def parse_cookie(self, s):
        out=[]
        skip={"path","domain","expires","max-age","secure","httponly","samesite"}
        for p in s.split(';'):
            p=p.strip()
            if '=' not in p: continue
            k,v=p.split('=',1)
            if k.lower() in skip: continue
            out.append({'name':k.strip(),'value':v.strip(),'path':'/','domain':'.facebook.com'})
        return out

    def make_driver(self):
        opt=Options()
        opt.add_argument("--window-size=1440,960")
        opt.add_argument("--disable-gpu")
        opt.add_argument("--no-sandbox")
        opt.add_argument("--disable-dev-shm-usage")
        opt.add_argument("--headless=new")
        opt.add_argument("--lang=vi-VN,vi")
        opt.add_argument("--disable-blink-features=AutomationControlled")
        service=Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=opt)

    def run(self):
        drv=None
        try:
            self.status_update.emit("🚀 Đang khởi động Chrome...")
            drv=self.make_driver()

            drv.get("https://www.facebook.com/")
            for c in self.parse_cookie(self.cookie_str):
                try: drv.add_cookie(c)
                except: pass
            drv.refresh()
            WebDriverWait(drv,10).until(lambda d:d.get_cookie("c_user"))
            uid=(drv.get_cookie("c_user") or {}).get("value","N/A")

            drv.get("https://www.facebook.com/me")
            WebDriverWait(drv,10).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
            name = drv.execute_script("""
                try{
                    const og=document.querySelector('meta[property="og:title"]');
                    if(og) return og.content;
                    const h1=document.querySelector('h1');
                    if(h1) return h1.innerText;
                    return document.title||'Unknown';
                }catch(e){return 'Unknown';}
            """)
            self.status_update.emit(f"✅ Đăng nhập thành công!\n👤 {name}\n🆔 {uid}")

            # vào trang lời mời
            drv.get("https://www.facebook.com/friends/requests")
            WebDriverWait(drv,10).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
            time.sleep(1.5)
            try:
                btn=drv.find_element(By.XPATH,"//span[normalize-space()='Xem lời mời đã gửi']/ancestor::*[@role='button'][1]")
                drv.execute_script("arguments[0].scrollIntoView({block:'center'});arguments[0].click();", btn)
                self.status_update.emit("✅ Đã bấm 'Xem lời mời đã gửi'")
            except:
                self.status_update.emit("⚠ Không thấy nút 'Xem lời mời đã gửi'")
            time.sleep(3)

            js_click = """
                try{
                    const RX=/(Hủy|Huỷ|Cancel)/i;
                    const all=document.querySelectorAll('div[role="button"],button,a[role="button"],span[role="button"]');
                    for(const b of all){
                        const t=(b.innerText||'')+(b.getAttribute('aria-label')||'');
                        if(RX.test(t)){
                            b.scrollIntoView({block:'center'});
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }catch(e){return false;}
            """

            js_confirm = """
                try{
                    const RX=/(Xác nhận|Confirm|Cancel request|Hủy|Huỷ)/i;
                    const all=document.querySelectorAll('button,div[role="button"],a[role="button"]');
                    for(const b of all){
                        const t=(b.innerText||'')+(b.getAttribute('aria-label')||'');
                        if(RX.test(t)){b.click();return true;}
                    }
                    return false;
                }catch(e){return false;}
            """

            miss=0
            while self.is_running and miss<1:
                while self.is_paused: time.sleep(0.3)
                ok=drv.execute_script(js_click)
                if not ok:
                    miss+=1
                    self.status_update.emit(f"Đã hết lời mời để hủy hoặc không phát hiện nút hủy!")
                    drv.execute_script("window.scrollBy(0,800);")
                    time.sleep(1)
                    continue
                miss=0
                drv.execute_script(js_confirm)
                time.sleep(self.delay_sec)
                self.cancelled+=1
                self.status_update.emit(f"✅ Đã hủy lời mời kết bạn {self.cancelled}")
                drv.execute_script("window.scrollBy(0,400);")
                time.sleep(1)

            self.status_update.emit(f"🎉 Hoàn tất! Đã hủy {self.cancelled} lời mời")

        except Exception as e:
            self.status_update.emit(f"❌ Lỗi: {e}")
        finally:
            if drv:
                try: drv.quit()
                except: pass
            self.finished.emit(self.cancelled)


# =========================================================
# ===============  GIAO DIỆN CHÍNH  =======================
# =========================================================
class MainDialog(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.worker=None
        self.is_paused=False
        self.Start.clicked.connect(self.start_clicked)
        self.Pause.clicked.connect(self.pause_clicked)

    def start_clicked(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.Start.setText("Bắt đầu")
            self.Pause.setEnabled(False)
            return
        cookie=self.cookie.toPlainText().strip()
        if not cookie:
            QtWidgets.QMessageBox.warning(self,"Cảnh báo","Vui lòng nhập cookie!")
            return
        self.Status.clear()
        self.worker=CancelWorker(cookie, delay_sec=1.0)
        self.worker.status_update.connect(self.log)
        self.worker.finished.connect(self.done)
        self.worker.start()
        self.Start.setText("Dừng")
        self.Pause.setEnabled(True)

    def pause_clicked(self):
        if not self.worker: return
        if self.is_paused:
            self.worker.resume(); self.Pause.setText("Tạm dừng"); self.is_paused=False
        else:
            self.worker.pause(); self.Pause.setText("Tiếp tục"); self.is_paused=True

    def log(self,msg):
        self.Status.append(msg)
        cur=self.Status.textCursor()
        cur.movePosition(cur.End)
        self.Status.setTextCursor(cur)

    def done(self,n):
        self.Start.setText("Bắt đầu")
        self.Pause.setEnabled(False)
        self.is_paused=False

    # ✅ Cho phép đóng bằng dấu X an toàn
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Xác nhận thoát",
                "Tiến trình đang chạy, bạn có muốn dừng và thoát không?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.worker.stop()
                self.worker.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# =========================================================
# ===============  CHẠY ỨNG DỤNG  =========================
# =========================================================
if __name__=="__main__":
    app=QtWidgets.QApplication(sys.argv)
    d=MainDialog(); d.show()
    sys.exit(app.exec_())
