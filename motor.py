"""Replantea 0.4: replanteo exacto de rectas y arcos planos; no modifica ejes."""
from dataclasses import dataclass
from pathlib import Path
import math, json, csv, tempfile
import ezdxf
from ezdxf.enums import TextEntityAlignment

EPS=1e-6
TAU=2*math.pi
def add(a,b):return (a[0]+b[0],a[1]+b[1])
def sub(a,b):return (a[0]-b[0],a[1]-b[1])
def mul(a,t):return (a[0]*t,a[1]*t)
def dot(a,b):return a[0]*b[0]+a[1]*b[1]
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def norm(a):return math.hypot(*a)
def unit(a):return mul(a,1/norm(a))
def dist(a,b):return norm(sub(a,b))
def left(a):return (-a[1],a[0])
def az(a):return math.atan2(a[0],a[1])*200/math.pi%400

@dataclass
class Segment:
    a:tuple
    b:tuple
    bulge:float=0.
    def __post_init__(self):
        self.a=tuple(self.a[:2]);self.b=tuple(self.b[:2])
        chord=sub(self.b,self.a);L=norm(chord)
        if L<EPS:raise ValueError('Segmento de longitud nula')
        self.center=None;self.radius=None;self.sweep=0.
        if abs(self.bulge)>1e-12:
            self.sweep=4*math.atan(self.bulge)
            self.center=add(add(self.a,mul(chord,.5)),mul(left(chord),(1-self.bulge**2)/(4*self.bulge)))
            self.radius=L*(1+self.bulge**2)/(4*abs(self.bulge))
            self.angle=math.atan2(self.a[1]-self.center[1],self.a[0]-self.center[0])
            self.length=abs(self.sweep)*self.radius
        else:self.length=L
    def point(self,t):
        if self.center is None:return add(self.a,mul(sub(self.b,self.a),t))
        v=self.angle+self.sweep*t
        return add(self.center,(self.radius*math.cos(v),self.radius*math.sin(v)))
    def tangent(self,t):
        if self.center is None:return unit(sub(self.b,self.a))
        return mul(left(unit(sub(self.point(t),self.center))),1 if self.sweep>0 else -1)
    def parameter(self,p):
        if self.center is None:
            v=sub(self.b,self.a);t=dot(sub(p,self.a),v)/dot(v,v)
            return t if -EPS/self.length<=t<=1+EPS/self.length and dist(self.point(t),p)<EPS*5 else None
        if abs(dist(p,self.center)-self.radius)>EPS*5:return None
        if dist(p,self.a)<EPS*5:return 0.
        if dist(p,self.b)<EPS*5:return 1.
        an=math.atan2(p[1]-self.center[1],p[0]-self.center[0]);delta=((an-self.angle) if self.sweep>0 else (self.angle-an))%TAU
        t=delta/abs(self.sweep)
        return t if t<=1+EPS/self.length else None
    def pi(self):
        if self.center is None:return None
        u,v=self.tangent(0),self.tangent(1);den=cross(u,v)
        if abs(den)<1e-10:return None
        return add(self.a,mul(u,cross(sub(self.b,self.a),v)/den))

