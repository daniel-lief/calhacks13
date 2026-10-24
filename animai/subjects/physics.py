"""
Physics visuals. Motion is computed, not faked: PhysicsWorld runs a real 2D rigid-body
simulation (pymunk), Pendulum integrates the nonlinear equation of motion, and
projectiles, springs and waves follow their exact formulas.
"""
from __future__ import annotations

import numpy as np

from manimlib import (
    Animation, AnimationGroup, Arrow, Circle, DashedLine, Dot, FadeIn, GrowArrow, Group,
    LaggedStart, Line, Mobject, Rectangle, RoundedRectangle, ShowCreation, Square, Succession,
    TracedPath, UpdateFromAlphaFunc, VGroup, VMobject, Write, Polygon, Arc, Rotate,
    UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, ORIGIN, PI, TAU,
)

from animai.core.media import Label
from animai.core.scaling import ScaleTracker
from animai.core.theme import get_theme, palette_color

__all__ = [
    "PhysicsWorld", "Pendulum", "Spring", "MassSpring", "ForceArrow", "FreeBodyDiagram",
    "Projectile", "Wave", "LensDiagram", "SimpleCircuit", "FieldLines",
]

_DT = 1 / 240  # Simulation step (s)


def _v3(p) -> np.ndarray:
    p = np.array(p, dtype=float).flatten()
    return np.array([p[0], p[1], p[2] if len(p) > 2 else 0.0])


# ------------------------------------------------------------------ rigid bodies

