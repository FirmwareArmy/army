import army.api
from army.api.debugtools import print_stack
from army.api.dict_file import load_dict_file
from army.api.log import log
from army.api.path import prefix_path
from army.api.schema import Schema, String, VersionString, Optional, PackageString, Array, Dict, VariableDict, Variant, VersionRangeString, Boolean
from army.api.version import Version, VersionRange
import os
import shutil

def find_installed_package(name, version_range="latest", scope=None, exist_ok=False):
    """ search for an installed package
    search is done inside project first and then in user space
    
    :param name package name to search, must be exact name
    :version_range version to match, if a range is given then match the greatest version in range
    :scope local or user, if None if will search in local then in user
    :exist_ok if True then no error is raised when package is not found
    """

    def search_package(path, version_range):
        package_path = os.path.join(os.path.expanduser(path), name)
         
        if os.path.exists(package_path)==False:
            return None
        
        versions = os.listdir(package_path)
        if len(versions)==0:
            return None
                
        version = VersionRange(versions)[str(version_range)]

        if version is None:
            return None

        return os.path.join(package_path, str(version))

    if version_range is None:
        version_range = 'latest'
            
    package = None
    
    # search package in local project
    package_local = None
    path_local = 'dist'
    if scope=='local' or scope is None:
        package_local = search_package(path_local, version_range)

    # search package in user space
    package_user = None
    path_user = prefix_path('~/.army/dist')
    if scope=='user' or scope is None: 
        package_user = search_package(path_user, version_range)

    package = package_local
    if package_local is None:
        package = package_user
    if package_user is not None and package_local is not None:
        if package_user.version>package_local.version:
            package = package_user
        else:
            package = package_local
    
    if package_user is None and package_local is None:
        if exist_ok==True:
            return None
        else:
            raise PackageException(f"{name}@{version_range}: package not installed")

    return package

def load_installed_package(name, version_range="latest", scope='local', exist_ok=False):
    """ search for an installed package
    search is done inside project first and then in user space
    
    :param name package name to search, must be exact name
    :version_range version to match, if a range is given then match the greatest version in range
    :scope local or user
    """

    def search_package(path, version_range):
        package_path = os.path.join(os.path.expanduser(path), name)
         
        if os.path.exists(package_path)==False:
            return None
        
        versions = os.listdir(package_path)
        if len(versions)==0:
            return None
        version = VersionRange(versions)[str(version_range)]

        if version is None:
            return None
    
        try:
            package = _load_installed_package(os.path.join(str(package_path), str(version)))
        except Exception as e:
            print_stack()
            log.error(e)
            raise PackageException(e)
#             log.error(f"{package_path}: not a valid package")
#             return None
        
        # check if package match requested version
        if VersionRange([package.version])[version] is None:
            raise PackageException(f"{os.path.join(package_path, version)}: incorrect package version")
        return package

    if version_range is None:
        version_range = 'latest'
            
    package = None
    
    # search package in local project
    package_local = None
    path_local = 'dist'
    if scope=='local':
        package_local = search_package(path_local, version_range)

    # search package in user space
    package_user = None
    path_user = prefix_path('~/.army/dist')
    if scope=='user': 
        package_user = search_package(path_user, version_range)

    package = package_local
    if package_local is None:
        package = package_user
    if package_user is not None and package_local is not None:
        if package_user.version>package_local.version:
            package = package_user
        else:
            package = package_local
    
    if package_user is None and package_local is None:
        return None

    return package

def load_installed_packages(scope='local', all=False):
    packages = []

    if scope=='local':
        # search package in local project
        path = 'dist'
    else:
        # search package in user space
        path = prefix_path('~/.army/dist')

    if os.path.exists(path)==False:
        return packages

    for package_name in os.listdir(path):
        versions = []
        for version in os.listdir(os.path.join(path, package_name)):
            versions.append(version)
        if all==False:
            # only return latest version
            versions = [VersionRange(versions).max()]
        for version in versions:
            try:
                package = _load_installed_package(os.path.join(str(path), package_name, str(version)))
                packages.append(package)
            except Exception as e:
                print_stack()
                log.error(e)
                raise PackageException(e)
            
    return packages

# TODO check version when loading package and in case of package installed both global and local use the best fit
def load_project_packages(project, target):
    loaded = []
    to_load = []
    for dependency in project.dependencies:
        to_load.append((dependency, project.dependencies[dependency]))

    for dependency in project.target[target].dependencies:
        to_load.append((dependency, project.target[target].dependencies[dependency]))

    dependencies = []
    while len(to_load)>0:
        dependency, version_range = to_load.pop(0)
        if dependency not in loaded:
            installed = load_installed_package(dependency, version_range=version_range)
            if installed is None:
                raise PackageException(f"{dependency}: package not installed")
            dependencies.append(installed)
        
            for subdependency in installed.dependencies:
                to_load.append((subdependency, installed.dependencies[subdependency]))
                
            loaded.append(dependency)
        else:
            log.info(f"{dependency} already loaded, skip")
    return dependencies

