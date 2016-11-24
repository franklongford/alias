# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='ALIAS',
    version='0.0.1',
    description='Analysis tools for simulations of air-liquid interfaces ',
    long_description=readme,
    author='Frank Longford',
    author_email='f.g.j.longford@soton.ac.uk',
    url='https://github.com/franklongford/alias',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)

