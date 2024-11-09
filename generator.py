from PyQt5.QtWidgets import QComboBox, QLineEdit, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt5.QtCore import pyqtSlot

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
        amplitude_index = self.amplitude_combo.currentIndex()  # 获取幅度的代号

        try:
            # 确保频率在允许范围内
            frequency = int(frequency)
            if frequency < 1 or frequency > 62500000:
                raise ValueError("频率超出范围")
            
            
            config = {
                "cmd_type": "update",
                "waveform": waveform_index,  # 使用波形的代号
                "frequency": frequency,
                "amplitude": amplitude_index  # 使用幅度的代号
            }
            self.communicator.send_data(config)
            # print("信号发生器配置已发送:", config)
        except ValueError:
            print("频率输入无效，请输入 1 - 62500000 范围内的整数")

    def closeEvent(self, event):
        """关闭窗口时执行的操作"""
        self.communicator.send_data({"cmd_type": "exitins"})
        event.accept()