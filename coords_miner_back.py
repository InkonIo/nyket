"""
coords_miner_back.py - Змейка на WEST (X уменьшается) - ОБРАТНЫЙ ХОД

SHIFT НИКОГДА НЕ ОТПУСКАЕТСЯ! (кроме еды)

При Y >= 120 → запускает coords_miner_respawn.py
"""

import time
import subprocess
import sys
import threading
import argparse
import pyautogui
import pygetwindow as gw

from pico_controller import PicoController
from coords import read_f3

# Парсим аргументы
parser = argparse.ArgumentParser()
parser.add_argument('--auto', action='store_true', help='Автозапуск без Enter')
args, _ = parser.parse_known_args()
AUTO_MODE = args.auto

# ========== НАСТРОЙКИ ==========

PICO_PORT = "COM4"

# Длина туннеля
TUNNEL_LENGTH = 24

# Время на сдвиг
SHIFT_MINE_TIME = 0.8
SHIFT_WALK_TIME = 0.8

# Сколько проходов (0 = бесконечно)
PASSES_COUNT = 0

# Слоты
PICKAXE_SLOT = 2
FOOD_SLOT = 9

# Еда каждые N секунд
EAT_INTERVAL = 300

# 🎯 КАЛИБРОВКА МЫШИ
MOUSE_SENSITIVITY = 139

# Точность
YAW_TOLERANCE = 5.0
COORD_TOLERANCE = 0.5

# ⚡ СКОРОСТЬ ПОВОРОТА
TURN_DELAY = 0.05
TURN_AGGRESSIVE = 2.0
MAX_TURN_ATTEMPTS = 30

# 🔄 РЕСПА|УН ДЕТЕКЦИЯ
RESPAWN_Y_THRESHOLD = 120

TEMP_SCREENSHOT = "screen.png"
VERBOSE = True
STOP_FLAG = False
RESPAWN_FLAG = False

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


