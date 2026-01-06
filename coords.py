"""
coords.py - Чтение XYZ из F3 (Tesseract с улучшенной обработкой)
Для VimeWorld формата
"""

import cv2
import numpy as np
import re
import pytesseract

# Путь к Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def read_f3(image_path, debug=False):
    """Читает данные из F3"""
    
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    h, w = img.shape[:2]
    
    # F3 область - левая верхняя часть
    roi = img[0:int(h*0.4), 0:int(w*0.45)]
    
    # Увеличиваем x3 для лучшего распознавания
    roi = cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    
    # Конвертируем в HSV для выделения белого/светлого текста
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # Маска для светлого текста (белый, жёлтый, светло-серый)
    lower = np.array([0, 0, 180])
    upper = np.array([180, 50, 255])
    mask = cv2.inRange(hsv, lower, upper)
    
    # Также добавляем жёлтый текст (XYZ строка)
    lower_yellow = np.array([20, 50, 150])
    upper_yellow = np.array([40, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    # Объединяем маски
    combined = cv2.bitwise_or(mask, mask_yellow)
    
    # Немного размываем и усиливаем
    combined = cv2.dilate(combined, None, iterations=1)
    
    # OCR с настройками для однострочного текста
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=XYZxyz0123456789-,./: '
    text = pytesseract.image_to_string(combined, config=custom_config)
    
    if debug:
        print("=== RAW TEXT ===")
        print(text)
        print("================")
        # Сохраняем обработанное изображение для отладки
        cv2.imwrite("debug_mask.png", combined)
        print("Сохранено: debug_mask.png")
    
    data = {
        'x': None, 'y': None, 'z': None,
        'facing': None, 'yaw': None, 'pitch': None
    }
    
    # ===== ПАРСИНГ XYZ =====
    # Ищем паттерн с числами через /
    # "-1333,700 / 98,000 / 783,700"
    xyz_match = re.search(
        r'(-?\d+[,\.]\d+)\s*/\s*(\d+[,\.]\d+)\s*/\s*(-?\d+[,\.]\d+)',
        text
    )
    
    if xyz_match:
        try:
            data['x'] = parse_num(xyz_match.group(1))
            data['y'] = parse_num(xyz_match.group(2))
            data['z'] = parse_num(xyz_match.group(3))
        except:
            pass
    
    # Если не нашли - пробуем без /
    if data['x'] is None:
        xyz_match2 = re.search(
            r'[XxYy][Yy]?[Zz][:\s]+(-?[\d,\.]+)\s+([\d,\.]+)\s+(-?[\d,\.]+)',
            text
        )
        if xyz_match2:
            try:
                data['x'] = parse_num(xyz_match2.group(1))
                data['y'] = parse_num(xyz_match2.group(2))
                data['z'] = parse_num(xyz_match2.group(3))
            except:
                pass
    
    # ===== FACING (читаем из оригинального изображения) =====
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    full_text = pytesseract.image_to_string(binary, config='--psm 6')
    
    facing_match = re.search(r'[Ff]acing[:\s]*(\w+)', full_text)
    if facing_match:
        f = facing_match.group(1).lower()
        if f in ['north', 'south', 'east', 'west']:
            data['facing'] = f
    
    # ===== YAW/PITCH =====
    yp_match = re.search(r'\((-?[\d,\.]+)\s*[/\s]\s*(-?[\d,\.]+)\)', full_text)
    if yp_match:
        try:
            data['yaw'] = float(yp_match.group(1).replace(',', '.'))
            data['pitch'] = float(yp_match.group(2).replace(',', '.'))
        except:
            pass
    
    return data


def parse_num(s):
    """Парсит VimeWorld число: "1333,700" -> 1333.7"""
    s = s.strip().replace(',', '.')
    return float(s)


def read_xyz(image_path, debug=False):
    """Только XYZ"""
    data = read_f3(image_path, debug)
    if data and data['x'] is not None:
        return (data['x'], data['y'], data['z'])
    return None


if __name__ == "__main__":
    import sys
    
    path = sys.argv[1] if len(sys.argv) > 1 else "test.png"
    
    print(f"Читаю {path}...")
    data = read_f3(path, debug=True)
    
    if data and data['x'] is not None:
        print(f"\n✅ РЕЗУЛЬТАТ:")
        print(f"   X: {data['x']}")
        print(f"   Y: {data['y']}")  
        print(f"   Z: {data['z']}")
        print(f"   Facing: {data['facing']}")
        print(f"   Yaw: {data['yaw']}")
        print(f"   Pitch: {data['pitch']}")
    else:
        print("\n❌ Не удалось распознать!")