def _load_installed_package(path, exist_ok=False):
    content = load_dict_file(path, "army", exist_ok=exist_ok)
    
    project = InstalledPackage(data=content, path=path)
    project.check()

    return project

def find_repository_package(repositories, name, version_range="latest", repository=None, editable=None):
    """ search for a package in repositories
    package with the greatest version in version_range is returned
    
    :param repositories: list of repository to search in
    :param name: name of the package to find
    :param version_range: version range to match, if None then match 'latest'
    :param repository: if not None the limit search to this repository
    :param editable: if True try to find a suitable version with a local dev repository
    """
    
    res_package = None
    res_repo = None
    
    for r in repositories:
        if repository is not None and repository!=r.name:
            continue
        
        res = r.search(name=name, version=version_range, fullname=True)
        if len(res)>0:
            for pkg_name in res:
                for pkg in res[pkg_name]:
                    if editable==True and not r.editable==True:
                        pass
                    if editable==False and not r.editable==False:
                        pass
                    if res_package is None:
                        res_package = pkg
                        res_repo = r
                    elif pkg.version>res_package.version:
                        res_package = pkg
                        res_repo = r
                        
 
    if res_package is not None:
        return res_package, res_repo
 
    return None, None

def parse_package_name(package_name):
    res = {
        'repository': None,
        'name': package_name,
        'version': None
    }
    
    chunks = package_name.split('@')
    if len(chunks)==2:
        try:
            # check chunks[1] is a valid version range
            VersionRange([])[chunks[1]]
            
            res['name'] = chunks[0]
            res['version'] = chunks[1]
        except Exception as e:
            res['repository'] = chunks[0]
            res['name'] = chunks[1]

    elif len(chunks)==3:
        res['repository'] = chunks[0]
        res['name'] = chunks[1]
        res['version'] = chunks[2]

        # check chunks[1] is a valid version range
        VersionRange([])[chunks[1]]

    elif len(chunks)!=1:
        raise PackageException(f"{package_name}: incorrect package name")
    
    return res

class PackageException(Exception):
    def __init__(self, message):
        self.message = message

class Package(Schema):
    def __init__(self, data, schema):
        super(Package, self).__init__(data, schema={
                **schema,
                'name': String(),
                'description': String(),
                'version': VersionString(),
                'dependencies': Optional(VariableDict(PackageString(), VersionRangeString())),
                'plugins': Optional(Array(String())),
#                 'plugin': Optional(VariableDict(PackageString(), Variant())),
                'packaging': Optional(Dict({
                    'include': Optional(Array(String())),
                    'exclude': Optional(Array(String()))
                    })),
                
                'profiles': Optional(Array(String())),
                
#                 # arch definition
#                 'arch': Optional(VariableDict(String(), Dict({
#                     'definition': Optional(String()),
#                     'cpu': Optional(String()),
#                     }))),

#                 # in case of a firmware
#                 'default-target': Optional(String()),
#                 'target': Optional(VariableDict(String(), Dict({
#                     'arch': String(),
#                     'definition': Optional(String()),
#                     'dependencies': Optional(VariableDict(PackageString(), VersionRangeString())),
#                     'plugins': Optional(VariableDict(PackageString(), VersionRangeString())),
#                     'plugin': Optional(VariableDict(PackageString(), Variant())),
#                     }))),
#                 
#                 # in case of a library
#                 'cmake': Optional(Dict({
#                     'include': Optional(String()),
#                     })),

           })
    
    @property
    def name(self):
        return self._data['name']
    
    @property
    def description(self):
        return self._data['description']
    
    @property
    def version(self):
        return Version(self._data['version'])

    @property
    def dependencies(self):
        if 'dependencies' in self._data:
            return self._data['dependencies']
        return {}
    
    @property
    def packaging(self):
        class Packaging(object):
            def __init__(self, data):
                self._data = data
        
            @property
            def include(self):
                if 'include' in self._data:
                    return self._data['include']
                return []
        
            @property
            def exclude(self):
                if 'exclude' in self._data:
                    return self._data['exclude']
                return []

        if 'packaging' in self._data:
            return Packaging(self._data['packaging'])
        return Packaging({})
        
    @property
    def profiles(self):
        if 'profiles' in self._data:
            return self._data['profiles']
        return []

    @property
    def plugins(self):
        if 'plugins' in self._data:
            return self._data['plugins']
        return []
