#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REPLANTEA · Prototipo independiente de la animación de inicio.

Abrir con Python 3.10 o posterior. No requiere instalar paquetes: usa Tkinter.
Si Pillow está instalado, activa automáticamente el renderizado con resplandor.

Espacio / R: repetir.   F11: pantalla completa.   Escape: salir.
La imagen final se mantiene en pantalla. No abre ni modifica Replantea.

Opciones: --duracion 12.5 --ancho 1200 --alto 720 --bucle --sin-pillow
Captura opcional con Pillow: --captura fotograma.png --tiempo 10.5
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import time

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
    PILLOW = True
except ImportError:
    PILLOW = False

TAU = math.tau
DURATION = 12.5
BG = (4, 10, 19)
CYAN = (74, 228, 246)
BLUE = (36, 135, 252)
WHITE = (225, 248, 255)


def clamp(x, a=0.0, b=1.0):
    return min(b, max(a, x))


def smooth(x):
    x = clamp(x)
    return x * x * (3.0 - 2.0 * x)


def smoother(x):
    x = clamp(x)
    return x * x * x * (x * (6.0 * x - 15.0) + 10.0)


def mix(a, b, t):
    return a + (b - a) * t


def lerp(a, b, t):
    return tuple(mix(x, y, t) for x, y in zip(a, b))


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, k):
    return tuple(x * k for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    return mul(a, 1.0 / max(length(a), 1e-12))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def p3(p, z=0.0):
    return (p[0], p[1], z)


def tint(color, alpha):
    alpha = clamp(alpha)
    return (round(4 + (color[0] - 4) * alpha), round(10 + (color[1] - 10) * alpha), round(19 + (color[2] - 19) * alpha))


def rgb(color):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(v))) for v in color)


@dataclass
class Element:
    start: tuple
    heading: float
    distance: float
    station: float
    radius: float = 0.0
    turn: float = 0.0
    center: tuple | None = None

    def point(self, u):
        u = clamp(u)
        if not self.radius:
            return (self.start[0] + math.cos(self.heading) * self.distance * u,
                    self.start[1] + math.sin(self.heading) * self.distance * u)
        radial = sub(self.start, self.center)
        angle = self.turn * u
        co, si = math.cos(angle), math.sin(angle)
        return (self.center[0] + radial[0] * co - radial[1] * si,
                self.center[1] + radial[0] * si + radial[1] * co)

    def tangent(self, u):
        angle = self.heading + self.turn * clamp(u)
        return math.cos(angle), math.sin(angle)

    def pi(self):
        if not self.radius:
            return None
        u, v = self.tangent(0), self.tangent(1)
        a, b = self.point(0), self.point(1)
        delta = sub(b, a)
        denominator = u[0] * v[1] - u[1] * v[0]
        if abs(denominator) < 1e-9:
            return None
        parameter = (delta[0] * v[1] - delta[1] * v[0]) / denominator
        return add(a, mul(u, parameter))


