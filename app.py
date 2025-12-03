import os
import uuid
import cv2
from flask import Flask, render_template, request, redirect, url_for
from ultralytics import YOLO

# Flask 설정
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["RESULT_FOLDER"] = os.path.join("static", "results")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["RESULT_FOLDER"], exist_ok=True)

# YOLO 모델 로드
model = YOLO("yolov8s.pt")

# 간단한 칼로리 테이블
CALORIE_TABLE = {
    "pizza": 285,
    "burger": 295,
    "sandwich": 250,
    "hot dog": 290,
    "cake": 350,
    "donut": 250,
    "banana": 96,
    "apple": 52,
    "orange": 47,
    "bottle": 0,
    "egg": 78,
}


# 음식 클래스만 계산
FOOD_CLASSES = [
    "pizza", "burger", "sandwich", "hot dog", "cake",
    "donut", "banana", "apple", "orange"
]

# 무시할 클래스
IGNORE_CLASSES = [
    "person", "cell phone", "scissors", "tie", "book", "chair", "tv",
    "keyboard", "mouse", "couch", "cat", "dog", "bottle", "cup",
    "remote", "umbrella", "handbag", "sports ball", "backpack",
    "car", "bus", "truck", "boat", "train"
]

def is_food(label: str) -> bool:
    """YOLO 클래스 이름이 음식인지 판별"""
    label = label.lower()
    return (label in FOOD_CLASSES) or ("food" in label)


def estimate_calories(label: str) -> int:
    """음식 이름 기반 + 카테고리 기반 칼로리 추정"""
    label = label.lower()
    
    # 1) 정확히 등록된 음식이면 즉시 반환
    for key, value in CALORIE_TABLE.items():
        if key in label:
            return value

    # 2) 음식 카테고리 기반 추정
    if any(word in label for word in ["bread", "bun", "toast", "bakery"]):
        return 260

    if any(word in label for word in ["noodle", "ramen", "soup"]):
        return 480

    if any(word in label for word in ["chicken", "beef", "meat", "pork"]):
        return 230

    if any(word in label for word in ["fish", "salmon", "tuna"]):
        return 150

    if any(word in label for word in ["fruit", "melon", "grape", "berry"]):
        return 60

    if any(word in label for word in ["vegetable", "salad", "lettuce"]):
        return 25

    if any(word in label for word in ["cookie", "dessert", "chocolate", "snack"]):
        return 300

    # 3) 위에 없는 경우 기본값
    return 200


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return redirect(url_for("index"))

    file = request.files["image"]
    if file.filename == "":
        return redirect(url_for("index"))

    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(upload_path)

    # YOLO 추론
    results = model(upload_path)[0]
    img = cv2.imread(upload_path)

    detections = []
    total_calories = 0

    for box in results.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        label = results.names[cls_id]

        # 무시할 객체 제외
        if label in IGNORE_CLASSES:
            continue

        # 음식 아닌 객체 제외
        if not is_food(label):
            continue

        # 칼로리 계산
        calories = estimate_calories(label)
        total_calories += calories

        # 저장
        detections.append({
            "label": label,
            "confidence": conf,
            "box": [x1, y1, x2, y2],
            "calories": calories
        })

        # 박스 드로잉
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(img, f"{label} {conf:.2f}", (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # 결과 이미지 저장
    result_filename = f"result_{filename}"
    result_path = os.path.join(app.config["RESULT_FOLDER"], result_filename)
    cv2.imwrite(result_path, img)

    return render_template(
        "result.html",
        detections=detections,
        total_calories=total_calories,
        original_image_url=url_for("static", filename=f"uploads/{filename}"),
        result_image_url=url_for("static", filename=f"results/{result_filename}")
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
