
class StaticData(object):
    
    def __new__(cls, *args, **kwargs)
    
    def __init__(self, name):
        with open(name, mode = 'r', encoding = 'utf-8') as f:
            raw_data = f.read().decode()
            self._data = json.load(raw_data)
        
        