class Alignment:
    """Rectas y arcos circulares exactos, con continuidad de tangente."""

    def __init__(self):
        self.elements = []
        point, heading, station = (0.0, 0.0), math.radians(20), 0.0
        definition = [('L', 52, 0), ('C', 62, 70), ('L', 28, 0),
                      ('C', 52, -105), ('L', 40, 0), ('C', 68, 60), ('L', 58, 0)]
        for kind, value, degrees in definition:
            turn = math.radians(degrees)
            if kind == 'L':
                element = Element(point, heading, value, station)
            else:
                sign = 1 if turn > 0 else -1
                center = (point[0] - math.sin(heading) * value * sign,
                          point[1] + math.cos(heading) * value * sign)
                element = Element(point, heading, abs(turn) * value, station, value, turn, center)
            self.elements.append(element)
            point = element.point(1)
            heading += turn
            station += element.distance
        self.length = station
        self.samples = [self.at(i * station / 270)[0] for i in range(271)]
        end = self.at(station)[0]
        self.overview_angle = math.atan2(end[1], end[0])
        right = (math.cos(self.overview_angle), math.sin(self.overview_angle))
        up = (-right[1], right[0])
        bounds = self.samples + [e.center for e in self.elements if e.center] + [e.pi() for e in self.elements if e.pi()]
        xx, yy = [dot(p, right) for p in bounds], [dot(p, up) for p in bounds]
        self.span = max(xx) - min(xx) + 30, max(yy) - min(yy) + 35
        self.center = add(mul(right, (min(xx) + max(xx)) / 2), mul(up, (min(yy) + max(yy)) / 2))
        self.grid = []
        xmin = math.floor((min(p[0] for p in bounds) - 95) / 20) * 20
        xmax = math.ceil((max(p[0] for p in bounds) + 95) / 20) * 20
        ymin = math.floor((min(p[1] for p in bounds) - 95) / 20) * 20
        ymax = math.ceil((max(p[1] for p in bounds) + 95) / 20) * 20
        for x in range(xmin, xmax + 1, 20):
            for y in range(ymin, ymax, 40):
                self.grid.append(((x, y, -.08), (x, min(y + 40, ymax), -.08), x % 80 == 0))
        for y in range(ymin, ymax + 1, 20):
            for x in range(xmin, xmax, 40):
                self.grid.append(((x, y, -.08), (min(x + 40, xmax), y, -.08), y % 80 == 0))
        self.mesh = []
        for i in range(236):
            s = self.length * i / 235
            p, tangent = self.at(s)
            n = (-tangent[1] * 3.1, tangent[0] * 3.1)
            self.mesh.append((s, p, tangent, add(p, n), sub(p, n)))

    def at(self, station):
        station = clamp(station, 0, self.length)
        for e in self.elements:
            if station <= e.station + e.distance + 1e-8:
                u = clamp((station - e.station) / e.distance)
                return e.point(u), e.tangent(u)
        e = self.elements[-1]
        return e.point(1), e.tangent(1)

    def extended(self, station):
        point, direction = self.at(station)
        if station < 0:
            point = add(point, mul(direction, station))
        elif station > self.length:
            point = add(point, mul(direction, station - self.length))
        return point, direction


class Camera:
    def __init__(self, eye, target, width, height, center_y=.47):
        self.eye = eye
        self.forward = unit(sub(target, eye))
        self.right = unit(cross(self.forward, (0, 0, 1)))
        self.up = unit(cross(self.right, self.forward))
        self.width, self.height = width, height
        self.focal = height * .92
        self.cx, self.cy = width / 2, height * center_y

    def view(self, point):
        x, y, z = point[0] - self.eye[0], point[1] - self.eye[1], point[2] - self.eye[2]
        r, u, f = self.right, self.up, self.forward
        return x*r[0]+y*r[1]+z*r[2], x*u[0]+y*u[1]+z*u[2], x*f[0]+y*f[1]+z*f[2]

    def project(self, point):
        x, y, z = self.view(point)
        if z < .45:
            return None
        return self.cx + self.focal * x / z, self.cy - self.focal * y / z, z

    def segment(self, a, b):
        a, b = self.view(a), self.view(b)
        near = .45
        if a[2] < near and b[2] < near:
            return None
        if a[2] < near:
            a = lerp(a, b, (near - a[2]) / (b[2] - a[2]))
        elif b[2] < near:
            b = lerp(b, a, (near - b[2]) / (a[2] - b[2]))
        ax, ay = self.cx + self.focal * a[0] / a[2], self.cy - self.focal * a[1] / a[2]
        bx, by = self.cx + self.focal * b[0] / b[2], self.cy - self.focal * b[1] / b[2]
        dx, dy, lo, hi = bx - ax, by - ay, 0., 1.
        for p, q in [(-dx, ax + 30), (dx, self.width + 30 - ax), (-dy, ay + 30), (dy, self.height + 30 - ay)]:
            if abs(p) < 1e-10:
                if q < 0:
                    return None
            elif p < 0:
                lo = max(lo, q / p)
            else:
                hi = min(hi, q / p)
            if lo > hi:
                return None
        return (ax + dx * lo, ay + dy * lo, ax + dx * hi, ay + dy * hi), (a[2] + b[2]) / 2


class Scene:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.shapes, self.labels = [], []

    def line(self, points, color, width=1, glow=0):
        self.shapes.append(('line', tuple(points), color, width, glow))

    def circle(self, xy, radius, color, width=1, fill=False, glow=0):
        self.shapes.append(('disk' if fill else 'circle', (xy[0], xy[1], radius), color, width, glow))

    def text(self, xy, value, size, color, anchor='center', bold=False, spacing=0):
        self.labels.append((xy, value, max(8, round(size)), color, anchor, bold, spacing))


