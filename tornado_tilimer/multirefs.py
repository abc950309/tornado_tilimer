from bson.objectid import ObjectId
import tornado_tilimer.container

class _multirefs_iter(object):
    __solts__ = [
        '_parent',
        '_iter',
    ]
    
    def __init__(self, parent, handler):
        self._parent = parent
        self._iter = handler(self._parent._data)
    
    def __next__(self):
        return self._parent.get_by_id(next(self._iter))

class _multirefs(object):
    
    def __init__(self, data, handler, parent = None):
        if data == None:
            data = []
        self._data = data
        self._ref_dict = {}
        self._handler = handler
        self._index = 0
        self.parent = parent

    @property
    def _change_lock(self):
        if self.parent != None:
            return self.parent._change_lock
        else:
            return False

    @_change_lock.setter
    def _change_lock(self, value):
        if self.parent != None:
            self.parent._change_lock = value

    def get_by_id(self, id):
        if id not in self._ref_dict:
            if id not in self._data:
                raise IndexError("list index out of range")
            self._ref_dict[id] = self._handler(id)
        return self._ref_dict[id]
    
    def __repr__(self):
        return repr(self._data)

    def __hash__(self):
        pass


    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._data == other._data
        if isinstance(other, list):
            other = [self._get_item_id(line) for line in other]
            return self._data == other
        
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return self._data != other._data
        if isinstance(other, list):
            other = [self._get_item_id(line) for line in other]
            return self._data != other
        
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return self._data < other._data
        if isinstance(other, list):
            other = [self._get_item_id(line) for line in other]
            return self._data < other
        
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, self.__class__):
            return self._data <= other._data
        if isinstance(other, list):
            other = [self._get_item_id(line) for line in other]
            return self._data <= other
        
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            return self._data > other._data
        if isinstance(other, list):
            other = [self._get_item_id(line) for line in other]
            return self._data > other
        
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, self.__class__):
            return self._data >= other._data
        if isinstance(other, list):
            other = [self._get_item_id(line) for line in other]
            return self._data >= other
        
        return NotImplemented


    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return _multirefs_iter(self, iter)

    def __contains__(self, item):
        if (isinstance(item, str) or isinstance(item, int) or isinstance(item, ObjectId)) and item in self._data:
            return True
        
        id = getattr(item, 'id', None)
        if id != None and id in self._data:
            return True
        
        return False


    def __add__(self, other):
        if isinstance(other, self.__class__):
            data = other._data
        elif isinstance(other, list):
            data = other
        else:
            return NotImplemented
        
        new_obj = self.copy()
        new_obj._data.extend(data)
        return new_obj

    def __iadd__(self, other):
        ref_dict = None
        if isinstance(other, self.__class__):
            data = other._data
            ref_dict = other._ref_dict
        elif isinstance(other, list):
            data = [self._get_item_id(line) for line in other]
        else:
            return NotImplemented
        
        self._data.extend(data)
        if ref_dict != None:
            self._ref_dict.update(data)
        
        self._change_lock = True
        return self

    def __mul__(self, other):
        if not isinstance(other,int):
            return NotImplemented
        
        new_obj = self.copy()
        new_obj._data *= other
        return new_obj
    
    __rmul__ = __mul__

    def __imul__(self, other):
        if not isinstance(other,int):
            return NotImplemented
        
        self._data *= other
        self._change_lock = True
        return self


    def __getitem__(self, key):
        return self.get_by_id(self._data[key])

    def __setitem__(self, key, val):
        if key >= self.__len__():
            raise IndexError("list assignment index out of range")
        if (isinstance(val, str) or isinstance(val, int) or isinstance(val, ObjectId)):
            id = val
        else:
            id = getattr(val, 'id', None)
            if id == None:
                return NotImplemented
            self._ref_dict[id] = val
        
        temp = self._data.get(key, None)
        self._data[key] = id
        self._change_lock = True
        
        if temp != None and temp not in self._data and temp in self._ref_dict:
            del self._ref_dict[temp]

    def __delitem__(self, key):
        temp = self._data[key]
        del self._data[key]
        self._change_lock = True
        
        if temp not in self._data and temp in self._ref_dict:
            del self._ref_dict[temp]


    _get_item_id = lambda x: tornado_tilimer.container.get_mixed_val(x, id = True)

    def sort(self, key = None, reverse = False):
        if key != None:
            self._data = [x.id for x in sorted(self, key = key, reverse = reverse)]
            self._change_lock = True
        elif reverse:
            self.reverse()

    def index(self, item):
        id = self._get_item_id(item)
        if id == NotImplemented:
            raise ValueError(repr(item) + " is not in list")
        
        self._data.index(id)

    def copy(self):
        new_obj = self.__class__(self._data, self._handler)
        return new_obj

    def append(self, item):
        id = self._get_item_id(item)
        if id == NotImplemented:
            raise TypeError(repr(item) + " is not str or bson.objectid.ObjectId or Datas")
        
        self._data.append(id)
        self._change_lock = True

    def reverse(self):
        self._data.reverse()
        self._change_lock = True

    def __reversed__(self):
        return _multirefs_iter(self, reversed)

    def count(self, item):
        id = self._get_item_id(item)
        if id == NotImplemented:
            return 0
        
        self._data.count(id)

    def pop(self, key = -1):
        if not isinstance(key, int):
            raise TypeError(repr(key) + ' object cannot be interpreted as an integer')
        id = self._data[key]
        obj = self.get_by_id(id)
        
        del self._data[key]
        if id not in self._data and id in self._ref_dict:
            del self._ref_dict[id]
        
        self._change_lock = True
        return obj

    def clear(self):
        self._data = []
        self._ref_dict = {}
        self._change_lock = True

    extend = __iadd__

    def insert(self, key, val):
        id = self._get_item_id(item)
        if id == NotImplemented:
            raise TypeError(repr(item) + " is not str or bson.objectid.ObjectId or Datas")

        self._data.insert(key, val)
        self._change_lock = True

    def remove(self, key):
        id = self._get_item_id(item)
        if id == NotImplemented:
            raise ValueError(repr(item) + " is not in list")
        
        self._data.remove(key)
        self._change_lock = True
        if id not in self._data and id in self._ref_dict:
            del self._ref_dict[id]
