import cv2
camera = cv2.VideoCapture(0) # try other numbers if you have other cameras
import numpy as np


if not camera.isOpened():
	print("camera is not availabale")
	

	
while True:
    blueframe = np.full((200,200,3),(255,0,0), dtype = np.uint8)
    cv2.imshow("blueonly",blueframe)

    ret, frame = camera.read()

    cv2.imshow("FART!!!!!", frame)
    cv2.waitKey(1) # this function draws your frame
    newframe = cv2.resize(frame, (10, 10))  # 200 is width and 300 is height
    frame = cv2.flip(frame, 1) 