"""
Chemistry visuals: structural formulas and 3D ball-and-stick models generated from
SMILES (via RDKit), reaction equations (mhchem), reaction energy diagrams, the
periodic table, and Bohr-model atoms.
"""
from __future__ import annotations

import numpy as np

from manimlib import (
    Animation, AnimationGroup, Arrow, Circle, DashedLine, Dot, FadeIn, Group, Indicate,
    LaggedStart, Line, Line3D, Mobject, Rotate, Rotating, RoundedRectangle, ShowCreation, Sphere,
    Succession, Tex, Text, VGroup, VMobject, Write, UP, DOWN, LEFT, RIGHT, ORIGIN, OUT, TAU, PI,
)

from animai.core.media import Label
from animai.core.theme import get_theme

__all__ = [
    "Molecule", "Molecule3D", "ChemEquation", "EnergyDiagram", "PeriodicTable", "BohrAtom",
    "COMMON_MOLECULES", "element_color",
]

COMMON_MOLECULES = {
    "water": "O", "hydrogen peroxide": "OO", "ammonia": "N", "methane": "C", "ethane": "CC",
    "ethene": "C=C", "ethyne": "C#C", "propane": "CCC", "butane": "CCCC", "octane": "CCCCCCCC",
    "methanol": "CO", "ethanol": "CCO", "acetic acid": "CC(=O)O", "acetone": "CC(=O)C",
    "formaldehyde": "C=O", "carbon dioxide": "O=C=O", "carbon monoxide": "[C-]#[O+]",
    "oxygen": "O=O", "nitrogen": "N#N", "hydrogen": "[H][H]", "ozone": "[O-][O+]=O",
    "benzene": "c1ccccc1", "toluene": "Cc1ccccc1", "phenol": "Oc1ccccc1",
    "glucose": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
    "caffeine": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofen": "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "glycine": "NCC(=O)O", "alanine": "C[C@@H](C(=O)O)N", "urea": "NC(=O)N",
    "sodium chloride": "[Na+].[Cl-]", "sulfuric acid": "OS(=O)(=O)O", "nitric acid": "O[N+](=O)[O-]",
    "hydrochloric acid": "Cl", "sodium hydroxide": "[Na+].[OH-]", "adrenaline": "CNC[C@H](O)c1ccc(O)c(O)c1",
    "dopamine": "NCCc1ccc(O)c(O)c1", "serotonin": "NCCc1c[nH]c2ccc(O)cc12",
    "nicotine": "CN1CCC[C@H]1c1cccnc1", "cholesterol": "CC(C)CCC[C@@H](C)[C@H]1CC[C@H]2[C@@H]3CC=C4C[C@@H](O)CC[C@]4(C)[C@H]3CC[C@]12C",
}

_CPK = {
    "H": "#E8E8E8", "C": "#909090", "N": "#4A6CF7", "O": "#FF3B30", "F": "#7BE07B",
    "Cl": "#3DDC3D", "Br": "#C0392B", "I": "#9B59B6", "S": "#F4D03F", "P": "#FF8C1A",
    "Na": "#AB5CF2", "K": "#8F40D4", "Mg": "#4CAF50", "Ca": "#3DBF3D", "Fe": "#E06633",
    "Li": "#CC80FF", "B": "#FFB5B5", "Si": "#DAA520",
}
_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def element_color(symbol: str) -> str:
    """CPK-style color for an element, adjusted for the theme (carbon/hydrogen use text tones)."""
    theme = get_theme()
    if symbol in ("C", "H"):
        return theme.text if symbol == "C" else theme.muted
    return _CPK.get(symbol, theme.secondary)


def _mol_from(smiles_or_name: str):
    from rdkit import Chem
    smiles = COMMON_MOLECULES.get(smiles_or_name.lower().strip(), smiles_or_name)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Couldn't parse molecule {smiles_or_name!r}: give a SMILES string "
                         f"or one of: {', '.join(sorted(COMMON_MOLECULES))}")
    return mol


