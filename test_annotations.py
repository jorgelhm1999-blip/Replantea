"""Comprobar las entidades CAD, la medida del ángulo y los anclajes reales."""
import math
import tempfile
import unittest
from pathlib import Path
import ezdxf
from motor import load,Result,export,PROFILES,dist,EPS


def example_source(path,version='R2010',offset=(0,0)):
    d=ezdxf.new(version);d.units=6
    turn=2*math.atan(8.5/30)
    points=[(70,0,0),(8.5,0,-math.tan(turn/4)),(-8.5*math.cos(turn),8.5*math.sin(turn),0),(-50,31,0)]
    source=d.modelspace().add_lwpolyline([(x+offset[0],y+offset[1],b) for x,y,b in points],format='xyb')
    d.saveas(path)
    return source


class AnnotationTests(unittest.TestCase):
    def test_center_circle_and_masked_mtext_in_both_scales(self):
        for scale in PROFILES:
            with self.subTest(scale=scale),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);example_source(p/'in.dxf');d,a,w=load(p/'in.dxf');r=Result(a,w)
                label='='.join(next(l['labels'] for l in r.locations if all(x.startswith('C') for x in l['labels'])))
                out,_=export(d,r,p/'out',scale=scale,label_overrides={label:(123,456)})
                z=ezdxf.readfile(out);m=z.modelspace()
                circles=list(m.query('CIRCLE[layer=="RP_CENTROS"]'));self.assertEqual(len(circles),1)
                circle=circles[0];self.assertEqual(circle.dxf.radius,1)
                self.assertLess(dist(circle.dxf.center,r.curves[0]['center']),EPS)
                self.assertEqual(circle.dxf.color,256);self.assertEqual(z.layers.get(circle.dxf.layer).rgb,(0,0,250))
                t=next(iter(m.query('MTEXT[layer=="RP_CENTROS_TXT"]')))
                self.assertEqual(t.text,'C1');self.assertEqual(t.dxf.style,'ARIAL');self.assertEqual(t.dxf.char_height,1.75)
                self.assertEqual(tuple(t.dxf.insert),(123,456,0));self.assertEqual(t.dxf.color,256);self.assertEqual(z.layers.get(t.dxf.layer).rgb,(0,0,250))
                self.assertEqual(t.dxf.bg_fill,1);self.assertEqual(t.dxf.bg_fill_true_color,0xFFFFFF)
                self.assertEqual(t.dxf.box_fill_scale,1.0001)
                self.assertFalse(list(m.query('TEXT[layer=="RP_CENTROS"]')))
                self.assertFalse(list(m.query('LINE[layer=="RP_CENTROS"]')))

    def test_angular_measure_is_interior_at_pi_invariant_under_reverse(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);example_source(p/'in.dxf');d,a,w=load(p/'in.dxf')
            for reverse in [False,True]:
                if reverse:a[0].reverse()
                r=Result(a,w);out,_=export(d,r,p/str(reverse));z=ezdxf.readfile(out)
                dimension=next(iter(z.modelspace().query('DIMENSION[layer=="RP_ANGULOS"]')))
                self.assertEqual(dimension.dxf.dimtype&7,5)
                self.assertAlmostEqual(dimension.get_measurement()*10/9,164.8462356722,places=7)
                self.assertLess(dist(dimension.dxf.defpoint4,r.curves[0]['pi']),EPS)
                style=z.dimstyles.get(dimension.dxf.dimstyle)
                for key,value in dict(dimasz=.75,dimexe=1.25,dimexo=.625,dimaunit=2,dimadec=4).items():self.assertEqual(getattr(style.dxf,key),value)
                self.assertEqual(style.dxf.dimtxsty,'ARIAL')
                arrows=dimension.override()
                self.assertEqual(arrows.get('dimblk1'),'ARCHTICK');self.assertEqual(arrows.get('dimblk2'),'ARCHTICK')
                inserts=list(z.blocks[dimension.dxf.geometry].query('INSERT'))
                self.assertEqual(len(inserts),2)
                self.assertTrue(all('ARCHTICK' in e.dxf.name.upper() for e in inserts))
                self.assertFalse(z.audit().errors)

    def test_multileader_properties_and_exact_midpoint_targets_after_reverse(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);example_source(p/'in.dxf');d,a,w=load(p/'in.dxf')
            for reverse in [False,True]:
                if reverse:a[0].reverse()
                r=Result(a,w);c=r.curves[0];out,_=export(d,r,p/str(reverse));z=ezdxf.readfile(out)
                leaders=list(z.modelspace().query('MULTILEADER[layer=="RP_TANGENTES"]'));self.assertEqual(len(leaders),2)
                for leader,endpoint,prefix in zip(leaders,[c['s'].a,c['s'].b],['TE','TS']):
                    self.assertEqual(leader.context.mtext.default_content,prefix+'=8.50')
                    target=leader.context.leaders[0].lines[0].vertices[0]
                    midpoint=((endpoint[0]+c['pi'][0])/2,(endpoint[1]+c['pi'][1])/2)
                    self.assertLess(dist(target,midpoint),EPS)
                    self.assertEqual(leader.context.char_height,1.5)
                    self.assertEqual(z.entitydb[leader.dxf.text_style_handle].dxf.name,'ARIAL')
                    self.assertEqual(leader.dxf.leader_type,1);self.assertEqual(leader.dxf.has_landing,1)
                    self.assertEqual(leader.dxf.has_dogleg,1);self.assertEqual(leader.dxf.dogleg_length,.5)
                    self.assertEqual(leader.context.landing_gap_size,.5)
                    self.assertEqual(leader.dxf.leader_extend_to_text,1);self.assertEqual(leader.dxf.has_text_frame,0)
                    self.assertEqual(leader.dxf.text_attachment_direction,0)
                    self.assertEqual(leader.dxf.text_left_attachment_type,6);self.assertEqual(leader.dxf.text_right_attachment_type,6)
                    self.assertEqual(z.entitydb[leader.dxf.arrow_head_handle].dxf.name,'_NONE')

    def test_glorieta_keeps_center_without_pi_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);example_source(p/'in.dxf');d,a,w=load(p/'in.dxf');a[0].roundabout=True
            out,_=export(d,Result(a,w),p/'out');z=ezdxf.readfile(out)
            self.assertTrue(list(z.modelspace().query('MTEXT[layer=="RP_CENTROS_TXT"]')))
            self.assertFalse(list(z.modelspace().query('DIMENSION[layer=="RP_ANGULOS"]')))
            self.assertFalse(list(z.modelspace().query('MULTILEADER[layer=="RP_TANGENTES"]')))

    def test_old_dxf_export_upgraded_without_changing_source_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=example_source(p/'in.dxf',version='R2000',offset=(10000,40000))
            d,a,w=load(p/'in.dxf');original=list(source.get_points('xyb'));version=d.dxfversion
            out,_=export(d,Result(a,w),p/'out');z=ezdxf.readfile(out)
            self.assertEqual(d.dxfversion,version);self.assertGreaterEqual(z.dxfversion,'AC1027')
            self.assertEqual(list(z.entitydb[source.dxf.handle].get_points('xyb')),original)
            self.assertFalse(z.audit().errors)

    def test_semicircle_without_finite_pi_does_not_add_wrong_angular_dimension(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);d=ezdxf.new('R2010');d.units=6;d.modelspace().add_lwpolyline([(10,0,1),(-10,0,0)],format='xyb');d.saveas(p/'in.dxf')
            d,a,w=load(p/'in.dxf');out,_=export(d,Result(a,w),p/'out');z=ezdxf.readfile(out)
            self.assertFalse(list(z.modelspace().query('DIMENSION[layer=="RP_ANGULOS"]')))
            self.assertFalse(list(z.modelspace().query('MULTILEADER[layer=="RP_TANGENTES"]')))


if __name__=='__main__':unittest.main()
