"""
mine_digger.py - Автоматическая копалка шахты

Копает туннели 2 блока в высоту с интервалом через 2 блока
Двигается змейкой по всей области
ВСЕГДА НА ШИФТЕ (чтобы не упасть)
"""

import time
import math
import pyautogui
import pygetwindow as gw

from pico_controller import PicoController
from coords import read_f3

# ========== НАСТРОЙКИ ==========

PICO_PORT = "COM4"
PICKAXE_SLOT = 2

# Координаты шахты
START_X = -1333.7
START_Z = 759.3
END_X = -1309.3
END_Z = 783.7

# Длина одного туннеля (блоков)
TUNNEL_LENGTH = 24
# Расстояние между туннелями
TUNNEL_SPACING = 3

# ========== КАЛИБРОВКА ==========

# Чувствительность мыши (пикселей для поворота на 90°)
# Подстраивай под свою сенсу через калибровку!
MOUSE_SENSITIVITY = 163

# ========== КОНСТАНТЫ (НЕ МЕНЯТЬ) ==========

# Скорость копания аметиста железной киркой с ЭФ4
BLOCK_BREAK_TIME = 0.45  # секунд на блок

# Скорость ходьбы на шифте (присед)
SNEAK_SPEED = 1.4  # м/с (блоков в секунду)

TEMP_SCREENSHOT = "screen.png"


