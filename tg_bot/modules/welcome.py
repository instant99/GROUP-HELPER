import html
import random
import re
import time
from typing import List
from functools import partial

from telegram import Update, Bot, CallbackQuery
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import MessageHandler, Filters, CommandHandler, run_async, CallbackQueryHandler, JobQueue
from telegram.utils.helpers import mention_markdown, mention_html, escape_markdown

import tg_bot.modules.sql.welcome_sql as sql
from tg_bot import dispatcher, OWNER_ID, DEV_USERS, SUDO_USERS, SUPPORT_USERS, TIGER_USERS, WHITELIST_USERS, LOGGER
from tg_bot.modules.helper_funcs.chat_status import user_admin, is_user_ban_protected
from tg_bot.modules.helper_funcs.misc import build_keyboard, revert_buttons
from tg_bot.modules.helper_funcs.msg_types import get_welcome_type
from tg_bot.modules.helper_funcs.string_handling import (markdown_parser,
                                                         escape_invalid_curly_brackets)
from tg_bot.modules.log_channel import loggable

VALID_WELCOME_FORMATTERS = ['first', 'last', 'fullname', 'username', 'id', 'count', 'chatname', 'mention']

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: dispatcher.bot.send_message,
    sql.Types.BUTTON_TEXT.value: dispatcher.bot.send_message,
    sql.Types.STICKER.value: dispatcher.bot.send_sticker,
    sql.Types.DOCUMENT.value: dispatcher.bot.send_document,
    sql.Types.PHOTO.value: dispatcher.bot.send_photo,
    sql.Types.AUDIO.value: dispatcher.bot.send_audio,
    sql.Types.VOICE.value: dispatcher.bot.send_voice,
    sql.Types.VIDEO.value: dispatcher.bot.send_video
}

VERIFIED_USER_WAITLIST = {}

# do not async
def send(update, message, keyboard, backup_message):
    try:
        msg = update.effective_message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except BadRequest as excp:
        if excp.message == "Button_url_invalid":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nNote: the current message has an invalid url "
                                                                      "in one of its buttons. Please update."),
                                                      parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Unsupported url protocol":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nNote: the current message has buttons which "
                                                                      "use url protocols that are unsupported by "
                                                                      "telegram. Please update."),
                                                      parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Wrong url host":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nNote: the current message has some bad urls. "
                                                                      "Please update."),
                                                      parse_mode=ParseMode.MARKDOWN)
            LOGGER.warning(message)
            LOGGER.warning(keyboard)
            LOGGER.exception("Could not parse! got invalid url host errors")
        else:
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nNote: An error occured when sending the "
                                                                      "custom message. Please update."),
                                                      parse_mode=ParseMode.MARKDOWN)
            LOGGER.exception()

    return msg