class Molecule(VGroup):
    """
    A 2D structural formula from a SMILES string or common name ("caffeine", "glucose",
    "ethanol"... see COMMON_MOLECULES). Carbon atoms are bond vertices (skeletal style)
    unless show_carbons=True; heteroatoms are colored labels with their hydrogens
    (OH, NH₂). show_hydrogens=True draws every H as its own atom (good for tiny molecules;
    default: automatic for molecules with 3 or fewer heavy atoms).

    `mol.atoms[i]` (label or vertex dot), `mol.bonds[(i, j)]`, `mol.atoms_of("O")` (indices);
    `mol.build()` draws bonds then labels; `mol.highlight_atoms([i, ...])`.

    Example: Molecule("caffeine", name="Caffeine")  or  Molecule("CCO", show_carbons=True)
    """

    def __init__(self, smiles: str, show_hydrogens: bool | None = None,
                 show_carbons: bool = False, bond_length: float = 0.85, name: str | None = None,
                 font_size: int = 30, **kwargs):
        from rdkit import Chem
        from rdkit.Chem import rdDepictor
        theme = get_theme()
        mol = _mol_from(smiles)
        heavy = mol.GetNumHeavyAtoms()
        if show_hydrogens is None:
            show_hydrogens = heavy <= 3
        if show_hydrogens:
            mol = Chem.AddHs(mol)
            show_carbons = True
        rdDepictor.Compute2DCoords(mol)
        Chem.Kekulize(mol, clearAromaticFlags=True)
        conf = mol.GetConformer()
        raw = np.array([[conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, 0.0]
                        for i in range(mol.GetNumAtoms())])
        # RDKit bonds are ~1.5 units long
        pts = (raw - raw.mean(axis=0)) * (bond_length / 1.5) if len(raw) > 1 else raw
        self.mol, self.symbols = mol, [a.GetSymbol() for a in mol.GetAtoms()]

        self.atoms: list[Mobject] = []
        labeled = []
        for a, p in zip(mol.GetAtoms(), pts):
            sym = a.GetSymbol()
            show_label = sym != "C" or show_carbons or a.GetDegree() == 0
            if show_label:
                text = sym
                hs = 0 if show_hydrogens else a.GetTotalNumHs()
                if hs:
                    text += "H" + (str(hs) if hs > 1 else "")
                charge = a.GetFormalCharge()
                if charge:
                    text += ("+" if charge > 0 else "−") * min(abs(charge), 1) if abs(charge) == 1 \
                        else f"{abs(charge)}{'+' if charge > 0 else '−'}"
                label = Text(text.translate(_SUBSCRIPTS), font=theme.font, font_size=font_size,
                             weight="BOLD", fill_color=element_color(sym))
                label.move_to(p)
                self.atoms.append(label)
                labeled.append(True)
            else:
                self.atoms.append(Dot(p, radius=0.001, fill_opacity=0))
                labeled.append(False)

        self.bonds = {}
        for b in mol.GetBonds():
            i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
            order = int(round(b.GetBondTypeAsDouble()))
            self.bonds[(i, j)] = self._bond(pts[i], pts[j], order, labeled[i], labeled[j],
                                            self._ring_side(mol, b, pts))
        parts = [*self.bonds.values(), *self.atoms]
        self.name_label = None
        if name:
            self.name_label = Label(name, size="small", color=theme.muted)
            parts.append(self.name_label)
        super().__init__(*parts, **kwargs)
        if self.name_label is not None:
            self.name_label.next_to(VGroup(*self.bonds.values(), *self.atoms), DOWN, buff=0.35)

    @staticmethod
    def _ring_side(mol, bond, pts):
        """For double bonds in rings, offset the second line toward the ring center."""
        ri = mol.GetRingInfo()
        for ring in ri.BondRings():
            if bond.GetIdx() in ring:
                atoms = set()
                for bi in ring:
                    bb = mol.GetBondWithIdx(bi)
                    atoms.update((bb.GetBeginAtomIdx(), bb.GetEndAtomIdx()))
                return np.mean([pts[a] for a in atoms], axis=0)
        return None

    def _bond(self, p, q, order, label_p, label_q, ring_center):
        theme = get_theme()
        d = q - p
        length = np.linalg.norm(d)
        u = d / (length or 1)
        trim = 0.24
        a = p + u * (trim if label_p else 0)
        b = q - u * (trim if label_q else 0)
        normal = np.array([-u[1], u[0], 0])
        style = dict(stroke_color=theme.text, stroke_width=3)
        if order == 1:
            return Line(a, b, **style)
        gap = 0.12
        if order == 2:
            if ring_center is not None:
                side = np.sign(np.dot(ring_center - (p + q) / 2, normal)) or 1
                inner_a = a + normal * side * gap * 1.4 + u * 0.1
                inner_b = b + normal * side * gap * 1.4 - u * 0.1
                return VGroup(Line(a, b, **style), Line(inner_a, inner_b, **style))
            return VGroup(Line(a + normal * gap / 2, b + normal * gap / 2, **style),
                          Line(a - normal * gap / 2, b - normal * gap / 2, **style))
        return VGroup(*(Line(a + normal * k * gap, b + normal * k * gap, **style) for k in (-1, 0, 1)))

    def atoms_of(self, symbol: str) -> list[int]:
        return [i for i, s in enumerate(self.symbols) if s == symbol]

    def bond(self, i: int, j: int) -> Mobject:
        return self.bonds[(i, j)] if (i, j) in self.bonds else self.bonds[(j, i)]

    def build(self, run_time: float = 2.0, **kwargs) -> Animation:
        labels = [a for a in self.atoms if isinstance(a, Text)]
        anims = [LaggedStart(*(ShowCreation(b) for b in self.bonds.values()), lag_ratio=0.05,
                             run_time=run_time * 0.6),
                 LaggedStart(*(FadeIn(l, scale=0.7) for l in labels), lag_ratio=0.05,
                             run_time=run_time * 0.4)]
        if self.name_label is not None:
            anims.append(FadeIn(self.name_label))
        return Succession(*anims, **kwargs)

    def highlight_atoms(self, indices, color=None) -> Animation:
        c = color or get_theme().accent
        return AnimationGroup(*(Indicate(self.atoms[i], color=c, scale_factor=1.4) for i in indices))


