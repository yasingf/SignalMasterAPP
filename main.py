import socket
import json
import logging
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
import ipaddress
from transfer import ZynqCommunicator
from scope import PlotWidget
from generator import SignalGeneratorWidget
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import pyqtSignal, QObject
import sys
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class MainApp(QObject):
    update_waveform_signal = pyqtSignal(list, int)  # 更新为传递波形数据和采样率
    update_device_signal = pyqtSignal(list)  # 定义一个信号，传递设备列表

    def __init__(self, root):
        super().__init__()
        self.root = root
        self.root.title("仪器选择界面")
        self.root.geometry("1920x1080")
        self.device_list = []
        self.selected_device = None
        self.waveform = []
        self.stop_event = threading.Event()

        self.plot_window = PlotWidget(self)
        self.update_waveform_signal.connect(self.plot_window.update_plot)
        self.update_device_signal.connect(self.update_device_buttons)

        self.init_main_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_main_ui(self):
        self.clear_frame()
        self.device_frame = tk.Frame(self.root)
        self.device_frame.pack(pady=10)
        self.manual_ip_button = tk.Button(self.root, text="手动输入IP", command=self.input_ip, font=('Arial', 20))
        self.manual_ip_button.pack(pady=5)
        self.scan_button = tk.Button(self.root, text="扫描局域网", command=self.start_scan, font=('Arial', 20))
        self.scan_button.pack(pady=5)

    def clear_frame(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def start_scan(self):
        self.device_list.clear()
        self.scan_thread = threading.Thread(target=self.scan_network)
        self.scan_thread.start()

    def scan_network(self):
        local_ip = self.get_local_ip()
        if not local_ip:
            messagebox.showerror("错误", "无法获取本机IP地址")
            return

        network = ipaddress.ip_network(local_ip + '/24', strict=False)
        threads = []
        for ip in network.hosts():
            thread = threading.Thread(target=self.scan_ip, args=(str(ip),))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self.root.after(0, lambda: self.update_device_signal.emit(self.device_list))

    def get_local_ip(self):
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except socket.error:
            return None

    def scan_ip(self, ip):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                if s.connect_ex((ip, 6401)) == 0:
                    self.device_list.append(ip)
        except Exception as e:
            log.error(f"错误扫描{ip}: {e}")

    def update_device_buttons(self, devices):
        self.device_list = devices
        for widget in self.device_frame.winfo_children():
            widget.destroy()
        for ip in self.device_list:
            button = tk.Button(self.device_frame, text=ip, command=lambda ip=ip: self.connect_to_device(ip), font=('Arial', 20))
            button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

    def input_ip(self):
        ip = simpledialog.askstring("输入IP", "请输入Zynq设备的IP地址:")
        if ip:
            self.connect_to_device(ip)

    def connect_to_device(self, ip):
        self.selected_device = ip
        self.communicator = ZynqCommunicator(ip, 6401)
        self.connect_thread = threading.Thread(target=self.connect_and_update_ui)
        self.connect_thread.start()

    def connect_and_update_ui(self):
        self.communicator.connect()
        if self.communicator.is_connected:
            self.show_instrument_selection()
        else:
            self.root.after(0, lambda: messagebox.showerror("连接失败", "无法连接到设备"))

    def show_instrument_selection(self):
        self.clear_frame()
        instruments = ['示波器', '波形发生器']
        for instrument in instruments:
            button = tk.Button(self.root, text=instrument, font=('Arial', 20),command=lambda instr=instrument: self.select_instrument(instr))
            button.pack(pady=5)

    def select_instrument(self, instrument):
        if instrument == '示波器':
            self.communicator.send_data({"cmd_type": "switch", "instrument": "scope"})
            self.plot_window.show()
            self.listen_for_data()
        elif instrument == '波形发生器':
            self.communicator.send_data({"cmd_type": "switch", "instrument": "generator"})
            self.signal_generator_widget = SignalGeneratorWidget(self.communicator)
            self.signal_generator_widget.show()

    def listen_for_data(self):
        self.stop_event.clear()
        self.receive_thread = threading.Thread(target=self.receive_data_loop)
        self.receive_thread.start()

    def receive_data_loop(self):
        while self.communicator.is_connected and not self.stop_event.is_set():
            try:
                data = self.communicator.receive_data()
                if data:
                    raw_waveform = data.get("waveform")
                    sample_rate = data.get("sample_rate", 64000000)
                    if raw_waveform:
                        waveform = self.parse_adc_data(raw_waveform)
                        self.root.after(0, lambda: self.update_waveform_signal.emit(waveform, sample_rate))
            except Exception as e:
                log.error(f"接收数据时出错: {e}")
                break

    def parse_adc_data(self, raw_waveform):
        return [(value / 2048) * 5.0 for value in raw_waveform]

    def on_closing(self):
        if messagebox.askokcancel("退出", "确定要退出吗？"):
            self.stop_event.set()
            if hasattr(self, 'communicator') and self.communicator.is_connected:
                self.communicator.send_data({"cmd_type": "exitins"})
                self.communicator.disconnect()
            self.root.destroy()
            QApplication.instance().quit()
            sys.exit()


if __name__ == '__main__':
    root = tk.Tk()
    app = QApplication([])
    main_app = MainApp(root)
    root.mainloop()
    app.exec_()
