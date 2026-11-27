import unittest, tempfile, math, json
from pathlib import Path
import ezdxf
from motor import *

class OrderAndStyleTests(unittest.TestCase):
    def test_intersection_numbered_in_traversal(self):
        a=Axis('a','A','0',[Segment((0,0),(100,0))]);b=Axis('b','B','0',[Segment((25,-10),(25,10))])
        r=Result([a,b],[])
        self.assertEqual([(v['id'],v['x'],v['y']) for v in r.vertices[:3]],[('V1',0,0),('V2',25,0),('V3',100,0)])
        self.assertEqual(r.vertices[1]['ejes'],['A','B'])
        r=Result([b,a],[]);self.assertEqual((r.vertices[0]['x'],r.vertices[0]['y']),(25,-10))
        a.reverse();r=Result([a,b],[]);self.assertEqual(r.vertices[0]['x'],100)
    def test_move_axes(self):
        axes=[Axis(c,c,'0',[]) for c in 'abcde']
        move_axes(axes,['c','d'],-1);self.assertEqual(''.join(a.handle for a in axes),'acdbe')
        move_axes(axes,['c','d'],1);self.assertEqual(''.join(a.handle for a in axes),'abcde')
        move_axes(axes,['a','b'],-1);self.assertEqual(''.join(a.handle for a in axes),'abcde')
        move_axes(axes,['a','c'],1);self.assertEqual(''.join(a.handle for a in axes),'badce')
    def test_pk(self):
        for value,expected in [(0,'0+000.000'),(10,'0+010.000'),(1234.567,'1+234.567'),(999.9996,'1+000.000'),(-20,'-0+020.000')]:self.assertEqual(format_pk(value),expected)
    def test_profiles_and_radial_dimensions(self):
        for scale in PROFILES:
            with self.subTest(scale=scale), tempfile.TemporaryDirectory() as temp:
                temp=Path(temp);d=ezdxf.new('R2010');d.units=6
                source=d.modelspace().add_lwpolyline([(0,0,0),(40,0,math.tan(math.pi/8)),(50,10,0)],format='xyb')
                d.saveas(temp/'in.dxf');d,axes,w=load(temp/'in.dxf')
                out,_=export(d,Result(axes,w),temp/'out',scale=scale);z=ezdxf.readfile(out);p=profile_for(scale)
                self.assertFalse(z.audit().errors)
                self.assertEqual(list(z.entitydb[source.dxf.handle].get_points('xyb')),list(source.get_points('xyb')))
                texts=list(z.modelspace().query('TEXT[layer=="RP_PK"]'))
                self.assertEqual([e.dxf.text for e in texts],['0+000.000'])
                for e in texts:self.assertEqual(e.dxf.height,p['pk_height']);self.assertEqual(e.dxf.style,'ARIAL')
                ticks=list(z.modelspace().query('LINE[layer=="RP_PK"]'))
                self.assertGreater(len(ticks),len(texts))
                for e in ticks:self.assertAlmostEqual(e.dxf.start.distance(e.dxf.end),3)
                self.assertFalse(list(z.modelspace().query('TEXT[layer=="RP_ELEMENTOS"]')))
                self.assertFalse(list(z.modelspace().query('LINE[layer=="RP_CENTROS"]')))
                center=result_center=Result(axes,w).curves[0]['center']
                center_label=next(iter(z.modelspace().query('TEXT[layer=="RP_CENTROS"]')))
                self.assertLess(dist(center_label.dxf.insert,center),p['geometry_height']*2)
                for e in z.modelspace().query('TEXT'):
                    if e.dxf.layer.startswith('RP_'):self.assertEqual(e.dxf.style,'ARIAL')
                for e in z.modelspace().query('TEXT[layer=="RP_VERTICES"]'):
                    self.assertEqual(e.dxf.height,p['vertex_height']);self.assertEqual(e.dxf.style,'ARIAL')
                for e in z.modelspace():
                    if e.dxf.layer.startswith('RP_'):
                        if e.dxf.layer=='RP_TABLAS':continue
                        self.assertEqual(e.dxf.true_color,VERTEX_RGB if e.dxf.layer=='RP_VERTICES' else GRAY_RGB)
                        self.assertEqual(e.dxf.color,5 if e.dxf.layer=='RP_VERTICES' else 9)
                dims=list(z.modelspace().query('DIMENSION'));self.assertEqual(len(dims),1)
                e=dims[0];self.assertEqual(e.dxf.dimtype&7,4);self.assertAlmostEqual(e.get_measurement(),10)
                style=z.dimstyles.get(e.dxf.dimstyle);self.assertEqual(style.dxf.dimasz,.75);self.assertEqual(style.dxf.dimcen,2.5)
                self.assertEqual(style.dxf.dimtxsty,'ARIAL')
                overrides=e.override();self.assertEqual(overrides.get('dimblk',''),'');self.assertEqual(overrides.get('dimasz'),.75)
                block=z.blocks[e.dxf.geometry];self.assertTrue(any(x.dxftype()=='INSERT' and 'CLOSEDFILLED' in x.dxf.name.upper() for x in block))
                for entity in block:
                    if entity.dxf.is_supported('true_color'):self.assertEqual(entity.dxf.true_color,GRAY_RGB)
                config=json.loads((temp/'out'/'Configuracion.json').read_text());self.assertEqual(config['escala'],scale)

