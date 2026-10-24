from animai import *


class ScalingCheck(AnimaiScene):
    """Components squeezed into small regions, then mutated: new parts must match the scale."""

    def construct(self):
        stack = StackViz([1, 2])
        bars = BarPlot([3, 5, 2], ["A", "B", "C"])
        ll = LinkedListViz([3, 7, 1])
        bst = BinaryTree([8, 3, 10, 1, 6])
        self.show(stack, "top_left")
        self.show(bars, "bottom_right", animation=bars.grow())
        self.show(ll, "top_right")
        self.show(bst, "bottom_left")
        self.play(stack.push(3), bars.animate_values([6, 2, 4]), ll.insert(1, 9))
        self.play(bst.insert(7))
        self.wait(0.5)
        self.fade_out_all()

        g = GraphViz([("A", "B", 2), ("B", "C", 3), ("A", "C", 7)], weighted=True)
        pie = PieChart([50, 30, 20], ["X", "Y", "Z"])
        venn = VennDiagram(["P", "Q"])
        num = BinaryNumber(5)
        self.show(g, "top_left")
        self.show(pie, "top_right", animation=pie.build())
        self.show(venn, "bottom_left")
        self.show(num, "bottom_right")
        venn.add_item("both", (0, 1))
        self.play(g.set_note("C", "d=5"), FadeIn(venn.items), num.set_value(12), pie.explode(0))
        self.wait()
