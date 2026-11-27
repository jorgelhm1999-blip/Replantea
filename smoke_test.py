"""Prueba de distribución con geometría sintética, sin planos de proyectos."""
from pathlib import Path
import tempfile,sys,math,json,re

def run(gui=False,require_frozen=False):
    import ezdwg,ezdxf
    from motor import load,Result,export,dist,Axis,Segment,PROFILES
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
        for scale in PROFILES:
            target,_=export(d,result,temp/scale.replace(':','_'),scale=scale)
            assert len(list(ezdxf.readfile(target).modelspace().query('DIMENSION')))==1
        assert not list(reread.modelspace().query('LINE[layer=="RP_CENTROS"]'))
        assert len(list(reread.modelspace().query('LINE[layer=="RP_TRANSICIONES"]')))==1
        for entity in reread.modelspace().query('TEXT'):
            if entity.dxf.layer.startswith('RP_'):assert entity.dxf.style=='ARIAL'
        tables=list(reread.modelspace().query('TEXT[layer=="RP_TABLAS"]'))
        assert tables and all(t.dxf.height==2 and t.dxf.halign==1 and t.dxf.valign==2 for t in tables)
        assert all(t.dxf.true_color==(255 if re.fullmatch(r'(V|TE|TS|C)\d+',t.dxf.text) else 0) for t in tables)
        axes[0].roundabout=True
        marked=Result(axes,w)
        assert not marked.vertices and len(marked.curves)==1 and len(marked.groups['TANGENTES'])==2
        marked_path,_=export(d,marked,temp/'glorieta')
        marked_doc=ezdxf.readfile(marked_path)
        assert not marked_doc.audit().errors
        assert not list(marked_doc.modelspace().query('LINE[layer=="RP_RADIOS"]'))
        assert json.loads((temp/'glorieta'/'Ejes.json').read_text())[0]['glorieta']
        axes[0].roundabout=False
        primary=axes[0]
        gui_ok=False
        if gui:
            import tkinter as tk
            from interfaz import App
            root=tk.Tk()
            try:
                root.withdraw();app=App(root);app.doc=d;app.axes=axes;app.warnings=w;app.refresh();app.calculate();root.update_idletasks();root.update()
                assert app.result is not None and len(app.result.curves)==1
                assert app.canvas.find_all()
                other=Axis('ui-second','B','0',[Segment((140,200),(180,200))])
                app.axes.append(other);app.refresh();app.calculate()
                app.tree.selection_set(other.handle);app.tree.focus(other.handle);root.update()
                assert app.canvas.find_withtag('selected_axis')
                arrows=app.canvas.find_withtag('direction_arrow');assert arrows
                coordinates=app.canvas.coords(arrows[0]);assert coordinates[2]>coordinates[0]
                camera=(app.origin,app.scale);app.reorder(-1);root.update()
                assert app.axes[0] is other and app.result.axes[0] is other
                assert app.tree.get_children()[0]==other.handle
                assert app.tree.selection()==(other.handle,)
                assert camera==(app.origin,app.scale)
                assert app.result.vertices[0]['x']==140
                assert app.tree.bind('<Shift-Up>') and app.tree.bind('<Shift-Down>')
                app.drawing_scale.set('1:1000');app.change_profile();root.update()
                assert app.export_scale=='1:1000' and app.profile['vertex_height']==1.75
                app.reverse();assert app.result.vertices[0]['x']==180
                arrow=app.canvas.find_withtag('direction_arrow')[0];coords=app.canvas.coords(arrow);assert coords[2]<coords[0]
                app.reorder(1);assert app.axes[-1] is other
                # Arrastre real por coordenadas del Treeview, con varias filas de distancia.
                from types import SimpleNamespace
                app.axes.extend([Axis('ui-'+str(k),'UI'+str(k),'0',[Segment((200+k*20,200),(210+k*20,200))]) for k in range(3)])
                app.refresh();app.calculate();root.deiconify();root.update()
                app.tree.selection_set('ui-2');app.tree.focus('ui-2');root.update()
                box=app.tree.bbox('ui-2');target=app.tree.bbox(app.axes[0].handle)
                assert box and target
                app.row_press(SimpleNamespace(x=20,y=box[1]+box[3]//2))
                app.row_motion(SimpleNamespace(x=20,y=target[1]+1))
                assert app.row_drag['moved'] and app.row_drag['slot']==0
                app.row_release(SimpleNamespace(x=20,y=target[1]+1));root.update()
                assert app.axes[0].handle=='ui-2' and app.result.axes[0].handle=='ui-2'
                assert app.tree.selection()==('ui-2',) and app.row_drag is None
                assert not app.drop_line.winfo_ismapped()
                assert app.canvas.find_withtag('direction_arrow')
                # Clasificación manual múltiple, reversible, sin perder selección ni cámara.
                handles=[primary.handle,other.handle]
                app.tree.selection_set(handles);camera=(app.origin,app.scale)
                app.set_roundabout(True);root.update()
                assert all(app.axis(h).roundabout for h in handles)
                assert all(app.tree.set(h,'roundabout')=='Sí' for h in handles)
                assert all('B' not in v['ejes'] and primary.name not in v['ejes'] for v in app.result.vertices)
                assert camera==(app.origin,app.scale)
                app.set_roundabout(False);root.update()
                assert all(not app.axis(h).roundabout for h in handles)
                assert any('B' in v['ejes'] for v in app.result.vertices)
                # Doble clic sobre la columna Glorieta, incluso con varias filas seleccionadas.
                box=app.tree.bbox(primary.handle,'roundabout');assert box
                app.edit(SimpleNamespace(x=box[0]+box[2]//2,y=box[1]+box[3]//2));root.update()
                assert primary.roundabout and not other.roundabout
                app.edit(SimpleNamespace(x=box[0]+box[2]//2,y=box[1]+box[3]//2));root.update()
                assert not primary.roundabout
                gui_ok=True
            finally:root.destroy()
        return dict(frozen=bool(getattr(sys,'frozen',False)),dxf_reader='ok',dwg_reader='ok',export='ok',gui=gui_ok,axis_order='ok',drag_reorder='ok' if gui_ok else 'not_run',direction_arrow='ok' if gui_ok else 'not_run',transition_marks='ok',scale_profiles='ok',radial_dimensions='ok',roundabouts='ok',roundabout_controls='ok' if gui_ok else 'not_run',coordinate_tables='ok',ezdxf=ezdxf.__version__,summary=summary)
