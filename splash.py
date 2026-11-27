"""Reproduce la introducción aprobada y entrega el control a la ventana principal."""
import time,logging
import tkinter as tk
from PIL import ImageTk
from intro import Intro,PillowRenderer,DURATION
from marca import apply_icon

class Splash:
    def __init__(self,root,on_done,duration=DURATION):
        self.root=root;self.on_done=on_done;self.duration=duration;self.done=False;self.job=None
        self.window=tk.Toplevel(root);self.window.withdraw();self.window.title('Replantea')
        apply_icon(self.window)
        self.width=min(1100,max(640,root.winfo_screenwidth()-80));self.height=min(660,max(400,root.winfo_screenheight()-100))
        x=(root.winfo_screenwidth()-self.width)//2;y=(root.winfo_screenheight()-self.height)//2
        self.window.geometry(f'{self.width}x{self.height}+{x}+{y}');self.window.resizable(False,False)
        self.window.configure(bg='#040a13')
        self.canvas=tk.Canvas(self.window,bg='#040a13',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.intro=Intro();self.renderer=PillowRenderer();self.start=time.perf_counter();self.photo=None
        self.window.bind('<Escape>',lambda e:self.finish())
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.skip=tk.Button(self.window,text='Abrir ahora  →',command=self.finish,bg='#10283e',fg='#b9e8ee',activebackground='#176076',activeforeground='white',relief='flat',borderwidth=0,font=('Segoe UI',9),cursor='hand2',padx=12,pady=5)
        self.skip.place(relx=1,rely=1,anchor='se',x=-14,y=-12)
        self.window.deiconify();self.window.lift();self.job=self.root.after(20,self.tick)
    def tick(self):
        self.job=None
        if self.done:return
        elapsed=time.perf_counter()-self.start
        if elapsed>=self.duration:self.finish();return
        try:
            scene=self.intro.frame(elapsed,self.width,self.height,duration=self.duration,controls=False)
            self.photo=ImageTk.PhotoImage(self.renderer.render(scene),master=self.window)
            self.canvas.delete('all');self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        except Exception:
            logging.exception('No se pudo reproducir la introducción; se abre la aplicación.');self.finish();return
        self.job=self.root.after(25,self.tick)
    def cancel_job(self):
        if self.job is not None:self.root.after_cancel(self.job);self.job=None
    def finish(self):
        if self.done:return
        self.done=True;self.cancel_job()
        self.on_done()
        if self.window.winfo_exists():self.window.destroy()
        self.photo=None
    def close(self):
        if self.done:return
        self.done=True;self.cancel_job();self.root.destroy()
