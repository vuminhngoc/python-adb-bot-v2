# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import sys  # to access the system
import cv2
from ppadb.client import Client as AdbClient
import numpy as np
from pyscreeze import *
import datetime
from threading import Thread
import re
from pytesseract import pytesseract
import cv2
from time import sleep
import winsound
from pynput import keyboard
from datetime import *
import random
import logging
from logging import config
import telepot
from img_util import get_grayscale, thresholding
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import time

log_config = {
    "version": 1,
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG"
    },
    "handlers": {
        "console": {
            "formatter": "std_out",
            "class": "logging.StreamHandler",
            "level": "DEBUG"
        },
        "file": {
            "formatter": "std_out",
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "filename": "logs/app.log",
            "maxBytes": 10485760,
            "backupCount": 40,
            "encoding": "utf8"
        }
    },
    "formatters": {
        "std_out": {
            "format": "%(asctime)s : %(levelname)s : %(module)s : %(funcName)s : %(lineno)d : %(message)s",
            "datefmt": "%d-%m-%Y %I:%M:%S"
        }
    },
}

config.dictConfig(log_config)

done = [False, False, False, False]  # danh dau da xong phan nao
bot = telepot.Bot('5725931529:AAH6DDwcN_FlKEzDaccE7cTFYGFYcV8DpNM')
start_minute = 5

pause = False
last_mine = None
force_done = False
traveled_mines = []
is_full_queue = False
share_status = True
share_lv = 2  # lvl mỏ mà cao hơn lvl này thì sẽ không share cho liên minh

client = AdbClient(host="127.0.0.1", port=5037)
device = client.device("emulator-5554")


def locateAllOnScreen(image, screenshotIm, **kwargs):
    """
    TODO
    """
    retVal = locateAll(image, screenshotIm, **kwargs)
    try:
        screenshotIm.fp.close()
    except AttributeError:
        # Screenshots on Windows won't have an fp since they came from
        # ImageGrab, not a file. Screenshots on Linux will have fp set
        # to None since the file has been unlinked
        pass
    return retVal


def locateOnScreen(image, screenshotIm, minSearchTime=0, **kwargs):
    """TODO - rewrite this
    minSearchTime - amount of time in seconds to repeat taking
    screenshots and trying to locate a match.  The default of 0 performs
    a single search.
    """
    start = time.time()
    while True:
        try:

            retVal = locate(image, screenshotIm, **kwargs)
            try:
                screenshotIm.fp.close()
            except AttributeError:
                # Screenshots on Windows won't have an fp since they came from
                # ImageGrab, not a file. Screenshots on Linux will have fp set
                # to None since the file has been unlinked
                pass
            if retVal or time.time() - start > minSearchTime:
                return retVal
        except ImageNotFoundException:
            if time.time() - start > minSearchTime:
                if USE_IMAGE_NOT_FOUND_EXCEPTION:
                    raise
                else:
                    return None


def locateCenterOnScreen(image, screenshotIm, **kwargs):
    """
    TODO
    """
    coords = locateOnScreen(image, screenshotIm, **kwargs)
    if coords is None:
        return None
    else:
        return center(coords)


def send_telebot(chatid, _str_coo, file_name):
    try:
        bot.sendMessage(chatid, _str_coo)
        bot.sendPhoto(chatid, photo=open(file_name, 'rb'))
    except:
        pass