def intersections(s,t):
    """Intersecciones analíticas en XY, sin extender los segmentos."""
    candidates=[]
    if s.center is None and t.center is None:
        u,v=sub(s.b,s.a),sub(t.b,t.a);den=cross(u,v)
        if abs(den)>1e-12*norm(u)*norm(v):candidates=[add(s.a,mul(u,cross(sub(t.a,s.a),v)/den))]
    elif s.center is None or t.center is None:
        ln,ar=(s,t) if s.center is None else (t,s)
        v=sub(ln.b,ln.a);w=sub(ln.a,ar.center);A=dot(v,v);B=2*dot(w,v);C=dot(w,w)-ar.radius**2;delta=B*B-4*A*C
        if delta>=-1e-8:
            q=math.sqrt(max(0,delta));candidates=[add(ln.a,mul(v,(-B+q)/(2*A))),add(ln.a,mul(v,(-B-q)/(2*A)))]
    else:
        v=sub(t.center,s.center);D=norm(v)
        if D>EPS and D<=s.radius+t.radius+EPS and D>=abs(s.radius-t.radius)-EPS:
            a=(s.radius**2-t.radius**2+D**2)/(2*D);h2=s.radius**2-a*a
            if h2>=-1e-6:
                mid=add(s.center,mul(v,a/D));off=mul(left(v),math.sqrt(max(0,h2))/D)
                candidates=[add(mid,off),sub(mid,off)]
    out=[]
    for p in candidates:
        if s.parameter(p) is not None and t.parameter(p) is not None and not any(dist(p,x)<EPS for x in out):out.append(p)
    return out

@dataclass
class Axis:
    handle:str
    name:str
    layer:str
    segments:list
    closed:bool=False
    selected:bool=True
    pk0:float=0.
    roundabout:bool=False
    def reverse(self):self.segments=[Segment(s.b,s.a,-s.bulge) for s in self.segments[::-1]]
    @property
    def length(self):return sum(s.length for s in self.segments)

def load(path):
    path=Path(path);warnings=[]
    if path.suffix.lower()=='.dwg':
        import ezdwg
        with tempfile.TemporaryDirectory() as tmp:
            result=ezdwg.to_dxf(str(path),str(Path(tmp)/'input.dxf'),modelspace_only=True)
            if result.skipped_entities or result.unqueried_by_type:warnings.append('Conversión DWG: entidades omitidas '+str(result))
            doc=ezdxf.readfile(Path(tmp)/'input.dxf')
    elif path.suffix.lower()=='.dxf':doc=ezdxf.readfile(path)
    else:raise ValueError('Entrada admitida: DWG o DXF. DWF no es compatible.')
    if doc.units!=6:warnings.append(f'Unidades declaradas: {doc.units}. Confirmar que las coordenadas representan metros; no se aplica escala.')
    axes=[];unsupported={}
    for e in doc.modelspace():
        kind=e.dxftype();pairs=[];closed=False
        if kind=='LWPOLYLINE':
            if abs(e.dxf.elevation)>EPS or not e.dxf.extrusion.isclose((0,0,1)):raise ValueError('Solo se admiten ejes planos XY con elevación 0 y normal +Z.')
            pts=list(e.get_points('xyb'));closed=e.closed
            pairs=[(p[:2],q[:2],p[2]) for p,q in zip(pts,pts[1:]+([pts[0]] if closed else []))]
        elif kind=='LINE':
            if abs(e.dxf.start.z)>EPS or abs(e.dxf.end.z)>EPS:raise ValueError('LINE 3D: exportar primero la planta XY.')
            pairs=[(tuple(e.dxf.start)[:2],tuple(e.dxf.end)[:2],0)]
        elif kind=='ARC':
            if abs(e.dxf.center.z)>EPS or not e.dxf.extrusion.isclose((0,0,1)):raise ValueError('ARC fuera del plano XY.')
            center=tuple(e.dxf.center)[:2];a,b=math.radians(e.dxf.start_angle),math.radians(e.dxf.end_angle)
            sweep=(b-a)%TAU
            pairs=[(add(center,(e.dxf.radius*math.cos(a),e.dxf.radius*math.sin(a))),add(center,(e.dxf.radius*math.cos(b),e.dxf.radius*math.sin(b))),math.tan(sweep/4))]
        elif kind=='CIRCLE':
            if abs(e.dxf.center.z)>EPS or not e.dxf.extrusion.isclose((0,0,1)):raise ValueError('CIRCLE fuera del plano XY.')
            ce=tuple(e.dxf.center)[:2];R=e.dxf.radius;ps=[add(ce,(R*math.cos(k*math.pi/2),R*math.sin(k*math.pi/2))) for k in range(4)]
            pairs=[(ps[k],ps[(k+1)%4],math.tan(math.pi/8)) for k in range(4)];closed=True
            warnings.append(f'Círculo {e.dxf.handle}: origen convencional este y cuatro cuadrantes; revisar origen y sentido.')
        else:
            unsupported[kind]=unsupported.get(kind,0)+1;continue
        seg=[]
        for j,(p,q,b) in enumerate(pairs):
            if dist(p,q)<EPS:
                warnings.append(f'Entidad {e.dxf.handle}: segmento {j+1} de longitud nula; omitido solo en cálculo.');continue
            seg.append(Segment(p,q,b))
        if not seg:continue
        name=f'E{len(axes)+1:02d}'
        if not closed and EPS<dist(seg[0].a,seg[-1].b)<.001:warnings.append(f'{name}: extremo a {dist(seg[0].a,seg[-1].b)*1000:.4f} mm del inicio; se conserva abierto.')
        for j,(a,b) in enumerate(zip(seg,seg[1:])):
            angle=math.acos(max(-1,min(1,dot(a.tangent(1),b.tangent(0)))))*200/math.pi
            if angle>.001:warnings.append(f'{name}: discontinuidad de dirección {angle:.6f} g en unión {j+1}; no se corrige.')
        axes.append(Axis(e.dxf.handle,name,e.dxf.layer,seg,closed))
    if unsupported:warnings.append('Entidades fuera del cálculo: '+str(unsupported)+'. Las alineaciones Civil nativas requieren exportación a geometría CAD.')
    if not axes:raise ValueError('No hay rectas, arcos, círculos o polilíneas XY compatibles. Exportar alineaciones Civil a geometría CAD.')
    return doc,axes,warnings

