from rqalpha.apis import *
from scipy.optimize import leastsq

import datetime as dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import configparser


# refer to https://blog.csdn.net/qq_44158369/article/details/120205029
def func(p, x):
    k, b = p
    return k * x + b


def error(p, x, y):
    return func(p, x) - y


def classify(context, order_book_id, order_day, historys, disp=False):
    Yi = historys['close']
    Xi = np.sort(Yi)

    #p0 = [Xi[0], Yi[0]]
    p0 = [1, 1]

    # 最小二乘法拟合直线
    Para = leastsq(error, p0, args=(Xi, Yi))

    k, b = Para[0]

    if disp:
        print(k, b)
        plt.plot(Xi, Yi, color='green', linewidth=2)
        plt.plot(Xi, k*Xi+b, color='red', linewidth=2)
        plt.show()

    k = round(k, 2)

    label = "holding"
    if k <= context.K_LOSS:
        label = "loss"
    elif k >= context.K_PROFIT:
        label = "profit"

    context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'k'] = k
    context.classifying.loc[(context.classifying['order_day'] == order_day) & (context.classifying['order_book_id'] == order_book_id), 'classify'] = label


def init(context):
    print(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "START")
    config = configparser.ConfigParser()
    config.read('../cranberry/preparing/config.ini')

    context.BAR_COUNT = (dt.datetime.strptime(config.get("CLASSIFY", "DAY"), "%Y-%m-%d") - dt.datetime.strptime(config.get("PICK", "START_DAY"), "%Y-%m-%d")).days
    context.BAR_COUNT = int(context.BAR_COUNT/7*5)
    context.FREQUENCY = '1d'

    context.POSITION_DAY = config.getint('POLICY', 'POSITION_DAY')
    context.K_LOSS = config.getfloat('POLICY', 'K_LOSS')
    context.K_PROFIT = config.getfloat('POLICY', 'K_PROFIT')

    # context.classifying = pd.DataFrame(columns=['order_day','order_book_id', 'k', 'classify'])
    context.classifying = pd.read_csv("picking.csv", parse_dates=["order_day"], date_parser=lambda x: dt.datetime.strptime(x, "%Y-%m-%d"))
    # CONVERT dtype: datetime64[ns] to datetime.date
    context.classifying['order_day'] = context.classifying['order_day'].dt.date

    context.classifying = context.classifying.assign(k=np.nan, classify="")


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
            # 数据不足
            if historys.size < context.POSITION_DAY:
                break
            classify(context, order_book_id, order_day, historys[:context.POSITION_DAY])

    if context.run_info.end_date == day:
        context.classifying.to_csv('classifying.csv', index=False)
        print(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "END")

