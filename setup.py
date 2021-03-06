#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re

from os.path import join
from setuptools import setup, find_packages

RE_REQUIREMENT = re.compile(r'^\s*-r\s*(?P<filename>.*)$')


def pip(filename):
    '''Parse pip requirement file and transform it to setuptools requirements'''
    requirements = []
    for line in open(join('requirements', filename)).readlines():
        match = RE_REQUIREMENT.match(line)
        if match:
            requirements.extend(pip(match.group('filename')))
        else:
            requirements.append(line)
    return requirements


def rst(filename):
    '''
    Load rst file and sanitize it for PyPI.
    Remove unsupported github tags:
     - code-block directive
    '''
    content = open(filename).read()
    return re.sub(r'\.\.\s? code-block::\s*(\w|\+)+', '::', content)


long_description = '\n'.join((
    rst('README.rst'),
    rst('CHANGELOG.rst'),
    ''
))

setup(
    name='django-eztables',
    version=__import__('eztables').__version__,
    description=__import__('eztables').__description__,
    long_description=long_description,
    url='https://github.com/noirbizarre/django-eztables',
    download_url='http://pypi.python.org/pypi/django-eztables',
    author='Axel Haustant',
    author_email='noirbizarre+django@gmail.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=pip('install.pip'),
    tests_require=pip('develop.pip'),
    license='LGPL',
    classifiers=[
        "Framework :: Django",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Environment :: Web Environment",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: System :: Software Distribution",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
    ],
)
