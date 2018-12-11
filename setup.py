from setuptools import setup, find_packages
import os


here = os.path.abspath(os.path.dirname(__file__))
README = 'SUNET frontend API'
CHANGES = ''
try:
    README = open(os.path.join(here, 'README.rst')).read()
except IOError:
    pass
try:
    CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
except IOError:
    pass

version = '0.0.1'

requires = [
    'flask',
    'simplejson >= 3.6.5',
]


test_requires = [
]

testing_extras = test_requires + [
    'nose==1.2.1',
    'coverage==3.6',
]


setup(
    name='haproxy_status',
    version=version,
    description='SUNET haproxy status page',
    long_description=README + '\n\n' + CHANGES,
    # TODO: add classifiers
    classifiers=[
        # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    ],
    keywords='',
    author='SUNET',
    url='https://github.com/SUNET/haproxy-status',
    license='BSD',
    packages=find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    tests_require=test_requires,
    extras_require={
        'testing': testing_extras,
    },
    test_suite='haproxy_status',
    entry_points={
        },
)
