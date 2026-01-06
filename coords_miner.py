"""
coords_miner_snake.py - Змейка!

SHIFT ВСЕГДА ЗАЖАТ! Никогда не отпускаем!

Алгоритм:
1. Стою на north (180°), копаю 24 блока (Z уменьшается: 783→759)
2. Поворот на east (-90°) → копаю + иду (X увеличивается)
3. Поворот на south (0°)
4. Копаю 24 блока (Z увеличивается: 759→783)
5. Поворот на east (-90°) → копаю + иду
6. Поворот на north (180°)
7. Повтор...
"""

import time
import threading
import pyautogui
import pygetwindow as gw

from pico_controller import PicoController
from coords import read_f3

# ========== НАСТРОЙКИ ==========

PICO_PORT = "COM4"

# Стартовые координаты
START_X = -1333.3
START_Z = 783.3

# Длина туннеля
TUNNEL_LENGTH = 24

# Время на сдвиг
SHIFT_MINE_TIME = 0.8  # сек копать
SHIFT_WALK_TIME = 0.8  # сек идти

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

TEMP_SCREENSHOT = "screen.png"
VERBOSE = True
STOP_FLAG = False

# Направления
NORTH = 180
SOUTH = 0
EAST = -90


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


class SnakeMiner:
    def __init__(self):
        self.pico = PicoController(PICO_PORT)
        self.window = None
        
        self.x = 0
        self.y = 0
        self.z = 0
        self.yaw = 0
        
        self.passes = 0
        self.next_eat = 0
        
        # Границы Z
        self.z_north = START_Z - TUNNEL_LENGTH
        self.z_south = START_Z
    
    def emergency_stop(self):
        """Только тут отпускаем всё!"""
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
    
    def normalize_yaw(self, yaw):
        while yaw > 180:
            yaw -= 360
        while yaw < -180:
            yaw += 360
        return yaw
    
    def turn_to_yaw(self, target_yaw):
        """Поворот - SHIFT остаётся зажатым!"""
        global STOP_FLAG
        
        target_yaw = self.normalize_yaw(target_yaw)
        
        if abs(target_yaw - 180) < 10 or abs(target_yaw + 180) < 10:
            dir_name = "North"
        elif abs(target_yaw) < 10:
            dir_name = "South"
        elif abs(target_yaw + 90) < 10:
            dir_name = "East"
        else:
            dir_name = f"{target_yaw}°"
        
        print(f"🔄 Поворот на {dir_name} ({target_yaw}°)...")
        
        # Отпускаем ТОЛЬКО W и ЛКМ, SHIFT держим!
        self.pico.release_key("W")
        self.pico.release()  # отпускает ЛКМ
        time.sleep(0.02)
        
        # SHIFT остаётся зажатым, но на всякий случай подтвердим
        self.pico.hold_key("SHIFT")
        
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
        
        print(f"⚠️ Не точно (yaw={self.yaw:.1f}°)")
        return False
    
    def mine_north(self):
        """Копаем на North - SHIFT всегда зажат"""
        global STOP_FLAG
        
        target_z = self.z_north
        print(f"⛏️ [North] Копаю до Z={target_z:.1f}...")
        
        # SHIFT уже зажат, просто добавляем W и ЛКМ
        self.pico.hold_key("W")
        time.sleep(0.02)
        self.pico.hold_left()
        
        last_log = 0
        timeout = time.time() + 90
        
        while time.time() < timeout and not STOP_FLAG:
            if not self.update_pos():
                time.sleep(0.2)
                continue
            
            if self.z <= target_z + COORD_TOLERANCE:
                log(f"✅ Z={self.z:.1f}")
                break
            
            if time.time() - last_log >= 3:
                log(f"Z={self.z:.1f}, осталось {self.z - target_z:.1f}")
                last_log = time.time()
            
            if time.time() >= self.next_eat:
                self.eat()
                # После еды снова зажимаем (SHIFT уже зажат в eat())
                self.pico.hold_key("W")
                time.sleep(0.02)
                self.pico.hold_left()
            
            time.sleep(0.15)
        
        # Отпускаем ТОЛЬКО W и ЛКМ!
        self.pico.release_key("W")
        self.pico.release()  # ЛКМ
        time.sleep(0.05)
    
    def mine_south(self):
        """Копаем на South - SHIFT всегда зажат"""
        global STOP_FLAG
        
        target_z = self.z_south
        print(f"⛏️ [South] Копаю до Z={target_z:.1f}...")
        
        self.pico.hold_key("W")
        time.sleep(0.02)
        self.pico.hold_left()
        
        last_log = 0
        timeout = time.time() + 90
        
        while time.time() < timeout and not STOP_FLAG:
            if not self.update_pos():
                time.sleep(0.2)
                continue
            
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
    
    def shift_east(self):
        """Сдвиг на East - SHIFT зажат"""
        global STOP_FLAG
        
        if STOP_FLAG:
            return
        
        self.update_pos()
        print(f"➡️ Сдвиг East: копаю {SHIFT_MINE_TIME}с + иду {SHIFT_WALK_TIME}с")
        
        # Копаем на месте (SHIFT уже зажат)
        self.pico.hold_left()
        time.sleep(SHIFT_MINE_TIME)
        
        # Идём вперёд
        self.pico.hold_key("W")
        time.sleep(SHIFT_WALK_TIME)
        
        # Отпускаем W и ЛКМ (SHIFT держим!)
        self.pico.release_key("W")
        self.pico.release()
        
        self.update_pos()
        log(f"✅ X={self.x:.1f}")
        time.sleep(0.05)
    
    def eat(self):
        """Еда - единственное место где временно отпускаем SHIFT"""
        if STOP_FLAG:
            return
        
        print("🍖 Ем...")
        
        # Тут отпускаем всё
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
        
        # Сразу зажимаем SHIFT обратно!
        self.pico.hold_key("SHIFT")
        
        self.next_eat = time.time() + EAT_INTERVAL
        print("✅ Поел!")
    
    def run_snake(self):
        """Главный цикл - SHIFT зажат с самого начала"""
        global STOP_FLAG
        
        # ЗАЖИМАЕМ SHIFT В НАЧАЛЕ И ДЕРЖИМ ВСЕГДА!
        self.pico.hold_key("SHIFT")
        
        pass_num = 0
        
        while (PASSES_COUNT == 0 or pass_num < PASSES_COUNT) and not STOP_FLAG:
            pass_num += 1
            
            print(f"\n{'='*50}")
            print(f"🐍 ПРОХОД #{pass_num}")
            print(f"{'='*50}")
            
            # ШАГ 1: North
            print(f"\n--- ШАГ 1: North (Z: {self.z_south} → {self.z_north}) ---")
            self.mine_north()
            if STOP_FLAG: break
            
            self.turn_to_yaw(EAST)
            if STOP_FLAG: break
            
            self.shift_east()
            if STOP_FLAG: break
            
            self.turn_to_yaw(SOUTH)
            if STOP_FLAG: break
            
            # ШАГ 2: South
            print(f"\n--- ШАГ 2: South (Z: {self.z_north} → {self.z_south}) ---")
            self.mine_south()
            if STOP_FLAG: break
            
            self.turn_to_yaw(EAST)
            if STOP_FLAG: break
            
            self.shift_east()
            if STOP_FLAG: break
            
            self.turn_to_yaw(NORTH)
            if STOP_FLAG: break
            
            self.passes += 1
            print(f"\n✅ Проход #{pass_num} готов!")
    
    def run(self):
        global STOP_FLAG
        
        print("="*50)
        print("🐍 SNAKE MINER (SHIFT ALWAYS ON!)")
        print(f"   Старт: X={START_X} Z={START_Z}")
        print(f"   Туннель: {TUNNEL_LENGTH} блоков")
        print(f"   Z: {self.z_south} ↔ {self.z_north}")
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
        print(f"1. Встань на X={START_X}, Z={START_Z}")
        print(f"2. Смотри на NORTH (~{NORTH}°)")
        print("3. Enter и переключись на Minecraft")
        print("="*50)
        input("\n▶️ Enter!\n")
        
        for i in range(3, 0, -1):
            print(f"   {i}...")
            time.sleep(1)
        print("🚀 ПОЕХАЛИ!\n")
        
        self.pico.slot(PICKAXE_SLOT)
        self.next_eat = time.time() + EAT_INTERVAL
        
        start = time.time()
        
        try:
            self.run_snake()
        except KeyboardInterrupt:
            pass
        finally:
            self.emergency_stop()
            self.pico.close()
            
            mins = (time.time() - start) / 60
            print(f"\n{'='*50}")
            print(f"📊 Время: {mins:.1f} мин | Проходов: {self.passes}")
            print(f"{'='*50}")


if __name__ == "__main__":
    bot = SnakeMiner()
    bot.run()