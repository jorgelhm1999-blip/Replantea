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
                self.assertEqual([e.dxf.text for e in texts[:3]],['0+000.000',format_pk(p['tick_interval']),format_pk(p['tick_interval']*2)])
                for e in texts:self.assertEqual(e.dxf.height,p['pk_height']);self.assertEqual(e.dxf.style,'Standard')
                ticks=list(z.modelspace().query('LINE[layer=="RP_PK"]'))
                self.assertEqual(len(texts),len(ticks))
                for e in ticks:self.assertAlmostEqual(e.dxf.start.distance(e.dxf.end),3)
                for e in z.modelspace().query('TEXT[layer=="RP_ELEMENTOS"]'):
                    self.assertEqual(e.dxf.text,e.dxf.text.upper());self.assertEqual(e.dxf.height,p['geometry_height']);self.assertEqual(e.dxf.style,'Standard')
                for e in z.modelspace().query('TEXT[layer=="RP_VERTICES"]'):
                    self.assertEqual(e.dxf.height,p['vertex_height']);self.assertEqual(e.dxf.style,'ARIAL')
                for e in z.modelspace():
                    if e.dxf.layer.startswith('RP_'):
                        self.assertEqual(e.dxf.true_color,VERTEX_RGB if e.dxf.layer=='RP_VERTICES' else GRAY_RGB)
                        self.assertEqual(e.dxf.color,5 if e.dxf.layer=='RP_VERTICES' else 9)
                dims=list(z.modelspace().query('DIMENSION'));self.assertEqual(len(dims),1)
                e=dims[0];self.assertEqual(e.dxf.dimtype&7,4);self.assertAlmostEqual(e.get_measurement(),10)
                style=z.dimstyles.get(e.dxf.dimstyle);self.assertEqual(style.dxf.dimasz,.75);self.assertEqual(style.dxf.dimcen,2.5)
                self.assertEqual(style.dxf.dimtxsty,'Standard')
                overrides=e.override();self.assertEqual(overrides.get('dimblk',''),'');self.assertEqual(overrides.get('dimasz'),.75)
                block=z.blocks[e.dxf.geometry];self.assertTrue(any(x.dxftype()=='INSERT' and 'CLOSEDFILLED' in x.dxf.name.upper() for x in block))
                for entity in block:
                    if entity.dxf.is_supported('true_color'):self.assertEqual(entity.dxf.true_color,GRAY_RGB)
                config=json.loads((temp/'out'/'Configuracion.json').read_text());self.assertEqual(config['escala'],scale)

if __name__=='__main__':unittest.main()
