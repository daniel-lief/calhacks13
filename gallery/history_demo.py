from animai import *

THEME = "paper"


class HistoryDemo(AnimaiScene):
    def construct(self):
        theme = get_theme()
        self.set_title("The Silk Road")
        world = WorldMap("world")
        self.show(world, "main", animation=world.build())
        route = world.route(["Beijing", "Tehran", "Istanbul", "Rome"], color=theme.secondary)
        stops = VGroup(*(world.city(c) for c in ["Beijing", "Tehran", "Istanbul", "Rome"]))
        self.play(LaggedStart(*(FadeIn(s) for s in stops), lag_ratio=0.3))
        self.play(ShowCreation(route), run_time=2)
        self.play(world.travel(route, run_time=2))
        self.play(world.highlight(["China", "Iran", "Turkey", "Italy"], theme.primary, 0.5))

        self.fade_out_all()
        self.set_title("Europe, 1914")
        europe = WorldMap("europe")
        self.show(europe, "main")
        self.play(europe.highlight(["Germany", "Austria", "Hungary"], theme.secondary),
                  europe.highlight(["France", "United Kingdom", "Russia"], theme.primary))
        self.play(FadeIn(europe.label_country("Germany")), FadeIn(europe.label_country("France")))
        rome = europe.territory([(44, 7), (46, 13), (41, 19), (38, 16), (40, 9)], label="Example region")
        self.play(FadeIn(rome))
        self.play(europe.zoom_to(["Italy"]))

        self.fade_out_all()
        self.set_title("A century of change")
        tl = Timeline(1900, 2000)
        for year, label in [(1914, "WWI begins"), (1929, "Great Depression"), (1939, "WWII begins"),
                            (1945, "UN founded"), (1969, "Moon landing"), (1989, "Berlin Wall falls")]:
            tl.add_event(year, label)
        tl.add_era(1914, 1918, "WWI", theme.negative)
        tl.add_era(1939, 1945, "WWII", theme.negative)
        tl.add_era(1947, 1991, "Cold War", theme.primary)
        self.show(tl, "main", animation=tl.build())
        cur = tl.cursor(1900)
        self.play(FadeIn(cur))
        self.play(tl.move_cursor(cur, 1969), run_time=2)
        self.wait()
