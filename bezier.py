#!/usr/bin/python
# coding: UTF-8
#
# This file is part of the pyTile project
#
# http://entropy.me.uk/pytile
#
## Copyright � 2008-2009 Timothy Baldock. All Rights Reserved.
##
## Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
##
## 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
##
## 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
##
## 3. The name of the author may not be used to endorse or promote products derived from this software without specific prior written permission from the author.
##
## 4. Products derived from this software may not be called "pyTile" nor may "pyTile" appear in their names without specific prior written permission from the author.
##
## THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. 

DEBUG = False

import os
import sys
import math

import pygame
from pygame.locals import *

import logger
debug = logger.Log()
 
from vec2d import *
 
grey = (100,100,100)
lightgray = (200,200,200)
red = (255,0,0)
darkred = (192,0,0)
green = (0,255,0)
darkgreen = (0,128,0)
blue = (0,0,255)
darkblue = (0,0,192)
brown = (72,64,0)
silver = (224,216,216)
black = (0,0,0)
white = (255,255,255)
yellow = (255,255,0)

FPS_REFRESH = 500
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800

# Size of the world in tiles
xWorld = 10
yWorld = 10

TILE_SIZE = 128
#TILE_SIZE = 96
#TILE_SIZE = 96

DRAW_HINTS = False

class World(object):
    """Global world object for all Tiles to reference"""
    init = True
    def __init__(self):
        if World.init:
            World.xWorld = xWorld
            World.yWorld = yWorld
            # Starting offsets, these will center the map by default
            World.offx = WINDOW_WIDTH / 2 - World.xWorld * TILE_SIZE / 2
            World.offy = WINDOW_HEIGHT / 2 - World.yWorld * TILE_SIZE / 2