class Result:
    def __init__(self,axes,warnings):
        self.axes=[a for a in axes if a.selected];self.warnings=list(warnings);self.rows=[];self.curves=[];self.locations=[];self.vertices=[]
        self.curve_n=0;self.v_n=0
        events={a.handle:[] for a in self.axes}
        def event(axis,station,kind,p,pk,curve=None):
            # Clasificación manual por eje; los accesos conservan sus propios V.
            if axis.roundabout and kind in ('V','PI'):return
            events[axis.handle].append((station,len(events[axis.handle]),kind,p,pk,curve))
        # Preparar todos los encuentros antes de numerar: su PK define cuándo se visitan.
        for i,a in enumerate(self.axes):
            for b in self.axes[i+1:]:
                pa=a.pk0
                for seg in a.segments:
                    pb=b.pk0
                    for other in b.segments:
                        for p in intersections(seg,other):
                            qa=pa+seg.parameter(p)*seg.length;qb=pb+other.parameter(p)*other.length
                            event(a,qa,'V',p,qa);event(b,qb,'V',p,qb)
                        pb+=other.length
                    pa+=seg.length
        for axis in self.axes:
            pk=axis.pk0
            for j,seg in enumerate(axis.segments):
                if seg.center is not None:
                    self.curve_n+=1;n=self.curve_n
                    curve=dict(id=n,eje=axis.name,segment=j+1,pk0=pk,pk1=pk+seg.length,r=seg.radius,length=seg.length,angle_g=seg.sweep*200/math.pi,center=seg.center,pi=seg.pi(),vertex='',tangent=None if seg.pi() is None else dist(seg.pi(),seg.a),s=seg,roundabout=axis.roundabout)
                    self.curves.append(curve)
                    event(axis,pk,'TE',seg.a,pk,curve);event(axis,pk+seg.length,'TS',seg.b,pk+seg.length,curve)
                    event(axis,pk,'C',seg.center,None,curve)
                    if curve['pi'] is not None:event(axis,pk+seg.length/2,'PI',curve['pi'],None,curve)
                    elif not axis.roundabout:self.warnings.append(f'{axis.name}: curva C{n}, tangentes paralelas; vértice de tangentes no definido.')
                else:
                    event(axis,pk,'V',seg.a,pk);event(axis,pk+seg.length,'V',seg.b,pk+seg.length)
                pk+=seg.length
            for station,_,kind,p,point_pk,curve in sorted(events[axis.handle],key=lambda e:(round(e[0],8),e[1])):
                if kind in ('V','PI'):
                    label=self.vertex(p,axis.name,point_pk)
                    if kind=='PI':curve['vertex']=label
                else:
                    group='CENTROS DE CURVAS' if kind=='C' else 'TANGENTES'
                    self.point(f"{kind}{curve['id']}",p,group,axis.name,point_pk)
        self.groups={g:[r for r in self.rows if r['grupo']==g] for g in ['VÉRTICES','TANGENTES','CENTROS DE CURVAS']}
    def point(self,label,p,group,axis,pk):
        row=next((r for r in self.rows if r['id']==label),None)
        if row is None:
            row=dict(id=label,x=p[0],y=p[1],grupo=group,ejes=[],pks=[]);self.rows.append(row)
            loc=next((x for x in self.locations if dist(x['p'],p)<EPS),None)
            if loc is None:loc=dict(p=p,labels=[]);self.locations.append(loc)
            loc['labels'].append(label)
        if axis not in row['ejes']:row['ejes'].append(axis)
        if pk is not None and not any(x['eje']==axis and abs(x['pk']-pk)<EPS for x in row['pks']):row['pks'].append(dict(eje=axis,pk=pk))
        return label
    def vertex(self,p,axis,pk):
        old=next((r for r in self.vertices if dist((r['x'],r['y']),p)<EPS),None)
        if old is not None:label=old['id']
        else:self.v_n+=1;label=f'V{self.v_n}'
        self.point(label,p,'VÉRTICES',axis,pk)
        if old is None:self.vertices.append(self.rows[-1])
        return label