class MineDigger:
    def __init__(self):
        self.pico = PicoController(PICO_PORT)
        self.window = None
        
        self.x = 0
        self.y = 0
        self.z = 0
        self.yaw = 0
        
        self.tunnels_done = 0
        self.blocks_mined = 0
    
    def find_window(self):
        try:
            for w in gw.getAllWindows():
                if w.title == "VimeWorld":
                    return w
        except:
            pass
        return None
    
    def screenshot(self):
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
                return True
        return False
    
    def distance_to(self, tx, tz):
        return math.sqrt((self.x - tx)**2 + (self.z - tz)**2)
    
    def angle_to(self, tx, tz):
        """Угол к точке"""
        dx = tx - self.x
        dz = tz - self.z
        angle = math.degrees(math.atan2(-dx, dz))
        return angle
    
    def turn_to(self, target_yaw):
        """Поворачивает к нужному yaw"""
        self.update_pos()
        
        diff = target_yaw - self.yaw
        while diff > 180: diff -= 360
        while diff < -180: diff += 360
        
        if abs(diff) < 5:
            return
        
        # Пикселей для поворота
        pixels_needed = int((diff / 90.0) * MOUSE_SENSITIVITY)
        
        # Поворачиваем плавно
        steps = max(abs(pixels_needed) // 10, 1)
        step_size = pixels_needed // steps
        
        for _ in range(steps):
            self.pico.mouse_move(step_size, 0)
            time.sleep(0.03)
            
        time.sleep(0.2)
    
    def turn_direction(self, direction):
        """Поворачивает в направление"""
        directions = {
            'north': 180,   # -Z
            'south': 0,     # +Z
            'east': -90,    # +X
            'west': 90      # -X
        }
        target = directions.get(direction, 0)
        self.turn_to(target)
    
    def walk_forward(self, blocks):
        """Идёт вперёд N блоков НА ШИФТЕ"""
        self.update_pos()
        start_x, start_z = self.x, self.z
        
        print(f"      🚶 Иду {blocks} блоков (shift + W)...")
        
        # Зажимаем SHIFT + W и копаем
        self.pico.hold_key("LSHIFT")
        time.sleep(0.1)
        self.pico.hold_key("W")
        self.pico.hold_left()
        
        # Время на прохождение (с запасом)
        estimated_time = blocks / SNEAK_SPEED
        timeout = time.time() + (estimated_time * 2)
        
        last_dist = 0
        stuck_count = 0
        
        while time.time() < timeout:
            self.update_pos()
            dist = self.distance_to(start_x, start_z)
            
            # Проверяем, не застряли ли
            if abs(dist - last_dist) < 0.1:
                stuck_count += 1
                if stuck_count > 10:
                    print("      ⚠️  Застрял! Прыгаю...")
                    self.pico.key("SPACE")
                    stuck_count = 0
            else:
                stuck_count = 0
            
            last_dist = dist
            
            # Достигли цели?
            if dist >= blocks - 0.3:
                break
            
            time.sleep(0.1)
        
        # Останавливаемся
        self.pico.release_key("W")
        self.pico.release_key("LSHIFT")
        self.pico.release()
        time.sleep(0.3)
        
        self.blocks_mined += blocks
        print(f"      ✅ Прошёл {dist:.1f} блоков")
    
    def dig_tunnel(self, direction, length):
        """Копает один туннель"""
        print(f"\n   🔨 Туннель #{self.tunnels_done + 1} ({direction}, {length} блоков)")
        
        self.turn_direction(direction)
        time.sleep(0.5)
        
        # Идём и копаем
        self.walk_forward(length)
        
        self.tunnels_done += 1
        print(f"   ✅ Туннель готов! (всего: {self.tunnels_done})")
    
    def move_to_next_tunnel(self, direction):
        """Переходит к следующему туннелю"""
        print(f"\n   ➡️  Переход к следующему туннелю...")
        
        # Поворачиваем перпендикулярно
        if direction in ['north', 'south']:
            # Идём на восток
            self.turn_direction('east')
        else:
            # Идём на север
            self.turn_direction('north')
        
        time.sleep(0.3)
        self.walk_forward(TUNNEL_SPACING)
        time.sleep(0.5)
    
    def dig_mine(self):
        """Копает всю шахту змейкой"""
        print("\n" + "="*50)
        print("🚀 НАЧИНАЮ КОПАТЬ ШАХТУ!")
        print(f"   Размер: {TUNNEL_LENGTH}x{TUNNEL_LENGTH}")
        print(f"   Интервал: {TUNNEL_SPACING} блока")
        print(f"   Режим: SHIFT (не упадём)")
        print("="*50)
        
        # Зажимаем SHIFT на всю копку
        self.pico.hold_key("LSHIFT")
        time.sleep(0.2)
        
        # Первый туннель - на север
        direction = 'north'
        tunnels_count = int(TUNNEL_LENGTH / TUNNEL_SPACING)
        
        try:
            for i in range(tunnels_count):
                # Копаем туннель
                self.dig_tunnel(direction, TUNNEL_LENGTH)
                
                # Если не последний - переходим к следующему
                if i < tunnels_count - 1:
                    self.move_to_next_tunnel(direction)
                    
                    # Меняем направление (змейка)
                    direction = 'south' if direction == 'north' else 'north'
                
                time.sleep(1)
        finally:
            # Отпускаем SHIFT
            self.pico.release_key("LSHIFT")
        
        print("\n" + "="*50)
        print(f"✅ ШАХТА ГОТОВА!")
        print(f"   Туннелей: {self.tunnels_done}")
        print(f"   Блоков выкопано: ~{self.blocks_mined}")
        print("="*50)
    
    def calibrate_mouse(self):
        """Калибровка чувствительности мыши"""
        print("\n" + "="*50)
        print("🎯 КАЛИБРОВКА ЧУВСТВИТЕЛЬНОСТИ МЫШИ")
        print("="*50)
        print("1. Встань в игре и смотри строго на СЕВЕР (F3)")
        print("   yaw должен быть 180° или -180°")
        print("2. Нажми Enter")
        print("3. Бот повернёт тебя на ЗАПАД (налево на 90°)")
        print("4. ЦЕЛЬ: yaw должен стать РОВНО 90.0°")
        print("5. Повторяй калибровку, меняя MOUSE_SENSITIVITY")
        print("="*50)
        print("\n💡 ЛОГИКА:")
        print("   - Если yaw > 90° (перекрутил) → УВЕЛИЧЬ MOUSE_SENSITIVITY")
        print("   - Если yaw < 90° (недокрутил) → УМЕНЬШИ MOUSE_SENSITIVITY")
        print("="*50)
        
        input("\n▶️  Enter когда смотришь на север...")
        
        self.update_pos()
        start_yaw = self.yaw
        print(f"\n📍 Текущий yaw: {start_yaw}°")
        
        target_yaw = 90.0
        
        print(f"\n🔄 Поворачиваю на ЗАПАД (цель: 90°)...")
        self.turn_to(target_yaw)
        
        time.sleep(0.3)
        self.update_pos()
        final_yaw = self.yaw
        
        error = final_yaw - 90.0
        
        print(f"\n📊 РЕЗУЛЬТАТ:")
        print(f"   Было: {start_yaw}°")
        print(f"   Стало: {final_yaw}°")
        print(f"   Ошибка: {error:+.1f}° (цель: 0°)")
        print(f"   MOUSE_SENSITIVITY: {MOUSE_SENSITIVITY}")
        
        if abs(error) < 1.0:
            print(f"\n✅ ИДЕАЛЬНО! Ошибка < 1°")
            print(f"   Запусти копалку (режим 2)")
        elif abs(error) < 3.0:
            print(f"\n✅ ХОРОШО! Ошибка < 3°")
            print(f"   Можно копать или улучшить точность")
        else:
            print(f"\n⚠️  НУЖНА КОРРЕКЦИЯ!")
            
        # Подсказка
        if abs(error) > 1.0:
            # Если недокрутил (yaw < 90) → нужно меньше MOUSE_SENSITIVITY
            # Если перекрутил (yaw > 90) → нужно больше MOUSE_SENSITIVITY
            new_sens = MOUSE_SENSITIVITY * (90.0 / (90.0 - error))
            print(f"\n💡 РЕКОМЕНДАЦИЯ:")
            print(f"   Попробуй: MOUSE_SENSITIVITY = {new_sens:.1f}")
            print(f"   (сейчас {MOUSE_SENSITIVITY})")
    
    def run(self):
        print("="*50)
        print("⛏️  MINE DIGGER - АВТОКОПАЛКА")
        print("="*50)
        
        # Pico
        print("🔌 Подключаюсь к Pico...")
        if not self.pico.connect():
            print("❌ Pico не найден!")
            return
        print("✅ Pico готов")
        
        # Окно
        print("🔎 Ищу Minecraft...")
        self.window = self.find_window()
        if not self.window:
            print("❌ VimeWorld не найден!")
            return
        print(f"✅ {self.window.title}")
        
        print("\n" + "="*50)
        print("ВЫБЕРИ РЕЖИМ:")
        print("1. Калибровка мыши (настрой сенсу)")
        print("2. Копать шахту")
        print("="*50)
        
        choice = input("\nВведи номер: ").strip()
        
        if choice == "1":
            self.calibrate_mouse()
            self.pico.close()
            return
        
        print("\n" + "="*50)
        print("📍 Встань в НАЧАЛЬНУЮ точку шахты")
        print("   (угол, откуда начинать копать)")
        print("🔨 Возьми в руки КИРКУ (слот 2)")
        print("⚠️  Убедись, что нет дыр в полу!")
        print("="*50)
        input("\n▶️  Enter когда готов...\n")
        
        # Выбираем слот с киркой
        self.pico.slot(PICKAXE_SLOT)
        time.sleep(0.3)
        
        start = time.time()
        
        try:
            self.dig_mine()
        except KeyboardInterrupt:
            print("\n⏹️  Остановлено!")
        finally:
            self.pico.release()
            self.pico.release_key("LSHIFT")
            self.pico.close()
            
            mins = (time.time() - start) / 60
            print(f"\n📊 Время: {mins:.1f} мин")
            print(f"   Туннелей: {self.tunnels_done}")
            print(f"   Блоков: ~{self.blocks_mined}")


if __name__ == "__main__":
    digger = MineDigger()
    digger.run()