class Bezier(object):
    """Bezier curve related methods"""
    def calculate_bezier(self, p, steps=30):
        """Calculate a bezier curve from 4 control points and return a list of the resulting points.
        This function uses the forward differencing algorithm described here: 
        http://www.niksula.cs.hut.fi/~hkankaan/Homepages/bezierfast.html"""

        # Bypasses the generation of a bezier curve in straight-line cases
        if len(p) == 2:
            return ([p[1], p[0]], [p[1] - p[0],p[1] - p[0]])

        t = 1.0 / steps
        temp = t*t
        
        f = p[0]
        fd = 3 * (p[1] - p[0]) * t
        fdd_per_2 = 3 * (p[0] - 2 * p[1] + p[2]) * temp
        fddd_per_2 = 3 * (3 * (p[1] - p[2]) + p[3] - p[0]) * temp * t
        
        fddd = fddd_per_2 + fddd_per_2
        fdd = fdd_per_2 + fdd_per_2
        fddd_per_6 = fddd_per_2 * (1.0 / 3)
        
        points = []
        tangents = []
        for x in range(steps):
            points.append(f)
            tangents.append(fd)
            f = f + fd + fdd_per_2 + fddd_per_6
            fd = fd + fdd + fddd_per_2
            fdd = fdd + fddd
            fdd_per_2 = fdd_per_2 + fddd_per_2
        points.append(f)
        tangents.append(fd)
        return (points, tangents)

    def get_at_width(self, point, tangent, width):
        """"""
        newpoint = point + tangent.perpendicular_normal() * width
        return newpoint

    def get_point_at_width(self, a, b, width):
        """"""
        a_to_b = b - a
        c = a + a_to_b.perpendicular_normal() * width
        d = b + a_to_b.perpendicular_normal() * width
        return d

    def find_midpoint(self, a, b):
        """"""
        a_to_b = b - a
        return a + a_to_b / 2.0

    def get_lengths(self, cps):
        """Return array of segment lengths for curve defined by the points in cps"""
        lengths = []
        for p in range(1, len(cps)):
            # Get gradient of a->b
            b = cps[p]
            a = cps[p-1]
            a_to_b = b - a
            ab_n = a_to_b.normalized()
            # Find length of vector divided by normal vector (number of unit lengths)
            lengths.append(a_to_b.get_length() / ab_n.get_length())
        return lengths

    def get_length(self, cps):
        """Return an approximation of the length of the curve
        defined by the control points in cps"""
        lengths = self.get_lengths(cps)
        return sum(lengths)

    def get_segment_vectors(self, cps):
        """Return segment vectors for curve defined by cps"""
        segments = []
        for p in range(1, len(cps)):
            # Get gradient of a->b
            b = cps[p]
            a = cps[p-1]
            a_to_b = b - a
            segments.append(a_to_b)
        return segments

    def get_point_at_length(self, cps, length):
        """Return a vec2d representing the coords of the point on the curve
        at the length specified in real terms"""
        # 1. look up array of segment vectors
        # cps is array from one endpoint to the other, need to find segments
        # in-between these points
        # Points:   0-1-2-3-4
        # Segments:  0-1-2-3
        segments = self.get_segment_vectors(cps)
        # 2. loop through these until the segment length is found
        running_total = 0
        remainder = 0
        exact_point = False
        for n, s in enumerate(segments):
            seg_length = s.get_length() / s.normalized().get_length()
            if running_total + seg_length == length:
                # Edge case, length falls exactly on a segment endpoint
                # Don't need to go any further, find exact point and break out
                exact_point = cps[n+1]
                break
            elif running_total + seg_length > length:
                # Don't need to go any further, find exact point and break out
                remainder = length - running_total
                exact_point = cps[n] + s.normalized() * remainder
                break
            else:
                # Continue
                running_total += seg_length
        return exact_point

        # 3. If segment outside curve, return False
        # 4. Once segment found, multiply remainder by the unit vector for
        #    that segment to find the coordinates of that point

    def nearest_point_on_curve(self, P, cps):
        """Compute the parameter value fo the point on a Bezier curve
        segment closest to some arbitrary, user-input point
        Return point on the curve at that parameter value"""
        self.maxdepth = 64
        self.epsilon = math.ldexp(1.0, -self.maxdepth-1)
        rec_depth = 0
        w_degree = 5
        degree = 3
        # Convert point p and bezcurve defined by control points cps into
        # a 5th-degree bezier curve form
        w = self.convert_to_bezier_form(P, cps)
        # Find all possible roots of that 5th degree equation
        n_candidates = self.find_roots(w, rec_depth)
        t_candidates = self.tvals

        # Check distance to beginning of curve, where t = 0
        dist = (P - cps[0]).get_length_sqrd()
        tval = 0.0

        # Compare distances of point p to all candidate points found as roots
        for t in t_candidates:
            p = self.get_at_t(cps, t)
            new_dist = (P - p).get_length_sqrd()
            if new_dist < dist:
                dist = new_dist
                tval = t

        # Finally, look at distance to end point, where t = 1.0
        new_dist = (P - cps[3]).get_length_sqrd()
        if new_dist < dist:
            dist = new_dist
            tval = 1.0

        #print tval, dist, self.tvals

        # Return point on curve at parameter value tval
        return self.get_at_t(cps, tval)

    def convert_to_bezier_form(self, P, cps):
        """Given a point and control points for a bezcurve, generate 5th degree
        Bezier-format equation whose solution finds the point on the curve
        nearest the user-defined point"""
        # Precomputed "z" values for cubics
        z = [[1.0, 0.6, 0.3, 0.1],
             [0.4, 0.6, 0.6, 0.4],
             [0.1, 0.3, 0.6, 1.0]]
        # Determine the "c" values, these are vectors created by subtracting
        # point P from each of the control points
        c = []
        for cp in cps:
            c.append(cp - P)
        # Determine the "d" values, these are vectors created by subtracting
        # each control point from the next (and multiplying by 3?)
        d = []
        for i in range(len(cps)-1):
            d.append((cps[i+1] - cps[i]) * 3.0)
        # Create table of c/d values, table of the dot products of the
        # values from c and d
        cdtable = []
        for row in range(len(cps)-1):
            temp = []
            for col in range(len(cps)):
                temp.append(d[row].dot(c[col]))
            cdtable.append(temp)
        # A little unsure about this part, the C-code was unclear!
        # Apply the "z" values to the dot products, on the skew diagonal
        # Also set up the x-values, making these "points"                   - What does this mean?
        w = []
        n = len(cps) - 1
        m = len(cps) - 2
        # Bezier is uniform parameterised
        for i in range(6):
            w.append(vec2d(i/5.0, 0.0))
        for k in range(n+m+1):
            lb = max(0, k - m)
            ub = min(k, n)
            for i in range(lb, ub+1):
                j = k - i
                w[i+j].y += cdtable[j][i] * z[j][i]
        return w
    def find_roots(self, cps, depth):
        """Given a 5th degree equation in Bernstein-Bezier form, find
        all the roots in the interval [0,1]. Return number of roots found"""
        if depth == 0:
            # First level of recursion, set up variables used by the next steps
            self.tvals = []
        cc = self.crossing_count(cps)
        if cc is 0:
            # No solutions here
            return 0
        elif cc is 1:
            # Unique solution
            # Stop recursion when enough recursions have occured (deep enough)
            # If deep enough, return 1 solution at midpoint of current curve
            if depth >= self.maxdepth:
                # cps here is relative, i.e. it refers to the control points
                # of the bisected bezier curve that this branch of recursion
                # is dealing with
                self.tvals.append((cps[0].x + cps[-1].x) / 2.0)
                return 1
            elif self.polygon_flat_enough(cps):
                self.tvals.append(self.compute_x_intercept(cps))
                return 1
        # Otherwise, solve recursively after subdividing control polygon
        left, right = self.subdivide_bezier(cps, 0.5)
        left_count = self.find_roots(left, depth+1)
        right_count = self.find_roots(right, depth+1)
        # All solutions are still being stored in self.tvals, so no need
        # to gather them together

        # Send back total number of solutions
        return left_count + right_count
    def crossing_count(self, cps):
        """Count the number of times a bezier control polygon crosses
        the 0-axis, this number is >= the number of roots"""
        crossings = 0
        # Starting state for sign
        sign = math.copysign(1, cps[0].y)
        old_sign = math.copysign(1, cps[0].y)
        for cp in cps:
            sign = math.copysign(1, cp.y)
            if sign != old_sign:
                crossings += 1
            old_sign = sign
        return crossings
    def polygon_flat_enough(self, cps):
        """Check if the control polygon of a bezier curve is flat
        enough for recursive subdivision to bottom out"""
        # Derive implicit equation for line connecting first and last
        # control points
        a = cps[0].y - cps[-1].y
        b = cps[-1].x - cps[0].x
        c = cps[0].x * cps[-1].y - cps[-1].x * cps[0].y

        max_above = 0.0
        max_below = 0.0

        for cp in cps:
            value = a * cp.x + b * cp.y + c
            if value > max_above:
                max_above = value
            elif value < max_below:
                max_below = value

        # Implicit equation for zero line
        a1 = 0.0
        b1 = 1.0
        c1 = 0.0
        # Implicit equation for "above" line
        a2 = a
        b2 = b
        c2 = c - max_above
        det = a1 * b2 - a2 * b1
        dInv = 1.0 / det
        intercept_1 = (b1 * c2 - b2 * c1) * dInv
        # Implicit equation for "below" line
        a2 = a
        b2 = b
        c2 = c - max_below
        det = a1 * b2 - a2 * b1
        dInv = 1.0 / det
        intercept_2 = (b1 * c2 - b2 * c1) * dInv
        # Compute intercepts of bounding box
        left_intercept = min(intercept_1, intercept_2)
        right_intercept = max(intercept_1, intercept_2)

        error = right_intercept - left_intercept
        if error < self.epsilon:
            return 1
        else:
            return 0

    def compute_x_intercept(self, cps):
        """Compute intersection of line from first control point
        to last control point with the 0-axis"""
        x_lk = 1.0
        y_lk = 0.0
        x_nm = cps[-1].x - cps[0].x
        y_nm = cps[-1].y - cps[0].y
        x_mk = cps[0].x
        y_mk = cps[0].y

        det = x_nm * y_lk - y_nm * x_lk
        dInv = 1.0/det

        return x_lk * (x_nm * y_mk - y_nm * x_mk) * dInv

    def build_vtemp(self, cps, t):
        """"""
        Vtemp = []
        vt2 = []
        for x in range(len(cps)):
            vt = []
            vt22 = []
            for y in range(len(cps)):
                vt.append(vec2d(0,0))
                vt22.append(0)
            vt2.append(vt22)
            Vtemp.append(vt)
                
        # Copy control points
        #print "control points are: %s" % cps
        for n, cp in enumerate(cps):
            Vtemp[0][n].x = cp.x
            vt2[0][n] = 2
            Vtemp[0][n].y = cp.y
        # Triangle computation
        for i in range(1, len(cps)):
            for j in range(len(cps) - i):
                Vtemp[i][j].x = (1.0 - t) * Vtemp[i-1][j].x + t * Vtemp[i-1][j+1].x
                Vtemp[i][j].y = (1.0 - t) * Vtemp[i-1][j].y + t * Vtemp[i-1][j+1].y
                vt2[i][j] = 1
        #for a in Vtemp:
        #    print a
        #for a in vt2:
        #    print a
        return Vtemp

    def subdivide_bezier(self, cps, t):
        """Subdivide bezier curve into two smaller curves
        Split occurs at parameter value t"""
        Vtemp = self.build_vtemp(cps, t)
        left = []
        right = []
        for j in range(len(cps)):
            left.append(Vtemp[j][0])
            right.append(Vtemp[len(cps)-1 - j][j])

        return (left, right)

    def get_at_t(self, cps, t):
        """Evaluate bezier curve at particular parameter value"""
        Vtemp = self.build_vtemp(cps, t)

        return Vtemp[len(cps)-1][0]

