import tornado.web
import tornado.concurrent
import tornado_tilimer.struct as struct
import tornado_tilimer.ui_modules as ui_modules
import tornado_tilimer.minfy as minfy
import tornado_tilimer as init

from concurrent.futures import ThreadPoolExecutor

import collections
import os.path

try:
    from config import *
except:
    from tornado_tilimer.default_config import *

DataException = struct.DataException

def get_args(needed = None, optional = None, n = None, o = None):
    
    """目的为获取参数的装饰器
    
    :param list needed: 必须参数.
    :param list optional: 可选参数.
    """
    
    if n:
        needed = n
    if o:
        optional = o
    
    if needed:
        needed = tuple(needed)
    if optional:
        optional = tuple(optional)
    
    def _deco(func):
        def __deco(self, *args, **kwargs):
            arguments = {}
            if needed:
                for line in needed:
                    arguments[line] = self.get_argument(line, None)
                    if not arguments[line] or len(arguments[line]) == 0:
                        raise tornado.web.HTTPError(400)
                        self.finish()
            if optional:
                for line in optional:
                    temp_argument = self.get_argument(line, None)
                    if temp_argument and temp_argument != '':
                        arguments[line] = temp_argument
            
            kwargs.update(arguments)
            return func(self, *args, **kwargs)
        return __deco
    return _deco


class Executor(ThreadPoolExecutor):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not getattr(cls, '_instance', None):
            cls._instance = ThreadPoolExecutor(max_workers=20)
        return cls._instance


def BaseApplication(**kwargs):

    class _application(tornado.web.Application):
        def __init__(self, **settings):
            if 'static_path' in settings:
                minfy.init_minfy(
                    os.path.join(settings['static_path'], 'css'),
                    os.path.join(settings['static_path'], 'js'),
                    os.path.join(settings['static_path'], 'less'),
                )
            super().__init__(**settings)

    return _application