# Tìm và điều quân đi ra mỏ, trả lại true nếu ăn thành công
def find_and_take(limit_x, limit_y):
    global last_mine
    _x = -1
    _y = -1
    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

        _x, _y = locateCenterOnScreen("imgs/crystal_mine.png", screenshot_image, grayscale=True, confidence=0.8)
        logging.debug(f"Tim thay mo :{_x}, {_y}")

    except:
        # ignored
        return False


    if _x < 0:
        return False

    # thử lại lần 2 do bị trượt
    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

        _x, _y = locateCenterOnScreen("imgs/crystal_mine.png", screenshot_image, grayscale=True, confidence=0.80)
        logging.debug(f"Tim lan 2 thay mo :{_x}, {_y}")
    except:
        # ignored
        return False

    if _x < 0:
        return False

    if _x < limit_x and _y > limit_y:
        return False

    # Click
    device.input_tap(_x, _y)

    star_x = -1
    star_y = -1
    for i in range(10):
        sleep(0.2)
        try:
            imgx = device.screencap()
            screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)
            star_x, star_y = locateCenterOnScreen("imgs/star.png", screenshot_image, grayscale=True, confidence=0.75)
            logging.debug(f'Tìm thấy nút star:{star_x},{star_y}')
            break
        except:
            pass

    if star_x < 0:
        logging.debug("Không thấy start button, hoặc lỗi chụp")
        return False

    # screenshot lại id mỏ
    last_mine = None
    last_lvl = None

    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)
        last_mine = screenshot_image[star_x + 15:star_x + 50, star_y: star_y + 180]
        last_lvl = screenshot_image[star_x - 50:star_x, star_y - 70: star_y + 260]
    except:
        logging.debug("Không thấy start button, hoặc lỗi chụp")
    global traveled_mines
    global share_lv
    mine_level = 100
    try:
        try:
            image = last_mine
            image = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray = get_grayscale(image)
            thresh = thresholding(gray)
            str_coo = pytesseract.image_to_string(thresh,
                                                  config='-c tessedit_char_whitelist=:0123456789XY --psm 11 --oem 0')
            str_coo = re.sub(r"\s\s+", " ", str_coo.strip())
            str_coo = str_coo.upper()
            str_arr: list[str] = str_coo.split('Y')
            str_arr = list(map(lambda x: re.sub(r'[^0-9]', '', x), str_arr))
            str_coo = str_arr[0] + ':' + str_arr[1]

            if str_coo in traveled_mines:
                tmp_cap = device.screencap()
                tmp_screenshot = cv2.imdecode(np.frombuffer(tmp_cap, np.uint8), -1)
                _x, _y = locateCenterOnScreen("imgs/back.png", tmp_screenshot, grayscale=True, confidence=0.85)
                device.input_tap(_x, _y)
                logging.debug('press Back')
                return
            traveled_mines.append(str_coo)

            image = last_lvl
            image = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray = get_grayscale(image)
            thresh = thresholding(gray)
            str_level = pytesseract.image_to_string(thresh, config='--psm 11 --oem 0')
            str_level = re.sub(r'[^0-9]', '', str_level)
            mine_level = int(str_level)

            if mine_level > share_lv:
                last_mine_screenshot = screenshot_image[star_x - 70 :star_x + 680, star_y - 145:star_y + 320]
                thread = Thread(target=send_telebot,
                                args=(-751408051, str_coo + ":lv= " + str_level, 'imgs/last_mine_screenshot.png'))
                thread.start()
        except Exception as e:
            print(e)

        if is_full_queue or share_status or mine_level <= share_lv:
            _x, _y = locateCenterOnScreen("imgs/share.png", screenshot_image, grayscale=True, confidence=0.85)
            device.input_tap(_x, _y)
            logging.debug('press Share')

            for i in range(10):
                sleep(0.5)
                try:
                    imgx = device.screencap()
                    screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

                    _x, _y = locateCenterOnScreen("imgs/alliance.png", screenshot_image, grayscale=True,
                                                  confidence=0.85)
                    device.input_tap(_x, _y)
                    logging.debug('press Alliance')
                    break
                except:
                    None

            sleep(0.2)
            imgx = device.screencap()
            screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)
            _x, _y = locateCenterOnScreen("imgs/share_button.png", screenshot_image, grayscale=True, confidence=0.85)
            device.input_tap(_x, _y)
            logging.debug('press Share button')

        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)
        _x, _y = locateCenterOnScreen("imgs/back.png", screenshot_image, grayscale=True, confidence=0.85)
        device.input_tap(_x, _y)
        logging.debug('press Back')
    except:
        logging.debug("Không thể share")

    return True


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # find_and_take(50000, 50000)

    # device.input_swipe(724, 229, 724, 650, 120)
    # device.input_swipe(724, 600, 724, 630, 60)
    #
    # device.input_swipe(320, 600, 924, 600, 200)
    # device.input_swipe(924, 600, 944, 600, 60)

    imgx = device.screencap()
    screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

    star_x, star_y = locateCenterOnScreen("imgs/star.png", screenshot_image, grayscale=True, confidence=0.75)
    last_mine = screenshot_image[star_x - 70 :star_x + 680, star_y - 145:star_y + 320]
    cv2.imshow("Sheep", last_mine)
    cv2.waitKey(0)

    # img = cv2.imread("imgs/crystal_mine.jpg", cv2.IMREAD_ANYCOLOR)
    #
    # x, y = locateCenterOnScreen(img, screenshot_image, confidence=0.8, grayscale=True)
    # print(x,y)
    # device.input_tap(x,y)

    sys.exit()  # to exit from all the processes
    #
    # cv2.destroyAllWindows()  # destroy all windows

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