class Intro:
    def __init__(self):
        self.axis = Alignment()

    def frame(self, seconds, width=1200, height=720, duration=DURATION, controls=True):
        t = max(0, seconds) * DURATION / duration
        travel = smoother(t / 6.5)
        rise = smoother((t - 6.5) / 3.4)
        front = travel * self.axis.length
        p, tangent = self.axis.at(front)
        # La cámara recorre el propio eje, 22 m detrás de la luz, a 1,70 m del suelo.
        # En los extremos prolonga la tangente; en las curvas sigue su arco exacto.
        ground_eye, _ = self.axis.extended(front - 22)
        look, _ = self.axis.extended(front + 12)
        target0 = p3(look, .2)
        target = lerp(target0, p3(self.axis.center), rise)
        look_vector = sub(look, ground_eye)
        horizontal_distance = length(look_vector)
        follow_angle = math.atan2(look_vector[1], look_vector[0])
        final_angle = self.axis.overview_angle + math.pi / 2
        difference = (final_angle - follow_angle + math.pi) % TAU - math.pi
        angle = follow_angle + difference * rise
        final_height = max(self.axis.span[0] * height * .92 / (width * .83), self.axis.span[1] * .92 / .51)
        distance = mix(math.hypot(horizontal_distance, 1.5), final_height, rise)
        elevation = mix(math.atan2(1.5, horizontal_distance), math.pi / 2 - .00001, rise)
        eye = add(target, (-math.cos(angle) * distance * math.cos(elevation),
                           -math.sin(angle) * distance * math.cos(elevation), distance * math.sin(elevation)))
        camera = Camera(eye, target, width, height, mix(.47, .445, rise))
        scene = Scene(width, height)

        def worldline(a, b, color, w=1, glow=0, alpha=1):
            projected = camera.segment(a, b)
            if projected:
                points, depth = projected
                fog = mix(math.exp(-depth / 420), .88, rise)
                scene.line(points, tint(color, alpha * fog), w, glow)

        # Rejilla del plano de trabajo: discretizada para que se desvanezca en el horizonte.
        for a, b, major in self.axis.grid:
            worldline(a, b, (29, 66, 83) if major else (18, 40, 53), .8 if major else .55, alpha=.72)

        # Dos bordes tenues y un eje central: la geometría pendiente permanece visible.
        for first, second in zip(self.axis.mesh, self.axis.mesh[1:]):
            s0, a, ta, left_a, right_a = first
            s1, b, tb, left_b, right_b = second
            if s1 < front:
                continue
            worldline(p3(a), p3(b), (32, 78, 95), 1.0, alpha=.72)
            for aa, bb in ((left_a, left_b), (right_a, right_b)):
                worldline(p3(aa), p3(bb), (25, 66, 78), .7, alpha=.75)

        # La luz recorre exactamente la misma geometría que la cámara.
        for first, second in zip(self.axis.mesh, self.axis.mesh[1:]):
            s0, a, ta, left_a, right_a = first
            if s0 >= front:
                break
            s1, b, tb, left_b, right_b = second
            if s1 > front:
                s1 = front
                b, tb = self.axis.at(front)
                n = (-tb[1]*3.1, tb[0]*3.1)
                left_b, right_b = add(b, n), sub(b, n)
            age = front - (s0 + s1) / 2
            color = lerp((30, 142, 225), CYAN, .55 + .45 * math.exp(-age / 42))
            projected = camera.segment(p3(a, .025), p3(b, .025))
            if projected:
                points, depth = projected
                pen = mix(clamp(camera.focal / depth * .09, 1.2, 3.7), 2.1, rise)
                scene.line(points, tint(color, .96), pen, glow=1.65)
            for aa, bb in ((left_a, left_b), (right_a, right_b)):
                worldline(p3(aa, .01), p3(bb, .01), (35, 133, 153), .8, alpha=.56)

        # Marcas de estación y puntos que se encienden a medida que pasa la luz.
        for k in range(int(self.axis.length / 10) + 1):
            station = k * 10.
            p0, direction = self.axis.at(station)
            n = (-direction[1], direction[0])
            visible = smooth((front - station) / 5)
            if visible <= 0:
                continue
            half = 1.55 if k % 5 == 0 else .8
            worldline(p3(add(p0, mul(n, -half)), .05), p3(add(p0, mul(n, half)), .05), (100, 206, 223), .9, alpha=visible * .8)
            screen = camera.project(p3(p0, .055))
            if screen and -.02 * width < screen[0] < width * 1.02 and 0 < screen[1] < height:
                radius = mix(clamp(camera.focal / screen[2] * .08, 1.1, 2.5), 1.5, rise)
                scene.circle(screen, radius, tint(CYAN, visible * .85), fill=True, glow=.7)

        # Un pulso corto acompaña al frente; se integra en el último punto al elevarse.
        head = camera.project(p3(p, .10))
        if head:
            power = 1 - .65 * rise
            radius = mix(5.5 + .35 * math.sin(t * 8), 3.3, rise)
            scene.circle(head, radius * 2.5, tint(BLUE, .18 * power), fill=True, glow=1.8)
            scene.circle(head, radius, tint(CYAN, power), fill=True, glow=2.5)
            scene.circle(head, radius * .40, WHITE, fill=True, glow=.8)

        annotation = smooth((t - 8.25) / 1.75)
        if annotation:
            self.annotations(scene, camera, annotation, worldline)

        # Cierre con el nombre de la aplicación y el trazado entero iluminado.
        brand = smooth((t - 9.55) / 1.1)
        factor = min(width / 1200, height / 720)
        if brand:
            scene.text((width * .5, height * .82), 'REPLANTEA', 42 * factor, tint(WHITE, brand), bold=True, spacing=4 * factor)
            scene.line((width * .5 - 38 * factor, height * .868, width * .5 + 38 * factor, height * .868), tint(CYAN, brand * .85), 1.5, .7)
            scene.text((width * .5, height * .903), 'Replanteo de ejes', 13 * factor, tint((122, 163, 184), brand))
        # Indicaciones del prototipo, fuera de la composición del logotipo.
        if controls and t > 11.2:
            opacity = smooth((t - 11.2) / .7)
            scene.text((width * .5, height - 19), 'ESPACIO  Repetir     ·     F11  Pantalla completa     ·     ESC  Cerrar', 10 * factor, tint((76, 110, 131), opacity))
        return scene

    def annotations(self, scene, camera, opacity, worldline):
        scale = min(scene.width / 1200, scene.height / 720)

        def label(point, text, dx=0, dy=0, size=13, color=WHITE, anchor='center'):
            q = camera.project(p3(point, .10))
            if q and 10 < q[0] < scene.width - 10 and 10 < q[1] < scene.height * .75:
                scene.text((q[0] + dx * scale, q[1] + dy * scale), text, size * scale, tint(color, opacity), anchor)

        curve_id = 0
        for e in self.axis.elements:
            if not e.radius:
                continue
            curve_id += 1
            ce, mid = e.center, e.point(.5)
            worldline(p3(ce, .05), p3(mid, .05), (100, 144, 163), .85, alpha=opacity * .9)
            c = camera.project(p3(ce, .05))
            if c:
                scene.circle(c, 3.2 * scale, tint(CYAN, opacity), 1, glow=.45)
            label(ce, f'C{curve_id}', 9, -8, 12, CYAN, 'left')
            radius_label = lerp(ce, mid, .54)
            label(radius_label, f'R={e.radius:.2f}', 0, -10, 12, (164, 196, 211))
            pi = e.pi()
            if pi:
                for endpoint in (e.point(0), e.point(1)):
                    worldline(p3(endpoint, .06), p3(pi, .06), (75, 119, 144), .75, alpha=opacity * .9)
                vertex = camera.project(p3(pi, .08))
                if vertex:
                    scene.circle(vertex, 2.3 * scale, tint(CYAN, opacity), 1)
                label(pi, f'V{curve_id}', 0, 15, 12, CYAN)

        # Una cota de longitud exacta de la última recta, con trazos oblicuos.
        final = self.axis.elements[-1]
        a, b, tangent = final.point(0), final.point(1), final.tangent(0)
        normal = (-tangent[1], tangent[0])
        aa, bb = add(a, mul(normal, -10)), add(b, mul(normal, -10))
        for start, end in ((a, add(aa, mul(normal, -2))), (b, add(bb, mul(normal, -2))), (aa, bb)):
            worldline(p3(start, .06), p3(end, .06), (132, 179, 198), .85, alpha=opacity)
        for endpoint in (aa, bb):
            tick = mul(unit(add(tangent, normal)), 1.5)
            worldline(p3(sub(endpoint, tick), .07), p3(add(endpoint, tick), .07), CYAN, 1.1, alpha=opacity)
        label(lerp(aa, bb, .5), f'L={final.distance:.2f} m', 0, 13, 12, (173, 215, 225))
        for station in (0, 100, 200, 300, 400):
            if station > self.axis.length:
                continue
            p, tangent = self.axis.at(station)
            normal = (-tangent[1], tangent[0])
            label(add(p, mul(normal, -6)), f'{station // 1000}+{station % 1000:03d}', 0, 13, 10, (91, 143, 165))


