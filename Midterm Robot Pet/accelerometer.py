from machine import Pin, I2C
import time
import ustruct

# LIS3DH accelerometer (I2C address 0x19 = 25)
ADDR = 0x19


class Accel:
    def __init__(self, sda=21, scl=22):
        self.i2c = I2C(0, sda=Pin(sda), scl=Pin(scl))
        # "who am I" check -- a LIS3DH answers 0x33
        who = self.i2c.readfrom_mem(ADDR, 0x0F, 1)[0]
        print("WHO_AM_I:", hex(who), "(LIS3DH = 0x33)")
        # CTRL_REG1: 100 readings/sec, X Y Z on
        self.i2c.writeto_mem(ADDR, 0x20, bytes([0x57]))
        # CTRL_REG4: +/-4g range, high resolution
        self.i2c.writeto_mem(ADDR, 0x23, bytes([0x18]))

    def read(self):
        # returns x, y, z in g's (1.0 = gravity)
        data = self.i2c.readfrom_mem(ADDR, 0x28 | 0x80, 6)  # 0x80 = read all 6 bytes in a row
        x, y, z = ustruct.unpack("<hhh", data)
        return x / 8192, y / 8192, z / 8192   # +/-4g range -> 8192 counts per g


# Step 2 test: print live values
if __name__ == "__main__":
    acc = Accel()
    while True:
        x, y, z = acc.read()
        print("X: {:6.2f}  Y: {:6.2f}  Z: {:6.2f}".format(x, y, z))
        time.sleep(0.1)
