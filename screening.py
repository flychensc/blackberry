from rqalpha.apis import *
from scipy.optimize import leastsq

import datetime as dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import configparser


def classify(context, order_book_id, order_day, historys):
    cost = historys['close'][0]
    # 跳过当天
    historys = historys[1:]

    # 下跌比例
    low = historys['close'].min()/cost - 1
    # 过了几天
    low_days = historys['close'].argmin() + 1

    # 上涨比例
    high = historys['close'].max()/cost - 1
    # 过了几天
    high_days = historys['close'].argmax() + 1

    # print(low, low_days, high, high_days)

    context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'low'] = low
    context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'low_days'] = low_days
    context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'high'] = high
    context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'high_days'] = high_days

    # 最低的涨幅都大于0
    if low > 0:
        context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'classify'] = "A"
    # 最高的涨幅都小于0
    elif high < 0:
        context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'classify'] = "D"
    # 先跌后涨
    elif low_days < high_days:
        context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'classify'] = "B"
    # 先涨后跌
    elif low_days > high_days:
        context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'classify'] = "C"


def init(context):
    print(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "START")
    config = configparser.ConfigParser()
    config.read('../cranberry/preparing/config.ini')

    context.BAR_COUNT = (dt.datetime.strptime(config.get("CLASSIFY", "DAY"), "%Y-%m-%d") - dt.datetime.strptime(config.get("PICK", "START_DAY"), "%Y-%m-%d")).days
    context.BAR_COUNT = int(context.BAR_COUNT/7*5)
    context.FREQUENCY = '1d'

    context.POSITION_DAY = config.getint('POLICY', 'POSITION_DAY')

    context.classifying = pd.read_csv("picking.csv", parse_dates=["order_day"], date_parser=lambda x: dt.datetime.strptime(x, "%Y-%m-%d"))
    # CONVERT dtype: datetime64[ns] to datetime.date
    context.classifying['order_day'] = context.classifying['order_day'].dt.date

    context.classifying = context.classifying.assign(low=np.nan, low_days=np.nan, high=np.nan, high_days=np.nan, classify="")


def after_trading(context):
    day = context.now.date()
    stocks = all_instruments(type="CS")
    for order_book_id in stocks['order_book_id']:
        historys = history_bars(order_book_id, context.BAR_COUNT, context.FREQUENCY, fields=['datetime', 'close'], include_now=True)

        if not historys.size: continue

        order_data = context.classifying[(context.classifying['order_book_id'] == order_book_id) &
                                     (context.classifying['order_day'] < day) &
                                     (context.classifying['classify'] == "")]

        # 该票所有的入选时间点
        for order_day in order_data['order_day'].sort_values():
            order_day64 = np.int64(order_day.strftime("%Y%m%d%H%M%S"))
            # 逐次缩小historys
            historys = historys[(historys['datetime'] >= order_day64)]

            # fix bug: 可能不是同一天
            if historys['datetime'][0] != order_day64:
                continue

            # 数据不足
            if historys.size < context.POSITION_DAY:
                break
            classify(context, order_book_id, order_day, historys[:context.POSITION_DAY])

    if context.run_info.end_date == day:
        # 丢弃空行
        context.classifying.drop(context.classifying[context.classifying["classify"].isna()].index, inplace=True)
        context.classifying.to_csv('classifying.csv', index=False)
        print(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "END")
