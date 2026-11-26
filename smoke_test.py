"""Prueba de distribución con geometría sintética, sin planos de proyectos."""
from pathlib import Path
import tempfile,sys,math,json

def run(gui=False,require_frozen=False):
    import ezdwg,ezdxf
    from motor import load,Result,export,dist
    if require_frozen and not getattr(sys,'frozen',False):raise RuntimeError('La prueba debe ejecutarse dentro del .exe compilado.')
    with tempfile.TemporaryDirectory(prefix='replantea_test_') as temp:
        temp=Path(temp);doc=ezdxf.new('R2010');doc.units=6
        doc.modelspace().add_lwpolyline([(100,200,0),(110,200,math.tan(math.pi/8)),(120,210,0)],format='xyb')
        source=temp/'prueba.dxf';doc.saveas(source)
        d,axes,w=load(source);result=Result(axes,w)
        assert len(axes)==1 and len(result.curves)==1
        assert abs(result.curves[0]['r']-10)<1e-8
        assert dist(result.curves[0]['center'],(110,210))<1e-8
        dest,summary=export(d,result,temp/'salida')
        reread=ezdxf.readfile(dest)
        assert not reread.audit().errors
        assert len(list(reread.modelspace().query('LWPOLYLINE')))==1
        dwg=Path(__file__).parent/'fixtures'/'synthetic.dwg'
        if not dwg.is_file():raise RuntimeError('Falta el DWG sintético para comprobar el lector nativo.')
        d2,a2,w2=load(dwg)
        assert len(a2)==1 and len(a2[0].segments)==2
        rr=Result(a2,w2)
        assert len(rr.curves)==1 and abs(rr.curves[0]['r']-10)<1e-6
        export(d2,rr,temp/'salida_dwg')
        gui_ok=False
        if gui:
            import tkinter as tk
            from interfaz import App
            root=tk.Tk()
            try:
                root.withdraw();app=App(root);app.doc=d;app.axes=axes;app.warnings=w;app.refresh();app.calculate();root.update_idletasks();root.update()
                assert app.result is not None and len(app.result.curves)==1
                assert app.canvas.find_all()
                gui_ok=True
            finally:root.destroy()
        return dict(frozen=bool(getattr(sys,'frozen',False)),dxf_reader='ok',dwg_reader='ok',export='ok',gui=gui_ok,ezdxf=ezdxf.__version__,summary=summary)
