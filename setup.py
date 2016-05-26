#!/usr/bin/env python

from distutils.core import setup

setup(name='tornado_tilimer',
      version='0.10',
      description='A Tornado Utils Package',
      author='Samuel Cui',
      author_email='i@samcui.com',
      url='http://samcui.com/',
      packages=['tornado_tilimer'],
      requires=['tornado', 'csscompressor']
     )