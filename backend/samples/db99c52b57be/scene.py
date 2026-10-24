from animai import *

TITLE = "Why Ice Floats"
THEME = "chalkboard"


class Explainer(AnimaiScene):
    def construct(self):
        random.seed(0)
        np.random.seed(0)
        theme = get_theme()

        # Beat 1: hook
        with self.voiceover("Almost every solid sinks in its own liquid. Drop solid wax into melted wax, and it sinks. So why does ice float on water?") as vo:
            self.title_card("Why Ice Floats", "The strange behavior of water")
        self.fade_out_all()

        # Beat 2: the puzzle with densities
        with self.voiceover("Here is the surprise. Liquid water at four degrees Celsius is denser than ice, about one gram per cubic centimeter versus point nine two.") as vo:
            self.set_title("Ice is less dense")
            plot = BarPlot([1.00, 0.92], ["Liquid water", "Ice"], colors=[theme.primary, theme.secondary],
                           unit=" g/cm³", max_value=1.2)
            self.show(plot, "main", animation=plot.grow(), run_time=min(2.5, vo.duration))

        # Beat 3: molecule
        with self.voiceover("The reason lives inside the molecule. Each water molecule has one oxygen and two hydrogens, bent at about one hundred and four degrees.") as vo:
            self.set_title("The water molecule")
            mol = Molecule("O", show_hydrogens=True, name="Water")
            self.show(mol, "main", animation=mol.build(), run_time=min(2.5, vo.duration), scale_up=True)
        self.fade_out_all()

        # Beat 4: hydrogen bonds
        with self.voiceover("Oxygen pulls electrons toward itself, so it is slightly negative and the hydrogens slightly positive. Neighboring molecules attract through hydrogen bonds.") as vo:
            self.set_title("Hydrogen bonds")

            def water_molecule(o_pos):
                o_pos = np.array(o_pos, dtype=float)
                o = VGroup(Circle(radius=0.38, fill_color=theme.negative, fill_opacity=0.4,
                                  stroke_color=theme.negative),
                           Label("O", size="small")).move_to(o_pos)
                hs = []
                lines = []
                for dx in (-0.9, 0.9):
                    hp = o_pos + np.array([dx, 0.7, 0])
                    h = VGroup(Circle(radius=0.25, fill_color=theme.primary, fill_opacity=0.4,
                                      stroke_color=theme.primary),
                               Label("H", size="small")).move_to(hp)
                    ln = Line(o_pos, hp, color=GREY_B, stroke_width=3)
                    hs.append(h)
                    lines.append(ln)
                return o, hs, lines

            o_a, hs_a, ln_a = water_molecule([-2.6, -0.4, 0])
            o_b, hs_b, ln_b = water_molecule([2.6, -0.4, 0])
            mols = VGroup(*ln_a, *ln_b, o_a, o_b, *hs_a, *hs_b)
            hb = DashedLine(hs_a[1].get_right() + RIGHT * 0.05, o_b.get_left() + LEFT * 0.05,
                            color=theme.accent, stroke_width=4)
            hb_label = Label("hydrogen bond", size="small", color=theme.accent).next_to(hb, DOWN, buff=0.5)
            dm = Label("δ−", size="small", color=theme.negative).next_to(o_a, DOWN, buff=0.15)
            dp = Label("δ+", size="small", color=theme.primary).next_to(hs_a[1], UP, buff=0.1)
            grp = VGroup(mols, hb, hb_label, dm, dp)
            self.show(grp, "main", animation=FadeIn, run_time=min(2.0, vo.duration), scale_up=True)

        # Beat 5: liquid is jumbled
        with self.voiceover("In liquid water, molecules tumble around. Bonds constantly break and reform, so molecules can crowd close together.") as vo:
            self.set_title("Liquid: jumbled and close")
            dots = VGroup()
            for i in range(12):
                for j in range(6):
                    d = Dot(radius=0.15, fill_color=theme.primary)
                    d.move_to([-2.5 + i * 0.45 + np.random.uniform(-0.08, 0.08),
                               -1.1 + j * 0.44 + np.random.uniform(-0.08, 0.08), 0])
                    dots.add(d)
            box = Rectangle(width=6, height=3.4, color=GREY_B)
            liquid = VGroup(box, dots)
            self.show(liquid, "main", animation=FadeIn, run_time=1)
            self.play(*[d.animate.shift(np.random.uniform(-0.12, 0.12) * RIGHT + np.random.uniform(-0.12, 0.12) * UP)
                        for d in dots], run_time=max(vo.get_remaining_duration() - 0.2, 0.5))

        # Beat 6: ice is a lattice
        with self.voiceover("When water freezes, molecules lock into a hexagonal lattice. Each one bonds to four neighbors at fixed angles, which holds them farther apart.") as vo:
            self.set_title("Ice: an open hexagonal lattice")
            r = 0.8
            dx = 1.5 * r
            dy = math.sqrt(3) * r
            hexes = VGroup()
            for i in range(4):
                for j in range(3):
                    h = RegularPolygon(6, radius=r, color=theme.secondary, stroke_width=4)
                    h.move_to([i * dx, j * dy + (dy / 2 if i % 2 else 0), 0])
                    hexes.add(h)
            vs = VGroup(*[Dot(p, radius=0.09, fill_color=theme.accent)
                          for h in hexes for p in h.get_vertices()])
            lattice = VGroup(hexes, vs)
            self.show(lattice, "main", animation=ShowCreation, run_time=min(3, vo.duration))

        self.fade_out_all()

        # Beat 7: compare spacing
        with self.voiceover("The lattice is full of empty space. Packed this way, the same molecules take up about nine percent more volume, so ice is lighter per unit volume.") as vo:
            self.set_title("Open structure, more volume")

            def packed(spacing, w, h, color):
                b = Rectangle(width=w, height=h, color=color)
                ds = VGroup(*[Dot([(i - 1) * spacing, (j - 0.5) * spacing, 0], radius=0.14, fill_color=color)
                              for i in range(3) for j in range(2)])
                ds.move_to(b)
                return VGroup(b, ds)

            liq = packed(0.5, 2.0, 1.5, theme.primary)
            ice = packed(0.62, 2.4, 1.8, theme.secondary)
            liq_l = Label("Liquid: tightly packed", size="small", color=theme.primary).next_to(liq, DOWN, buff=0.3)
            ice_l = Label("Ice: open, +9% volume", size="small", color=theme.secondary).next_to(ice, DOWN, buff=0.3)
            both = VGroup(VGroup(liq, liq_l), VGroup(ice, ice_l)).arrange(RIGHT, buff=1.2)
            self.show(both, "main", animation=FadeIn, run_time=min(2, vo.duration), scale_up=True)

        # Beat 8: floating
        with self.voiceover("Lighter per volume means it floats, with about nine tenths of an iceberg below the surface. Notice the ice sits mostly submerged.") as vo:
            self.set_title("Floating ice")
            water = Rectangle(width=9, height=2.4, fill_color=theme.primary, fill_opacity=0.35, stroke_width=0)
            ice_block = Rectangle(width=2.4, height=1.6, fill_color=WHITE, fill_opacity=0.85, stroke_color=WHITE)
            ice_block.move_to([0, water.get_top()[1] + 0.1 * 1.6 - 0.8, 0])
            lbl = Label("90% below", size="small", color=BLACK).move_to(ice_block)
            scene_grp = VGroup(water, ice_block, lbl)
            self.show(scene_grp, "main", animation=FadeIn, run_time=min(2, vo.duration))

        self.fade_out_all()

        # Beat 9: recap
        with self.voiceover("So ice floats because hydrogen bonds force water into an open lattice when it freezes. That floating layer insulates lakes, letting life survive winter below.") as vo:
            self.set_title("The aha")
            bl = BulletList("Hydrogen bonds", "Open hexagonal lattice", "Ice is less dense", "It floats")
            self.show(bl, "main", animation=bl.reveal(), run_time=min(3, vo.duration))
