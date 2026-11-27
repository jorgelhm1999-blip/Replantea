"""Punto de entrada para Replantea.exe y su comprobación integrada."""
from pathlib import Path
import argparse,json,logging,os,sys,traceback
VERSION='0.4.0'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--gui-test',action='store_true')
    parser.add_argument('--require-frozen',action='store_true')
    parser.add_argument('--report',default='selftest.json')
    args=parser.parse_args()
    if args.self_test:
        from smoke_test import run
        try:
            result=run(gui=args.gui_test,require_frozen=args.require_frozen)
            result.update(version=VERSION,status='ok')
            Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            return 0
        except Exception:
            Path(args.report).write_text(json.dumps(dict(status='error',traceback=traceback.format_exc()),ensure_ascii=False,indent=2),encoding='utf-8')
            return 1
    from interfaz import App
    import tkinter as tk
    root=tk.Tk();app=App(root);root.title(f'Replantea {VERSION}');root.mainloop()
    return 0

if __name__=='__main__':
    try:
        folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Replantea'
        folder.mkdir(parents=True,exist_ok=True)
        logging.basicConfig(filename=folder/'replantea.log',level=logging.INFO,encoding='utf-8')
        logging.info('Inicio Replantea %s · frozen=%s',VERSION,bool(getattr(sys,'frozen',False)))
        sys.exit(main())
    except Exception:
        error=traceback.format_exc();logging.exception('Fallo de inicio')
        text='Replantea no ha podido iniciarse.\n\n'+str(folder/'replantea.log')+'\n\n'+error[-1200:]
        try:
            import tkinter as tk
            from tkinter import messagebox
            root=tk.Tk();root.withdraw();messagebox.showerror('Replantea',text);root.destroy()
        except Exception:
            if sys.platform=='win32':
                import ctypes
                ctypes.windll.user32.MessageBoxW(0,text,'Replantea',16)
        sys.exit(1)