class PhysicsWorld(VGroup):
    """
    A 2D rigid-body world (pymunk). Units are scene units and seconds; gravity defaults to
    9.8 down. Build it, show it, then `self.play(world.simulate(3))` to run 3 seconds of
    physics (calls can be chained; each continues where the last stopped).

    Bodies: `add_ball(pos, radius, mass, velocity, elasticity)`, `add_box(pos, width, height,
    mass, velocity, angle)`. Static: `add_ground(y)`, `add_wall(a, b)`, `add_ramp(a, b)`.
    Joints: `add_spring(body_a, body_b, rest_length, stiffness, damping)`,
    `add_pendulum_rod(body, pivot)`. `world.trace(body)` returns a trail to add.

    Example:
        world = PhysicsWorld()
        world.add_ground(-3)
        ball = world.add_ball((-4, 2), radius=0.35, velocity=(3, 0), elasticity=0.85)
        self.show(world, "main"); self.add(world.trace(ball))
        self.play(world.simulate(4))
    """

    def __init__(self, gravity=(0, -9.8), **kwargs):
        import pymunk
        self._pymunk = pymunk
        self.space = pymunk.Space()
        self.space.gravity = tuple(gravity)
        self.tracker = ScaleTracker()
        self._bodies: list[tuple] = []   # (pymunk body, mobject)
        self._springs: list[tuple] = []  # (pymunk spring, mobject)
        self._rods: list[tuple] = []     # (body, pivot, mobject)
        super().__init__(*self.tracker.mobjects, **kwargs)

    # Static geometry
    def _segment(self, a, b, elasticity=0.8, friction=0.8, color=None, width=4):
        seg = self._pymunk.Segment(self.space.static_body, tuple(a[:2]), tuple(b[:2]), 0.02)
        seg.elasticity, seg.friction = elasticity, friction
        self.space.add(seg)
        line = Line(_v3(a), _v3(b), stroke_color=color or get_theme().muted, stroke_width=width)
        self.add(self.tracker.adopt(line))
        return line

    def add_ground(self, y: float = -3.0, x0: float = -6.5, x1: float = 6.5, **kwargs) -> Mobject:
        return self._segment((x0, y), (x1, y), **kwargs)

    def add_wall(self, a, b, **kwargs) -> Mobject:
        return self._segment(a, b, **kwargs)

    def add_ramp(self, a, b, **kwargs) -> Mobject:
        return self._segment(a, b, **kwargs)

    # Dynamic bodies
    def add_ball(self, position, radius: float = 0.3, mass: float = 1.0, velocity=(0, 0),
                 elasticity: float = 0.8, friction: float = 0.6, color=None) -> Mobject:
        pm = self._pymunk
        body = pm.Body(mass, pm.moment_for_circle(mass, 0, radius))
        body.position, body.velocity = tuple(position[:2]), tuple(velocity[:2])
        shape = pm.Circle(body, radius)
        shape.elasticity, shape.friction = elasticity, friction
        self.space.add(body, shape)
        c = color or palette_color(len(self._bodies))
        mob = VGroup(Circle(radius=radius, fill_color=c,
                            fill_opacity=1 if get_theme().name == "bubble" else 0.85, stroke_color=c,
                            stroke_width=0 if get_theme().name == "bubble" else 2),
                     Line(ORIGIN, RIGHT * radius * 0.85, stroke_color=get_theme().background,
                          stroke_width=3))  # Marker so rotation is visible
        mob.move_to(_v3(position))
        return self._register(body, mob)

    def add_box(self, position, width: float = 0.8, height: float = 0.8, mass: float = 1.0,
                velocity=(0, 0), angle: float = 0.0, elasticity: float = 0.3,
                friction: float = 0.7, color=None) -> Mobject:
        pm = self._pymunk
        body = pm.Body(mass, pm.moment_for_box(mass, (width, height)))
        body.position, body.velocity, body.angle = tuple(position[:2]), tuple(velocity[:2]), angle
        shape = pm.Poly.create_box(body, (width, height))
        shape.elasticity, shape.friction = elasticity, friction
        self.space.add(body, shape)
        c = color or palette_color(len(self._bodies))
        mob = RoundedRectangle(width=width, height=height,
                               corner_radius=min(width, height) * .16,
                               fill_color=c, fill_opacity=1 if get_theme().name == "bubble" else 0.85,
                               stroke_color=c, stroke_width=0 if get_theme().name == "bubble" else 2
                               ).rotate(angle).move_to(_v3(position))
        return self._register(body, mob)

    def _register(self, body, mob):
        mob._sim_angle = body.angle
        self.tracker.adopt(mob.shift(-mob.get_center()))
        mob.move_to(self.tracker.to_scene(_v3(body.position)))
        self._bodies.append((body, mob))
        self.add(mob)
        return mob

    def _body_of(self, mob):
        return next(b for b, m in self._bodies if m is mob)

    # Joints
    def add_spring(self, a: Mobject, b: Mobject | tuple, rest_length: float | None = None,
                   stiffness: float = 60.0, damping: float = 0.5) -> Mobject:
        """Spring between two bodies, or a body and a fixed point (pass an (x, y) tuple)."""
        pm = self._pymunk
        body_a = self._body_of(a)
        if isinstance(b, Mobject):
            body_b, anchor_b = self._body_of(b), (0, 0)
        else:
            body_b, anchor_b = self.space.static_body, tuple(b[:2])
        pa, pb = np.array(body_a.position), np.array(body_b.local_to_world(anchor_b))
        rest = rest_length if rest_length is not None else float(np.linalg.norm(pa - pb))
        spring = pm.DampedSpring(body_a, body_b, (0, 0), anchor_b, rest, stiffness, damping)
        self.space.add(spring)
        mob = Spring(self.tracker.to_scene(_v3(pb)), self.tracker.to_scene(_v3(pa)))
        self._springs.append((spring, mob))
        self.add(mob)
        self.bring_to_back(mob)
        return mob

    def add_pendulum_rod(self, bob: Mobject, pivot) -> Mobject:
        pm = self._pymunk
        body = self._body_of(bob)
        joint = pm.PinJoint(self.space.static_body, body, tuple(pivot[:2]), (0, 0))
        self.space.add(joint)
        rod = Line(self.tracker.to_scene(_v3(pivot)), bob.get_center(),
                   stroke_color=get_theme().text, stroke_width=3)
        pivot_dot = Dot(self.tracker.to_scene(_v3(pivot)), fill_color=get_theme().text)
        self._rods.append((body, _v3(pivot), rod))
        self.add(rod, pivot_dot)
        return rod

    def trace(self, mob: Mobject, color=None, width: float = 3) -> TracedPath:
        return TracedPath(mob.get_center, stroke_color=color or get_theme().accent,
                          stroke_width=width)

    def bring_to_back(self, *mobs):
        for m in mobs:
            self.remove(m)
        self.submobjects = list(mobs) + self.submobjects
        return self

    # Running
    def simulate(self, duration: float, **kwargs) -> Animation:
        """Run `duration` seconds of physics as an animation (run_time = duration)."""
        steps = max(int(round(duration / _DT)), 1)
        states = [self._snapshot()]
        for _ in range(steps):
            self.space.step(_DT)
            states.append(self._snapshot())

        def update(world, alpha):
            self._apply(states[min(int(alpha * steps), steps)])

        kwargs.setdefault("run_time", duration)
        return UpdateFromAlphaFunc(self, update, rate_func=lambda t: t, **kwargs)

    def _snapshot(self):
        return ([(_v3(b.position), b.angle) for b, _ in self._bodies],
                [(_v3(s.a.local_to_world(s.anchor_a)), _v3(s.b.local_to_world(s.anchor_b)))
                 for s, _ in self._springs])

    def _apply(self, state):
        bodies, springs = state
        for (body, mob), (pos, angle) in zip(self._bodies, bodies):
            mob.rotate(angle - mob._sim_angle)
            mob._sim_angle = angle
            mob.move_to(self.tracker.to_scene(pos))
        for (spring, mob), (pa, pb) in zip(self._springs, springs):
            mob.put_between(self.tracker.to_scene(pb), self.tracker.to_scene(pa))
        for body, pivot, rod in self._rods:
            rod.put_start_and_end_on(self.tracker.to_scene(pivot),
                                     self.tracker.to_scene(_v3(body.position)))


# ------------------------------------------------------------------ oscillators