def write_csv(path,headers,rows):
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f,delimiter=';');w.writerow(headers);w.writerows(rows)

PROFILES={
    '1:2000':dict(vertex_height=3.5,pk_height=1.5,geometry_height=1.5,tick_interval=10.,tick_length=3.,pk_interval=100.),
    '1:1000':dict(vertex_height=1.75,pk_height=2.,geometry_height=2.,tick_interval=20.,tick_length=3.,pk_interval=100.),
}
GRAY_RGB=0xC0C0C0
VERTEX_RGB=0x0000FA
TABLE_FORMAT=dict(text_height=2.,column_widths=[10.,19.2289,19.2289],row_height=4.,coordinate_offset=[9.1366,2.0211],text_rgb=[0,0,0],identifier_rgb=[0,0,255])

def coordinate_tables(modelspace,result,origin):
    """Cuadros LINE/TEXT en unidades de modelo, independientes de la escala."""
    cw=TABLE_FORMAT['column_widths'];rh=TABLE_FORMAT['row_height'];height=TABLE_FORMAT['text_height'];width=sum(cw)
    dx,dy=TABLE_FORMAT['coordinate_offset'];tx,ty=origin;gap=5.
    def attributes(blue=False):return dict(layer='RP_TABLAS',color=5 if blue else 7,true_color=0x0000FF if blue else 0x000000)
    def line(a,b):modelspace.add_line(a,b,dxfattribs=attributes())
    def text(caption,p,blue=False):
        e=modelspace.add_text(caption,dxfattribs={**attributes(blue),'height':height,'style':'ARIAL'})
        e.set_placement(p,align=TextEntityAlignment.MIDDLE_CENTER)
        return e
    def title(caption,center,y):
        e=text(caption,(center,y))
        # Subrayado editable con el ancho real de ARIAL (mismo estilo que el texto).
        from ezdxf.tools.text_size import text_size
        half=text_size(e).width/2
        line((center-half,y-height*.75),(center+half,y-height*.75))
    title('COORDENADAS REPLANTEO',tx+(2*width+gap)/2,ty+11)
    right=tx+width+gap
    centers_height=(len(result.groups['CENTROS DE CURVAS'])+1)*rh
    tables=[('VÉRTICES',tx,ty),('CENTROS DE CURVAS',right,ty),('TANGENTES',right,ty-centers_height-9.)]
    for group,x,y in tables:
        rows=result.groups[group];bottom=y-(len(rows)+1)*rh
        title(group,x+cw[0]+(cw[1]+cw[2])/2,y+4.)
        # Cabecera escalonada: solo X e Y; el identificador empieza en la primera fila de datos.
        for j,caption in [(1,'X'),(2,'Y')]:
            text(caption,(x+sum(cw[:j])+cw[j]/2,y-rh/2))
        for k,row in enumerate(rows,1):
            top=y-k*rh
            text(row['id'],(x+cw[0]/2,top-rh/2),blue=True)
            for j,key in [(1,'x'),(2,'y')]:
                text(f"{row[key]:.3f}",(x+sum(cw[:j])+dx,top-dy))
        line((x+cw[0],y),(x+width,y))
        for k in range(1,len(rows)+2):line((x if rows else x+cw[0],y-k*rh),(x+width,y-k*rh))
        if rows:line((x,y-rh),(x,bottom))
        for j in range(1,4):
            xx=x+sum(cw[:j]);line((xx,y),(xx,bottom))

