from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.callback_data import CallbackData
import requests

import config


bot = Bot(token=config.token_Bot)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

#Текстовые значения для отображение команд для пользователя 
text_start_location = 'start location'
text_finish_location = 'finish location'
text_info = 'info'
text_help = 'help'
warring_text = '\n\nПредупреждение: Указана примерная стоимость поездки по выбранному маршруту. Цена может отличаться в связи со спросом и наличием свободных такси'


#States
class Form(StatesGroup):
    zero_state = State()
    start_location = State()  
    finish_location = State()

#Functions
async def get_info(state):
    try:
        async with state.proxy() as data:
            return 'Точка отправления: '+data['start_location']['adress']+'\nТочка прибытия: '+data['finish_location']['adress']
    except:
        await message.reply('Данные не введены')

async def get_adresses(message, button_label):

    link_geocoder='https://geocode-maps.yandex.ru/1.x/?apikey='+config.api_yandex_geocoder+'&geocode='+message.text+'&format=json'
    try:
        geocoder_respond = requests.get(link_geocoder).json()
        inline_kb = types.InlineKeyboardMarkup()
        dict_of_locations = {}
        counter = 1
        for i in geocoder_respond.get('response').get('GeoObjectCollection').get('featureMember'):
            current_adress_list = i.get('GeoObject').get('metaDataProperty').get('GeocoderMetaData').get('text').split()[1:] #убираем страну
            current_adress = ''
            for j in current_adress_list:
                current_adress = current_adress + j + ' '
            current_point = i.get('GeoObject').get('Point').get('pos')
            current_callback_data = button_label + str(counter)
            dict_of_locations[current_callback_data] = {'adress': current_adress, 'point': current_point}
            inline_btn = types.InlineKeyboardButton(current_adress, callback_data=current_callback_data)
            inline_kb.add(inline_btn)
            counter = counter + 1
    except:
        await message.answer('Что-то пошло не так, попробуйте еще раз')
        await message.answer('Введите адрес подробнее')
    return dict_of_locations, inline_kb

async def get_price_yandex(state, start_lon, start_lat, finish_lon, finish_lat):

    start_lon_lat = start_lon+', '+start_lat
    finish_lon_lat = finish_lon+', '+finish_lat
    web_yandex_taxi = 'https://taxi-routeinfo.taxi.yandex.net/taxi_info?clid=' + config.yandex_taxi_clid + '&apikey=' + config.api_yandex_taxi +'&rll=' + start_lon_lat + '~' + finish_lon_lat
    yandex_respond = requests.get(web_yandex_taxi).json()
    return yandex_respond['options'][0]['price']

async def get_lon_lat(state):
    async with state.proxy() as data:
        start_list = data['start_location']['point'].split()
        finish_list = data['finish_location']['point'].split()
    return start_list[0], start_list[1], finish_list[0], finish_list[1]

#Handlers
@dp.message_handler(commands=['start'], state='*')
async def start_cmd(message: types.Message):
    await Form.zero_state.set()
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    buttons = [text_start_location, text_finish_location]
    keyboard.add(*buttons)
    buttons = [text_info, text_help]
    keyboard.add(*buttons)
    
    await message.reply('Привет!\nИнструкция по всем командам', reply_markup = keyboard)

@dp.message_handler(lambda message: message.text == text_help, state='*')
async def help_cmd(message: types.Message):
    await message.reply('Инструкция')

@dp.message_handler(lambda message: message.text == text_info, state='*')
async def info_cmd(message: types.Message, state: FSMContext):
    await message.answer(await get_info(state))

@dp.message_handler(lambda message: message.text == text_start_location, state='*')
async def start_location_cmd(message: types.Message):
    await Form.start_location.set()
    await message.answer('Введите адрес отправления')

@dp.message_handler(lambda message: message.text == text_finish_location, state='*')
async def finish_location_cmd(message: types.Message):
    await Form.finish_location.set()
    await message.answer('Введите адрес прибытия')

@dp.message_handler(state=Form.start_location)
async def process_start_location(message: types.Message, state: FSMContext):
    
    dict_of_start_locations, inline_kb = await get_adresses(message, 'start_button')
    
    async with state.proxy() as data:
        data['dict_of_start_locations'] = dict_of_start_locations
    await message.answer('Выберите адрес из предложенных', reply_markup=inline_kb)
            
@dp.message_handler(state=Form.finish_location)
async def process_finish_location(message: types.Message, state: FSMContext):

    dict_of_finish_locations, inline_kb = await get_adresses(message, 'finish_button')
    
    async with state.proxy() as data:
        data['dict_of_finish_locations'] = dict_of_finish_locations
    await message.answer('Выберите адрес из предложенных', reply_markup=inline_kb)

@dp.callback_query_handler(lambda x: 'start_button' in x.data, state=Form.start_location)
async def process_callback_start_button(callback_query: types.CallbackQuery, state: FSMContext):

    await bot.answer_callback_query(callback_query.id)
    async with state.proxy() as data:
        data['start_location'] = data['dict_of_start_locations'][callback_query.data]
    await Form.finish_location.set()
    await bot.send_message(callback_query.from_user.id, 'Введите адрес прибытия')

@dp.callback_query_handler(lambda x: 'finish_button' in x.data, state=Form.finish_location)
async def process_callback_finish_button(callback_query: types.CallbackQuery, state: FSMContext):

    await bot.answer_callback_query(callback_query.id)
    async with state.proxy() as data:
        data['finish_location'] = data['dict_of_finish_locations'][callback_query.data]
    await Form.zero_state.set()

    inline_kb = types.InlineKeyboardMarkup()
    inline_btn = types.InlineKeyboardButton('Рассчитать стоимость', callback_data='acept')
    inline_kb.add(inline_btn)
    await callback_query.message.answer(await get_info(state), reply_markup=inline_kb)
    
@dp.callback_query_handler(lambda x: 'acept' == x.data, state=Form.zero_state)
async def process_callback_acept_button(callback_query: types.CallbackQuery, state: FSMContext):

    await bot.answer_callback_query(callback_query.id)

    start_lon, start_lat, finish_lon, finish_lat = await get_lon_lat(state)
    yandex_price = await get_price_yandex(state, start_lon, start_lat, finish_lon, finish_lat)

    url_to_yandex = 'https://3.redirect.appmetrica.yandex.com/route?start-lat='+start_lat+'&start-lon='+start_lon+'&end-lat='+finish_lat+'&end-lon='+finish_lon+'&appmetrica_tracking_id=1178268795219780156'
    inline_kb = types.InlineKeyboardMarkup()
    inline_btn_yandex = types.InlineKeyboardButton('Яндекс', url=url_to_yandex)
    inline_kb.row(inline_btn_yandex)
    inline_btn_update = types.InlineKeyboardButton('Обновить цены', callback_data='acept')
    inline_kb.add(inline_btn_update)
    
    await callback_query.message.answer('Цена поездки в Яндексе: '+str(yandex_price)+warring_text, reply_markup=inline_kb)


if __name__ == '__main__':
    executor.start_polling(dp)