class Spring(VMobject):
    """
    A zigzag coil between two points. `spring.put_between(a, b)` re-stretches it (use in
    updaters).

    Example: Spring(LEFT * 3, RIGHT * 1, coils=10)
    """

    def __init__(self, start, end, coils: int = 10, radius: float = 0.18, color=None, **kwargs):
        self.coils, self.radius = coils, radius
        super().__init__(stroke_color=color or get_theme().text, stroke_width=3, **kwargs)
        self.put_between(start, end)

    def put_between(self, start, end):
        a, b = _v3(start), _v3(end)
        d = b - a
        length = np.linalg.norm(d) or 1e-6
        u = d / length
        n = np.array([-u[1], u[0], 0])
        lead = min(0.15, length * 0.1)
        pts = [a, a + u * lead]
        k = self.coils * 2
        for i in range(1, k):
            t = lead + (length - 2 * lead) * i / k
            pts.append(a + u * t + n * self.radius * (1 if i % 2 else -1))
        pts += [b - u * lead, b]
        self.set_points_as_corners(pts)
        return self


class Pendulum(VGroup):
    """
    A simple pendulum, integrated exactly from θ'' = -(g/L) sin θ (so large swings are
    right too). `swing(duration)` animates it; `pendulum.bob`, `pendulum.rod`;
    `pendulum.angle_arc()` returns a live angle marker; `pendulum.trace()` a trail.

    Example: p = Pendulum(length=3, angle=40 * DEG); self.show(p, "main"); self.play(p.swing(6))
    """

    def __init__(self, length: float = 3.0, angle: float = PI / 6, g: float = 9.8,
                 damping: float = 0.0, bob_radius: float = 0.25, color=None, **kwargs):
        theme = get_theme()
        self.L, self.g, self.damping = length, g, damping
        self.theta, self.omega = angle, 0.0
        self.tracker = ScaleTracker()
        self.pivot_dot = Dot(ORIGIN, fill_color=theme.text)
        self.ceiling = Line(LEFT * 0.8, RIGHT * 0.8, stroke_color=theme.muted, stroke_width=4)
        self.rod = Line(ORIGIN, self._bob_design(), stroke_color=theme.text, stroke_width=3)
        c = color or theme.primary
        self.bob = Circle(radius=bob_radius, fill_color=c,
                          fill_opacity=1 if theme.name == "bubble" else 0.9, stroke_color=c,
                          stroke_width=0 if theme.name == "bubble" else 1)
        self.bob.move_to(self._bob_design())
        super().__init__(self.ceiling, self.rod, self.pivot_dot, self.bob, *self.tracker.mobjects,
                         **kwargs)

    def _bob_design(self, theta=None):
        th = self.theta if theta is None else theta
        return np.array([self.L * np.sin(th), -self.L * np.cos(th), 0.0])

    def _place(self):
        pivot = self.tracker.to_scene(ORIGIN)
        bob = self.tracker.to_scene(self._bob_design())
        self.rod.put_start_and_end_on(pivot, bob)
        self.bob.move_to(bob)

    def swing(self, duration: float, **kwargs) -> Animation:
        steps = max(int(duration / _DT), 1)
        thetas = [self.theta]
        th, om = self.theta, self.omega
        for _ in range(steps):  # RK4
            def acc(t, w):
                return -(self.g / self.L) * np.sin(t) - self.damping * w
            k1t, k1w = om, acc(th, om)
            k2t, k2w = om + _DT / 2 * k1w, acc(th + _DT / 2 * k1t, om + _DT / 2 * k1w)
            k3t, k3w = om + _DT / 2 * k2w, acc(th + _DT / 2 * k2t, om + _DT / 2 * k2w)
            k4t, k4w = om + _DT * k3w, acc(th + _DT * k3t, om + _DT * k3w)
            th += _DT / 6 * (k1t + 2 * k2t + 2 * k3t + k4t)
            om += _DT / 6 * (k1w + 2 * k2w + 2 * k3w + k4w)
            thetas.append(th)
        self.omega = om

        def update(_, alpha):
            self.theta = thetas[min(int(alpha * steps), steps)]
            self._place()

        kwargs.setdefault("run_time", duration)
        return UpdateFromAlphaFunc(self, update, rate_func=lambda t: t, **kwargs)

    def period(self) -> float:
        """Small-angle period 2π√(L/g)."""
        return TAU * np.sqrt(self.L / self.g)

    def trace(self, color=None) -> TracedPath:
        return TracedPath(self.bob.get_center, stroke_color=color or get_theme().accent,
                          stroke_width=2, time_traced=1.5)

    def angle_arc(self, color=None) -> Mobject:
        c = color or get_theme().accent

        def make():
            pivot = self.tracker.to_scene(ORIGIN)
            r = 0.8 * self.tracker.scale()
            arc = Arc(start_angle=-PI / 2, angle=self.theta, radius=r, arc_center=pivot,
                      stroke_color=c, stroke_width=3)
            ref = DashedLine(pivot, pivot + DOWN * self.L * self.tracker.scale() * 0.6,
                             stroke_color=get_theme().muted, stroke_width=2)
            return VGroup(ref, arc)

        from manimlib import always_redraw
        return always_redraw(make)


