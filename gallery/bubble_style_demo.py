"""A short, silent tour of the Figma visual identity across unrelated subjects.

python -m animai gallery/bubble_style_demo.py BubbleStyleDemo -q medium --no-narration
"""
from animai import *

THEME = "bubble"


class BubbleStyleDemo(AnimaiScene):
    def construct(self):
        self.title_card("Small ideas. Big clarity.", "A softer way to see how things work", run_time=1.2)
        self.wait(1.4)
        self.fade_out_all(.5)

        self.set_title("Bubble Sort", run_time=.6)
        bars = BarPlot([3, 1, 5, 2, 6, 4], ["", "", "", "", "", ""], width=5.4, height=2.5)
        code = CodeBlock("for i in range(n):\n  swapped = False\n  for j in range(n-1-i):\n    if a[j] > a[j+1]:\n      swap(j, j+1)\n      swapped = True", font_size=20)
        stats = VGroup(StatPill("Pass", 0), StatPill("Compares", 0), StatPill("Swaps", 0)).arrange(RIGHT, buff=.2)
        content = VGroup(stats, VGroup(bars, code).arrange(RIGHT, buff=.45)).arrange(DOWN, buff=.4)
        self.show(Card(content, padding=.4), "stage", run_time=.7)
        self.show(Card(Label("The tallest bubbles\nto the end", size=28, color=get_theme().accent),
                       title="One simple idea"), "sidebar", run_time=.6)
        self.wait(1.2)
        self.play(stats[0].set_value(1), stats[1].set_value(5), stats[2].set_value(3), run_time=.7)
        self.wait(.7)
        self.fade_out_all(.5)

        self.set_title("A place for every value", run_time=.6)
        stack, queue = StackViz([1, 2]), QueueViz(["A", "B", "C"])
        self.show(stack, "top_left", run_time=.5)
        self.show(queue, "top_right", run_time=.5)
        graph = GraphViz([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")])
        self.show(graph, "bottom_left", run_time=.5)
        self.show(BinaryTree([8, 3, 10, 1, 6]), "bottom_right", run_time=.5)
        self.play(stack.push(3), queue.enqueue("D"), graph.visit("C"), run_time=.8)
        self.wait(.8)
        self.fade_out_all(.5)

        self.set_title("Patterns in the numbers", run_time=.6)
        chart = LinePlot([0, 1, 2, 3, 4], {"First idea": [1, 2, 2, 4, 5], "Second idea": [4, 3, 3, 2, 1]},
                         width=4.2, height=2.4, size="tiny")
        self.show(chart, "left", animation=chart.draw(), run_time=.8)
        pie = PieChart([3, 2, 1], ["A", "B", "C"], radius=1.4)
        self.show(pie, "right", animation=pie.build(), run_time=.8)
        self.wait(1.5)
        self.fade_out_all(.5)

        self.set_title("Science, with a little softness", run_time=.6)
        atom = BohrAtom("C")
        self.show(atom, "top_left", run_time=.5)
        molecule = Molecule("water", name="Water")
        self.show(molecule, "top_right", animation=molecule.build(), run_time=.5)
        pendulum, spring = Pendulum(length=1.7), MassSpring(rest_length=2, amplitude=.5)
        self.show(pendulum, "bottom_left", run_time=.5)
        self.show(spring, "bottom_right", run_time=.5)
        self.play(atom.orbit(1.6), pendulum.swing(1.6), spring.oscillate(1.6))
        self.fade_out_all(.5)

        self.set_title("Connected ideas", run_time=.6)
        flow = Flowchart({"a": "Ask", "b": "Explore", "c": "Understand"}, [("a", "b"), ("b", "c")])
        self.show(flow, "top", animation=flow.build(), run_time=.8)
        table = ComparisonTable(["", "Observe", "Explain"], [["Start with", "A pattern", "A question"],
                                                                ["Look for", "Examples", "Connections"]], size=24)
        self.show(table, "bottom", animation=table.build(), run_time=.8)
        self.wait(1.2)
        self.fade_out_all(.5)

        self.set_title("Stories across space and time", run_time=.6)
        world = WorldMap("world")
        self.show(world, "top", animation=world.build(), run_time=.8)
        timeline = Timeline(1900, 2000, width=10)
        timeline.add_event(1910, "An idea")
        timeline.add_event(1950, "A discovery")
        timeline.add_event(1990, "A new question")
        self.show(timeline, "bottom", animation=timeline.build(), run_time=.8)
        self.wait(1.4)
