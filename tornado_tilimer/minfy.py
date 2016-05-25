import hashlib
from autoclave import db
import autoclave.file_tools as file_tools
import autoclave.models as models
from autoclave.js_tools import jsmin
from csscompressor import compress
import os.path
import os

def _md5_for_file(f, block_size=2**20):
    md5 = hashlib.md5()
    while True:
        data = f.read(block_size)
        if not data:
            break
        md5.update(data)
    return md5.hexdigest()

def md5_for_file(fname):
    with open(fname, 'rb') as f:
        return _md5_for_file(f)

def write_file_json(dict):
    """为静态文件随变化压缩提供记录方式
    """

def get_file_json():
    """为静态文件随变化压缩提供提取方式
    """

def minfy_static_files(type, dealer):
    raw_list = os.listdir( os.path.join( os.path.dirname(__file__), "static", type))
    list = []
    for line in raw_list:
        if os.path.isdir( os.path.join( os.path.dirname(__file__), "static", type, line ) ):
            continue
        if ".min." in line:
            continue
        file = ".".join(line.split(".")[0:-1])
        path = os.path.join( os.path.dirname(__file__), "static", type, line )
        
        if not db.datas_meta.find_one({
                "name": type + "_minfy",
                "file": file,
                "hash": file_tools.md5_for_file( path ),
            }):
            
            print(("minfy " + type + " file " + file).title())
            
            minfy_path = os.path.join( os.path.dirname(__file__), "static", type, file + ".min." + type )
            
            with open(path, "r", encoding = "utf-8") as input_f:
                minfy_file = dealer(input_f.read())
            with open(minfy_path, "w", encoding = "utf-8") as output_f:
                output_f.write(minfy_file)
            
            db.datas_meta.update(
                {
                    "name": type + "_minfy",
                    "file": file,
                },
                {
                    "$set": {
                        "hash": file_tools.md5_for_file( path )
                    }
                },
                upsert = True
            )


minfy_static_files("js", jsmin)
minfy_static_files("css", compress)