@run_async
@loggable
def new_member(bot: Bot, update: Update, job_queue: JobQueue):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    should_welc, cust_welcome, welc_type = sql.get_welc_pref(chat.id)
    welc_mutes = sql.welcome_mutes(chat.id)
    human_checks = sql.get_human_checks(user.id, chat.id)

    new_members = update.effective_message.new_chat_members

    for new_mem in new_members:

        welcome_log = None
        sent = None
        should_mute = True
        welcome_bool = True

        if should_welc:

            # Give the owner a special welcome
            if new_mem.id == OWNER_ID:
                update.effective_message.reply_text("YEAH LEGENDS  IS HERE")
                welcome_log = (f"{html.escape(chat.title)}\n"
                               f"#USER_JOINED\n"
                               f"Bot Owner just joined the chat")

            # Welcome Devs
            elif new_mem.id in DEV_USERS:
                update.effective_message.reply_text("YEAH I SEE PRO PLAYER IS HERE!")

            # Welcome Sudos
            elif new_mem.id in SUDO_USERS:
                update.effective_message.reply_text("Huh! A Powered just joined! Stay Alert!")

            # Welcome Support
            elif new_mem.id in SUPPORT_USERS:
                update.effective_message.reply_text("Hey! A support user joined!")

            # Welcome Whitelisted
            elif new_mem.id in TIGER_USERS:
                update.effective_message.reply_text("Oof! A Tiger disaster just joined!")

            # Welcome Tigers
            elif new_mem.id in WHITELIST_USERS:
                update.effective_message.reply_text("Oof! A Wolf disaster just joined!")

            # Welcome yourself
            elif new_mem.id == bot.id:
                update.effective_message.reply_text("hello 😎 thanks for using me make sure you promote me then i can safe your group for spammers 🥰🥰🥰")

            else:
                # If welcome message is media, send with appropriate function
                if welc_type not in (sql.Types.TEXT, sql.Types.BUTTON_TEXT):
                    ENUM_FUNC_MAP[welc_type](chat.id, cust_welcome)
                    continue

                # else, move on
                first_name = new_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.

                if cust_welcome:
                    if cust_welcome == sql.DEFAULT_WELCOME:
                        cust_welcome = random.choice(sql.DEFAULT_WELCOME_MESSAGES).format(first=escape_markdown(first_name))

                    if new_mem.last_name:
                        fullname = escape_markdown(f"{first_name} {new_mem.last_name}")
                    else:
                        fullname = escape_markdown(first_name)
                    count = chat.get_members_count()
                    mention = mention_markdown(new_mem.id, escape_markdown(first_name))
                    if new_mem.username:
                        username = "@" + escape_markdown(new_mem.username)
                    else:
                        username = mention

                    valid_format = escape_invalid_curly_brackets(cust_welcome, VALID_WELCOME_FORMATTERS)
                    res = valid_format.format(first=escape_markdown(first_name),
                                              last=escape_markdown(new_mem.last_name or first_name),
                                              fullname=escape_markdown(fullname), username=username, mention=mention,
                                              count=count, chatname=escape_markdown(chat.title), id=new_mem.id)
                    buttons = sql.get_welc_buttons(chat.id)
                    keyb = build_keyboard(buttons)

                else:
                    res = random.choice(sql.DEFAULT_WELCOME_MESSAGES).format(first=escape_markdown(first_name))
                    keyb = []

                backup_message = random.choice(sql.DEFAULT_WELCOME_MESSAGES).format(first=escape_markdown(first_name))
                keyboard = InlineKeyboardMarkup(keyb)

        else:
            welcome_bool = False
            res = None
            keyboard = None
            backup_message = None

        # User exceptions from welcomemutes
        if is_user_ban_protected(chat, new_mem.id, chat.get_member(new_mem.id)) or human_checks:
            should_mute = False
        # Join welcome: soft mute
        if new_mem.is_bot:
            should_mute = False

        if user.id == new_mem.id:
            if should_mute:
                if welc_mutes == "soft":
                    bot.restrict_chat_member(chat.id, new_mem.id,
                                             can_send_messages=True,
                                             can_send_media_messages=False,
                                             can_send_other_messages=False,
                                             can_add_web_page_previews=False,
                                             until_date=(int(time.time() + 24 * 60 * 60)))

                if welc_mutes == "strong":
                    welcome_bool = False
                    VERIFIED_USER_WAITLIST.update({
                        new_mem.id : {
                            "should_welc" : should_welc,
                            "status" : False,
                            "update" : update,
                            "res" : res,
                            "keyboard" : keyboard,
                            "backup_message" : backup_message
                        }
                    })
                    new_join_mem = f"[{escape_markdown(new_mem.first_name)}](tg://user?id={user.id})"
                    message = msg.reply_text(f"{new_join_mem}, click the button below to prove you're human.\nYou have 160 seconds.",
                                             reply_markup=InlineKeyboardMarkup([{InlineKeyboardButton(
                                                 text="Yes, I'm human.",
                                                 callback_data=f"user_join_({new_mem.id})")}]),
                                             parse_mode=ParseMode.MARKDOWN)
                    bot.restrict_chat_member(chat.id, new_mem.id,
                                             can_send_messages=False,
                                             can_send_media_messages=False,
                                             can_send_other_messages=False,
                                             can_add_web_page_previews=False)

                    job_queue.run_once(
                        partial(
                            check_not_bot, new_mem, chat.id, message.message_id
                        ), 160, name="welcomemute"
                    )

        if welcome_bool:
            sent = send(update, res, keyboard, backup_message)

            prev_welc = sql.get_clean_pref(chat.id)
            if prev_welc:
                try:
                    bot.delete_message(chat.id, prev_welc)
                except BadRequest:
                    pass

                if sent:
                    sql.set_clean_welcome(chat.id, sent.message_id)

        if welcome_log:
            return welcome_log

        return (f"{html.escape(chat.title)}\n"
                f"#USER_JOINED\n"
                f"<b>User</b>: {mention_html(user.id, user.first_name)}\n"
                f"<b>ID</b>: <code>{user.id}</code>")

    return ""