class PillowRenderer:
    def __init__(self):
        if not PILLOW:
            raise RuntimeError('La exportación de imágenes requiere Pillow: python -m pip install pillow')
        self.backgrounds = {}
        self.fonts = {}

    def font(self, size, bold):
        key = size, bold
        if key in self.fonts:
            return self.fonts[key]
        candidates = [r'C:\Windows\Fonts\arialbd.ttf' if bold else r'C:\Windows\Fonts\arial.ttf',
                      'Arial Bold.ttf' if bold else 'Arial.ttf',
                      '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                      'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf']
        for path in candidates:
            try:
                font = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
        else:
            font = ImageFont.load_default()
        self.fonts[key] = font
        return font

    def background(self, width, height):
        key = width, height
        if key not in self.backgrounds:
            image = Image.new('RGB', (width, height), BG)
            draw = ImageDraw.Draw(image)
            for y in range(height):
                light = math.exp(-((y / height - .54) / .44) ** 2)
                color = tuple(round(a + b * light) for a, b in zip(BG, (2, 6, 10)))
                draw.line((0, y, width, y), fill=color)
            self.backgrounds = {key: image}
        return self.backgrounds[key].copy()

    def render(self, scene):
        w, h = scene.width, scene.height
        image = self.background(w, h)
        glow = Image.new('RGB', (max(1, w // 2), max(1, h // 2)), (0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        for kind, points, color, width, amount in scene.shapes:
            if amount <= 0:
                continue
            color = tuple(round(v * min(.82, amount * .32)) for v in color)
            if kind == 'line':
                glow_draw.line(tuple(v / 2 for v in points), fill=color, width=max(2, round((width + amount * 7) / 2)))
            else:
                x, y, r = points
                r = (r + amount * 3) / 2
                glow_draw.ellipse((x / 2 - r, y / 2 - r, x / 2 + r, y / 2 + r), fill=color)
        bounds = glow.getbbox()
        if bounds:
            box = (max(0,bounds[0]-12), max(0,bounds[1]-12), min(glow.width,bounds[2]+12), min(glow.height,bounds[3]+12))
            final_box = (box[0]*2,box[1]*2,min(w,box[2]*2),min(h,box[3]*2))
            bloom = glow.crop(box).filter(ImageFilter.GaussianBlur(3.2)).resize((final_box[2]-final_box[0],final_box[3]-final_box[1]), Image.Resampling.BILINEAR)
            image.paste(ImageChops.screen(image.crop(final_box),bloom),final_box)
        draw = ImageDraw.Draw(image)
        for kind, points, color, width, _ in scene.shapes:
            color = tuple(round(v) for v in color)
            if kind == 'line':
                draw.line(points, fill=color, width=max(1, round(width)))
            else:
                x, y, r = points
                bounds = (x - r, y - r, x + r, y + r)
                if kind == 'disk':
                    draw.ellipse(bounds, fill=color)
                else:
                    draw.ellipse(bounds, outline=color, width=max(1, round(width)))
        for (x, y), value, size, color, anchor, bold, spacing in scene.labels:
            font = self.font(size, bold)
            bounds = font.getbbox(value)
            text_width = font.getlength(value) + spacing * max(0, len(value) - 1)
            left = x if anchor == 'left' else (x - text_width if anchor == 'right' else x - text_width / 2)
            top = y - (bounds[3] - bounds[1]) / 2 - bounds[1]
            if spacing:
                for character in value:
                    draw.text((left, top), character, font=font, fill=tuple(round(v) for v in color))
                    left += font.getlength(character) + spacing
            else:
                draw.text((left, top), value, font=font, fill=tuple(round(v) for v in color))
        return image


class TkRenderer:
    """Alternativa sin paquetes externos para cualquier instalación normal de Python."""
    def render(self, scene, canvas):
        canvas.delete('all')
        w, h = scene.width, scene.height
        for i in range(32):
            y = h * i / 32
            light = math.exp(-((i / 32 - .54) / .44) ** 2)
            color = tuple(round(a + b * light) for a, b in zip(BG, (2, 6, 10)))
            canvas.create_rectangle(0, y, w, y + h / 32 + 1, fill=rgb(color), outline='')
        for kind, points, color, width, glow in scene.shapes:
            if kind == 'line':
                if glow:
                    canvas.create_line(*points, fill=rgb(tint(color, .08)), width=width + 13 * glow, capstyle='round')
                    canvas.create_line(*points, fill=rgb(tint(color, .22)), width=width + 4 * glow, capstyle='round')
                canvas.create_line(*points, fill=rgb(color), width=width, capstyle='round')
            else:
                x, y, r = points
                if glow:
                    rr = r + glow * 3
                    canvas.create_oval(x - rr, y - rr, x + rr, y + rr, fill=rgb(tint(color, .13)), outline='')
                canvas.create_oval(x - r, y - r, x + r, y + r, fill=rgb(color) if kind == 'disk' else '', outline='' if kind == 'disk' else rgb(color), width=width)
        for (x, y), value, size, color, anchor, bold, spacing in scene.labels:
            canvas.create_text(x, y, text=value, fill=rgb(color), anchor={'left': 'w', 'right': 'e'}.get(anchor, 'center'),
                               font=('Arial', -size, 'bold' if bold else 'normal'))


def play(args):
    import tkinter as tk
    root = tk.Tk()
    root.title('Replantea · Vista previa de inicio')
    width = min(args.ancho, root.winfo_screenwidth() - 80)
    height = min(args.alto, root.winfo_screenheight() - 100)
    root.geometry(f'{width}x{height}+{max(0,(root.winfo_screenwidth()-width)//2)}+{max(0,(root.winfo_screenheight()-height)//2)}')
    root.minsize(640, 400)
    root.configure(bg=rgb(BG))
    canvas = tk.Canvas(root, bg=rgb(BG), highlightthickness=0)
    canvas.pack(fill='both', expand=True)
    intro = Intro()
    high_quality = PILLOW and not args.sin_pillow
    renderer = PillowRenderer() if high_quality else TkRenderer()
    if high_quality:
        from PIL import ImageTk
    state = dict(start=time.perf_counter(), image=None, fullscreen=False, last_size=None, final=False)

    def restart(event=None):
        state['start'] = time.perf_counter()
        state['final'] = False

    def fullscreen(event=None):
        state['fullscreen'] = not state['fullscreen']
        root.attributes('-fullscreen', state['fullscreen'])

    def update():
        started = time.perf_counter()
        elapsed = started - state['start']
        if args.bucle and elapsed > args.duracion + 2:
            restart()
            elapsed = 0
        size = max(32, canvas.winfo_width()), max(32, canvas.winfo_height())
        if not state['final'] or size != state['last_size']:
            scene = intro.frame(min(elapsed, args.duracion), *size, duration=args.duracion)
            if high_quality:
                state['image'] = ImageTk.PhotoImage(renderer.render(scene))
                canvas.delete('all')
                canvas.create_image(0, 0, image=state['image'], anchor='nw')
            else:
                renderer.render(scene, canvas)
            state['last_size'] = size
        state['final'] = elapsed >= args.duracion
        cost = time.perf_counter() - started
        root.after(max(1, round((1 / 30 - cost) * 1000)) if not state['final'] else 80, update)

    root.bind('<space>', restart)
    root.bind('<r>', restart)
    root.bind('<R>', restart)
    root.bind('<F11>', fullscreen)
    root.bind('<Escape>', lambda event: root.destroy())
    root.after(80, update)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Vista previa independiente de la animación de inicio de Replantea.')
    parser.add_argument('--duracion', type=float, default=DURATION)
    parser.add_argument('--ancho', type=int, default=1200)
    parser.add_argument('--alto', type=int, default=720)
    parser.add_argument('--bucle', action='store_true')
    parser.add_argument('--sin-pillow', action='store_true', help='Usar solo la biblioteca estándar de Python.')
    parser.add_argument('--captura', type=Path, help='Exportar un fotograma PNG; requiere Pillow.')
    parser.add_argument('--tiempo', type=float, default=10.8)
    args = parser.parse_args()
    if not math.isfinite(args.duracion) or args.duracion <= 0:
        parser.error('La duración debe ser un número positivo.')
    if args.ancho < 320 or args.alto < 240:
        parser.error('Tamaño mínimo de exportación: 320 x 240.')
    if args.captura:
        args.captura.parent.mkdir(parents=True, exist_ok=True)
        PillowRenderer().render(Intro().frame(args.tiempo, args.ancho, args.alto, args.duracion)).save(args.captura)
    else:
        play(args)


if __name__ == '__main__':
    main()
