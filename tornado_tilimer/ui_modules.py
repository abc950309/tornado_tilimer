import tornado.web

class AutoCss(tornado.web.UIModule):
    def css_files(self):
        return self.handler._render_data['custom_css']

class AutoJs(tornado.web.UIModule):
    def javascript_files(self):
        return self.handler._render_data['custom_js']

class AutoLess(tornado.web.UIModule):    
    def html_head(self):
        return ''.join(self.handler._render_data['custom_less'])
        
    def javascript_files(self):
        if getattr(self.handler, "less_flag", False):
            return "//cdn.bootcss.com/less.js/2.7.1/less.min.js"
    