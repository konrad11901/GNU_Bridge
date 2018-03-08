#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import subprocess
from configparser import SafeConfigParser

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from fbchat import Client
from fbchat.models import *

# OTHER STUFF

mutedFB = []
mutedTL = []
rawTL = []

def toggleRawTL(bot, update):
    if update.message.from_user.first_name and update.message.from_user.last_name and \
        update.message.from_user.last_name is not "ギルバイツ":
        user_name = update.message.from_user.first_name + " " + \
                update.message.from_user.last_name
    else:
        user_name = update.message.from_user.username

    if update.message.from_user.id in rawTL:
        rawTL.remove(update.message.from_user.id) 
        sendTextTL(user_name + " no longer sends raw messages.")
    else:
        rawTL.append(update.message.from_user.id) 
        sendTextTL(user_name + " now sends raw messages.")

def toggleMuteTL(bot, update):
    """Toggle mute state"""
    if update.message.from_user.first_name and update.message.from_user.last_name and \
        update.message.from_user.last_name is not "ギルバイツ":
        user_name = update.message.from_user.first_name + " " + \
                update.message.from_user.last_name
    else:
        user_name = update.message.from_user.username

    if update.message.from_user.id in mutedTL:
        mutedTL.remove(update.message.from_user.id) 
        sendTextTL(user_name + " is now unmuted.")
    else:
        mutedTL.append(update.message.from_user.id) 
        sendTextTL(user_name + " is now muted.")

def toggleMuteFB(user_id, user_name):
    """Toggle mute state"""
    if user_id in mutedFB:
        mutedFB.remove(user_id) 
        sendTextFB(user_name + " is now unmuted.")
    else:
        mutedFB.append(user_id) 
        sendTextFB(user_name + " is now muted.")

# Set logging level
# DEBUG for debug mode
# INFO for production mode
# SILENT for no stuff
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def prepareForJSON(text):
    return text.strip("'<>() ").replace("\'", "\"").replace("None", "\"None\"") \
        .replace("[]", "\"[]\"").replace("False", "\"False\"").replace("True", "\"True\"")

# FACEBOOK STUFF #

class FBClient(Client):
    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        if author_id == self.uid:
            logger.info("Read self sent message")
            return

        self.markAsDelivered(author_id, thread_id)
        self.markAsRead(author_id)
        self.markAsSeen()

        user = fbclient.fetchUserInfo(author_id)
        for uid in user:
            author_name = user[uid].name
        author_name = "*" + author_name + "*"

        if message_object.text == "/mute":
            logger.info("Toggling mute for %s", author_name)
            toggleMuteFB(author_id, author_name)
            return

        if message_object.attachments:
            processAtt(message_object, author_name)

        if not message_object.text:
            return

        if message_object.text[0] == '!' or author_id in mutedFB:
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
            sendTextTL(name + " sent photo:")
        except AttributeError as ae:
            sendVideoTL(att.preview_url)
            sendTextTL(name + " sent video:")
            pass
        except:
            logger.warning("Couldn't sent attachment")
            sentTextTL(name + " sent something but I can't see what it is")
            pass

def sendTextFB(body):
    """No magick here boi"""
    logger.info("Sending message to %s", thread_id)
    fbclient.send(Message(body), thread_id=thread_id, thread_type = thread_type)

def sendPhotoFB(url):
    fbclient.sendRemoteImage(url, message=Message(text=''), thread_id=thread_id, thread_type=thread_type)

# TELEGRAM STUFF #

def sendPhotoTL(url):
    updater.bot.sendPhoto(group_id, url)

def sendVideoTL(url):
    updater.bot.sendVideo(group_id, url)