class MassSpring(VGroup):
    """
    A block on a horizontal spring attached to a wall, moving in simple harmonic motion
    x(t) = A cos(ωt), ω = √(k/m). `oscillate(duration)` animates it; `ms.block`,
    `ms.spring`; `ms.position()` is the current displacement.

    Example: ms = MassSpring(k=8, mass=1, amplitude=1.2); self.show(ms, "main"); self.play(ms.oscillate(5))
    """

    def __init__(self, k: float = 10.0, mass: float = 1.0, amplitude: float = 1.0,
                 rest_length: float = 3.0, damping: float = 0.0, **kwargs):
        theme = get_theme()
        self.k, self.m, self.A, self.rest, self.damping = k, mass, amplitude, rest_length, damping
        self.t = 0.0
        self.tracker = ScaleTracker()
        self.wall = VGroup(Line(UP * 0.9, DOWN * 0.6, stroke_color=theme.muted, stroke_width=5))
        self.floor = Line(DOWN * 0.6, DOWN * 0.6 + RIGHT * (rest_length + amplitude + 1.6),
                          stroke_color=theme.muted, stroke_width=3)
        self.block = RoundedRectangle(width=0.9, height=0.9, corner_radius=0.16,
                                      fill_color=theme.primary, fill_opacity=1 if theme.name == "bubble" else 0.85,
                                      stroke_color=theme.primary, stroke_width=0 if theme.name == "bubble" else 1)
        self.block.move_to(self._block_design())
        self.spring = Spring(ORIGIN, self._block_design() + LEFT * 0.45, coils=12)
        self.equilibrium = DashedLine(RIGHT * rest_length + UP * 0.9 + RIGHT * 0.45,
                                      RIGHT * rest_length + DOWN * 0.6 + RIGHT * 0.45,
                                      stroke_color=theme.muted, stroke_width=2)
        super().__init__(self.wall, self.floor, self.equilibrium, self.spring, self.block,
                         *self.tracker.mobjects, **kwargs)

    @property
    def omega(self) -> float:
        return float(np.sqrt(self.k / self.m))

    def position(self, t=None) -> float:
        t = self.t if t is None else t
        return self.A * np.exp(-self.damping * t) * np.cos(self.omega * t)

    def _block_design(self, t=None):
        return RIGHT * (self.rest + 0.45 + self.position(t)) + DOWN * 0.15

    def oscillate(self, duration: float, **kwargs) -> Animation:
        t0 = self.t

        def update(_, alpha):
            self.t = t0 + alpha * duration
            center = self.tracker.to_scene(self._block_design())
            self.block.move_to(center)
            self.spring.put_between(self.tracker.to_scene(DOWN * 0.15),
                                    center + LEFT * self.block.get_width() / 2)

        kwargs.setdefault("run_time", duration)
        return UpdateFromAlphaFunc(self, update, rate_func=lambda t: t, **kwargs)


# ------------------------------------------------------------------ forces

class ForceArrow(VGroup):
    """
    A force vector drawn from `origin` with a label at its tip (e.g. "F_g", "N", "f").
    `vector` is in scene units (its length shows magnitude).

    Example: ForceArrow(box.get_bottom(), DOWN * 1.5, "mg", color=get_theme().negative)
    """

    def __init__(self, origin, vector, label: str = "", color=None, **kwargs):
        c = color or get_theme().accent
        o, v = _v3(origin), _v3(vector)
        self.arrow = Arrow(o, o + v, buff=0, thickness=4, fill_color=c)
        parts = [self.arrow]
        self.label = None
        if label:
            self.label = Label(label, size="small", color=c, bold=True)
            u = v / (np.linalg.norm(v) or 1)
            self.label.next_to(o + v, u, buff=0.12)
            parts.append(self.label)
        super().__init__(*parts, **kwargs)

    def grow(self) -> Animation:
        anims = [GrowArrow(self.arrow)]
        if self.label is not None:
            anims.append(FadeIn(self.label))
        return Succession(*anims)


class FreeBodyDiagram(VGroup):
    """
    A body (box by default, or any mobject) with labeled force arrows from its center.
    forces: {"label": vector} e.g. {"Weight": DOWN * 2, "Normal": UP * 2, "Push": RIGHT * 1.5}.
    `fbd.build()` grows the forces one by one; `fbd.forces[label]`; `fbd.net_force()`
    returns an animation adding the resultant arrow.

    Example: FreeBodyDiagram({"mg": DOWN * 2, "N": UP * 2, "F": RIGHT * 1.5, "f": LEFT * 0.8})
    """

    def __init__(self, forces: dict, body: Mobject | None = None, body_label: str = "m",
                 **kwargs):
        theme = get_theme()
        if body is None:
            body = VGroup(RoundedRectangle(width=1.2, height=1.2, corner_radius=.2,
                                 fill_color=theme.primary if theme.name == "bubble" else theme.surface,
                                 fill_opacity=1, stroke_color=theme.outline,
                                 stroke_width=0 if theme.name == "bubble" else 3),
                          Label(body_label, size="label"))
        self.body = body
        self.forces = {}
        c = body.get_center()
        for i, (label, vec) in enumerate(forces.items()):
            v = _v3(vec)
            u = v / (np.linalg.norm(v) or 1)
            start = body.get_boundary_point(u) if np.linalg.norm(v) > 0 else c
            self.forces[label] = ForceArrow(start, v, label, color=palette_color(i + 1))
        self._vectors = {k: _v3(v) for k, v in forces.items()}
        super().__init__(self.body, *self.forces.values(), **kwargs)

    def build(self, lag_ratio: float = 0.6, **kwargs) -> Animation:
        return Succession(FadeIn(self.body),
                          LaggedStart(*(f.grow() for f in self.forces.values()), lag_ratio=lag_ratio),
                          **kwargs)

    def net_force(self, label: str = "Net force") -> Animation:
        """Show the resultant force as a separate arrow below the diagram."""
        total = sum(self._vectors.values(), np.zeros(3))
        scale = self.body.get_width() / 1.2 if self.body.get_width() else 1
        anchor = np.array([self.body.get_center()[0], self.get_bottom()[1] - 0.6 * scale, 0])
        if np.linalg.norm(total) < 1e-6:
            tag = Label(f"{label} = 0", size="small", color=get_theme().positive).scale(scale)
            tag.move_to(anchor)
            self.add(tag)
            return FadeIn(tag)
        start = anchor - total * scale / 2
        arrow = ForceArrow(start, total * scale, "", color=get_theme().accent)
        tag = Label(label, size="small", color=get_theme().accent, bold=True).scale(scale)
        tag.next_to(arrow, DOWN, buff=0.12)
        self.add(arrow, tag)
        return Succession(arrow.grow(), FadeIn(tag))


