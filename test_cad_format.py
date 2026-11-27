import math,tempfile,unittest
from pathlib import Path
import ezdxf
from motor import Axis,Segment,Result,export
from formato_cad import LAYERS,DISTANCE_LAYER

class CadFormatTests(unittest.TestCase):
    def test_distances_do_not_join_separate_axes(self):
        a=Axis('a','A','0',[Segment((0,0),(10,0))]);b=Axis('b','B','0',[Segment((100,50),(115,50))])
        with tempfile.TemporaryDirectory() as tmp:
            out,_=export(ezdxf.new(),Result([a,b],[]),tmp);z=ezdxf.readfile(out)
            texts=list(z.modelspace().query(f'MTEXT[layer=="{DISTANCE_LAYER}"]'))
            self.assertEqual([t.text for t in texts],['V1-V2=10.00','V3-V4=15.00'])
            for t in texts:
                self.assertEqual(t.dxf.char_height,1.5);self.assertEqual(t.dxf.line_spacing_factor,1)
                self.assertFalse(t.dxf.get('bg_fill',0));self.assertEqual(t.dxf.color,256)
            self.assertEqual(z.layers.get(DISTANCE_LAYER).rgb,(0,187,250))

    def test_shared_vertex_follows_each_axis_in_both_directions(self):
        a=Axis('a','A','0',[Segment((0,0),(100,0))]);b=Axis('b','B','0',[Segment((50,-20),(50,20))])
        for reverse in (False,True):
            if reverse:a.reverse();b.reverse()
            r=Result([a,b],[])
            expected=[f"{u['id']}-{v['id']}={math.dist(u['p'],v['p']):.2f}" for axis in [a,b] for u,v in zip(r.axis_vertices[axis.handle],r.axis_vertices[axis.handle][1:])]
            with tempfile.TemporaryDirectory() as tmp:
                out,_=export(ezdxf.new(),r,tmp);z=ezdxf.readfile(out)
                actual=[t.text for t in z.modelspace().query(f'MTEXT[layer=="{DISTANCE_LAYER}"]')]
                self.assertEqual(actual,expected);self.assertEqual(len(actual),4)

    def test_pk_text_is_on_tick_normal_and_all_generated_entities_by_layer(self):
        a=Axis('a','A','0',[Segment((0,0),(250,0))])
        with tempfile.TemporaryDirectory() as tmp:
            out,_=export(ezdxf.new(),Result([a],[]),tmp);z=ezdxf.readfile(out)
            pk=next(t for t in z.modelspace().query('TEXT[layer=="RP_PK"]') if t.dxf.text=='0+100.000')
            self.assertAlmostEqual(pk.dxf.align_point.x,100)
            self.assertAlmostEqual(abs(pk.dxf.rotation),90)
            for e in z.modelspace():
                if e.dxf.layer in LAYERS:
                    self.assertEqual(e.dxf.color,256);self.assertFalse(e.dxf.hasattr('true_color'))
                    self.assertEqual(z.layers.get(e.dxf.layer).rgb,LAYERS[e.dxf.layer])
            labels=list(z.modelspace().query('MTEXT[layer=="RP_VERTICES_TXT"]'))
            for e in labels:
                self.assertEqual(e.dxf.char_height,1.75);self.assertEqual(e.dxf.width,1.75)
                self.assertAlmostEqual(e.dxf.line_spacing_factor*e.dxf.char_height*5/3,2.9167)
                self.assertEqual(e.dxf.box_fill_scale,1.0001);self.assertEqual(e.dxf.bg_fill_true_color,0xFFFFFF)

    def test_dimension_blocks_are_black_and_radial_mask_is_formatted(self):
        a=Axis('a','A','0',[Segment((10,0),(0,10),math.tan(math.pi/8))])
        with tempfile.TemporaryDirectory() as tmp:
            out,_=export(ezdxf.new(),Result([a],[]),tmp);z=ezdxf.readfile(out)
            for e in z.modelspace().query('DIMENSION'):
                self.assertEqual(z.layers.get(e.dxf.layer).rgb,(0,0,0))
                for part in z.blocks[e.dxf.geometry]:
                    if part.dxf.is_supported('color'):
                        self.assertEqual(part.dxf.color,256);self.assertFalse(part.dxf.hasattr('true_color'))
                    if part.dxftype()=='MTEXT':
                        self.assertEqual(part.dxf.bg_fill_true_color,0xFFFFFF)
                        if e.dxf.layer=='RP_RADIOS':
                            self.assertEqual(part.dxf.char_height,1.75);self.assertEqual(part.dxf.width,1.75)
                            self.assertAlmostEqual(part.dxf.line_spacing_factor*1.75*5/3,2.9167)
            self.assertFalse(z.audit().errors)

if __name__=='__main__':unittest.main()
