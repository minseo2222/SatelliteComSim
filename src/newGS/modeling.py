#!/usr/bin/env python3
import sys
import ctypes
import math
import numpy as np
import trimesh
from PIL import Image
from PyQt5.QtWidgets import QOpenGLWidget, QApplication
from PyQt5.QtCore import Qt, QTimer
from OpenGL.GL import *
from OpenGL.GLU import gluPerspective

def load_model(filepath, texture_path=None):
    mesh = trimesh.load(filepath, force='scene')
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.geometry.values())
    vertices = mesh.vertices.astype(np.float32)
    indices = mesh.faces.astype(np.uint32).flatten()
    texcoords = None
    if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
        texcoords = mesh.visual.uv.astype(np.float32)
    texture = None
    if texture_path:
        texture = Image.open(texture_path).convert('RGB')
    return vertices, indices, texcoords, texture

class EarthSatelliteView(QOpenGLWidget):
    DEFAULT_PARAMS = {
        "sat_type": "ISS",
        "sat_size": 10.0,
        "sat_speed": 0.05,
        "orbital_radius": 400.0,
        "inclination": 45.0,
        "eccentricity": 0.0,
        "frequency": 2.4,
        "antenna_gain": 10.0,
        "transmit_power": 0.0
    }

    def __init__(self, model_path='textures/earth.glb', texture_path='textures/image_0.png',
                 bg_image_path='textures/background.jpg', sat_model_path='textures/satellite.glb',
                 sat_texture_path='textures/satellite_texture.jpg', parent=None):
        super().__init__(parent)
        # Paths
        self.model_path = model_path
        self.texture_path = texture_path
        self.bg_image_path = bg_image_path
        self.sat_model_path = sat_model_path
        self.sat_texture_path = sat_texture_path
        # GL buffers & textures
        self.bg_vbo = None
        self.bg_texture = 0
        self.earth_vbo = self.earth_ebo = self.earth_tbo = None
        self.earth_texture = 0
        self.sat_vbo = self.sat_ebo = self.sat_tbo = None
        self.sat_texture = 0
        # Counts
        self.earth_index_count = 0
        self.sat_index_count = 0
        self.gl_ready = False
        # Radii
        self.earth_radius = 1.0
        self.orbital_radius = 1.0
        # Camera control
        self.rotation = [30.0, -45.0]
        self.zoom = -10.0
        self.last_pos = None
        # Satellite parameters
        self.sat_type = '소형 위성'
        self.sat_size = 10.0
        self.sat_speed = 0.05
        self.orbital_radius_units = 300.0
        self.inclination = 45.0
        self.eccentricity = 0.0
        self.frequency = 2.4
        self.antenna_gain = 10.0
        self.transmit_power = 0.0
        self.sat_angle = 0.0
        # Ground station parameters
        self.gs_name = "Default GS"
        self.gs_lat = 36.350413
        self.gs_lon = 127.384548
        self.gs_alt = 50.0
        self.min_elevation = 5.0
        self.gs_antenna_gain = 35.0
        # Communication / environment parameters
        self.base_delay_ms = 0.0
        self.jitter_ms = 0.0
        self.ber = 0.0
        self.ber_mode = "payload_only"
        self.anim_time = 0.0
        self.starfield = self._generate_starfield()
        # Timer (~60fps)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer)
        self.timer.start(16)
        # Enable mouse events
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def on_timer(self):
        self.anim_time = (self.anim_time + 0.016) % 1000.0
        self.sat_angle = (self.sat_angle + self.sat_speed) % 360.0
        self.update()

    def initializeGL(self):
        self.gl_ready = True
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_POINT_SMOOTH)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        # Background quad
        bg = np.array([-1,-1,0,0, 1,-1,1,0, 1,1,1,1, -1,1,0,1], dtype=np.float32)
        self.bg_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.bg_vbo)
        glBufferData(GL_ARRAY_BUFFER, bg.nbytes, bg, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        # Background texture
        img = Image.open(self.bg_image_path).convert('RGB')
        w, h = img.size
        data = img.tobytes('raw','RGB',0,-1)
        self.bg_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.bg_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)
        # Load Earth model
        verts, inds, uvs, tex = load_model(self.model_path, self.texture_path)
        raw_radius = float(np.max(np.linalg.norm(verts, axis=1)))
        verts *= 0.4
        self.earth_radius = raw_radius * 0.4
        self._recompute_orbital_radius()
        self.zoom = -self.earth_radius * 4.0
        self.earth_index_count = len(inds)
        # Earth buffers
        self.earth_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.earth_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        self.earth_ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.earth_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, inds.nbytes, inds, GL_STATIC_DRAW)
        if uvs is not None:
            self.earth_tbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.earth_tbo)
            glBufferData(GL_ARRAY_BUFFER, uvs.nbytes, uvs, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        # Earth texture
        if tex is not None:
            tw, th = tex.size
            tdata = tex.tobytes('raw','RGB',0,-1)
            self.earth_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.earth_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, tw, th, 0, GL_RGB, GL_UNSIGNED_BYTE, tdata)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glBindTexture(GL_TEXTURE_2D, 0)
        # Build satellite geometry
        self._build_satellite()

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, w/h if h else 1.0, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # Draw background
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); glOrtho(-1,1,-1,1,-1,1)
        glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity(); glDisable(GL_DEPTH_TEST)
        glBindBuffer(GL_ARRAY_BUFFER, self.bg_vbo); glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(2, GL_FLOAT, 16, ctypes.c_void_p(0)); glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glTexCoordPointer(2, GL_FLOAT, 16, ctypes.c_void_p(8)); glBindTexture(GL_TEXTURE_2D, self.bg_texture)
        glDrawArrays(GL_QUADS, 0, 4); glDisableClientState(GL_TEXTURE_COORD_ARRAY); glDisableClientState(GL_VERTEX_ARRAY)
        self._draw_background_fx()
        glBindTexture(GL_TEXTURE_2D, 0); glEnable(GL_DEPTH_TEST); glPopMatrix()
        glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW); glClear(GL_DEPTH_BUFFER_BIT)
        # Camera transform
        glLoadIdentity(); glTranslatef(0,0,self.zoom); glRotatef(self.rotation[0],1,0,0); glRotatef(self.rotation[1],0,1,0)
        # Earth
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBindTexture(GL_TEXTURE_2D,self.earth_texture); glBindBuffer(GL_ARRAY_BUFFER,self.earth_vbo)
        glEnableClientState(GL_VERTEX_ARRAY); glVertexPointer(3,GL_FLOAT,0,ctypes.c_void_p(0))
        if hasattr(self,'earth_tbo') and self.earth_tbo:
            glEnableClientState(GL_TEXTURE_COORD_ARRAY); glBindBuffer(GL_ARRAY_BUFFER,self.earth_tbo); glTexCoordPointer(2,GL_FLOAT,0,ctypes.c_void_p(0))
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,self.earth_ebo); glDrawElements(GL_TRIANGLES,self.earth_index_count,GL_UNSIGNED_INT,ctypes.c_void_p(0))
        glDisableClientState(GL_VERTEX_ARRAY);
        if hasattr(self,'earth_tbo') and self.earth_tbo: glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        self._draw_earth_glow()
        self._draw_orbit_path()
        self._draw_satellite_trail()
        # Satellite
        sat_pos = self._satellite_position()
        x, y, z = sat_pos.tolist()
        glPushMatrix(); glTranslatef(x,y,z)
        forward=np.array([0.0,-1.0,0.0],np.float32); target=np.array([-x,-y,-z],np.float32)
        if np.linalg.norm(target)>1e-6:
            target/=np.linalg.norm(target); axis=np.cross(forward,target)
            if np.linalg.norm(axis)>1e-6:
                axis/=np.linalg.norm(axis); cosang=np.dot(forward,target)
                angle=math.degrees(math.acos(max(-1.0,min(1.0,cosang)))); glRotatef(angle,axis[0],axis[1],axis[2])
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBindTexture(GL_TEXTURE_2D,self.sat_texture); glBindBuffer(GL_ARRAY_BUFFER,self.sat_vbo)
        glEnableClientState(GL_VERTEX_ARRAY); glVertexPointer(3,GL_FLOAT,0,ctypes.c_void_p(0))
        if hasattr(self,'sat_tbo') and self.sat_tbo: glEnableClientState(GL_TEXTURE_COORD_ARRAY); glBindBuffer(GL_ARRAY_BUFFER,self.sat_tbo); glTexCoordPointer(2,GL_FLOAT,0,ctypes.c_void_p(0))
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,self.sat_ebo); glDrawElements(GL_TRIANGLES,self.sat_index_count,GL_UNSIGNED_INT,ctypes.c_void_p(0))
        glDisableClientState(GL_VERTEX_ARRAY)
        if hasattr(self,'sat_tbo') and self.sat_tbo: glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glBindTexture(GL_TEXTURE_2D,0); glPopMatrix()
        gs_pos = self._ground_station_position()
        self._draw_ground_station(gs_pos)
        self._draw_comm_link(gs_pos, sat_pos)

    # Mouse and wheel events
    def mousePressEvent(self, event):
        self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.last_pos and event.buttons() & Qt.LeftButton:
            dx = event.x() - self.last_pos.x()
            dy = event.y() - self.last_pos.y()
            self.rotation[0] += dy
            self.rotation[1] += dx
            self.update()
        self.last_pos = event.pos()

    def wheelEvent(self, event):
        self.zoom += event.angleDelta().y() / 120 * 0.3
        self.update()

    def _build_satellite(self):
        verts, inds, uvs, tex = load_model(self.sat_model_path, self.sat_texture_path)
        verts *= (self.sat_size / 50.0 * self.earth_radius)
        self.sat_index_count = len(inds)
        self.sat_vbo = glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER,self.sat_vbo); glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        self.sat_ebo = glGenBuffers(1); glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,self.sat_ebo); glBufferData(GL_ELEMENT_ARRAY_BUFFER, inds.nbytes, inds, GL_STATIC_DRAW)
        if uvs is not None: self.sat_tbo = glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER,self.sat_tbo); glBufferData(GL_ARRAY_BUFFER, uvs.nbytes, uvs, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER,0); glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,0)
        if tex is not None:
            sw,sh=tex.size; sdata=tex.tobytes('raw','RGB',0,-1)
            self.sat_texture=glGenTextures(1); glBindTexture(GL_TEXTURE_2D,self.sat_texture)
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,sw,sh,0,GL_RGB,GL_UNSIGNED_BYTE,sdata)
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
            glBindTexture(GL_TEXTURE_2D,0)

    def _recompute_orbital_radius(self):
        self.orbital_radius = self.earth_radius * (self.orbital_radius_units / 100.0 + 1.0)

    def _satellite_position(self, angle_deg=None):
        theta = math.radians(self.sat_angle if angle_deg is None else angle_deg)
        incl = math.radians(self.inclination)
        ecc = max(0.0, min(self.eccentricity, 0.95))
        radius = self.orbital_radius
        if ecc > 0.0:
            radius = self.orbital_radius * (1.0 - ecc * ecc) / (1.0 + ecc * math.cos(theta))
        x = radius * math.cos(theta)
        z = radius * math.sin(theta)
        y = z * math.sin(incl)
        z = z * math.cos(incl)
        return np.array([x, y, z], dtype=np.float32)

    def _ground_station_position(self):
        lat = math.radians(self.gs_lat)
        lon = math.radians(self.gs_lon)
        alt_km = max(0.0, float(self.gs_alt)) / 1000.0
        radius = self.earth_radius * (1.0 + alt_km / 100.0)
        x = radius * math.cos(lat) * math.cos(lon)
        y = radius * math.sin(lat)
        z = radius * math.cos(lat) * math.sin(lon)
        return np.array([x, y, z], dtype=np.float32)

    def _generate_starfield(self):
        rng = np.random.default_rng(42)
        stars = []
        for _ in range(140):
            stars.append((
                float(rng.uniform(-1.0, 1.0)),
                float(rng.uniform(-1.0, 1.0)),
                float(rng.uniform(0.9, 1.8)),
                float(rng.uniform(0.35, 0.95)),
                float(rng.uniform(0.0, math.tau)),
            ))
        return stars

    def _draw_radial_fan(self, cx, cy, rx, ry, inner_rgba, outer_rgba, segments=48):
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(*inner_rgba)
        glVertex2f(cx, cy)
        glColor4f(*outer_rgba)
        for i in range(segments + 1):
            angle = math.tau * i / segments
            glVertex2f(cx + math.cos(angle) * rx, cy + math.sin(angle) * ry)
        glEnd()

    def _link_quality_color(self):
        severity = min(1.0, self.ber * 8.0 + self.base_delay_ms / 1500.0 + self.jitter_ms / 800.0)
        good = np.array([0.15, 0.95, 0.35], dtype=np.float32)
        bad = np.array([1.0, 0.25, 0.2], dtype=np.float32)
        color = good * (1.0 - severity) + bad * severity
        return color.tolist()

    def _elevation_angle_deg(self, gs_pos, sat_pos):
        los = sat_pos - gs_pos
        if np.linalg.norm(los) < 1e-6:
            return -90.0
        los_unit = los / np.linalg.norm(los)
        zenith = gs_pos / np.linalg.norm(gs_pos)
        return math.degrees(math.asin(float(np.dot(los_unit, zenith))))

    def _draw_orbit_path(self):
        glDisable(GL_TEXTURE_2D)
        glColor4f(0.25, 0.55, 0.95, 0.14)
        glLineWidth(5.0)
        glBegin(GL_LINE_LOOP)
        for deg in range(0, 360, 3):
            pos = self._satellite_position(deg)
            glVertex3f(pos[0], pos[1], pos[2])
        glEnd()
        glColor4f(0.35, 0.85, 1.0, 0.6)
        glLineWidth(1.6)
        glBegin(GL_LINE_LOOP)
        for deg in range(0, 360, 3):
            pos = self._satellite_position(deg)
            glVertex3f(pos[0], pos[1], pos[2])
        glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_ground_station(self, gs_pos):
        pulse = 0.5 + 0.5 * math.sin(self.anim_time * 2.4)
        normal = gs_pos / max(1e-6, np.linalg.norm(gs_pos))
        beacon_tip = gs_pos + normal * (0.10 + 0.05 * pulse)
        glDisable(GL_TEXTURE_2D)
        glPointSize(16.0)
        glColor4f(1.0, 0.88, 0.28, 0.32 + 0.25 * pulse)
        glBegin(GL_POINTS)
        glVertex3f(gs_pos[0], gs_pos[1], gs_pos[2])
        glEnd()
        glPointSize(9.0)
        glColor4f(1.0, 0.97, 0.55, 1.0)
        glBegin(GL_POINTS)
        glVertex3f(gs_pos[0], gs_pos[1], gs_pos[2])
        glEnd()
        glLineWidth(2.0)
        glColor4f(1.0, 0.88, 0.35, 0.45 + 0.2 * pulse)
        glBegin(GL_LINES)
        glVertex3f(gs_pos[0], gs_pos[1], gs_pos[2])
        glVertex3f(beacon_tip[0], beacon_tip[1], beacon_tip[2])
        glEnd()
        for idx, scale in enumerate((1.0, 1.45, 1.9)):
            radius = (0.035 + pulse * 0.025) * scale
            alpha = max(0.0, 0.28 - idx * 0.08 + pulse * 0.06)
            tangent = np.cross(normal, np.array([0.0, 1.0, 0.0], dtype=np.float32))
            if np.linalg.norm(tangent) < 1e-4:
                tangent = np.cross(normal, np.array([1.0, 0.0, 0.0], dtype=np.float32))
            tangent /= np.linalg.norm(tangent)
            bitangent = np.cross(normal, tangent)
            glColor4f(1.0, 0.85, 0.3, alpha)
            glLineWidth(1.4)
            glBegin(GL_LINE_LOOP)
            for deg in range(0, 360, 12):
                angle = math.radians(deg)
                offset = tangent * math.cos(angle) * radius + bitangent * math.sin(angle) * radius
                pos = gs_pos + normal * 0.01 + offset
                glVertex3f(pos[0], pos[1], pos[2])
            glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_comm_link(self, gs_pos, sat_pos):
        elevation = self._elevation_angle_deg(gs_pos, sat_pos)
        visible = elevation >= self.min_elevation
        if visible:
            r, g, b = self._link_quality_color()
            alpha = 0.85 if self.ber_mode == "payload_only" else 0.95
        else:
            r, g, b, alpha = 0.55, 0.55, 0.55, 0.35
        glDisable(GL_TEXTURE_2D)
        glLineWidth(8.0 if visible else 3.0)
        glColor4f(r, g, b, alpha * 0.18)
        glBegin(GL_LINES)
        glVertex3f(gs_pos[0], gs_pos[1], gs_pos[2])
        glVertex3f(sat_pos[0], sat_pos[1], sat_pos[2])
        glEnd()
        glLineWidth(3.0 if visible else 1.5)
        glColor4f(r, g, b, alpha)
        glBegin(GL_LINES)
        glVertex3f(gs_pos[0], gs_pos[1], gs_pos[2])
        glVertex3f(sat_pos[0], sat_pos[1], sat_pos[2])
        glEnd()
        if visible:
            travel = (self.anim_time * 0.35) % 1.0
            for offset in (travel, (travel + 0.33) % 1.0, (travel + 0.66) % 1.0):
                pulse = gs_pos * (1.0 - offset) + sat_pos * offset
                glPointSize(5.0)
                glColor4f(0.95, 0.98, 1.0, 0.8)
                glBegin(GL_POINTS)
                glVertex3f(pulse[0], pulse[1], pulse[2])
                glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_background_fx(self):
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_DEPTH_TEST)
        self._draw_radial_fan(-0.45, 0.38, 0.72, 0.52, (0.07, 0.16, 0.33, 0.16), (0.02, 0.04, 0.09, 0.0))
        self._draw_radial_fan(0.58, -0.22, 0.55, 0.40, (0.20, 0.07, 0.14, 0.14), (0.06, 0.02, 0.05, 0.0))
        self._draw_radial_fan(0.12, 0.72, 0.35, 0.23, (0.16, 0.12, 0.05, 0.10), (0.03, 0.02, 0.01, 0.0))
        for x, y, size, base_alpha, phase in self.starfield:
            twinkle = 0.55 + 0.45 * math.sin(self.anim_time * 1.6 + phase)
            glPointSize(size)
            glColor4f(0.9, 0.96, 1.0, base_alpha * twinkle)
            glBegin(GL_POINTS)
            glVertex2f(x, y)
            glEnd()
        glColor4f(1.0, 1.0, 1.0, 0.9)
        glPointSize(2.5)
        glBegin(GL_POINTS)
        for x, y, size, base_alpha, phase in self.starfield[::9]:
            twinkle = 0.75 + 0.25 * math.sin(self.anim_time * 2.8 + phase)
            glColor4f(1.0, 0.98, 0.9, base_alpha * twinkle)
            glVertex2f(x, y)
        glEnd()
        glEnable(GL_DEPTH_TEST)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_earth_glow(self):
        glow_radius = self.earth_radius * 1.08
        glDisable(GL_TEXTURE_2D)
        for idx, alpha in enumerate((0.18, 0.1, 0.05)):
            radius = glow_radius + idx * self.earth_radius * 0.04
            glLineWidth(2.8 - idx * 0.5)
            glColor4f(0.28, 0.66, 1.0, alpha)
            for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                glBegin(GL_LINE_LOOP)
                for deg in range(0, 360, 8):
                    angle = math.radians(deg)
                    if axis == (1, 0, 0):
                        glVertex3f(0.0, math.cos(angle) * radius, math.sin(angle) * radius)
                    elif axis == (0, 1, 0):
                        glVertex3f(math.cos(angle) * radius, 0.0, math.sin(angle) * radius)
                    else:
                        glVertex3f(math.cos(angle) * radius, math.sin(angle) * radius, 0.0)
                glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_satellite_trail(self):
        glDisable(GL_TEXTURE_2D)
        glLineWidth(2.0)
        glBegin(GL_LINE_STRIP)
        for idx in range(18):
            trail_angle = self.sat_angle - idx * max(2.5, self.sat_speed * 18.0)
            pos = self._satellite_position(trail_angle)
            fade = max(0.0, 1.0 - idx / 18.0)
            glColor4f(0.58, 0.9, 1.0, 0.28 * fade)
            glVertex3f(pos[0], pos[1], pos[2])
        glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_TEXTURE_2D)

    def updateSatelliteParameters(self, sat_type, sat_size, sat_speed,
                                  orbital_radius, inclination,
                                  eccentricity, frequency,
                                  antenna_gain, transmit_power):
        self.sat_type = sat_type
        self.sat_size = sat_size
        self.sat_speed = sat_speed
        self.orbital_radius_units = orbital_radius
        self.inclination = inclination
        self.eccentricity = eccentricity
        self.frequency = frequency
        self.antenna_gain = antenna_gain
        self.transmit_power = transmit_power
        self._recompute_orbital_radius()
        if self.gl_ready:
            self._build_satellite()
        self.update()

    def updateBaseStationParameters(self, gs_name, gs_lat, gs_lon, gs_alt,
                                    min_elevation, gs_antenna_gain):
        self.gs_name = gs_name
        self.gs_lat = gs_lat
        self.gs_lon = gs_lon
        self.gs_alt = gs_alt
        self.min_elevation = min_elevation
        self.gs_antenna_gain = gs_antenna_gain
        self.update()

    def updateCommParameters(self, base_delay_ms, jitter_ms, ber, mode):
        self.base_delay_ms = base_delay_ms
        self.jitter_ms = jitter_ms
        self.ber = ber
        self.ber_mode = mode
        self.update()

    def getCurrentParameters(self):
        return {
            'sat_type': self.sat_type,
            'sat_size': self.sat_size,
            'sat_speed': self.sat_speed,
            'orbital_radius': self.orbital_radius_units,
            'inclination': self.inclination,
            'eccentricity': self.eccentricity,
            'frequency': self.frequency,
            'antenna_gain': self.antenna_gain,
            'transmit_power': self.transmit_power,
            'gs_name': self.gs_name,
            'gs_lat': self.gs_lat,
            'gs_lon': self.gs_lon,
            'gs_alt': self.gs_alt,
            'min_elevation': self.min_elevation,
            'gs_antenna_gain': self.gs_antenna_gain,
            'base_delay_ms': self.base_delay_ms,
            'jitter_ms': self.jitter_ms,
            'ber': self.ber,
            'mode': self.ber_mode
        }

if __name__=='__main__':
    app = QApplication(sys.argv)
    view = EarthSatelliteView()
    view.resize(800,600)
    view.show()
    sys.exit(app.exec_())
