from animai import *

TITLE = "Dijkstra's Shortest Path"
THEME = "classic"


class Explainer(AnimaiScene):
    def construct(self):
        random.seed(0)
        np.random.seed(0)
        theme = get_theme()

        edges = [("A", "B", 4), ("A", "C", 2), ("C", "B", 1), ("B", "D", 5),
                 ("C", "D", 8), ("D", "E", 3), ("C", "E", 10)]
        layout = {"A": (-4, 0), "B": (-1, 1.6), "C": (-1, -1.6),
                  "D": (2, 1.0), "E": (4, -1.2)}

        with self.voiceover("You open your map app and ask for the fastest route home. Out of millions of possible roads, how does it find the best one in a blink?") as vo:
            self.title_card("Dijkstra's Shortest Path", "How maps find the fastest route")
        self.fade_out_all()

        with self.voiceover("Picture a network. Each circle is a place, and each number on a line is the cost of travelling that road, like minutes of driving.") as vo:
            self.set_title("A weighted graph")
            g = GraphViz(edges, weighted=True, layout=layout)
            self.show(g, "main", animation=FadeIn(g), run_time=min(2.0, vo.duration))

        with self.voiceover("Our goal is to find the cheapest path from A to every other place. The obvious idea is to try every path, but that explodes quickly as maps grow.") as vo:
            s = Badge("Start: A", color=theme.primary)
            t = Badge("Goal: E", color=theme.accent)
            tags = VGroup(s, t).arrange(DOWN, buff=0.4)
            self.place(tags, "sidebar")
            self.play(g.animate.scale(0.75).shift(LEFT * 2.5),
                      FadeIn(tags), run_time=min(1.5, vo.duration))

        with self.voiceover("Dijkstra's trick is to be greedy and patient. Keep a best known distance for every place, starting at zero for A and infinity for everyone else.") as vo:
            g.set_note("A", "0")
            self.play(g.highlight_node("A"), run_time=min(1.5, vo.duration))
            self.wait(0.3)

        with self.voiceover("Always visit the closest place you haven't finished yet. Then look at its roads, and ask whether going through it gives a shorter way to its neighbors.") as vo:
            g.set_note("C", "2")
            g.set_note("B", "4")
            self.play(g.highlight_edge("A", "C"), run_time=min(1.5, vo.duration))
            self.wait(0.3)

        with self.voiceover("Notice what happens at B. Going straight from A costs four, but going through C costs two plus one, only three. So we update B to three.") as vo:
            g.set_note("B", "3")
            self.play(g.highlight_edge("C", "B"), run_time=min(1.5, vo.duration))
            self.wait(0.3)

        self.fade_out_all()

        with self.voiceover("Let's watch the whole thing run. Each step, the closest unfinished node gets locked in, and its neighbors get their distances improved.") as vo:
            self.set_title("Dijkstra in action")
            g2 = GraphViz(edges, weighted=True, layout=layout)
            self.show(g2, "main", animation=FadeIn(g2), run_time=1)
        g2.run_dijkstra(self, "A", target="E")

        with self.voiceover("The cheapest route to E is A, C, B, D, E, with a total cost of eleven. The direct-looking road from C to E would have cost twelve.") as vo:
            c = Card(Label("A → C → B → D → E = 11", size="body", color=theme.positive), title="Shortest path")
            self.place(c, "sidebar")
            self.play(g2.animate.scale(0.75).shift(LEFT * 2.5),
                      FadeIn(c), run_time=min(1.5, vo.duration))

        self.fade_out_all()

        with self.voiceover("So the hook's answer: your map app keeps a growing circle of finished places, always expanding at the cheapest edge. Greedy choices, made in order, are never regretted.") as vo:
            self.set_title("Recap")
            b = BulletList("Start at zero, others infinity", "Lock in the closest node", "Relax its neighbors", "Repeat until done", size="body")
            self.show(b, "main", animation=b.reveal(), run_time=min(3, vo.duration))
        self.wait(0.5)
