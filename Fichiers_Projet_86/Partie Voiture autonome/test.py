from ultralytics import YOLO

model = YOLO("weights.pt")
results = model.predict(source=1, show=False, imgsz=320, conf=0.4)
