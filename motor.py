"""Replantea 0.1: replanteo exacto de rectas y arcos planos; no modifica ejes."""
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
        for axis in self.axes:
            pk=axis.pk0
            for j,s in enumerate(axis.segments):
                if s.center is not None:
                    self.curve_n+=1;n=self.curve_n
                    self.point(f'TE{n}',s.a,'TANGENTES',axis.name,pk);self.point(f'TS{n}',s.b,'TANGENTES',axis.name,pk+s.length)
                    self.point(f'C{n}',s.center,'CENTROS DE CURVAS',axis.name,None)
                    pi=s.pi();vertex=''
                    if pi is not None:
                        vertex=self.vertex(pi,axis.name,None)
                    else:self.warnings.append(f'{axis.name}: curva C{n}, tangentes paralelas; vértice de tangentes no definido.')
                    self.curves.append(dict(id=n,eje=axis.name,segment=j+1,pk0=pk,pk1=pk+s.length,r=s.radius,length=s.length,angle_g=s.sweep*200/math.pi,center=s.center,pi=pi,vertex=vertex,tangent=None if pi is None else dist(pi,s.a),s=s))
                else:
                    self.vertex(s.a,axis.name,pk);self.vertex(s.b,axis.name,pk+s.length)
                pk+=s.length
        # Encuentros exactos entre ejes, también en interiores de segmentos.
        for i,a in enumerate(self.axes):
            for b in self.axes[i+1:]:
                pa=a.pk0
                for s in a.segments:
                    pb=b.pk0
                    for t in b.segments:
                        for p in intersections(s,t):
                            v=self.vertex(p,a.name,pa+s.parameter(p)*s.length);self.point(v,p,'VÉRTICES',b.name,pb+t.parameter(p)*t.length)
                        pb+=t.length
                    pa+=s.length
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

