import socket
import json
import logging
from PyQt5.QtCore import pyqtSignal, QObject
import struct  # 用于处理包头的二进制数据

# 配置日志
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class ZynqCommunicator(QObject):
    data_received_signal = pyqtSignal(dict)  # 定义一个信号用于接收数据

    def __init__(self, ip, port):
        super().__init__()  # 调用 QObject 的初始化
        self.ip = ip
        self.port = port
        self.socket = None
        self.is_connected = False

    def connect(self):
        """连接到Zynq设备"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.ip, self.port))
            self.is_connected = True
            log.info(f"已连接到Zynq设备: {self.ip}:{self.port}")
        except Exception as e:
            log.error(f"连接失败: {e}")
            self.is_connected = False

    def disconnect(self):
        """断开与Zynq设备的连接"""
        if self.socket:
            self.socket.close()
            self.is_connected = False
            log.info("已断开与Zynq设备的连接")

    def send_data(self, data):
        """发送数据到Zynq设备"""
        if not self.is_connected:
            log.error("未连接到Zynq设备")
            return
        
        try:
            json_data = json.dumps(data)
            self.socket.sendall(json_data.encode('utf-8'))
            log.info(f"发送数据: {json_data}")
        except Exception as e:
            log.error(f"发送数据失败: {e}")

    def receive_data(self):
        """接收来自Zynq设备的数据"""
        if not self.is_connected:
            log.error("未连接到Zynq设备")
            return None

        try:
            # Step 1: 读取包头，获得数据长度（4字节，网络字节序）
            header = self.socket.recv(4)
            if len(header) < 4:
                log.error("接收包头失败")
                return None

            # 将包头转换为整数，得到数据长度
            data_len = struct.unpack("!I", header)[0]  # !I 表示网络字节序的无符号整型

            # Step 2: 根据长度读取数据内容
            data = b""
            while len(data) < data_len:
                packet = self.socket.recv(data_len - len(data))
                if not packet:
                    log.error("接收数据包失败")
                    return None
                data += packet

            # 将完整数据包转换为字符串
            response = data.decode('utf-8')
            # log.info(f"接收数据: {response}")

            # Step 3: 解析 JSON 数据
            data = json.loads(response)
            self.data_received_signal.emit(data)  # 发射信号更新 GUI
            return data
        except Exception as e:
            log.error(f"接收数据失败: {e}")
            return None