def parseText(bot, update):
    """Parse text only message"""
    forward_body = ""

    if update.message.from_user.id in mutedTL or update.message.text[0] == '!':
        logger.info("Skipping silented message")
        return

    if update.message.reply_to_message:
        if update.message.reply_to_message.from_user.first_name is not None and update.message.reply_to_message.from_user.last_name is not None:
            forward_body = forward_body + "> " + \
                        update.message.reply_to_message.from_user.first_name + \
                        update.message.reply_to_message.from_user.last_name + ":\n"
        else:
            forward_body = "SaintGNU:\n"

        for line in update.message.reply_to_message.text.split('\n'):
            forward_body = forward_body + "> " + line + "\n"
    if update.message.from_user.id in rawTL: 
        forward_body = update.message.text
        rawTL.remove(update.message.from_user.id) 
    else:
        if update.message.from_user.first_name is not None and update.message.from_user.last_name is not None and \
            update.message.from_user.last_name is not "ギルバイツ":
            username = update.message.from_user.first_name + " " + \
                    update.message.from_user.last_name
        elif update.message.from_user.username is not None:
            username = update.message.from_user.username
        elif update.message.from_user.first_name is not None:
            username = update.message.from_user.first_name + " Noname"
        else:
            username = "Frajer bez imienia"
        forward_body = forward_body + username + ":\n" + update.message.text
    sendTextFB(forward_body)

def sendTextTL(body):
    """Send text from FB to telegram"""
    updater.bot.sendMessage(group_id, body, parse_mode='Markdown')

def parsePhotos(bot, update):
    """Parse photos"""

    if update.message.from_user.id in mutedTL:
        logger.info("Skipping silented message")
        return

    max_res = 0 
    photo_id = ""
    photo = json.loads(prepareForJSON(str(update.message)))

    # Send photo's owner credentials
    if update.message.from_user.first_name is not None and update.message.from_user.last_name is not None and \
        update.message.from_user.last_name is not "ギルバイツ":
        username = update.message.from_user.first_name + " " + \
                update.message.from_user.last_name
    elif update.message.from_user.username is not None:
        username = update.message.from_user.username
    elif update.message.from_user.first_name is not None:
        username = update.message.from_user.first_name + " Noname"
    else:
        username = "Frajer bez imienia"

    pre_body = username + " sent photo:"
    sendTextFB(pre_body) 

    # This is like the ugliest hack ever, but I'm not in a mood to fix it
    # It's like 3 AM
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
    """Parse videos from TL"""
    pre_body = update.message.from_user.first_name + " " + \
            update.message.from_user.last_name + " sent a video but I'm not able to show it to you yet! :("
    sendTextFB(pre_body) 

#    video_id = update.message.video.file_id
#    video_size = update.message.video.file_size

def error(bot, update, error):
        """Log errors and stuff"""
        logger.warning('[ERR]"%s" caused error "%s"', update, error)


# Read settings from config file
try:
    config = SafeConfigParser()
    config.read("config.ini")

    group_id = config.get("Telegram", "GroupID")
    updater = Updater(config.get("Telegram", "BotAPIKey"))

    thread_id = config.get("Facebook", "ChatID")
    thread_type = ThreadType.GROUP
    fbclient = FBClient(config.get("Facebook", "Email"), config.get("Facebook", "Passwd"))
except:
    logger.warning("Could not load configuration file")

if config.get("MOTD", "Start") is not "None":
    try:
        with open(config.get("MOTD", "Start"), "r") as startFile:
            msg = startFile.read()
            sendTextFB(msg)
            sendTextTL(msg)
    except:
        logger.warning("Could not read start message")
if config.get("MOTD", "Update") is not "None":
    try:
        with open(config.get("MOTD", "Update"), "r") as updateFile:
            msg = updateFile.read()
            if msg is not "":
                msg = "New updates: " + msg
                sendTextFB(msg)
                sendTextTL(msg)
    except:
        logger.warning("Could not read update message")

def sendPope(bot, update):
    sendTextFB("@dailypope")

def main():
    """Start the bot with async listening and
    add function to parse messages"""
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("mute", toggleMuteTL))
    # dp.add_handler(CommandHandler("raw", toggleRawTL))
    dp.add_handler(CommandHandler("pope", sendPope))

    dp.add_handler(MessageHandler(Filters.text, parseText))
    dp.add_handler(MessageHandler(Filters.photo , parsePhotos))
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
    main()
