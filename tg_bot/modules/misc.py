import html
import re
import json
from typing import List

import requests
from requests import get
from bs4 import BeautifulSoup
from telegram import Bot, Update, MessageEntity, ParseMode
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async, Filters
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, OWNER_ID, SUDO_USERS, SUPPORT_USERS, DEV_USERS, TIGER_USERS, WHITELIST_USERS
from tg_bot.__main__ import STATS, USER_INFO, TOKEN
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import user_admin, sudo_plus, bot_admin, can_restrict
from tg_bot.modules.helper_funcs.extraction import extract_user
from tg_bot.modules.sql.safemode_sql import set_safemode, is_safemoded
import tg_bot.modules.sql.users_sql as sql


MARKDOWN_HELP = f"""
Markdown - очень мощный инструмент для форматирования текста, который поддерживает  Telegram. {dispatcher.bot.first_name} имеет некоторые улучшения, чтобы убедиться, что \
сохраненные сообщения правильно написаны , что позволяет создавать кнопки.

- <code>_italic_</code>: выделение с двух сторон текста с помощью '_' приведет к созданию курсивного текста.
- <code>*bold*</code>: выделение с двух сторон текста с помощью '*' приведет к получению жирного текста.
- <code>`code`</code>: выделение с двух сторон текста с помощью '`' приведет к получению моноширинного текста, также известного как 'код',
- <code>[ваш_текст](ваша_ссылка)</code>:  это создаст ссылку - сообщение просто покажет <code> ваш_текст </code>, \
и нажатие на него откроет страницу в <code>ваша_ссылка</code>.
Пример: <code>[test](ваша_ссылка)</code>

- <code>[Текст кнопки](buttonurl:ваша ссылка)</code>: это специальное расширение, позволяющее пользователям создавать кнопки-ссылки. <code> Текст Кнопки </code> будет отображаться на кнопке, а <code>ваша ссылка</code> \
будет открывать ваш URL-адрес.
Пример: <code>[Это кнопка](buttonurl:это_ссылка)</code>

Если вам нужно несколько кнопок в одной строке, используйте это:
<code>[one](buttonurl://ваша_ссылка)
[two](buttonurl://google.com:same)</code>
Это создаст две кнопки в одной строке, а не одну кнопку на строку.
"""


