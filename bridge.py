#!/usr/bin/python3

# -*- coding: utf-8 -*-

import json
import logging
import subprocess
import sys
from configparser import SafeConfigParser

from telegram.ext import Updater, MessageHandler, Filters
from fbchat import Client
from fbchat.models import *


# Set logging level: DEBUG, INFO, SILENT
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def prepareForJSON(text):
    return text.strip("'<>() ").replace("\'", "\"").replace("None", "\"None\"") \
        .replace("[]", "\"[]\"").replace("False", "\"False\"").replace("True", "\"True\"")


# ================================================== #
# ======= FACEBOOK STUFF =========================== #
# ================================================== #

class FBClient(Client):
    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        if author_id == self.uid:
            logger.info("Read self sent message")
            return

        self.markAsDelivered(author_id, thread_id)
        self.markAsRead(author_id)
        self.markAsSeen()

        if thread_id != our_thread_id:
            logger.info("Got a message from different group. Skipping.");
            return

        user = fbclient.fetchUserInfo(author_id)
        for uid in user:
            author_name = user[uid].name
        author_name = "*" + author_name + "*"

        if message_object.attachments:
            processAtt(message_object, author_name)

        if not message_object.text:
            return
        elif message_object.text[0] == '!':
            logger.info("Skipping silented message")
            return

        forward_text = author_name + ":\n" + message_object.text
        sendTextTL(forward_text)

        logger.info("{} from {} in {}".format(message_object, thread_id, thread_type.name))

def processAtt(msg, name):
    """Process image and send it to telegram"""
    for attachment in msg.attachments:
        att = attachment
        try:
            sendPhotoTL(att.large_preview_url)
            sendTextTL(name + " sent photo...")
        except AttributeError as ae:
            sendVideoTL(att.preview_url)
            sendTextTL(name + " sent video...")
            pass
        except:
            logger.warning("Couldn't sent attachment")
            sentTextTL(name + " sent something but I can't see what it is :(")
            pass

def sendTextFB(body):
    logger.info("Sending message to FB: %s", our_thread_id)
    fbclient.send(Message(body), thread_id=our_thread_id, thread_type=thread_type)

def sendPhotoFB(url):
    logger.info("Sending photo to FB: %s", our_thread_id)
    fbclient.sendRemoteImage(url, message=Message(text=''), thread_id=our_thread_id, thread_type=thread_type)


# ================================================== #
# ======= TELEGRAM STUFF =========================== #
# ================================================== #

def sendPhotoTL(url):
    updater.bot.sendPhoto(group_id, url)

def sendVideoTL(url):
    updater.bot.sendVideo(group_id, url)

def sendTextTL(body):
    updater.bot.sendMessage(group_id, body, parse_mode='Markdown')

def parseText(bot, update):
    """Parse text only message"""

    if update.message.text[0] == '!':
        logger.info("Skipping silented message")
        return

    forward_body = update.message.from_user.first_name
    if update.message.from_user.last_name is not None:
        forward_body += " " + update.message.from_user.last_name
    forward_body += ":\n"

    if update.message.reply_to_message:
        forward_body += ">>" + update.message.reply_to_message.from_user.first_name
        if update.message.reply_to_message.from_user.last_name is not None:
            forward_body += " " + update.message.reply_to_message.from_user.last_name
        for line in update.message.reply_to_message.text.split('\n'):
            forward_body += "\n>" + line

    forward_body += "\n" + update.message.text
    sendTextFB(forward_body)


def parsePhotos(bot, update):
    """Parse photos"""

    max_res = 0 
    photo_id = ""
    photo = json.loads(prepareForJSON(str(update.message)))

    # Send photo's owner credentials
    caption_body = update.message.from_user.first_name
    if update.message.from_user.last_name is not None:
        caption_body += " " + update.message.from_user.last_name
    caption_body += " sent photo..."
    sendTextFB(caption_body) 

    # This is like the ugliest hack ever, but I'm not in a mood to fix it
    # It's like 3 AM
        # Oh shit, I ain't touching that either. Someone pls fix.
    # TODO: FIX THIS SOMETIME
    for info in photo:
        if info == "photo":
            for meta in photo[info]:
                if meta["width"] > max_res:
                    max_res = meta["width"]
                    photo_id = meta["file_id"]

    logger.info("Sending photo %s size %s", photo_id, max_res)
    sendPhotoFB(bot.getFile(photo_id).file_path)
    logger.info("Done...")


def parseVideos(bot, update):
    """Parse videos from TG"""
    #no1cares
    pre_body = update.message.from_user.first_name + " " + \
            update.message.from_user.last_name + " sent a video but I'm not able to show it to you :("
    sendTextFB(pre_body)

#    video_id = update.message.video.file_id
#    video_size = update.message.video.file_size


def error(bot, update, error):
        """Log errors and stuff"""
        logger.warning('[ERR]"%s" caused error "%s"', update, error)


# =================================================== #
# ======= BRIDGE STUFF ============================== #
# =================================================== #

def main():
    """Start the bot with async listening and
    add function to parse messages"""

    if config.get("MOTD", "Start") is not "None":
        try:
            with open(config.get("MOTD", "Start"), "r") as startFile:
                msg = startFile.read()
                sendTextFB(msg)
                sendTextTL(msg)
        except:
            logger.warning("Could not read start message")

    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text,  parseText))
    dp.add_handler(MessageHandler(Filters.photo, parsePhotos))
    dp.add_handler(MessageHandler(Filters.video, parseVideos))
    dp.add_error_handler(error)
    updater.start_polling()
    #updater.idle()

    fbclient.listen()

    if config.get("MOTD", "Stop") is not "None":
        try:
            with open(config.get("MOTD", "Stop"), "r") as stopFile:
                msg = stopFile.read()
                sendTextFB(msg)
                sendTextTL(msg)
        except:
            logger.warning("Could not read stop message")


if __name__ == '__main__':
    config = SafeConfigParser()
    try:
        config.read("config.ini")
    except:
        logger.warning("No config file!")
        sys.exit()
    try:
        #telegram
        group_id = config.get("Telegram", "GroupID")
        updater = Updater(config.get("Telegram", "BotAPIKey"))
        logger.info("Telegram set. OK")

        #facebook
        our_thread_id = config.get("Facebook", "ChatID")
        thread_type = ThreadType.GROUP
        fbclient = FBClient(config.get("Facebook", "Email"), config.get("Facebook", "Passwd"))
        logger.info("Facebook set. OK")
    except:
        logger.warning("configuration invalid")
        sys.exit()
    main()
