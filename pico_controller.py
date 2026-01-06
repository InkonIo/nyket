"""
pico_controller.py - Управление Raspberry Pi Pico
"""

import serial
import time


class PicoController:
    def __init__(self, port="COM4"):
        self.port = port
        self.serial = None
    
    def connect(self):
        """Подключается к Pico"""
        try:
            self.serial = serial.Serial(self.port, 115200, timeout=1)
            time.sleep(0.5)
            
            # Проверяем связь
            self.serial.write(b"PING\n")
            response = self.serial.readline().decode().strip()
            return response == "PONG"
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False
    
    def send(self, cmd):
        """Отправляет команду"""
        if not self.serial:
            return False
        try:
            self.serial.write(f"{cmd}\n".encode())
            time.sleep(0.02)
            return True
        except:
            return False
    
    def close(self):
        """Закрывает соединение"""
        if self.serial:
            self.send("RELEASE")
            self.serial.close()
    
    # === КЛАВИШИ ===
    def key(self, k):
        """Нажать клавишу (и отпустить)"""
        return self.send(f"KEY_{k}")
    
    def hold_key(self, k):
        """Зажать клавишу"""
        return self.send(f"HOLD_KEY_{k}")
    
    def release_key(self, k):
        """Отпустить клавишу"""
        return self.send(f"RELEASE_KEY_{k}")
    
    # === СЛОТЫ ===
    def slot(self, n):
        """Выбрать слот 1-9"""
        return self.send(f"SLOT_{n}")
    
    # === МЫШЬ ===
    def mouse_move(self, dx, dy):
        """Двигает мышь"""
        return self.send(f"MOUSE_MOVE_{dx}_{dy}")
    
    def hold_left(self):
        """Зажать ЛКМ"""
        return self.send("HOLD_LEFT")
    
    def hold_right(self):
        """Зажать ПКМ"""
        return self.send("HOLD_RIGHT")
    
    def click_left(self):
        """Клик ЛКМ"""
        return self.send("CLICK_LEFT")
    
    def click_right(self):
        """Клик ПКМ"""
        return self.send("CLICK_RIGHT")
    
    def release(self):
        """Отпустить всё"""
        return self.send("RELEASE")