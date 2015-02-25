#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read().replace('.. :changelog:', '')

requirements = [
    'wheel==0.23.0',
    'lazy==1.2',
    'pycountry==1.3',
    'django-cities',
    'cookiecutter',
    'django-vanilla-views',
    'model_mommy',
    'django_webtest',
    'django-bootstrap3',
    'gunicorn==18.0',
]


test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='dr-django-tools',
    version='0.1.0',
    description="David Renne and Rocky Burt's Collaboration of scripts and tools used to build nice web apps",
    long_description=readme + '\n\n' + history,
    author="David Renne",
    author_email='davidrenne@gmail.com',
    url='https://github.com/davidrenne/dr-django-tools',
    packages=[
        'dr_django_tools',
        'dr_django_tools.shared',
        'dr_django_tools.shared.commondata',
        'dr_django_tools.shared.django',
    ],
    package_dir={'dr-django-tools':
                 'dr_django_tools'},
    include_package_data=True,
    install_requires=requirements,
    license="BSD",
    zip_safe=False,
    keywords='dr-django-tools',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
