from animai import *


class DiagramsDemo(AnimaiScene):
    def construct(self):
        self.set_title("Flowchart")
        fc = Flowchart(
            {"in": "Read input", "check": "Valid?", "ok": "Save record", "err": "Show error"},
            [("in", "check"), ("check", "ok", "yes"), ("check", "err", "no")],
            shapes={"check": "diamond"},
        )
        self.show(fc, "main", animation=fc.build())
        self.play(fc.trace(["in", "check", "ok"]))

        self.set_title("Cycle")
        cycle = CycleDiagram(["Evaporation", "Condensation", "Precipitation", "Collection"])
        self.show(cycle, "main", animation=cycle.build())

        self.set_title("Venn diagram")
        venn = VennDiagram(["Mammals", "Can fly"])
        self.place(venn, "main")
        for text, sets in [("Dog", (0,)), ("Bat", (0, 1)), ("Eagle", (1,))]:
            venn.add_item(text, sets)
        self.show(venn, "main", animation=venn.build())
        self.play(FadeIn(venn.items))

        self.set_title("Comparison table")
        table = ComparisonTable(["", "Mitosis", "Meiosis"],
                                [["Daughter cells", "2", "4"], ["Genetically identical", "Yes", "No"],
                                 ["Purpose", "Growth", "Reproduction"]])
        self.show(table, "main", animation=table.build())

        self.set_title("Hierarchy")
        h = Hierarchy({"Animals": {"Vertebrates": ["Mammals", "Birds", "Fish"],
                                   "Invertebrates": ["Insects", "Mollusks"]}})
        self.show(h, "main", animation=h.build())
        self.wait()


class ChartsDemo(AnimaiScene):
    def construct(self):
        self.set_title("Bar plot")
        plot = BarPlot([3.2, 5.1, 1.4, 2.6], ["Coal", "Gas", "Solar", "Wind"], unit=" TW")
        self.show(plot, "main", animation=plot.grow())
        self.play(plot.animate_values([2.1, 5.6, 3.9, 3.0]))

        self.set_title("Ranking race")
        race = BarPlot([5, 3, 4, 1], ["USA", "China", "Japan", "India"], horizontal=True)
        self.show(race, "main", animation=race.grow())
        self.play(race.animate_values([5, 9, 3, 4], sort=True), run_time=2)

        self.set_title("Line plot")
        years = list(range(1900, 2021, 10))
        line = LinePlot(years, {"World": [1.6, 1.8, 1.9, 2.1, 2.3, 2.5, 3.0, 3.7, 4.4, 5.3, 6.1, 6.9, 7.8],
                                "Asia": [0.9, 1.0, 1.0, 1.1, 1.2, 1.4, 1.7, 2.1, 2.6, 3.2, 3.7, 4.2, 4.6]},
                        x_label="Year", y_label="Population (billions)")
        self.show(line, "main", animation=line.draw())

        self.set_title("Pie chart")
        pie = PieChart([36, 23, 22, 10, 9], ["Coal", "Gas", "Renewables", "Nuclear", "Oil"])
        self.show(pie, "main", animation=pie.build())
        self.play(pie.explode(2))
        self.wait()
