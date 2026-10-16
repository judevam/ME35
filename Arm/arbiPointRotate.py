import numpy as np
import matplotlib.pyplot as plt

def rotate_around_point(x, y, cx, cy, theta):
    point = np.array([x,y,1])
    
    # Translate to origin
    translation_x = -cx
    translation_y = -cy
    translation_matrix = np.array([
    [1,0,translation_x],
    [0,1,translation_y],
    [0,0,1]])

    translate_Origin = translation_matrix @ point

    # Rotate
    rotation_matrix = np.array([
    [np.cos(theta), -np.sin(theta),0],
    [np.sin(theta), np.cos(theta),0],
    [0,0,1]
    ])
    
    rotate_Origin = rotation_matrix @ translate_Origin
    
    # Translate back
    translation_x = cx
    translation_y = cy
    translation_matrix = np.array([
    [1,0,translation_x],
    [0,1,translation_y],
    [0,0,1]])
    
    final = translation_matrix @ rotate_Origin
    
    x_final = final[0]
    y_final = final[1]
    print(x_final)
    print(y_final)
    
    return x_final, y_final

rotate_around_point(10, 11, 3, 4, np.pi/3)