def BaseHandler(**kwargs):
    
    """通过这个函数获得 BaseHandler.
    
    :param dict api_handlers: 附加到 template 的 namespace 中的属性.
    :param dict authless_handlers: 附加到 template 的 namespace 中的属性.
    :param dict public_js: 附加到 template 的 namespace 中的属性.
    :param dict public_css: 附加到 template 的 namespace 中的属性.
    :param dict current_user_handler: 附加到 template 的 namespace 中的属性.
    """
    
    class _base_handler(tornado.web.RequestHandler):

        """Base Handler，提供基本服务。
        添加了Session和验证处理。
        """

        executor = Executor()

        @property
        def class_name(self):
        
            """获取 Class Name, 方便根据 Class Name 进行辨别.
            """
            
            return self.__class__.__name__
        
        @property
        def ip_address(self):
            return self.request.headers.get("X-Real-IP") or self.request.remote_ip

        @property
        def api_flag(self):
            
            """确认是否为api
            """
            
            if not hasattr(self, '_api_flag'):
                self._api_flag = (True if hasattr(self, '_api_handlers') and self.class_name in self._api_handlers else False)
            return self._api_flag
        
        def __init__(self, *args, **kwargs):
            
            """替代原 __init__ 函数.
            """
            
            super().__init__(*args, **kwargs)
            
            if hasattr(self, '_template_namespace'):
                self.ui.update(self._template_namespace)
            
            self.ui['class_name'] = self.class_name


        def new_session(self):
        
            """获取新的 session。
            """
            
            self.session = struct.DataSession.new()
            self.session_id = self.session._id


        @tornado.concurrent.run_on_executor
        def run_on_executor(self, func, *args, **kwargs):
            return func(*args, **kwargs)

        @tornado.concurrent.run_on_executor
        def run_data_func(self, func, *args, **kwargs):
            try:
                return func(*args, **kwargs)
            except DataException as e:
                self.show_exception(e)

        def show_exception(self, *args, header = None):
            if not isinstance(args[0], DataException):
                e = DataException(*args)
            else:
                e = args[0]
            
            if self._finished:
                raise RuntimeError("Cannot write() after finish()")
            
            if not (self.ajax_flag or self.api_flag):
                url = [self.request.headers.get("Referer", '/')]
                
                if '?' in url[0]:
                    if url[0][-1] != '&':
                        url.append('&')
                else:
                    url.append('?')
                
                url.append('dscp=')
                url.append(str(e.dscp))
                url.append('&errno=')
                url.append(str(e.errno))
                if header:
                    url.append('&header=')
                    url.append(str(header))
                self.redirect(''.join(url))

            else:
                self.finish({'errno': e.errno, 'dscp': e.dscp})

        def get_session_id(self):
        
            """获取 session_id.
            """
            if self.api_flag:
                raw_session_id = self.get_argument('token', None)
                if raw_session_id:
                    return raw_session_id
            
            if self.settings.get('cookie_secret'):
                raw_session_id = self.get_secure_cookie("token")
                return (raw_session_id.decode() if raw_session_id else None)
            else:
                return self.get_cookie("token")


        def initialize_session(self):
            
            """初始化 session.
            """
            
            self.session_id = self.get_session_id()
            
            if not self.session_id:
                if self.api_flag:
                    raise tornado.web.HTTPError(400)
                    return
                self.new_session()
                self.set_session()
            else:
                self.session = struct.DataSession.get(self.session_id)
            
            self.add_wait_to_save_data(self.session)

        def set_session(self):
            
            """在Cookie中设置session id
            """
            
            if self.api_flag:
                raise tornado.web.HTTPError(400)
            
            if self.settings.get('cookie_secret'):
                return self.set_secure_cookie("token", self.session_id)
            else:
                return self.set_cookie("token", self.session_id)

        @property
        def ajax_flag(self):
            
            """检测是否为Ajax请求，需在Ajax请求中添加ajax_flag标签
            """
            
            if not hasattr(self, '_ajax_flag'):
                try:
                    self.get_argument('ajax_flag')
                except:
                    self._ajax_flag = None
                else:
                    self._ajax_flag = True
            
            return self._ajax_flag


        @property
        def mobile_flag(self):
            
            """检测是否为Ajax请求，需在Ajax请求中添加ajax_flag标签
            """
            
            if not hasattr(self, '_mobile_flag'):
                if self.request.headers['User-Agent'].find("Mobile") != -1 :
                    self._mobile_flag = True
                else:
                    self._mobile_flag = False
            
            return self._mobile_flag


        def prepare(self):
            
            """准备进入页面正式的处理，提供了session初始化接口、公共js&css接口、render数据人性化和根据列表提供验证等的服务基础。
            """
            
            self.session_id = None
            self.session = None
            self._render_data = {}
            
            if not (self.ajax_flag or self.api_flag):
                self.add_public_js()
                self.add_public_css()
                self.add_public_less()
            
            self.initialize_session()
            
            self.prepare_c()
            
            if hasattr(self, '_authless_handlers') and self.class_name not in self._authless_handlers:
                self.authenticate()


        def add_wait_to_save_data(self, data):
            
            """为自动数据保存做准备
            """
            
            if not hasattr(self, '_wait_to_save_data'):
                self._wait_to_save_data = []
            
            if data not in self._wait_to_save_data:
                self._wait_to_save_data.append(data)
            
        
        def add_public_js(self):
            
            """为生成器准备的添加公共js脚本的钩子
            假如您并未使用该特性，请按照您的意愿使用
            """
            
            pass
        
        def add_public_css(self):
            
            """为生成器准备的添加公共css脚本的钩子
            假如您并未使用该特性，请按照您的意愿使用
            """
            
            pass
        
        def add_public_less(self):
            
            """为生成器准备的添加公共css脚本的钩子
            假如您并未使用该特性，请按照您的意愿使用
            """
            
            pass
        
        def prepare_c(self):
            
            """为自定义的prepare程序段留下的钩子
            """
            
            pass

        
        def initialize_render_data(self):
            
            """初始化 render data
            """
            
            if not hasattr(self, '_render_data'):
                self._render_data = {}
        
        
        def add_render(self, name, val):
            
            """在render预备字典中添加数据，在渲染时不必添加极多的各类数据。
            
            :param name: 在模板中可用的调用名.
            :param val: 调用名对应的值.
            """
            
            self.initialize_render_data()
            self._render_data[name] = val


        def make_static_url_of_files(self, list):
            for index in range(len(list)):
                if not self.is_absolute(list[index]):
                    list[index] = self.static_url(list[index], include_version=True)


        def add_less(self, name):
            self.initialize_render_data()
            
            if self.settings.get('debug', False) or not minfy.minfy_flag():
                self.less_flag = True
                if 'custom_less' not in self._render_data:
                    self._render_data['custom_less'] = []
                
                name = self.static_url(''.join(('less/', name, '.less')), include_version=True)
                return self._render_data['custom_less'].append( ''.join(('<link rel="stylesheet/less" type="text/css" href="', name, '" />')))
            
            return self._render_data['custom_css'].append( ''.join(("less/", name, '.min.less')) )


        def add_css(self, name):
            self.initialize_render_data()
            
            if self.settings.get('debug', False) or not minfy.minfy_flag():
                if 'custom_less' not in self._render_data:
                    self._render_data['custom_less'] = []
                if not self.is_absolute(name):
                    name = self.static_url(''.join(('css/', name, '.css')), include_version=True)
                
                return self._render_data['custom_less'].append( ''.join(('<link href="', name, '" type="text/css" rel="stylesheet" />')) )
            
            if 'custom_css' not in self._render_data:
                self._render_data['custom_css'] = []
            if self.is_absolute(name):
                return self._render_data['custom_css'].append( name )
            return self._render_data['custom_css'].append( ''.join(('css/', name, '.min.css')) )


        def add_js(self, name):
            self.initialize_render_data()
            
            if 'custom_js' not in self._render_data:
                self._render_data['custom_js'] = []
            
            if self.is_absolute(name):
                return self._render_data['custom_js'].append( name )
            
            if self.settings.get('debug', False) or not minfy.minfy_flag():
                return self._render_data['custom_js'].append( ''.join(("js/", name, '.js')) )
            
            return self._render_data['custom_js'].append( ''.join(("js/", name, '.min.js')) )


        def put_render(self, template_name, **kwargs):
            
            """根据之前添加的数据渲染模板。
            
            :param template_name: 模板名.
            """
            if not hasattr(self, '_render_data'):
                self.render(template_name, **kwargs)
            else:
                if 'custom_css' in self._render_data:
                    if not hasattr(self, '_active_modules'):
                        self._active_modules = collections.OrderedDict()
                    self._active_modules['AutoCss'] = ui_modules.AutoCss(self)
                    #self.make_static_url_of_files(self._render_data['custom_css'])
                if 'custom_js' in self._render_data:
                    if not hasattr(self, '_active_modules'):
                        self._active_modules = collections.OrderedDict()
                    self._active_modules['AutoJs'] = ui_modules.AutoJs(self)
                    #self.make_static_url_of_files(self._render_data['custom_js'])
                if 'custom_less' in self._render_data:
                    if not hasattr(self, '_active_modules'):
                        self._active_modules = collections.OrderedDict()
                    self._active_modules['AutoLess'] = ui_modules.AutoLess(self)
                    #self.make_static_url_of_files(self._render_data['custom_js'])
                self._render_data.update(kwargs)
                self._render_data['__keys__'] = self._render_data.keys()
                self.render(template_name, **(self._render_data))


        @tornado.web.authenticated
        def authenticate(self):
            
            """调用进行登录验证装饰器的虚方法
            """
            
            pass


        def on_finish_c(self):
            
            """由用户自定义的结束方法钩子
            """
            
            pass


        def on_finish(self):
            
            """提供数据自动保存服务等
            """
            
            self.on_finish_c()
            
            if hasattr(self, '_wait_to_save_data'):
                for line in self._wait_to_save_data:
                    line.save()

        @staticmethod
        def is_absolute(path):
            return any(path.startswith(x) for x in ["/", "http:", "https:"])


    if 'api_handlers' in kwargs:
        setattr(_base_handler, '_api_handlers', kwargs['api_handlers'])
    if 'authless_handlers' in kwargs:
        setattr(_base_handler, '_authless_handlers', kwargs['authless_handlers'])
    
    if 'public_js' in kwargs:
        def add_public_js(self):
            for line in kwargs['public_js']:
                self.add_js(line)
        setattr(_base_handler, 'add_public_js', add_public_js)
    
    if 'public_css' in kwargs:
        def add_public_css(self):
            for line in kwargs['public_css']:
                self.add_css(line)
        setattr(_base_handler, 'add_public_css', add_public_css)
    
    if 'public_less' in kwargs:
        def add_public_less(self):
            for line in kwargs['public_less']:
                self.add_less(line)
        setattr(_base_handler, 'add_public_less', add_public_less)
    
    if 'current_user_handler' in kwargs:
        setattr(_base_handler, 'get_current_user', kwargs['current_user_handler'])

    return _base_handler