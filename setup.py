from setuptools import setup, find_packages

setup(
      name             = 'pbs3',
      version          = '3.0.2',
      description      = 'pbs3 is a python package for launching external processes easily.',
      license          = 'MIT',
      url              = 'http://github.com/xapple/pbs3/',
      author           = 'Lucas Sinclair',
      author_email     = 'lucas.sinclair@me.com',
      packages         = find_packages(),
      #long_description = open('README.md').read(),
      #long_description_content_type = 'text/markdown',
      include_package_data = True,
)