# ------------------------------------------------------------------ kinematics and waves

class Projectile(VGroup):
    """
    Projectile motion from `origin` with launch speed v0 (units/s) and angle (radians),
    on flat ground at the origin's height. Draws the ground and (optionally) the dashed
    predicted path. `launch()` animates the ball with a trail over the real flight time;
    `velocity_arrows(t)` returns the velocity components at time t.

    Example: p = Projectile(v0=7, angle=50 * DEG); self.show(p, "main"); self.play(p.launch())
    """

    def __init__(self, v0: float = 7.0, angle: float = PI / 4, g: float = 9.8,
                 show_path: bool = True, **kwargs):
        theme = get_theme()
        self.v0, self.angle, self.g = v0, angle, g
        self.vx, self.vy = v0 * np.cos(angle), v0 * np.sin(angle)
        self.flight_time = 2 * self.vy / g
        self.range = self.vx * self.flight_time
        self.max_height = self.vy ** 2 / (2 * g)
        self.tracker = ScaleTracker()
        self.ground = Line(LEFT * 0.5, RIGHT * (self.range + 0.5), stroke_color=theme.muted,
                           stroke_width=3)
        self.ball = Dot(ORIGIN, radius=0.14, fill_color=theme.primary)
        self.path = VMobject(stroke_color=theme.muted, stroke_width=2)
        self.path.set_points_smoothly([self._pos(t) for t in np.linspace(0, self.flight_time, 40)])
        from manimlib import DashedVMobject
        self.dashed_path = DashedVMobject(self.path, num_dashes=40)
        parts = [self.ground, self.ball]
        if show_path:
            parts.insert(1, self.dashed_path)
        super().__init__(*parts, *self.tracker.mobjects, **kwargs)

    def _pos(self, t):
        return np.array([self.vx * t, self.vy * t - 0.5 * self.g * t * t, 0.0])

    def position(self, t: float) -> np.ndarray:
        """Scene point of the projectile at time t."""
        return self.tracker.to_scene(self._pos(t))

    def launch(self, run_time: float | None = None, trail: bool = True, **kwargs) -> Animation:
        theme = get_theme()
        T = self.flight_time
        if trail:
            trace = TracedPath(self.ball.get_center, stroke_color=theme.accent, stroke_width=3)
            self.add(trace)

        def update(ball, alpha):
            ball.move_to(self.position(alpha * T))

        return UpdateFromAlphaFunc(self.ball, update, run_time=run_time or T,
                                   rate_func=lambda t: t, **kwargs)

    def velocity_arrows(self, t: float, scale: float = 0.25) -> VGroup:
        theme = get_theme()
        p = self.position(t)
        s = scale * self.tracker.scale()
        vy = self.vy - self.g * t
        return VGroup(
            ForceArrow(p, RIGHT * self.vx * s, "vₓ", color=theme.primary),
            ForceArrow(p, UP * vy * s, "vᵧ", color=theme.secondary),
        )


