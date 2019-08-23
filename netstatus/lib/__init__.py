from . import *
# carrega todos os arquivos, incluindo os de switch, de forma dinâmica, para o switchfactory
import pkgutil 
__path__ = pkgutil.extend_path(__path__, __name__)
for importer, modname, ispkg in pkgutil.walk_packages(path=__path__, prefix=__name__+'.'):
    __import__(modname)

#from .switch.Switch import *
#from .switch.Switch3Com import *
#from .switch.SwitchHH3C import *
#from .switch.SwitchDLINK import *
#from .switch.SwitchHuawei import *
