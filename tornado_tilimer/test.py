
def get_a():
    class a:
        @property
        def class_name(self):
        
            """获取 Class Name, 方便根据 Class Name 进行辨别.
            """
            
            return self.__class__.__name__
        
        def __init__(self):
            pass

        def print_name(self):
            print(self.class_name)
    return a

class b(get_a()):
    def __init__(self):
        self.print_name()


b()