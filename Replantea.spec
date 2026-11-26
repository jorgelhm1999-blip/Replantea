# Compilar en Windows con: python -m PyInstaller --noconfirm --clean Replantea.spec
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
root=Path(SPECPATH)
datas=[];binaries=[];hiddenimports=[]
for name in ('ezdwg','ezdxf'):
    da,bi,hi=collect_all(name)
    datas+=da;binaries+=bi;hiddenimports+=hi
datas.append((str(root/'fixtures'/'synthetic.dwg'),'fixtures'))
a=Analysis([str(root/'launcher.py')],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Replantea',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False,argv_emulation=False,target_arch=None,codesign_identity=None,entitlements_file=None)
