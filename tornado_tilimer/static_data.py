import os

def get_data(filename):
    with open(filename, mode = 'r', encoding = 'utf-8') as f:
        return json.load(f.read().decode())

def write_data(filename, data):
    with open(filename, mode = 'w', encoding = 'utf-8') as f:
        return f.write(json.dumps(demoDictList, indent = 4))