class Wave(VGroup):
    """
    A traveling sine wave y = A sin(kx - ωt) drawn over [x_min, x_max].
    `propagate(duration)` animates it moving; `wave.curve`; standing=True makes a
    standing wave instead. Combine two with `Wave.superpose(w1, w2)` (returns a Wave-like
    curve showing their sum).

    Example: w = Wave(amplitude=1, wavelength=3, speed=2); self.show(w, "main"); self.play(w.propagate(4))
    """

    def __init__(self, amplitude: float = 1.0, wavelength: float = 3.0, speed: float = 2.0,
                 x_range=(-6, 6), standing: bool = False, color=None, show_axis: bool = True,
                 **kwargs):
        theme = get_theme()
        self.A, self.lam, self.v, self.standing = amplitude, wavelength, speed, standing
        self.x_range = x_range
        self.t = 0.0
        self.tracker = ScaleTracker()
        self.axis = Line(RIGHT * x_range[0], RIGHT * x_range[1], stroke_color=theme.muted,
                         stroke_width=2)
        self.curve = VMobject(stroke_color=color or theme.primary, stroke_width=4)
        self._redraw()
        parts = ([self.axis] if show_axis else []) + [self.curve]
        super().__init__(*parts, *self.tracker.mobjects, **kwargs)

    def y(self, x, t=None):
        t = self.t if t is None else t
        k, w = TAU / self.lam, TAU / self.lam * self.v
        if self.standing:
            return 2 * self.A * np.sin(k * x) * np.cos(w * t)
        return self.A * np.sin(k * x - w * t)

    def _redraw(self):
        xs = np.linspace(*self.x_range, 200)
        pts = [np.array([x, self.y(x), 0.0]) for x in xs]
        if hasattr(self, "submobjects") and self.submobjects:
            pts = [self.tracker.to_scene(p) for p in pts]
        self.curve.set_points_smoothly(pts)

    def propagate(self, duration: float, **kwargs) -> Animation:
        t0 = self.t

        def update(_, alpha):
            self.t = t0 + alpha * duration
            self._redraw()

        kwargs.setdefault("run_time", duration)
        return UpdateFromAlphaFunc(self, update, rate_func=lambda t: t, **kwargs)

    @staticmethod
    def superpose(*waves: "Wave", color=None) -> VMobject:
        """A live curve equal to the sum of the given waves (keep it on screen while they move)."""
        from manimlib import always_redraw
        ref = waves[0]

        def make():
            xs = np.linspace(*ref.x_range, 200)
            pts = [ref.tracker.to_scene(np.array([x, sum(w.y(x) for w in waves), 0.0])) for x in xs]
            curve = VMobject(stroke_color=color or get_theme().accent, stroke_width=4)
            curve.set_points_smoothly(pts)
            return curve

        return always_redraw(make)


# ------------------------------------------------------------------ optics and circuits

class LensDiagram(VGroup):
    """
    Ray diagram for a thin lens: principal axis, lens, focal points, an object arrow, the
    three principal rays, and the image (dashed if virtual). Uses 1/f = 1/d_o + 1/d_i.
    converging=False makes a diverging lens. `diagram.build()` animates object, rays,
    then image; `diagram.image_distance`, `diagram.magnification`.

    Example: LensDiagram(focal_length=2, object_distance=5, object_height=1.2)
    """

    def __init__(self, focal_length: float = 2.0, object_distance: float = 5.0,
                 object_height: float = 1.2, converging: bool = True, half_width: float = 6.5,
                 **kwargs):
        theme = get_theme()
        f = focal_length if converging else -abs(focal_length)
        do, ho = object_distance, object_height
        di = 1 / (1 / f - 1 / do) if abs(1 / f - 1 / do) > 1e-9 else float("inf")
        self.image_distance, self.magnification = di, -di / do
        hi = self.magnification * ho
        self.axis = Line(LEFT * half_width, RIGHT * half_width, stroke_color=theme.muted, stroke_width=2)
        lens_h = max(abs(ho), abs(hi) if np.isfinite(hi) else 0, 1.5) * 1.35
        self.lens = VGroup(Line(DOWN * lens_h, UP * lens_h, stroke_color=theme.primary, stroke_width=4))
        tip = 1 if converging else -1
        for end in (UP * lens_h, DOWN * lens_h):
            d = 1 if end[1] > 0 else -1
            self.lens.add(Line(end, end + np.array([-0.2, -0.25 * d * tip, 0]), stroke_color=theme.primary, stroke_width=4),
                          Line(end, end + np.array([0.2, -0.25 * d * tip, 0]), stroke_color=theme.primary, stroke_width=4))
        self.focal_points = VGroup()
        for x in (-abs(f), abs(f)):
            self.focal_points.add(Dot(RIGHT * x, fill_color=theme.secondary),
                                  Label("F", size="small", color=theme.secondary).next_to(RIGHT * x, DOWN, buff=0.15))
        obj_base = LEFT * do
        self.object = Arrow(obj_base, obj_base + UP * ho, buff=0, thickness=4, fill_color=theme.positive)
        top = obj_base + UP * ho
        rays = VGroup()
        ray_style = dict(stroke_color=theme.accent, stroke_width=2.5)
        far = half_width
        virtual = VGroup()
        if np.isfinite(di):
            img_top = RIGHT * di + UP * hi
            # 1: parallel, then through (or away from) the far focal point
            hit = np.array([0, ho, 0])
            rays.add(Line(top, hit, **ray_style))
            out_dir = (img_top - hit) if di > 0 else (hit - img_top)
            out_dir = out_dir / np.linalg.norm(out_dir)
            rays.add(Line(hit, hit + out_dir * far, **ray_style))
            # 2: through the center, undeviated
            d2 = -top / np.linalg.norm(top)
            rays.add(Line(top, top + d2 * (np.linalg.norm(top) + far), **ray_style))
            # 3: toward the near focal point, then parallel
            hit3 = np.array([0, hi, 0])
            rays.add(Line(top, hit3, **ray_style), Line(hit3, hit3 + RIGHT * far, **ray_style))
            if di < 0:  # Virtual image: extend rays backwards, dashed
                for start in (hit, hit3):
                    virtual.add(DashedLine(start, img_top, stroke_color=theme.muted, stroke_width=2))
            image_color = theme.negative
            self.image = Arrow(RIGHT * di, img_top, buff=0, thickness=4, fill_color=image_color)
            if di < 0:
                self.image.set_fill(opacity=0.5)
        else:
            self.image = VGroup()
        self.rays, self.virtual_rays = rays, virtual
        super().__init__(self.axis, self.lens, self.focal_points, self.object, self.rays,
                         self.virtual_rays, self.image, **kwargs)

    def build(self, **kwargs) -> Animation:
        return Succession(
            AnimationGroup(ShowCreation(self.axis), FadeIn(self.lens), FadeIn(self.focal_points)),
            GrowArrow(self.object),
            LaggedStart(*(ShowCreation(r) for r in self.rays), lag_ratio=0.3, run_time=2.5),
            AnimationGroup(ShowCreation(self.virtual_rays), FadeIn(self.image)),
            **kwargs,
        )