class Molecule3D(Group):
    """
    A 3D ball-and-stick model (geometry optimized with RDKit's MMFF force field).
    Rotate it with `self.play(mol.spin())`, or tilt the camera with
    `self.frame.reorient(theta_deg, phi_deg)`.

    Example: water = Molecule3D("water"); self.show(water, "main"); self.play(water.spin(run_time=6))
    """

    def __init__(self, smiles: str, scale: float = 1.3, seed: int = 7, **kwargs):
        from rdkit import Chem
        from rdkit.Chem import rdDistGeom, rdForceFieldHelpers
        mol = Chem.AddHs(_mol_from(smiles))
        if rdDistGeom.EmbedMolecule(mol, randomSeed=seed) != 0:
            raise ValueError(f"Couldn't generate 3D coordinates for {smiles!r}")
        try:
            rdForceFieldHelpers.MMFFOptimizeMolecule(mol)
        except Exception:
            pass
        conf = mol.GetConformer()
        pts = np.array([[conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y,
                         conf.GetAtomPosition(i).z] for i in range(mol.GetNumAtoms())])
        pts = (pts - pts.mean(axis=0)) * scale
        self.symbols = [a.GetSymbol() for a in mol.GetAtoms()]
        self.balls = Group()
        for sym, p in zip(self.symbols, pts):
            r = 0.22 if sym == "H" else 0.36
            color = _CPK.get(sym, "#B0B0B0") if sym != "C" else "#5A5A5A"
            ball = Sphere(radius=r * scale / 1.3, resolution=(24, 12))
            ball.set_color(color).move_to(p)
            self.balls.add(ball)
        self.sticks = Group()
        for b in mol.GetBonds():
            i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
            stick = Line3D(pts[i], pts[j], width=0.08, resolution=(8, 8))
            stick.set_color("#BFBFBF")
            self.sticks.add(stick)
        super().__init__(self.sticks, self.balls, **kwargs)
        self.apply_depth_test()

    def spin(self, angle: float = TAU, axis=UP, run_time: float = 6.0, **kwargs) -> Animation:
        return Rotate(self, angle, axis=axis, run_time=run_time, rate_func=lambda t: t, **kwargs)

    def build(self, **kwargs) -> Animation:
        return Succession(LaggedStart(*(FadeIn(b, scale=0.5) for b in self.balls), lag_ratio=0.05),
                          FadeIn(self.sticks), **kwargs)


