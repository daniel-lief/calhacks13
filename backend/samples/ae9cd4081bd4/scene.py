from animai import *

TITLE = "Supply and Demand"
THEME = "paper"


class Explainer(AnimaiScene):
    def construct(self):
        random.seed(0)
        np.random.seed(0)
        theme = get_theme()

        def make_axes():
            axes = Axes(x_range=(0, 10, 1), y_range=(0, 10, 1), width=7, height=4.6,
                        axis_config={"color": theme.text})
            xl = Label("Quantity of coffee", size="small").next_to(axes.c2p(5, 0), DOWN, buff=0.35)
            yl = Label("Price", size="small").next_to(axes.c2p(0, 10), UP, buff=0.15)
            return axes, xl, yl

        def span_marker(p1, p2, color, vertical_dir):
            # Dimension marker built from plain lines (no LaTeX needed)
            line = Line(p1, p2, color=color, stroke_width=4)
            t1 = Line(p1 + vertical_dir * 0.12, p1 - vertical_dir * 0.12, color=color, stroke_width=4)
            t2 = Line(p2 + vertical_dir * 0.12, p2 - vertical_dir * 0.12, color=color, stroke_width=4)
            return VGroup(line, t1, t2)

        # Beat 1: hook
        with self.voiceover("Why does a cup of coffee cost three dollars, and not thirty cents or three hundred dollars? Nobody in charge picks that number. So where does it come from?") as vo:
            self.title_card("Supply and Demand", "Who decides the price?")
        self.fade_out_all()

        # Beat 2: demand
        axes, xl, yl = make_axes()
        demand = axes.get_graph(lambda x: 9 - 0.8 * x, x_range=(0.5, 10), color=theme.primary)
        dlab = Label("Demand", size="small", color=theme.primary).next_to(axes.c2p(9.5, 1.4), UP)
        grp = VGroup(axes, xl, yl)
        with self.voiceover("Start with buyers. The lower the price, the more cups people want. That downward sloping blue line is demand.") as vo:
            self.set_title("Demand: buyers")
            self.show(grp, "main", animation=FadeIn)
            self.play(ShowCreation(demand), run_time=min(2.5, vo.duration))
            self.play(FadeIn(dlab))

        # Beat 3: supply
        supply = axes.get_graph(lambda x: 1 + 0.8 * x, x_range=(0.5, 10), color=theme.secondary)
        slab = Label("Supply", size="small", color=theme.secondary).next_to(axes.c2p(9.5, 8.6), DOWN)
        with self.voiceover("Now sellers. The higher the price, the more coffee they are happy to produce. That upward sloping red line is supply.") as vo:
            self.set_title("Supply: sellers")
            self.play(ShowCreation(supply), run_time=min(2.5, vo.duration))
            self.play(FadeIn(slab))

        # Beat 4: equilibrium
        eq = axes.c2p(5, 5)
        dot = Dot(eq, fill_color=theme.accent, radius=0.12)
        hl = DashedLine(axes.c2p(0, 5), eq, color=theme.accent)
        vl = DashedLine(axes.c2p(5, 0), eq, color=theme.accent)
        elab = Label("Equilibrium", size="small", color=theme.accent).next_to(dot, UR, buff=0.2)
        elab.set_backstroke(theme.background, 5)
        with self.voiceover("Where the lines cross, buyers want exactly as much as sellers offer. That price is the equilibrium, and the market naturally settles there.") as vo:
            self.set_title("Equilibrium")
            self.play(ShowCreation(hl), ShowCreation(vl), run_time=1.2)
            self.play(GrowFromCenter(dot), FadeIn(elab))
            self.play(Flash(dot, color=theme.accent))

        # Beat 5: surplus
        p_hi = 7.5
        qd, qs = (9 - p_hi) / 0.8, (p_hi - 1) / 0.8
        a = axes.c2p(qd, p_hi)
        b = axes.c2p(qs, p_hi)
        pline = DashedLine(axes.c2p(0, p_hi), axes.c2p(qs, p_hi), color=theme.negative)
        br = span_marker(a + UP * 0.25, b + UP * 0.25, theme.negative, UP)
        sur = Label("Surplus", size="small", color=theme.negative).next_to(br, UP, buff=0.08)
        sur.set_backstroke(theme.background, 5)
        with self.voiceover("Set the price too high, and sellers have unsold coffee piling up. A surplus. To clear the shelves, they cut prices.") as vo:
            self.set_title("Price too high: surplus")
            self.play(FadeOut(VGroup(hl, vl, elab)), run_time=0.6)
            self.play(ShowCreation(pline), run_time=1)
            self.play(ShowCreation(br), FadeIn(sur))
            self.wait(max(0.3, vo.get_remaining_duration() - 0.2))

        # Beat 6: shortage
        p_lo = 2.5
        qd2, qs2 = (9 - p_lo) / 0.8, (p_lo - 1) / 0.8
        a2 = axes.c2p(qs2, p_lo)
        b2 = axes.c2p(qd2, p_lo)
        pl2 = DashedLine(axes.c2p(0, p_lo), axes.c2p(qd2, p_lo), color=theme.positive)
        br2 = span_marker(a2 + DOWN * 0.25, b2 + DOWN * 0.25, theme.positive, UP)
        sh = Label("Shortage", size="small", color=theme.positive).next_to(br2, DOWN, buff=0.08)
        sh.set_backstroke(theme.background, 5)
        with self.voiceover("Set it too low, and the shop runs out while buyers still queue. A shortage. Sellers notice, and prices creep up.") as vo:
            self.set_title("Price too low: shortage")
            self.play(FadeOut(VGroup(pline, br, sur)), run_time=0.6)
            self.play(ShowCreation(pl2), run_time=1)
            self.play(ShowCreation(br2), FadeIn(sh))
            self.wait(max(0.3, vo.get_remaining_duration() - 0.2))
        self.fade_out_all()

        # Beat 7: demand shift
        axes, xl, yl = make_axes()
        grp = VGroup(axes, xl, yl)
        d1 = axes.get_graph(lambda x: 9 - 0.8 * x, x_range=(0.5, 10), color=theme.primary)
        d2 = axes.get_graph(lambda x: 12 - 0.8 * x, x_range=(3.2, 10), color=theme.primary)
        s1 = axes.get_graph(lambda x: 1 + 0.8 * x, x_range=(0.5, 10), color=theme.secondary)
        e1 = Dot(axes.c2p(5, 5), fill_color=theme.accent)
        with self.voiceover("Now a cold snap hits and everyone wants hot coffee. Demand shifts right. Along the supply line, both the price and the quantity rise to a new equilibrium.") as vo:
            self.set_title("When demand rises")
            self.show(VGroup(grp, d1, s1, e1), "main", animation=FadeIn)
            self.wait(0.5)
            self.play(Transform(d1, d2), e1.animate.move_to(axes.c2p(6.9, 6.5)),
                      run_time=min(3, max(1.5, vo.get_remaining_duration() - 0.5)))

        # Beat 8: supply shift
        with self.voiceover("If instead a frost destroys coffee crops, supply shifts left. Now there is less coffee around, and the price climbs. Shifts in either curve move the market.") as vo:
            self.set_title("When supply falls")
            s2 = axes.get_graph(lambda x: 4 + 0.8 * x, x_range=(0.5, 6), color=theme.secondary)
            self.play(Transform(s1, s2), e1.animate.move_to(axes.c2p(5, 8)),
                      run_time=min(3, max(1.5, vo.duration - 1)))

        self.fade_out_all()

        # Beat 9: recap
        recap = BulletList("Demand: price down, buyers up", "Supply: price up, sellers up",
                           "Crossing point sets the price", size="body")
        with self.voiceover("So the price of coffee is not decided by anyone. Buyers pull it down, sellers push it up, and the price settles where they agree.") as vo:
            self.set_title("Recap")
            self.show(recap, "main", animation=recap.reveal(), run_time=min(3, vo.duration))

        with self.voiceover("The aha: a price is a signal, created by millions of people each chasing their own interests.") as vo:
            self.set_title("The big idea")
            card = Card(Label("Price = where wants meet supplies", size="body", color=theme.accent), title="The aha")
            self.show(card, "main", animation=FadeIn)
