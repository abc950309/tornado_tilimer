import tornado_tilimer
from tornado_tilimer.multirefs import _multirefs

from collections import UserDict
import traceback
import uuid
import time

pool = {'setting': {}}
clean_couter = {}

class class_property(property):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()

def get_obj_id():
    return uuid.uuid1().hex

def get_obj_id_time(id):
    return int((uuid.UUID(id).time - 0x01b21dd213814000)*100/1e9)

id_type = type(get_obj_id())

def check_data(cls):
    return hasattr(cls, 'tornado_tilimer_datas_signal')

def get_mixed_val(item, id = False):
    if check_data(item):
        return getattr(item, 'id', NotImplemented)
    elif (not id) or isinstance(item, id_type):
        return item
    else:
        raise NotImplementedError()

def get_names(func):
    return tuple((func.__qualname__).split('.')[-2:])

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

class RawDataDict(UserDict):
    def __init__(self, *args, data, **kwargs):
        super(RawDataDict, self).__init__(*args, **kwargs)
        self._base_data = data
    
    def __setitem__(self, key, item):
        self.data[key] = item
        if self._base_data._builded:
            self._base_data._change_lock = True
    
    def __delitem__(self, key):
        del self.data[key]
        if self._base_data._builded:
            self._base_data._change_lock = True

