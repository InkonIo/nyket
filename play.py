"""
play.py - Идёт по route.json + автоповороты по yaw из F3

🛑 ОСТАНОВКА: Нажми Q или ESC в консоли!

Новое: в определённых точках бот сам крутится до нужного yaw
"""

import time
import json
import math
import threading
import pyautogui
import pygetwindow as gw

from pico_controller import PicoController
from coords import read_f3

# ========== НАСТРОЙКИ ==========

ROUTE_FILE = "route.json"
PICO_PORT = "COM4"

# Слоты
PICKAXE_SLOT = 2
FOOD_SLOT = 9
HEAL_SLOT = 4

# Еда каждые N секунд
EAT_INTERVAL = 180

# Насколько близко к точке = "достигли"
WAYPOINT_RADIUS = 3.0

# Повторять маршрут (0 = бесконечно)
REPEAT_COUNT = 0

# 🎯 КАЛИБРОВКА МЫШИ (пикселей на 90°)
MOUSE_SENSITIVITY = 135

# Точность поворота (градусы)
YAW_TOLERANCE = 5.0

TEMP_SCREENSHOT = "screen.png"

# Логи
VERBOSE = True

# Глобальный флаг остановки
STOP_FLAG = False

# 🎯 ТОЧКИ ПОВОРОТОВ (где нужно выровнять yaw)
# Формат: {'x': X, 'z': Z, 'target_yaw': градусы, 'mine_after': True/False, 'walk_after': True/False}
TURN_POINTS = [
    # ПЕРВЫЙ ПОВОРОТ: поворот направо + копать на месте (не идти!)
    {'x': -1333.3, 'z': 759.3, 'target_yaw': -90, 'mine_after': True, 'walk_after': False},
    
    # ВТОРОЙ ПОВОРОТ: ещё раз поворот + НЕ копать, НЕ идти (просто развернулся)
    {'x': -1332.3, 'z': 759.3, 'target_yaw': 0, 'mine_after': False, 'walk_after': False},
    
    # Добавь остальные точки поворотов здесь!
]


def log(msg):
    if VERBOSE:
        t = time.strftime("%H:%M:%S")
        print(f"      [{t}] {msg}")


def keyboard_listener():
    """Слушает клавиши для остановки"""
    global STOP_FLAG
    try:
        import keyboard
        print("🛑 Нажми Q или ESC для остановки!")
        keyboard.wait('q')
        STOP_FLAG = True
        print("\n\n🛑🛑🛑 СТОП ПО Q! 🛑🛑🛑\n")
    except ImportError:
        print("⚠️  pip install keyboard - для горячих клавиш")
    except:
        pass


