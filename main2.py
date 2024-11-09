import socket
import json
import logging
import threading
import tkinter as tk
import ipaddress
from tkinter import messagebox, simpledialog
from transfer import ZynqCommunicator
import pyqtgraph as pg
from PyQt5.QtWidgets import QComboBox, QLineEdit, QPushButton, QHBoxLayout, QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt5.QtCore import pyqtSignal, QObject
import numpy as np
import time  # 用于帧率计算
import sys

# 配置日志
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class PlotWidget(QMainWindow):
    '''
    示波器界面
    绘制波形
    '''
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app  # 将 MainApp 的引用传入以便发送退出命令
        self.setWindowTitle("波形绘制")
        self.setGeometry(100, 100, 800, 600)

        # 创建波形绘制区域
        self.plot_widget = pg.PlotWidget(title="示波器波形")
        self.plot_widget.setLabel('left', '幅值')
        self.plot_widget.setLabel('bottom', '时间')
        self.plot_widget.showGrid(x=True, y=True)
        self.curve = self.plot_widget.plot([], pen='y')

        # 参数显示区域，使用QLabel代替
        self.peak_voltage_label = QLabel("峰值电压: 未知")
        self.sample_rate_label = QLabel("采样率: 未知")

        # 设置布局
        layout = QVBoxLayout()
        layout.addWidget(self.peak_voltage_label)
        layout.addWidget(self.sample_rate_label)
        layout.addWidget(self.plot_widget)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # 帧率计算变量
        self.last_update_time = time.time()

    def update_plot(self, waveform, sample_rate=None):
        """更新波形绘制和参数显示"""
        if waveform is not None:
            time_axis = np.arange(len(waveform))
            self.curve.setData(time_axis, waveform)

            # 计算并显示峰值电压
            peak_voltage = max(waveform) - min(waveform)
            self.peak_voltage_label.setText(f"峰值电压: {peak_voltage:.2f} V")

            # 更新采样率显示
            if sample_rate:
                self.sample_rate_label.setText(f"采样率: {sample_rate} Hz")

            # 计算并输出帧率
            current_time = time.time()
            frame_time = current_time - self.last_update_time
            self.last_update_time = current_time
            frame_rate = 1.0 / frame_time
            log.info(f"当前绘制帧率: {frame_rate:.2f} FPS")

    def closeEvent(self, event):
        """重载窗口关闭事件以发送退出指令"""
        if self.main_app and self.main_app.communicator.is_connected:
            self.main_app.communicator.send_data({"cmd_type": "exitins"})
            print("已发送")
            self.main_app.stop_event.set()
        event.accept()



