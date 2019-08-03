import sys
print('##vso[task.setvariable variable=PyVersion]%s_%s' % (sys.version_info.major, sys.version_info.minor))