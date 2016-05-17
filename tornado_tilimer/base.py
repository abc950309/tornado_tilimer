import tornado.web
import tornado_tilimer.struct as struct

_db = None

def get_arg_by_list(needed = None, optional = None):
    
    """目的为获取参数的装饰器
    
    :param list needed: 必须参数.
    :param list optional: 可选参数.
    """
    
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
                    arguments[line] = self.get_argument(line, None)
                    if arguments[line] and len(arguments[line]) == 0:
                        arguments[line] = None
            
            kwargs.update(arguments)
            return func(self, *args, **kwargs)
        return __deco
    return _deco


def base_handler(db, template_namespace, api_handlers = None, authless_handlers = None):
    global _db
    _db = db
    
    """通过这个函数获得 BaseHandler.
    
    :param pymongo.collection.Collection db: APP 使用的 MongoDB Collection.
    :param dict template_namespace: 附加到 template 的 namespace 中的属性.
    """
    
    class _base_handler(tornado.web.RequestHandler):
        
        """Base Handler，提供基本服务。
        添加了Session和验证处理。
        """
        
        global caches
        _db = db
        _template_namespace = template_namespace
        _api_handlers = api_handlers
        _authless_handlers = authless_handlers
        
        error_write = lambda self, error_name: (
            self._error_write(error_name) or self.finish()
        )


        @property
        def class_name(self):
        
            """获取 Class Name, 方便根据 Class Name 进行辨别.
            """
            
            return self.__class__.__name__
        
        
        def __init__(self, *args, **kwargs):
            
            """替代原 __init__ 函数.
            """
            
            super().__init__(*args, **kwargs)
            self.ui.update(self._template_namespace)
            self.ui['class_name'] = self.class_name


        def new_session(self):
        
            """获取新的 session。
            """
            
            self.session = struct.DataSession.new()
            self.session_id = self.session._id
            

        def fresh_current_user(self, uid = None):
            if uid and uid != 0:
                models.User.get4id(uid, fresh = True)
            else:
                self._current_user = self.get_current_user(fresh = True)


        def fresh_session(self):
            session = _db.sessions.find_one({"_id": self.session_id})
            
            if not session:
                self.session_id = self.new_session()
                self.fresh_session()
            else:
                self.session = caches['sessions'][self.session_id] = models.Session(session)


        def change_session(self, list):
            _db.sessions.update_one(
                {"_id": self.session_id},
                {
                    "$set": list,
                    "$currentDate": {"lastModified": True}
                }
            )
            self.fresh_session()


        def fresh_all(self):
            self.fresh_session()
            self.fresh_current_user()


        def get_session_id(self):
        
            """获取 session_id.
            """
        
            session_id = self.get_argument('token', None)
            if not session_id:
                session_id = self.get_secure_cookie("token")
            return session_id


        def get_session(self):
            
            """获取 session.
            """
            
            session_id = self.get_session_id()
            
            if not session_id:
                if api_handlers and self.class_name in api_handlers:
                    raise tornado.web.HTTPError(400)
                self.session_id = self.new_session()
                set_session()
            else:
                self.session_id = session_id.decode()
            
            if self.session_id in caches['sessions']:
                #print("Get From Cache sessions")
                self.session = caches['sessions'][self.session_id]
            else:
                #print("Not Get From Cache sessions")
                self.fresh_session()


        def mobile_checker(self):
            if self.request.headers['User-Agent'].find("Mobile") != -1 :
                self.mobile_flag = True
            else:
                self.mobile_flag = False


        def ajax_checker(self):
            try:
                self.ajax_flag = self.get_argument('ajax_flag')
            except:
                self.ajax_flag = None


        def prepare(self):
        
            self.session_id = None
            self.session = None
            self.render_data = {}
            
            self.add_css("mine")
            self.add_js("mine")
            
            self.get_session()
            self.ajax_checker()
            self.mobile_checker()
            
            self.prepare_c()
            
            if self.get_login_url() not in self.request.uri:
                self.authenticate()


        def add_render(self, name, val):
            self.render_data[name] = val


        def put_render(self, template_name, **kwargs):
            self.render_data.update(kwargs)
            self.render_data['__keys__'] = self.render_data.keys()
            self.render(template_name, **(self.render_data))


        def get_current_user(self, fresh = False):
            return models.User.get4id(self.session.uid, fresh)


        @tornado.web.authenticated
        def authenticate(self):
            pass


        def prepare_c(self):
            pass


        def on_finish_c(self):
            pass


        def on_finish(self):
            self.on_finish_c()
            
            if hasattr(self, '_current_user') and getattr(self, '_current_user'):
                self.current_user.access_time = time.time()
            if hasattr(self, 'session') and getattr(self, 'session'):
                self.session.access_time = time.time()
            caches['counter'] += 1
            
            if caches['counter'] >= CACHES_COUNTER_LIMIT:
                clear_users_caches(caches)
                clear_sessions_caches(caches)


        def _error_write(self, error_name):
            if self.ajax_flag:
                self.write({
                    "status": ERROR_CODES[error_name]['code'],
                    "dscp": ERROR_CODES[error_name]['dscp'],
                })
            else:
                return self.redirect("/" + self.class_name.replace("Handler", "") + "?show_type=danger&show_text=" + ERROR_CODES[error_name]['dscp'])
        
        def add_js(self, name):
            if 'custom_js' not in self.render_data:
                self.render_data['custom_js'] = []
            
            if self.settings.get('debug'):
                self.render_data['custom_js'].append( "js/" + name + '.js' )
                return
            
            return self.render_data['custom_js'].append( "js/" + name + '.min.js' )

        def add_css(self, name):
            if 'custom_css' not in self.render_data:
                self.render_data['custom_css'] = []
            
            if self.settings.get('debug'):
                self.render_data['custom_css'].append( "css/" + name + '.css' )
                return
            
            return self.render_data['custom_css'].append( "css/" + name + '.min.css' )
    
    return _base_handler