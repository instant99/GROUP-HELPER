import html
from typing import List

from telegram import Bot, Update, ParseMode
from telegram.error import BadRequest
from telegram.ext import Filters, run_async
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, LOGGER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import user_admin, can_delete
from tg_bot.modules.log_channel import loggable


@run_async
@user_admin
@loggable
def purge(bot: Bot, update: Update, args: List[str]) -> str:
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if can_delete(chat, bot.id):

        if msg.reply_to_message:

            message_id = msg.reply_to_message.message_id
            start_message_id = message_id - 1
            delete_to = msg.message_id - 1

            if args and args[0].isdigit():
                new_del = message_id + int(args[0])
                # No point deleting messages which haven't been written yet.
                if new_del < delete_to:
                    delete_to = new_del
        else:

            if args and args[0].isdigit():
                messages_to_delete = int(args[0])

            if messages_to_delete < 1:
                msg.reply_text("Can't purge less than 1 message.")
                return ""

            delete_to = msg.message_id - 1
            start_message_id = delete_to - messages_to_delete

        for m_id in range(delete_to, start_message_id, -1):  # Reverse iteration over message ids

            try:
                bot.deleteMessage(chat.id, m_id)
            except BadRequest as err:
                if err.message == "Message can't be deleted":
                    bot.send_message(chat.id, "Cannot delete all messages. The messages may be too old, I might "
                                              "not have delete rights, or this might not be a supergroup.")

                elif err.message != "Message to delete not found":
                    LOGGER.exception("Error while purging chat messages.")

        try:
            msg.delete()
        except BadRequest as err:
            if err.message == "Message can't be deleted":
                bot.send_message(chat.id, "Не удается удалить все сообщения. Сообщения могут быть слишком старыми, или у меня "
                                          "может не быть прав на удаление, или это может быть не супергруппа.")

            elif err.message != "Message to delete not found":
                LOGGER.exception("Error while purging chat messages.")

        bot.send_message(chat.id, f"Purge <code>{delete_to - start_message_id}</code> messages.",
                         parse_mode=ParseMode.HTML)
        return (f"<b>{html.escape(chat.title)}:</b>\n"
                f"#PURGE\n"
                f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                f"Purged <code>{delete_to - start_message_id}</code> messages.")

    return ""


@run_async
@user_admin
@loggable
def del_message(bot: Bot, update: Update) -> str:
    if update.effective_message.reply_to_message:
        user = update.effective_user
        chat = update.effective_chat
        if can_delete(chat, bot.id):
            update.effective_message.reply_to_message.delete()
            update.effective_message.delete()
            return (f"<b>{html.escape(chat.title)}:</b>\n"
                    f"#DEL\n"
                    f"<b>Admin:</b> {mention_html(user.id, user.first_name)}\n"
                    f"Message deleted.")
    else:
        update.effective_message.reply_text("Что я должен удалить?")

    return ""


__help__ = """
*Только админы:*
 - /del: Удалить сообщение на которое вы ответили.
 - /purge: Удаляет все сообщения между этим и сообщением на которое вы ответили.
 - /purge <integer X>: Удаляет сообщение на которое вы ответили и последующие X-сообщенияe.
 - /purge <integer X>: Удаляет количество сообщений, начинающихся снизу. (Также подсчитывает количество удаляемых сообщений)
"""

DELETE_HANDLER = DisableAbleCommandHandler("del", del_message, filters=Filters.group)
PURGE_HANDLER = DisableAbleCommandHandler("purge", purge, filters=Filters.group, pass_args=True)

dispatcher.add_handler(DELETE_HANDLER)
dispatcher.add_handler(PURGE_HANDLER)

__mod_name__ = "PURGE & DEL"
__command_list__ = ["del", "purge"]
__handlers__ = [DELETE_HANDLER, PURGE_HANDLER]