def check_not_bot(member, chat_id, message_id, bot, job):

    member_dict = VERIFIED_USER_WAITLIST.pop(member.id)
    member_status = member_dict.get("status")
    if not member_status:
        try:
            bot.unban_chat_member(chat_id, member.id)
        except:
            pass

        try:
            bot.edit_message_text("*kicks user*\nThey can always rejoin and try.", chat_id=chat_id, message_id=message_id)
        except:
            pass


@run_async
def left_member(bot: Bot, update: Update):
    chat = update.effective_chat
    user = update.effective_user
    should_goodbye, cust_goodbye, goodbye_type = sql.get_gdbye_pref(chat.id)

    if user.id == bot.id:
        return

    if should_goodbye:
        left_mem = update.effective_message.left_chat_member
        if left_mem:
            # Ignore bot being kicked
            if left_mem.id == bot.id:
                return

            # Give the owner a special goodbye
            if left_mem.id == OWNER_ID:
                update.effective_message.reply_text("ooo sed legend is gone")
                return

            # Give the devs a special goodbye
            elif left_mem.id in DEV_USERS:
                update.effective_message.reply_text("See you later at the Hero's Association!")
                return

            # if media goodbye, use appropriate function for it
            if goodbye_type != sql.Types.TEXT and goodbye_type != sql.Types.BUTTON_TEXT:
                ENUM_FUNC_MAP[goodbye_type](chat.id, cust_goodbye)
                return

            first_name = left_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.
            if cust_goodbye:
                if cust_goodbye == sql.DEFAULT_GOODBYE:
                    cust_goodbye = random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(first=escape_markdown(first_name))
                if left_mem.last_name:
                    fullname = escape_markdown(f"{first_name} {left_mem.last_name}")
                else:
                    fullname = escape_markdown(first_name)
                count = chat.get_members_count()
                mention = mention_markdown(left_mem.id, first_name)
                if left_mem.username:
                    username = "@" + escape_markdown(left_mem.username)
                else:
                    username = mention

                valid_format = escape_invalid_curly_brackets(cust_goodbye, VALID_WELCOME_FORMATTERS)
                res = valid_format.format(first=escape_markdown(first_name),
                                          last=escape_markdown(left_mem.last_name or first_name),
                                          fullname=escape_markdown(fullname), username=username, mention=mention,
                                          count=count, chatname=escape_markdown(chat.title), id=left_mem.id)
                buttons = sql.get_gdbye_buttons(chat.id)
                keyb = build_keyboard(buttons)

            else:
                res = random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(first=first_name)
                keyb = []

            keyboard = InlineKeyboardMarkup(keyb)

            send(update, res, keyboard, random.choice(sql.DEFAULT_GOODBYE_MESSAGES).format(first=first_name))


