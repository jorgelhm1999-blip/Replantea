"""Formato final de las anotaciones: colores exclusivamente Por capa."""
import math,re
from ezdxf.colors import encode_raw_color

DISTANCE_LAYER='03_RVI_REP_DIST_VERTICES_TXT'
PK_LAYER='RP_PK'
LAYERS={name:(0,0,0) for name in ['RP_TEXTOS','RP_RADIOS','RP_ANGULOS','RP_TANGENTES','RP_PK','RP_TRANSICIONES','RP_EJES_NOMBRES','RP_ELEMENTOS','RP_AUXILIARES','RP_TABLAS']}
LAYERS.update({name:(0,0,250) for name in ['RP_VERTICES','RP_PUNTOS','RP_CENTROS','RP_VERTICES_TXT','RP_TANGENCIAS_TXT','RP_CENTROS_TXT']})
LAYERS.update({'RP_TABLAS_IDS':(0,0,255),DISTANCE_LAYER:(0,187,250)})

def point_label(modelspace,text,insert,layer):
    e=modelspace.add_mtext(text,dxfattribs=dict(layer=layer,insert=insert,style='ARIAL',char_height=1.75,width=1.75,attachment_point=7,line_spacing_style=2,line_spacing_factor=2.9167/(1.75*5/3)))
    e.set_bg_color((255,255,255),scale=1.0001)
    return e

def vertex_distances(modelspace,result):
    """Distancia XY directa, sin enlazar listas de vértices de ejes diferentes."""
    for axis in result.axes:
        rows=result.axis_vertices.get(axis.handle,[])
        pairs=list(zip(rows,rows[1:]))
        if axis.closed and len(rows)>2 and rows[-1]['id']!=rows[0]['id']:pairs.append((rows[-1],rows[0]))
        for a,b in pairs:
            dx,dy=b['p'][0]-a['p'][0],b['p'][1]-a['p'][1];distance=math.hypot(dx,dy)
            if distance<1e-6:continue
            angle=(math.degrees(math.atan2(dy,dx))+90)%180-90
            x=(a['p'][0]+b['p'][0])/2-dy/distance*1.8;y=(a['p'][1]+b['p'][1])/2+dx/distance*1.8
            e=modelspace.add_mtext(f"{a['id']}-{b['id']}={distance:.2f}",dxfattribs=dict(layer=DISTANCE_LAYER,style='ARIAL',char_height=1.5,line_spacing_style=2,line_spacing_factor=1.))
            e.set_location((x,y),rotation=angle,attachment_point=8)

def by_layer(entity,layer):
    entity.dxf.layer=layer;entity.dxf.color=256
    entity.dxf.discard('true_color');entity.dxf.discard('color_name')

def organize_layers(doc):
    for name,color in LAYERS.items():
        if name not in doc.layers:doc.layers.new(name)
        entry=doc.layers.get(name);entry.dxf.color=5 if color[2] else 7
        entry.rgb=color
    for entity in list(doc.modelspace()):
        layer=entity.dxf.layer
        if layer not in LAYERS:continue
        kind=entity.dxftype()
        if kind=='LINE' and layer in ('RP_PUNTOS','RP_VERTICES'):layer='RP_AUXILIARES'
        if kind=='LINE' and layer=='RP_RADIOS':layer='RP_AUXILIARES'
        if kind=='MTEXT':
            layer={'RP_VERTICES':'RP_VERTICES_TXT','RP_PUNTOS':'RP_TANGENCIAS_TXT','RP_CENTROS':'RP_CENTROS_TXT'}.get(layer,layer)
        if kind=='TEXT' and layer=='RP_TABLAS' and re.fullmatch(r'(V|C|TE|TS)\d+',entity.dxf.text):layer='RP_TABLAS_IDS'
        by_layer(entity,layer)
        if kind=='DIMENSION':
            if layer=='RP_RADIOS':
                entity.dxf.line_spacing_style=2
                entity.dxf.line_spacing_factor=2.9167/(1.75*5/3)
            style=doc.dimstyles.get(entity.dxf.dimstyle)
            style.dxf.dimclrd=256;style.dxf.dimclre=256;style.dxf.dimclrt=256
            override=entity.override();override.update({'dimclrd':256,'dimclre':256,'dimclrt':256});override.commit()
            for part in doc.blocks[entity.dxf.geometry]:
                if not part.dxf.is_supported('layer'):continue
                by_layer(part,layer)
                if part.dxftype()=='MTEXT':
                    part.text=re.sub(r'\\[Cc][^;]*;','',part.text)
                    part.set_bg_color((255,255,255),scale=1.0001)
                    if layer=='RP_RADIOS':
                        part.dxf.char_height=1.75;part.dxf.width=1.75
                        part.dxf.line_spacing_style=2;part.dxf.line_spacing_factor=2.9167/(1.75*5/3)
        if kind=='MULTILEADER':
            entity.dxf.leader_line_color=encode_raw_color(256);entity.dxf.text_color=encode_raw_color(256)
            if entity.context.mtext:entity.context.mtext.color=encode_raw_color(256)
            for leader in entity.context.leaders:
                for line in leader.lines:line.color=encode_raw_color(256)
    if 'RP_TANGENTES' in doc.mleader_styles:
        style=doc.mleader_styles.get('RP_TANGENTES');style.dxf.leader_line_color=encode_raw_color(256);style.dxf.text_color=encode_raw_color(256)
