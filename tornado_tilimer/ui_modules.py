import tornado.web

class AutoCss(tornado.web.UIModule):
    def css_files(self):
        return self.handler._render_data['custom_css']

class AutoJs(tornado.web.UIModule):
    def javascript_files(selfe):
        return self.handler._render_data['custom_js']