@run_async
@user_admin
def welcome(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat
    # if no args, show current replies.
    if not args or args[0].lower() == "noformat":
        noformat = True
        pref, welcome_m, welcome_type = sql.get_welc_pref(chat.id)
        update.effective_message.reply_text(f"This chat has it's welcome setting set to: `{pref}`.\n"
                                            f"*The welcome message (not filling the {{}}) is:*",
                                            parse_mode=ParseMode.MARKDOWN)

        if welcome_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_welc_buttons(chat.id)
            if noformat:
                welcome_m += revert_buttons(buttons)
                update.effective_message.reply_text(welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, welcome_m, keyboard, sql.DEFAULT_WELCOME)

        else:
            if noformat:
                ENUM_FUNC_MAP[welcome_type](chat.id, welcome_m)

            else:
                ENUM_FUNC_MAP[welcome_type](chat.id, welcome_m, parse_mode=ParseMode.MARKDOWN)

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_welc_preference(str(chat.id), True)
            update.effective_message.reply_text("Okay! I'll greet members when they join.")

        elif args[0].lower() in ("off", "no"):
            sql.set_welc_preference(str(chat.id), False)
            update.effective_message.reply_text("I'll go loaf around and not welcome anyone then.")

        else:
            update.effective_message.reply_text("I understand 'on/yes' or 'off/no' only!")


@run_async
@user_admin
def goodbye(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat

    if not args or args[0] == "noformat":
        noformat = True
        pref, goodbye_m, goodbye_type = sql.get_gdbye_pref(chat.id)
        update.effective_message.reply_text(f"This chat has it's goodbye setting set to: `{pref}`.\n"
                                            f"*The goodbye  message (not filling the {{}}) is:*",
                                            parse_mode=ParseMode.MARKDOWN)

        if goodbye_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_gdbye_buttons(chat.id)
            if noformat:
                goodbye_m += revert_buttons(buttons)
                update.effective_message.reply_text(goodbye_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, goodbye_m, keyboard, sql.DEFAULT_GOODBYE)

        else:
            if noformat:
                ENUM_FUNC_MAP[goodbye_type](chat.id, goodbye_m)

            else:
                ENUM_FUNC_MAP[goodbye_type](chat.id, goodbye_m, parse_mode=ParseMode.MARKDOWN)

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_gdbye_preference(str(chat.id), True)
            update.effective_message.reply_text("Ok!")

        elif args[0].lower() in ("off", "no"):
            sql.set_gdbye_preference(str(chat.id), False)
            update.effective_message.reply_text("Ok!")

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text("I understand 'on/yes' or 'off/no' only!")


@run_async
@user_admin
@loggable
def set_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("You didn't specify what to reply with!")
        return ""

    sql.set_custom_welcome(chat.id, content or text, data_type, buttons)
    msg.reply_text("Successfully set custom welcome message!")

    return (f"<b>{html.escape(chat.title)}:</b>\n"
            f"#SET_WELCOME\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Set the welcome message.")


@run_async
@user_admin
@loggable
def reset_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat
    user = update.effective_user

    sql.set_custom_welcome(chat.id, sql.DEFAULT_WELCOME, sql.Types.TEXT)
    update.effective_message.reply_text("Successfully reset welcome message to default!")

    return (f"<b>{html.escape(chat.title)}:</b>\n"
            f"#RESET_WELCOME\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Reset the welcome message to default.")


@run_async
@user_admin
@loggable
def set_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message
    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("You didn't specify what to reply with!")
        return ""

    sql.set_custom_gdbye(chat.id, content or text, data_type, buttons)
    msg.reply_text("Successfully set custom goodbye message!")
    return (f"<b>{html.escape(chat.title)}:</b>\n"
            f"#SET_GOODBYE\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Set the goodbye message.")


@run_async
@user_admin
@loggable
def reset_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat
    user = update.effective_user

    sql.set_custom_gdbye(chat.id, sql.DEFAULT_GOODBYE, sql.Types.TEXT)
    update.effective_message.reply_text("Successfully reset goodbye message to default!")

    return (f"<b>{html.escape(chat.title)}:</b>\n"
            f"#RESET_GOODBYE\n"
            f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
            f"Reset the goodbye message.")


@run_async
@user_admin
@loggable
def welcomemute(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if len(args) >= 1:
        if args[0].lower() in ("off", "no"):
            sql.set_welcome_mutes(chat.id, False)
            msg.reply_text("I will no longer mute people on joining!")
            return (f"<b>{html.escape(chat.title)}:</b>\n"
                    f"#WELCOME_MUTE\n"
                    f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                    f"Has toggled welcome mute to <b>OFF</b>.")
        elif args[0].lower() in ["soft"]:
            sql.set_welcome_mutes(chat.id, "soft")
            msg.reply_text("I will restrict users' permission to send media for 24 hours.")
            return (f"<b>{html.escape(chat.title)}:</b>\n"
                    f"#WELCOME_MUTE\n"
                    f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                    f"Has toggled welcome mute to <b>SOFT</b>.")
        elif args[0].lower() in ["strong"]:
            sql.set_welcome_mutes(chat.id, "strong")
            msg.reply_text("I will now mute people when they join until they prove they're not a bot.\nThey will have 160seconds before they get kicked.")
            return (f"<b>{html.escape(chat.title)}:</b>\n"
                    f"#WELCOME_MUTE\n"
                    f"<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n"
                    f"Has toggled welcome mute to <b>STRONG</b>.")
        else:
            msg.reply_text("Please enter `off`/`no`/`soft`/`strong`!", parse_mode=ParseMode.MARKDOWN)
            return ""
    else:
        curr_setting = sql.welcome_mutes(chat.id)
        reply = (f"\n Give me a setting!\nChoose one out of: `off`/`no` or `soft` or `strong` only! \n"
                 f"Current setting: `{curr_setting}`")
        msg.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
        return ""


@run_async
@user_admin
@loggable
def clean_welcome(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat
    user = update.effective_user

    if not args:
        clean_pref = sql.get_clean_pref(chat.id)
        if clean_pref:
            update.effective_message.reply_text("I should be deleting welcome messages up to two days old.")
        else:
            update.effective_message.reply_text("I'm currently not deleting old welcome messages!")
        return ""

    if args[0].lower() in ("on", "yes"):
        sql.set_clean_welcome(str(chat.id), True)
        update.effective_message.reply_text("I'll try to delete old welcome messages!")
        return (f"<b>{html.escape(chat.title)}:</b>\n"
                f"#CLEAN_WELCOME\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has toggled clean welcomes to <code>ON</code>.")
    elif args[0].lower() in ("off", "no"):
        sql.set_clean_welcome(str(chat.id), False)
        update.effective_message.reply_text("I won't delete old welcome messages.")
        return (f"<b>{html.escape(chat.title)}:</b>\n"
                f"#CLEAN_WELCOME\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Has toggled clean welcomes to <code>OFF</code>.")
    else:
        update.effective_message.reply_text("I understand 'on/yes' or 'off/no' only!")
        return ""


@run_async
def user_button(bot: Bot, update: Update):
    chat = update.effective_chat
    user = update.effective_user
    query = update.callback_query
    match = re.match(r"user_join_\((.+?)\)", query.data)
    message = update.effective_message
    join_user = int(match.group(1))

    if join_user == user.id:
        member_dict = VERIFIED_USER_WAITLIST.pop(user.id)
        member_dict["status"] = True
        VERIFIED_USER_WAITLIST.update({user.id: member_dict})
        query.answer(text="Yeet! You're a human, unmuted!")
        bot.restrict_chat_member(chat.id, user.id, can_send_messages=True,
                                 can_send_media_messages=True,
                                 can_send_other_messages=True,
                                 can_add_web_page_previews=True)
        bot.deleteMessage(chat.id, message.message_id)
        if member_dict["should_welc"]:
            sent = send(member_dict["update"], member_dict["res"], member_dict["keyboard"], member_dict["backup_message"])

            prev_welc = sql.get_clean_pref(chat.id)
            if prev_welc:
                try:
                    bot.delete_message(chat.id, prev_welc)
                except BadRequest:
                    pass

                if sent:
                    sql.set_clean_welcome(chat.id, sent.message_id)

    else:
        query.answer(text="You're not allowed to do this!")


WELC_HELP_TXT = ("Your group's welcome/goodbye messages can be personalised in multiple ways. If you want the messages"
                 " to be individually generated, like the default welcome message is, you can use *these* variables:\n"
                 " - `{{first}}`: Имя пользователя\n"
                 " - `{{last}}`: Фамилия пользователя. Если нет фамилии, будет использовано имя "
                 "last name.\n"
                 " - `{{fullname}}`: Полное имя пользователя. Если нет полного имени, будет использовано имя.\n"
                 " - `{{username}}`: Ник пользователя. Если нет полного имени, будет использовано упоминание.\n"
                 " - `{{mention}}`:  Просто упоминае пользователя с именем.\n"
                 " - `{{id}}`: ID пользователя\n"
                 " - `{{count}}`: Счетчик пользователей в группе.\n"
                 " - `{{chatname}}`: Имя группы.\n"
                 "\nКаждая переменная ДОЛЖНА быть окружена `{{}}` to be для замены.\n"
                 "Сообщения Приветсвия и Прощания также поддерживают markdown, поэтому вы можете создавать любые элементы.."
                 "Кнопки также поддерживаются, поэтому вы можете сделать свои приветствия великолепными с помощью некоторых кнопок с надписью.\n"
                 f"Чтобы создать кнопку, ссылающуюся на ваши правила, используйте это: `[Rules](buttonurl://t.me/{dispatcher.bot.username}?start=group_id)`."
                 "Просто замените `group_id` ID вашей группы, который можно получить через /id ."
                 "Обратите внимание, что ID группы обычно предшествует знак `-` он необходим, поэтому, пожалуйста,"
                 "не удаляйте его.\n"
                 "Вы можете даже установить изображения/гифки/видио/голосовые сообщения в качестве приветственного сообщения "
                 "ответе на нужный элемент и напишите /setwelcome.")

WELC_MUTE_HELP_TXT = (
    "You can get the bot to mute new people who join your group and hence prevent spambots from flooding your group. "
    "The following options are possible:\n"
    "- `/welcomemute soft`: restricts new members from sending media for 24 hours.\n"
    "- `/welcomemute strong`: mutes new members till they tap on a button thereby verifying they're human.\n"
    "- `/welcomemute off`: turns off welcomemute.\n"
    "`Note:` Strong mode kicks a user from the chat if they dont verify in 160seconds. They can always rejoin though"
                     )

@run_async
@user_admin
def welcome_help(bot: Bot, update: Update):
    update.effective_message.reply_text(WELC_HELP_TXT, parse_mode=ParseMode.MARKDOWN)


@run_async
@user_admin
def welcome_mute_help(bot: Bot, update: Update):
    update.effective_message.reply_text(WELC_MUTE_HELP_TXT, parse_mode=ParseMode.MARKDOWN)


# TODO: get welcome data from group butler snap
# def __import_data__(chat_id, data):
#     welcome = data.get('info', {}).get('rules')
#     welcome = welcome.replace('$username', '{username}')
#     welcome = welcome.replace('$name', '{fullname}')
#     welcome = welcome.replace('$id', '{id}')
#     welcome = welcome.replace('$title', '{chatname}')
#     welcome = welcome.replace('$surname', '{lastname}')
#     welcome = welcome.replace('$rules', '{rules}')
#     sql.set_custom_welcome(chat_id, welcome, sql.Types.TEXT)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    welcome_pref, _, _ = sql.get_welc_pref(chat_id)
    goodbye_pref, _, _ = sql.get_gdbye_pref(chat_id)
    return "This chat has it's welcome preference set to `{}`.\n" \
           "It's goodbye preference is `{}`.".format(welcome_pref, goodbye_pref)


__help__ = """
{}

*Admin only:*
 - /welcome <on/off>: Включить/Выключить приветсвенные сообщения.
 - /welcome: Показать текущий статус приветсвенных сообщений.
 - /welcome noformat: Показывает текущие настройки приветствия, без форматирования - полезно при изменении вашого приветственного сообщения!
 - /goodbye -> такое же использование как и /welcome.
 - /setwelcome <sometext>: Установка пользовательского приветственного сообщение.
 - /setgoodbye <sometext>: Установка пользовательского сообщение прощания.
 - /resetwelcome: Вернуть приветственное сообщение по умолчанию.
 - /resetgoodbye: Вернуть прощальное сообщение по умолчанию.
 - /cleanwelcome <on/off>: Удаление преведущего приветственного сообщение после отправки нового, что бы избежать спама в группе.
 - /welcomemutehelp: Предоставляет информацию о приветственных отключениях.
 - /welcomehelp: просмотр дополнительной информации о форматировании пользовательских приветственных/прощальных сообщений.
""".format(WELC_HELP_TXT)

NEW_MEM_HANDLER = MessageHandler(Filters.status_update.new_chat_members, new_member, pass_job_queue=True)
LEFT_MEM_HANDLER = MessageHandler(Filters.status_update.left_chat_member, left_member)
WELC_PREF_HANDLER = CommandHandler("welcome", welcome, pass_args=True, filters=Filters.group)
GOODBYE_PREF_HANDLER = CommandHandler("goodbye", goodbye, pass_args=True, filters=Filters.group)
SET_WELCOME = CommandHandler("setwelcome", set_welcome, filters=Filters.group)
SET_GOODBYE = CommandHandler("setgoodbye", set_goodbye, filters=Filters.group)
RESET_WELCOME = CommandHandler("resetwelcome", reset_welcome, filters=Filters.group)
RESET_GOODBYE = CommandHandler("resetgoodbye", reset_goodbye, filters=Filters.group)
WELCOMEMUTE_HANDLER = CommandHandler("welcomemute", welcomemute, pass_args=True, filters=Filters.group)
CLEAN_WELCOME = CommandHandler("cleanwelcome", clean_welcome, pass_args=True, filters=Filters.group)
WELCOME_HELP = CommandHandler("welcomehelp", welcome_help)
WELCOME_MUTE_HELP = CommandHandler("welcomemutehelp", welcome_mute_help)
BUTTON_VERIFY_HANDLER = CallbackQueryHandler(user_button, pattern=r"user_join_")

dispatcher.add_handler(NEW_MEM_HANDLER)
dispatcher.add_handler(LEFT_MEM_HANDLER)
dispatcher.add_handler(WELC_PREF_HANDLER)
dispatcher.add_handler(GOODBYE_PREF_HANDLER)
dispatcher.add_handler(SET_WELCOME)
dispatcher.add_handler(SET_GOODBYE)
dispatcher.add_handler(RESET_WELCOME)
dispatcher.add_handler(RESET_GOODBYE)
dispatcher.add_handler(CLEAN_WELCOME)
dispatcher.add_handler(WELCOME_HELP)
dispatcher.add_handler(WELCOMEMUTE_HANDLER)
dispatcher.add_handler(BUTTON_VERIFY_HANDLER)
dispatcher.add_handler(WELCOME_MUTE_HELP)

__mod_name__ = "GREETINGS"
__command_list__ = ["welcome", "goodbye", "setwelcome", "setgoodbye", "resetwelcome", "resetgoodbye",
                    "welcomemute", "cleanwelcome", "welcomehelp", "welcomemutehelp"]
__handlers__ = [NEW_MEM_HANDLER, LEFT_MEM_HANDLER, WELC_PREF_HANDLER, GOODBYE_PREF_HANDLER,
                SET_WELCOME, SET_GOODBYE, RESET_WELCOME, RESET_GOODBYE, CLEAN_WELCOME,
                WELCOME_HELP, WELCOMEMUTE_HANDLER, BUTTON_VERIFY_HANDLER, WELCOME_MUTE_HELP]
