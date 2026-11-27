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
            target_doc=ezdxf.readfile(target)
            assert len(list(target_doc.modelspace().query('DIMENSION[layer=="RP_RADIOS"]')))==1
            assert len(list(target_doc.modelspace().query('DIMENSION[layer=="RP_ANGULOS"]')))==1
            assert len(list(target_doc.modelspace().query('MULTILEADER[layer=="RP_TANGENTES"]')))==2
            angle=next(iter(target_doc.modelspace().query('DIMENSION[layer=="RP_ANGULOS"]')))
            angle_style=target_doc.dimstyles.get(angle.dxf.dimstyle)
            assert angle_style.dxf.dimexe==1.25 and angle_style.dxf.dimexo==.625 and angle_style.dxf.dimasz==.75
            assert angle.override().get('dimblk1')=='ARCHTICK' and angle.override().get('dimblk2')=='ARCHTICK'
            for leader in target_doc.modelspace().query('MULTILEADER[layer=="RP_TANGENTES"]'):
                assert leader.dxf.leader_extend_to_text==1 and leader.dxf.has_dogleg==1 and leader.dxf.has_landing==1
                assert leader.dxf.text_left_attachment_type==6 and leader.dxf.text_right_attachment_type==6
                assert leader.dxf.dogleg_length==.5 and leader.context.landing_gap_size==.5 and leader.context.char_height==1.5
                assert target_doc.entitydb[leader.dxf.arrow_head_handle].dxf.name=='_NONE'
        from formato_cad import LAYERS,DISTANCE_LAYER
        for entity in reread.modelspace():
            if entity.dxf.layer in LAYERS:
                assert entity.dxf.color==256 and not entity.dxf.hasattr('true_color')
                assert reread.layers.get(entity.dxf.layer).rgb==LAYERS[entity.dxf.layer]
        assert list(reread.modelspace().query(f'MTEXT[layer=="{DISTANCE_LAYER}"]'))
        for label in reread.modelspace().query('MTEXT[layer=="RP_VERTICES_TXT"]'):
            assert label.dxf.char_height==1.75 and label.dxf.width==1.75
            assert abs(label.dxf.line_spacing_factor*1.75*5/3-2.9167)<1e-8
        assert not list(reread.modelspace().query('LINE[layer=="RP_CENTROS"]'))
        assert len(list(reread.modelspace().query('LINE[layer=="RP_TRANSICIONES"]')))==1
        for entity in reread.modelspace().query('TEXT'):
            if entity.dxf.layer.startswith('RP_'):assert entity.dxf.style=='ARIAL'
        tables=list(reread.modelspace().query('TEXT[layer=="RP_TABLAS"]'))
        assert tables and all(t.dxf.height==2 and t.dxf.halign==1 and t.dxf.valign==2 for t in tables)
        assert all(t.dxf.color==256 and reread.layers.get(t.dxf.layer).rgb==(0,0,0) for t in tables)
        axes[0].roundabout=True
        marked=Result(axes,w)
        assert not marked.vertices and len(marked.curves)==1 and len(marked.groups['TANGENTES'])==2
        marked_path,_=export(d,marked,temp/'glorieta')
        marked_doc=ezdxf.readfile(marked_path)
        assert not marked_doc.audit().errors
        assert not list(marked_doc.modelspace().query('LINE[layer=="RP_RADIOS"]'))
        assert not list(marked_doc.modelspace().query('DIMENSION[layer=="RP_ANGULOS"]'))
        assert not list(marked_doc.modelspace().query('MULTILEADER[layer=="RP_TANGENTES"]'))
        center_label=next(iter(marked_doc.modelspace().query('MTEXT[layer=="RP_CENTROS_TXT"]')))
        assert center_label.dxf.char_height==1.75 and center_label.dxf.bg_fill_true_color==0xFFFFFF
        assert center_label.dxf.box_fill_scale==1.0001 and center_label.dxf.color==256
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
                app.centers.set(True);app.draw();root.update()
                center_items=[item for item,key in app.text_items.items() if key.startswith('C')]
                assert center_items and app.canvas.itemcget(center_items[0],'fill')=='#0000fa'
                assert not app.issues_visible and not app.issues_panel.winfo_ismapped()
                saved_log=app.log.get('1.0','end')
                app.toggle_issues();root.update()
                assert app.issues_visible and app.issues_panel.winfo_ismapped()
                app.toggle_issues();root.update()
                assert not app.issues_visible and not app.issues_panel.winfo_ismapped()
                assert app.log.get('1.0','end')==saved_log
                assert root._replantea_icons and app.brand_icon
                from splash import Splash
                delivered=[]
                preview=Splash(root,lambda:delivered.append(True))
                preview.tick();root.update()
                assert preview.photo is not None
                preview.start-=13;preview.tick();root.update()
                assert preview.done and delivered==[True] and not preview.window.winfo_exists()
                preview.finish();assert delivered==[True]
                # Comprobar también el acceso anticipado antes de terminar la introducción.
                preview=Splash(root,lambda:delivered.append(True));preview.skip.invoke();root.update()
                assert preview.done and len(delivered)==2 and preview.job is None
                from PIL import ImageGrab
                root.geometry(f'{min(1380,root.winfo_screenwidth()-30)}x{min(850,root.winfo_screenheight()-80)}+10+10')
                root.update()
                ImageGrab.grab().save('ui-preview.png')
                if require_frozen and sys.platform=='win32':
                    import ctypes
                    assert ctypes.windll.shell32.ExtractIconExW(sys.executable,-1,None,None,0)>0
                gui_ok=True
            finally:root.destroy()
        return dict(frozen=bool(getattr(sys,'frozen',False)),dxf_reader='ok',dwg_reader='ok',export='ok',gui=gui_ok,axis_order='ok',drag_reorder='ok' if gui_ok else 'not_run',direction_arrow='ok' if gui_ok else 'not_run',transition_marks='ok',scale_profiles='ok',radial_dimensions='ok',roundabouts='ok',roundabout_controls='ok' if gui_ok else 'not_run',coordinate_tables='ok',layer_colors='ok',vertex_distances='ok',pk_alignment='ok',startup_animation='ok' if gui_ok else 'not_run',issues_panel='ok' if gui_ok else 'not_run',app_icon='ok' if gui_ok else 'not_run',center_mtext='ok',angular_dimensions='ok',tangent_multileaders='ok',ezdxf=ezdxf.__version__,summary=summary)
