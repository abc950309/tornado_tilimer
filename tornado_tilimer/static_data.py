import os
import json

def get_data(filename):
    try:
        with open(filename, mode = 'r', encoding = 'utf-8') as f:
            return json.load(f)
    except:
        return None

def write_data(filename, data):
    with open(filename, mode = 'w', encoding = 'utf-8') as f:
        return f.write(json.dumps(data, indent = 4))
