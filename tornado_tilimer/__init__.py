
class _DataBase(object):
    
    def __init__(self):
        pass
    
    def set(self, db):
        self._db = db
    
    def __call__(self):
        return self._db

db = _DataBase()

def set_database(collection):
    
    """设置公用的数据库Collection
   
    :param pymongo.collection.Collection db: APP 使用的 MongoDB Collection.
    """
    
    db.set(collection)