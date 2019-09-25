#!/usr/bin/env python
import sys
if ((sys.version_info[0] < 3) or
    (sys.version_info[0] == 3 and sys.version_info[1] < 5)):
    print('rpy2 is no longer supporting Python < 3.'
          'Consider using an older rpy2 release when using an '
          'older Python release.')
    sys.exit(1)

import enum
import os
import shutil
import subprocess
import tempfile
import utils
import warnings

from distutils.ccompiler import new_compiler
from distutils.sysconfig import customize_compiler
from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError

from rpy2 import situation

from setuptools import setup

PACKAGE_NAME = 'rpy2'
pack_version = __import__('rpy2').__version__

package_prefix='.'

R_MIN_VERSION = (3, 3)

def _format_version(x):
    return '.'.join(map(str, x))

    
def _get_r_home(r_bin = 'R'):
    
    if (os.getenv('R_ENVIRON') is not None) or (os.getenv('R_ENVIRON_USER') is not None):
        warnings.warn('The environment variable R_ENVIRON or R_ENVIRON_USER is set.'
                      ' Differences between their settings during build time and run'
                      ' time may lead to issues when using rpy2.')

    try:
        r_home = subprocess.check_output((r_bin, "RHOME"),
                                         universal_newlines=True)
    except:
        msg = "Error: Tried to guess R's HOME but no command '%s' in the PATH." % r_bin
        print(msg)
        sys.exit(1)

    r_home = r_home.split(os.linesep)

    #Twist if 'R RHOME' spits out a warning
    if r_home[0].startswith("WARNING"):
        warnings.warn("R emitting a warning: %s" % r_home[0])
        r_home = r_home[1].rstrip()
    else:
        r_home = r_home[0].rstrip()

    if os.path.exists(os.path.join(r_home, 'Renviron.site')):
        warnings.warn("The optional file '%s' is defined. Modifying it between "
                      "build time and run time may lead to issues when using rpy2." %
                      os.path.join(r_home, 'Renviron.site'))

    return r_home


def cmp_version(x, y):
    if (x[0] < y[0]):
        return -1
    if (x[0] > y[0]):
        return 1
    if (x[0] == y[0]):
        if len(x) == 1 or len(y) == 1:
            return 0
        return cmp_version(x[1:], y[1:])


class COMPILATION_STATUS(enum.Enum):
    COMPILE_ERROR=('unable to compile R C extensions - missing headers '
                   'or R not compiled as a library ?')
    NO_COMPILER=('unable to compile sqlite3 C extensions - '
                 'no c compiler?')
    PLATFORM_ERROR=('unable to compile R C extensions - platform error')
    OK = None


def get_c_extension_status(libraries=['R'], include_dirs=None,
                           library_dirs=None):
    c_code = ('#include <Rinterface.h>\n\n'
              'int main(int argc, char **argv) { return 0; }')
    tmp_dir = tempfile.mkdtemp(prefix='tmp_pw_r_')
    bin_file = os.path.join(tmp_dir, 'test_pw_r')
    src_file = bin_file + '.c'
    with open(src_file, 'w') as fh:
        fh.write(c_code)

    compiler = new_compiler()
    customize_compiler(compiler)
    try:
        compiler.link_executable(
            compiler.compile([src_file], output_dir=tmp_dir,
                             include_dirs=include_dirs),
            bin_file,
            libraries=libraries,
            library_dirs=library_dirs)
    except CCompilerError:
        status = COMPILATION_STATUS.COMPILE_ERROR
    except DistutilsExecError:
        status = COMPILATION_STATUS.NO_COMPILER        
    except DistutilsPlatformError:
        status = COMPILATION_STATUS.PLATFORM_ERROR
    else:
        status = COMPILATION_STATUS.OK
    shutil.rmtree(tmp_dir)
    return status


def get_r_c_extension_status():
    r_home = situation.get_r_home()
    c_ext = situation.CExtensionOptions()
    c_ext.add_lib(
        *situation.get_r_flags(r_home, '--ldflags')
    )
    c_ext.add_include(
        *situation.get_r_flags(r_home, '--cppflags')
    )
    status = get_c_extension_status(libraries=['R'],
                                    include_dirs=c_ext.include_dirs,
                                    library_dirs=c_ext.library_dirs)
    return status


c_extension_status = get_r_c_extension_status()

cffi_mode = situation.get_cffi_mode()
if cffi_mode == situation.CFFI_MODE.ABI:
    cffi_modules = ['rpy2/_rinterface_cffi_build.py:ffibuilder_abi']
elif cffi_mode == situation.CFFI_MODE.API:
    if c_extension_status != COMPILATION_STATUS.OK:
        print('API mode requested but %s' % c_extension_status.value)
        sys.exit(1)
    cffi_modules = ['rpy2/_rinterface_cffi_build.py:ffibuilder_api']
elif cffi_mode == situation.CFFI_MODE.BOTH:
    if c_extension_status != COMPILATION_STATUS.OK:
        print('API mode requested but %s' % c_extension_status.value)
        sys.exit(1)
    cffi_modules = ['rpy2/_rinterface_cffi_build.py:ffibuilder_abi',
                    'rpy2/_rinterface_cffi_build.py:ffibuilder_api']
else:
    # default interface
    cffi_modules = ['rpy2/_rinterface_cffi_build.py:ffibuilder_abi']    
    
LONG_DESCRIPTION = """
Python interface to the R language.

`rpy2` is running an embedded R, providing access to it from Python 
using R's own C-API through either:

- a high-level interface making R functions an objects just like Python
  functions and providing a seamless conversion to numpy and pandas data 
  structures
- a low-level interface closer to the C-API

It is also providing features for when working with jupyter notebooks or
ipython.
"""

if __name__ == '__main__':
    pack_dir = {pack_name: os.path.join(package_prefix, 'rpy2')}
        
    requires = ['pytest', 'jinja2', 'pytz', 'simplegeneric', 'tzlocal']
    
    setup(
        name=pack_name,
        version=pack_version,
        description='Python interface to the R language (embedded R)',
        long_description=LONG_DESCRIPTION,
        url='https://rpy2.bitbucket.io',
        license='GPLv2+',
        author='Laurent Gautier',
        author_email='lgautier@gmail.com',
        requires=requires,
        install_requires=requires + ['cffi>=1.10.0'],
        setup_requires=['cffi>=1.10.0'],
        cffi_modules=cffi_modules,
        package_dir=pack_dir,
        packages=([pack_name] +
                  ['{pack_name}.{x}'.format(pack_name=pack_name, x=x)
                   for x in ('rlike', 'rinterface_lib', 'robjects',
                             'robjects.lib', 'interactive', 'ipython',
                             'tests',
                             'tests.rinterface', 'tests.rlike',
                             'tests.robjects',
                             'tests.ipython',
                             'tests.robjects.lib')]
        ),
        classifiers = ['Programming Language :: Python',
                       'Programming Language :: Python :: 3',
                       'Programming Language :: Python :: 3.5',
                       'Programming Language :: Python :: 3.6',
                       'Programming Language :: Python :: 3.7',
                       'Programming Language :: Python :: 3.8',
                       ('License :: OSI Approved :: GNU General '
                        'Public License v2 or later (GPLv2+)'),
                       'Intended Audience :: Developers',
                       'Intended Audience :: Science/Research',
                       'Development Status :: 5 - Production/Stable'
        ],
        data_files=[('rpy2/rinterface_lib',
                     ['rpy2/rinterface_lib/R_API.h',
                      'rpy2/rinterface_lib/R_API_eventloop.h'])],
    )

