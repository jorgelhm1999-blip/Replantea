"""Icono vectorial de Replantea: eje curvo bajo una lupa."""
import io
from PIL import Image,ImageDraw

def icon_image(size=256):
    image=Image.new('RGBA',(512,512),(0,0,0,0));d=ImageDraw.Draw(image)
    d.rounded_rectangle((8,8,504,504),radius=112,fill='#10283e')
    # Eje en S, con marcas perpendiculares a su tangente.
    points=[]
    for i in range(151):
        t=i/150;u=1-t
        points.append((65*u**3+3*165*u*u*t+3*275*u*t*t+365*t**3,
                       355*u**3+3*350*u*u*t+3*85*u*t*t+125*t**3))
    d.line(points,fill='#3ee0de',width=19,joint='curve')
    for i in (18,42,68,94,120):
        x,y=points[i];a,b=points[i-1],points[i+1];dx,dy=b[0]-a[0],b[1]-a[1];length=(dx*dx+dy*dy)**.5
        nx,ny=-dy/length*18,dx/length*18
        d.line((x-nx,y-ny,x+nx,y+ny),fill='#a0f7f3',width=6)
    d.line((336,320,423,412),fill='#071725',width=66)
    d.line((336,320,423,412),fill='#e4f6ff',width=43)
    d.ellipse((136,94,362,320),outline='#071725',width=44)
    d.ellipse((136,94,362,320),outline='#e4f6ff',width=24)
    return image.resize((size,size),Image.Resampling.LANCZOS)

def apply_icon(root):
    from PIL import ImageTk
    root._replantea_icons=[ImageTk.PhotoImage(icon_image(s),master=root) for s in (64,32,16)]
    root.iconphoto(True,*root._replantea_icons)

def windows_identity():
    import sys
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Replantea.Desktop')