#     @property
#     def arch(self):
#         class ArchDictIterator(object):
#             def __init__(self, values):
#                 self._list = values
#                 self._iter = iter(self._list)
#              
#             def __next__(self):
#                 return next(self._iter)
# 
#         class ArchDict(object):
#             def __init__(self, data):
#                 self._data = data
#                 
#             def __iter__(self):
#                 return ArchDictIterator(self._data)
#             
#             def __getitem__(self, item):
#                 return Arch(self._data[item])
#             
#         class Arch(object):
#             def __init__(self, data):
#                 self._data = data
#             
#             @property
#             def definition(self):
#                 if 'definition' in self._data:
#                     return self._data['definition']
#                 return None
#             
#             @property
#             def cpu(self):
#                 if 'cpu' in self._data:
#                     return self._data['cpu']
#                 return None
#             
#         if 'arch' in self._data:
#             return ArchDict(self._data['arch'])
#         return ArchDict({})

#     @property
#     def plugins(self):
#         if 'plugins' in self._data:
#             return self._data['plugins']
#         return []
#     
#     @property
#     def plugin(self):
#         if 'plugin' in self._data:
#             return self._data['plugin']
#         return []

#     @property
#     def default_target(self):
#         if 'default-target' in self._data:
#             return self._data['default-target']
#         return None
#         
#     @property
#     def target(self):
#         class TargetDictIterator(object):
#             def __init__(self, values):
#                 self._list = values
#                 self._iter = iter(self._list)
#              
#             def __next__(self):
#                 return next(self._iter)
# 
#         class TargetDict(object):
#             def __init__(self, data):
#                 self._data = data
#                 
#             def __iter__(self):
#                 return TargetDictIterator(self._data)
#             
#             def __getitem__(self, item):
#                 return Target(self._data[item])
#             
#         class Target(object):
#             def __init__(self, data):
#                 self._data = data
#             
#             @property
#             def arch(self):
#                 return self._data['arch']
#             
#             @property
#             def definition(self):
#                 if 'definition' in self._data:
#                     return self._data['definition']
#                 return None
# 
#             @property
#             def dependencies(self):
#                 if 'dependencies' in self._data:
#                     return self._data['dependencies']
#                 return []
#         
#             @property
#             def plugins(self):
#                 if 'plugins' in self._data:
#                     return self._data['plugins']
#                 return []
#             
#             @property
#             def plugin(self):
#                 if 'plugin' in self._data:
#                     return self._data['plugin']
#                 return []
# 
#         if 'target' in self._data:
#             return TargetDict(self._data['target'])
#         return TargetDict({})
# 
#     @property
#     def cmake(self):
#         class CMake(object):
#             def __init__(self, data):
#                 self._data = data
#             
#             @property
#             def include(self):
#                 if 'include' in self._data:
#                     return self._data['include']
#                 return None
#         if 'cmake' in self._data:
#             return CMake(self._data['cmake'])
#         return CMake({})
    
    def package(self, output_path):
        """ Packaging command, to be overloaded by package behavior
        """
        pass
    
    def __repr__(self):
        return f"{self.name}@{self.version}"

class InstalledPackage(Package):
    def __init__(self, data, path):
        super(InstalledPackage, self).__init__(data, schema={
                'repository': Variant(),
                'installed_user': Optional(Boolean()),
                'installed_by': Optional(Array(PackageString())),
            })

        self._path = path
        
    @property
    def path(self):
        return self._path

    @property
    def repository(self):
        class Repository(object):
            def __init__(self, data):
                self._data = data
        
            @property
            def name(self):
                return self._data['name']
        
            @property
            def uri(self):
                return self._data['uri']

        return Repository(self._data['repository'])

    def uninstall(self):
        def rmtree_error(func, path, exc_info):
            print(exc_info)
            exit(1)
        if os.path.exists(self._path):
            log.debug(f"rm {self._path}")
            shutil.rmtree(self._path, onerror=rmtree_error)
        
        profiles_path = os.path.normpath(os.path.join(self._path, '..', '..', '..', 'profile')) 
        # remove profiles
        for profile in self.profiles:
            profile_path = os.path.join(profiles_path, f"{profile}@{self.version}.yaml")
            if os.path.exists(profile_path):
                os.remove(profile_path)

    @property
    def installed_user(self):
        if 'installed_user' in self._data:
            return self._data['installed_user']
        return False

    @property
    def installed_by(self):
        if 'installed_by' in self._data:
            return self._data['installed_by']
        return []

    def remove_installed_by(self, package_ref):
        self._data['installed_by'].remove(package_ref)
        