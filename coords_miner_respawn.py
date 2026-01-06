"""
coords_miner_respawn.py - Обработчик респауна

При Y >= 120:
1. Сначала ПОЕСТЬ (слот 9, ПКМ)
2. Центрироваться на блоке (X.500, Z.500)  
3. Копать вниз под себя (pitch 90°) с запасом 18-19 блоков
4. Выставить камеру: yaw=180° (North), pitch=52.5°
5. Запустить coords_miner.py

SHIFT НЕ ОТПУСКАЕТСЯ! (кроме еды)
"""

import time
import subprocess
import sys
import threading
import pyautogui
import pygetwindow as gw

from pico_controller import PicoController
from coords import read_f3

# ========== НАСТРОЙКИ ==========

PICO_PORT = "COM4"

# Слоты
PICKAXE_SLOT = 2
FOOD_SLOT = 9

# 🎯 КАЛИБРОВКА МЫШИ
MOUSE_SENSITIVITY = 139

# Точность
YAW_TOLERANCE = 5.0
PITCH_TOLERANCE = 5.0
CENTER_TOLERANCE = 0.15

# ⚡ СКОРОСТЬ ПОВОРОТА
TURN_DELAY = 0.05
TURN_AGGRESSIVE = 2.0
MAX_TURN_ATTEMPTS = 30

# 🔄 РЕСПА|УН
RESPAWN_Y_THRESHOLD = 120
DIG_DOWN_BLOCKS = 19  # С запасом!

# Целевая камера
TARGET_YAW = 180      # North
TARGET_PITCH = 52.5

TEMP_SCREENSHOT = "screen.png"
VERBOSE = True
STOP_FLAG = False

# Направления
NORTH = 180
SOUTH = 0
EAST = -90
WEST = 90


def log(msg):
    if VERBOSE:
        t = time.strftime("%H:%M:%S")
        print(f"      [{t}] {msg}")


def keyboard_listener():
    global STOP_FLAG
    try:
        import keyboard
        print("🛑 Нажми Q для остановки!")
        keyboard.wait('q')
        STOP_FLAG = True
        print("\n\n🛑 СТОП! 🛑\n")
    except:
        pass


