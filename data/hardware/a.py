from ultralytics import YOLO
import cv2
import time
import serial

# 🔌 SERIAL CONNECTIONS
PORT_IR = 'COM9'     # Arduino 1 (IR + Conveyor)
PORT_SORT = 'COM10'   # Arduino 2 (Stepper + Servo)
BAUD = 9600

try: 
    arduino_ir = serial.Serial(PORT_IR, BAUD, timeout=1)
    print("✅ Arduino 1 (IR) Connected")
except Exception as e:
    print("❌ Arduino 1 NOT connected:", e)
    exit()

try:
    arduino_sort = serial.Serial(PORT_SORT, BAUD, timeout=1)
    print("✅ Arduino 2 (Sorter) Connected")
except Exception as e:
    print("❌ Arduino 2 NOT connected:", e)
    exit()

time.sleep(2)

# 🤖 LOAD YOLO
model = YOLO("yolov8n.pt")
model.to("cpu")

# 📦 CATEGORY LISTS
e_waste = ['cell phone', 'keyboard', 'mouse', 'laptop', 'tv', 'remote']
recyclable = ['banana', 'apple', 'orange', 'broccoli', 'book', 'bottle', 'cup']
non_recyclable = []

label_map = {
    'bottle': 'plastic',
    'cup': 'plastic',
    'book': 'paper',
    'tv': 'e-waste',
    'cell phone': 'e-waste'
}

def classify(label):
    label = label_map.get(label, label)

    if label in e_waste or label == 'e-waste':
        return "E"
    elif label in non_recyclable or label == 'plastic':
        return "N"
    elif label in recyclable or label in ['paper', 'cardboard']:
        return "B"
    else:
        return "U"

print("🚀 Waiting for IR trigger from Arduino 1...")

while True:

    # 📡 LISTEN FROM ARDUINO 1
    if arduino_ir.in_waiting > 0:
        signal = arduino_ir.readline().decode().strip()

        if signal == "DETECT":
            print("📸 Object detected → Capturing...")


            # 🎥 CAPTURE IMAGE
            cap = cv2.VideoCapture(1)
            time.sleep(0.5)

            ret, frame = cap.read()
            cap.release()

            if not ret:
                print("❌ Camera Error")
                continue

            # 🧠 YOLO
            results = model(frame, conf=0.5)
            detected_category = "U"

            for r in results:
                if len(r.boxes) > 0:
                    box = max(r.boxes, key=lambda b: float(b.conf[0]))
                    cls_id = int(box.cls[0])
                    label = model.names[cls_id]

                    print("Detected:", label)

                    detected_category = classify(label)
                    break

            # 🔌 SEND TO ARDUINO 2 (SORTING)
            try:
                if detected_category == "E":
                    arduino_sort.write(b'1')
                    print("➡ Sent to Sorter: 1 (E-WASTE)")
                elif detected_category == "B":
                    arduino_sort.write(b'2')
                    print("➡ Sent to Sorter: 2 (BIO)")
                elif detected_category == "N":
                    arduino_sort.write(b'3')
                    print("➡ Sent to Sorter: 3 (NON-BIO)")
                else:
                    arduino_sort.write(b'4')
                    print("➡ Sent to Sorter: 4 (UNKNOWN)")

            except Exception as e:
                print("❌ Serial Error:", e)

            # ⏱ avoid duplicate triggers
            time.sleep(2)