class ChemEquation(Tex):
    """
    A chemical equation typeset with mhchem: write it as you would in \\ce{...}
    (no \\ce needed). Arrows: ->, <=>, <-. States: (s), (aq). Charges: ^2+, ^-.

    Example: ChemEquation("2H2 + O2 -> 2H2O")  or  ChemEquation("CH3COOH <=> CH3COO^- + H^+")
    """

    def __init__(self, equation: str, font_size: int = 48, **kwargs):
        self.equation = equation
        super().__init__(R"\ce{" + equation + "}", font_size=font_size,
                         additional_preamble=R"\usepackage[version=4]{mhchem}", **kwargs)


class EnergyDiagram(VGroup):
    """
    Reaction energy profile: reactant level, transition-state peak, product level.
    Energies are in any consistent unit (e.g. kJ/mol). `diagram.draw()` traces the curve;
    `diagram.show_activation()` and `diagram.show_delta_h()` add labeled arrows;
    `diagram.add_catalyst(peak)` returns an animation drawing a lower dashed path.

    Example:
        d = EnergyDiagram(reactants=50, transition=120, products=10,
                          reactant_label="H₂ + O₂", product_label="H₂O")
        self.show(d, "main", animation=d.draw()); self.play(d.show_activation())
    """

    def __init__(self, reactants: float, transition: float, products: float,
                 reactant_label: str = "Reactants", product_label: str = "Products",
                 width: float = 10.0, height: float = 5.0, unit: str = "", **kwargs):
        theme = get_theme()
        self.E = (reactants, transition, products)
        self.w, self.h, self.unit = width, height, unit
        lo, hi = min(self.E + (0,)), max(self.E)
        self._lo, self._span = lo, (hi - lo) or 1
        self.axes = VGroup(
            Line(ORIGIN, UP * height * 1.08, stroke_color=theme.muted, stroke_width=2.5),
            Line(ORIGIN, RIGHT * width, stroke_color=theme.muted, stroke_width=2.5),
        )
        self.axis_labels = VGroup(
            Label("Energy", size="small", color=theme.muted).rotate(PI / 2).next_to(self.axes[0], LEFT, buff=0.2),
            Label("Reaction progress", size="small", color=theme.muted).next_to(self.axes[1], DOWN, buff=0.2),
        )
        self.curve = VMobject(stroke_color=theme.primary, stroke_width=5)
        self.curve.set_points_smoothly([self._p(x, e) for x, e in self._profile(transition)])
        self.reactant_label = Label(reactant_label, size="small").next_to(self._p(1.1, reactants), UP, buff=0.15)
        self.product_label = Label(product_label, size="small").next_to(self._p(8.9, products), UP, buff=0.15)
        super().__init__(self.axes, self.axis_labels, self.curve, self.reactant_label,
                         self.product_label, **kwargs)

    def _profile(self, peak):
        r, _, p = self.E
        return [(0.2, r), (2.0, r), (3.6, r + (peak - r) * 0.55), (5.0, peak),
                (6.4, p + (peak - p) * 0.55), (8.0, p), (9.8, p)]

    def _p(self, x, e):
        """Scene point for progress x (0-10) and energy e, from the axes' current geometry."""
        if hasattr(self, "axes"):
            origin = self.axes[1].get_start()
            w = self.axes[1].get_length()
            h = self.axes[0].get_length() / 1.08
        else:
            origin, w, h = ORIGIN, self.w, self.h
        return origin + RIGHT * x / 10 * w + UP * (0.15 + (e - self._lo) / self._span * 0.85) * h

    def draw(self, run_time: float = 2.5, **kwargs) -> Animation:
        return Succession(
            AnimationGroup(ShowCreation(self.axes), FadeIn(self.axis_labels), run_time=1),
            ShowCreation(self.curve, run_time=run_time),
            AnimationGroup(FadeIn(self.reactant_label), FadeIn(self.product_label)),
            **kwargs,
        )

    def _scale(self) -> float:
        return self.axes[1].get_length() / self.w

    def _arrow_with_label(self, x, e0, e1, text, color, side=RIGHT):
        a, b = self._p(x, e0), self._p(x, e1)
        mid = (a + b) / 2
        arrow = VGroup(Arrow(mid, a, buff=0, thickness=2.5, fill_color=color),
                       Arrow(mid, b, buff=0, thickness=2.5, fill_color=color))
        label = Label(text, size="small", color=color, bold=True).scale(self._scale())
        label.next_to(arrow, side, buff=0.15)
        return VGroup(arrow, label)

    def show_activation(self, label: str | None = None) -> Animation:
        theme = get_theme()
        r, t, _ = self.E
        text = label or ("Eₐ" + (f" = {t - r:g} {self.unit}".rstrip() if self.unit else ""))
        level = DashedLine(self._p(1.0, r), self._p(5.6, r), stroke_color=theme.muted, stroke_width=2)
        group = self._arrow_with_label(5.0, r, t, text, theme.accent)
        self.add(level, group)
        return AnimationGroup(ShowCreation(level), FadeIn(group, shift=UP * 0.2))

    def show_delta_h(self, label: str | None = None) -> Animation:
        theme = get_theme()
        r, _, p = self.E
        text = label or ("ΔH" + (f" = {p - r:+g} {self.unit}".rstrip() if self.unit else ""))
        level = DashedLine(self._p(2.0, r), self._p(9.4, r), stroke_color=theme.muted, stroke_width=2)
        color = theme.positive if p < r else theme.negative
        group = self._arrow_with_label(9.2, r, p, text, color)
        self.add(level, group)
        return AnimationGroup(ShowCreation(level), FadeIn(group, shift=UP * 0.2))

    def add_catalyst(self, peak: float, label: str = "with catalyst") -> Animation:
        theme = get_theme()
        path = VMobject(stroke_color=theme.positive, stroke_width=4)
        path.set_points_smoothly([self._p(x, e) for x, e in self._profile(peak)])
        dashed = path.copy()
        from manimlib import DashedVMobject
        dashed = DashedVMobject(path, num_dashes=40)
        tag = Label(label, size="small", color=theme.positive).scale(self._scale())
        tag.next_to(self._p(3.0, self.E[0] + (peak - self.E[0]) * 0.2), DOWN, buff=0.3)
        self.add(dashed, tag)
        return AnimationGroup(ShowCreation(dashed), FadeIn(tag))


