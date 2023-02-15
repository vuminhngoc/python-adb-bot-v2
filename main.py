# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import sys  # to access the system
from tempfile import TemporaryFile

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
share_lv = 0  # lvl mỏ mà cao hơn lvl này thì sẽ không share cho liên minh

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


def send_telebot(chatid, _str_coo, img):
    try:
        bot.sendMessage(chatid, _str_coo)
        cv2.imwrite("imgs/tmp.png", img)
        bot.sendPhoto(chatid, photo=open("imgs/tmp.png", 'rb'))


    except  Exception as e:
        print(e)


def start(update: Update, context: CallbackContext) -> None:
    """Bắt đầu"""
    update.message.reply_text(f'Hi! Use /set <seconds> to set a timer. Chatid = {update.message.chat_id}')


def full(update: Update, context: CallbackContext) -> None:
    """queue bị đầy, sẽ bị reset vào giờ tới"""
    global is_full_queue
    update.message.reply_text(f'Full queue status: {is_full_queue}')
    print(context.args)
    is_full_queue = not is_full_queue


def setlv(update: Update, context: CallbackContext) -> None:
    """set max lvl của mine được phép share cho liên minh"""
    global share_lv
    update.message.reply_text(f'Mine lv before=: {share_lv}')
    share_lv = int(context.args[0])


def swich(update: Update, context: CallbackContext) -> None:
    """thay đổi chế độ chạy"""
    global share_status
    share_status = not share_status
    update.message.reply_text(f'Chế độ share thay đổi thành:{share_status}')


