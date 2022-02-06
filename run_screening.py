# -*- coding: utf-8 -*-

from rqalpha import run_file

import configparser


cfg = configparser.ConfigParser()
cfg.read('config.ini')

config = {
  "base": {
    "start_date": cfg.get('CLASSIFY', 'DAY'),
    "end_date": cfg.get('CLASSIFY', 'DAY')
  },
  "extra": {
    "log_level": "warning",
  },
  "mod": {
    "sys_analyser": {
      "enabled": False
    }
  },
}

strategy_file_path = "./screening.py"

run_file(strategy_file_path, config)
