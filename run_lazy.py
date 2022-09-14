# -*- coding: utf-8 -*-

from rqalpha import run_file

import configparser


cfg = configparser.ConfigParser()
cfg.read('../cranberry/quantify/config.ini')

config = {
  "base": {
    "start_date": cfg.get('ANALYZE', 'START_DAY'),
    "end_date": cfg.get('ANALYZE', 'END_DAY'),
    "accounts": {
        "stock": 100000
    }
  },
  "extra": {
    "log_level": "warning",
  },
  "mod": {
    "sys_progress": {
        "enabled": False,
        "show": True,
    },
    "sys_analyser": {
      "enabled": True,
      "plot": True
    }
  },
}

strategy_file_path = "./lazy.py"

run_file(strategy_file_path, config)