def profile_for(scale):
    if scale not in PROFILES:raise ValueError('Escala admitida: 1:1000 o 1:2000.')
    return dict(PROFILES[scale])

def format_pk(value):
    millis=round(abs(value)*1000);km,rest=divmod(millis,1000000)
    return f"{'-' if value<0 else ''}{km}+{rest//1000:03d}.{rest%1000:03d}"

def move_axes(axes,handles,direction):
    if direction not in (-1,1):raise ValueError('Dirección de orden no válida.')
    handles=set(handles);indices=range(1,len(axes)) if direction<0 else range(len(axes)-2,-1,-1)
    for i in indices:
        j=i+direction
        if axes[i].handle in handles and axes[j].handle not in handles:axes[i],axes[j]=axes[j],axes[i]

def place_axes(axes,handles,slot):
    """Insertar filas seleccionadas en un límite de la lista original (0..n)."""
    selected=set(handles);slot=max(0,min(len(axes),int(slot)))
    moving=[a for a in axes if a.handle in selected]
    insert=sum(a.handle not in selected for a in axes[:slot])
    remaining=[a for a in axes if a.handle not in selected]
    axes[:]=remaining[:insert]+moving+remaining[insert:]

def direction_marker(axis):
    station=axis.length*.5
    for seg in axis.segments:
        if station<=seg.length:return seg.point(station/seg.length),seg.tangent(station/seg.length)
        station-=seg.length
    return axis.segments[-1].b,axis.segments[-1].tangent(1)

def readable_angle(vector):
    angle=math.degrees(math.atan2(vector[1],vector[0]))
    return (angle+90)%180-90

def transition_marks(axis,short_arm=3.5,long_arm=32.646):
    """Cambios recta/arco. Normal derecha según el sentido creciente de PK."""
    pk=axis.pk0
    for j,after in enumerate(axis.segments):
        if j or axis.closed:
            before=axis.segments[j-1]
            if (before.center is None)!=(after.center is None) and dist(before.b,after.a)<EPS*5:
                tangent=after.tangent(0) if after.center else before.tangent(1)
                normal=mul(left(tangent),-1);point=after.a
                yield dict(p=point,tangent=tangent,normal=normal,start=add(point,mul(normal,-short_arm)),end=add(point,mul(normal,long_arm)),pk=pk,
                    before='RECTA' if before.center is None else f'R={before.radius:.3f}',after='RECTA' if after.center is None else f'R={after.radius:.3f}')
        pk+=after.length

