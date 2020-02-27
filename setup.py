#!/usr/bin/env python3

from distutils.core import setup
import setuptools

setup(name='pyneedle',
      version='0.2',
      description='Quick search utility allowing the use of multiple serach engines (tracker or recoll)',
      author='Alejandro Perez',
      author_email='alejandro.perez.mendez@gmail.com',
      url='https://bitbucket.org/aperezmendez/pyneedle',
      packages=['pyneedle'],
      package_dir={'pyneedle': 'pyneedle/'},
      entry_points={'gui_scripts': ['pyneedle = pyneedle.pyneedle:main']},
      data_files=[
            ('share/pyneedle', ['README.md']),
            ('share/applications', ['pyneedle.desktop']),
      ],
)
