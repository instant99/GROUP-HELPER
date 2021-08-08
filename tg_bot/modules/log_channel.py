from datetime import datetime
from functools import wraps

from tg_bot.modules.helper_funcs.misc import is_module_loaded

FILENAME = __name__.rsplit(".", 1)[-1]

if is_module_loaded(FILENAME):
    from telegram import Bot, Update, ParseMode
    from telegram.error import BadRequest, Unauthorized
    from telegram.ext import CommandHandler, run_async
    from telegram.utils.helpers import escape_markdown

    from tg_bot import dispatcher, LOGGER, GBAN_LOGS
    from tg_bot.modules.helper_funcs.chat_status import user_admin
    from tg_bot.modules.sql import log_channel_sql as sql


    def loggable(func):
        @wraps(func)
        def log_action(bot: Bot, update: Update, *args, **kwargs):

            result = func(bot, update, *args, **kwargs)
            chat = update.effective_chat
            message = update.effective_message

            if result:
                datetime_fmt = "%H:%M - %d-%m-%Y"
                result += f"\n<b>Event Stamp</b>: <code>{datetime.utcnow().strftime(datetime_fmt)}</code>"

                if message.chat.type == chat.SUPERGROUP and message.chat.username:
                    result += f'\n<b>Link:</b> <a href="https://t.me/{chat.username}/{message.message_id}">click here</a>'
                log_chat = sql.get_chat_log_channel(chat.id)
                if log_chat:
                    send_log(bot, log_chat, chat.id, result)
            elif result == "":
                pass
            else:
                LOGGER.warning("%s was set as loggable, but had no return statement.", func)

            return result

        return log_action


    def gloggable(func):
        @wraps(func)
        def glog_action(bot: Bot, update: Update, *args, **kwargs):

            result = func(bot, update, *args, **kwargs)
            chat = update.effective_chat
            message = update.effective_message

            if result:
                datetime_fmt = "%H:%M - %d-%m-%Y"
                result += "\n<b>Event Stamp</b>: <code>{}</code>".format(datetime.utcnow().strftime(datetime_fmt))

                if message.chat.type == chat.SUPERGROUP and message.chat.username:
                    result += f'\n<b>Link:</b> <a href="https://t.me/{chat.username}/{message.message_id}">click here</a>'
                log_chat = str(GBAN_LOGS)
                if log_chat:
                    send_log(bot, log_chat, chat.id, result)
            elif result == "":
                pass
            else:
                LOGGER.warning("%s was set as loggable to gbanlogs, but had no return statement.", func)

            return result

        return glog_action


    def send_log(bot: Bot, log_chat_id: str, orig_chat_id: str, result: str):

        try:
            bot.send_message(log_chat_id, result, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except BadRequest as excp:
            if excp.message == "Chat not found":
                bot.send_message(orig_chat_id, "This log channel has been deleted - unsetting.")
                sql.stop_chat_logging(orig_chat_id)
            else:
                LOGGER.warning(excp.message)
                LOGGER.warning(result)
                LOGGER.exception("Could not parse")

                bot.send_message(log_chat_id, result + "\n\nFormatting has been disabled due to an unexpected error.")


    @run_async
    @user_admin
    def logging(bot: Bot, update: Update):

        message = update.effective_message
        chat = update.effective_chat

        log_channel = sql.get_chat_log_channel(chat.id)
        if log_channel:
            log_channel_info = bot.get_chat(log_channel)
            message.reply_text(f"This group has all it's logs sent to:"
                               f" {escape_markdown(log_channel_info.title)} (`{log_channel}`)",
                               parse_mode=ParseMode.MARKDOWN)

        else:
            message.reply_text("No log channel has been set for this group!")


    @run_async
    @user_admin
    def setlog(bot: Bot, update: Update):

        message = update.effective_message
        chat = update.effective_chat
        if chat.type == chat.CHANNEL:
            message.reply_text("Теперь перешлите /setlog в группу, с которой вы хотите связать этот канал!")

        elif message.forward_from_chat:
            sql.set_chat_log_channel(chat.id, message.forward_from_chat.id)
            try:
                message.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    LOGGER.exception("Error deleting message in log channel. Should work anyway though.")

            try:
                bot.send_message(message.forward_from_chat.id,
                                 f"Этот канал был установлен как канал логов для {chat.title or chat.first_name}.")
            except Unauthorized as excp:
                if excp.message == "Forbidden: bot is not a member of the channel chat":
                    bot.send_message(chat.id, "Успешно установлен канал логов!")
                else:
                    LOGGER.exception("Ошибка настройки канала логов.")

            bot.send_message(chat.id, "Successfully set log channel!")

        else:
            message.reply_text("Настройка канала для логирования:\n"
                               " - Добавление бота в канал (Как админа!)\n"
                               " - Отправка `/setlog` в канал\n"
                               " - Пересылка отправленного сообщения `/setlog` в группе\n")


    @run_async
    @user_admin
    def unsetlog(bot: Bot, update: Update):

        message = update.effective_message
        chat = update.effective_chat

        log_channel = sql.stop_chat_logging(chat.id)
        if log_channel:
            bot.send_message(log_channel, f"Канал отключен от {chat.title}")
            message.reply_text("Канал с логами был отключен.")

        else:
            message.reply_text("Канал логов еще не установлен!")


    def __stats__():
        return f"{sql.num_logchannels()} log channels set."


    def __migrate__(old_chat_id, new_chat_id):
        sql.migrate_chat(old_chat_id, new_chat_id)


    def __chat_settings__(chat_id, user_id):
        log_channel = sql.get_chat_log_channel(chat_id)
        if log_channel:
            log_channel_info = dispatcher.bot.get_chat(log_channel)
            return f"This group has all it's logs sent to: {escape_markdown(log_channel_info.title)} (`{log_channel}`)"
        return "No log channel is set for this group!"


    __help__ = """
*Только админы:*
- /logchannel: Получить информацию о текущем лог канале
- /setlog: Установить канал для логирования.
- /unsetlog: Отключить канал для логирования.
Настройка канала для логирования::
- Добавление бота в канал (Как админа!)
- Отправка `/setlog` в канал
- Пересылка отправленного сообщения `/setlog` в группе
"""

    __mod_name__ = "LOG CHANNEL"

    LOG_HANDLER = CommandHandler("logchannel", logging)
    SET_LOG_HANDLER = CommandHandler("setlog", setlog)
    UNSET_LOG_HANDLER = CommandHandler("unsetlog", unsetlog)

    dispatcher.add_handler(LOG_HANDLER)
    dispatcher.add_handler(SET_LOG_HANDLER)
    dispatcher.add_handler(UNSET_LOG_HANDLER)

else:
    # run anyway if module not loaded
    def loggable(func):
        return func


    def gloggable(func):
        return func