_ELEMENTS = (
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se "
    "Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb "
    "Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm "
    "Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
).split()
assert len(_ELEMENTS) == 118

_CATEGORIES = {
    "alkali metal": {3, 11, 19, 37, 55, 87},
    "alkaline earth metal": {4, 12, 20, 38, 56, 88},
    "transition metal": set(range(21, 31)) | set(range(39, 49)) | set(range(72, 81)) | set(range(104, 113)),
    "lanthanide": set(range(57, 72)),
    "actinide": set(range(89, 104)),
    "post-transition metal": {13, 31, 49, 50, 81, 82, 83, 84, 113, 114, 115, 116},
    "metalloid": {5, 14, 32, 33, 51, 52},
    "nonmetal": {1, 6, 7, 8, 15, 16, 34},
    "halogen": {9, 17, 35, 53, 85, 117},
    "noble gas": {2, 10, 18, 36, 54, 86, 118},
}
_CATEGORY_COLORS = {
    "alkali metal": "#FC6255", "alkaline earth metal": "#F0AC5F", "transition metal": "#E8C27A",
    "lanthanide": "#E07BB8", "actinide": "#C792EA", "post-transition metal": "#83C167",
    "metalloid": "#5CD0B3", "nonmetal": "#58C4DD", "halogen": "#7FD1FF", "noble gas": "#9A72AC",
}


