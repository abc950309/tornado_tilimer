from autoclave import db
from autoclave.config import *
import uuid
import ObjectId from bson.objectid

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
    
    :param dict setting:
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
            
            """由给定的数据，建立结构体
            """
            
            self._data = data
            self._ref_data = {}
        
        @classmethod
        def get_by_filter(cls, filter):
        
            """通过filter来获取数据
            """
            
            new_obj = cls()
            new_obj.build(db[cls._collection_name].find_one(
                filter
            ))
            return new_obj
        
        @classmethod
        def get(cls):
        
            """通过_id来获取数据
            """
            
            return cls.get_by_filter({"_id": id})
        
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
            
        
        def save(self):
            
            """保存当前结构体
            """
            
            db[self._collection_name].replace_one(
                filter = {'_id': self._data['_id']},
                replacement = self._data,
                upsert = True,
            )
        
        def destroy(self):
            
            """摧毁当前对象所代表的数据库结构
            """
            
            db[self._collection_name].delete_many(
                filter = {'_id': self._data['_id']},
            )
        
        def get_dict(self):
            
            """获取结构体中的数据
            """
            
            return self._data

        def get_raw(self, key):
        
            """使用key获取数据初始值
            """
            
            return self._data[key] if key in self._data else None
        
        def __getitem__(self, key):
            
            """"通过数组形式获取的值为初始值
            """"
            
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
            
            if key in self._direct_list:
                self._data[key] = value
            elif key in self._ref_dict:
                if not (isinstance(value, string) or isinstance(value, int) or isinstance(value, ObjectId)):
                    value = value._id
                self._data[key] = value
                if key in self._ref_data:
                    del self._ref_data[key]
            elif key in self._multiref_dict:
                if isinstance(value, _multirefs):
                    value = value._data
                self._data[key] = value
                if key in self._ref_data:
                    del self._ref_data[key]
            else:
                raise NameError("Key is not in the list!")
        
        def __delattr__(self, key):
            
            """通过属性来删除值
            """
            
            if key in self._data:
                del self._data[key]
                if key in self._ref_data:
                    del self._ref_data[key]
    
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