import pyowm
from telegram import Message, Chat, Update, Bot
from telegram.ext import run_async

from tg_bot import dispatcher, updater, API_WEATHER
from tg_bot.modules.disable import DisableAbleCommandHandler

@run_async
def weather(bot, update, args):
    if len(args) == 0:
        update.effective_message.reply_text("Напишите место чтобы получить его погоду.")
        return

    location = " ".join(args)
    if location.lower() == bot.first_name.lower():
        update.effective_message.reply_text("Я буду следить за счастливыми и печальными временами!")
        bot.send_sticker(update.effective_chat.id, BAN_STICKER)
        return

    try:
        owm = pyowm.OWM(API_WEATHER)
        observation = owm.weather_at_place(location)
        getloc = observation.get_location()
        thelocation = getloc.get_name()
        if thelocation == None:
            thelocation = "Unknown"
        theweather = observation.get_weather()
        temperature = theweather.get_temperature(unit='celsius').get('temp')
        if temperature == None:
            temperature = "Unknown"

        # Weather symbols
        status = ""
        status_now = theweather.get_weather_code()
        if status_now < 232: # Rain storm
            status += "⛈️ "
        elif status_now < 321: # Drizzle
            status += "🌧️ "
        elif status_now < 504: # Light rain
            status += "🌦️ "
        elif status_now < 531: # Cloudy rain
             status += "⛈️ "
        elif status_now < 622: # Snow
            status += "🌨️ "
        elif status_now < 781: # Atmosphere
            status += "🌪️ "
        elif status_now < 800: # Bright
            status += "🌤️ "
        elif status_now < 801: # A little cloudy
             status += "⛅️ "
        elif status_now < 804: # Cloudy
             status += "☁️ "
        status += theweather._detailed_status
                        

        update.message.reply_text("Сегодня в {} is being {}, примерно {}°C.\n".format(thelocation,
                status, temperature))

    except pyowm.exceptions.not_found_error.NotFoundError:
        update.effective_message.reply_text("Простите, местоположение не найдено.")


__help__ = """
 - /weather <city>: get weather info in a particular place
"""

__mod_name__ = "WEATHER"

WEATHER_HANDLER = DisableAbleCommandHandler("weather", weather, pass_args=True)

dispatcher.add_handler(WEATHER_HANDLER)
