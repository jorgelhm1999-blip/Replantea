"""Aplicación de escritorio. Python 3.10+; iniciar con INICIAR.cmd en Windows."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import math,threading,queue,traceback,json
from motor import load,Result,export,label_layout,dist,profile_for,PROFILES,move_axes,place_axes,direction_marker

class App:
    def __init__(self,root):
        self.root=root;root.title('Replantea 0.5.0');root.geometry('1380x850')
        self.doc=None;self.axes=[];self.warnings=[];self.result=None;self.offsets={};self.scale=1;self.origin=(0,0);self.queue=queue.Queue();self.busy=False
        self.status=tk.StringVar(value='Abra un DWG o DXF. No se modificará el archivo original.')
        self.drawing_scale=tk.StringVar(value='1:2000');self.profile=profile_for('1:2000');self.centers=tk.BooleanVar(value=False)
        self.transition_short=tk.StringVar(value='3.5');self.transition_long=tk.StringVar(value='32.646')
        self.row_drag=None;self.drag_scroll_job=None
        top=ttk.Frame(root,padding=10);top.pack(fill='x')
        ttk.Button(top,text='Abrir DWG / DXF',command=self.open).pack(side='left')
        ttk.Label(top,text='  Escala de salida ').pack(side='left')
        self.scale_combo=ttk.Combobox(top,textvariable=self.drawing_scale,values=list(PROFILES),state='readonly',width=9)
        self.scale_combo.pack(side='left');self.scale_combo.bind('<<ComboboxSelected>>',self.change_profile)
        ttk.Button(top,text='Calcular / actualizar',command=self.calculate).pack(side='left',padx=10)
        ttk.Button(top,text='Exportar DXF y tablas',command=self.save).pack(side='left',padx=10)
        ttk.Checkbutton(top,text='Mostrar centros',variable=self.centers,command=self.draw).pack(side='left')
        ttk.Button(top,text='Encuadrar',command=self.fit).pack(side='right')
        self.profile_note=tk.StringVar();ttk.Label(root,textvariable=self.profile_note,padding=(10,0,10,6)).pack(fill='x');self.update_profile_note()
        transition_bar=ttk.Frame(root,padding=(10,0,10,6));transition_bar.pack(fill='x')
        ttk.Label(transition_bar,text='Marca recta / curva · Brazo corto (m) ').pack(side='left')
        ttk.Entry(transition_bar,textvariable=self.transition_short,width=7).pack(side='left')
        ttk.Label(transition_bar,text='  Brazo largo (m) ').pack(side='left')
        ttk.Entry(transition_bar,textvariable=self.transition_long,width=8).pack(side='left')
        ttk.Label(transition_bar,text='  · PK en el extremo · Textos alineados con la marca').pack(side='left')
        pan=ttk.Panedwindow(root,orient='horizontal');pan.pack(fill='both',expand=True,padx=10)
        left=ttk.Frame(pan);right=ttk.Frame(pan);pan.add(left,weight=1);pan.add(right,weight=3)
        ttk.Label(left,text='Ejes · Seleccionar: resaltar · Arrastrar filas o Mayús + ↑ / ↓: ordenar').pack(anchor='w')
        self.tree=ttk.Treeview(left,columns=('order','on','name','pk','long','arcs','roundabout'),show='headings',selectmode='extended',height=15)
        for c,t,w in [('order','Orden',42),('on','Usar',45),('name','Eje',70),('pk','PK inicial',70),('long','Longitud',80),('arcs','Arcos',45),('roundabout','Glorieta',65)]:self.tree.heading(c,text=t);self.tree.column(c,width=w,anchor='center')
        self.tree.pack(fill='both',expand=True);self.tree.bind('<Double-1>',self.edit);self.tree.bind('<<TreeviewSelect>>',lambda e:self.draw())
        self.tree.bind('<Shift-Up>',lambda e:self.reorder(-1));self.tree.bind('<Shift-Down>',lambda e:self.reorder(1))
        self.tree.bind('<ButtonPress-1>',self.row_press);self.tree.bind('<B1-Motion>',self.row_motion);self.tree.bind('<ButtonRelease-1>',self.row_release)
        self.drop_line=tk.Frame(self.tree,height=3,bg='#f97316')
        controls=ttk.Frame(left);controls.pack(fill='x',pady=5)
        ttk.Button(controls,text='Activar / desactivar',command=self.toggle).pack(side='left')
        ttk.Button(controls,text='Invertir sentido',command=self.reverse).pack(side='left',padx=5)
        ttk.Button(controls,text='↑ Subir',command=lambda:self.reorder(-1)).pack(side='left',padx=2)
        ttk.Button(controls,text='↓ Bajar',command=lambda:self.reorder(1)).pack(side='left',padx=2)
        roundabout_controls=ttk.Frame(left);roundabout_controls.pack(fill='x',pady=(0,5))
        ttk.Button(roundabout_controls,text='Marcar glorieta',command=lambda:self.set_roundabout(True)).pack(side='left')
        ttk.Button(roundabout_controls,text='Quitar glorieta',command=lambda:self.set_roundabout(False)).pack(side='left',padx=5)
        ttk.Label(left,text='Doble clic: activar, nombre, PK o Glorieta. Los ejes de glorieta no generan vértices V ni líneas hacia PI; conservan centros, tangencias y PK.',wraplength=540).pack(anchor='w')
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
    def update_profile_note(self):
        p=profile_for(self.drawing_scale.get())
        self.profile_note.set(f"Vértices ARIAL: {p['vertex_height']:g} m · PK / RECTA / R ARIAL: {p['pk_height']:g} m · PK cada 100 m · Marcas cada {p['tick_interval']:g} m, longitud total 3 m")
    def change_profile(self,event=None):
        if self.busy:
            self.drawing_scale.set(getattr(self,'export_scale','1:2000'));return
        self.profile=profile_for(self.drawing_scale.get());self.update_profile_note();self.offsets={}
        if self.axes:self.calculate(fit_view=False)
        else:self.draw()
    def refresh(self):
        selected=self.tree.selection();focus=self.tree.focus()
        self.tree.delete(*self.tree.get_children())
        for i,a in enumerate(self.axes):self.tree.insert('', 'end',iid=a.handle,values=(i+1,'Sí' if a.selected else 'No',a.name,f'{a.pk0:.3f}',f'{a.length:.3f}',sum(s.center is not None for s in a.segments),'Sí' if a.roundabout else 'No'))
        self.tree.selection_set([h for h in selected if self.tree.exists(h)])
        if self.tree.exists(focus):self.tree.focus(focus)
    def axis(self,handle):return next(a for a in self.axes if a.handle==handle)
    def reorder(self,direction):
        if self.busy or not self.tree.selection():return 'break'
        selected=self.tree.selection();move_axes(self.axes,selected,direction);self.refresh()
        focus=self.tree.focus() or selected[0];self.tree.see(focus)
        self.calculate(fit_view=False);return 'break'
    def row_press(self,event):
        self.clear_row_drag()
        row=self.tree.identify_row(event.y)
        if self.busy or not row or self.tree.identify_region(event.x,event.y) not in ('cell','tree'):return
        selected=self.tree.selection()
        self.row_drag=dict(handles=list(selected) if row in selected else [row],source=row,start=(event.x,event.y),y=event.y,moved=False,slot=None,scroll=0)
    def clear_row_drag(self):
        if self.drag_scroll_job is not None:
            self.root.after_cancel(self.drag_scroll_job);self.drag_scroll_job=None
        self.row_drag=None
        if hasattr(self,'drop_line'):self.drop_line.place_forget()
    def update_drop_target(self):
        drag=self.row_drag
        if not drag:return
        y=drag['y'];children=self.tree.get_children();row=self.tree.identify_row(y)
        if row:
            box=self.tree.bbox(row);after=y>=box[1]+box[3]/2
            drag['slot']=children.index(row)+int(after)
            self.drop_line.place(x=0,y=box[1]+(box[3] if after else 0),relwidth=1,height=3)
        elif children:
            drag['slot']=0 if y<30 else len(children)
            self.drop_line.place_forget()
    def row_autoscroll(self):
        self.drag_scroll_job=None
        if self.row_drag and self.row_drag['moved'] and self.row_drag['scroll']:
            self.tree.yview_scroll(self.row_drag['scroll'],'units');self.update_drop_target()
            self.drag_scroll_job=self.root.after(90,self.row_autoscroll)
    def row_motion(self,event):
        drag=self.row_drag
        if not drag or self.busy:return
        if not drag['moved'] and math.hypot(event.x-drag['start'][0],event.y-drag['start'][1])<6:return
        drag['moved']=True;drag['y']=event.y;self.tree.selection_set(drag['handles'])
        drag['scroll']=-1 if event.y<42 else (1 if event.y>self.tree.winfo_height()-24 else 0)
        self.update_drop_target()
        if self.drag_scroll_job is None and drag['scroll']:self.drag_scroll_job=self.root.after(90,self.row_autoscroll)
        return 'break'
    def drop_rows(self,handles,slot):
        place_axes(self.axes,handles,slot);self.refresh();self.tree.selection_set(handles)
        if handles:self.tree.focus(handles[0]);self.tree.see(handles[0])
        self.calculate(fit_view=False)
    def row_release(self,event):
        drag=self.row_drag
        if not drag:return
        moved=drag['moved'];handles=drag['handles'];slot=drag['slot'];self.clear_row_drag()
        if moved:
            if not self.busy and slot is not None:self.drop_rows(handles,slot)
            return 'break'
    def edit(self,e):
        row=self.tree.identify_row(e.y);col=self.tree.identify_column(e.x)
        if not row or self.busy:return
        a=self.axis(row)
        if col=='#7':self.set_roundabout(not a.roundabout,[row]);return
        if col=='#2':a.selected=not a.selected;self.result=None;self.offsets={};self.refresh();self.draw();return
        if col not in ('#3','#4'):return
        box=self.tree.bbox(row,col);entry=ttk.Entry(self.tree);entry.place(x=box[0],y=box[1],width=box[2],height=box[3]);entry.insert(0,a.name if col=='#3' else str(a.pk0));entry.select_range(0,'end');entry.focus_set()
        def accept(event=None):
            try:
                value=entry.get().strip()
                if col=='#3':
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
        for handle in self.tree.selection():self.axis(handle).selected=not self.axis(handle).selected
        self.result=None;self.offsets={};self.refresh();self.draw()
    def reverse(self):
        if self.busy:return
        for handle in self.tree.selection():self.axis(handle).reverse()
        self.refresh();self.calculate(fit_view=False)
    def set_roundabout(self,value,handles=None):
        if self.busy:return
        handles=list(self.tree.selection() if handles is None else handles)
        if not handles:return
        for handle in handles:self.axis(handle).roundabout=bool(value)
        self.refresh();self.calculate(fit_view=False)
    def calculate(self,fit_view=True):
        if self.busy or not self.axes:return
        try:
            if not any(a.selected for a in self.axes):raise ValueError('Seleccione al menos un eje.')
            self.profile=profile_for(self.drawing_scale.get());self.export_scale=self.drawing_scale.get()
            self.result=Result(self.axes,self.warnings);self.offsets={}
            self.log.delete('1.0','end');self.log.insert('end','Numeración según orden de filas y sentido de cada eje. Los puntos compartidos conservan el primer número asignado. PK independiente por entidad. No se unen ejes ni se cierran bucles.\n\n'+'\n'.join(self.result.warnings))
            self.status.set(f'{len(self.result.axes)} ejes · {len(self.result.curves)} curvas · {len(self.result.rows)} coordenadas · {len(self.result.warnings)} incidencias · Escala {self.export_scale}')
            if fit_view:self.fit()
            else:self.draw()
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
        selected=set(self.tree.selection())
        # Los ejes seleccionados se trazan al final, para que destaquen en los cruces.
        for a in sorted(self.axes,key=lambda a:a.handle in selected):
            active=a.handle in selected
            if not a.selected and not active:continue
            for s in a.segments:
                n=max(2,int(abs(s.sweep)*40)) if s.center else 2;points=[self.xy(s.point(k/(n-1))) for k in range(n)]
                self.canvas.create_line(*[v for p in points for v in p],fill='#f97316' if active else '#64748b',width=5 if active else 2,tags=('selected_axis' if active else 'axis',),dash=() if a.selected else (6,3))
            if active:
                midpoint,tangent=direction_marker(a);x,y=self.xy(midpoint);vx,vy=tangent[0],-tangent[1]
                self.canvas.create_line(x-24*vx,y-24*vy,x+24*vx,y+24*vy,fill='#ea580c',width=4,arrow='last',arrowshape=(14,17,7),tags=('direction_arrow',))
            x,y=self.xy(a.segments[0].a);self.canvas.create_text(x,y+16,text=a.name,fill='#ea580c' if active else '#9a6700',anchor='nw',font=('Arial',10,'bold' if active else 'normal'))
        if self.result:
            positions=label_layout(self.result,profile=self.profile);positions.update(self.offsets)
            for loc in self.result.locations:
                if not self.centers.get() and all(x.startswith('C') for x in loc['labels']):continue
                vertex=any(x.startswith('V') for x in loc['labels']);center=all(x.startswith('C') for x in loc['labels']);color='#0000fa' if vertex or center else '#999999'
                key='='.join(loc['labels']);p=self.xy(loc['p']);q=self.xy(positions[key]);r=max(2.5,self.scale) if center else 2.5
                self.canvas.create_oval(p[0]-r,p[1]-r,p[0]+r,p[1]+r,outline=color)
                if not all(x.startswith('C') for x in loc['labels']):self.canvas.create_line(*p,*q,fill=color)
                item=self.canvas.create_text(*q,text=key,anchor='w' if center else 'sw',font=('Arial',10 if vertex else 9),fill=color);self.text_items[item]=key
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
        if self.drawing_scale.get()!=self.export_scale:
            messagebox.showinfo('Exportación','Actualice el cálculo con la escala seleccionada.');return
        try:
            short=float(self.transition_short.get().replace(',','.'));long=float(self.transition_long.get().replace(',','.'))
            if not all(math.isfinite(v) and v>0 for v in (short,long)):raise ValueError()
        except ValueError:
            messagebox.showerror('Exportación','Los brazos de transición deben ser longitudes positivas en metros.');return
        folder=filedialog.askdirectory(title='Carpeta de salida')
        if not folder:return
        output=Path(folder)/'Replantea_salida'
        if output.exists() and not messagebox.askyesno('Archivos existentes','Se sustituirán los archivos de Replantea_salida. ¿Continuar?'):return
        def done(val):self.status.set('Exportado: '+str(val[0]));messagebox.showinfo('Exportación terminada',str(val[0])+'\n\nRevise las incidencias y las etiquetas en CAD.')
        self.run(lambda:export(self.doc,self.result,output,label_overrides=self.offsets,scale=self.export_scale,transition_short=short,transition_long=long),done)

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