class Tile(pygame.sprite.Sprite):
    """A tile containing tracks, drawn in layers"""
    init = True
    props = {
             "track_width": 0.05,           # Relative to tile size
             "track_spacing": 2.0,
             "sleeper_spacing": 0.75,
             "sleeper_width": 0.3,
             "sleeper_length": 1.5,
             "rail_spacing": 0.9,
             "rail_width": 0.2,
             "ballast_width": 2.3,
             "curve_factor": 0.3,           # Relative to tile size
             "curve_multiplier": 0.02,
             }
    props_lookup = []
    for key in props.keys():
        props_lookup.append(key)

    def get_dimension(self, key):
        """Lookup and return a dimension value by numbered key"""
        return Tile.props[Tile.props_lookup[key]]

    def change_dimension(self, key, value):
        """Change one of the dimension values, lookup is by key number"""
        Tile.props[Tile.props_lookup[key]] = value
        self.update_dimensions()
        return True

    def update_dimensions(self):
        """Calculate actual dimensions for drawing track from the multiplier values"""
        # Setup constants
        # Track drawing
        track_width = Tile.size * Tile.props["track_width"]
        Tile.track_spacing = track_width * Tile.props["track_spacing"]
        Tile.sleeper_spacing = track_width * Tile.props["sleeper_spacing"]
        Tile.sleeper_width = track_width * Tile.props["sleeper_width"]
        Tile.sleeper_length = track_width * Tile.props["sleeper_length"]
        Tile.rail_spacing = track_width * Tile.props["rail_spacing"]
        Tile.rail_width = track_width * Tile.props["rail_width"]
        if Tile.rail_width < 1:
            Tile.rail_width = 1
        Tile.ballast_width = track_width * Tile.props["ballast_width"]
        # Curve offsets
        Tile.curve_factor = Tile.size * Tile.props["curve_factor"]
        Tile.curve_multiplier = Tile.curve_factor * Tile.props["curve_multiplier"]


    def __init__(self, position, type, track_width=2.5, curve_factor=12):
        pygame.sprite.Sprite.__init__(self)
        if Tile.init:
            Tile.bezier = Bezier()
            tex = pygame.image.load("ballast_texture.png")
            Tile.ballast_texture = tex.convert()
            Tile.init = False
            Tile.size = TILE_SIZE
            Tile.font = pygame.font.SysFont("Arial", 12)
            Tile.bezier_steps = 30
            self.update_dimensions()

        # Position of the tile in tile coordinates from which the world coordinates are derived
        self.position = position

        # Type determines which part of the image this sprite draws (rails, sleepers, ballast or hints)
        self.type = type

        # Init variables
        self.paths = []
        self.paths_changed = False
        self.highlight_changed = False
        self.control_hint = None

        self.box = [vec2d(Tile.size, Tile.size),
                    vec2d(0, Tile.size),
                    vec2d(0, 0),
                    vec2d(Tile.size, 0)]

        self.calc_rect()

        self.box_midpoints = []
        self.box_allmidpoints = []
        for p in range(len(self.box)):
            self.box_midpoints.append(self.bezier.find_midpoint(self.box[p-1], self.box[p]))
        box_mids_temp = []
        box_mids_temp2 = []


        for p in range(len(self.box_midpoints)):
            # Vector from origin to start point, unit vector representing the gradient of this vector
            box_mids_temp.append(self.bezier.find_midpoint(self.box_midpoints[p-1], self.box_midpoints[p]))

            box_mids_temp.append(self.box_midpoints[p])

        # Copy the midpoints array
        for p in box_mids_temp:
            box_mids_temp2.append(p)
        # Offset the midpoints array
        for p in range(4):
            box_mids_temp2.insert(0, box_mids_temp2.pop())

        for p, q in zip(box_mids_temp, box_mids_temp2):
            # Append the vector to the starting point followed by the vector from the starting point to the endpoint on the other side
            self.box_allmidpoints.append([p, (q - p).normalized()])

        # Used for drawing the paths in the tile, [vector from origin to the point, gradient at that point, tangent (in iso space) at that point]
        self.box_endpoints = []

        p = self.box_allmidpoints

        for p in self.box_allmidpoints:
            self.box_endpoints.append([p[0] - p[1].perpendicular() * Tile.track_spacing,    p[1],    p[1].perpendicular()])
            self.box_endpoints.append([p[0],                                                p[1],    p[1].perpendicular()])
            self.box_endpoints.append([p[0] + p[1].perpendicular() * Tile.track_spacing,    p[1],    p[1].perpendicular()])

        self.image = pygame.Surface((self.size, self.size/2))
        self.image.fill(black)
        self.image.set_colorkey(black, pygame.RLEACCEL)
        self.paths_changed = True
        self.init_box = True
        self.update()


    def add_path(self, path):
        """Add another path to this tile
        Only add a path if that path does not already exist
        Only add a path if it passes the bounds checks for this track type"""
        debug("add_path - add: %s to existing: %s" % (path, self.paths))
        if path in self.paths or path[::-1] in self.paths:
            # Trying to add duplicate path
            return False
        else:
            # Path is not a duplicate, check if it is allowed
            # Divide by the number of paths per side, then find "angle" (in number of sides) between the two
            # sides being compared. If this is in the allowed "angles" permit drawing of this path
            side1, subside1 = divmod(path[0], 3)
            side2, subside2 = divmod(path[1], 3)
            # K determines the allowed "angle" between two endpoints
            # 0 is endpoint to itself, 1 is endpoint to immediate neighbour etc. 4 is endpoint to its opposite
            # Disallow values of K to restrict endpoints