class SnakeMinerBack:
    def __init__(self):
        self.pico = PicoController(PICO_PORT)
        self.window = None
        
        self.x = 0
        self.y = 0
        self.z = 0
        self.yaw = 0
        
        self.passes = 0
        self.next_eat = 0
        
        # Границы Z (будут установлены при старте)
        self.z_north = 0
        self.z_south = 0
    
    def emergency_stop(self):
        print("\n🛑 СТОП!")
        try:
            self.pico.release_key("W")
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
                return True
        return False
    
    def check_respawn(self):
        global RESPAWN_FLAG
        if self.y >= RESPAWN_Y_THRESHOLD:
            print(f"\n🔄 РЕСПА|УН! Y={self.y:.1f}")
            RESPAWN_FLAG = True
            return True
        return False
    
    def normalize_yaw(self, yaw):
        while yaw > 180:
            yaw -= 360
        while yaw < -180:
            yaw += 360
        return yaw
    
    def turn_to_yaw(self, target_yaw):
        """Поворот - SHIFT НЕ ОТПУСКАЕТСЯ!"""
        global STOP_FLAG, RESPAWN_FLAG
        
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
        
        print(f"🔄 Поворот на {dir_name} ({target_yaw}°)...")
        
        self.pico.release_key("W")
        self.pico.release()
        time.sleep(0.02)
        
        for attempt in range(MAX_TURN_ATTEMPTS):
            if STOP_FLAG or RESPAWN_FLAG:
                return False
            
            if not self.update_pos():
                time.sleep(0.05)
                continue
            
            if self.check_respawn():
                return False
            
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
        
        print(f"⚠️ Не точно (yaw={self.yaw:.1f}°)")
        return False
    
    def mine_north(self):
        global STOP_FLAG, RESPAWN_FLAG
        
        target_z = self.z_north
        print(f"⛏️ [North] Копаю до Z={target_z:.1f}...")
        
        self.pico.hold_key("W")
        time.sleep(0.02)
        self.pico.hold_left()
        
        last_log = 0
        timeout = time.time() + 90
        
        while time.time() < timeout and not STOP_FLAG and not RESPAWN_FLAG:
            if not self.update_pos():
                time.sleep(0.2)
                continue
            
            if self.check_respawn():
                self.pico.release_key("W")
                self.pico.release()
                return False
            
            if self.z <= target_z + COORD_TOLERANCE:
                log(f"✅ Z={self.z:.1f}")
                break
            
            if time.time() - last_log >= 3:
                log(f"Z={self.z:.1f}, осталось {self.z - target_z:.1f}")
                last_log = time.time()
            
            if time.time() >= self.next_eat:
                self.eat()
                self.pico.hold_key("W")
                time.sleep(0.02)
                self.pico.hold_left()
            
            time.sleep(0.15)
        
        self.pico.release_key("W")
        self.pico.release()
        time.sleep(0.05)
        return True
    
    def mine_south(self):
        global STOP_FLAG, RESPAWN_FLAG
        
        target_z = self.z_south
        print(f"⛏️ [South] Копаю до Z={target_z:.1f}...")
        
        self.pico.hold_key("W")
        time.sleep(0.02)
        self.pico.hold_left()
        
        last_log = 0
        timeout = time.time() + 90
        
        while time.time() < timeout and not STOP_FLAG and not RESPAWN_FLAG:
            if not self.update_pos():
                time.sleep(0.2)
                continue
            
            if self.check_respawn():
                self.pico.release_key("W")
                self.pico.release()
                return False
            
            if self.z >= target_z - COORD_TOLERANCE:
                log(f"✅ Z={self.z:.1f}")
                break
            
            if time.time() - last_log >= 3:
                log(f"Z={self.z:.1f}, осталось {target_z - self.z:.1f}")
                last_log = time.time()
            
            if time.time() >= self.next_eat:
                self.eat()
                self.pico.hold_key("W")
                time.sleep(0.02)
                self.pico.hold_left()
            
            time.sleep(0.15)
        
        self.pico.release_key("W")
        self.pico.release()
        time.sleep(0.05)
        return True
    
    def shift_west(self):
        """Сдвиг на WEST (X уменьшается) - SHIFT зажат"""
        global STOP_FLAG, RESPAWN_FLAG
        
        if STOP_FLAG or RESPAWN_FLAG:
            return False
        
        self.update_pos()
        
        if self.check_respawn():
            return False
        
        print(f"⬅️ Сдвиг West: копаю {SHIFT_MINE_TIME}с + иду {SHIFT_WALK_TIME}с")
        
        self.pico.hold_left()
        time.sleep(SHIFT_MINE_TIME)
        
        self.pico.hold_key("W")
        time.sleep(SHIFT_WALK_TIME)
        
        self.pico.release_key("W")
        self.pico.release()
        
        self.update_pos()
        log(f"✅ X={self.x:.1f}")
        time.sleep(0.05)
        return True
    
    def eat(self):
        if STOP_FLAG:
            return
        
        print("🍖 Ем...")
        
        self.pico.release_key("W")
        self.pico.release_key("SHIFT")
        self.pico.release()
        time.sleep(0.2)
        
        self.pico.slot(FOOD_SLOT)
        time.sleep(0.1)
        self.pico.hold_right()
        time.sleep(2.5)
        self.pico.release()
        time.sleep(0.1)
        self.pico.slot(PICKAXE_SLOT)
        time.sleep(0.1)
        
        self.pico.hold_key("SHIFT")
        
        self.next_eat = time.time() + EAT_INTERVAL
        print("✅ Поел!")
    
    def run_snake_back(self):
        """Змейка на WEST (обратно)"""
        global STOP_FLAG, RESPAWN_FLAG
        
        self.pico.hold_key("SHIFT")
        
        # Устанавливаем границы Z от текущей позиции
        self.update_pos()
        self.z_south = self.z
        self.z_north = self.z - TUNNEL_LENGTH
        
        print(f"📍 Границы Z: {self.z_south:.1f} ↔ {self.z_north:.1f}")
        
        pass_num = 0
        
        while (PASSES_COUNT == 0 or pass_num < PASSES_COUNT) and not STOP_FLAG and not RESPAWN_FLAG:
            pass_num += 1
            
            print(f"\n{'='*50}")
            print(f"🐍 ПРОХОД #{pass_num} [← WEST]")
            print(f"{'='*50}")
            
            # ШАГ 1: North
            print(f"\n--- ШАГ 1: North ---")
            if not self.mine_north():
                break
            if STOP_FLAG or RESPAWN_FLAG:
                break
            
            # Поворот на WEST (не East!)
            if not self.turn_to_yaw(WEST):
                break
            if STOP_FLAG or RESPAWN_FLAG:
                break
            
            if not self.shift_west():
                break
            if STOP_FLAG or RESPAWN_FLAG:
                break
            
            if not self.turn_to_yaw(SOUTH):
                break
            if STOP_FLAG or RESPAWN_FLAG:
                break
            
            # ШАГ 2: South
            print(f"\n--- ШАГ 2: South ---")
            if not self.mine_south():
                break
            if STOP_FLAG or RESPAWN_FLAG:
                break
            
            if not self.turn_to_yaw(WEST):
                break
            if STOP_FLAG or RESPAWN_FLAG:
                break
            
            if not self.shift_west():
                break
            if STOP_FLAG or RESPAWN_FLAG:
                break
            
            if not self.turn_to_yaw(NORTH):
                break
            if STOP_FLAG or RESPAWN_FLAG:
                break
            
            self.passes += 1
            print(f"\n✅ Проход #{pass_num} готов!")
    
    def launch_respawn_handler(self):
        print("\n🔄 Запускаю coords_miner_respawn.py...")
        time.sleep(0.5)
        self.pico.close()
        subprocess.run([sys.executable, "coords_miner_respawn.py"])
    
    def run(self):
        global STOP_FLAG, RESPAWN_FLAG
        
        print("="*50)
        print("🐍 SNAKE MINER ← WEST (ОБРАТНО)")
        print(f"   Туннель: {TUNNEL_LENGTH} блоков")
        print(f"   Респаун: Y >= {RESPAWN_Y_THRESHOLD}")
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
        
        print("="*50)
        print("📋 ИНСТРУКЦИЯ:")
        print(f"1. Встань смотри на NORTH (~{NORTH}°)")
        print("2. Enter и переключись на Minecraft")
        print("="*50)
        
        if AUTO_MODE:
            print("\n🤖 АВТО-РЕЖИМ! Старт через 3 сек...")
        else:
            input("\n▶️ Enter!\n")
        
        for i in range(3, 0, -1):
            print(f"   {i}...")
            time.sleep(1)
        print("🚀 ПОЕХАЛИ!\n")
        
        self.pico.slot(PICKAXE_SLOT)
        self.next_eat = time.time() + EAT_INTERVAL
        
        start = time.time()
        
        try:
            self.run_snake_back()
        except KeyboardInterrupt:
            pass
        finally:
            self.emergency_stop()
            
            mins = (time.time() - start) / 60
            print(f"\n{'='*50}")
            print(f"📊 Время: {mins:.1f} мин | Проходов: {self.passes}")
            print(f"{'='*50}")
            
            if RESPAWN_FLAG:
                self.launch_respawn_handler()
            else:
                self.pico.close()


if __name__ == "__main__":
    bot = SnakeMinerBack()
    bot.run()