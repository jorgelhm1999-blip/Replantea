"""Aplicación de escritorio. Python 3.10+; iniciar con INICIAR.cmd en Windows."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import math,threading,queue,traceback,json
from motor import load,Result,export,label_layout,dist

class App:
    def __init__(self,root):
        self.root=root;root.title('Replantea 0.1 · Prueba de replanteo');root.geometry('1380x850')
        self.doc=None;self.axes=[];self.warnings=[];self.result=None;self.offsets={};self.scale=1;self.origin=(0,0);self.queue=queue.Queue();self.busy=False
        self.status=tk.StringVar(value='Abra un DWG o DXF. No se modificará el archivo original.')
        self.height=tk.StringVar(value='1.5');self.step=tk.StringVar(value='100');self.centers=tk.BooleanVar(value=False)
        top=ttk.Frame(root,padding=10);top.pack(fill='x')
        ttk.Button(top,text='Abrir DWG / DXF',command=self.open).pack(side='left')
        ttk.Label(top,text='  Texto (m)').pack(side='left');ttk.Entry(top,textvariable=self.height,width=6).pack(side='left')
        ttk.Label(top,text='  Intervalo PK (m)').pack(side='left');ttk.Entry(top,textvariable=self.step,width=6).pack(side='left')
        ttk.Button(top,text='Calcular / actualizar',command=self.calculate).pack(side='left',padx=10)
        ttk.Button(top,text='Exportar DXF y tablas',command=self.save).pack(side='left',padx=10)
        ttk.Checkbutton(top,text='Mostrar centros',variable=self.centers,command=self.draw).pack(side='left')
        ttk.Button(top,text='Encuadrar',command=self.fit).pack(side='right')
        pan=ttk.Panedwindow(root,orient='horizontal');pan.pack(fill='both',expand=True,padx=10)
        left=ttk.Frame(pan);right=ttk.Frame(pan);pan.add(left,weight=1);pan.add(right,weight=3)
        ttk.Label(left,text='Ejes · Doble clic: nombre, PK o selección').pack(anchor='w')
        self.tree=ttk.Treeview(left,columns=('on','name','pk','long','arcs'),show='headings',selectmode='extended',height=15)
        for c,t,w in [('on','Usar',45),('name','Eje',85),('pk','PK inicial',75),('long','Longitud',95),('arcs','Arcos',50)]:self.tree.heading(c,text=t);self.tree.column(c,width=w,anchor='center')
        self.tree.pack(fill='both',expand=True);self.tree.bind('<Double-1>',self.edit)
        controls=ttk.Frame(left);controls.pack(fill='x',pady=5)
        ttk.Button(controls,text='Activar / desactivar',command=self.toggle).pack(side='left')
        ttk.Button(controls,text='Invertir sentido',command=self.reverse).pack(side='left',padx=5)
        ttk.Label(left,text='Incidencias y criterios de cálculo').pack(anchor='w')
        self.log=tk.Text(left,height=14,wrap='word',font=('Segoe UI',9));self.log.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(right,bg='#f8fafc',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw());self.canvas.bind('<MouseWheel>',self.zoom)
        self.canvas.bind('<Button-4>',lambda e:self.zoom(e,1.2));self.canvas.bind('<Button-5>',lambda e:self.zoom(e,1/1.2))
        self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<B1-Motion>',self.drag);self.canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'active',None))
        ttk.Label(root,text='Rueda: zoom · Arrastrar fondo: desplazar · Arrastrar una etiqueta: recolocar · Coordenadas XY, sin ajuste de ejes.',padding=6).pack(fill='x')
        ttk.Label(root,textvariable=self.status,padding=6).pack(fill='x')
        self.active=None;self.last=(0,0);self.text_items={};root.after(100,self.poll)
    def run(self,fn,done):
        if self.busy:return
        self.busy=True;self.status.set('Procesando…')
        def job():
            try:self.queue.put((done,fn(),None))
            except Exception:self.queue.put((done,None,traceback.format_exc()))
        threading.Thread(target=job,daemon=True).start()
    def poll(self):
        try:
            callback,val,err=self.queue.get_nowait();self.busy=False
            if err:self.status.set('No se ha completado la operación.');messagebox.showerror('Replantea',err)
            else:callback(val)
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def open(self):
        if self.busy:return
        p=filedialog.askopenfilename(filetypes=[('Ejes CAD','*.dwg *.dxf')])
        if not p:return
        def done(val):
            self.doc,self.axes,self.warnings=val;self.result=None;self.offsets={};self.refresh();self.calculate();self.fit()
        self.run(lambda:load(p),done)
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,a in enumerate(self.axes):self.tree.insert('', 'end',iid=str(i),values=('Sí' if a.selected else 'No',a.name,f'{a.pk0:.3f}',f'{a.length:.3f}',sum(s.center is not None for s in a.segments)))
    def edit(self,e):
        row=self.tree.identify_row(e.y);col=self.tree.identify_column(e.x)
        if not row or self.busy:return
        a=self.axes[int(row)]
        if col=='#1':a.selected=not a.selected;self.result=None;self.offsets={};self.refresh();self.draw();return
        if col not in ('#2','#3'):return
        box=self.tree.bbox(row,col);entry=ttk.Entry(self.tree);entry.place(x=box[0],y=box[1],width=box[2],height=box[3]);entry.insert(0,a.name if col=='#2' else str(a.pk0));entry.select_range(0,'end');entry.focus_set()
        def accept(event=None):
            try:
                value=entry.get().strip()
                if col=='#2':
                    if not value or any(x is not a and x.name==value for x in self.axes):raise ValueError('Nombre vacío o duplicado.')
                    a.name=value
                else:
                    v=float(value.replace(',','.'))
                    if not math.isfinite(v):raise ValueError('PK no válido.')
                    a.pk0=v
                entry.destroy();self.result=None;self.offsets={};self.refresh();self.draw()
            except ValueError as ex:messagebox.showerror('Dato no válido',str(ex))
        entry.bind('<Return>',accept);entry.bind('<Escape>',lambda e:entry.destroy())
    def toggle(self):
        if self.busy:return
        for i in self.tree.selection():self.axes[int(i)].selected=not self.axes[int(i)].selected
        self.result=None;self.offsets={};self.refresh();self.draw()
    def reverse(self):
        if self.busy:return
        for i in self.tree.selection():self.axes[int(i)].reverse()
        self.refresh();self.calculate()
    def calculate(self):
        if self.busy or not self.axes:return
        try:
            h=float(self.height.get().replace(',','.'));step=float(self.step.get().replace(',','.'))
            if not math.isfinite(h) or not math.isfinite(step) or h<=0 or step<0:raise ValueError('Altura positiva; intervalo PK no negativo (0 desactiva los PK).')
            if not any(a.selected for a in self.axes):raise ValueError('Seleccione al menos un eje.')
            self.result=Result(self.axes,self.warnings);self.offsets={};self.h=h;self.pkstep=step
            self.log.delete('1.0','end');self.log.insert('end','PK independiente por entidad. Numeración provisional. No se unen ejes ni se cierran bucles.\n\n'+'\n'.join(self.result.warnings))
            self.status.set(f'{len(self.result.axes)} ejes · {len(self.result.curves)} curvas · {len(self.result.rows)} coordenadas · {len(self.result.warnings)} incidencias')
            self.fit()
        except Exception as ex:messagebox.showerror('Cálculo',str(ex))
    def xy(self,p):return ((p[0]-self.origin[0])*self.scale,(self.origin[1]-p[1])*self.scale)
    def world(self,x,y):return (x/self.scale+self.origin[0],self.origin[1]-y/self.scale)
    def fit(self):
        axes=self.result.axes if self.result else self.axes
        ps=[s.point(t) for a in axes for s in a.segments for t in [0,.25,.5,.75,1]]
        if not ps:return
        self.canvas.update_idletasks();w=max(100,self.canvas.winfo_width());h=max(100,self.canvas.winfo_height())
        x0=min(p[0] for p in ps);x1=max(p[0] for p in ps);y0=min(p[1] for p in ps);y1=max(p[1] for p in ps)
        self.scale=.85*min(w/max(x1-x0,1),h/max(y1-y0,1));self.origin=((x0+x1)/2-w/(2*self.scale),(y0+y1)/2+h/(2*self.scale));self.draw()
    def draw(self):
        self.canvas.delete('all');self.text_items={}
        axes=self.result.axes if self.result else self.axes
        for a in axes:
            if not a.selected:continue
            for s in a.segments:
                n=max(2,int(abs(s.sweep)*40)) if s.center else 2;points=[self.xy(s.point(k/(n-1))) for k in range(n)]
                self.canvas.create_line(*[v for p in points for v in p],fill='#1e293b',width=2)
            x,y=self.xy(a.segments[0].a);self.canvas.create_text(x,y+16,text=a.name,fill='#9a6700',anchor='nw')
        if self.result:
            positions=label_layout(self.result,self.h);positions.update(self.offsets)
            for loc in self.result.locations:
                if not self.centers.get() and all(x.startswith('C') for x in loc['labels']):continue
                key='='.join(loc['labels']);p=self.xy(loc['p']);q=self.xy(positions[key]);r=2.5
                self.canvas.create_oval(p[0]-r,p[1]-r,p[0]+r,p[1]+r,outline='#2563eb')
                self.canvas.create_line(*p,*q,fill='#94a3b8')
                item=self.canvas.create_text(*q,text=key,anchor='sw',font=('Segoe UI',9),fill='#1d4ed8');self.text_items[item]=key
    def zoom(self,e,factor=None):
        if not self.axes:return
        f=factor or (1.2 if e.delta>0 else 1/1.2);p=self.world(e.x,e.y);self.scale=max(.0001,min(10000,self.scale*f));self.origin=(p[0]-e.x/self.scale,p[1]+e.y/self.scale);self.draw()
    def press(self,e):
        self.last=(e.x,e.y);self.active=None
        for item in reversed(self.canvas.find_overlapping(e.x-3,e.y-3,e.x+3,e.y+3)):
            if item in self.text_items:self.active=self.text_items[item];break
    def drag(self,e):
        if self.active:self.offsets[self.active]=self.world(e.x,e.y)
        else:
            dx=e.x-self.last[0];dy=e.y-self.last[1];self.origin=(self.origin[0]-dx/self.scale,self.origin[1]+dy/self.scale)
        self.last=(e.x,e.y);self.draw()
    def save(self):
        if self.busy:return
        # Recalcular antes de exportar si han cambiado ejes, nombres o PK.
        if not self.result:messagebox.showinfo('Exportación','Calcule primero el replanteo.');return
        try:
            if float(self.height.get().replace(',','.'))!=self.h or float(self.step.get().replace(',','.'))!=self.pkstep:
                messagebox.showinfo('Exportación','Han cambiado la altura o el intervalo. Pulse Calcular / actualizar antes de exportar.');return
        except ValueError:
            messagebox.showerror('Exportación','Altura o intervalo no válidos.');return
        folder=filedialog.askdirectory(title='Carpeta de salida')
        if not folder:return
        output=Path(folder)/'Replantea_salida'
        if output.exists() and not messagebox.askyesno('Archivos existentes','Se sustituirán los archivos de Replantea_salida. ¿Continuar?'):return
        def done(val):self.status.set('Exportado: '+str(val[0]));messagebox.showinfo('Exportación terminada',str(val[0])+'\n\nRevise las incidencias y las etiquetas en CAD.')
        self.run(lambda:export(self.doc,self.result,output,self.h,self.pkstep,self.offsets),done)

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
