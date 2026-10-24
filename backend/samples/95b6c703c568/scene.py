from animai import *

TITLE = "The Silk Road"
THEME = "paper"


class Explainer(AnimaiScene):
    def construct(self):
        random.seed(0)
        np.random.seed(0)
        theme = get_theme()

        box = (-10, 125, 15, 55)
        pts = [(34.3, 108.9), (39.5, 76.0), (39.65, 66.97),
               (33.3, 44.4), (41.0, 29.0), (41.9, 12.5)]
        names = ["Chang'an", "Kashgar", "Samarkand", "Baghdad",
                 "Constantinople", "Rome"]

        with self.voiceover("How did a fabric woven in China end up in the wardrobes of Roman senators, six thousand kilometers away?") as vo:
            self.title_card("The Silk Road", "How a trail of trade connected the world")
        self.fade_out_all()

        with self.voiceover("Starting around one hundred thirty BC, under the Han dynasty, traders began linking China to the Mediterranean. It was never one road, but a web of routes across deserts and mountains.") as vo:
            self.set_title("A web of routes")
            m = WorldMap(box)
            self.show(m, "main", animation=FadeIn, run_time=min(2, vo.duration))
            r = m.route(pts, theme.primary)
            self.play(ShowCreation(r), run_time=max(vo.get_remaining_duration() - 1, 0.5))
        self.fade_out_all()

        with self.voiceover("Here is the main route, from Chang'an in China, through Central Asia and Persia, to the ports of the Mediterranean.") as vo:
            self.set_title("Chang'an to Rome")
            m = WorldMap(box)
            self.show(m, "main")
            r = m.route(pts, theme.primary)
            self.play(ShowCreation(r), run_time=min(3, max(vo.duration * 0.5, 0.5)))
            dots = VGroup(*[Dot(m.point(p[0], p[1]), radius=0.07, color=theme.accent) for p in pts])
            # stagger label positions to avoid overlaps
            dirs = [UP, UP, DOWN, DOWN, DOWN, UP]
            labels = VGroup()
            for p, n, d in zip(pts, names, dirs):
                lb = Label(n, size="tiny", color=theme.accent, bold=True)
                lb.set_backstroke(theme.background, 5)
                lb.next_to(m.point(p[0], p[1]), d, buff=0.12)
                labels.add(lb)
            labels[4].shift(RIGHT * 0.5)
            labels[5].shift(LEFT * 0.4)
            labels[1].shift(UP * 0.1)
            self.play(FadeIn(dots), FadeIn(labels), run_time=max(vo.get_remaining_duration(), 0.5))
        self.fade_out_all()

        with self.voiceover("Almost nobody traveled the whole way. Goods passed hand to hand, through merchant after merchant, and each one took a cut.") as vo:
            self.set_title("Hand to hand")
            nodes = {"a": "Chinese merchants", "b": "Central Asian traders",
                     "c": "Persian merchants", "d": "Roman buyers"}
            fc = Flowchart(nodes, [("a", "b", "silk"), ("b", "c"), ("c", "d")])
            self.show(fc, "main", animation=fc.build(), run_time=min(3, vo.duration))
        self.fade_out_all()

        with self.voiceover("Silk was the star, but spices, paper, glass, horses and precious metals moved too.") as vo:
            self.set_title("What traveled")
            east = VGroup(IconLabel("coins", "Silk"),
                          IconLabel("wheat", "Spices"),
                          IconLabel("lightbulb", "Paper")).arrange(RIGHT, buff=0.8)
            card = Card(east, title="East to West")
            west = Card(Label("Glass, horses, gold, silver", size="body"), title="West to East")
            g = VGroup(card, west).arrange(DOWN, buff=0.5)
            self.show(g, "main", animation=FadeIn, run_time=min(2, vo.duration))
        self.fade_out_all()

        with self.voiceover("Ideas rode along with the caravans. Buddhism spread from India into China, paper and printing moved west, and so did gunpowder and the compass.") as vo:
            self.set_title("Ideas on the move")
            h = Hierarchy({"Silk Road": {"Religion": ["Buddhism", "Islam"],
                                         "Technology": ["Paper", "Gunpowder"],
                                         "Goods": ["Silk", "Spices"]}})
            self.show(h, "main", animation=h.build(), run_time=min(3, vo.duration))
        self.fade_out_all()

        with self.voiceover("Trade also carried danger. In the thirteen forties, the Black Death likely spread along these same routes and reached Europe in thirteen forty-seven.") as vo:
            self.set_title("A deadly side effect")
            tl = Timeline(1200, 1400, tick_step=50)
            tl.add_event(1271, "Marco Polo departs")
            tl.add_event(1347, "Plague reaches Europe")
            tl.add_era(1206, 1368, "Mongol Empire", theme.secondary)
            self.show(tl, "main", animation=tl.build(), run_time=min(3, vo.duration))
        self.fade_out_all()

        with self.voiceover("The routes faded after the fourteen hundreds, as Ottoman control grew and ships opened sea routes around Africa and across the oceans.") as vo:
            self.set_title("The decline")
            tl = Timeline(1300, 1600, tick_step=50)
            tl.add_event(1453, "Fall of Constantinople")
            tl.add_event(1498, "da Gama reaches India")
            tl.add_era(1453, 1600, "Ottoman control and sea routes", theme.secondary)
            self.show(tl, "main", animation=tl.build(), run_time=min(3, vo.duration))
        self.fade_out_all()

        with self.voiceover("So that Roman silk? It passed through dozens of hands over thousands of kilometers. The Silk Road was a chain of exchange, and it connected the world long before the modern age.") as vo:
            self.set_title("Recap")
            b = BulletList("A web of routes, not one road",
                           "Goods, ideas, and disease",
                           "Connected East and West", size="body")
            self.show(b, "main", animation=b.reveal(), run_time=min(2.5, vo.duration))
            c = Card(Label("Trade connects the world", size="body", color=theme.accent))
            self.show(c, "bottom", animation=FadeIn)
            b.shift(UP * 0.6)
            c.to_edge(DOWN, buff=1.0)