class SignalGeneratorWidget(QWidget):
    def __init__(self, communicator):
        super().__init__()
        self.communicator = communicator
        self.setWindowTitle("信号发生器设置")
        self.setGeometry(100, 100, 400, 300)

        # 创建波形选择下拉框
        self.waveform_label = QLabel("波形:")
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(["正弦波", "三角波", "锯齿波", "方波"])

        # 创建频率输入框
        self.freq_label = QLabel("频率 (Hz):")
        self.freq_input = QLineEdit()
        self.freq_input.setPlaceholderText("1 - 62500000")
        self.freq_input.setText("1000")  # 设置默认频率为1000 Hz

        # 创建幅度选择下拉框
        self.amplitude_label = QLabel("幅度(3V为基准):")
        self.amplitude_combo = QComboBox()
        self.amplitude_combo.addItems(["1", "1/2", "1/4", "1/8", "1/16"])

        # 创建按钮
        self.update_button = QPushButton("更新")
        self.exit_button = QPushButton("退出")

        # 设置布局
        layout = QVBoxLayout()
        layout.addWidget(self.waveform_label)
        layout.addWidget(self.waveform_combo)
        layout.addWidget(self.freq_label)
        layout.addWidget(self.freq_input)
        layout.addWidget(self.amplitude_label)
        layout.addWidget(self.amplitude_combo)
        layout.addWidget(self.update_button)
        layout.addWidget(self.exit_button)
        self.setLayout(layout)

        # 绑定按钮事件
        self.update_button.clicked.connect(self.update_signal_generator)
        self.exit_button.clicked.connect(self.close)

    def update_signal_generator(self):
        """更新信号发生器的设置"""
        # 获取波形、频率和幅度值
        waveform_index = self.waveform_combo.currentIndex()  # 获取波形的代号
        frequency = self.freq_input.text()
        amplitude_ratio = self.amplitude_combo.currentText()

        try:
            # 确保频率在允许范围内
            frequency = int(frequency)
            if frequency < 1 or frequency > 62500000:
                raise ValueError("频率超出范围")
            
            # 将参数发送到Zynq设备
            config = {
                "cmd_type": "update",
                "waveform": waveform_index,  # 使用波形的代号
                "frequency": frequency,
                "amplitude": amplitude_ratio
            }
            self.communicator.send_data(config)
            print("信号发生器配置已发送:", config)
        except ValueError:
            print("频率输入无效，请输入 1 - 62500000 范围内的整数")

    def closeEvent(self, event):
        """关闭窗口时执行的操作"""
        self.communicator.send_data({"cmd_type": "exitins"})
        event.accept()



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
        self.stop_event = threading.Event()  # 创建停止事件

        # 初始化绘图窗口
        self.plot_window = PlotWidget(self)  # 将 MainApp 自身传递给 PlotWidget
        self.update_waveform_signal.connect(self.plot_window.update_plot)
        self.update_device_signal.connect(self.update_device_buttons)

        self.init_main_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)  # 绑定关闭事件
 

    def init_main_ui(self):
        """初始界面布局"""
        self.clear_frame()

        self.device_frame = tk.Frame(self.root)
        self.device_frame.pack(pady=10)

        self.manual_ip_button = tk.Button(self.root, text="手动输入IP", command=self.input_ip ,font=('Arial',20))
        self.manual_ip_button.pack(pady=5)

        self.scan_button = tk.Button(self.root, text="扫描局域网", command=self.start_scan,font=('Arial',20))
        self.scan_button.pack(pady=5)

    def clear_frame(self):
        """清空当前窗口内容"""
        for widget in self.root.winfo_children():
            widget.destroy()

    def start_scan(self):
        """开始在局域网内扫描开放6401端口的主机"""
        self.device_list.clear()
        self.scan_thread = threading.Thread(target=self.scan_network)
        self.scan_thread.start()

    def scan_network(self):
        """扫描网络并更新设备列表"""
        self.device_list.clear()
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
        """获取本机的IP地址"""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return local_ip
        except socket.error:
            return None

    def scan_ip(self, ip):
        """扫描单个IP地址"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                if s.connect_ex((ip, 6401)) == 0:
                    self.device_list.append(ip)
        except Exception as e:
            log.error(f"错误扫描{ip}: {e}")

    def update_device_buttons(self, devices):
        """更新设备按钮列表"""
        self.device_list = devices
        for widget in self.device_frame.winfo_children():
            widget.destroy()

        for ip in self.device_list:
            button = tk.Button(self.device_frame, text=ip, command=lambda ip=ip: self.connect_to_device(ip),font=('Arial',20))
            button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

    def input_ip(self):
        """手动输入IP地址"""
        ip = simpledialog.askstring("输入IP", "请输入Zynq设备的IP地址:")
        if ip:
            self.connect_to_device(ip)

    def connect_to_device(self, ip):
        """连接到选择的设备"""
        self.selected_device = ip
        self.communicator = ZynqCommunicator(ip, 6401)

        self.connect_thread = threading.Thread(target=self.connect_and_update_ui)
        self.connect_thread.start()

    def connect_and_update_ui(self):
        """连接设备并更新界面"""
        self.communicator.connect()
        if self.communicator.is_connected:
            self.show_instrument_selection()
        else:
            self.root.after(0, lambda: messagebox.showerror("连接失败", "无法连接到设备"))

    def show_instrument_selection(self):
        """显示仪器选择界面"""
        self.clear_frame()

        # 示例仪器选择按钮
        instruments = ['示波器', '波形发生器']
        for instrument in instruments:
            button = tk.Button(self.root, text=instrument, command=lambda instr=instrument: self.select_instrument(instr))
            button.pack(pady=5)

    def select_instrument(self, instrument):
        """选择仪器并显示对应的界面"""
        if instrument == '示波器':
            self.communicator.send_data({"cmd_type": "switch", "instrument": "scope"})
            self.plot_window.show()
            self.listen_for_data()
        elif instrument == '波形发生器':
            self.communicator.send_data({"cmd_type": "switch", "instrument": "generator"})
            self.signal_generator_widget = SignalGeneratorWidget(self.communicator)
            self.signal_generator_widget.show()

    def listen_for_data(self):
        """监听数据接收"""
        self.stop_event.clear()  # 清除停止事件
        self.receive_thread = threading.Thread(target=self.receive_data_loop)
        self.receive_thread.start()


    def receive_data_loop(self):
        """循环接收数据"""
        while self.communicator.is_connected and not self.stop_event.is_set():
            try:
                data = self.communicator.receive_data()
                if data:
                    raw_waveform = data.get("waveform")
                    sample_rate = data.get("sample_rate", 64000000)

                    if raw_waveform:
                        waveform = self.parse_adc_data(raw_waveform)  # 解析
                        self.root.after(0, lambda: self.update_waveform_signal.emit(waveform, sample_rate))
            except Exception as e:
                log.error(f"接收数据时出错: {e}")
                break

    def parse_adc_data(self, raw_waveform):
        """解析12位带符号的ADC数据"""
        parsed_waveform = []

        for value in raw_waveform:
            # 将12位ADC数据转换为幅度值，假设ADC的满量程是±5V
            amplitude = (value / 2048) * 5.0
            parsed_waveform.append(amplitude)

        return parsed_waveform

    def on_closing(self):
        """关闭窗口时立即停止所有线程并断开连接"""
        if messagebox.askokcancel("退出", "确定要退出吗？"):
            self.stop_event.set()  # 设置停止事件，通知线程结束

            # 直接断开连接
            if hasattr(self, 'communicator') and self.communicator.is_connected:
                self.communicator.send_data({"cmd_type": "exitins"})
                self.communicator.disconnect()

            # 关闭窗口
            self.root.destroy()  # 对于Tkinter主窗口
            QApplication.instance().quit()  # 对于Qt应用
            sys.exit()  # 强制退出程序


if __name__ == '__main__':
    root = tk.Tk()
    app = QApplication([])
    main_app = MainApp(root)
    root.mainloop()
    app.exec_()