# Tìm và điều quân đi ra mỏ, trả lại true nếu ăn thành công
def find_and_take(limit_x, limit_y):
    global last_mine
    _x = -1
    _y = -1
    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

        _x, _y = locateCenterOnScreen("imgs/crystal_mine.png", screenshot_image, grayscale=True, confidence=0.75)
        logging.debug(f"Tim thay mo :{_x}, {_y}, limit : {limit_x},{limit_y}")

    except:
        # ignored
        return False

    if _x < 0:
        return False

    # thử lại lần 2 do bị trượt
    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

        _x, _y = locateCenterOnScreen("imgs/crystal_mine.png", screenshot_image, grayscale=True, confidence=0.7)
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
        sleep(0.35)
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

    global traveled_mines
    global share_lv
    mine_level = 100
    try:
        try:
            last_mine = screenshot_image[star_y - 10:star_y + 5, star_x + 15:star_x + 100]
            last_lvl = screenshot_image[star_y - 45:star_y - 20, star_x - 25:star_x + 150]
            image = cv2.resize(last_mine, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray = get_grayscale(image)
            thresh = thresholding(gray)

            str_coo = pytesseract.image_to_string(thresh,
                                                  config='-c tessedit_char_whitelist=:0123456789XY --psm 11 --oem 0')
            str_coo = re.sub(r"\s\s+", " ", str_coo.strip())
            str_coo = str_coo.upper()
            str_arr: list[str] = str_coo.split('Y')
            str_arr = list(map(lambda x: re.sub(r'[^0-9]', '', x), str_arr))
            print(str_coo)
            str_coo = str_arr[0] + ':' + str_arr[1]

            if str_coo in traveled_mines:
                tmp_cap = device.screencap()
                tmp_screenshot = cv2.imdecode(np.frombuffer(tmp_cap, np.uint8), -1)
                _x, _y = locateCenterOnScreen("imgs/back.png", tmp_screenshot, grayscale=True, confidence=0.85)
                device.input_tap(_x, _y)
                logging.debug('press Back')
                sleep(2)
                return
            traveled_mines.append(str_coo)

            image = cv2.resize(last_lvl, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray = get_grayscale(image)
            thresh = thresholding(gray)
            str_level = pytesseract.image_to_string(thresh, config='--psm 11 --oem 0')
            str_level = re.sub(r'[^0-9]', '', str_level)
            mine_level = int(str_level)

            if mine_level > share_lv:
                last_mine_screenshot = screenshot_image[star_y - 55:star_y + 400, star_x - 60:star_x + 180]
                thread = Thread(target=send_telebot,
                                args=(-751408051, str_coo + ":lv= " + str_level, last_mine_screenshot))
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
        sleep(2)
    except:
        logging.debug("Không thể share")

    return True


def move_ziczac(x, y, w=4, h=10, find_lv=0):
    close_all()

    go_x = -1
    go_y = -1
    star_x = -1
    star_y = -1
    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

        star_x, star_y = locateCenterOnScreen("imgs/star_yellow.PNG", screenshot_image, grayscale=True, confidence=0.85)
        logging.debug(f"Yellow star: {star_x},{star_y}")
    except:
        logging.debug("Khong thay Yellow star")

    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

        go_x, go_y = locateCenterOnScreen("imgs/go.PNG", screenshot_image, grayscale=True, confidence=0.85)
    except:
        pass

    # Nếu không thấy nut go thì bấm vào tọa độ
    if go_x < 0:
        try:
            imgx = device.screencap()
            screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

            smal_x, smal_y = locateCenterOnScreen("imgs/earth.PNG", screenshot_image, grayscale=True, confidence=0.85)
            logging.debug(f"small earth: {smal_x}, {smal_y}")
            # todo: check
            device.input_tap(smal_x - 100, smal_y)

            sleep(0.25)

            imgx = device.screencap()
            screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

            go_x, go_y = locateCenterOnScreen("imgs/go.PNG", screenshot_image, grayscale=True, confidence=0.85)
            logging.debug(f"Go button: {go_x}, {go_y}")
        except:
            logging.debug("Khong thay erth")
    if go_x < 0:
        return False

    # jump đến tọa độ
    # device.input_tap(go_x - 400, go_y)
    device.input_text(str(x))
    device.input_tap(go_x - 400, go_y)

    device.input_tap(go_x - 120, go_y)
    device.input_text(str(y))
    device.input_tap(go_x - 120, go_y)

    sleep(0.2)
    device.input_tap(go_x, go_y)

    not_found_objects = True
    for index in range(10):
        sleep(0.15)
        try:
            imgx = device.screencap()
            screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

            lv_x, lv_y = locateCenterOnScreen("imgs/lv.PNG", screenshot_image, grayscale=True, confidence=0.75)
            not_found_objects = False
            break
        except:
            pass

    if not_found_objects:
        refresh()

    limit_x = star_x + 90
    limit_y = star_y - 10

    h_direction = 1
    global pause, start_minute
    # Tìm ngay khi vừa đến
    find_and_take(limit_x, limit_y)
    for index in range(w):
        # force done
        if force_done or (find_lv > 0 and datetime.utcnow().minute < start_minute):
            break

        for j in range(h):
            if force_done or (find_lv > 0 and datetime.utcnow().minute < start_minute):
                break

            if h_direction > 0:
                device.input_swipe(700, 100, 700, 400, 250)
                # device.input_swipe(724, 550, 724, 750, 60)
            else:
                device.input_swipe(700, 400, 700, 100, 250)
                # device.input_swipe(724, 230, 724, 229, 60)
            find_and_take(limit_x, limit_y)

        # dịch sang bên phải 1 bước
        device.input_swipe(950, 200, 200, 200, 250)
        # device.input_swipe(924, 600, 944, 600, 60)

        find_and_take(limit_x, limit_y)
        h_direction *= -1

    return True


def refresh():
    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

        kingdom_x, kingdom_y = locateCenterOnScreen("imgs/kingdom.PNG", screenshot_image, confidence=0.85)
        device.input_tap(kingdom_x, kingdom_y)
    except:
        logging.debug("Khong thay Kingdom")

    for i in range(20):
        sleep(0.5)
        try:
            imgx = device.screencap()
            screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

            kingdom_x, kingdom_y = locateCenterOnScreen("imgs/field.PNG", screenshot_image, confidence=0.85)
            device.input_tap(kingdom_x, kingdom_y)
            break
        except:
            logging.debug("Khong thay Kingdom")

    for i in range(20):
        sleep(0.5)
        try:
            imgx = device.screencap()
            screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

            kingdom_x, kingdom_y = locateCenterOnScreen("imgs/kingdom.PNG", screenshot_image, confidence=0.85)
            break
        except:
            logging.debug("Khong thay Kingdom")


def restart_game():
    pass


def close_all():
    """
    Đóng toàn bộ các mục đang được mở trên màn hình game
    """
    _x = _y = 1
    count = 0

    while _x > 0 and count < 10:
        count += 1
        _x = _y = -1
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)
        try:
            _x, _y = locateCenterOnScreen("imgs/back.png", screenshot_image, grayscale=True, confidence=0.85)
        except:
            pass
        try:
            _x, _y = locateCenterOnScreen("imgs/x.png", screenshot_image, grayscale=True, confidence=0.85)
        except:
            pass
        if _x > 0:
            device.input_tap(_x, _y)


# Press the green button in the gutter to run the script.
# ngang: 540
# doc 1500
# dpi: 240
if __name__ == '__main__':
    logging.debug("LOKA AI PLAYER STARTING...")
    traveled = ["0"]

    # # START TELEGRAM SERVICE
    # """Run bot."""
    # # Create the Updater and pass it your bot's token.
    # updater = Updater("5725931529:AAH6DDwcN_FlKEzDaccE7cTFYGFYcV8DpNM")
    #
    # # Get the dispatcher to register handlers
    # dispatcher = updater.dispatcher
    # dispatcher.add_handler(CommandHandler("start", start))
    # dispatcher.add_handler(CommandHandler("full", full))
    # dispatcher.add_handler(CommandHandler("sc", swich))
    # dispatcher.add_handler(CommandHandler("lv", setlv))
    #
    # updater.start_polling()

    # tìm tọa độ nút field
    field_x = -1
    field_y = -1
    try:
        imgx = device.screencap()
        screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

        field_x, field_y = locateCenterOnScreen("imgs/field.PNG", screenshot_image, confidence=0.85)
        logging.debug(f"field {field_x}, {field_y}")
    except:
        logging.debug("Khong thay Field")

    if field_x > 0:
        device.input_tap(field_x, field_y)
        for i in range(10):
            try:
                imgx = device.screencap()
                screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)

                kingdom_x, kingdom_y = locateCenterOnScreen("imgs/kingdom.PNG", screenshot_image, confidence=0.85)
                logging.debug(f"kingdom: {kingdom_x}, {kingdom_y}")
                break
            except:
                logging.debug("Khong thay Kingdom")

    l0_targets = [(974, 1025, 4, 9), (845, 1090, 4, 9)]
    l1_targets = [(870, 1373, 3, 6),
                  (871, 1633, 3, 6),
                  (1120, 1384, 3, 6),
                  (1120, 1637, 3, 6),
                  (673, 1031, 2, 2),
                  (987, 1812, 5, 2),
                  (1119, 1121, 3, 6)]
    l2_targets = [
        (1330, 1245, 2, 2),
        (970, 1120, 5, 46),
        (743, 1035, 2, 30),
        (614, 1123, 3, 6),
        (614, 1378, 3, 6),
        (614, 1628, 3, 6),
        (1377, 1123, 3, 6),
        (1377, 1378, 3, 6),
        (1377, 1628, 3, 6),
        (1630, 1123, 3, 6),
        (1630, 1378, 3, 6),
        (1630, 1628, 3, 6),
        (358, 1123, 3, 6),
        (358, 1378, 3, 6),
        (358, 1628, 3, 6),
    ]
    l3_targets = [
        (1245, 1334, 2, 5),
        (968, 1174, 1, 40),
        (1046, 1374, 1, 30),
        (704, 1024, 2, 40),
        (562, 1024, 1, 40),
        (481, 1024, 1, 50),
        (233, 1024, 1, 70),
        (1251, 1024, 1, 40),
        (1824, 1024, 6, 5),
        (1064, 1444, 6, 6),
        (213, 1035, 40, 3),
        (306, 1115, 1, 45),
        (989, 1236, 10, 15),
        (766, 1348, 10, 15),
        (238, 1727, 30, 10),
        (402, 1562, 35, 3),
        (10, 1987, 7, 5),
        (730, 1745, 35, 6),
        (195, 1282, 3, 5),
    ]

    h = -1
    time = datetime.utcnow()
    if time.minute > 6:
        done[0] = True
    if time.minute > 14:
        done[1] = True
    if time.minute > 24:
        done[2] = True

    treasure_checker = datetime(2022, 1, 1)

    while True:
        logging.debug(time)

        targetx = None
        delayx = 0.2
        lv = 3

        hour_time = datetime.utcnow()
        hour_time = hour_time.replace(minute=0, second=0, microsecond=0)

        if treasure_checker < hour_time:
            # change_treasure()
            logging.debug(f"Change treasure: before={treasure_checker}, after = {hour_time}")
            treasure_checker = hour_time
            traveled_mines = []
            is_full_queue = False
            restart_game()

        # trước phút thứ 5 thì lặp lại liên tục l0
        if datetime.utcnow().minute < start_minute:
            done = [False, False, False, False]
            force_done = False
            logging.debug(f"reset{datetime.utcnow().hour}")

        if not done[3]:
            targetx = l3_targets

        if not done[2]:
            targetx = l2_targets
            lv = 2
        if not done[1]:
            targetx = l1_targets
            lv = 1
        if not done[0]:
            targetx = l0_targets
            lv = 0
            delayx = 0.15

        if targetx is not None:
            random.shuffle(targetx)

        logging.debug(f"lv={lv}")
        if targetx is None:
            logging.debug("Hết đối tượng cần tìm. Bắt đầu sleep...")
            # tính thời gian sleep
            t = datetime.now() + timedelta(hours=1)
            future = datetime(t.year, t.month, t.day, t.hour)
            delta = round((future - datetime.now()).total_seconds()) + 1
            if delta >= 60 * 60:
                delta = 0
            logging.debug(f"Sleep time is {delta // 60}:{delta % 60}")
            sleep(delta)
            logging.debug("End sleep...")
            while pause:
                sleep(1)
            continue

        success = True
        for target in targetx:
            logging.debug(f"Target {targetx.index(target) + 1} / {len(targetx)} : {target}")
            # Thử tối đa là 3 lần  trên 1 target
            for t in range(3):
                t_success = move_ziczac(target[0], target[1], target[2], target[3], lv)
                if t_success:
                    break
                else:
                    restart_game()
            success = success and t_success
            # Check action reset
            if force_done or (lv > 0 and datetime.utcnow().minute < start_minute):
                break

        if success:
            done[lv] = True
    # device.input_text("500")
    # cv2.imshow("Sheep", last_mine)
    # cv2.waitKey(0)
    # imgx = device.screencap()
    # screenshot_image = cv2.imdecode(np.frombuffer(imgx, np.uint8), -1)
    # star_x, star_y = locateCenterOnScreen("imgs/star.png", screenshot_image, grayscale=True, confidence=0.75)
    # print(star_x, star_y)
    # # device.input_tap(star_x, star_y)
    # last_mine = screenshot_image[star_y - 55:star_y + 400, star_x - 60:star_x + 180]
    # cv2.imshow("Sheep", last_mine)
    # cv2.waitKey(0)
