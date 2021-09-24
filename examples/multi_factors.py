# -*- coding: utf-8 -*-
import pandas as pd
from conbond import ricequant, strategy
from datetime import date
from rqalpha import run
from rqalpha.api import *
import csv
import pathlib
import logging
import pprint

# A few note for this to work:
# convertible bond is not supported by rqalpha by default
# for the backtest to work, we are making the convertible bond as common stock
# The instruments.pk file will need to be updated to include all the bonds' order_book_id

config = {
    'base': {
        'start_date': '2018-01-03',
        'end_date': '2021-09-01',
        'accounts': {
            'stock': 1000000
        },
        'frequency': '1d',
        'benchmark': '000300.XSHG',
        'strategy_file': __file__,
    },
    'extra': {
        'log_level': 'error',
    },
    'mod': {
        'sys_analyser': {
            'enabled': True,
            # 'report_save_path': '.',
            'plot': True
        },
        'sys_simulation': {
            'enabled': True,
            # 'matching_type': 'last'
        },
        'sys_accounts': {
            'enabled': True,
            # 'report_save_path': '.',
            'plot': True
        },
        'sys_scheduler': {
            'enabled': True,
            # 'report_save_path': '.',
            #  'plot': True
        },
        'sys_progress': {
            'enabled': True,
            'show': True,
        },
        'sys_transaction_cost': {
            'enabled': True,
        },
        'local_source': {
            'enabled':
            True,
            'lib':
            'rqalpha_mod_local_source',
            # 其他配置参数
            'start_date':
            '2018-01-02',
            'end_date':
            '2021-09-08',
            'data_path':
            pathlib.Path(__file__).parent.joinpath('cache', 'combined.csv'),
            'data_format':
            'csv',
        }
    }
}


def init(context):
    logging.basicConfig(filename='cache/log.txt',
                        filemode='w',
                        level=logging.DEBUG)
    context.top = 20
    context.ordersf = open('cache/orders.csv', 'w')
    context.orders = csv.writer(context.ordersf)
    context.orders.writerow(
        ['symbol', 'side', 'positionEffect', 'price', 'volume', 'createdAt'])
    scheduler.run_weekly(rebalance,
                         tradingday=1,
                         time_rule=market_open(minute=10))


def rebalance(context, bar_dict):
    logger.info('Running date: %s' % context.now)
    all_instruments = ricequant.fetch(context.now,
                                      cache_dir='cache',
                                      logger=logging)

    df = strategy.rq_filter_conbond(context.now, all_instruments)
    df_candidates = strategy.multi_factors(
        df, {
            'factors': {
                'bond_price': 0.0,
                'conversion_premium': 1.0,
            },
            'top': context.top,
        })
    logging.info('Candidates at %s:' % context.now)
    logging.info('\n%s' % df_candidates.to_string())

    candidates = set(df_candidates.index.values.tolist())
    positions = set()
    for p in context.portfolio.get_positions():
        positions.add(p.order_book_id)
    orders = []
    # 平仓
    for order_book_id in list(positions - candidates):
        orders.append(order_target_percent(order_book_id, 0))
    # 调仓
    for order_book_id in list(positions & candidates):
        orders.append(order_target_percent(order_book_id, 1 / context.top))
    # 开仓
    for order_book_id in list(candidates - positions):
        orders.append(order_target_percent(order_book_id, 1 / context.top))

    for order in orders:
        if order is not None:
            logging.info(order)
            if order.status != ORDER_STATUS.FILLED:
                logging.error('Order error: %s' % order)
            context.orders.writerow([
                'SZSE.%s' % order.order_book_id[:6]
                if order.order_book_id.endswith('XSHE') else 'SHSE.%s' %
                order.order_book_id[:6], 1 if order.side == SIDE.BUY else 2,
                1 if order.position_effect == POSITION_EFFECT.OPEN else 2,
                str(order.avg_price),
                str(order.filled_quantity),
                str(order.datetime)
            ])
    context.ordersf.flush()
    logging.info(pprint.pformat(context.portfolio))


if __name__ == '__main__':
    run(config=config)