def label_height(loc,profile):
    return profile['vertex_height'] if any(x.startswith('V') for x in loc['labels']) else profile['geometry_height']

def export(doc,result,out,text_height=1.5,pk_step=100,label_overrides=None,scale='1:2000',transition_short=3.5,transition_long=32.646):
    if not all(math.isfinite(v) and v>0 for v in (transition_short,transition_long)):raise ValueError('Los brazos de la marca de transición deben ser positivos.')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    import copy
    d=copy.deepcopy(doc);m=d.modelspace();profile=profile_for(scale);h=profile['vertex_height'];gh=profile['geometry_height']
    layers=['RP_PUNTOS','RP_VERTICES','RP_TEXTOS','RP_CENTROS','RP_RADIOS','RP_PK','RP_TABLAS','RP_EJES_NOMBRES','RP_ELEMENTOS','RP_TRANSICIONES']
    for layer in layers:
        if layer not in d.layers:d.layers.new(layer)
        l=d.layers.get(layer);l.dxf.color=7 if layer=='RP_TABLAS' else (5 if layer=='RP_VERTICES' else 9);l.dxf.true_color=0 if layer=='RP_TABLAS' else (VERTEX_RGB if layer=='RP_VERTICES' else GRAY_RGB)
    if 'ARIAL' not in d.styles:d.styles.new('ARIAL',dxfattribs={'font':'arial.ttf'})
    else:d.styles.get('ARIAL').dxf.font='arial.ttf'
    def attrs(layer):return dict(layer=layer,color=5 if layer=='RP_VERTICES' else 9,true_color=VERTEX_RGB if layer=='RP_VERTICES' else GRAY_RGB)
    def text(t,p,layer='RP_TEXTOS',height=None,angle=0,align=None,style='ARIAL'):
        e=m.add_text(t,dxfattribs={**attrs(layer),'height':gh if height is None else height,'style':style,'rotation':angle})
        e.set_placement(p,align=align or TextEntityAlignment.LEFT);return e
    def line(a,b,layer='RP_RADIOS'):return m.add_line(a,b,dxfattribs=attrs(layer))
    positions=label_layout(result,profile=profile);positions.update(label_overrides or {})
    for loc in result.locations:
        p=loc['p'];labels=loc['labels'];vertex=any(x.startswith('V') for x in labels);center=all(x.startswith('C') for x in labels)
        layer='RP_VERTICES' if vertex else ('RP_CENTROS' if center else 'RP_PUNTOS')
        size=label_height(loc,profile);m.add_circle(p,size*.20,dxfattribs=attrs(layer));m.add_point(p,dxfattribs=attrs(layer))
        label='='.join(labels);q=positions[label]
        text(label,q,layer=layer,height=size)
        if not center:line(p,q,layer)
    # Cotas radiales asociadas a cada arco: DIMENSION de tipo radio, sin explotar.
    dimname='RP_RADIAL_'+scale.replace(':','_')
    if dimname not in d.dimstyles:d.dimstyles.new(dimname)
    d.dimstyles.get(dimname).update_dxf_attribs(dict(dimscale=1.,dimlfac=1.,dimtxt=gh,dimasz=.75,dimcen=2.5,dimclrd=9,dimclre=9,dimclrt=9,dimtxsty='ARIAL',dimdec=3,dimpost='<>',dimtad=0))
    for c in result.curves:
        seg=c['s'];mid=seg.point(.5);radial=unit(sub(mid,seg.center));q=add(mid,mul(radial,4*gh))
        dim=m.add_radius_dim(center=seg.center,radius=seg.radius,location=q,dimstyle=dimname,dxfattribs=attrs('RP_RADIOS'))
        dim.set_arrows(blk=ezdxf.ARROWS.closed_filled,size=.75);dim.render()
        # El bloque de representación también lleva el color verdadero explícito.
        block=d.blocks.get(dim.dimension.dxf.geometry)
        for entity in block:
            if entity.dxf.is_supported('true_color'):entity.dxf.color=9;entity.dxf.true_color=GRAY_RGB;entity.dxf.layer='RP_RADIOS'
        if c['pi'] is not None and not c['roundabout']:
            for p in [seg.a,seg.b]:line(p,c['pi'])
    segrows=[]
    for axis in result.axes:
        pk=axis.pk0;text(axis.name.upper(),add(axis.segments[0].a,(0,-5*gh)),'RP_EJES_NOMBRES',gh)
        for j,seg in enumerate(axis.segments):
            segrows.append([axis.name,j+1,'ARCO' if seg.center else 'RECTA',f'{pk:.6f}',f'{pk+seg.length:.6f}',f'{seg.length:.6f}', '' if not seg.center else f'{seg.radius:.6f}',f'{az(seg.tangent(0)):.6f}',f'{az(seg.tangent(1)):.6f}'])
            # Marcas de longitud fija, independientes de la altura de los textos.
            step=profile['tick_interval'];first=math.ceil((pk-EPS)/step);last=math.floor((pk+seg.length+EPS)/step)
            for k in range(first,last+1):
                value=k*step
                # Una marca común al límite de dos elementos se dibuja una sola vez.
                if j>0 and abs(value-pk)<EPS:continue
                t=max(0.,min(1.,(value-pk)/seg.length));p=seg.point(t);normal=left(seg.tangent(t));half=profile['tick_length']/2
                line(add(p,mul(normal,-half)),add(p,mul(normal,half)),'RP_PK')
                if abs(value/profile['pk_interval']-round(value/profile['pk_interval']))<EPS:
                    text(format_pk(value),add(p,mul(normal,-3*profile['pk_height'])),'RP_PK',profile['pk_height'])
            pk+=seg.length
        for mark in transition_marks(axis,transition_short,transition_long):
            normal=mark['normal'];tangent=mark['tangent'];angle=readable_angle(normal)
            line(mark['start'],mark['end'],'RP_TRANSICIONES')
            # El texto de cada elemento ocupa su propio lado del límite, siguiendo el sentido del eje.
            middle=add(mark['p'],mul(normal,transition_long*.5));offset=gh*1.25
            for caption,side in [(mark['before'],-1),(mark['after'],1)]:
                text(caption,add(middle,mul(tangent,side*offset)),'RP_TRANSICIONES',gh,angle,TextEntityAlignment.MIDDLE_CENTER)
            end=add(mark['end'],mul(normal,profile['pk_height']))
            # Mantener el PK fuera del brazo largo también cuando la lectura gira 180 grados.
            direction=(math.cos(math.radians(angle)),math.sin(math.radians(angle)))
            alignment=TextEntityAlignment.MIDDLE_LEFT if dot(direction,normal)>0 else TextEntityAlignment.MIDDLE_RIGHT
            text(format_pk(mark['pk']),end,'RP_TRANSICIONES',profile['pk_height'],angle,alignment)
    # Tablas de coordenadas en la derecha del trazado, con el formato de tres columnas de la referencia.
    ps=[s.point(t) for a in result.axes for s in a.segments for t in [0,.25,.5,.75,1]]
    xmin=min(p[0] for p in ps);xmax=max(p[0] for p in ps);ymax=max(p[1] for p in ps)
    coordinate_tables(m,result,(xmax+30*h,ymax))
    # No se crean bases topográficas: no se han aportado observaciones de campo.
    d.set_modelspace_vport(height=max(100,ymax-min(p[1] for p in ps))*1.2,center=((xmin+xmax)/2,(ymax+min(p[1] for p in ps))/2))
    dest=out/'Replanteo.dxf';d.saveas(dest)
    write_csv(out/'Coordenadas.csv',['PUNTO','GRUPO','X','Y','EJES','PK_POR_EJE'],[[r['id'],r['grupo'],f"{r['x']:.6f}",f"{r['y']:.6f}",','.join(r['ejes']),json.dumps(r['pks'],ensure_ascii=False)] for r in result.rows])
    write_csv(out/'Curvas.csv',['CURVA','EJE','VERTICE','TE','TS','CENTRO_X','CENTRO_Y','RADIO','DESARROLLO','GIRO_g','TANGENTE','PK_TE','PK_TS'],[[f"C{c['id']}",c['eje'],c['vertex'],f"TE{c['id']}",f"TS{c['id']}",*c['center'],c['r'],c['length'],c['angle_g'],c['tangent'],c['pk0'],c['pk1']] for c in result.curves])
    write_csv(out/'Elementos.csv',['EJE','ELEMENTO','TIPO','PK_INICIO','PK_FIN','LONGITUD','RADIO','AZIMUT_ENTRADA_g','AZIMUT_SALIDA_g'],segrows)
    config=[dict(orden=i+1,handle=a.handle,nombre=a.name,capa=a.layer,pk0=a.pk0,longitud=a.length,cerrado=a.closed,glorieta=a.roundabout) for i,a in enumerate(result.axes)]
    (out/'Configuracion.json').write_text(json.dumps(dict(escala=scale,**profile,transition_short=transition_short,transition_long=transition_long,radial_arrow=.75,center_mark=2.5,annotation_rgb=[192,192,192],vertex_rgb=[0,0,250],tablas=TABLE_FORMAT),indent=2),encoding='utf-8')
    (out/'Ejes.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(ejes=len(result.axes),curvas=len(result.curves),vertices=len(result.groups['VÉRTICES']),tangencias=len(result.groups['TANGENTES']),incidencias=len(result.warnings))
    (out/'Revision.txt').write_text('REPLANTEA 0.4 — PRUEBA PARA REVISIÓN\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n\n'+ '\n'.join(result.warnings)+'\n\nNumeración según orden de ejes y sentido de recorrido. Perfil de escala en Configuracion.json. Sin ajuste de coordenadas ni radios. Ejes fuente conservados. Coordenadas en dibujo: 3 decimales; CSV: 6. PK independientes por entidad, origen 0 salvo configuración. Ejes sin nombre: E01… Revisión de continuidad y sentido pendiente. No se crean bases BR ni cotas Z. Salida exclusivamente XY. Numeración de curvas independiente de V; la relación está en Curvas.csv. Los textos CAD son editables. Uniones y cierres no se reparan automáticamente. Glorietas: clasificación manual documentada en Ejes.json; no generan V ni líneas auxiliares a PI. Los V propios de los accesos se conservan. Tablas ARIAL 2; filas 4; columnas 10/19.2289/19.2289; anclaje X/Y medio centro a 9.1366 derecha y 2.0211 abajo de la esquina de su celda. Identificadores azules; coordenadas y rejilla negras.\n',encoding='utf-8')
    return dest,summary

def label_layout(result,h=1.5,profile=None):
    boxes=[];positions={}
    for loc in result.locations:
        size=label_height(loc,profile) if profile else h
        p=loc['p'];label='='.join(loc['labels']);w=len(label)*size*.65
        if all(x.startswith('C') for x in loc['labels']):
            # Sin directriz: mantener el rótulo junto al centro geométrico.
            positions[label]=add(p,(size*.9,size*.9));continue
        for k in range(80):
            ang=(k%8)*math.pi/4;rr=size*(2+3*(k//8));q=add(p,(rr*math.cos(ang),rr*math.sin(ang)))
            box=(q[0],q[1],q[0]+w,q[1]+size*1.3)
            if all(box[2]<b[0] or box[0]>b[2] or box[3]<b[1] or box[1]>b[3] for b in boxes):break
        boxes.append(box);positions[label]=q
    return positions
