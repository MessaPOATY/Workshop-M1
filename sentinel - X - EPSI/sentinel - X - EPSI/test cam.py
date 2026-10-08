import cv2
print("OpenCV :", cv2.__version__)
cap = cv2.VideoCapture(0)
print("Camera ouverte :", cap.isOpened())
ok, frame = cap.read()
print("Image lue :", ok)
if ok:
    cv2.imshow("test", frame)
    cv2.waitKey(3000)
cap.release()