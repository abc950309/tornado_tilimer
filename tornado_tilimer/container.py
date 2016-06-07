from tornado_tilimer import db

import uuid
import time
from bson.objectid import ObjectId

pool = {}
clean_couter = {}

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

def generate_base_data_class(setting, name, cache = False):

    """参数为class的设置
    
    :param dict setting:
    项内容为字符串 'Ref'，按照DBRef处理。
    项内容为字符串 'MultiRef'，按照DBRef的List处理。
    项内容为字符串 'Direct'，按照正常内容处理。
    """
    
    global pool
    global clean_couter
    
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
        _name = name
        
        def __init__(self, *args, **kwargs):
            
            """对象初始化
            """
            
            setattr(self, '_change_lock', False)
            setattr(self, '_destroyed', False)
            self.initialize(*args, **kwargs)
        
        def initialize(self, *args, **kwargs):
            
            """为初始化自定义而设计的钩子
            """
            
            pass
        
        @property
        def class_name(self):
        
            """获取 Class Name, 方便根据 Class Name 进行辨别.
            """
            
            return self.__class__.__name__

        def build(self, data):
            
            """由给定的数据，建立结构体
            """
            
            self._data = data
            self._ref_data = {}
        
        @classmethod 
        def find_by_filter(cls, filter):
            return db()[cls._name].find_one(
                filter
            )
        
        @classmethod
        def get_by_filter(cls, filter):
        
            """通过filter来获取数据
            """
            
            new_obj = cls()
            new_obj.build(db()[cls._name].find_one(
                filter
            ))
            return new_obj
        
        @classmethod
        def get(cls, id):
        
            """通过_id来获取数据
            """
            
            return cls.get_by_filter({"_id": id})

        
        @classmethod
        def clean_data(cls):
            pass
        
        @classmethod
        def clean_db(cls):
            pass
        
        def __del__(self):
            self.save()
        
        @classmethod
        def new(cls):
            _id = str(uuid.uuid4().hex)
            new_obj = cls({"_id": _id})
            new_obj.create()
            new_obj.save()
            return new_obj
        
        def create(self):
        
            """被new方法引用，自定义创建过程中的操作。
            """
            
            pass
            
        
        def save(self, *args, **kwargs):
            
            """保存当前结构体
            """
            
            if self._change_lock and not self._destroyed:
                db()[self._name].replace_one(
                    filter = {'_id': self._data['_id']},
                    replacement = self._data,
                    upsert = True,
                )
                self._change_lock = False
            
            self.on_save(*args, **kwargs)
            
            self.clean_data()
        
        def on_save(self):
            
            pass
            
        def destroy(self):
            
            """摧毁当前对象所代表的数据库结构
            """
            
            self._destroyed = False
            self._data = {}
            self._ref_data = {}
            
            db()[self._name].delete_many(
                filter = {'_id': self._data['_id']},
            )
            
            del pool[self._name][self._id]
        
        def get_dict(self):
            
            """获取结构体中的数据
            """
            
            return self._data

        def get_raw(self, key):
        
            """使用key获取数据初始值
            """
            
            return self._data[key] if key in self._data else None
        
        def __getitem__(self, key):
            
            """通过数组形式获取的值为初始值
            """
            
            return self.get_raw(key)
        
        def __getattr__(self, key):
            
            """通过属性形式获取值使用解析过的版本
            """
            
            if key in self._direct_list:
                return self._data[key] if key in self._data else None
            
            elif key in self._ref_dict:
                if key in self._ref_data:
                    return self._ref_data[key]
                if key in self._data and self._data[key]:
                    self._ref_data[key] = self._ref_dict[key](self._data[key])
                    return self._ref_data[key]
                return None
            
            elif key in self._multiref_dict:
                if key in self._ref_data:
                    return self._ref_data[key]
                if key in self._data and self._data[key]:
                    self._ref_data[key] = _multirefs(self._data[key], self.multiref_dict[key], self, key)
                    return self._ref_data[key]
                return None
            return None
            
        def __setattr__(self, key, value):
            
            """通过属性来设置值
            """
            
            if key == "_change_lock" or key in self.__dict__:
                self.__dict__[key] = value
                return
            
            self._change_lock = True
            
            if key in self._direct_list:
                self._data[key] = value
                if not self._change_lock:
                    self._change_lock = True
            elif key in self._ref_dict:
                if not (isinstance(value, string) or isinstance(value, int) or isinstance(value, ObjectId)):
                    value = value._id
                self._data[key] = value
                if key in self._ref_data:
                    del self._ref_data[key]
                if not self._change_lock:
                    self._change_lock = True
            elif key in self._multiref_dict:
                if isinstance(value, _multirefs):
                    value = value._data
                self._data[key] = value
                if key in self._ref_data:
                    del self._ref_data[key]
                if not self._change_lock:
                    self._change_lock = True
            else:
                self.__dict__[key] = value
        
        def __delattr__(self, key):
            
            """通过属性来删除值
            """
            
            if key in self._data:
                del self._data[key]
                self._change_lock = True
                if key in self._ref_data:
                    del self._ref_data[key]
    
    if cache:
    
        @classmethod
        def get_by_filter(cls, filter):
        
            """通过filter来获取数据
            """
            
            data = False
            
            if "_id" not in filter:
                data = cls.find_by_filter(filter)
                id = data._id
            else:
                id = filter["_id"]
            
            if id not in pool[cls._name]:            
                if data == False:
                    data = cls.find_by_filter(filter)
                
                if data == None:
                    return None
                new_obj = cls()
                new_obj.build(data)
                pool[cls._name][id] = new_obj
            
            pool[cls._name][id].last_refer = int(time.time())
            return pool[cls._name][id]

        @classmethod
        def get(cls, id):
        
            """通过_id来获取数据
            """
            
            if id not in pool[cls._name]:
                return cls.get_by_filter({"_id": id})
            
            pool[cls._name][id].last_refer = int(time.time())
            return pool[cls._name][id]
        
        @classmethod
        def clean_data(cls):
            clean_couter[cls._name] = clean_couter[cls._name] + 1
            if clean_couter[cls._name] > 1024:
                now = int(time.time())
                last_line = now - 3600

                for index, val in pool[cls._name].items():
                    if val.last_refer < last_line:
                        del pool[cls._name][index]

                if len(pool[cls._name]) > 1024:
                    for line in sorted(pool[cls._name].items(), key=lambda d:d[1].last_refer, reverse = True)[1024:]:
                        del pool[cls._name][line[0]]
                
                cls.clean_db()
                
                clean_couter[cls._name] = 0

        setattr(base_data, "get_by_filter", get_by_filter)
        setattr(base_data, "get", get)
        setattr(base_data, "clean_data", clean_data)
        clean_couter[name] = 0
        pool[name] = {}
        
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
    
    def __setitem__(self, key, value):
        self._data[key] = value
        if key in self._ref_list:
            del self._ref_list[key]
    
    def __getitem__(self, key):
        if key not in self._ref_list:
            self._ref_list[key] = (self._handler)(self._data[key])
        return self._ref_list[key]

    def __delitem__(self, key):
        del self._data[key]
        self._length = self._length - 1
        if key < self._index:
            self._index = self._index - 1
    
    def __contains__(self, item):
        return item in self._data
    
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