def export(doc,result,out,text_height=1.5,pk_step=100,label_overrides=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    # Copia independiente; los objetos fuente conservan todos sus vértices y bulges.
    import copy
    d=copy.deepcopy(doc);m=d.modelspace();h=float(text_height)
    if h<=0:raise ValueError('La altura de texto debe ser positiva.')
    layers={'RP_PUNTOS':5,'RP_TEXTOS':5,'RP_CENTROS':5,'RP_RADIOS':8,'RP_PK':4,'RP_TABLAS':7,'RP_EJES_NOMBRES':2}
    for layer,col in layers.items():
        if layer not in d.layers:d.layers.new(layer,dxfattribs={'color':col})
    def text(t,p,layer='RP_TEXTOS',height=h,angle=0,align=None):
        e=m.add_text(t,dxfattribs={'height':height,'layer':layer,'rotation':angle})
        e.set_placement(p,align=align or TextEntityAlignment.LEFT);return e
    def line(a,b,layer='RP_RADIOS'):m.add_line(a,b,dxfattribs={'layer':layer})
    # Ubicación simple de rótulos con comprobación de cajas; se pueden desplazar en CAD.
    positions=label_layout(result,h)
    positions.update(label_overrides or {})
    for loc in result.locations:
        p=loc['p'];labels=loc['labels'];is_center=all(x.startswith('C') for x in labels)
        layer='RP_CENTROS' if is_center else 'RP_PUNTOS'
        m.add_circle(p,h*.25,dxfattribs={'layer':layer});m.add_point(p,dxfattribs={'layer':layer})
        label='='.join(labels);q=positions[label]
        text(label,q,layer='RP_CENTROS' if is_center else 'RP_TEXTOS');line(p,q,'RP_TEXTOS')
    for c in result.curves:
        s=c['s'];mid=s.point(.5);radial=unit(sub(mid,s.center));q=add(mid,mul(radial,4*h))
        text(f"R{c['id']}={c['r']:.3f}",q,height=h*.85)
        text(f"L={c['length']:.3f}",add(q,(0,-h*1.2)),height=h*.7)
        if c['pi'] is not None and abs(s.sweep)<math.pi:
            text(f"TE={c['tangent']:.3f}  TS={c['tangent']:.3f}",add(q,(0,-h*2.4)),height=h*.7)
            text(f"{200-abs(c['angle_g']):.4f}g",add(c['pi'],(h,-2*h)),height=h*.75)
        if c['pi'] is not None:
            # Pequeñas prolongaciones de tangentes para reconocer el vértice geométrico.
            for p in [s.a,s.b]:line(p,c['pi'])
    segrows=[]
    for a in result.axes:
        pk=a.pk0
        text(a.name,add(a.segments[0].a,(0,-5*h)),'RP_EJES_NOMBRES',h*1.6)
        for j,s in enumerate(a.segments):
            segrows.append([a.name,j+1,'ARCO' if s.center else 'RECTA',f'{pk:.6f}',f'{pk+s.length:.6f}',f'{s.length:.6f}', '' if not s.center else f'{s.radius:.6f}',f'{az(s.tangent(0)):.6f}',f'{az(s.tangent(1)):.6f}'])
            if s.center is None:
                mid=s.point(.5);t=s.tangent(0);angle=math.degrees(math.atan2(t[1],t[0]));angle=angle+180 if angle>90 or angle<-90 else angle
                text(f'L={s.length:.3f}',add(mid,mul(left(t),3*h)),height=h*.85,angle=angle)
            if pk_step>0:
                vals=[pk] if j==0 else []
                k=math.floor(pk/pk_step)+1
                while k*pk_step<pk+s.length-EPS:vals.append(k*pk_step);k+=1
                vals.append(pk+s.length)
                for v in vals:
                    t=(v-pk)/s.length;p=s.point(t);normal=left(s.tangent(t));line(add(p,mul(normal,-h)),add(p,mul(normal,h)),'RP_PK')
                    text(f'{int(v//1000)}+{v%1000:07.3f}',add(p,mul(normal,-4*h)),'RP_PK',h*.7)
            pk+=s.length
    # Tablas de coordenadas en la derecha del trazado, con el formato de tres columnas de la referencia.
    ps=[s.point(t) for a in result.axes for s in a.segments for t in [0,.25,.5,.75,1]]
    xmin=min(p[0] for p in ps);xmax=max(p[0] for p in ps);ymax=max(p[1] for p in ps)
    tx=xmax+30*h;ty=ymax;cw=[12*h,40*h,40*h];rh=3*h;tw=sum(cw)
    text('COORDENADAS REPLANTEO',(tx+tw*1.6,ty+9*h),'RP_TABLAS',h*1.8,align=TextEntityAlignment.CENTER)
    for n,g in enumerate(['VÉRTICES','TANGENTES','CENTROS DE CURVAS']):
        x=tx+n*(tw+10*h);rows=result.groups[g];y=ty
        text(g,(x+tw/2,y+4*h),'RP_TABLAS',h*1.2,align=TextEntityAlignment.CENTER)
        headers=['','X','Y'];table=[headers]+[[r['id'],f"{r['x']:.3f}",f"{r['y']:.3f}"] for r in rows]
        for k,row in enumerate(table):
            yy=y-k*rh
            for j,cell in enumerate(row):
                xx=x+sum(cw[:j]);text(str(cell),(xx+cw[j]/2,yy-rh*.7),'RP_TABLAS',h,align=TextEntityAlignment.CENTER)
        for k in range(len(table)+1):line((x,y-k*rh),(x+tw,y-k*rh),'RP_TABLAS')
        for j in range(4):xx=x+sum(cw[:j]);line((xx,y),(xx,y-len(table)*rh),'RP_TABLAS')
    # No se crean bases topográficas: no se han aportado observaciones de campo.
    d.set_modelspace_vport(height=max(100,ymax-min(p[1] for p in ps))*1.2,center=((xmin+xmax)/2,(ymax+min(p[1] for p in ps))/2))
    dest=out/'Replanteo.dxf';d.saveas(dest)
    write_csv(out/'Coordenadas.csv',['PUNTO','GRUPO','X','Y','EJES','PK_POR_EJE'],[[r['id'],r['grupo'],f"{r['x']:.6f}",f"{r['y']:.6f}",','.join(r['ejes']),json.dumps(r['pks'],ensure_ascii=False)] for r in result.rows])
    write_csv(out/'Curvas.csv',['CURVA','EJE','VERTICE','TE','TS','CENTRO_X','CENTRO_Y','RADIO','DESARROLLO','GIRO_g','TANGENTE','PK_TE','PK_TS'],[[f"C{c['id']}",c['eje'],c['vertex'],f"TE{c['id']}",f"TS{c['id']}",*c['center'],c['r'],c['length'],c['angle_g'],c['tangent'],c['pk0'],c['pk1']] for c in result.curves])
    write_csv(out/'Elementos.csv',['EJE','ELEMENTO','TIPO','PK_INICIO','PK_FIN','LONGITUD','RADIO','AZIMUT_ENTRADA_g','AZIMUT_SALIDA_g'],segrows)
    config=[dict(handle=a.handle,nombre=a.name,capa=a.layer,pk0=a.pk0,longitud=a.length,cerrado=a.closed) for a in result.axes]
    (out/'Ejes.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(ejes=len(result.axes),curvas=len(result.curves),vertices=len(result.groups['VÉRTICES']),tangencias=len(result.groups['TANGENTES']),incidencias=len(result.warnings))
    (out/'Revision.txt').write_text('REPLANTEA 0.1 — PRUEBA PARA REVISIÓN\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n\n'+ '\n'.join(result.warnings)+'\n\nSin ajuste de coordenadas ni radios. Ejes fuente conservados. Coordenadas en dibujo: 3 decimales; CSV: 6. PK independientes por entidad, origen 0 salvo configuración. Ejes sin nombre: E01… Revisión de continuidad y sentido pendiente. No se crean bases BR ni cotas Z. Salida exclusivamente XY. Numeración de curvas independiente de V; la relación está en Curvas.csv. Los textos CAD son editables. Uniones y cierres no se reparan automáticamente.\n',encoding='utf-8')
    return dest,summary

def label_layout(result,h=1.5):
    boxes=[];positions={}
    for loc in result.locations:
        p=loc['p'];label='='.join(loc['labels']);w=len(label)*h*.65
        for k in range(80):
            ang=(k%8)*math.pi/4;rr=h*(2+3*(k//8));q=add(p,(rr*math.cos(ang),rr*math.sin(ang)))
            box=(q[0],q[1],q[0]+w,q[1]+h*1.3)
            if all(box[2]<b[0] or box[0]>b[2] or box[3]<b[1] or box[1]>b[3] for b in boxes):break
        boxes.append(box);positions[label]=q
    return positions
