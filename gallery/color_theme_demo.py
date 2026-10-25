"""The same typography and geometry, recolored with --theme <palette>."""
import json
from animai import *

THEME = "bubble"


class ColorThemeDemo(AnimaiScene):
    def construct(self):
        self.set_title("Ideas in every color", run_time=.3)
        plot = BarPlot([3, 1, 5, 2, 6, 4], ["A", "B", "C", "D", "E", "F"],
                       width=5, height=2.4, size=24)
        self.show(plot, "top_left", animation=plot.grow(), run_time=.4)
        code = CodeBlock("for idea in ideas:\n    if idea.is_clear():\n        share(idea)\n    else:\n        try_again()", font_size=20)
        self.show(code, "top_right", run_time=.3)
        flow = Flowchart({"a":"An idea", "b":"A scene", "c":"An aha!"}, [("a","b"),("b","c")])
        self.show(flow, "bottom_left", animation=flow.build(), run_time=.4)
        molecule = Molecule("water", name="Water")
        atom = BohrAtom("C")
        science = VGroup(molecule, atom).arrange(RIGHT, buff=1.0)
        self.show(science, "bottom_right", run_time=.3)
        geometry = {name: [round(m.get_width(),6), round(m.get_height(),6)]
                    for name,m in [("plot",plot),("code",code),("flow",flow),("science",science)]}
        print("@@THEME_GEOMETRY " + json.dumps(geometry), flush=True)
        self.wait(.5)


class Explainer(ColorThemeDemo):
    pass
