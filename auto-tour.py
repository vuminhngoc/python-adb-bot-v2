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
bot = telepot.Bot('5893551902:AAGF7r8xRJC442d2KhArNF6oMSy0ZeEJfJo')
start_minute = 5

pause = False
last_mine = None
force_done = False
traveled_mines = []
is_full_queue = False
share_status = False
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

    except ex:
        print(ex)


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

        _x, _y = locateCenterOnScreen("imgs/crystal_mine.png", screenshot_image, grayscale=True, confidence=0.7)
        logging.debug(f"Tim thay mo :{_x}, {_y}, limit : {limit_x},{limit_y}")

    except:
        # ignored
        return False

    if _x < 0:
        return False

    thread = Thread(target=send_telebot,
                    args=(1706064050, "C36 screenshot", screenshot_image))
    thread.start()


def move_ziczac(x, y, w=4, h=10, find_lv=0):
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
        device.input_swipe(950, 600, 200, 600, 250)
        # device.input_swipe(924, 600, 944, 600, 60)

        find_and_take(limit_x, limit_y)
        h_direction *= -1

    return True


def refresh():
    pass


def restart_game():
    pass


# Press the green button in the gutter to run the script.
# ngang: 540
# doc 1500
# dpi: 240
if __name__ == '__main__':
    logging.debug("LOKA AI PLAYER STARTING...")
    traveled = ["0"]

    # START TELEGRAM SERVICE
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater("5893551902:AAGF7r8xRJC442d2KhArNF6oMSy0ZeEJfJo")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("full", full))
    dispatcher.add_handler(CommandHandler("sc", swich))
    dispatcher.add_handler(CommandHandler("lv", setlv))

    updater.start_polling()

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

    l0_targets = [(1008, 1129, 2, 40)]  # dọc phía trên congress
    l1_targets = [(1128, 1359, 4, 10),  # B3
                  (871, 1373, 4, 10),  # B2
                  (1381, 1118, 3, 8),  # B6
                  (1395, 1624, 3, 8),  # C5
                  (979, 1246, 12, 16),  # Vùng rộng phía trên A2
                  (826, 1242, 10, 28)]  # Vùng rộng phía trên A1

    l2_targets = [
        (836, 1032, 1, 35),  # vùng dọc giữa B và A
        (466, 1041, 1, 50),  # vùng dọc giữa C và B
        (1250, 1025, 1, 20),  # vùng dọc bên cạnh shrine A2
        (220, 1031, 1, 40),  # vùng dọc bên ngoài trái C
        (713, 1817, 8, 0),  # vùng ngang trên cùng bản đồ
        (1634, 1118, 3, 6),  # C10
        (1639, 1378, 3, 6),  # C8
        (1386, 1380, 3, 6),  # B4
        (1335, 1240, 2, 2),  # vùng nhỏ bên cạnh B4 dưới
        (1614, 1382, 4, 4),  # vùng nhỏ bên cạnh B4 trên
        (1345, 1037, 9, 2),  # vùng ngang bản đồ bên phải
        (595, 1027, 6, 1),  # vùng ngang bản đồ bên trái
        (1827, 1032, 5, 16),  # vuùng góc phải bản đồ
    ]

    l3_targets = [
        (359, 1120, 3, 5),  # C9
        (359, 1380, 3, 5),  # C7
        (359, 1635, 3, 5),  # C1
        (612, 1635, 3, 5),  # C2
    ]

    h = -1
    time = datetime.utcnow()
    if time.minute > 6:
        done[0] = True
    if time.minute > 35:
        done[1] = True
    if time.minute > 50:
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
