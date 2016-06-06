import tornado_tilimer.container as container

import time
try:
    from config import *
except:
    from tornado_tilimer.default_config import *

session_setting = {
    "_id": {
        "type": "Direct",
    },
    "uid": {
        "type": "Direct",
    },
    "data": {
        "type": "Direct",
    },
    "creation": {
        "type": "Direct",
    },
    "expired": {
        "type": "Direct",
    },
}

class DataSession(container.generate_base_data_class(setting = session_setting, name = 'session', cache = True)):
    
    """session的结构
    """
    
    def initialize(self, data = None):
        if data:
            self.build(data)
    
    def create(self):
        self.creation = int(time.time())
        self.expired = self.creation + EXPIRED_TIME
    
    def test_expire(self):
        if int(time.time()) > self.expired:
            self.destroy()
            return False
    
    @classmethod
    def clean_db(cls):
        db[self._name].delete_many({"expired": {"$lt": int(time.time())}})
