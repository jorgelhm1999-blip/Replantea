import unittest,math,tempfile
from pathlib import Path
import ezdxf
from motor import *
class GeometryTests(unittest.TestCase):
    def test_quarter(self):
        s=Segment((10,0),(0,10),math.tan(math.pi/8))
        self.assertLess(dist(s.center,(0,0)),1e-12)
        self.assertAlmostEqual(s.length,5*math.pi)
        self.assertLess(dist(s.pi(),(10,10)),1e-12)
        self.assertLess(dist(s.tangent(0),(0,1)),1e-12)
    def test_reverse(self):
        s=Segment((428000,4476000),(428010,4476010),-.12);t=Segment(s.b,s.a,-s.bulge)
        self.assertLess(dist(s.center,t.center),1e-8)
        self.assertAlmostEqual(s.length,t.length)
        for k in range(11):self.assertLess(dist(s.point(k/10),t.point(1-k/10)),1e-8)
    def test_major_arc(self):
        s=Segment((1,0),(0,-1),math.tan(3*math.pi/8))
        self.assertAlmostEqual(s.length,1.5*math.pi)
        self.assertIsNotNone(s.parameter((-1,0)));self.assertIsNone(s.parameter((math.sqrt(.5),-math.sqrt(.5))))
    def test_semicircle(self):
        s=Segment((1,0),(-1,0),1);self.assertIsNone(s.pi());self.assertAlmostEqual(s.length,math.pi)
    def test_intersections(self):
        a=Segment((0,0),(10,10));b=Segment((0,10),(10,0));p=intersections(a,b)
        self.assertEqual(len(p),1);self.assertLess(dist(p[0],(5,5)),1e-9)
        self.assertEqual(intersections(a,Segment((20,0),(20,10))),[])
    def test_line_arc(self):
        s=Segment((10,0),(0,10),math.tan(math.pi/8));line=Segment((0,5),(20,5))
        p=intersections(s,line);self.assertEqual(len(p),1);self.assertLess(dist(p[0],(math.sqrt(75),5)),1e-8)
    def test_registry(self):
        a=Axis('a','A','0',[Segment((10,0),(0,10),math.tan(math.pi/8))])
        b=Axis('b','B','0',[Segment((0,10),(0,20))])
        r=Result([a,b],[])
        loc=next(l for l in r.locations if dist(l['p'],(0,10))<EPS)
        self.assertTrue('TS1' in loc['labels']);self.assertTrue(any(x.startswith('V') for x in loc['labels']))
    def test_export_preserves_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);d=ezdxf.new();d.units=6;e=d.modelspace().add_lwpolyline([(0,0,.2),(10,0,0)],format='xyb');d.saveas(tmp/'in.dxf')
            d,axes,w=load(tmp/'in.dxf');r=Result(axes,w);out,_=export(d,r,tmp/'out')
            z=ezdxf.readfile(out);original=z.entitydb[e.dxf.handle];self.assertEqual(list(original.get_points('xyb')),list(e.get_points('xyb')))
            self.assertTrue((tmp/'out'/'Curvas.csv').exists())
    def test_invalid_3d(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'3d.dxf';d=ezdxf.new();d.modelspace().add_line((0,0,1),(10,1,1));d.saveas(p)
            with self.assertRaises(ValueError):load(p)
if __name__=='__main__':unittest.main()
