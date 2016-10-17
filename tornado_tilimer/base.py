import tornado.web
import tornado.concurrent
import tornado_tilimer.struct as struct
import tornado_tilimer.ui_modules as ui_modules
import tornado_tilimer.minfy as minfy
import tornado_tilimer as init

from concurrent.futures import ThreadPoolExecutor

import collections
import os.path
import time

try:
    from config import *
except:
    from tornado_tilimer.default_config import *

DataException = struct.DataException

def get_args(needed = None, optional = None, n = None, o = None, body_only = False):
    
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
    
    if body_only:
        _argument = tornado.web.RequestHandler.get_body_argument
    else:
        _argument = tornado.web.RequestHandler.get_argument
    
    def _deco(func):
        def __deco(self, *args, **kwargs):
            arguments = {}
            if needed:
                for line in needed:
                    arguments[line] = _argument(self, line, None)
                    if not arguments[line] or len(arguments[line]) == 0:
                        return self.show_exception(-1, '您没有填写必要的信息')
            
            if optional:
                for line in optional:
                    temp_argument = _argument(self, line, None)
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
            cls._instance = ThreadPoolExecutor(max_workers=50)
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

        def show_exception(self, *args, header = None, url = None):
            if not isinstance(args[0], DataException):
                e = DataException(*args)
            else:
                e = args[0]
            
            if self._finished:
                raise RuntimeError("Cannot write() after finish()")
            
            if not (self.ajax_flag or self.api_flag):
                url = [(url or self.request.headers.get("Referer", '/'))]
                
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
                self.finish()

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
                return self.set_secure_cookie("token", self.session_id, expires = int(time.time()) + EXPIRED_TIME)
            else:
                return self.set_cookie("token", self.session_id, expires = int(time.time()) + EXPIRED_TIME)

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
                self._wait_to_save_data = set()
                self._wait_to_save_id = set()
            
            try:
                if data.id not in self._wait_to_save_id:
                    self._wait_to_save_data.add(data)
                    self._wait_to_save_id.add(data.id)
            except Exception as e:
                if self.setting.get('debug', False):
                    raise e
        
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
            
            return self._render_data['custom_css'].append( ''.join(("less/", name, '.min.css')) )


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


        @authenticated
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
            
            return self.on_finish_c()
            return self.on_finish_save()

        @tornado.gen.coroutine
        def _execute(self, transforms, *args, **kwargs):
            """Executes this request with the given output transforms."""
            self._transforms = transforms
            try:
                if self.request.method not in self.SUPPORTED_METHODS:
                    raise HTTPError(405)
                self.path_args = [self.decode_argument(arg) for arg in args]
                self.path_kwargs = dict((k, self.decode_argument(v, name=k))
                                        for (k, v) in kwargs.items())
                # If XSRF cookies are turned on, reject form submissions without
                # the proper cookie
                if self.request.method not in ("GET", "HEAD", "OPTIONS") and \
                        self.application.settings.get("xsrf_cookies"):
                    self.check_xsrf_cookie()

                result = self.prepare()
                if result is not None:
                    result = yield result
                if self._prepared_future is not None:
                    # Tell the Application we've finished with prepare()
                    # and are ready for the body to arrive.
                    self._prepared_future.set_result(None)
                if self._finished:
                    return

                if tornado.web._has_stream_request_body(self.__class__):
                    # In streaming mode request.body is a Future that signals
                    # the body has been completely received.  The Future has no
                    # result; the data has been passed to self.data_received
                    # instead.
                    try:
                        yield self.request.body
                    except iostream.StreamClosedError:
                        return

                method = getattr(self, self.request.method.lower())
                result = method(*self.path_args, **self.path_kwargs)
                if result is not None:
                    result = yield result
                if self._auto_finish and not self._finished:
                    self.finish()
            except Exception as e:
                try:
                    self._handle_request_exception(e)
                except Exception:
                    app_log.error("Exception in exception handler", exc_info=True)
                if (self._prepared_future is not None and
                        not self._prepared_future.done()):
                    # In case we failed before setting _prepared_future, do it
                    # now (to unblock the HTTP server).  Note that this is not
                    # in a finally block to avoid GC issues prior to Python 3.4.
                    self._prepared_future.set_result(None)

            result = self.on_finish_save()
            if result is not None:
                result = yield result

        @tornado.gen.coroutine
        def on_finish_save(self):
            if hasattr(self, '_wait_to_save_data'):
                for line in self._wait_to_save_data:
                    try:
                        res = yield self.run_on_executor(line.save)
                    except:
                        print(line)

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

import functools
import urllib.parse

def authenticated(method):
    """Decorate methods with this to require that the user be logged in.

    If the user is not logged in, they will be redirected to the configured
    `login url <RequestHandler.get_login_url>`.

    If you configure a login url with a query parameter, Tornado will
    assume you know what you're doing and use it as-is.  If not, it
    will add a `next` parameter so the login page knows where to send
    you once you're logged in.
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            if self.request.method in ("GET", "HEAD"):
                url = self.get_login_url()
                if "?" not in url:
                    if urllib.parse.urlsplit(url).scheme:
                        # if login url is absolute, make next absolute too
                        next_url = self.request.full_url()
                    else:
                        next_url = self.request.uri
                    url += "?" + urllib.parse.urlencode(dict(next=next_url, errno=-1, dscp='您需要登录才能访问这个页面'))
                self.redirect(url)
                return
            raise HTTPError(403)
        return method(self, *args, **kwargs)
    return wrapper