class RouteBot:
    def __init__(self):
        self.pico = PicoController(PICO_PORT)
        self.window = None
        self.waypoints = []
        
        self.x = 0
        self.y = 0
        self.z = 0
        self.yaw = 0
        
        self.loops = 0
        self.next_eat = 0
    
    def emergency_stop(self):
        """Аварийная остановка"""
        print("\n🛑 АВАРИЙНАЯ ОСТАНОВКА!")
        try:
            self.pico.release_key("W")
            self.pico.release_key("SHIFT")
            self.pico.release()
        except:
            pass
    
    def find_window(self):
        try:
            for w in gw.getAllWindows():
                if w.title == "VimeWorld":
                    return w
        except:
            pass
        return None
    
    def screenshot(self):
        if STOP_FLAG:
            return None
        if not self.window:
            self.window = self.find_window()
        if not self.window:
            return None
        try:
            x, y, w, h = self.window.left, self.window.top, self.window.width, self.window.height
            img = pyautogui.screenshot(region=(x, y, w, h))
            img.save(TEMP_SCREENSHOT)
            return TEMP_SCREENSHOT
        except:
            return None
    
    def update_pos(self):
        """Обновляет позицию"""
        if STOP_FLAG:
            return False
        img = self.screenshot()
        if img:
            data = read_f3(img)
            if data:
                if data['x'] is not None:
                    self.x = data['x']
                    self.y = data['y']
                    self.z = data['z']
                if data['yaw'] is not None:
                    self.yaw = data['yaw']
                log(f"📍 X={self.x:.1f} Z={self.z:.1f} | Yaw={self.yaw:.1f}°")
                return True
        return False
    
    def load_route(self):
        try:
            with open(ROUTE_FILE) as f:
                self.waypoints = json.load(f)
            print(f"✅ Загружено {len(self.waypoints)} точек")
            return True
        except:
            print(f"❌ Не найден {ROUTE_FILE}")
            return False
    
    def distance_to(self, tx, tz):
        return math.sqrt((self.x - tx)**2 + (self.z - tz)**2)
    
    def angle_to(self, tx, tz):
        dx = tx - self.x
        dz = tz - self.z
        angle = math.degrees(math.atan2(-dx, dz))
        return angle
    
    def normalize_yaw(self, yaw):
        """Нормализует yaw в диапазон -180..180"""
        while yaw > 180:
            yaw -= 360
        while yaw < -180:
            yaw += 360
        return yaw
    
    def check_turn_point(self):
        """Проверяет, находимся ли мы у точки поворота"""
        for turn in TURN_POINTS:
            dist = self.distance_to(turn['x'], turn['z'])
            if dist < 2.0:  # В пределах 2 блоков от точки поворота
                return turn
        return None
    
    def turn_to_yaw(self, target_yaw):
        """Крутится пока не достигнет нужного yaw, ВСЕГДА с SHIFT"""
        global STOP_FLAG
        
        target_yaw = self.normalize_yaw(target_yaw)
        
        print(f"🔄 Поворот на {target_yaw}°...")
        
        # Отпускаем только W и ЛКМ, SHIFT остаётся!
        log("   Отпускаю W, ЛКМ (SHIFT держим!)")
        self.pico.release_key("W")
        self.pico.release()
        time.sleep(0.1)
        
        # SHIFT всегда зажат!
        log("   Держу SHIFT")
        self.pico.hold_key("SHIFT")
        
        max_attempts = 15
        attempt = 0
        
        while attempt < max_attempts and not STOP_FLAG:
            attempt += 1
            
            # Читаем текущий yaw
            if not self.update_pos():
                time.sleep(0.1)
                continue
            
            current_yaw = self.normalize_yaw(self.yaw)
            
            # Разница
            diff = self.normalize_yaw(target_yaw - current_yaw)
            
            log(f"   Yaw: {current_yaw:.1f}° → {target_yaw}° (diff: {diff:.1f}°)")
            
            # Достигли?
            if abs(diff) < YAW_TOLERANCE:
                log(f"✅ Повернулись! Yaw={current_yaw:.1f}°")
                
                # После поворота: копать 1 сек + идти 1 сек
                log("   Копаю 1 сек...")
                self.pico.hold_left()
                time.sleep(1.0)
                self.pico.release()
                
                log("   Иду вперёд 1 сек...")
                self.pico.hold_key("W")
                time.sleep(1.0)
                self.pico.release_key("W")
                
                return True
            
            # Крутим
            pixels = int((diff / 90.0) * MOUSE_SENSITIVITY)
            
            # Ограничиваем шаг
            max_step = MOUSE_SENSITIVITY
            if abs(pixels) > max_step:
                pixels = max_step if pixels > 0 else -max_step
            
            self.pico.mouse_move(pixels, 0)
            time.sleep(0.3)
        
        print(f"⚠️  Поворот не точный (попытки: {attempt})")
        return False
    
    def turn_to(self, target_yaw):
        """Поворачивает к нужному yaw - ОДНИМ быстрым движением"""
        if STOP_FLAG:
            return
            
        diff = target_yaw - self.yaw
        
        while diff > 180: diff -= 360
        while diff < -180: diff += 360
        
        if abs(diff) < 5:
            return
        
        pixels = int((diff / 90.0) * MOUSE_SENSITIVITY)
        
        log(f"🔄 Быстрый поворот: {diff:.1f}° = {pixels}px")
        
        self.pico.mouse_move(pixels, 0)
    
    def go_to(self, wp):
        """Идёт к точке"""
        global STOP_FLAG
        
        tx, tz = wp['x'], wp['z']
        
        log(f"🎯 Цель: X={tx} Z={tz}")
        
        timeout = time.time() + 15
        
        while time.time() < timeout:
            if STOP_FLAG:
                self.emergency_stop()
                return False
            
            self.update_pos()
            
            # 🎯 Проверка точек поворота
            turn_point = self.check_turn_point()
            if turn_point:
                print(f"\n🎯 ТОЧКА ПОВОРОТА!")
                self.turn_to_yaw(turn_point['target_yaw'])
                
                # После поворота продолжаем с SHIFT + W + ЛКМ
                log("   Возобновляю SHIFT + W + ЛКМ")
                self.pico.hold_key("SHIFT")
                time.sleep(0.02)
                self.pico.hold_key("W")
                time.sleep(0.02)
                self.pico.hold_left()
                time.sleep(0.2)
            
            dist = self.distance_to(tx, tz)
            
            if dist < WAYPOINT_RADIUS:
                log(f"✅ Достигли! ({dist:.1f} блоков)")
                return True
            
            target_angle = self.angle_to(tx, tz)
            self.turn_to(target_angle)
            
            time.sleep(0.2)
        
        log(f"⏰ Таймаут!")
        return False
    
    def eat(self):
        if STOP_FLAG:
            return
            
        print("🍖 Ем...")
        
        log("   ↳ Отпускаю W, SHIFT, ЛКМ")
        self.pico.release_key("W")
        self.pico.release_key("SHIFT")
        self.pico.release()
        time.sleep(0.2)
        
        log(f"   ↳ Слот {FOOD_SLOT} (еда)")
        self.pico.slot(FOOD_SLOT)
        
        log("   ↳ Зажимаю ПКМ")
        self.pico.hold_right()
        time.sleep(2.5)
        
        self.pico.release()
        
        log(f"   ↳ Слот {PICKAXE_SLOT} (кирка)")
        self.pico.slot(PICKAXE_SLOT)
        
        log("   ↳ Зажимаю SHIFT + W + ЛКМ")
        self.pico.hold_key("SHIFT")
        self.pico.hold_key("W")
        self.pico.hold_left()
        
        self.next_eat = time.time() + EAT_INTERVAL
        print("✅ Поел!")
    
    def run_route(self):
        """Проходит маршрут один раз"""
        global STOP_FLAG
        
        print(f"\n🚀 Маршрут ({len(self.waypoints)} точек)")
        
        log("🎮 Зажимаю SHIFT + W + ЛКМ")
        self.pico.hold_key("SHIFT")
        time.sleep(0.02)
        self.pico.hold_key("W")
        time.sleep(0.02)
        self.pico.hold_left()
        time.sleep(0.1)
        
        for i, wp in enumerate(self.waypoints):
            if STOP_FLAG:
                self.emergency_stop()
                return
            
            print(f"\n   --- Точка {i+1}/{len(self.waypoints)} ---")
            
            if time.time() >= self.next_eat:
                self.eat()
            
            ok = self.go_to(wp)
            
            if STOP_FLAG:
                self.emergency_stop()
                return
            
            status = "✅" if ok else "⚠️"
            print(f"   {status} Точка {i+1}/{len(self.waypoints)}")
        
        self.loops += 1
    
    def run(self):
        global STOP_FLAG
        
        print("="*50)
        print("▶️  ROUTE PLAYER + AUTO TURNS")
        print(f"   Сенса: {MOUSE_SENSITIVITY} px/90°")
        if TURN_POINTS:
            print(f"   Точек поворота: {len(TURN_POINTS)}")
        print("="*50)
        print("🛑 ОСТАНОВКА: нажми Q в любой момент!")
        print("="*50)
        
        # Pico
        print("🔌 Pico...")
        if not self.pico.connect():
            print("❌ Pico не найден!")
            return
        print("✅ OK")
        
        # Окно
        print("🔎 Minecraft...")
        self.window = self.find_window()
        if not self.window:
            print("❌ VimeWorld не найден!")
            return
        print(f"✅ {self.window.title}")
        
        # Маршрут
        if not self.load_route():
            return
        
        # Запускаем слушатель клавиш в отдельном потоке
        listener = threading.Thread(target=keyboard_listener, daemon=True)
        listener.start()
        
        print("="*50)
        input("▶️  Enter когда готов - и переключайся на Minecraft!")
        
        for i in range(3, 0, -1):
            print(f"   {i}...")
            time.sleep(1)
        print("🚀 ПОЕХАЛИ!\n")
        
        log(f"🔧 Слот {PICKAXE_SLOT} (кирка)")
        self.pico.slot(PICKAXE_SLOT)
        self.next_eat = time.time() + EAT_INTERVAL
        
        start = time.time()
        
        try:
            loop = 0
            while (REPEAT_COUNT == 0 or loop < REPEAT_COUNT) and not STOP_FLAG:
                loop += 1
                print(f"\n{'='*50}")
                print(f"🔄 Цикл {loop}")
                print(f"{'='*50}")
                self.run_route()
                
                if STOP_FLAG:
                    break
                    
                time.sleep(1)
                
        except KeyboardInterrupt:
            log("⛔ Ctrl+C")
        finally:
            print("\n⏹️  Стоп!")
            log("🛑 Отпускаю ВСЁ")
            self.pico.release_key("W")
            self.pico.release_key("SHIFT")
            self.pico.release()
            self.pico.close()
            mins = (time.time() - start) / 60
            print(f"📊 {mins:.1f} мин | Циклов: {self.loops}")


if __name__ == "__main__":
    bot = RouteBot()
    bot.run()