class SimpleCircuit(VGroup):
    """
    A series circuit drawn as a rectangle loop with schematic symbols placed along it.
    components: list of "battery", "resistor", "bulb", "switch", "capacitor" (or
    (kind, label) pairs, e.g. ("resistor", "R₁")). `circuit.flow(duration)` animates
    charges moving around the loop (conventional current, + to -); `circuit.components`.

    Example: c = SimpleCircuit(["battery", ("resistor", "10 Ω"), "bulb"]); self.play(c.flow(4))
    """

    def __init__(self, components, width: float = 7.0, height: float = 4.0, **kwargs):
        theme = get_theme()
        self.w, self.h = width, height
        corners = [np.array(p) for p in [(-width / 2, -height / 2, 0), (-width / 2, height / 2, 0),
                                          (width / 2, height / 2, 0), (width / 2, -height / 2, 0)]]
        self.corners = corners
        perimeter_pts = corners + [corners[0]]
        comps = [c if isinstance(c, tuple) else (c, None) for c in components]
        # Spread components over the left, top and right sides
        slots = []
        sides = [(corners[0], corners[1]), (corners[1], corners[2]), (corners[2], corners[3])]
        per_side = int(np.ceil(len(comps) / 3)) or 1
        for i, _ in enumerate(comps):
            a, b = sides[min(i // per_side, 2)]
            k = i % per_side
            slots.append((a + (b - a) * (k + 1) / (per_side + 1), (b - a) / np.linalg.norm(b - a)))
        self.components, gaps = [], []
        for (kind, label), (center, u) in zip(comps, slots):
            sym = self._symbol(kind)
            if abs(u[1]) > 0.5:
                sym.rotate(PI / 2)
            sym.move_to(center)
            if label:
                tag = Label(label, size="small", color=theme.muted)
                normal = np.array([-u[1], u[0], 0])
                tag.next_to(sym, -normal if abs(u[1]) > 0.5 else normal, buff=0.2)
                sym = VGroup(sym, tag)
            self.components.append(sym)
            half = 0.45
            gaps.append((center - u * half, center + u * half))
        # Wires: the loop minus the component gaps
        self.wires = VGroup()
        loop = perimeter_pts
        for a, b in zip(loop, loop[1:]):
            cuts = sorted([g for g in gaps if _on_segment(g[0], a, b)],
                          key=lambda g: np.linalg.norm(g[0] - a))
            start = a
            for g0, g1 in cuts:
                self.wires.add(Line(start, g0, stroke_color=theme.text, stroke_width=3))
                start = g1
            self.wires.add(Line(start, b, stroke_color=theme.text, stroke_width=3))
        self.tracker = ScaleTracker()
        self._loop = loop
        super().__init__(self.wires, *self.components, *self.tracker.mobjects, **kwargs)

    def _symbol(self, kind: str) -> VGroup:
        theme = get_theme()
        s = dict(stroke_color=theme.text, stroke_width=3)
        if kind == "battery":
            return VGroup(Line(UP * 0.4 + LEFT * 0.08, DOWN * 0.4 + LEFT * 0.08, stroke_color=theme.text, stroke_width=4),
                          Line(UP * 0.2 + RIGHT * 0.08, DOWN * 0.2 + RIGHT * 0.08, stroke_color=theme.text, stroke_width=7),
                          Line(LEFT * 0.45, LEFT * 0.08, **s), Line(RIGHT * 0.08, RIGHT * 0.45, **s),
                          Label("+", size="tiny", color=theme.positive).move_to(UP * 0.5 + LEFT * 0.25),
                          Label("−", size="tiny", color=theme.negative).move_to(UP * 0.5 + RIGHT * 0.25))
        if kind == "resistor":
            zz = VMobject(**s)
            pts = [LEFT * 0.45] + [LEFT * 0.3 + RIGHT * 0.1 * i + UP * (0.15 if i % 2 else -0.15)
                                   for i in range(1, 6)] + [RIGHT * 0.3, RIGHT * 0.45]
            zz.set_points_as_corners(pts)
            return VGroup(zz)
        if kind == "bulb":
            glass = Circle(radius=0.32, stroke_color=theme.secondary, stroke_width=3,
                           fill_color=theme.secondary, fill_opacity=0.15)
            cross = VGroup(Line(UL * 0.22, DR * 0.22, **s), Line(UR * 0.22, DL * 0.22, **s))
            return VGroup(Line(LEFT * 0.45, LEFT * 0.32, **s), glass, cross,
                          Line(RIGHT * 0.32, RIGHT * 0.45, **s))
        if kind == "capacitor":
            return VGroup(Line(LEFT * 0.45, LEFT * 0.08, **s), Line(RIGHT * 0.08, RIGHT * 0.45, **s),
                          Line(UP * 0.35 + LEFT * 0.08, DOWN * 0.35 + LEFT * 0.08, **s),
                          Line(UP * 0.35 + RIGHT * 0.08, DOWN * 0.35 + RIGHT * 0.08, **s))
        if kind == "switch":
            return VGroup(Dot(LEFT * 0.3, fill_color=theme.text), Dot(RIGHT * 0.3, fill_color=theme.text),
                          Line(LEFT * 0.3, RIGHT * 0.25 + UP * 0.3, **s),
                          Line(LEFT * 0.45, LEFT * 0.3, **s), Line(RIGHT * 0.3, RIGHT * 0.45, **s))
        raise ValueError(f"Unknown component {kind!r}: use battery, resistor, bulb, capacitor, switch")

    def flow(self, duration: float = 4.0, n_charges: int = 14, speed: float = 1.0, **kwargs) -> Animation:
        theme = get_theme()
        loop = [self.tracker.to_scene(p) for p in self._loop]
        lengths = [np.linalg.norm(b - a) for a, b in zip(loop, loop[1:])]
        total = sum(lengths)

        def point_at(d):
            d %= total
            for (a, b), L in zip(zip(loop, loop[1:]), lengths):
                if d <= L:
                    return a + (b - a) * d / L
                d -= L
            return loop[-1]

        charges = VGroup(*(Dot(radius=0.07, fill_color=theme.accent) for _ in range(n_charges)))
        self.add(charges)

        def update(group, alpha):
            for i, dot in enumerate(group):
                dot.move_to(point_at(i * total / n_charges + alpha * duration * speed * total / 6))

        kwargs.setdefault("run_time", duration)
        update(charges, 0)
        return Succession(FadeIn(charges, run_time=0.3),
                          UpdateFromAlphaFunc(charges, update, rate_func=lambda t: t, **kwargs))


def _on_segment(p, a, b, tol=1e-6):
    ab, ap = b - a, p - a
    cross = np.linalg.norm(np.cross(ab, ap))
    return cross < tol * max(np.linalg.norm(ab), 1) and -tol <= np.dot(ap, ab) <= np.dot(ab, ab) + tol


class FieldLines(VGroup):
    """
    Electric field of point charges: charge markers (+/−) and field lines traced from the
    positive charges. charges: [((x, y), q), ...] in scene units.
    `field.build()` draws the lines outward.

    Example: FieldLines([((-2, 0), 1), ((2, 0), -1)])   # a dipole
    """

    def __init__(self, charges, lines_per_charge: int = 12, bounds=(6.5, 3.5), **kwargs):
        theme = get_theme()
        self.charges = [(_v3(p), q) for p, q in charges]
        self.lines = VGroup()
        has_positive = any(q > 0 for _, q in self.charges)
        for p, q in self.charges:
            sign = 1 if q > 0 else -1
            for a in np.linspace(0, TAU, lines_per_charge, endpoint=False):
                pts = self._trace(p + 0.25 * np.array([np.cos(a), np.sin(a), 0]), sign, bounds)
                # Lines from negative charges are traced backwards; keep only those that come
                # in from infinity (the rest duplicate lines already drawn from + charges)
                if sign < 0 and has_positive and self._ends_at_charge(pts[-1]):
                    continue
                if len(pts) > 3:
                    line = VMobject(stroke_color=theme.primary, stroke_width=2, stroke_opacity=0.8)
                    line.set_points_smoothly(pts[::3] + [pts[-1]])
                    self.lines.add(line)
        self.markers = VGroup()
        for p, q in self.charges:
            c = theme.negative if q > 0 else theme.primary
            self.markers.add(VGroup(Circle(radius=0.25, fill_color=c, fill_opacity=0.9, stroke_width=0),
                                    Label("+" if q > 0 else "−", size="label", bold=True)).move_to(p))
        super().__init__(self.lines, self.markers, **kwargs)

    def _ends_at_charge(self, x) -> bool:
        return any(np.linalg.norm(x - p) < 0.3 for p, _ in self.charges)

    def _field(self, x):
        e = np.zeros(3)
        for p, q in self.charges:
            r = x - p
            d = np.linalg.norm(r)
            e += q * r / max(d, 0.05) ** 3
        return e

    def _trace(self, start, sign, bounds, step=0.04, max_steps=600):
        pts, x = [start], start.copy()
        for _ in range(max_steps):
            e = self._field(x)
            n = np.linalg.norm(e)
            if n < 1e-9:
                break
            x = x + sign * step * e / n
            pts.append(x.copy())
            if abs(x[0]) > bounds[0] or abs(x[1]) > bounds[1]:
                break
            if any(np.linalg.norm(x - p) < 0.22 for p, q in self.charges if q * sign < 0):
                break
        return pts

    def build(self, **kwargs) -> Animation:
        return Succession(FadeIn(self.markers, scale=0.5),
                          LaggedStart(*(ShowCreation(l) for l in self.lines), lag_ratio=0.03,
                                      run_time=2.5), **kwargs)