class RevisionTests(unittest.TestCase):
    def test_drop_boundary_and_multiselection(self):
        axes=[Axis(c,c,'0',[]) for c in 'abcdef']
        place_axes(axes,['e'],1);self.assertEqual(''.join(a.handle for a in axes),'aebcdf')
        place_axes(axes,['a','b'],6);self.assertEqual(''.join(a.handle for a in axes),'ecdfab')
        place_axes(axes,['a','b'],5);self.assertEqual(''.join(a.handle for a in axes),'ecdfab')
        place_axes(axes,['a','b'],0);self.assertEqual(''.join(a.handle for a in axes),'abecdf')
    def test_direction_after_reverse(self):
        axis=Axis('a','A','0',[Segment((0,0),(100,0))])
        p,t=direction_marker(axis);self.assertEqual(p,(50,0));self.assertEqual(t,(1,0))
        axis.reverse();q,u=direction_marker(axis);self.assertEqual(q,p);self.assertEqual(u,(-1,0))
        axis=Axis('b','B','0',[Segment((10,0),(0,10),math.tan(math.pi/8))])
        p,t=direction_marker(axis);axis.reverse();q,u=direction_marker(axis)
        self.assertLess(dist(p,q),EPS);self.assertLess(norm(add(t,u)),EPS)
    def test_regular_pk_only_at_hundreds(self):
        for scale in PROFILES:
            with self.subTest(scale=scale),tempfile.TemporaryDirectory() as tmp:
                d=ezdxf.new('R2010');a=Axis('a','A','0',[Segment((0,0),(250,0))])
                out,_=export(d,Result([a],[]),tmp,scale=scale);z=ezdxf.readfile(out)
                labels=list(z.modelspace().query('TEXT[layer=="RP_PK"]'))
                self.assertEqual([t.dxf.text for t in labels],['0+000.000','0+100.000','0+200.000'])
                self.assertEqual(len(list(z.modelspace().query('LINE[layer=="RP_PK"]'))),int(250//PROFILES[scale]['tick_interval'])+1)
    def test_transition_geometry_text_sides_and_pk(self):
        a=Axis('a','A','0',[Segment((0,0),(40,0)),Segment((40,0),(50,10),math.tan(math.pi/8)),Segment((50,10),(50,50))])
        for reverse in [False,True]:
            if reverse:a.reverse()
            marks=list(transition_marks(a));self.assertEqual(len(marks),2)
            for mark in marks:
                self.assertAlmostEqual(dist(mark['start'],mark['p']),3.5);self.assertAlmostEqual(dist(mark['end'],mark['p']),32.646)
                self.assertAlmostEqual(dot(sub(mark['end'],mark['start']),mark['tangent']),0)
            self.assertEqual(marks[0]['before'],'RECTA');self.assertEqual(marks[0]['after'],'R=10.000')
            self.assertEqual(marks[1]['after'],'RECTA');self.assertEqual(marks[1]['before'],'R=10.000')
            with tempfile.TemporaryDirectory() as tmp:
                out,_=export(ezdxf.new('R2010'),Result([a],[]),tmp,scale='1:1000');z=ezdxf.readfile(out)
                lines=list(z.modelspace().query('LINE[layer=="RP_TRANSICIONES"]'));self.assertEqual(len(lines),2)
                for e in lines:self.assertAlmostEqual(e.dxf.start.distance(e.dxf.end),36.146)
                texts=list(z.modelspace().query('TEXT[layer=="RP_TRANSICIONES"]'));self.assertEqual(len(texts),6)
                for i,mark in enumerate(marks):
                    before,after,pk=texts[i*3:i*3+3]
                    self.assertEqual(before.dxf.text,mark['before']);self.assertEqual(after.dxf.text,mark['after']);self.assertEqual(pk.dxf.text,format_pk(mark['pk']))
                    for e in [before,after,pk]:self.assertEqual(e.dxf.height,2);self.assertEqual(e.dxf.style,'ARIAL');self.assertAlmostEqual(e.dxf.rotation,readable_angle(mark['normal']))
                    # Punto real de alineación, a cada lado según avance del eje.
                    self.assertLess(dot(sub(before.dxf.align_point,mark['p']),mark['tangent']),0)
                    self.assertGreater(dot(sub(after.dxf.align_point,mark['p']),mark['tangent']),0)
    def test_custom_transition_arms(self):
        a=Axis('a','A','0',[Segment((0,0),(10,0)),Segment((10,0),(20,10),math.tan(math.pi/8))])
        with tempfile.TemporaryDirectory() as tmp:
            out,_=export(ezdxf.new('R2010'),Result([a],[]),tmp,transition_short=4,transition_long=20)
            e=next(iter(ezdxf.readfile(out).modelspace().query('LINE[layer=="RP_TRANSICIONES"]')))
            self.assertAlmostEqual(e.dxf.start.distance(e.dxf.end),24)
        with self.assertRaises(ValueError):export(ezdxf.new(),Result([a],[]),'unused',transition_long=float('nan'))

if __name__=='__main__':unittest.main()
