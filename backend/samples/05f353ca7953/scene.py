from animai import *

TITLE = "How a Pendulum Keeps Time"
THEME = "blueprint"


class Explainer(AnimaiScene):
    def construct(self):
        random.seed(0)
        np.random.seed(0)
        theme = get_theme()

        # Beat 1: hook
        with self.voiceover("For hundreds of years, the best clocks in the world were just a weight swinging back and forth. Why does a swinging weight make such a good timekeeper?") as vo:
            self.title_card("How a Pendulum Keeps Time", "Why a swinging weight beats the clock")
        self.fade_out_all()

        # Beat 2: Galileo
        with self.voiceover("The story goes that around fifteen eighty-three, a young Galileo watched a lamp swing in a cathedral, and timed it with his pulse. Big swings and small swings seemed to take the same time.") as vo:
            self.set_title("Galileo's observation")
            p = Pendulum(length=3, angle=30 * DEG)
            self.show(p, "main", animation=FadeIn, run_time=1)
            self.play(p.swing(max(vo.get_remaining_duration() - 0.5, 1)))

        # Beat 3: period formula (no LaTeX needed)
        with self.voiceover("The time for one full swing is called the period. For small swings it depends only on the length L and gravity g: T equals two pi times the square root of L over g.") as vo:
            self.set_title("The period")
            formula = Label("T = 2π √(L / g)", size="title", color=theme.accent)
            legend = VGroup(
                Label("T: period", size="body", color=theme.accent),
                Label("L: length", size="body", color=theme.primary),
                Label("g: gravity", size="body", color=theme.secondary),
            ).arrange(RIGHT, buff=0.8)
            eq = VGroup(formula, legend).arrange(DOWN, buff=0.8)
            self.show(eq, "main", animation=FadeIn, run_time=min(2.5, vo.duration))
        self.wait(0.5)

        # Beat 4: amplitude does not matter
        with self.voiceover("Notice what is missing: the size of the swing. Start it at ten degrees or twenty, and the period is almost the same. That is why it keeps steady time even as it slowly dies down.") as vo:
            self.set_title("Swing size barely matters")
            angles = np.linspace(2, 40, 10)
            periods = []
            base = 2 * math.pi * math.sqrt(3 / 9.8)
            for a in angles:
                th = a * DEG
                # exact period via the arithmetic-geometric mean
                k = math.sin(th / 2)
                x, y = 1.0, math.sqrt(1 - k * k)
                for _ in range(20):
                    x, y = (x + y) / 2, math.sqrt(x * y)
                periods.append(base / x)
            plot = LinePlot([int(a) for a in angles], {"Period (s)": [float(v) for v in periods]},
                            x_label="Starting angle (degrees)", y_label="Period (s)",
                            y_range=(0, 4), legend=False)
            self.show(plot, "main", animation=plot.draw(), run_time=min(2.5, vo.duration))

        # Beat 5: length controls it
        with self.voiceover("What does matter is length. Quadruple the length and the period doubles. So a clockmaker can tune a clock simply by moving the bob up or down.") as vo:
            self.set_title("Length sets the beat")
            short = Pendulum(length=1.5, angle=25 * DEG, color=theme.primary)
            long = Pendulum(length=3, angle=25 * DEG, color=theme.secondary)
            self.show(short, "left", animation=FadeIn)
            self.show(long, "right", animation=FadeIn)
            self.play(AnimationGroup(short.swing(max(vo.get_remaining_duration() - 0.5, 1)),
                                     long.swing(max(vo.get_remaining_duration() - 0.5, 1))))
        self.fade_out_all()

        # Beat 6: problem - friction
        with self.voiceover("But a real pendulum loses energy to air and friction, and each swing gets smaller. Left alone, it would eventually stop.") as vo:
            self.set_title("The catch: friction")
            d = Pendulum(length=3, angle=35 * DEG, damping=0.25)
            self.show(d, "main", animation=FadeIn)
            self.play(d.swing(max(vo.get_remaining_duration() - 0.5, 1)))
        self.fade_out_all()

        # Beat 7: escapement flowchart
        with self.voiceover("The fix is the escapement. A falling weight or a spring pushes the gears, and the escapement lets them advance one tooth per swing, giving the pendulum a tiny push each time.") as vo:
            self.set_title("The escapement")
            fc = Flowchart({"w": "Falling weight", "g": "Gear train", "e": "Escapement", "p": "Pendulum"},
                           [("w", "g"), ("g", "e"), ("e", "p", "tiny push")],
                           colors={"w": theme.accent, "p": theme.primary})
            self.show(fc, "main", animation=fc.build(), run_time=min(3, vo.duration))
        self.fade_out_all()

        # Beat 8: the tick
        with self.voiceover("Each tick you hear is a gear tooth being caught and released. The pendulum sets the rhythm, and the weight supplies the energy. The gears simply count the swings.") as vo:
            self.set_title("Counting swings")
            clock = VGroup(Circle(radius=1.5, color=theme.primary),
                           Line(ORIGIN, UP * 1.1, color=theme.accent))
            self.show(clock, "left", animation=FadeIn)
            pend = Pendulum(length=2.5, angle=25 * DEG, color=theme.primary)
            self.show(pend, "right", animation=FadeIn)
            hand = clock[1]
            dur = max(vo.get_remaining_duration() - 0.5, 1)
            self.play(AnimationGroup(
                Rotate(hand, -TAU / 3, about_point=clock[0].get_center(),
                       run_time=dur, rate_func=linear),
                pend.swing(dur)))

        # Beat 9: recap
        with self.voiceover("So a pendulum keeps time because its swing depends on length, not on size. Add a little push to beat friction, and a swinging weight becomes a clock.") as vo:
            self.fade_out_all()
            self.set_title("Recap")
            card = Card(Label("Period depends on length, not swing size", size="body", color=theme.accent),
                        title="The aha")
            self.show(card, "main", animation=FadeIn)
        self.wait(1)