##            K = [0,1,2,3,4]
            K = [3,4]
            L = [0,1,2,3,4,3,2,1]
            for i in range(side1):
                L.insert(0, L.pop())
            debug("add_path - transform: %s, result: %s, lookup: %s, result: %s" % (side1, L, side2, L[side2]))
            if L[side2] in K:
                self.paths.append(path)
                self.paths_changed = True
                self.update()
                return True
            else:
                return False

    def remove_path(self, path):
        """Remove a path from this tile
        Return True if path removed, False if path doesn't exist"""
        print "remove_path - self.paths: %s" % self.paths
        if path in self.paths or path[::-1] in self.paths:
            print   self.paths
            self.paths.remove(path)
            print self.paths
            self.paths_changed = True
            self.update()
            return True
        else:
            return False

    def set_control_hint(self, endpoint_number):
        """Add a control hint to this sprite, used to indicate which endpoints are active
        Pass None as endpoint_number to clear the control hint"""
        self.control_hint = endpoint_number
        self.highlight_changed = True
        self.update()

    def calc_rect(self):
        """Calculate the current rect of this tile"""
        x = self.position[0]
        y = self.position[1]
        p = self.size
        p2 = self.size / 2
        p4 = self.size / 4
        # Global screen positions
        self.xpos = xWorld*p2 - (x * p2) + (y * p2) - p2
        self.ypos = (x * p4) + (y * p4)
        # Rect position takes into account the offset
        self.rect = (self.xpos + World.offx, self.ypos + World.offy, p, p)
        return self.rect

    def update(self, update_type=0):
        """Draw the image this tile represents"""
        # Draw a track for every entry in paths
        if (self.paths_changed or update_type == 2) and self.type in ["rails", "sleepers", "ballast"]:
            # Reset image
            self.image.fill(black)
            # Only update the image once when first drawn, can be persistent after that (redrawn when the paths change only)
            self.paths_changed = False
            paths_to_draw = []
            for p in self.paths:
                paths_to_draw.append(self.calc_control_points(p))
            if self.type == "rails":
                for p in paths_to_draw:
                    self.draw_rails(p)
            elif self.type == "sleepers":
                for p in paths_to_draw:
                    self.draw_sleepers(p)
            elif self.type == "ballast":
                self.draw_ballast(paths_to_draw)
        # Box never changes, draw once only
        if self.init_box and self.type == "box":
            self.init_box = False
            self.draw_box()
        self.calc_rect()

    def calc_control_points(self, p):
        """Calculate control points from a path"""
        a = self.box_endpoints[p[0]][0]
        d = self.box_endpoints[p[1]][0]
        # If this tile is a straight line no need to use a bezier curve
        if p[0] + p[1] in [32,26,20,14]:
            return [a,d]
        else:
            p0 = p[0]
            p1 = p[1]
            # This gets us +1, +0 or -1, to bring the real value of the end point up to the midpoint
            p03 = -1 * ((p0 % 3) - 1)
            p13 = -1 * ((p1 % 3) - 1)
            # Curve factor is the length between the two endpoints of each of the two curve control points
            # By varying the length of these control points, we can make the curve smoother and sharper
            # Taking two control points which make up a path, for each one multiply curve factor by 
            # either + or - of the offset location of the other point
            # Find midpoint to real point vectors
            x = (self.box_endpoints[p[1]][1] * Tile.track_spacing).length
            y = (self.box_endpoints[p[0]][1] * Tile.track_spacing).length

            b = self.box_endpoints[p[0]][0] + self.box_endpoints[p[0]][1] * self.curve_factor
            c = self.box_endpoints[p[1]][0] + self.box_endpoints[p[1]][1] * self.curve_factor

            return [a,b,c,d]

    def draw_box(self):
        #Translate points into iso space
        box_points = []
        for p in self.box_endpoints:
            box_points.append(p[0])
        box_points = self.translate_points(box_points)
        box_mids = self.translate_points(self.box_midpoints)
        print "box_points: %s" % box_points
        # Draw the outline of the box
        pygame.draw.lines(self.image, True, darkblue, box_mids)
        # Draw the remaining box endpoints
        for n, p in enumerate(box_points):
            # Draw red circles indicating the path endpoints
            pygame.draw.circle(self.image, red, (int(p[0]),int(p[1])), 0)
            if n == 1:
                pygame.draw.circle(self.image, green, (int(p[0]),int(p[1])), 2)
            # Draw normal lines indicating the path endpoints
