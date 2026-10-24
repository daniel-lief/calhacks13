from animai import *


class ChemistryDemo(AnimaiScene):
    def construct(self):
        self.set_title("Molecules from SMILES")
        caffeine = Molecule("caffeine", name="Caffeine")
        water = Molecule("water", name="Water")
        self.show(caffeine, "left", animation=caffeine.build())
        self.show(water, "right", animation=water.build())
        self.play(caffeine.highlight_atoms(caffeine.atoms_of("N")))

        self.set_title("Reaction equation")
        eq = ChemEquation("2H2 + O2 -> 2H2O")
        self.show(eq, "top", animation=Write)
        energy = EnergyDiagram(reactants=50, transition=120, products=-240,
                               reactant_label="2H₂ + O₂", product_label="2H₂O", unit="kJ")
        self.place(energy, "bottom")
        self.show(energy, "bottom", animation=energy.draw())
        self.play(energy.show_activation())
        self.play(energy.show_delta_h())

        self.fade_out_all()
        self.set_title("Periodic table")
        pt = PeriodicTable()
        self.show(pt, "main", animation=pt.build())
        self.play(pt.highlight_group(1))
        self.play(pt.highlight_category("noble gas"))
        self.play(pt.reset())

        self.set_title("Bohr model")
        atom = BohrAtom("Na")
        self.show(atom, "left")
        self.play(atom.orbit(2))
        ethanol = Molecule3D("ethanol")
        self.show(ethanol, "right")
        self.play(ethanol.spin(run_time=3))
        self.wait()