class RespawnHandler:
    def __init__(self):
        self.pico = PicoController(PICO_PORT)
        self.window = None
        
        self.x = 0
        self.y = 0
        self.z = 0
        self.yaw = 0
        self.pitch = 0
    
    def emergency_stop(self):
        print("\n🛑 СТОП!")
        try:
            self.pico.release_key("W")
            self.pico.release_key("A")
            self.pico.release_key("S")
            self.pico.release_key("D")
            self.pico.release_key("SHIFT")
            self.pico.release()
        except:
            pass
    
    def find_window(self):
        for w in gw.getAllWindows():
            if w.title == "VimeWorld":
                return w
        return None
    
    def screenshot(self):
        if STOP_FLAG or not self.window:
            return None
        try:
            x, y, w, h = self.window.left, self.window.top, self.window.width, self.window.height
            img = pyautogui.screenshot(region=(x, y, w, h))
            img.save(TEMP_SCREENSHOT)
            return TEMP_SCREENSHOT
        except:
            return None
    
    def update_pos(self):
        if STOP_FLAG:
            return False
        img = self.screenshot()
        if img:
            data = read_f3(img)
            if data and data['x'] is not None:
                self.x = data['x']
                self.y = data['y']
                self.z = data['z']
                if data['yaw'] is not None:
                    self.yaw = data['yaw']
                if data.get('pitch') is not None:
                    self.pitch = data['pitch']
                return True
        return False
    
    def normalize_yaw(self, yaw):
        while yaw > 180:
            yaw -= 360
        while yaw < -180:
            yaw += 360
        return yaw
    
    def eat(self):
        """Еда - первое действие при респауне!"""
        print("🍖 Ем после респауна...")
        
        # Отпускаем всё
        self.pico.release_key("W")
        self.pico.release_key("SHIFT")
        self.pico.release()
        time.sleep(0.3)
        
        self.pico.slot(FOOD_SLOT)
        time.sleep(0.2)
        self.pico.hold_right()
        time.sleep(3.0)  # Чуть дольше едим после респауна
        self.pico.release()
        time.sleep(0.2)
        self.pico.slot(PICKAXE_SLOT)
        time.sleep(0.2)
        
        # Зажимаем SHIFT
        self.pico.hold_key("SHIFT")
        
        print("✅ Поел!")
    
    def turn_to_yaw(self, target_yaw):
        """Поворот по горизонтали - SHIFT зажат"""
        global STOP_FLAG
        
        target_yaw = self.normalize_yaw(target_yaw)
        
        if abs(target_yaw - 180) < 10 or abs(target_yaw + 180) < 10:
            dir_name = "North"
        elif abs(target_yaw) < 10:
            dir_name = "South"
        elif abs(target_yaw + 90) < 10:
            dir_name = "East"
        elif abs(target_yaw - 90) < 10:
            dir_name = "West"
        else:
            dir_name = f"{target_yaw}°"
        
        print(f"🔄 Поворот yaw → {dir_name} ({target_yaw}°)...")
        
        # Не трогаем SHIFT!
        self.pico.release_key("W")
        self.pico.release()
        time.sleep(0.02)
        
        for attempt in range(MAX_TURN_ATTEMPTS):
            if STOP_FLAG:
                return False
            
            if not self.update_pos():
                time.sleep(0.05)
                continue
            
            current = self.normalize_yaw(self.yaw)
            diff = self.normalize_yaw(target_yaw - current)
            
            if abs(diff) < YAW_TOLERANCE:
                log(f"✅ Yaw={current:.1f}°")
                return True
            
            if abs(diff) > 45:
                pixels = int((diff / 90.0) * MOUSE_SENSITIVITY * TURN_AGGRESSIVE)
            elif abs(diff) > 15:
                pixels = int((diff / 90.0) * MOUSE_SENSITIVITY * 1.5)
            else:
                pixels = int((diff / 90.0) * MOUSE_SENSITIVITY)
            
            max_step = int(MOUSE_SENSITIVITY * 2.5)
            pixels = max(-max_step, min(max_step, pixels))
            if abs(pixels) < 3 and abs(diff) > 1:
                pixels = 3 if diff > 0 else -3
            
            self.pico.mouse_move(pixels, 0)
            time.sleep(TURN_DELAY)
        
        print(f"⚠️ Yaw не точно ({self.yaw:.1f}°)")
        return False
    
    def turn_to_pitch(self, target_pitch):
        """Поворот по вертикали - SHIFT зажат"""
        global STOP_FLAG
        
        print(f"🔄 Поворот pitch → {target_pitch}°...")
        
        self.pico.release_key("W")
        self.pico.release()
        time.sleep(0.02)
        
        for attempt in range(MAX_TURN_ATTEMPTS):
            if STOP_FLAG:
                return False
            
            if not self.update_pos():
                time.sleep(0.05)
                continue
            
            current = self.pitch
            diff = target_pitch - current
            
            if abs(diff) < PITCH_TOLERANCE:
                log(f"✅ Pitch={current:.1f}°")
                return True
            
            if abs(diff) > 30:
                pixels = int((diff / 90.0) * MOUSE_SENSITIVITY * TURN_AGGRESSIVE)
            elif abs(diff) > 10:
                pixels = int((diff / 90.0) * MOUSE_SENSITIVITY * 1.5)
            else:
                pixels = int((diff / 90.0) * MOUSE_SENSITIVITY)
            
            max_step = int(MOUSE_SENSITIVITY * 2)
            pixels = max(-max_step, min(max_step, pixels))
            if abs(pixels) < 3 and abs(diff) > 1:
                pixels = 3 if diff > 0 else -3
            
            self.pico.mouse_move(0, pixels)
            time.sleep(TURN_DELAY)
        
        print(f"⚠️ Pitch не точно ({self.pitch:.1f}°)")
        return False
    
    def center_on_block(self):
        """Центровка на блоке (X.500, Z.500) - SHIFT зажат"""
        global STOP_FLAG
        
        print("📍 Центруюсь на блоке...")
        
        self.update_pos()
        log(f"Позиция: X={self.x:.3f}, Z={self.z:.3f}")
        
        # Ближайший .500
        if self.x >= 0:
            target_x = int(self.x) + 0.5
        else:
            target_x = int(self.x) - 0.5
            if (self.x - int(self.x)) > -0.5:
                target_x = int(self.x) + 0.5
        
        if self.z >= 0:
            target_z = int(self.z) + 0.5
        else:
            target_z = int(self.z) - 0.5
            if (self.z - int(self.z)) > -0.5:
                target_z = int(self.z) + 0.5
        
        log(f"Цель: X={target_x:.1f}, Z={target_z:.1f}")
        
        # SHIFT уже зажат!
        
        max_attempts = 50
        for attempt in range(max_attempts):
            if STOP_FLAG:
                return False
            
            self.update_pos()
            
            diff_x = target_x - self.x
            diff_z = target_z - self.z
            
            if abs(diff_x) < CENTER_TOLERANCE and abs(diff_z) < CENTER_TOLERANCE:
                log(f"✅ Центр! X={self.x:.3f}, Z={self.z:.3f}")
                self.pico.release_key("W")
                return True
            
            # X
            if abs(diff_x) >= CENTER_TOLERANCE:
                if diff_x > 0:
                    self.turn_to_yaw(EAST)
                else:
                    self.turn_to_yaw(WEST)
                self.pico.hold_key("W")
                time.sleep(0.15)
                self.pico.release_key("W")
                continue
            
            # Z
            if abs(diff_z) >= CENTER_TOLERANCE:
                if diff_z > 0:
                    self.turn_to_yaw(SOUTH)
                else:
                    self.turn_to_yaw(NORTH)
                self.pico.hold_key("W")
                time.sleep(0.15)
                self.pico.release_key("W")
            
            time.sleep(0.1)
        
        log("⚠️ Центровка не точная")
        return False
    
    def dig_down(self):
        """Копает вниз под себя - SHIFT зажат"""
        global STOP_FLAG
        
        self.update_pos()
        start_y = self.y
        target_y = start_y - DIG_DOWN_BLOCKS
        
        print(f"⬇️ Копаю вниз: Y={start_y:.1f} → {target_y:.1f} ({DIG_DOWN_BLOCKS} блоков)")
        
        # Смотрим вниз (pitch = 90°)
        self.turn_to_pitch(90)
        
        # Копаем (SHIFT уже зажат)
        self.pico.hold_left()
        
        timeout = time.time() + 120
        last_log = 0
        
        while time.time() < timeout and not STOP_FLAG:
            self.update_pos()
            
            if self.y <= target_y + 0.5:
                log(f"✅ Y={self.y:.1f}")
                break
            
            if time.time() - last_log >= 2:
                log(f"Y={self.y:.1f}, осталось {self.y - target_y:.1f}")
                last_log = time.time()
            
            time.sleep(0.2)
        
        self.pico.release()
        time.sleep(0.2)
    
    def set_camera(self):
        """Выставляет камеру - SHIFT зажат"""
        print(f"📷 Камера: yaw={TARGET_YAW}°, pitch={TARGET_PITCH}°...")
        
        self.turn_to_yaw(TARGET_YAW)
        time.sleep(0.1)
        self.turn_to_pitch(TARGET_PITCH)
        time.sleep(0.1)
        
        self.update_pos()
        print(f"✅ Камера: yaw={self.yaw:.1f}°, pitch={self.pitch:.1f}°")
    
    def handle_respawn(self):
        """Полная обработка респауна"""
        global STOP_FLAG
        
        print(f"\n{'='*50}")
        print("🔄 ОБРАБОТКА РЕСПАУНА")
        print(f"{'='*50}")
        
        time.sleep(0.5)
        
        # 1. СНАЧАЛА ЕДИМ!
        self.eat()
        if STOP_FLAG:
            return False
        
        time.sleep(0.3)
        
        # 2. Центровка
        self.center_on_block()
        if STOP_FLAG:
            return False
        
        time.sleep(0.3)
        
        # 3. Копаем вниз
        self.dig_down()
        if STOP_FLAG:
            return False
        
        time.sleep(0.3)
        
        # 4. Камера
        self.set_camera()
        
        print(f"\n✅ Респаун обработан!")
        return True
    
    def launch_miner(self):
        """Запускает основной майнер с флагом --auto"""
        print("\n🚀 Запускаю coords_miner.py --auto...\n")
        time.sleep(1)
        self.pico.close()
        subprocess.run([sys.executable, "coords_miner.py", "--auto"])
    
    def run(self):
        global STOP_FLAG
        
        print("="*50)
        print("🔄 RESPAWN HANDLER")
        print(f"   Порог: Y >= {RESPAWN_Y_THRESHOLD}")
        print(f"   Копать вниз: {DIG_DOWN_BLOCKS} блоков")
        print(f"   Камера: yaw={TARGET_YAW}° pitch={TARGET_PITCH}°")
        print("="*50)
        
        print("🔌 Pico...")
        if not self.pico.connect():
            print("❌ Pico не найден!")
            return
        print("✅ OK")
        
        print("🔎 Minecraft...")
        self.window = self.find_window()
        if not self.window:
            print("❌ VimeWorld не найден!")
            return
        print(f"✅ {self.window.title}")
        
        listener = threading.Thread(target=keyboard_listener, daemon=True)
        listener.start()
        
        self.pico.slot(PICKAXE_SLOT)
        
        self.update_pos()
        print(f"\n📍 Позиция: X={self.x:.1f}, Y={self.y:.1f}, Z={self.z:.1f}")
        
        try:
            # Если Y >= порога - обрабатываем
            if self.y >= RESPAWN_Y_THRESHOLD:
                print("⚠️ Наверху! Обрабатываю...")
                if self.handle_respawn():
                    self.launch_miner()
            else:
                # Уже внизу - сразу запускаем майнер
                print("✅ Уже внизу! Запускаю майнер...")
                self.launch_miner()
        
        except KeyboardInterrupt:
            pass
        finally:
            self.emergency_stop()
            self.pico.close()
            print("\n👋 Завершено!")


if __name__ == "__main__":
    handler = RespawnHandler()
    handler.run()