@run_async
def get_id(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message
    chat = update.effective_chat
    msg = update.effective_message
    user_id = extract_user(msg, args)

    if user_id:

        if msg.reply_to_message and msg.reply_to_message.forward_from:

            user1 = message.reply_to_message.from_user
            user2 = message.reply_to_message.forward_from

            msg.reply_text(f"Отправитель, {html.escape(user2.first_name)},"
                           f" имеет ID <code>{user2.id}</code>.\n"
                           f"Пересылающий, {html.escape(user1.first_name)},"
                           f" имеет ID <code>{user1.id}</code>.",
                           parse_mode=ParseMode.HTML)

        else:

            user = bot.get_chat(user_id)
            msg.reply_text(f"{html.escape(user.first_name)}'s id is <code>{user.id}</code>.",
                           parse_mode=ParseMode.HTML)

    else:

        if chat.type == "private":
            msg.reply_text(f"Ваш ID - <code>{chat.id}</code>.",
                           parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(f"ID этой группы - <code>{chat.id}</code>.",
                           parse_mode=ParseMode.HTML)


@run_async
def gifid(bot: Bot, update: Update):
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.animation:
        update.effective_message.reply_text(f"Gif ID:\n<code>{msg.reply_to_message.animation.file_id}</code>",
                                            parse_mode=ParseMode.HTML)
    else:
        update.effective_message.reply_text("Please reply to a gif to get its ID.")


@run_async
def info(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message
    chat = update.effective_chat
    user_id = extract_user(update.effective_message, args)

    if user_id:
        user = bot.get_chat(user_id)

    elif not message.reply_to_message and not args:
        user = message.from_user

    elif not message.reply_to_message and (not args or (
            len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not message.parse_entities(
        [MessageEntity.TEXT_MENTION]))):
        message.reply_text("Я не могу извлечь ID этого пользователя")
        return

    else:
        return

    text = (f"<b>Информация о пользователе:</b>\n"
            f"🆔️ID: <code>{user.id}</code>\n"
            f"👤Имя: {html.escape(user.first_name)}")

    if user.last_name:
        text += f"\n👤Фамилия: {html.escape(user.last_name)}"

    if user.username:
        text += f"\n👤Ник: @{html.escape(user.username)}"

    text += f"\n👤Постоянная ссылка на пользователя: {mention_html(user.id, 'link')}"

    num_chats = sql.get_user_num_chats(user.id)
    text += f"\n🌍Chat count: <code>{num_chats}</code>"

    try:
        user_member = chat.get_member(user.id)
        if user_member.status == 'administrator':
            result = requests.post(f"https://api.telegram.org/bot{TOKEN}/getChatMember?chat_id={chat.id}&user_id={user.id}")
            result = result.json()["result"]
            if "custom_title" in result.keys():
                custom_title = result['custom_title']
                text += f"\nThis user holds the title <b>{custom_title}</b> here."
    except BadRequest:
        pass

    disaster_level_present = False

    if user.id == OWNER_ID:
        text += "\n😎The Disaster level of this person is 'LEGEND'."
        disaster_level_present = True
    elif user.id in DEV_USERS:
        text += "\n🔥This member is one of 'Hero Association'."
        disaster_level_present = True
    elif user.id in SUDO_USERS:
        text += "\n🔥The Disaster level of this person is 'Dragon'."
        disaster_level_present = True
    elif user.id in SUPPORT_USERS:
        text += "\n🔥The Disaster level of this person is 'HACKER'."
        disaster_level_present = True
    elif user.id in TIGER_USERS:
        text += "\n🔥The Disaster level of this person is 'Tiger'."
        disaster_level_present = True
    elif user.id in WHITELIST_USERS:
        text += "\n🔥The Disaster level of this person is 'Wolf'."
        disaster_level_present = True

    if disaster_level_present:
        text += ' [<a href="http://t.me/{}?start=disasters">?</a>]'.format(bot.username)

    text += "\n"
    for mod in USER_INFO:
        if mod.__mod_name__ == "Users":
            continue

        try:
            mod_info = mod.__user_info__(user.id)
        except TypeError:
            mod_info = mod.__user_info__(user.id, chat.id)
        if mod_info:
            text += "\n" + mod_info

    update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@run_async
@user_admin
def echo(bot: Bot, update: Update):
    args = update.effective_message.text.split(None, 1)
    message = update.effective_message

    if message.reply_to_message:
        message.reply_to_message.reply_text(args[1])
    else:
        message.reply_text(args[1], quote=False)

    message.delete()


@run_async
def markdown_help(bot: Bot, update: Update):
    update.effective_message.reply_text(MARKDOWN_HELP, parse_mode=ParseMode.HTML)
    update.effective_message.reply_text("Попробуйте переслать мне следующее сообщение, и вы увидите!")
    update.effective_message.reply_text("/save test Это тест markdown. _italics_, *bold*, `code`, "
                                        "[URL](example.com) [button](buttonurl:github.com) "
                                        "[button2](buttonurl://google.com:same)")


@run_async
@sudo_plus
def stats(bot: Bot, update: Update):
    stats = "Current stats:\n" + "\n".join([mod.__stats__() for mod in STATS])
    result = re.sub(r'(\d+)', r'<code>\1</code>', stats)
    update.effective_message.reply_text(result, parse_mode=ParseMode.HTML)


@bot_admin
@can_restrict
@user_admin
def safe_mode(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat
    message = update.effective_message
    if not args:
        message.reply_text("This chat has its Safe Mode set to *{}*".format(is_safemoded(chat.id).safemode_status), parse_mode=ParseMode.MARKDOWN)
        return

    if str(args[0]).lower() in ["on", "yes"]:
        set_safemode(chat.id, True)
        message.reply_text("Safe Mode has been set to *{}*".format(is_safemoded(chat.id).safemode_status), parse_mode=ParseMode.MARKDOWN)
        return

    elif str(args[0]).lower() in ["off", "no"]:
        set_safemode(chat.id, False)
        message.reply_text("Safe Mode has been set to *{}*".format(is_safemoded(chat.id).safemode_status), parse_mode=ParseMode.MARKDOWN)
        return
    else:
        message.reply_text("I only recognize the arguments `{}`, `{}`, `{}` or `{}`".format("Yes", "No", "On", "Off"), parse_mode=ParseMode.MARKDOWN)

@run_async
def magisk(bot, update):
    url = 'https://raw.githubusercontent.com/topjohnwu/magisk_files/'
    releases = ""
    for type, branch in {"Stable":["master/stable","master"], "Beta":["master/beta","master"], "Canary (release)":["canary/release","canary"], "Canary (debug)":["canary/debug","canary"]}.items():
        data = get(url + branch[0] + '.json').json()
        releases += f'*{type}*: \n' \
                    f'• [Changelog](https://github.com/topjohnwu/magisk_files/blob/{branch[1]}/notes.md)\n' \
                    f'• Zip - [{data["magisk"]["version"]}-{data["magisk"]["versionCode"]}]({data["magisk"]["link"]}) \n' \
                    f'• App - [{data["app"]["version"]}-{data["app"]["versionCode"]}]({data["app"]["link"]}) \n' \
                    f'• Uninstaller - [{data["magisk"]["version"]}-{data["magisk"]["versionCode"]}]({data["uninstaller"]["link"]})\n\n'
                        

    del_msg = update.message.reply_text("*Latest Magisk Releases:*\n{}".format(releases),
                               parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    time.sleep(300)
    try:
        del_msg.delete()
        update.effective_message.delete()
    except BadRequest as err:
        if (err.message == "Message to delete not found" ) or (err.message == "Message can't be deleted" ):
            return

@run_async
def checkfw(bot, update, args):
    if not len(args) == 2:
        reply = f'Give me something to fetch, like:\n`/checkfw SM-N975F DBT`'
        del_msg = update.effective_message.reply_text("{}".format(reply),
                               parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        time.sleep(5)
        try:
            del_msg.delete()
            update.effective_message.delete()
        except BadRequest as err:
            if (err.message == "Message to delete not found" ) or (err.message == "Message can't be deleted" ):
                return
    temp,csc = args
    model = f'sm-'+temp if not temp.upper().startswith('SM-') else temp
    fota = get(f'http://fota-cloud-dn.ospserver.net/firmware/{csc.upper()}/{model.upper()}/version.xml')
    test = get(f'http://fota-cloud-dn.ospserver.net/firmware/{csc.upper()}/{model.upper()}/version.test.xml')
    if test.status_code != 200:
        reply = f"Couldn't check for {temp.upper()} and {csc.upper()}, please refine your search or try again later!"
        del_msg = update.effective_message.reply_text("{}".format(reply),
                               parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        time.sleep(5)
        try:
            del_msg.delete()
            update.effective_message.delete()
        except BadRequest as err:
            if (err.message == "Message to delete not found" ) or (err.message == "Message can't be deleted" ):
                return
    page1 = BeautifulSoup(fota.content, 'lxml')
    page2 = BeautifulSoup(test.content, 'lxml')
    os1 = page1.find("latest").get("o")
    os2 = page2.find("latest").get("o")
    if page1.find("latest").text.strip():
        pda1,csc1,phone1=page1.find("latest").text.strip().split('/')
        reply = f'*Latest released firmware for {model.upper()} and {csc.upper()} is:*\n'
        reply += f'• PDA: `{pda1}`\n• CSC: `{csc1}`\n'
        if phone1:
            reply += f'• Phone: `{phone1}`\n'
        if os1:
            reply += f'• Android: `{os1}`\n'
        reply += f'\n'
    else:
        reply = f'*No public release found for {model.upper()} and {csc.upper()}.*\n\n'
    reply += f'*Latest test firmware for {model.upper()} and {csc.upper()} is:*\n'
    if len(page2.find("latest").text.strip().split('/')) == 3:
        pda2,csc2,phone2=page2.find("latest").text.strip().split('/')
        reply += f'• PDA: `{pda2}`\n• CSC: `{csc2}`\n'
        if phone2:
            reply += f'• Phone: `{phone2}`\n'
        if os2:
            reply += f'• Android: `{os2}`\n'
        reply += f'\n'
    else:
        md5=page2.find("latest").text.strip()
        reply += f'• Hash: `{md5}`\n• Android: `{os2}`\n\n'
    
    update.message.reply_text("{}".format(reply),
                           parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

@run_async
def getfw(bot, update, args):
    if not len(args) == 2:
        reply = f'Give me something to fetch, like:\n`/getfw SM-N975F DBT`'
        del_msg = update.effective_message.reply_text("{}".format(reply),
                               parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        time.sleep(5)
        try:
            del_msg.delete()
            update.effective_message.delete()
        except BadRequest as err:
            if (err.message == "Message to delete not found" ) or (err.message == "Message can't be deleted" ):
                return
    temp,csc = args
    model = f'sm-'+temp if not temp.upper().startswith('SM-') else temp
    test = get(f'http://fota-cloud-dn.ospserver.net/firmware/{csc.upper()}/{model.upper()}/version.test.xml')
    if test.status_code != 200:
        reply = f"Couldn't find any firmware downloads for {temp.upper()} and {csc.upper()}, please refine your search or try again later!"
        del_msg = update.effective_message.reply_text("{}".format(reply),
                               parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        time.sleep(5)
        try:
            del_msg.delete()
            update.effective_message.delete()
        except BadRequest as err:
            if (err.message == "Message to delete not found" ) or (err.message == "Message can't be deleted" ):
                return
    url1 = f'https://samfrew.com/model/{model.upper()}/region/{csc.upper()}/'
    url2 = f'https://www.sammobile.com/samsung/firmware/{model.upper()}/{csc.upper()}/'
    url3 = f'https://sfirmware.com/samsung-{model.lower()}/#tab=firmwares'
    url4 = f'https://samfw.com/firmware/{model.upper()}/{csc.upper()}/'
    fota = get(f'http://fota-cloud-dn.ospserver.net/firmware/{csc.upper()}/{model.upper()}/version.xml')
    page = BeautifulSoup(fota.content, 'lxml')
    os = page.find("latest").get("o")
    reply = ""
    if page.find("latest").text.strip():
        pda,csc2,phone=page.find("latest").text.strip().split('/')
        reply += f'*Latest firmware for {model.upper()} and {csc.upper()} is:*\n'
        reply += f'• PDA: `{pda}`\n• CSC: `{csc2}`\n'
        if phone:
            reply += f'• Phone: `{phone}`\n'
        if os:
            reply += f'• Android: `{os}`\n'
    reply += f'\n'
    reply += f'*Downloads for {model.upper()} and {csc.upper()}*\n'
    reply += f'• [samfrew.com]({url1})\n'
    reply += f'• [sammobile.com]({url2})\n'
    reply += f'• [sfirmware.com]({url3})\n'
    reply += f'• [samfw.com]({url4})\n'
    update.message.reply_text("{}".format(reply),
                           parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

@run_async
def twrp(bot, update, args):
    if len(args) == 0:
        reply='No codename provided, write a codename for fetching informations.'
        del_msg = update.effective_message.reply_text("{}".format(reply),
                               parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        time.sleep(5)
        try:
            del_msg.delete()
            update.effective_message.delete()
        except BadRequest as err:
            if (err.message == "Message to delete not found" ) or (err.message == "Message can't be deleted" ):
                return

    device = " ".join(args)
    url = get(f'https://eu.dl.twrp.me/{device}/')
    if url.status_code == 404:
        reply = f"Couldn't find twrp downloads for {device}!\n"
        del_msg = update.effective_message.reply_text("{}".format(reply),
                               parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        time.sleep(5)
        try:
            del_msg.delete()
            update.effective_message.delete()
        except BadRequest as err:
            if (err.message == "Message to delete not found" ) or (err.message == "Message can't be deleted" ):
                return
    else:
        reply = f'*Latest Official TWRP for {device}*\n'            
        db = get(DEVICES_DATA).json()
        newdevice = device.strip('lte') if device.startswith('beyond') else device
        try:
            brand = db[newdevice][0]['brand']
            name = db[newdevice][0]['name']
            reply += f'*{brand} - {name}*\n'
        except KeyError as err:
            pass
        page = BeautifulSoup(url.content, 'lxml')
        date = page.find("em").text.strip()
        reply += f'*Updated:* {date}\n'
        trs = page.find('table').find_all('tr')
        row = 2 if trs[0].find('a').text.endswith('tar') else 1
        for i in range(row):
            download = trs[i].find('a')
            dl_link = f"https://eu.dl.twrp.me{download['href']}"
            dl_file = download.text
            size = trs[i].find("span", {"class": "filesize"}).text
            reply += f'[{dl_file}]({dl_link}) - {size}\n'

        update.message.reply_text("{}".format(reply),
                               parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)



__help__ = """
 - /id: получить ID группы. Если ответить коммандой на сообщение - выдаст ID пользователя.

 - /gifid: ответьте мне на gif, чтобы сообщить вам идентификатор файла..

 - /info: Получить информацию о пользователе.

 - /markdownhelp: Краткое изложение того, как работает markdown в Telegram, - можно вызывать только в личке.

 - /safemode <on/off/yes/no>: Запрещает новым пользователям отправлять материалы в течение 24 часов после присоединения к группе.
    Используйте включение, чтобы ограничить их.

 - /magisk - Получит последнюю версию магиска для Stable/Beta/Canary.

 - /twrp <codename> -  получает последнюю версию twrp для устройства Android, используя кодовое имя.

 - /checkfw <model> <csc> - Только для Samsung - показывает последнюю информацию о прошивке для данного устройства, полученную с серверов samsung

 - /getfw <model> <csc> - Только Samsung - получает ссылки на загрузку прошивки от samfrew, sammobile и sfirmwares для данного устройства

 - /imdb <movie or TV series name>: Просмотр результатов IMDb для выбранного фильма или сериала
"""

ID_HANDLER = DisableAbleCommandHandler("id", get_id, pass_args=True)
GIFID_HANDLER = DisableAbleCommandHandler("gifid", gifid)
INFO_HANDLER = DisableAbleCommandHandler("info", info, pass_args=True)
ECHO_HANDLER = DisableAbleCommandHandler("echo", echo, filters=Filters.group)
MD_HELP_HANDLER = CommandHandler("markdownhelp", markdown_help, filters=Filters.private)
STATS_HANDLER = CommandHandler("stats", stats)
MAGISK_HANDLER = DisableAbleCommandHandler("magisk", magisk)
TWRP_HANDLER = DisableAbleCommandHandler("twrp", twrp, pass_args=True)
GETFW_HANDLER = DisableAbleCommandHandler("getfw", getfw, pass_args=True)
CHECKFW_HANDLER = DisableAbleCommandHandler("checkfw", checkfw, pass_args=True)

SAFEMODE_HANDLER = CommandHandler("safemode", safe_mode, pass_args=True)

dispatcher.add_handler(ID_HANDLER)
dispatcher.add_handler(GIFID_HANDLER)
dispatcher.add_handler(INFO_HANDLER)
dispatcher.add_handler(ECHO_HANDLER)
dispatcher.add_handler(MD_HELP_HANDLER)
dispatcher.add_handler(STATS_HANDLER)
dispatcher.add_handler(SAFEMODE_HANDLER)
dispatcher.add_handler(MAGISK_HANDLER)
dispatcher.add_handler(TWRP_HANDLER)
dispatcher.add_handler(GETFW_HANDLER)
dispatcher.add_handler(CHECKFW_HANDLER)


__mod_name__ = "MASTER MOD"
__command_list__ = ["id", "info", "echo"]
__handlers__ = [ID_HANDLER, GIFID_HANDLER, INFO_HANDLER, ECHO_HANDLER, MD_HELP_HANDLER, STATS_HANDLER, SAFEMODE_HANDLER, MAGISK_HANDLER, TWRP_HANDLER, GETFW_HANDLER, CHECKFW_HANDLER]