def _grid_position(z: int) -> tuple[float, int]:
    """(row, column) in the standard 18-column layout; f-block rows are 8.5 and 9.5."""
    if 57 <= z <= 71:
        return 8.5, 3 + (z - 57)
    if 89 <= z <= 103:
        return 9.5, 3 + (z - 89)
    bounds = [0, 2, 10, 18, 36, 54, 86, 118]
    period = next(p for p in range(1, 8) if z <= bounds[p])
    k = z - bounds[period - 1]  # 1-based position within the period
    if period == 1:
        col = 1 if z == 1 else 18
    elif period in (2, 3):
        col = k if k <= 2 else k + 10
    elif period in (4, 5):
        col = k
    else:
        if k <= 2:
            col = k
        else:
            col = k - 14 if k >= 18 else 3  # k 3..17 are the f-block, placed below
    return float(period), col


class PeriodicTable(VGroup):
    """
    The periodic table with cells colored by category. `table.element("Na")` returns a cell;
    `table.highlight(["Li", "Na", "K"])`, `table.highlight_group(17)`,
    `table.highlight_period(3)` and `table.highlight_category("noble gas")` return animations
    that dim everything else. `table.build()` sweeps the cells in.

    Example: pt = PeriodicTable(); self.show(pt, "main", animation=pt.build()); self.play(pt.highlight_group(1))
    """

    def __init__(self, cell_size: float = 0.68, show_numbers: bool = True, **kwargs):
        theme = get_theme()
        self.cells = {}
        self.z_of = {}
        for z, sym in enumerate(_ELEMENTS, start=1):
            row, col = _grid_position(z)
            cat = next(c for c, zs in _CATEGORIES.items() if z in zs)
            color = _CATEGORY_COLORS[cat]
            box = RoundedRectangle(width=cell_size * 0.94, height=cell_size * 0.94,
                                   corner_radius=0.05, fill_color=color, fill_opacity=0.28,
                                   stroke_color=color, stroke_width=1.5)
            label = Text(sym, font=theme.font, font_size=int(cell_size * 34), weight="BOLD",
                         fill_color=theme.text)
            parts = [box, label.move_to(box).shift(DOWN * cell_size * 0.06)]
            if show_numbers:
                num = Text(str(z), font=theme.font, font_size=int(cell_size * 15),
                           fill_color=theme.muted)
                num.move_to(box.get_corner(UP + LEFT) + np.array([0.06, -0.06, 0]) * cell_size / 0.68,
                            aligned_edge=UP + LEFT)
                parts.append(num)
            cell = VGroup(*parts).move_to(np.array([col * cell_size, -row * cell_size, 0]))
            cell.category, cell.z, cell.period = cat, z, row
            cell.group_number = col if row < 8 else None
            self.cells[sym] = cell
            self.z_of[sym] = z
        super().__init__(*self.cells.values(), **kwargs)
        self.center()

    def element(self, symbol: str) -> Mobject:
        return self.cells[symbol]

    def _focus(self, symbols) -> Animation:
        chosen = set(symbols)
        anims = []
        for sym, cell in self.cells.items():
            if sym in chosen:
                anims.append(cell.animate.set_opacity(1))
            else:
                anims.append(cell.animate.set_opacity(0.18))
        return AnimationGroup(*anims)

    def highlight(self, symbols) -> Animation:
        return self._focus(symbols)

    def highlight_group(self, group: int) -> Animation:
        return self._focus([s for s, c in self.cells.items() if c.group_number == group])

    def highlight_period(self, period: int) -> Animation:
        return self._focus([s for s, c in self.cells.items() if c.period == period])

    def highlight_category(self, category: str) -> Animation:
        return self._focus([s for s, c in self.cells.items() if c.category == category])

    def reset(self) -> Animation:
        return AnimationGroup(*(c.animate.set_opacity(1) for c in self.cells.values()))

    def build(self, run_time: float = 2.5, **kwargs) -> Animation:
        ordered = sorted(self.cells.values(), key=lambda c: c.z)
        return LaggedStart(*(FadeIn(c, scale=0.6) for c in ordered), lag_ratio=0.02,
                           run_time=run_time, **kwargs)


