import time
from libdatabus import databus
from libutils import get_data_path
from mktdata.mktdata_base import MktDataBase


class MktDataCurrencies(MktDataBase):
    def execute(self):
        pass

    def loop(self):
        while True:
            data_sources = {"MarketData": "RobotFX_MarketData.json"}
            for key, datafile in data_sources.items():
                databus.update_from_file(get_data_path(datafile), key)
            time.sleep(10)
