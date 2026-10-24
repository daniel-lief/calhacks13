from animai import *

TITLE = "How Merge Sort Works"
THEME = "classic"


def merge_levels(data):
    rows = []
    size = 1
    while size < len(data):
        size *= 2
    size = 1
    while size <= len(data):
        chunks = [sorted(data[i:i + size]) for i in range(0, len(data), size)]
        rows.append("  |  ".join(" ".join(str(x) for x in c) for c in chunks))
        size *= 2
    return rows


class Explainer(AnimaiScene):
    def construct(self):
        random.seed(0)
        np.random.seed(0)
        theme = get_theme()

        with self.voiceover("How would you sort a million names? Comparing everything with everything would take forever. There's a smarter way, and it starts with giving up on the big problem.") as vo:
            self.title_card("Merge Sort", "Divide, then conquer")
        self.fade_out_all()

        # Split
        with self.voiceover("The first trick: split the list in half, then split each half again, and keep going until every piece holds just one number. A single number is already sorted.") as vo:
            self.set_title("Step 1: Split")
            tree = Hierarchy({
                "5 2 9 1 7 3 8 4": {
                    "5 2 9 1": {"5 2": ["5", "2"], "9 1": ["9", "1"]},
                    "7 3 8 4": {"7 3": ["7", "3"], "8 4": ["8", "4"]},
                }
            }, size="label")
            self.show(tree, "main", animation=tree.build(), run_time=min(5, vo.duration))
        self.fade_out_all()

        # Merge idea
        with self.voiceover("The second trick is merging. If you have two lists that are already sorted, combining them into one sorted list is easy: you only ever compare the two front items.") as vo:
            self.set_title("Step 2: Merge")
            a = ArrayViz([2, 5, 8])
            b = ArrayViz([1, 6, 9])
            self.show(VGroup(a, b).arrange(RIGHT, buff=1.5), "main", animation=FadeIn, run_time=min(2, vo.duration))
        self.fade_out_all()

        # Merge demo
        A = [2, 5, 8]
        B = [1, 6, 9]
        with self.voiceover("Watch the two pointers. Compare the front of each list, take the smaller one, and move that pointer forward. Repeat until everything has been copied into the result.") as vo:
            self.set_title("Merging two sorted lists")
            arr_a = ArrayViz(A)
            arr_b = ArrayViz(B)
            res = ArrayViz(["?"] * 6, show_indices=False)
            group = VGroup(arr_a, arr_b, res).arrange(DOWN, buff=1.3)
            self.show(group, "main", animation=FadeIn, run_time=1)
            pa = arr_a.pointer(0, "i")
            pb = arr_b.pointer(0, "j")
            self.play(FadeIn(pa), FadeIn(pb))
            i = j = k = 0
            while i < 3 or j < 3:
                take_a = j >= 3 or (i < 3 and A[i] <= B[j])
                if take_a:
                    val = A[i]
                    self.play(arr_a.highlight(i, theme.primary), run_time=0.3)
                    self.play(res.set_value(k, val), run_time=0.4)
                    self.play(arr_a.unhighlight(i), run_time=0.2)
                    i += 1
                    if i < 3:
                        self.play(arr_a.move_pointer(pa, i), run_time=0.3)
                    else:
                        self.play(FadeOut(pa), run_time=0.3)
                else:
                    val = B[j]
                    self.play(arr_b.highlight(j, theme.secondary), run_time=0.3)
                    self.play(res.set_value(k, val), run_time=0.4)
                    self.play(arr_b.unhighlight(j), run_time=0.2)
                    j += 1
                    if j < 3:
                        self.play(arr_b.move_pointer(pb, j), run_time=0.3)
                    else:
                        self.play(FadeOut(pb), run_time=0.3)
                k += 1
        with self.voiceover("Six numbers, six steps, and the result is perfectly sorted. Each item is touched just once.") as vo:
            self.play(Indicate(res), run_time=min(1.5, vo.duration))
        self.fade_out_all()

        # Merge back up
        with self.voiceover("Now run it in reverse. Merge the single numbers into sorted pairs, merge pairs into sorted fours, and finally merge the two halves into the full sorted list.") as vo:
            self.set_title("Step 3: Merge back up")
            data = [5, 2, 9, 1, 7, 3, 8, 4]
            rows = merge_levels(data)
            labels = VGroup(*[
                Label(r, size="body", color=palette_color(n)) for n, r in enumerate(rows)
            ]).arrange(DOWN, buff=0.45)
            self.show(labels, "main", animation=None, run_time=0.5)
            self.play(LaggedStart(*[FadeIn(l, shift=UP * 0.3) for l in labels],
                                  lag_ratio=0.8), run_time=min(5, vo.duration))
        self.fade_out_all()

        # Cost
        with self.voiceover("Why is this fast? Halving a list can only happen about log n times, and each level of merging touches every item once. So the work grows like n log n, far below n squared.") as vo:
            self.set_title("The cost")
            ns = list(range(2, 65, 2))
            plot = LinePlot(
                ns,
                {"n squared": [n * n for n in ns],
                 "n log n": [n * math.log2(n) for n in ns]},
                x_label="List size n", y_label="Steps",
                colors=[theme.negative, theme.positive])
            self.show(plot, "main", animation=plot.draw(), run_time=min(3, vo.duration))
        self.fade_out_all()

        with self.voiceover("For a million items, that's about twenty million steps instead of a trillion. The curves pull apart as the list grows.") as vo:
            self.set_title("A million items")
            n = 10 ** 6
            fast = n * math.log2(n)
            slow = n * n
            ratio = int(round(slow / fast, -3))
            card_fast = Card(
                VGroup(Label("n log n", size="body", color=theme.positive),
                       Label(f"about {fast / 1e6:.0f} million steps", size="body")).arrange(DOWN, buff=0.3),
                color=theme.positive)
            card_slow = Card(
                VGroup(Label("n squared", size="body", color=theme.negative),
                       Label("1 trillion steps", size="body")).arrange(DOWN, buff=0.3),
                color=theme.negative)
            cards = VGroup(card_fast, card_slow).arrange(RIGHT, buff=0.8)
            note = Label(f"About {ratio:,} times more work", size="body", color=theme.accent)
            both = VGroup(cards, note).arrange(DOWN, buff=0.7)
            self.show(both, "main", animation=FadeIn, run_time=min(2.5, vo.duration))
        self.fade_out_all()

        # Recap
        with self.voiceover("So: split until trivial, then merge sorted pieces back together. Hard problems get easy when you cut them small enough. That's how a million names get sorted in moments.") as vo:
            fc = Flowchart({"s": "Split in half", "r": "Sort each half", "m": "Merge"},
                           [("s", "r"), ("r", "m")],
                           colors={"s": theme.primary, "r": theme.accent, "m": theme.positive})
            self.show(fc, "main", animation=fc.build(), run_time=min(3, vo.duration))
        self.wait(0.5)
