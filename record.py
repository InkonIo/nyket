"""
record.py - Записывает маршрут по координатам

1. Запусти
2. Enter - начинается таймер
3. Переключись на Minecraft и ходи
4. Через N секунд - сохраняет route.json
"""

import time
import json
import pyautogui
import pygetwindow as gw

from coords import read_xyz

# ========== НАСТРОЙКИ ==========

ROUTE_FILE = "route.json"
DELAY_BEFORE = 3      # Секунд до старта
RECORD_DURATION = 80 # Секунд записи маршрута 
READ_INTERVAL = 0.1   # Как часто читать координаты

TEMP_SCREENSHOT = "screen.png"


def find_window():
    try:
        for w in gw.getAllWindows():
            if w.title == "VimeWorld":
                return w
    except:
        pass
    return None


def take_screenshot(window):
    if not window:
        return None
    try:
        x, y, w, h = window.left, window.top, window.width, window.height
        img = pyautogui.screenshot(region=(x, y, w, h))
        img.save(TEMP_SCREENSHOT)
        return TEMP_SCREENSHOT
    except:
        return None


def main():
    print("="*50)
    print("🎬 ROUTE RECORDER")
    print("="*50)
    
    # Окно
    print("🔎 Minecraft...")
    window = find_window()
    if not window:
        print("❌ VimeWorld не найден!")
        return
    print(f"✅ {window.title}")
    
    print(f"\n⏱️  Задержка: {DELAY_BEFORE} сек")
    print(f"⏱️  Запись: {RECORD_DURATION} сек")
    print("="*50)
    
    input("\n▶️  Enter - и переключайся на Minecraft!\n")
    
    # Отсчёт
    for i in range(DELAY_BEFORE, 0, -1):
        print(f"   {i}...")
        time.sleep(1)
    
    print("\n🔴 ЗАПИСЬ! Ходи по маршруту...\n")
    
    # Записываем
    waypoints = []
    start_time = time.time()
    last_x, last_z = None, None
    
    while time.time() - start_time < RECORD_DURATION:
        elapsed = time.time() - start_time
        
        # Скриншот и координаты
        screenshot = take_screenshot(window)
        if screenshot:
            coords = read_xyz(screenshot, debug=False)
            if coords:
                x, y, z = coords
                
                # Записываем если сдвинулись на 2+ блока
                if last_x is None or abs(x - last_x) > 2 or abs(z - last_z) > 2:
                    waypoints.append({
                        'x': round(x, 1),
                        'y': round(y, 1),
                        'z': round(z, 1),
                        'time': round(elapsed, 1)
                    })
                    print(f"   📍 X={x:.1f} Z={z:.1f} (точка {len(waypoints)})")
                    last_x, last_z = x, z
        
        # Прогресс
        remaining = int(RECORD_DURATION - elapsed)
        if int(elapsed) % 20 == 0 and int(elapsed) > 0:
            print(f"   ⏱️  {remaining} сек | Точек: {len(waypoints)}")
        
        time.sleep(READ_INTERVAL)
    
    print("\n⏹️  СТОП!")
    
    # Сохраняем
    if waypoints:
        with open(ROUTE_FILE, 'w') as f:
            json.dump(waypoints, f, indent=2)
        
        print(f"\n✅ Сохранено: {ROUTE_FILE}")
        print(f"   📊 Точек: {len(waypoints)}")
        print(f"   ⏱️  Время: {waypoints[-1]['time']} сек")
    else:
        print("\n❌ Нет точек! Проверь F3.")


if __name__ == "__main__":
    main()