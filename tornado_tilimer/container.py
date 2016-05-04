from autoclave import db
from autoclave.config import *

def generate_caches_clear_func( name ):
    def clear(caches):
        if len(caches[name]) >= CACHES_NUMBER_LIMIT:
            need_to_del_list = sorted(
                caches[name].keys(),
                key = (lambda d : caches[name][d].access_time)
            )[0:(len(caches[name]) - CACHES_NUMBER_LIMIT)]
            for line in need_to_del_list:
                del caches[name][line]
    return clear

def generate_base_data_class( setting, collection_name, db ):

    """参数为class的设置
    
    :param dict setting: 附加到 template 的 namespace 中的属性.
    项内容为字符串 'Ref'，按照DBRef处理。
    项内容为字符串 'MultiRef'，按照DBRef的List处理。
    项内容为字符串 'Direct'，按照正常内容处理。
    """

    direct_list = []
    ref_dict = {}
    multiref_dict = {}
    for line in setting:
        if setting[line]['type'] == 'Ref':
            ref_dict[line] = setting[line]['handler']
        elif setting[line]['type'] == 'MultiRef':
            multiref_dict[line] = setting[line]['handler']
        else:
            direct_list.append(line)

    class base_data(object):
        
        _direct_list = direct_list
        _ref_dict = ref_dict
        _multiref_dict = multiref_dict
        _collection_name = collection_name

        @property
        def class_name(self):
        
            """获取 Class Name, 方便根据 Class Name 进行辨别.
            """
            
            return self.__class__.__name__

        def build(self, data):
            self._data = data
            self._ref_data = {}
        
        def save(self):
            
            """保存当前结构体
            """
            
            db[_collection_name].replace_one(
                filter = {'_id': self._data['_id']},
                replacement = self._data,
                upsert = True,
            )

        def get_dict(self):
            return self._data

        def get(self, key):
            return self._data[key] if key in self._data else None
        
        def __getitem__(self, key):
            return self.get(key)
        
        def __getattribute__(self, key):
            if key == "_data":
                return object.__getattribute__(self, "_data")
            
            if key in self._direct_list:
                return self._data[key] if key in self._data else None
            
            if key in self._ref_dict:
                if key in self._ref_data:
                    return self._ref_data[key]
                if key in self._data and self._data[key]:
                    self._ref_data[key] = self._ref_dict[key](self._data[key])
                    return self._ref_data[key]
                return None
            
            if key in self._multiref_dict:
                if key in self._ref_data:
                    return self._ref_data[key]
                if key in self._data and self._data[key]:
                    self._ref_data[key] = _multirefs(self._data[key], self.multiref_dict[key], self, key)
                    return self._ref_data[key]
                return None
            
            v = object.__getattribute__(self, key)
            if hasattr(v, '__get__'):
               return v.__get__(self)
            return v

    return base_data

class _multirefs(object):
    
    def __init__(self, parent, key, handler):
        self._parent = parent
        self._key = key
        
        data = self._parent[self._key]
        if data == None:
            data = []
        self._data = data
        self._ref_list = {}
        self._handler = handler
        self._length = len(data)
        self._index = 0

    
    def __iter__(self):
        return self
    
    def __len__(self):
        return self._length
    
    def __next__(self):
        if self._index == self._length:
            raise StopIteration
        index = self._index
        self._index = self._index + 1
        return self[index]

    def __getitem__(self, key):
        if key not in self._ref_list:
            self._ref_list[key] = (self._handler)(self._data[key])
        return self._ref_list[key]
    
    def __delitem__(self, key):
        del self._data[key]
        if key < self._index:
            self._index = self._index - 1
    
    def update(self, input):
        if isinstance(input, list):
            self._data.update(input)
            self._length = len(self._data)
        else:
            self._data.push(input)
            self._length = self._length + 1
    
    def delete(self, input):
        if isinstance(input, list):
            for line in input:
                del self[self._data.index(line)]
        else:
            del self[self._data.index(input)]
    
    def clear(self):
        self._data = []
        self._length = 0
        self._index = 0