class BohrAtom(VGroup):
    """
    Bohr model: a nucleus labeled with the element symbol and electrons on circular shells
    (filled 2, 8, 8, 18...). `atom.orbit(run_time)` spins the shells; `atom.shells[k]` and
    `atom.electrons[k]` (lists per shell, innermost first);
    `atom.jump(shell_from, shell_to)` animates one electron moving between shells.

    Example: atom = BohrAtom("Na"); self.show(atom, "main"); self.play(atom.orbit(4))
    """

    def __init__(self, element: str, electrons: int | None = None, shell_gap: float = 0.6,
                 **kwargs):
        theme = get_theme()
        z = _ELEMENTS.index(element) + 1
        n = z if electrons is None else electrons
        capacities, counts = [2, 8, 8, 18, 18, 32, 32], []
        left = n
        for cap in capacities:
            if left <= 0:
                break
            counts.append(min(cap, left))
            left -= cap
        self.nucleus = VGroup(Circle(radius=0.45, fill_color=theme.negative, fill_opacity=0.85,
                                     stroke_width=0),
                              Label(element, size="label", bold=True))
        self.shells, self.electrons = VGroup(), []
        for k, count in enumerate(counts):
            r = 0.45 + shell_gap * (k + 1)
            shell = Circle(radius=r, stroke_color=theme.muted, stroke_width=1.5)
            self.shells.add(shell)
            dots = [Dot(r * np.array([np.cos(a), np.sin(a), 0]), radius=0.09, fill_color=theme.primary)
                    for a in np.linspace(0, TAU, count, endpoint=False) + k * 0.4]
            self.electrons.append(VGroup(*dots))
        self.shell_counts = counts
        super().__init__(self.shells, self.nucleus, *self.electrons, **kwargs)

    def orbit(self, run_time: float = 4.0) -> Animation:
        return AnimationGroup(*(Rotate(e, TAU / (k + 1), about_point=self.nucleus.get_center(),
                                       run_time=run_time, rate_func=lambda t: t)
                                for k, e in enumerate(self.electrons)))

    def jump(self, shell_from: int, shell_to: int, color=None) -> Animation:
        electron = self.electrons[shell_from][-1]
        center = self.nucleus.get_center()
        r_to = self.shells[shell_to].get_width() / 2 if shell_to < len(self.shells) else \
            self.shells[-1].get_width() / 2 + 0.6
        d = electron.get_center() - center
        d = d / (np.linalg.norm(d) or 1)
        return electron.animate.move_to(center + d * r_to).set_color(color or get_theme().accent)
