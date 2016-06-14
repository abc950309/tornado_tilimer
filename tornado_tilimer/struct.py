import tornado_tilimer.container as container

import time
import types

try:
    from config import *
except:
    from tornado_tilimer.default_config import *

session_setting = {
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
        self.expired = self.creation + EXPIRED_TIME
    
    def test_expire(self):
        if int(time.time()) > self.expired:
            self.destroy()
            return False
    
    @classmethod
    def clean_db(cls):
        cls.db[self._name].delete_many({"expired": {"$lt": int(time.time())}})

class _structs(object):
    
    def __init__(self):
        setattr(self, 'DataSession', DataSession)

    def add_struct(self, item):
        if isinstance(item, types.ModuleType):
            for n in dir(item):
                if container.check_data(getattr(item, n)):
                    setattr(self, n, getattr(item, n))

        elif isinstance(item, list):
            for m in item:
                if hasattr(getattr(m, 'get', None), '__call__'):
                    setattr(self, m.__name__, m)

        else:
            assert isinstance(item, dict)
            for name, cls in item.items():
                if hasattr(getattr(cls, 'get', None), '__call__'):
                    setattr(self, name, cls)

Structs = _structs()