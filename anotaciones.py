"""Anotaciones CAD editables de centros, ángulos interiores y tangentes."""
from ezdxf import ARROWS
from ezdxf.math import Vec2
from ezdxf.render.mleader import HorizontalConnection,LeaderType

BLUE=0x0000FA
FORMAT=dict(center_radius=1.,center_text_height=1.75,background_rgb=[255,255,255],background_scale=1.0001,
    angular_arrow=.75,angular_arrow_type='ARCHTICK',angular_extension=1.25,angular_offset=.625,angular_text_height=1.5,angular_units='gon',angular_decimals=4,
    leader_type='straight',leader_arrow='NONE',leader_landing=True,leader_dogleg=.5,leader_gap=.5,leader_extend_to_text=True,leader_text_height=1.5,leader_attachment=6,leader_text_frame=False)


def prepare_styles(doc):
    """Estilos propios: no cambiar los estilos existentes del plano fuente."""
    name='RP_ANGULAR'
    if name not in doc.dimstyles:doc.dimstyles.new(name)
    style=doc.dimstyles.get(name)
    style.update_dxf_attribs(dict(dimscale=1.,dimlfac=1.,dimtxt=1.5,dimasz=.75,dimexe=1.25,dimexo=.625,dimtxsty='ARIAL',
        dimclrd=7,dimclre=7,dimclrt=7,dimaunit=2,dimadec=4,dimazin=0,dimdsep=44,dimtad=1,dimtih=0,dimtoh=0,dimtsz=0.,dimsah=1,dimtfill=2,dimtfillclr=255))
    arrow=ARROWS.arrow_handle(doc.blocks,ARROWS.architectural_tick)
    style.dxf.dimblk1_handle=arrow;style.dxf.dimblk2_handle=arrow
    name='RP_TANGENTES'
    if name not in doc.mleader_styles:doc.mleader_styles.duplicate_entry('Standard',name)
    style=doc.mleader_styles.get(name);style.set_mtext_style('ARIAL')
    from ezdxf.colors import encode_raw_color
    black=encode_raw_color((0,0,0))
    style.update_dxf_attribs(dict(leader_type=1,leader_line_color=black,has_landing=1,has_dogleg=1,dogleg_length=.5,landing_gap_size=.5,
        arrow_head_handle=ARROWS.arrow_handle(doc.blocks,ARROWS.none),arrow_head_size=.75,text_left_attachment_type=6,text_right_attachment_type=6,
        char_height=1.5,text_color=black,has_text_frame=0,scale=1.,text_attachment_direction=0,text_angle_type=1))


def add_center_label(modelspace,label,point,insert):
    attrs=dict(layer='RP_CENTROS',color=5,true_color=BLUE)
    modelspace.add_circle(point,1.,dxfattribs=attrs)
    modelspace.add_point(point,dxfattribs=attrs)
    text=modelspace.add_mtext(label,dxfattribs={**attrs,'insert':insert,'style':'ARIAL','char_height':1.75,'attachment_point':4})
    text.set_bg_color((255,255,255),scale=1.0001,text_frame=False)
    text.dxf.width=1.75
    text.dxf.line_spacing_style=2
    text.dxf.line_spacing_factor=2.9167/(1.75*5/3)
    return text


def tangent_geometry(curve):
    """Ángulo interior entre PI–TE y PI–TS; independiente del sentido del eje."""
    if curve['pi'] is None or curve['roundabout']:return None
    pi=Vec2(curve['pi']);p1=Vec2(curve['s'].a);p2=Vec2(curve['s'].b)
    u=(p1-pi).normalize();v=(p2-pi).normalize()
    if u.det(v)<0:p1,p2=p2,p1;u,v=v,u
    bisector=u+v
    if bisector.magnitude<1e-10:return None
    radius=max(1.25*min((p1-pi).magnitude,(p2-pi).magnitude),9.)
    return pi,p1,p2,pi+bisector.normalize(radius)


def add_tangent_annotations(doc,modelspace,curve):
    geometry=tangent_geometry(curve)
    if geometry is None:return
    pi,p1,p2,base=geometry
    attrs=dict(layer='RP_ANGULOS',color=7,true_color=0)
    dim=modelspace.add_angular_dim_3p(base=base,center=pi,p1=p1,p2=p2,dimstyle='RP_ANGULAR',dxfattribs=attrs)
    dim.set_arrows(blk1=ARROWS.architectural_tick,blk2=ARROWS.architectural_tick,size=.75)
    dim.render()
    for entity in doc.blocks[dim.dimension.dxf.geometry]:
        if entity.dxf.is_supported('true_color'):entity.dxf.color=7;entity.dxf.true_color=0;entity.dxf.layer='RP_ANGULOS'
        if entity.dxftype()=='MTEXT':entity.set_bg_color((255,255,255),scale=1.0001)
    # Cada directriz apunta exactamente al punto medio del segmento PI–tangencia.
    center=Vec2(curve['center'])
    for index,(prefix,endpoint) in enumerate([('TE',curve['s'].a),('TS',curve['s'].b)]):
        endpoint=Vec2(endpoint);mid=(pi+endpoint)*.5;leg=(endpoint-pi).normalize()
        normal=Vec2(-leg.y,leg.x)
        if normal.dot(mid-center)<0:normal=-normal
        builder=modelspace.add_multileader_mtext('RP_TANGENTES',dxfattribs=dict(layer='RP_TANGENTES',color=7,true_color=0))
        builder.set_leader_properties(color=(0,0,0),leader_type=LeaderType.straight_lines)
        builder.set_connection_properties(landing_gap=.5,dogleg_length=.5)
        builder.set_connection_types(left=HorizontalConnection.bottom_of_top_line_underline,right=HorizontalConnection.bottom_of_top_line_underline)
        builder.set_arrow_properties(name=ARROWS.none,size=.75)
        builder.multileader.dxf.has_landing=1
        builder.multileader.dxf.leader_extend_to_text=1
        builder.multileader.dxf.has_text_frame=0
        builder.quick_leader(f'{prefix}={(endpoint-pi).magnitude:.2f}',target=mid,segment1=normal*(6.+index*2.),connection_type=HorizontalConnection.bottom_of_top_line_underline)
