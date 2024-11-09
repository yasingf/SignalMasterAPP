from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QLabel, QWidget
import pyqtgraph as pg
import numpy as np
import time
import logging

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