##            pygame.draw.line(self.image, darkblue, p[0], p[0] + 20 * p[1])

    def draw_sleepers(self, control_points):
        """draw the sleeper component of the track"""
        # calculate bezier curve points and tangents
        cps, tangents = self.bezier.calculate_bezier(control_points, 30)
        overflow = Tile.sleeper_spacing * -0.5
        sleeper_points = []
        start = True
        # calculate total length of this curve section based on the straight lines which make it up
        total_length = self.bezier.get_length(cps)
        # number of sleepers is length, (minus one interval to make the ends line up) divided by interval length
        num_sleepers = float(total_length) / float(Tile.sleeper_spacing)
        true_spacing = float(total_length) / float(math.ceil(num_sleepers))

        for p in range(1, len(cps)):
            # find gradient of a->b
            b = cps[p]
            a = cps[p-1]
            a_to_b = b - a
            ab_n = a_to_b.normalized()
            # vector to add to start vector, to get offset start location
            start_vector = overflow * ab_n
            # number of sleepers to draw in this section
            n_sleepers, overflow = divmod((a_to_b + start_vector).get_length(), 
                                          (ab_n * true_spacing).get_length())
            n_sleepers = int(n_sleepers)
            # loop through n_sleepers, draw a sleeper at the start of each sleeper spacing interval
            if start:
                s = 0
                start = False
            else:
                s = 1
            for n in range(s, n_sleepers+1):
                sleep_p = [self.bezier.get_at_width(a - start_vector + n*ab_n*true_spacing - ab_n*0.5*self.sleeper_width, a_to_b, -self.sleeper_length),
                           self.bezier.get_at_width(a - start_vector + n*ab_n*true_spacing - ab_n*0.5*self.sleeper_width, a_to_b, self.sleeper_length),
                           self.bezier.get_at_width(a - start_vector + n*ab_n*true_spacing + ab_n*0.5*self.sleeper_width, a_to_b, self.sleeper_length),
                           self.bezier.get_at_width(a - start_vector + n*ab_n*true_spacing + ab_n*0.5*self.sleeper_width, a_to_b, -self.sleeper_length)]
                # translate points into iso perspective
                sleeper_points.append(self.translate_points(sleep_p))


        # finally draw all the sleeper points
        for p in sleeper_points:
            pygame.draw.polygon(self.image, brown, p, 0)

    def draw_ballast(self, points_to_draw):
        """Draw the ballast component of the track"""
        # Draw out to the image
        surface = pygame.Surface((self.size, self.size))
        # Black surface, draw onto it in white, then set colourkey to white so only black parts drawn over the final texture,
        surface.fill(black)
        for control_points in points_to_draw:
            # Calculate bezier curve points and tangents
            cps, tangents = self.bezier.calculate_bezier(control_points, 30)
            # Polygon defined by the two lines at either side of the track
            ballast_points = []
            # Add one side
            for p in range(0, len(cps)):
                ballast_points.append(self.bezier.get_at_width(cps[p], tangents[p], Tile.ballast_width))
            ballast_points.reverse()
            for p in range(0, len(cps)):
                ballast_points.append(self.bezier.get_at_width(cps[p], tangents[p], -Tile.ballast_width))
            # Translate points into iso space
            ballast_points = self.translate_points(ballast_points)
            pygame.draw.polygon(surface, white, ballast_points, 0)
        # Set mask key to white, so only the outline parts drawn
        surface.set_colorkey(white, pygame.RLEACCEL)
        # Blit in the texture
        self.image.blit(self.ballast_texture, (0,0), (0,0,self.image.get_width(), self.image.get_height()))
        # Blit in the mask to obscure invisible parts of the texture with black
        self.image.blit(surface, (0,0))
        # Then set colourkey of the final surface to black to remove the mask
        self.image.set_colorkey(black)


    def draw_rails(self, control_points):
        """Draw the rails component of the track"""
        # Calculate bezier curve points and tangents
        cps, tangents = self.bezier.calculate_bezier(control_points, 30)
        if DEBUG:
            pygame.draw.lines(self.image, red, False, cps, 1)
            pygame.draw.lines(self.image, silver, False, cps2, 1)
        for s in [1, -1]:
            points1 = []
            for p in range(0, len(cps)):
                points1.append(self.bezier.get_at_width(cps[p], tangents[p], s*self.rail_spacing))
            points1 = self.translate_points(points1)
            pygame.draw.lines(self.image, silver, False, points1, Tile.rail_width)

    def translate_points(self, points):
        """Translate a set of points to convert from world space into iso space"""
        scale = vec2d(1,0.5)
        out = []
        for p in points:
            out.append(p*scale)
        return out



