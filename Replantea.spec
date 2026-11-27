# Compilar en Windows con: python -m PyInstaller --noconfirm --clean Replantea.spec
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
root=Path(SPECPATH)
from marca import icon_image
icon_path=root/'replantea.ico'
icon_image(256).save(icon_path,format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
datas=[];binaries=[];hiddenimports=[]
for name in ('ezdwg','ezdxf'):
    da,bi,hi=collect_all(name)
    datas+=da;binaries+=bi;hiddenimports+=hi
datas.append((str(root/'fixtures'/'synthetic.dwg'),'fixtures'))
a=Analysis([str(root/'launcher.py')],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Replantea',icon=str(icon_path),debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False,argv_emulation=False,target_arch=None,codesign_identity=None,entitlements_file=None)