def generate_base_data_class(setting, name, cache = False):

    """参数为class的设置
    
    :param dict setting:
    项内容为字符串 'Ref'，按照DBRef处理。
    项内容为字符串 'MultiRef'，按照DBRef的List处理。
    项内容为字符串 'Direct'，按照正常内容处理。
    """
    
    global pool
    global clean_couter
    
    direct_list = ['_id', 'lastModified']
    ref_dict = {}
    multiref_dict = {}
    for line in setting:
        if setting[line]['type'] == 'Ref':
            ref_dict[line] = setting[line]['handler']
        elif setting[line]['type'] == 'MultiRef':
            multiref_dict[line] = setting[line]['handler']
        else:
            direct_list.append(line)
    
    direct_list = tuple(direct_list)
    
    class base_data(object):
        
        _direct_list = direct_list
        _ref_dict = ref_dict
        _multiref_dict = multiref_dict
        _name = name
        
        @class_property
        @classmethod
        def db(cls):
            return tornado_tilimer.db()
        
        def __init__(self, *args, **kwargs):
            
            """对象初始化
            """
            
            setattr(self, '_change_lock', False)
            setattr(self, '_destroyed', False)
            setattr(self, '_builded', False)
            self._data = RawDataDict({}, data = self)
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
        
        @staticmethod
        def tornado_tilimer_datas_signal():
            pass
        
        @property
        def id(self):
        
            """获取 Class Name, 方便根据 Class Name 进行辨别.
            """
            
            return self._id

        def build(self, data):
            
            """由给定的数据，建立结构体
            """
            
            self._data.update(data)
            self._ref_data = {}
            setattr(self, '_builded', True)
        
        
        @classmethod 
        def find_by_filter(cls, filter, **kwargs):
            return cls.db[cls._name].find_one(filter, **kwargs)
        
        @classmethod
        def get_by_filter(cls, filter, **kwargs):
        
            """通过filter来获取数据
            """
            
            data = cls.find_by_filter(filter, **kwargs)
            if data == None:
                return None
            
            new_obj = cls()
            new_obj.build(data)
            return new_obj
        
        @classmethod
        def get_multi(cls, filter, **kwargs):
            if 'sort' not in kwargs:
                kwargs['sort'] = (('lastModified', -1),)
            data = [x['_id'] for x in cls.db[cls._name].find(filter, ('_id'), **kwargs)]
            return _multirefs(data, cls.get)
        
        @classmethod
        def count(cls, filter, **kwargs):
            return cls.db[cls._name].find(filter, ('_id'), **kwargs).count()
        
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
        def new(cls, *args, did = None, **kwargs):
            id = did or get_obj_id()
            new_obj = cls()
            new_obj.build({"_id": id})
            new_obj.__dict__['__creating'] = True
            
            if new_obj.create(*args, **kwargs) == False:
                return False
            else:
                del new_obj.__dict__['__creating']
            
            new_obj.force_save()
            return new_obj

        def renew(self):
            id = get_obj_id()
            new_obj = self.__class__()
            new_obj.build(self._data)
            new_obj.build({'_id': id})
            new_obj.save()
            return new_obj


        @property
        def creation(self):
            return get_obj_id_time(self.id)
        
        @property
        def lastModified(self):
            return self._data['lastModified'] or 0
        
        def create(self):
        
            """被new方法引用，自定义创建过程中的操作。
            """
            
            pass
            
        
        def save(self, *args, **kwargs):
            
            """保存当前结构体
            """
            if self._change_lock and not self._destroyed:
                self.force_save(*args, **kwargs)
            self.clean_data()
        
        def force_save(self, *args, **kwargs):
            if self.__dict__.get('__creating', False):
                return
            
            self.on_save(*args, **kwargs)
            for index in list(self._data.keys()):
                if self._data[index] == None:
                    del self._data[index]
            
            self._data['lastModified'] = int(time.time())
            
            result = self.db[self._name].replace_one(
                filter = {'_id': self.id},
                replacement = self._data,
                upsert = True,
            )
            
            self._change_lock = False

        def on_save(self):
            
            pass
            
        def destroy(self, *args, **kwargs):
            
            """摧毁当前对象所代表的数据库结构
            """
            
            self.on_destroy(*args, **kwargs)
            self._destroyed = True
            
            self.db[self._name].delete_many(
                filter = {'_id': self._data['_id']},
            )
            
            try:
                del pool[self._name][self._data['_id']]
            except KeyError:
                pass
            
            self._data = RawDataDict({}, data = self)
            self._ref_data = {}
        
        def on_destroy(self, *args, **kwargs):
            pass
        
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
                return self._data.get(key, None)
            
            elif key in self._ref_dict:
                if key not in self._ref_data and key in self._data and self._data[key]:
                    self._ref_data[key] = self._ref_dict[key](self._data[key])
                return self._ref_data.get(key, None)
            
            elif key in self._multiref_dict:
                if key not in self._ref_data and key in self._data and isinstance(self._data[key], list):
                    self._ref_data[key] = _multirefs(self._data[key], self._multiref_dict[key], parent = self)
                return self._ref_data.get(key, None)
            
            return None
        
        def __setattr__(self, key, value):
            
            """通过属性来设置值
            """

            if key in self.__dict__:
                self.__dict__[key] = value
                return
            
            if ( key in self.__class__.__dict__
                and isinstance(self.__class__.__dict__[key], property)
                and getattr(self.__class__.__dict__[key], 'fset', None) != None ):
                return self.__class__.__dict__[key].__set__(self, value)
            
            if key in self._direct_list:
                self._data[key] = value
                return
            elif key in self._ref_dict:
                if value == None:
                    self.__delattr__(key)
                    return
                value = get_mixed_val(value, id = True)
                self._data[key] = value
                if key in self._ref_data:
                    del self._ref_data[key]
                return
            elif key in self._multiref_dict:
                if value == None:
                    self.__delattr__(key)
                    return
                if isinstance(value, _multirefs):
                    value = value._data
                elif isinstance(value, list):
                    value = [get_mixed_val(line, id = True) for line in value]
                else:
                    raise TypeError(repr(value) + " is not str or int or bson.objectid.ObjectId or Datas")
                
                self._data[key] = value
                if key in self._ref_data:
                    del self._ref_data[key]
                return
            else:
                self.__dict__[key] = value
        
        def __delattr__(self, key):
            
            """通过属性来删除值
            """
            if ( key in self.__class__.__dict__
                and isinstance(self.__class__.__dict__[key], property)
                and getattr(self.__class__.__dict__[key], 'fdel', None) != None ):
                return self.__class__.__dict__[key].__delete__(self)
            
            if key in self._data:
                del self._data[key]
                if key in self._ref_data:
                    del self._ref_data[key]
            elif key in self.__dict__:
                del self.__dict__[key]
    
    if cache:
    
        @classmethod
        def get_by_filter(cls, filter, **kwargs):
        
            """通过filter来获取数据
            """

            data = False
            
            if "_id" in filter:
                id = filter["_id"]
            else:
                data = cls.find_by_filter(filter, **kwargs)
                if data == None:
                    return None
                id = data["_id"]
            
            if id not in cls._pool[cls._name]:            
                if data == False:
                    data = cls.find_by_filter(filter, **kwargs)
                    if data == None:
                        return None
                
                new_obj = cls()
                new_obj.build(data)
                cls._pool[cls._name][id] = new_obj
            
            cls._pool[cls._name][id].last_refer = int(time.time())
            return cls._pool[cls._name][id]

        @classmethod
        def get(cls, id):
        
            """通过_id来获取数据
            """
            
            if id not in cls._pool[cls._name]:
                return cls.get_by_filter({"_id": id})
            
            cls._pool[cls._name][id].last_refer = int(time.time())
            return cls._pool[cls._name][id]
        
        @classmethod
        def clean_data(cls):
            cls._clean_couter[cls._name] = cls._clean_couter[cls._name] + 1
            if cls._clean_couter[cls._name] > 1024:
                now = int(time.time())
                last_line = now - 3600

                for index, val in cls._pool[cls._name].items():
                    if val.last_refer < last_line:
                        del cls._pool[cls._name][index]

                if len(cls._pool[cls._name]) > 1024:
                    for line in sorted(cls._pool[cls._name].items(), key=lambda d:d[1].last_refer, reverse = True)[1024:]:
                        del cls._pool[cls._name][line[0]]
                
                cls.clean_db()
                
                cls._clean_couter[cls._name] = 0

        setattr(base_data, "get_by_filter", get_by_filter)
        setattr(base_data, "get", get)
        setattr(base_data, "clean_data", clean_data)
        setattr(base_data, "_pool", pool)
        setattr(base_data, "_clean_couter", clean_couter)
        clean_couter[name] = 0
        pool[name] = {}
        
    return base_data
