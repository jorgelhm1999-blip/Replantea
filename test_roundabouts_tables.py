"""Regresión de glorietas y formato CAD solicitado (solo geometría sintética)."""
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

import ezdxf
from ezdxf.enums import TextEntityAlignment
from motor import Axis,Segment,Result,export,coordinate_tables,dist,EPS,PROFILES


def ring():
    points=[(10,0),(0,10),(-10,0),(0,-10)]
    return Axis('ring','GLORIETA','0',[Segment(p,points[(i+1)%4],math.tan(math.pi/8)) for i,p in enumerate(points)],closed=True,roundabout=True)


class RoundaboutTests(unittest.TestCase):
    def test_ring_keeps_tangencies_centers_and_curve_numbers_without_vertices(self):
        a=ring();r=Result([a],[])
        self.assertEqual(r.vertices,[])
        self.assertEqual([c['id'] for c in r.curves],[1,2,3,4])
        self.assertEqual(len(r.groups['TANGENTES']),8)
        self.assertEqual(len(r.groups['CENTROS DE CURVAS']),4)
        self.assertTrue(all(c['vertex']=='' for c in r.curves))
        a.reverse();self.assertEqual(Result([a],[]).vertices,[])
        a.roundabout=False
        self.assertEqual(len(Result([a],[]).vertices),4)

    def test_access_intersection_retained_for_both_orders_and_directions(self):
        a=ring();access=Axis('access','ACCESO','0',[Segment((5,-20),(5,20))])
        for reverse in [False,True]:
            if reverse:access.reverse();a.reverse()
            for axes in [[a,access],[access,a]]:
                r=Result(axes,[])
                self.assertEqual(len(r.vertices),4)
                self.assertEqual([v['id'] for v in r.vertices],['V1','V2','V3','V4'])
                self.assertTrue(all(v['ejes']==['ACCESO'] for v in r.vertices))
                self.assertTrue(all(c['vertex']=='' for c in r.curves))
                self.assertEqual(len(r.curves),4)

    def test_separate_open_axes_can_all_be_marked_and_excluded(self):
        a=ring()
        axes=[Axis(str(i),'G'+str(i),'0',[s],roundabout=True) for i,s in enumerate(a.segments)]
        r=Result(axes,[])
        self.assertEqual(r.vertices,[]);self.assertEqual(len(r.curves),4)
        axes[0].selected=False
        r=Result(axes,[])
        self.assertEqual(r.vertices,[]);self.assertEqual(len(r.curves),3)
        axes[0].selected=True;axes[0].roundabout=False
        self.assertEqual(len(Result(axes,[]).vertices),1)  # Solo el PI del arco sin marcar.

    def test_no_parallel_tangent_warning_for_roundabout(self):
        a=Axis('a','G','0',[Segment((1,0),(-1,0),1)],roundabout=True)
        self.assertFalse(Result([a],[]).warnings)
        a.roundabout=False;self.assertTrue(Result([a],[]).warnings)

    def test_export_removes_pi_legs_and_preserves_source_and_deliverables(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=ezdxf.new('R2010');d.units=6
            source=d.modelspace().add_circle((0,0),10)
            a=ring();a.handle=source.dxf.handle;r=Result([a],[])
            out,_=export(d,r,tmp);z=ezdxf.readfile(out)
            self.assertFalse(z.audit().errors)
            self.assertEqual(z.entitydb[source.dxf.handle].dxf.radius,10)
            self.assertEqual(len(list(d.modelspace())),1)
            self.assertFalse(list(z.modelspace().query('TEXT[layer=="RP_VERTICES"]')))
            self.assertFalse(list(z.modelspace().query('LINE[layer=="RP_RADIOS"]')))
            self.assertEqual(len(list(z.modelspace().query('DIMENSION'))),4)
            self.assertTrue(list(z.modelspace().query('TEXT[layer=="RP_PK"]')))
            self.assertEqual(json.loads((Path(tmp)/'Ejes.json').read_text())[0]['glorieta'],True)
            with open(Path(tmp)/'Curvas.csv',encoding='utf-8-sig') as stream:
                rows=list(csv.DictReader(stream,delimiter=';'))
            self.assertEqual(len(rows),4);self.assertTrue(all(row['VERTICE']=='' for row in rows))


class TableTests(unittest.TestCase):
    def test_roundtrip_geometry_alignment_colors_and_stepped_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=ezdxf.new('R2010');d.styles.new('ARIAL',dxfattribs={'font':'arial.ttf'})
            groups={g:[dict(id=label,x=100.123,y=2000.456)] for g,label in [('VÉRTICES','V1'),('CENTROS DE CURVAS','C1'),('TANGENTES','TE1')]}
            coordinate_tables(d.modelspace(),SimpleNamespace(groups=groups),(0,0))
            path=Path(tmp)/'table.dxf';d.saveas(path);z=ezdxf.readfile(path)
            self.assertFalse(z.audit().errors)
            texts=list(z.modelspace().query('TEXT'))
            for t in texts:
                self.assertEqual(t.dxf.height,2)
                self.assertEqual(t.dxf.style,'ARIAL')
                self.assertEqual(t.get_placement()[0],TextEntityAlignment.MIDDLE_CENTER)
                blue=t.dxf.text in ['V1','C1','TE1']
                self.assertEqual(t.dxf.true_color,255 if blue else 0)
                self.assertEqual(t.dxf.color,5 if blue else 7)
            # Tres tablas: vértices izquierda; centros derecha; tangentes debajo de centros.
            for label,x,y in [('V1',0,0),('C1',53.4578,0),('TE1',53.4578,-17)]:
                t=next(e for e in texts if e.dxf.text==label)
                self.assertLess(dist(t.dxf.align_point,(x+5,y-6)),EPS)
                for caption,cx in [('100.123',x+10+9.1366),('2000.456',x+10+19.2289+9.1366)]:
                    self.assertTrue(any(e.dxf.text==caption and dist(e.dxf.align_point,(cx,y-4-2.0211))<EPS for e in texts))
            lines=list(z.modelspace().query('LINE'))
            vertical=[e for e in lines if abs(e.dxf.start.x-e.dxf.end.x)<EPS]
            self.assertEqual(len(vertical),12)
            for x,top,bottom in [(0,-4,-8),(10,0,-8),(29.2289,0,-8),(48.4578,0,-8)]:
                self.assertTrue(any(dist(e.dxf.start,(x,top))<EPS and dist(e.dxf.end,(x,bottom))<EPS for e in vertical))
            for e in lines:self.assertEqual(e.dxf.true_color,0);self.assertEqual(e.dxf.color,7)
            for y in [-4,-8]:
                self.assertTrue(any(dist(e.dxf.start,(0,y))<EPS and dist(e.dxf.end,(48.4578,y))<EPS for e in lines))
            self.assertTrue(any(dist(e.dxf.start,(10,0))<EPS and dist(e.dxf.end,(48.4578,0))<EPS for e in lines))

    def test_fixed_table_dimensions_in_both_scales_and_config(self):
        for scale in PROFILES:
            with self.subTest(scale=scale),tempfile.TemporaryDirectory() as tmp:
                d=ezdxf.new('R2010');a=ring();a.roundabout=False
                out,_=export(d,Result([a],[]),tmp,scale=scale);z=ezdxf.readfile(out)
                for t in z.modelspace().query('TEXT[layer=="RP_TABLAS"]'):self.assertEqual(t.dxf.height,2)
                cfg=json.loads((Path(tmp)/'Configuracion.json').read_text())['tablas']
                self.assertEqual(cfg['column_widths'],[10,19.2289,19.2289])
                self.assertEqual(cfg['row_height'],4)
                self.assertEqual(cfg['coordinate_offset'],[9.1366,2.0211])

    def test_tangent_table_follows_centers_without_overlap(self):
        d=ezdxf.new('R2010');d.styles.new('ARIAL',dxfattribs={'font':'arial.ttf'})
        groups={'VÉRTICES':[], 'CENTROS DE CURVAS':[dict(id='C'+str(i),x=i,y=i) for i in range(100)],'TANGENTES':[dict(id='TE1',x=0,y=0)]}
        coordinate_tables(d.modelspace(),SimpleNamespace(groups=groups),(0,0))
        title=next(t for t in d.modelspace().query('TEXT') if t.dxf.text=='TANGENTES')
        self.assertLess(title.dxf.align_point.y+1,-404)


if __name__=='__main__':unittest.main()