class DisplayMain(object):
    """This handles the main initialisation
    and startup for the display"""
    def __init__(self, width, height):
        # Initialize PyGame
        pygame.init()
        
        # Set the window Size
        self.screen_width = width
        self.screen_height = height
        
        # Create the Screen
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))#, pygame.RESIZABLE)
        self.screen.fill(darkgreen)

        #tell pygame to keep sending up keystrokes when they are held down
        pygame.key.set_repeat(500, 30)

        # Setup fonts
        self.font = pygame.font.SysFont("Arial", 16)

        # Set up variables
        self.refresh_screen = True

        self.world = World()

    def control_locate(self, mousepos, tolerance=7):
        """Locate all control points close to the mouse position"""
        x = mousepos[0] - World.offx
        y = mousepos[1] - World.offy
        control_points = []
        for a in range(xWorld):
            for b in range(yWorld):
                for n, c in enumerate(self.map[a][b]["controls"]):
                    # Rough tolerance check
                    if abs(x - c[0]) < tolerance and abs(y - c[1]) < tolerance:
                        xx = abs(x - c[0])
                        yy = abs(y - c[1])
                        # Expensive tolerance check if rough passes
                        if math.sqrt(xx * xx + yy * yy) <= tolerance:
                            control_points.append([a, b, n])
        return control_points

    def MainLoop(self):
        """This is the Main Loop of the Game"""
        # Initiate the clock
        self.clock = pygame.time.Clock()

        self.box_size = 200

        # Settings for FPS counter
        self.fps_refresh = FPS_REFRESH
        self.fps_elapsed = 0

        # The currently selected point
        self.selected = None
        # Array to contain endpoint positions selected during the start of a draw operation
        self.start_positions = []
        # Stores the last recorded drag operation position for world movement
        self.last_rmbpos = (0,0)

        # Current tool mode
        self.mode = "add"


        # Layers to draw, first listed drawn first
        layers = [
                  "box",
                  "ballast",
                  "sleepers",
                  "rails",
                  "highlight",
                  ]

        # 2D array, [x][y]
        self.sprites = pygame.sprite.LayeredUpdates()

        # Can look up in self.map:
        #   self.map[x][y]["paths"] -> List of paths for this tile
        #   self.map[x][y]["layers"] -> List of all the tile sprites making up this tile by layer

        # Map, used to look up all the tiles
        self.map = []
        for x in range(xWorld):
            a = []
            for y in range(yWorld):
                b = {"paths": [], "layers": {}, "controls": []}
                for c, d in enumerate(layers):
                    b["layers"][d] = Tile((x,y), d)
                    self.sprites.add(b["layers"][d], layer=c)
                a.append(b)
            self.map.append(a)

        # Testing paths
        for x in range(2,7):
            self.map[x][4]["layers"]["rails"].add_path([1, 13]) 
            self.map[x][4]["layers"]["sleepers"].add_path([1, 13]) 
            self.map[x][4]["layers"]["ballast"].add_path([1, 13]) 
        for x in range(2,8):
            self.map[x][7]["layers"]["rails"].add_path([0, 14]) 
            self.map[x][7]["layers"]["sleepers"].add_path([0, 14]) 
            self.map[x][7]["layers"]["ballast"].add_path([0, 14]) 
        for x in range(2,8):
            self.map[x][7]["layers"]["rails"].add_path([2, 12]) 
            self.map[x][7]["layers"]["sleepers"].add_path([2, 12]) 
            self.map[x][7]["layers"]["ballast"].add_path([2, 12]) 

        self.map[6][4]["layers"]["rails"].add_path([13, 22])  
        self.map[5][3]["layers"]["rails"].add_path([10, 22])  
        self.map[4][2]["layers"]["rails"].add_path([10, 1])  
        self.map[3][2]["layers"]["rails"].add_path([1, 13])  
        self.map[6][4]["layers"]["sleepers"].add_path([13, 22])  
        self.map[5][3]["layers"]["sleepers"].add_path([10, 22])  
        self.map[4][2]["layers"]["sleepers"].add_path([10, 1])  
        self.map[3][2]["layers"]["sleepers"].add_path([1, 13])  
        self.map[6][4]["layers"]["ballast"].add_path([13, 22])  
        self.map[5][3]["layers"]["ballast"].add_path([10, 22])  
        self.map[4][2]["layers"]["ballast"].add_path([10, 1])  
        self.map[3][2]["layers"]["ballast"].add_path([1, 13])  

        self.map[6][7]["layers"]["rails"].add_path([12, 23])  
        self.map[5][6]["layers"]["rails"].add_path([2, 9])  
        self.map[4][6]["layers"]["rails"].add_path([2, 12])  
        self.map[6][7]["layers"]["rails"].add_path([14, 21])  
        self.map[5][6]["layers"]["rails"].add_path([0, 11])  
        self.map[4][6]["layers"]["rails"].add_path([0, 14])  
        self.map[6][7]["layers"]["sleepers"].add_path([12, 23])  
        self.map[5][6]["layers"]["sleepers"].add_path([2, 9])  
        self.map[4][6]["layers"]["sleepers"].add_path([2, 12])  
        self.map[6][7]["layers"]["sleepers"].add_path([14, 21])  
        self.map[5][6]["layers"]["sleepers"].add_path([0, 11])  
        self.map[4][6]["layers"]["sleepers"].add_path([0, 14])  
        self.map[6][7]["layers"]["ballast"].add_path([12, 23])  
        self.map[5][6]["layers"]["ballast"].add_path([2, 9])  
        self.map[4][6]["layers"]["ballast"].add_path([2, 12])  
        self.map[6][7]["layers"]["ballast"].add_path([14, 21])  
        self.map[5][6]["layers"]["ballast"].add_path([0, 11])  
        self.map[4][6]["layers"]["ballast"].add_path([0, 14])  

        self.altervalue = 0
        self.modified = True

        while True:
            self.clock.tick(0)
            # If there's a quit event, don't bother parsing the event queue
            if pygame.event.peek(pygame.QUIT):
                pygame.display.quit()
                sys.exit()

            # Clear the stack of dirty tiles
            self.dirty = []
            clear = False
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.display.quit()
                        sys.exit()
                    if event.key == pygame.K_q:
                        # Decrease currently active value
                        self.map[0][0]["layers"]["rails"].change_dimension(self.altervalue, self.map[0][0]["layers"]["rails"].get_dimension(self.altervalue) - 0.01)
                        self.modified = 2
                        print "decrease"
                    if event.key == pygame.K_w:
                        # Increase currently active value
                        self.map[0][0]["layers"]["rails"].change_dimension(self.altervalue, self.map[0][0]["layers"]["rails"].get_dimension(self.altervalue) + 0.01)
                        self.modified = 2
                        print "increase"
                    if pygame.key.name(event.key) in map(lambda x: str(x), range(10)):
                        # If key is a number key
                        self.altervalue = int(pygame.key.name(event.key))
                        print "Now altering value of attribute: %s" % Tile.props_lookup[self.altervalue]

                if event.type == MOUSEMOTION:
                    if event.buttons[2] == 1:
                        rmbpos = event.pos
                        if rmbpos != self.last_rmbpos:
                            World.offx -= self.last_rmbpos[0] - rmbpos[0]
                            World.offy -= self.last_rmbpos[1] - rmbpos[1]
                        #print "offx: %s, offy: %s" % (World.offx, World.offy)
                        self.last_rmbpos = rmbpos
                        self.modified = 1
                if event.type == MOUSEBUTTONDOWN:
                    if event.button == 3:
                        self.last_rmbpos = event.pos
                        self.refresh_screen = True
                if event.type == MOUSEBUTTONUP:
                    pass
##                    if event.button == 3:
##                        self.drag_start = None


            if self.modified:
                self.sprites.update(self.modified)
                self.refresh_screen = True
                self.modfied = False

            # Write some useful info on the top bar
            self.fps_elapsed += self.clock.get_time()
            if self.fps_elapsed >= self.fps_refresh:
                self.fps_elapsed = 0
                pygame.display.set_caption("FPS: %i" %
                                           (self.clock.get_fps()))

            # Refresh the screen if necessary, or just draw the updated bits
            if self.refresh_screen:
                self.screen.fill(darkgreen)
                rectlist = self.sprites.draw(self.screen)
                pygame.display.update()
                self.refresh_screen = False
            else:
                for a in self.dirty:
                    self.screen.fill(darkgreen, a)
                rectlist = self.sprites.draw(self.screen)
                pygame.display.update(self.dirty)


    
if __name__ == "__main__":
    sys.stderr = debug
    sys.stdout = debug
    os.environ["SDL_VIDEO_CENTERED"] = "1"
    MainWindow = DisplayMain(WINDOW_WIDTH, WINDOW_HEIGHT)
    MainWindow.MainLoop()
