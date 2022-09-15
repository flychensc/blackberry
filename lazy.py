from rqalpha.apis import *

import datetime as dt
import numpy as np

import configparser
import talib


def init(context):
    print(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "START")
    config = configparser.ConfigParser()
    config.read('../cranberry/quantify/config.ini')

    context.MA1 = config.getint('MA', 'MA1')
    context.MA2 = config.getint('MA', 'MA2')
    context.MA3 = config.getint('MA', 'MA3')

    context.RSI1 = config.getint('RSI', 'RSI1')
    context.RSI1_THR = config.getint('RSI', 'THR1')

    context.BAR_COUNT = config.getint('CANDLE', 'PERIOD')
    context.FREQUENCY = '1d'

    context.WAIT_DAYS = config.getfloat('POLICY', 'WAIT_DAYS')

    context.DRAW_DOWN = config.getfloat('POLICY', 'DRAW_DOWN')
    context.BUY_LOSS = config.getfloat('POLICY', 'BUY_LOSS')

    context.TAKE_PROFIT = config.getfloat('POLICY', 'TAKE_PROFIT')
    context.STOP_LOSS = config.getfloat('POLICY', 'STOP_LOSS')

    context.SHIFT = config.getfloat('POLICY', 'SHIFT')

    context.POSITION_DAY = config.getfloat('POLICY', 'POSITION_DAY')
    context.STOCKS_NUM = config.getfloat('POLICY', 'STOCKS_NUM')

    context.stocks = dict()
    context.params = dict()


def handle_bar(context, bar_dict):
    day = context.now.date()

    # 持仓的
    for position in get_positions():
        # fix bug: 除权引起价格变化，触发止损
        # 1. 成本 = 市值-盈利
        # 2. 市值/成本
        profit = position.market_value/(position.market_value-position.pnl)
        #print(f"{position.order_book_id} {(context.params[position.order_book_id]['STOP_LOSS']-1)*100:.2f}% {(context.params[position.order_book_id]['TAKE_PROFIT']-1)*100:.2f}% {(profit-1)*100:.2f}%")
        if profit < context.params[position.order_book_id]['STOP_LOSS']:
            # 进行清仓
            print(f"止损卖出 {position.order_book_id} {(profit-1)*100:.2f}%")
            order_target_percent(position.order_book_id, 0)
            continue
        if profit > context.TAKE_PROFIT:
            # 进行清仓
            print(f"止盈卖出 {position.order_book_id} {(profit-1)*100:.2f}%")
            order_target_percent(position.order_book_id, 0)
            continue
        if profit > context.params[position.order_book_id]['TAKE_PROFIT']:
            # 动态调整
            print(f"动态调整止损区间 {position.order_book_id} {(profit-1)*100:.2f}%")
            context.params[position.order_book_id]['STOP_LOSS'] = context.params[position.order_book_id]['TAKE_PROFIT'] - context.SHIFT
            context.params[position.order_book_id]['TAKE_PROFIT'] += context.SHIFT
            # 不更新day
            continue
        if (day - context.params[position.order_book_id]["day"]).days > context.POSITION_DAY:
            # 进行清仓
            print(f"超期卖出 {position.order_book_id} {(profit-1)*100:.2f}%")
            order_target_percent(position.order_book_id, 0)
            continue

    # 候选的
    for symbol in list(context.stocks):

        # 超幅回撤
        if bar_dict[symbol].close < context.stocks[symbol]["price"]*context.DRAW_DOWN:
            del context.stocks[symbol]
            continue

        # 超过观察点
        if (day - context.stocks[symbol]["day"]).days > context.WAIT_DAYS:
            del context.stocks[symbol]
            continue

        # 低于买点
        if bar_dict[symbol].close < context.stocks[symbol]["price"]*context.BUY_LOSS:

            # 起稳
            if bar_dict[symbol].close > bar_dict[symbol].prev_close:
                print(f"买入 {symbol} {(bar_dict[symbol].close/context.stocks[symbol]['price']-1)*100:.2f}%")
                # 购买该票
                order_target_percent(symbol, 1/context.STOCKS_NUM)
                # 记录购买日期
                context.params[symbol] = {
                    "day": day,
                    "STOP_LOSS": context.STOP_LOSS,
                    "TAKE_PROFIT": 1+context.SHIFT,
                }

                del context.stocks[symbol]


def after_trading(context):
    day = context.now.date()
    day64 = np.int64(day.strftime("%Y%m%d%H%M%S"))
    stocks = all_instruments(type="CS")
    for order_book_id in stocks['order_book_id']:
        # 免费的日级别数据每个月月初更新，下载命令: rqalpha download-bundle
        historys = history_bars(order_book_id, context.BAR_COUNT, context.FREQUENCY, fields=['datetime', 'close'], include_now=True)

        # 数据不足: 新股
        if historys['datetime'].size < context.BAR_COUNT:
            continue
        # 今日无数据: 停牌
        if historys['datetime'][-1] < day64:
            continue

        # 计算指数
        ma1 = talib.SMA(historys['close'], context.MA1)
        ma2 = talib.SMA(historys['close'], context.MA2)
        ma3 = talib.SMA(historys['close'], context.MA3)

        rsi = talib.RSI(historys['close'], timeperiod=context.RSI1)

        # 符合指标与否
        if historys['close'][-1] > ma1[-1] > ma2[-1] > ma3[-1] and rsi[-1] > context.RSI1_THR:
            if order_book_id in context.stocks:
                # 刷新日期
                context.stocks[order_book_id]['day'] = day
            else:
                context.stocks[order_book_id] = {
                    "day": day,
                    "price": historys['close'][-1],
                }

